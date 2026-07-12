# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1
#
# 反检测 —— AntiDetectGuard 协调器
#
# 给各平台 crawler 提供的统一入口。crawler 在关键节点调用:
#   guard = AntiDetectGuard(platform, page)
#   await guard.humanized_sleep(base)           # 拟人化停顿(替代 asyncio.sleep)
#   await guard.simulate_browse()               # 模拟浏览
#   result = await guard.check_risk()           # 截图风控感知
#   if result.is_risk: ...                      # 按策略处理
#
# ENABLE_ANTI_DETECT=False 时所有方法 no-op,完全不影响原行为。

import logging
from typing import Optional

import config
from anti_detect.backoff import BackoffStrategy, RiskControlError, handle_risk
from anti_detect.detector import detect_via_screenshot, detect_via_http_status
from anti_detect.humanize import humanized_sleep, simulate_page_browse
from anti_detect.types import RiskResult, RiskType

logger = logging.getLogger("anti_detect")


class AntiDetectGuard:
    """反检测协调器。每个 crawler 实例持有一个。

    用 base_crawler 的 disabled_guard() 获取 no-op 实例(未启用时)。
    """

    def __init__(self, platform: str, enabled: bool) -> None:
        self.platform = platform
        self.enabled = enabled
        self._page = None  # playwright Page(由 crawler 注入)
        self._backoff = BackoffStrategy(
            base_sec=getattr(config, "ANTI_DETECT_BACKOFF_BASE", 60),
            max_sec=getattr(config, "ANTI_DETECT_BACKOFF_MAX", 1800),
            risk_limit=getattr(config, "ANTI_DETECT_RISK_LIMIT", 3),
        )

    @classmethod
    def disabled(cls) -> "AntiDetectGuard":
        """构造禁用的 guard(no-op)"""
        return cls(platform="", enabled=False)

    def attach_page(self, page) -> None:
        """注入 playwright Page 对象(crawler 创建 context_page 后调用)"""
        self._page = page

    # ---- 行为拟人化 ----

    async def humanized_sleep(self, base_sec: float) -> None:
        """拟人化停顿(替代裸 asyncio.sleep)。未启用时仍 sleep base_sec(保持原行为)。"""
        if not self.enabled:
            import asyncio
            await asyncio.sleep(base_sec)
            return
        jitter = getattr(config, "HUMANIZE_SLEEP_JITTER", 0)
        actual = await humanized_sleep(base_sec, jitter)
        return None

    async def simulate_browse(self) -> None:
        """模拟人类浏览(停留+滚动)。未启用时 no-op。"""
        if not self.enabled:
            return
        stay = getattr(config, "HUMANIZE_PAGE_STAY_SEC", 3)
        scroll = getattr(config, "HUMANIZE_SCROLL_TIMES", 3)
        await simulate_page_browse(self._page, stay_sec=stay, scroll_times=scroll)

    # ---- 风控感知 ----

    async def check_risk(self) -> RiskResult:
        """截图 + LLM 识别风控。未启用/无 page 时返回 NORMAL。"""
        if not self.enabled or self._page is None:
            return RiskResult(RiskType.NORMAL, confidence=1.0, detail="anti-detect 未启用")
        if not getattr(config, "ANTI_DETECT_SCREENSHOT", True):
            return RiskResult(RiskType.NORMAL, confidence=1.0, detail="截图感知未启用")
        screenshot_dir = getattr(config, "ANTI_DETECT_SCREENSHOT_DIR", "")
        return await detect_via_screenshot(self._page, self.platform, screenshot_dir)

    def check_http_status(self, status_code: int) -> Optional[RiskResult]:
        """HTTP 状态码快速判定(471/461/403)。无风控返回 None。"""
        if not self.enabled:
            return None
        return detect_via_http_status(status_code)

    # ---- 风控处理 ----

    async def handle(self, result: RiskResult) -> str:
        """处理风控结果,返回动作指令。

        Returns:
            "continue" - 正常,继续
            "stop"     - 停止该账号(封禁级或达退避上限)
            "slider"   - 尝试过滑块
        """
        if not result.is_risk:
            self._backoff.reset()  # 正常 → 重置退避计数
            return "continue"

        # 记录风控
        logger.warning(f"[AntiDetect] {self.platform} 检测到风控: {result}")

        # 滑块 + 开启自动通过 → 尝试
        if (result.risk_type == RiskType.SLIDER_CAPTCHA
                and getattr(config, "ANTI_DETECT_AUTO_SLIDER", False)):
            from anti_detect.slider import try_pass_slider
            passed = await try_pass_slider(self._page)
            if passed:
                logger.info("[AntiDetect] 滑块已尝试通过,等待复检")
                return "continue"
            # 滑块失败 → 按策略退避或停止

        policy = getattr(config, "ANTI_DETECT_ON_RISK", "stop")
        action = await handle_risk(result, self._backoff, policy)
        return action

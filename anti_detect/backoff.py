# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1
#
# 反检测 —— 智能退避策略
#
# 检测到风控时的应对:
# - 指数退避:首次等 backoff_base,后续翻倍,上限 backoff_max
# - 连续 risk_limit 次风控 → 停止该账号(防止硬冲导致升级处置)
# - 与多账号池协同:停号后由 pool 切换下一个账号

import asyncio
from typing import Optional

from anti_detect.types import RiskResult, RiskType


class BackoffStrategy:
    """指数退避状态机。每个 crawler 实例持有一个。"""

    def __init__(self, base_sec: float = 60, max_sec: float = 1800, risk_limit: int = 3) -> None:
        self.base_sec = base_sec
        self.max_sec = max_sec
        self.risk_limit = risk_limit
        self.consecutive_risks = 0   # 连续风控计数
        self.current_wait = base_sec  # 当前退避时长(指数增长)

    def reset(self) -> None:
        """风控解除(成功请求)后重置计数"""
        self.consecutive_risks = 0
        self.current_wait = self.base_sec

    def record_risk(self) -> bool:
        """记录一次风控。返回是否应停止该账号(达 limit)。

        Returns:
            True = 已达上限,应停止;False = 还可退避重试
        """
        self.consecutive_risks += 1
        if self.consecutive_risks >= self.risk_limit:
            return True
        # 指数增长退避时长
        self.current_wait = min(self.current_wait * 2, self.max_sec)
        return False

    async def wait(self) -> float:
        """执行退避等待,返回实际等待秒数"""
        wait_sec = min(self.current_wait, self.max_sec)
        await asyncio.sleep(wait_sec)
        return wait_sec


class RiskControlError(Exception):
    """风控触发,需停止采集的自定义异常(供 main 编排器捕获切换账号)"""

    def __init__(self, result: RiskResult, action: str = "stop") -> None:
        self.risk_result = result
        self.action = action  # stop / backoff
        super().__init__(f"风控触发: {result.risk_type.value} - {result.detail}")


async def handle_risk(
    result: RiskResult,
    backoff: BackoffStrategy,
    on_risk_policy: str = "stop",
) -> str:
    """处理风控检测结果,返回动作指令。

    Args:
        result: 风控识别结果
        backoff: 退避状态机
        on_risk_policy: stop(默认,停止)或 backoff(退避重试)

    Returns:
        动作: "stop"(停止该账号) / "backoff"(退避后继续) / "slider"(尝试过滑块)
    """
    # 封禁级:立即停止,不退避
    if result.is_block_level:
        return "stop"

    # 验证码级 + 开启了自动滑块 → 尝试滑块
    if result.risk_type == RiskType.SLIDER_CAPTCHA:
        # 滑块尝试交由调用方执行(需要 page 对象),这里先返回指令
        return "slider"

    # 策略为 stop → 停止
    if on_risk_policy == "stop":
        return "stop"

    # 策略为 backoff → 退避重试,达上限则停
    should_stop = backoff.record_risk()
    if should_stop:
        return "stop"
    await backoff.wait()
    return "continue"

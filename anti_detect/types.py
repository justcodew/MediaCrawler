# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1
#
# 反检测 —— 风控类型定义
#
# LLM 识别截图后会返回这些风控类型之一,crawler 据此决定后续动作。

from enum import Enum
from typing import Optional


class RiskType(str, Enum):
    """LLM 识别出的页面风控类型"""
    NORMAL = "normal"              # 正常页面,无风控
    SLIDER_CAPTCHA = "slider"     # 滑块验证码
    SMS_CAPTCHA = "sms"           # 短信验证码
    IMAGE_CAPTCHA = "image"       # 图形验证码(数字/字母)
    LOGIN_EXPIRED = "login_expired"  # 登录失效/需重新登录
    RISK_BLOCK = "risk_block"     # 明确的风控/封禁提示(如"操作频繁""账号异常")
    UNKNOWN = "unknown"           # 无法判断


class RiskResult:
    """风控识别结果"""

    def __init__(self, risk_type: RiskType, confidence: float = 1.0,
                 detail: str = "", screenshot_path: str = "") -> None:
        self.risk_type = risk_type
        self.confidence = confidence   # LLM 置信度 0~1
        self.detail = detail           # LLM 给出的说明
        self.screenshot_path = screenshot_path

    @property
    def is_risk(self) -> bool:
        """是否检测到风险(非 NORMAL)"""
        return self.risk_type not in (RiskType.NORMAL,)

    @property
    def is_block_level(self) -> bool:
        """是否达到需立即停止的级别(封禁/登录失效)"""
        return self.risk_type in (RiskType.RISK_BLOCK, RiskType.LOGIN_EXPIRED)

    @property
    def is_captcha_level(self) -> bool:
        """是否为验证码级别(可尝试自动通过或等用户处理)"""
        return self.risk_type in (RiskType.SLIDER_CAPTCHA, RiskType.SMS_CAPTCHA, RiskType.IMAGE_CAPTCHA)

    def __repr__(self) -> str:
        return f"RiskResult(type={self.risk_type.value}, confidence={self.confidence:.2f}, detail={self.detail!r})"


# 各平台风险关键词(LLM 不可用时的本地兜底检测,基于页面文本)
# 用于在没有多模态 LLM 时,通过 page.content() 文本匹配做粗判
RISK_KEYWORDS = {
    "xhs": {
        RiskType.SLIDER_CAPTCHA: ["验证", "滑块", "拖动", "captcha", "verify"],
        RiskType.SMS_CAPTCHA: ["短信验证", "手机号验证", "发送验证码"],
        RiskType.RISK_BLOCK: ["操作频繁", "稍后再试", "异常", "限制", "blocked", "频繁"],
        RiskType.LOGIN_EXPIRED: ["登录", "重新登录", "login"],
    },
    "dy": {
        RiskType.SLIDER_CAPTCHA: ["验证", "滑块", "拖动", "captcha"],
        RiskType.RISK_BLOCK: ["操作频繁", "稍后再试", "异常", "风险"],
        RiskType.LOGIN_EXPIRED: ["登录", "重新登录"],
    },
    # 其余平台用通用关键词
    "_default": {
        RiskType.SLIDER_CAPTCHA: ["验证", "滑块", "拖动", "captcha", "verify"],
        RiskType.SMS_CAPTCHA: ["短信验证", "验证码"],
        RiskType.RISK_BLOCK: ["操作频繁", "稍后再试", "异常", "限制", "blocked", "风险"],
        RiskType.LOGIN_EXPIRED: ["登录", "重新登录", "login"],
    },
}


def get_risk_keywords(platform: str) -> dict:
    """取某平台的风险关键词表(无则用 _default)"""
    from anti_detect.types import RISK_KEYWORDS
    return RISK_KEYWORDS.get(platform, RISK_KEYWORDS["_default"])

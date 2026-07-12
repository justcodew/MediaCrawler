# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1
#
# 反检测模块 (Anti-Detect)
#
# 降低被平台识别为机器人的风险。包含三层防护:
#   1. 截图风控感知(LLM 多模态 + 本地兜底)
#   2. 行为拟人化(随机停顿 + 滚动 + 停留)
#   3. 智能退避(指数退避 + 连续风控停号)
#   4. 滑块自动通过(opencv,可选)
#
# 用法:
#   from anti_detect import AntiDetectGuard
#   guard = AntiDetectGuard("xhs", enabled=True)
#   guard.attach_page(page)
#   await guard.humanized_sleep(2)      # 替代 asyncio.sleep(2)
#   result = await guard.check_risk()   # 截图感知
#   action = await guard.handle(result) # 处理(stop/continue/slider)

from anti_detect.backoff import BackoffStrategy, RiskControlError
from anti_detect.guard import AntiDetectGuard
from anti_detect.types import RiskResult, RiskType

__all__ = ["AntiDetectGuard", "RiskResult", "RiskType", "RiskControlError", "BackoffStrategy"]

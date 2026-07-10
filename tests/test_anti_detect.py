# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1
#
# 反检测模块测试
#
# 验证:
# 1. AntiDetectGuard disabled 时所有方法 no-op
# 2. 行为拟人化:humanized_sleep 随机化
# 3. 风控类型判定:RiskResult.is_risk / is_block_level
# 4. 智能退避:指数增长 + 达上限停止
# 5. LLM 响应解析(不真实调 LLM)
# 6. HTTP 状态码判定

import asyncio
import time

import pytest


# ---------- disabled guard ----------

async def test_disabled_guard_noop():
    from anti_detect import AntiDetectGuard, RiskType
    g = AntiDetectGuard.disabled()
    assert g.enabled is False
    # humanized_sleep 应仍 sleep(disabled 时保持原行为)
    await g.humanized_sleep(0.01)  # 不抛即可
    # simulate_browse 应 no-op
    await g.simulate_browse()
    # check_risk 应返回 NORMAL
    r = await g.check_risk()
    assert r.risk_type == RiskType.NORMAL
    # check_http_status 应返回 None
    assert g.check_http_status(200) is None
    assert g.check_http_status(471) is None  # disabled 时不判定


# ---------- 行为拟人化 ----------

async def test_humanized_sleep_is_random():
    from anti_detect.humanize import humanized_sleep
    # 多次调用应产生不同时长(随机性)
    durations = [await humanized_sleep(0.1, jitter_sec=0.5) for _ in range(5)]
    assert all(d >= 0.1 for d in durations)
    # 至少有两次不同(随机性生效)
    assert len(set(round(d, 2) for d in durations)) > 1


async def test_simulate_browse_no_page():
    from anti_detect.humanize import simulate_page_browse
    # page=None 应不抛
    await simulate_page_browse(None, stay_sec=0, scroll_times=0)


# ---------- 风控类型判定 ----------

def test_risk_result_classification():
    from anti_detect import RiskResult, RiskType
    assert not RiskResult(RiskType.NORMAL).is_risk
    assert RiskResult(RiskType.SLIDER_CAPTCHA).is_risk
    assert RiskResult(RiskType.SLIDER_CAPTCHA).is_captcha_level
    assert not RiskResult(RiskType.SLIDER_CAPTCHA).is_block_level
    assert RiskResult(RiskType.RISK_BLOCK).is_block_level
    assert RiskResult(RiskType.LOGIN_EXPIRED).is_block_level


# ---------- 智能退避 ----------

async def test_backoff_exponential_and_limit():
    from anti_detect.backoff import BackoffStrategy
    b = BackoffStrategy(base_sec=0.01, max_sec=0.1, risk_limit=3)
    # 前2次:未达上限,返回 False
    assert b.record_risk() is False
    assert b.record_risk() is False
    # 退避时长应指数增长
    assert b.current_wait > 0.01
    # 第3次:达上限,返回 True(应停止)
    assert b.record_risk() is True
    # reset 后归零
    b.reset()
    assert b.consecutive_risks == 0


async def test_backoff_wait_actually_sleeps():
    from anti_detect.backoff import BackoffStrategy
    b = BackoffStrategy(base_sec=0.05, max_sec=0.1, risk_limit=3)
    t0 = time.time()
    actual = await b.wait()
    assert time.time() - t0 >= 0.04  # 确实 sleep 了
    assert actual >= 0.05


# ---------- 风控处理策略 ----------

async def test_handle_risk_normal_resets_backoff():
    from anti_detect import AntiDetectGuard, RiskResult, RiskType
    from anti_detect.backoff import BackoffStrategy
    g = AntiDetectGuard("xhs", enabled=True)
    g._backoff = BackoffStrategy(base_sec=0.01, max_sec=0.1, risk_limit=3)
    g._backoff.record_risk()  # 先制造一些风控计数
    # 正常结果应重置
    action = await g.handle(RiskResult(RiskType.NORMAL))
    assert action == "continue"
    assert g._backoff.consecutive_risks == 0


async def test_handle_risk_block_stops():
    from anti_detect import AntiDetectGuard, RiskResult, RiskType
    g = AntiDetectGuard("xhs", enabled=True)
    action = await g.handle(RiskResult(RiskType.RISK_BLOCK))
    assert action == "stop"


# ---------- LLM 响应解析 ----------

def test_parse_llm_response_normal():
    from anti_detect.detector import _parse_llm_response
    from anti_detect.types import RiskType
    r = _parse_llm_response('{"type": "normal", "confidence": 0.95, "detail": "正常"}')
    assert r.risk_type == RiskType.NORMAL and r.confidence == 0.95


def test_parse_llm_response_slider():
    from anti_detect.detector import _parse_llm_response
    from anti_detect.types import RiskType
    # 带 markdown 代码块的响应
    r = _parse_llm_response('```json\n{"type": "slider", "confidence": 0.9}\n```')
    assert r.risk_type == RiskType.SLIDER_CAPTCHA


def test_parse_llm_response_invalid():
    from anti_detect.detector import _parse_llm_response
    from anti_detect.types import RiskType
    r = _parse_llm_response("这不是JSON")
    assert r.risk_type == RiskType.UNKNOWN


# ---------- HTTP 状态码判定 ----------

def test_detect_http_status():
    from anti_detect.detector import detect_via_http_status
    from anti_detect.types import RiskType
    assert detect_via_http_status(200) is None
    assert detect_via_http_status(471).risk_type == RiskType.SLIDER_CAPTCHA
    assert detect_via_http_status(403).risk_type == RiskType.RISK_BLOCK


# ---------- 本地兜底文本检测 ----------

async def test_detect_via_text_risk_keyword():
    from anti_detect.detector import _detect_via_text
    from anti_detect.types import RiskType

    class FakePage:
        async def content(self):
            return "<html>操作频繁,请稍后再试</html>"
        async def evaluate(self, *a):
            return "操作频繁,请稍后再试"

    r = await _detect_via_text(FakePage(), "xhs")
    assert r.risk_type == RiskType.RISK_BLOCK
    assert "操作频繁" in r.detail

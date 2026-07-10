# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1
#
# 反检测 —— 截图风控感知
#
# 核心:截图当前页面 → LLM 多模态识别 → 返回 RiskResult
# 双通道:
#   1. LLM 通道(优先):截图 base64 → OpenAI 兼容多模态接口 → 结构化判断
#   2. 本地兜底(LLM 不可用时):page.content() 文本匹配风险关键词
#   3. HTTP 状态码兜底:471/461 等已知风控码直接判定

import asyncio
import base64
import os
import time
from typing import Optional

from anti_detect.types import RiskResult, RiskType, get_risk_keywords

#: LLM 识别用的提示词(要求返回结构化 JSON,便于解析)
VISION_PROMPT = """你是一个反爬虫风控识别专家。请分析这张网页截图,判断当前页面是否存在风控/验证机制。

请只返回一个 JSON 对象(不要其他内容),格式如下:
{
  "type": "normal | slider | sms | image | login_expired | risk_block | unknown",
  "confidence": 0.0~1.0,
  "detail": "简短说明(中文)"
}

类型说明:
- normal: 正常内容页,无任何风控
- slider: 滑块验证码(需要拖动滑块)
- sms: 短信验证码(要求输入手机验证码)
- image: 图形验证码(数字/字母点击)
- login_expired: 登录失效/要求重新登录
- risk_block: 明确的风控或封禁提示(如"操作频繁""账号异常""请稍后再试")
- unknown: 无法判断

只返回 JSON,不要解释。"""


async def detect_via_screenshot(page, platform: str, screenshot_dir: str = "") -> RiskResult:
    """截图 → 风控识别。

    优先级(三层,逐级降级):
      1. RapidOCR 提取截图文字 → 本地关键词库判定(纯本地、零成本、零延迟)
      2. LLM 多模态识别截图(OCR 失败/拿不准时兜底)
      3. 本地 page.content() 文本匹配(无截图时的最后兜底)

    Args:
        page: playwright Page 对象
        platform: 平台名(用于关键词匹配)
        screenshot_dir: 截图保存目录(空则不存盘)

    Returns:
        RiskResult
    """
    # 1. 截图
    screenshot_bytes = await _take_screenshot(page, screenshot_dir)

    # 2. 优先:OCR 提取文字 + 关键词判定
    if screenshot_bytes:
        ocr_result = await _detect_via_ocr(screenshot_bytes, platform)
        if ocr_result is not None and ocr_result.risk_type != RiskType.UNKNOWN:
            return ocr_result  # OCR 拿到了明确结论(正常或风控)

        # 3. OCR 失败/拿不准 → LLM 多模态兜底
        llm_result = await _detect_via_llm(screenshot_bytes)
        if llm_result is not None:
            return llm_result

    # 4. 都不可用 → 本地文本兜底
    return await _detect_via_text(page, platform)


async def _take_screenshot(page, screenshot_dir: str) -> Optional[bytes]:
    """截图,返回 bytes。失败返回 None。"""
    try:
        screenshot_bytes = await page.screenshot(type="png", full_page=False)
        # 可选存盘(供用户事后查看风控页面)
        if screenshot_dir and screenshot_bytes:
            os.makedirs(screenshot_dir, exist_ok=True)
            fname = f"risk_{int(time.time())}.png"
            with open(os.path.join(screenshot_dir, fname), "wb") as f:
                f.write(screenshot_bytes)
        return screenshot_bytes
    except Exception:
        return None


#: RapidOCR 引擎单例(懒加载,首次调用时初始化)
_rapidocr_engine = None


def _get_rapidocr():
    """懒加载 RapidOCR 引擎。未安装返回 None。"""
    global _rapidocr_engine
    if _rapidocr_engine is not None:
        return _rapidocr_engine
    try:
        # 优先用 rapidocr_onnxruntime(旧版稳定 API)
        from rapidocr_onnxruntime import RapidOCR
        _rapidocr_engine = RapidOCR()
        return _rapidocr_engine
    except ImportError:
        pass
    try:
        # 新版 rapidocr 2.x
        from rapidocr import RapidOCR
        _rapidocr_engine = RapidOCR()
        return _rapidocr_engine
    except ImportError:
        return None


async def _detect_via_ocr(screenshot_bytes: bytes, platform: str) -> Optional[RiskResult]:
    """用 RapidOCR(ppocr)提取截图文字 → 本地关键词库判定风控。

    纯本地、零成本、零延迟。RapidOCR 未安装返回 None(交由 LLM 兜底)。
    """
    import asyncio
    engine = _get_rapidocr()
    if engine is None:
        return None  # RapidOCR 未安装

    try:
        # RapidOCR 接受文件路径或 numpy 数组;这里用 numpy 数组(避免写临时文件)
        import numpy as np
        import cv2
        # bytes → numpy 数组
        nparr = np.frombuffer(screenshot_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            return None

        # 在线程池跑 OCR(避免阻塞事件循环,OCR 是 CPU 密集)
        def _run_ocr():
            result, _ = engine(img)
            return result

        loop = asyncio.get_event_loop()
        ocr_result = await loop.run_in_executor(None, _run_ocr)

        # 提取所有识别到的文字
        texts = []
        if ocr_result:
            for item in ocr_result:
                # result 每项格式:[box, text, score]
                if isinstance(item, (list, tuple)) and len(item) >= 2:
                    texts.append(str(item[1]))
        full_text = " ".join(texts)

        if not full_text.strip():
            # OCR 没识别到文字(可能页面是图片为主,或 OCR 失效)
            return RiskResult(RiskType.UNKNOWN, confidence=0.3,
                              detail="OCR 未识别到文字,建议 LLM 兜底")

        # 用关键词库判定
        return _match_keywords(full_text, platform)
    except Exception:
        return None


def _match_keywords(text: str, platform: str) -> RiskResult:
    """基于关键词库判定文本是否含风控提示。

    OCR 提取的文字或 page.content() 的文本都走这个判定。
    """
    text_lower = (text or "").lower()
    keywords = get_risk_keywords(platform)

    # 按严重度检查:先查封禁级,再查验证码级
    for risk_type in [RiskType.RISK_BLOCK, RiskType.LOGIN_EXPIRED,
                      RiskType.SMS_CAPTCHA, RiskType.SLIDER_CAPTCHA]:
        words = keywords.get(risk_type, [])
        for w in words:
            if w.lower() in text_lower:
                return RiskResult(risk_type, confidence=0.85,
                                  detail=f"OCR/文本匹配到关键词: {w}")

    # 没匹配到任何风控关键词 → 正常
    return RiskResult(RiskType.NORMAL, confidence=0.8,
                      detail=f"OCR 识别 {len(text)} 字符,未发现风控关键词")


async def _detect_via_llm(screenshot_bytes: bytes) -> Optional[RiskResult]:
    """用多模态 LLM 识别截图。LLM 不可用/未配置返回 None(交由兜底)。"""
    try:
        from agent.config import is_configured, get_llm_config
        if not is_configured():
            return None

        import httpx
        cfg = get_llm_config()
        b64 = base64.b64encode(screenshot_bytes).decode("utf-8")

        payload = {
            "model": cfg["model"],
            "messages": [
                {"role": "user", "content": [
                    {"type": "text", "text": VISION_PROMPT},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                ]},
            ],
            "temperature": 0.1,  # 风控判定要确定性,低温
            "max_tokens": 200,
        }
        headers = {"Authorization": f"Bearer {cfg['api_key']}", "Content-Type": "application/json"}
        url = cfg["base_url"].rstrip("/") + "/chat/completions"
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"].strip()

        return _parse_llm_response(content)
    except Exception:
        return None  # 任何异常都降级到本地兜底


def _parse_llm_response(content: str) -> RiskResult:
    """解析 LLM 返回的 JSON"""
    import json
    # 容错:LLM 可能在 JSON 外包了 markdown 代码块
    text = content.strip().strip("`").strip()
    if text.startswith("json"):
        text = text[4:].strip()
    try:
        data = json.loads(text)
        rtype_str = data.get("type", "unknown").lower()
        # 映射到枚举
        type_map = {
            "normal": RiskType.NORMAL, "slider": RiskType.SLIDER_CAPTCHA,
            "sms": RiskType.SMS_CAPTCHA, "image": RiskType.IMAGE_CAPTCHA,
            "login_expired": RiskType.LOGIN_EXPIRED, "risk_block": RiskType.RISK_BLOCK,
            "unknown": RiskType.UNKNOWN,
        }
        return RiskResult(
            risk_type=type_map.get(rtype_str, RiskType.UNKNOWN),
            confidence=float(data.get("confidence", 0.8)),
            detail=data.get("detail", ""),
        )
    except (json.JSONDecodeError, ValueError):
        return RiskResult(RiskType.UNKNOWN, confidence=0.3, detail=f"LLM 响应解析失败: {content[:80]}")


async def _detect_via_text(page, platform: str) -> RiskResult:
    """本地兜底:基于页面文本的关键词匹配(无截图时的最后手段)。"""
    try:
        content = await page.content()
        # 取纯文本(去标签)
        text = await page.evaluate("() => document.body.innerText") if hasattr(page, "evaluate") else content
    except Exception:
        return RiskResult(RiskType.UNKNOWN, confidence=0.2, detail="无法读取页面内容")

    # 复用统一的关键词匹配
    return _match_keywords(text, platform)


def detect_via_http_status(status_code: int) -> Optional[RiskResult]:
    """基于 HTTP 状态码的快速判定(471/461 是小红书的风控验证码码)。

    返回 None 表示状态码无风控含义。
    """
    if status_code in (471, 461):
        return RiskResult(RiskType.SLIDER_CAPTCHA, confidence=0.9,
                          detail=f"HTTP {status_code}: 触发验证码")
    if status_code == 403:
        return RiskResult(RiskType.RISK_BLOCK, confidence=0.8,
                          detail="HTTP 403: 被拒绝访问")
    return None

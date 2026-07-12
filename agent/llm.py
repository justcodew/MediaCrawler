# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1
#
# AI 内容分析 Agent —— LLM 调用封装
#
# 走 OpenAI 兼容接口(httpx 直连,不强制依赖 openai SDK,降低安装负担)。
# 支持 OpenAI / DeepSeek / 智谱 / 通义千问等兼容 /v1/chat/completions 的服务。

import json
from typing import Dict, List, Optional

import httpx

from agent.config import get_llm_config


async def chat(messages: List[Dict[str, str]], **overrides) -> str:
    """调用 LLM chat completions,返回助手回复文本。

    messages: OpenAI 风格的 [{role, content}, ...]
    overrides: 可覆盖 model/temperature 等
    """
    cfg = get_llm_config()
    cfg.update({k: v for k, v in overrides.items() if v is not None})

    if not cfg["api_key"]:
        raise RuntimeError("LLM_API_KEY 未配置,请在 .env 设置 LLM_API_KEY / LLM_BASE_URL / LLM_MODEL")

    payload = {
        "model": cfg["model"],
        "messages": messages,
        "temperature": cfg["temperature"],
        "max_tokens": cfg["max_tokens"],
    }
    headers = {
        "Authorization": f"Bearer {cfg['api_key']}",
        "Content-Type": "application/json",
    }
    url = cfg["base_url"].rstrip("/") + "/chat/completions"
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()
    return data["choices"][0]["message"]["content"]

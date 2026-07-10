# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1
#
# AI 内容分析 Agent —— 配置
#
# LLM 走 OpenAI 兼容接口(支持 OpenAI / DeepSeek / 智谱 / 通义千问等兼容 API)。
# 配置从环境变量读取(可用 .env)。

import os


def get_llm_config() -> dict:
    return {
        "api_key": os.getenv("LLM_API_KEY", ""),
        "base_url": os.getenv("LLM_BASE_URL", "https://api.openai.com/v1"),
        "model": os.getenv("LLM_MODEL", "gpt-4o-mini"),
        "temperature": float(os.getenv("LLM_TEMPERATURE", "0.7")),
        "max_tokens": int(os.getenv("LLM_MAX_TOKENS", "2000")),
    }


def is_configured() -> bool:
    return bool(get_llm_config()["api_key"])

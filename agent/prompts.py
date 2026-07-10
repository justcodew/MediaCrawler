# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1
#
# AI 内容分析 Agent —— 提示词模板
#
# 让 LLM 把自媒体内容拆解为「爆款元素」,输出结构化报告。

SYSTEM_PROMPT = """你是一位资深的自媒体内容分析师,擅长拆解爆款内容的底层逻辑。
你会从选题方向、情绪价值、内容结构、钩子设计、目标受众等维度分析内容,
并给出可复用的创作建议。请用中文回答。"""

REMIX_PROMPT_TEMPLATE = """请分析以下自媒体内容,拆解它的爆款元素:

{content}

请按以下结构输出分析报告(用 Markdown):

## 选题分析
- 核心选题方向:
- 切入角度:
- 选题亮点:

## 情绪价值
- 触发的核心情绪(如共鸣/好奇/焦虑/认同等):
- 情绪触发点:

## 内容结构
- 整体结构(如总分总/故事线/对比等):
- 节奏安排:

## 钩子设计
- 标题钩子:
- 开头钩子(前3秒/前2行):

## 互动分析
- 引导互动的手法:
- 数据表现解读:

## 可复用建议
- 3 条可迁移到其他赛道的创作建议:
1.
2.
3.

请基于实际内容给出具体、可操作的分析,避免空泛套话。"""


def build_remix_prompt(content: str) -> str:
    return REMIX_PROMPT_TEMPLATE.format(content=content)

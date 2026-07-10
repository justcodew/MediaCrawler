# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1
#
# AI 内容分析 Agent —— 内容拆解工作流 (ContentRemix)
#
# 工作流:加载内容 → 结构化(转文本) → LLM 拆解 → 渲染报告
#
# 优先用 LangGraph 编排(若安装);否则用纯 async 函数链实现等价流程,
# 保证无 LangGraph 也能运行(LangGraph 仅作为可选编排框架)。

import json
import time
from pathlib import Path
from typing import Dict, List, Optional

from agent import data_loader, prompts
from agent.llm import chat

#: 报告输出目录
_REPORT_DIR = Path(__file__).resolve().parent.parent / "data" / "analysis_reports"


async def analyze_content(platform: str, note_id: str) -> Dict:
    """分析单条内容,返回结构化结果。

    Returns:
        {note_id, platform, content_text, report, ts}
    """
    contents = data_loader.load_contents(platform, limit=200, note_ids=[note_id])
    if not contents:
        raise ValueError(f"未找到 {platform} 平台的内容: {note_id}")
    item = contents[0]
    content_text = data_loader.content_to_text(item)
    report = await _run_remix(content_text)
    return {
        "note_id": note_id,
        "platform": platform,
        "content_text": content_text,
        "report": report,
        "ts": int(time.time()),
    }


async def analyze_contents(platform: str, note_ids: Optional[List[str]] = None, limit: int = 5) -> List[Dict]:
    """批量分析(默认取最近 limit 条)"""
    contents = data_loader.load_contents(platform, limit=limit if not note_ids else 200, note_ids=note_ids)
    if not contents:
        raise ValueError(f"未找到 {platform} 平台的内容")
    results = []
    for item in contents[:limit]:
        content_text = data_loader.content_to_text(item)
        try:
            report = await _run_remix(content_text)
        except Exception as e:
            report = f"_分析失败: {e}_"
        results.append({
            "note_id": item.get("_id", ""),
            "platform": platform,
            "content_text": content_text,
            "report": report,
            "ts": int(time.time()),
        })
    return results


async def _run_remix(content_text: str) -> str:
    """执行拆解:优先 LangGraph,否则纯 async。

    LangGraph 版把流程建模为节点(load/analyze),便于后续扩展(如加"生成选题"节点)。
    """
    try:
        return await _run_remix_langgraph(content_text)
    except ImportError:
        # LangGraph 未安装,走纯 async 实现
        return await _run_remix_plain(content_text)


async def _run_remix_plain(content_text: str) -> str:
    """纯 async 实现:直接调 LLM"""
    messages = [
        {"role": "system", "content": prompts.SYSTEM_PROMPT},
        {"role": "user", "content": prompts.build_remix_prompt(content_text)},
    ]
    return await chat(messages)


# ---------- LangGraph 版(可选) ----------

async def _run_remix_langgraph(content_text: str) -> str:
    """用 LangGraph StateGraph 编排。未安装 langgraph 时抛 ImportError 由上层 fallback。"""
    from langgraph.graph import StateGraph, END
    from typing import TypedDict

    class RemixState(TypedDict, total=False):
        content_text: str
        messages: List[Dict[str, str]]
        report: str

    async def load_node(state: RemixState) -> RemixState:
        state["messages"] = [
            {"role": "system", "content": prompts.SYSTEM_PROMPT},
            {"role": "user", "content": prompts.build_remix_prompt(state["content_text"])},
        ]
        return state

    async def analyze_node(state: RemixState) -> RemixState:
        state["report"] = await chat(state["messages"])
        return state

    graph = StateGraph(RemixState)
    graph.add_node("load", load_node)
    graph.add_node("analyze", analyze_node)
    graph.set_entry_point("load")
    graph.add_edge("load", "analyze")
    graph.add_edge("analyze", END)
    app = graph.compile()

    result = await app.ainvoke({"content_text": content_text})
    return result["report"]


# ---------- 报告持久化 ----------

def save_report(result: Dict) -> str:
    """保存分析报告到 data/analysis_reports/,返回文件路径"""
    _REPORT_DIR.mkdir(parents=True, exist_ok=True)
    fname = f"{result['platform']}_{result['note_id']}_{result['ts']}.json"
    fpath = _REPORT_DIR / fname
    with open(fpath, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    return str(fpath)


def list_reports() -> List[Dict]:
    """列出已生成的报告"""
    if not _REPORT_DIR.exists():
        return []
    reports = []
    for fpath in sorted(_REPORT_DIR.glob("*.json"), reverse=True):
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                reports.append(json.load(f))
        except (json.JSONDecodeError, OSError):
            continue
    return reports


def get_report(report_id: str) -> Optional[Dict]:
    """按文件名(不含路径)读取单个报告"""
    fpath = _REPORT_DIR / report_id
    if not fpath.exists():
        return None
    with open(fpath, "r", encoding="utf-8") as f:
        return json.load(f)

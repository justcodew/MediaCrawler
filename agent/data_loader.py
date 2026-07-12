# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1
#
# AI 内容分析 Agent —— 数据加载器
#
# 从已抓取的数据(data/ 目录或 DB)读取内容,供 Agent 拆解分析。
# 优先读 data/ 下的 jsonl/json/csv(与 AsyncFileWriter 的产物格式一致)。

import csv
import glob
import json
import os
from pathlib import Path
from typing import Dict, List, Optional

#: 项目根
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_DATA_DIR = _PROJECT_ROOT / "data"

#: data/ 下的非平台目录(系统生成的子目录,不应当作平台)
_NON_PLATFORM_DIRS = {"analysis_reports", ".cache", "media"}


def list_platforms() -> List[str]:
    """列出 data/ 下有数据的平台目录"""
    if not _DATA_DIR.exists():
        return []
    return sorted([
        d.name for d in _DATA_DIR.iterdir()
        if d.is_dir() and not d.name.startswith(".") and d.name not in _NON_PLATFORM_DIRS
    ])


def list_content_files(platform: str) -> List[str]:
    """列出某平台的 contents 类文件(jsonl/json/csv)"""
    base = _DATA_DIR / platform
    if not base.exists():
        return []
    files = []
    for ext in ("*.jsonl", "*.json", "*.csv"):
        files.extend(glob.glob(str(base / "**" / ext), recursive=True))
    # 过滤出 contents 文件(排除 comments)
    return sorted([f for f in files if "comment" not in os.path.basename(f).lower()])


def load_contents(platform: str, limit: int = 50, note_ids: Optional[List[str]] = None) -> List[Dict]:
    """加载某平台的内容列表。

    Args:
        platform: 平台名(xhs/douyin/...)
        limit: 最多返回多少条
        note_ids: 可选,只返回这些 id 的内容(用于指定笔记拆解)
    """
    files = list_content_files(platform)
    if not files:
        return []
    contents: List[Dict] = []
    want_ids = set(note_ids) if note_ids else None
    for fpath in files:
        rows = _read_file(fpath)
        for row in rows:
            # 统一 id 字段名(各平台不同:note_id/aweme_id/video_id/content_id ...)
            rid = (row.get("note_id") or row.get("aweme_id") or row.get("video_id")
                   or row.get("content_id") or row.get("tid") or "")
            row["_id"] = str(rid)
            if want_ids is not None and str(rid) not in want_ids:
                continue
            contents.append(row)
            if len(contents) >= limit:
                return contents
    return contents


def _read_file(fpath: str) -> List[Dict]:
    """根据扩展名读取文件为 dict 列表"""
    ext = os.path.splitext(fpath)[1].lower()
    if ext == ".jsonl":
        rows = []
        with open(fpath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        rows.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        return rows
    if ext == ".json":
        with open(fpath, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else [data]
    if ext == ".csv":
        with open(fpath, "r", encoding="utf-8-sig", newline="") as f:
            return list(csv.DictReader(f))
    return []


def content_to_text(item: Dict) -> str:
    """把一条内容转成供 LLM 分析的纯文本(拼接标题/描述/标签等)"""
    title = item.get("title") or item.get("desc") or ""
    desc = item.get("desc") or item.get("content") or item.get("description") or ""
    tags = item.get("tag_list") or ""
    liked = item.get("liked_count") or item.get("digg_count") or item.get("like_count") or 0
    collected = item.get("collected_count") or 0
    comment = item.get("comment_count") or 0
    parts = [
        f"【标题】{title}" if title else "",
        f"【正文】{desc}" if desc else "",
        f"【标签】{tags}" if tags else "",
        f"【互动】点赞{liked} 收藏{collected} 评论{comment}",
    ]
    return "\n".join(p for p in parts if p)

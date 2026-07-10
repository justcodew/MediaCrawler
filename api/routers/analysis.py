# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1
#
# AI 内容分析 Agent —— API 路由
#
# 端点:
#   GET  /api/analysis/platforms       列出有数据的平台
#   GET  /api/analysis/contents        列出某平台可分析的内容(preview)
#   POST /api/analysis/remix           触发内容拆解(单条/批量)
#   GET  /api/analysis/reports         列出已生成报告
#   GET  /api/analysis/reports/{rid}   读取单个报告

import asyncio
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from agent import config as agent_config, content_remix, data_loader

router = APIRouter(prefix="/analysis", tags=["analysis"])


class RemixRequest(BaseModel):
    platform: str = Field(..., description="平台")
    note_ids: Optional[List[str]] = Field(None, description="指定分析的 note_id 列表;空则取最近 limit 条")
    limit: int = Field(5, description="批量分析条数(仅 note_ids 为空时生效)", ge=1, le=20)
    save: bool = Field(True, description="是否保存报告到 data/analysis_reports/")


class RemixResponse(BaseModel):
    status: str = "ok"
    configured: bool
    results: List[dict]


@router.get("/platforms")
async def get_platforms():
    """列出 data/ 下有数据的平台"""
    return {"platforms": data_loader.list_platforms()}


@router.get("/contents")
async def get_contents(platform: str, limit: int = 20):
    """列出某平台可分析的内容(预览,不含 LLM 分析)"""
    items = data_loader.load_contents(platform, limit=limit)
    return {
        "platform": platform,
        "total": len(items),
        "items": [
            {
                "note_id": it.get("_id", ""),
                "title": it.get("title") or (it.get("desc", "")[:40] if it.get("desc") else ""),
                "liked_count": it.get("liked_count") or it.get("digg_count") or 0,
            }
            for it in items
        ],
    }


@router.post("/remix", response_model=RemixResponse)
async def remix(req: RemixRequest):
    """触发内容拆解分析"""
    if not agent_config.is_configured():
        raise HTTPException(
            status_code=503,
            detail="LLM 未配置。请在 .env 设置 LLM_API_KEY / LLM_BASE_URL / LLM_MODEL",
        )
    try:
        results = await content_remix.analyze_contents(
            req.platform, note_ids=req.note_ids, limit=req.limit
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")

    if req.save:
        for r in results:
            content_remix.save_report(r)

    return RemixResponse(configured=True, results=results)


@router.get("/reports")
async def get_reports():
    """列出已生成报告"""
    reports = content_remix.list_reports()
    # 仅返回摘要,正文太长
    return {
        "total": len(reports),
        "reports": [
            {
                "platform": r.get("platform"),
                "note_id": r.get("note_id"),
                "ts": r.get("ts"),
                "report_preview": (r.get("report", "")[:120] + "...") if len(r.get("report", "")) > 120 else r.get("report", ""),
            }
            for r in reports
        ],
    }


@router.get("/reports/{rid}")
async def get_report(rid: str):
    """读取单个报告(rid 为文件名,如 xhs_abc123_1234567890.json)"""
    report = content_remix.get_report(rid)
    if report is None:
        raise HTTPException(status_code=404, detail=f"报告不存在: {rid}")
    return report

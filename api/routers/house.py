# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1
#
# 好房雷达(house_pro)对接 API
#
# 端点:
#   GET  /api/house/listings    读取 MediaCrawler 已采集数据,返回 house_pro Listing 格式
#   POST /api/house/export      把已采集数据转成 Listing 格式,写到 house_pro 目录(文件落盘)
#   GET  /api/house/platforms   列出有数据的平台
#
# 数据流:
#   MediaCrawler 采集 → data/<platform>/jsonl/ (原始格式)
#   本接口读取 → house_adapter 转换 → 返回 Listing JSON / 写到 HOUSE_RAW_DIR

import glob
import json
import os
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from house_adapter.converter import to_listing_batch, PLATFORM_TO_SOURCE

router = APIRouter(prefix="/house", tags=["house"])

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))


def _load_platform_data(platform: str, limit: int = 100) -> list[dict]:
    """读取某平台已采集的 jsonl 数据"""
    data_dir = os.path.join(_PROJECT_ROOT, "data", platform)
    if not os.path.isdir(data_dir):
        return []
    notes = []
    # 搜 contents 类文件(排除 comments)
    for pattern in ("**/*contents*.jsonl", "**/*contents*.json", "**/search_contents*.jsonl"):
        for fpath in glob.glob(os.path.join(data_dir, pattern), recursive=True):
            try:
                with open(fpath, encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            notes.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
            except Exception:
                continue
            if len(notes) >= limit:
                break
    return notes[:limit]


class ExportRequest(BaseModel):
    """文件落盘请求"""
    platform: str = Field("xhs", description="MediaCrawler 平台标识(xhs/douban/...)")
    output_dir: str = Field("", description="输出目录(空则用 config.HOUSE_RAW_DIR)")
    limit: int = Field(100, ge=1, le=500)


class ExportResponse(BaseModel):
    status: str = "ok"
    platform: str
    source: str  # house_pro 的 source 字段值
    exported: int
    output_file: str


@router.get("/platforms")
async def get_platforms():
    """列出有已采集数据的平台"""
    import config
    platforms = []
    data_root = os.path.join(_PROJECT_ROOT, "data")
    if os.path.isdir(data_root):
        for d in os.listdir(data_root):
            full = os.path.join(data_root, d)
            if os.path.isdir(full) and not d.startswith(".") and d not in ("risk_screenshots", "analysis_reports"):
                # 检查有没有 jsonl 文件
                has_data = bool(glob.glob(os.path.join(full, "**", "*.jsonl"), recursive=True))
                if has_data:
                    platforms.append({
                        "platform": d,
                        "source": PLATFORM_TO_SOURCE.get(d, d),
                    })
    return {"platforms": platforms}


@router.get("/listings")
async def get_listings(
    platform: str = "xhs",
    limit: int = 100,
    only_with_price: bool = False,
):
    """读取已采集数据,返回 house_pro Listing 格式的 JSON。

    Args:
        platform: MediaCrawler 平台标识
        limit: 最多返回条数
        only_with_price: 只返回提取到价格的房源
    """
    notes = _load_platform_data(platform, limit=limit * 2)  # 多读一些,过滤后可能减少
    if not notes:
        raise HTTPException(status_code=404, detail=f"平台 {platform} 无已采集数据")

    listings = to_listing_batch(notes, platform)
    if only_with_price:
        listings = [l for l in listings if l.get("price")]
    listings = listings[:limit]

    return {
        "platform": platform,
        "source": PLATFORM_TO_SOURCE.get(platform, platform),
        "total": len(listings),
        "listings": listings,
    }


@router.post("/export", response_model=ExportResponse)
async def export_to_house(req: ExportRequest):
    """把已采集数据转成 Listing 格式,写到 house_pro 目录(文件落盘模式)。

    house_pro 的 Celery 定时扫该目录做 ETL 入库。
    """
    import config
    notes = _load_platform_data(req.platform, limit=req.limit)
    if not notes:
        raise HTTPException(status_code=404, detail=f"平台 {req.platform} 无已采集数据")

    listings = to_listing_batch(notes, req.platform)

    # 输出目录:优先用请求参数,其次 config
    output_dir = req.output_dir or getattr(config, "HOUSE_RAW_DIR", "")
    if not output_dir:
        raise HTTPException(status_code=400, detail="未指定 output_dir,且 config.HOUSE_RAW_DIR 为空")

    os.makedirs(output_dir, exist_ok=True)
    source = PLATFORM_TO_SOURCE.get(req.platform, req.platform)
    # 文件名格式与 house_pro 期望一致:<source>_<timestamp>.jsonl
    import time
    fname = f"{source}_{int(time.time())}.jsonl"
    output_file = os.path.join(output_dir, fname)

    with open(output_file, "w", encoding="utf-8") as f:
        for listing in listings:
            f.write(json.dumps(listing, ensure_ascii=False) + "\n")

    return ExportResponse(
        platform=req.platform,
        source=source,
        exported=len(listings),
        output_file=output_file,
    )

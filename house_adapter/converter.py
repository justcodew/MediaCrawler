# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1
#
# 数据格式转换:MediaCrawler note → house_pro Listing
# 把各平台采集的原始数据 + extractor 提取的结构化字段,转成 house_pro 能直接入库的格式。

from __future__ import annotations

from typing import Any

from house_adapter.extractor import extract_listing_fields, is_probably_agent

#: 平台名映射(MediaCrawler 平台标识 → house_pro source 字段)
PLATFORM_TO_SOURCE = {
    "xhs": "xiaohongshu",
    "douban": "douban",
    "wb": "weibo",
    "zhihu": "zhihu",
    "dy": "douyin",
    "ks": "kuaishou",
    "bili": "bilibili",
    "tieba": "tieba",
}


def _get_id_field(note: dict) -> str:
    """从 note 里取平台原始 ID(各平台字段名不同)"""
    for key in ("note_id", "topic_id", "aweme_id", "video_id", "content_id", "mblog_id"):
        val = note.get(key)
        if val:
            return str(val)
    return ""


def _get_content(note: dict) -> str:
    """取正文内容"""
    for key in ("desc", "content", "description"):
        val = note.get(key)
        if val:
            return str(val)
    return ""


def to_listing(note: dict, platform: str) -> dict[str, Any]:
    """把一条 MediaCrawler note 转成 house_pro Listing 格式。

    Args:
        note: MediaCrawler 采集的原始数据(xhs/douban/weibo 等)
        platform: MediaCrawler 平台标识(xhs/douban/...)

    Returns:
        house_pro Listing 格式的 dict(含结构化字段,可直接入库)
    """
    source = PLATFORM_TO_SOURCE.get(platform, platform)
    source_id = _get_id_field(note)
    title = note.get("title", "") or ""
    content = _get_content(note)
    images_raw = note.get("image_list", "") or note.get("images", "") or ""
    image_urls = [u.strip() for u in str(images_raw).split(",") if u.strip()]

    # 提取结构化字段
    fields = extract_listing_fields(content, title)
    is_agent = is_probably_agent(content, title)

    # 时间戳 → ISO(house_pro posted_at 期望 datetime)
    posted_ts = note.get("time") or note.get("create_time") or note.get("last_update_time")
    posted_at = None
    if posted_ts and isinstance(posted_ts, (int, float)) and posted_ts > 0:
        from datetime import datetime, timezone
        # 毫秒级时间戳(>1e12)转成秒
        ts = int(posted_ts)
        if ts > 1e12:
            ts = ts // 1000
        try:
            posted_at = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
        except (ValueError, OSError):
            posted_at = None

    return {
        "source": source,
        "source_id": source_id,
        "source_url": note.get("note_url", "") or note.get("url", ""),
        "poster_id": note.get("creator_hash", "") or note.get("user_id", ""),
        "poster_name": note.get("nickname", "") or note.get("user_nickname", ""),
        "title": title,
        "content": content,
        "image_urls": image_urls,
        "posted_at": posted_at,
        # 结构化字段(extractor 提取)
        "price": fields["price"],
        "price_unit": "元/月",
        "size_sqm": fields["size_sqm"],
        "layout": fields["layout"],
        "area_name": fields["area_name"],
        "location_detail": None,
        "floor_info": fields["floor_info"],
        "orientation": fields["orientation"],
        "contact_info": fields["contact_info"],
        # 元信息
        "status": "active",
        "raw_data": {
            "note": note,
            "is_agent_initial": is_agent,
            "fields_pre_extracted": True,  # 标记:house_pro ETL 可跳过 extractor
        },
    }


def to_listing_batch(notes: list[dict], platform: str) -> list[dict[str, Any]]:
    """批量转换"""
    return [to_listing(n, platform) for n in notes if _get_id_field(n)]

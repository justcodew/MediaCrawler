# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1
#
# 断点续爬 —— 独立 sqlite 存储引擎
#
# 用独立 sqlite 库(database/checkpoints.db)而非主库,避免:
# 1. 与 SAVE_DATA_OPTION 耦合(jsonl/csv 模式也能续爬)
# 2. 主库 schema 迁移的兼容性风险

import json
import os
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from checkpoint.models import Base, CrawlCheckpoint, CrawlTask

#: checkpoint 专用 sqlite 路径(与主 sqlite 库分离)
_DB_PATH = str(Path(__file__).resolve().parent.parent / "database" / "checkpoints.db")
_DB_URL = f"sqlite+aiosqlite:///{_DB_PATH}"

_engine = None
_SessionFactory = None


def _ensure_dir() -> None:
    os.makedirs(os.path.dirname(_DB_PATH), exist_ok=True)


async def _get_session() -> AsyncSession:
    global _engine, _SessionFactory
    _ensure_dir()
    if _engine is None:
        _engine = create_async_engine(_DB_URL, echo=False)
        async with _engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        _SessionFactory = sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)
    return _SessionFactory()


# ---------- 任务管理 ----------

async def create_task(platform: str, crawler_type: str, config_snapshot: Optional[Dict] = None) -> str:
    """创建一个爬虫任务,返回 task_id"""
    task_id = uuid.uuid4().hex
    now = int(time.time())
    session = await _get_session()
    try:
        task = CrawlTask(
            task_id=task_id,
            platform=platform,
            crawler_type=crawler_type,
            config_snapshot=json.dumps(config_snapshot or {}, ensure_ascii=False),
            status="running",
            started_at=now,
        )
        session.add(task)
        await session.commit()
        return task_id
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


async def get_task(task_id: str) -> Optional[Dict]:
    """读取任务信息"""
    session = await _get_session()
    try:
        task = await session.get(CrawlTask, task_id)
        if task is None:
            return None
        return {
            "task_id": task.task_id,
            "platform": task.platform,
            "crawler_type": task.crawler_type,
            "status": task.status,
            "started_at": task.started_at,
            "finished_at": task.finished_at,
        }
    finally:
        await session.close()


async def mark_task_status(task_id: str, status: str, error_msg: str = "") -> None:
    session = await _get_session()
    try:
        task = await session.get(CrawlTask, task_id)
        if task:
            task.status = status
            if status in ("completed", "failed"):
                task.finished_at = int(time.time())
            if error_msg:
                task.error_msg = error_msg
            await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


# ---------- 断点读写 ----------

async def save_checkpoint(
    task_id: str,
    platform: str,
    scope: str,
    last_page: int,
    processed_note_ids: Optional[List[str]] = None,
    last_search_id: str = "",
    last_cursor: str = "",
) -> None:
    """保存/更新一个 scope 的断点(upsert)"""
    now = int(time.time())
    session = await _get_session()
    try:
        stmt = select(CrawlCheckpoint).where(
            CrawlCheckpoint.task_id == task_id,
            CrawlCheckpoint.scope == scope,
        )
        result = await session.execute(stmt)
        cp = result.scalar_one_or_none()
        if cp is None:
            cp = CrawlCheckpoint(
                task_id=task_id, platform=platform, scope=scope,
                last_page=last_page, last_search_id=last_search_id,
                last_cursor=last_cursor, processed_note_ids="[]", updated_ts=now,
            )
            session.add(cp)
        else:
            cp.last_page = last_page
            cp.last_search_id = last_search_id
            cp.last_cursor = last_cursor
            cp.updated_ts = now
        if processed_note_ids is not None:
            cp.processed_note_ids = json.dumps(processed_note_ids, ensure_ascii=False)
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


async def load_checkpoint(task_id: str, scope: str) -> Optional[Dict]:
    """读取一个 scope 的断点,无则返回 None"""
    session = await _get_session()
    try:
        stmt = select(CrawlCheckpoint).where(
            CrawlCheckpoint.task_id == task_id,
            CrawlCheckpoint.scope == scope,
        )
        result = await session.execute(stmt)
        cp = result.scalar_one_or_none()
        if cp is None:
            return None
        return {
            "last_page": cp.last_page or 0,
            "last_search_id": cp.last_search_id or "",
            "last_cursor": cp.last_cursor or "",
            "processed_note_ids": json.loads(cp.processed_note_ids or "[]"),
        }
    finally:
        await session.close()


async def add_processed_note_ids(task_id: str, scope: str, note_ids: List[str]) -> None:
    """把新增的 note_id 追加到 processed_note_ids(自动去重)"""
    session = await _get_session()
    try:
        stmt = select(CrawlCheckpoint).where(
            CrawlCheckpoint.task_id == task_id,
            CrawlCheckpoint.scope == scope,
        )
        result = await session.execute(stmt)
        cp = result.scalar_one_or_none()
        if cp is None:
            # 不存在则建一条(页码未知,仅记 note_id)
            cp = CrawlCheckpoint(
                task_id=task_id, platform="", scope=scope,
                last_page=0, processed_note_ids="[]", updated_ts=int(time.time()),
            )
            session.add(cp)
        existing = set(json.loads(cp.processed_note_ids or "[]"))
        existing.update(note_ids)
        cp.processed_note_ids = json.dumps(sorted(existing), ensure_ascii=False)
        cp.updated_ts = int(time.time())
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()

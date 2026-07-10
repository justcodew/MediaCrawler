# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1
#
# 多账号 —— 账号池存储引擎(独立 sqlite: database/accounts.db)
#
# 与 checkpoint 一样用独立库,避免与 SAVE_DATA_OPTION 耦合。

import json
import os
import time
from pathlib import Path
from typing import List, Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from account.types import (
    STATUS_ACTIVE, STATUS_COOLING, STATUS_DISABLED, STATUS_IN_USE,
    Account, AccountInfo, account_orm_to_info,
)

_DB_PATH = str(Path(__file__).resolve().parent.parent / "database" / "accounts.db")
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
            await conn.run_sync(Account.metadata.create_all)
        _SessionFactory = sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)
    return _SessionFactory()


# ---------- CRUD ----------

async def add_account(info: AccountInfo) -> int:
    """新增账号,返回主键 id"""
    now = int(time.time())
    session = await _get_session()
    try:
        acc = Account(
            account_id=info.account_id, platform=info.platform, nickname=info.nickname,
            cookies=info.cookies, user_agent=info.user_agent, status=STATUS_ACTIVE,
            proxy_config=json.dumps(info.proxy_config, ensure_ascii=False) if info.proxy_config else "",
            add_ts=now,
        )
        session.add(acc)
        await session.commit()
        return acc.id
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


async def list_accounts(platform: Optional[str] = None, status: Optional[str] = None) -> List[AccountInfo]:
    """列出账号(可按平台/状态过滤)"""
    session = await _get_session()
    try:
        stmt = select(Account)
        if platform:
            stmt = stmt.where(Account.platform == platform)
        if status:
            stmt = stmt.where(Account.status == status)
        result = await session.execute(stmt.order_by(Account.id))
        return [account_orm_to_info(r) for r in result.scalars()]
    finally:
        await session.close()


async def get_available_account(platform: str) -> Optional[AccountInfo]:
    """取一个 active 账号(按 last_used_ts 升序,优先用最久没用的)"""
    session = await _get_session()
    try:
        stmt = (select(Account)
                .where(Account.platform == platform, Account.status == STATUS_ACTIVE)
                .order_by(Account.last_used_ts.asc().nulls_first()))
        result = await session.execute(stmt.limit(1))
        acc = result.scalar_one_or_none()
        return account_orm_to_info(acc) if acc else None
    finally:
        await session.close()


async def set_status(
    db_id: int,
    status: str,
    error_msg: str = "",
    *,
    is_success: bool = False,
    is_failure: bool = False,
) -> int:
    """更新账号状态,返回更新后的 fail_count。

    - is_success=True:成功归还,重置 fail_count=0,累加 success_count
    - is_failure=True:失败,累加 fail_count(不在此处决定 cooling,由调用方按阈值判定)
    - 普通状态切换(如 in_use/cooling/disabled):只更新 status
    """
    now = int(time.time())
    session = await _get_session()
    try:
        values: dict = {"status": status, "last_used_ts": now}
        if is_success:
            values["fail_count"] = 0
            values["success_count"] = Account.success_count + 1
        if is_failure:
            values["fail_count"] = Account.fail_count + 1
        if error_msg:
            values["last_error"] = error_msg
        await session.execute(update(Account).where(Account.id == db_id).values(**values))
        await session.commit()
        # 读回最新 fail_count
        acc = await session.get(Account, db_id)
        return (acc.fail_count if acc else 0) or 0
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


async def delete_account(db_id: int) -> None:
    session = await _get_session()
    try:
        acc = await session.get(Account, db_id)
        if acc:
            await session.delete(acc)
            await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()

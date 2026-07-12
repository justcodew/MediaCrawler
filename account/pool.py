# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1
#
# 多账号 —— AccountPool 账号池
#
# 用法(在 main 编排器里):
#   pool = AccountPool("xhs", enabled=True, fail_threshold=3)
#   while account := await pool.acquire():
#       crawler = build_crawler_for(account)
#       try:
#           await crawler.start()
#           await pool.release(account, success=True)
#       except AccountBlockedError:
#           await pool.release(account, success=False, error="blocked")
#           continue   # 切换下一个账号
#
# 失败计数达 fail_threshold 自动 cooling(冷却时间见 COOLING_SECONDS),
# 池内账号全部 cooling/disabled 时 acquire 返回 None(池耗尽)。

import asyncio
import time
from typing import Optional

from account import store
from account.types import (
    STATUS_ACTIVE, STATUS_COOLING, STATUS_DISABLED,
    AccountInfo,
)

#: 默认连续失败阈值:达到后账号进入 cooling
DEFAULT_FAIL_THRESHOLD = 3
#: cooling 状态的冷却秒数(超过后自动恢复 active)
COOLING_SECONDS = 600


class AccountPool:
    """账号池。enabled=False 时退化为单账号模式(acquire 返回 None)。"""

    def __init__(self, platform: str, enabled: bool, fail_threshold: int = DEFAULT_FAIL_THRESHOLD) -> None:
        self.platform = platform
        self.enabled = enabled
        self.fail_threshold = fail_threshold
        self._lock = asyncio.Lock()  # 串行化 acquire/release,避免同一账号被并发取用

    async def acquire(self) -> Optional[AccountInfo]:
        """取一个可用账号并标记 in_use。池耗尽返回 None。

        会先把超过冷却期的 cooling 账号恢复为 active(基于 last_used_ts 判定,
        即使进程重启过也能正确恢复——不依赖后台任务)。
        """
        if not self.enabled:
            return None
        async with self._lock:
            await self._revive_cooled_accounts()
            account = await store.get_available_account(self.platform)
            if account is None:
                return None
            await store.set_status(account.db_id, "in_use")
            account._status = "in_use"
            return account

    async def release(self, account: AccountInfo, success: bool, error: str = "") -> None:
        """归还账号:成功则 active(重置失败计数);失败则累加计数,达阈值则 cooling。"""
        if not self.enabled or account is None:
            return
        async with self._lock:
            if success:
                await store.set_status(account.db_id, STATUS_ACTIVE, is_success=True)
                account.fail_count = 0
                return
            # 失败:累加 fail_count,拿回最新计数
            fail_count = await store.set_status(
                account.db_id, STATUS_ACTIVE, error_msg=error or "failed", is_failure=True
            )
            account.fail_count = fail_count
            # 达阈值 → 进入 cooling(冷却期内不会被 acquire)
            if fail_count >= self.fail_threshold:
                import logging
                logging.getLogger("account").info(
                    f"[AccountPool] account {account.account_id} reached fail threshold "
                    f"({fail_count}/{self.fail_threshold}), entering cooling"
                )
                await store.set_status(account.db_id, STATUS_COOLING, error_msg=error or "cooling")
                # 安排冷却后自动恢复(后台任务,不阻塞主流程)
                asyncio.create_task(self._cooling_recover(account.db_id))

    async def mark_failed(self, account: AccountInfo, error: str = "") -> None:
        """标记账号失败并按阈值决定 cooling/disabled。与 release(success=False) 等价。"""
        await self.release(account, success=False, error=error)

    async def disable(self, account: AccountInfo, reason: str = "") -> None:
        """永久禁用某账号(如确认封号)"""
        if not self.enabled:
            return
        await store.set_status(account.db_id, STATUS_DISABLED, error_msg=reason or "disabled")

    async def size(self) -> int:
        """池内 active 账号数(立即可用总数;cooling 不计)"""
        if not self.enabled:
            return 0
        active = await store.list_accounts(self.platform, STATUS_ACTIVE)
        return len(active)

    async def _cooling_recover(self, db_id: int) -> None:
        """冷却期过后把账号恢复为 active(后台任务,加速恢复)。

        主要恢复机制是 _revive_cooled_accounts(基于时间,进程重启也有效);
        本任务作为进程存活时的快速恢复补充。
        """
        await asyncio.sleep(COOLING_SECONDS)
        try:
            await store.set_status(db_id, STATUS_ACTIVE, is_success=True)
        except Exception:
            pass

    async def _revive_cooled_accounts(self) -> None:
        """把超过冷却期的 cooling 账号恢复为 active(基于 last_used_ts,进程重启也有效)。"""
        try:
            await store.revive_cooled_accounts(self.platform, COOLING_SECONDS)
        except Exception:
            pass  # 恢复失败不阻塞 acquire

    @classmethod
    def disabled(cls) -> "AccountPool":
        """禁用的池(acquire 永远返回 None)"""
        return cls(platform="", enabled=False)

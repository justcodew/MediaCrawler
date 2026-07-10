# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1
#
# 断点续爬 —— CheckpointManager
#
# 给各平台 crawler 提供的高层接口。crawler 在分页循环里:
#   1. 开始某 keyword/creator 前:ckpt = manager.begin_scope(scope) → 取断点(决定起始页/游标/已处理ID)
#   2. 每页结束后:manager.save_page(scope, page, note_ids, search_id=..., cursor=...)
#   3. 整个任务结束:manager.complete()
#
# 若 ENABLE_RESUME=False 或无 task_id,manager 退化为 no-op,不影响原有逻辑。

from typing import Dict, List, Optional

from checkpoint import store


class ScopeState:
    """单 scope 的内存态(减少 DB 读)"""

    def __init__(self) -> None:
        self.last_page: int = 0          # 已完成的最后一页
        self.search_id: str = ""         # xhs search_id(续爬需复用)
        self.cursor: str = ""            # creator 翻页游标
        self.processed: set = set()      # 已处理 note_id(去重跳过)


class CheckpointManager:
    """断点续爬管理器。ENABLE_RESUME=False 时所有方法 no-op。"""

    def __init__(self, task_id: str, platform: str, enabled: bool) -> None:
        self.task_id = task_id
        self.platform = platform
        self.enabled = enabled
        self._scopes: Dict[str, ScopeState] = {}

    @classmethod
    def disabled(cls) -> "CheckpointManager":
        """构造一个禁用的 manager(无 task_id,纯 no-op)"""
        return cls(task_id="", platform="", enabled=False)

    async def begin_scope(self, scope: str) -> ScopeState:
        """开始一个 scope 的爬取,返回其状态(含断点恢复信息)。

        - enabled=False:返回空状态(起始页0、无 search_id)
        - enabled=True 且有断点:返回上次断点状态

        注:此方法为 async,因为要从 DB 读取断点。在 crawler 的 async 上下文中调用。
        """
        if not self.enabled:
            self._scopes[scope] = ScopeState()
            return self._scopes[scope]

        state = ScopeState()
        cp = await store.load_checkpoint(self.task_id, scope)
        if cp:
            state.last_page = cp["last_page"]
            state.search_id = cp["last_search_id"]
            state.cursor = cp["last_cursor"]
            state.processed = set(cp["processed_note_ids"])
        self._scopes[scope] = state
        return state

    async def save_page(
        self,
        scope: str,
        page: int,
        new_note_ids: Optional[List[str]] = None,
        search_id: str = "",
        cursor: str = "",
    ) -> None:
        """记录某页已完成(page 从1开始,new_note_ids 追加到已处理集合)"""
        if not self.enabled:
            return
        state = self._scopes.get(scope)
        if state is None:
            state = ScopeState()
            self._scopes[scope] = state
        state.last_page = page
        if search_id:
            state.search_id = search_id
        if cursor:
            state.cursor = cursor
        if new_note_ids:
            state.processed.update(new_note_ids)
        await store.save_checkpoint(
            task_id=self.task_id,
            platform=self.platform,
            scope=scope,
            last_page=page,
            processed_note_ids=list(state.processed),
            last_search_id=state.search_id,
            last_cursor=state.cursor,
        )

    def is_processed(self, scope: str, note_id: str) -> bool:
        """note_id 是否已处理过(用于 detail/creator 跳过)"""
        if not self.enabled:
            return False
        state = self._scopes.get(scope)
        return bool(state and note_id in state.processed)

    async def complete(self, error_msg: str = "") -> None:
        """标记任务完成/失败"""
        if not self.enabled or not self.task_id:
            return
        await store.mark_task_status(
            self.task_id,
            status="failed" if error_msg else "completed",
            error_msg=error_msg,
        )

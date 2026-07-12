# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1
#
# 断点续爬测试
#
# 验证:
# 1. CheckpointManager 在 enabled=False 时所有方法 no-op
# 2. create_task/get_task/mark_task_status 任务生命周期
# 3. save_page/load_checkpoint 断点读写 + note_id 累积去重
# 4. 续爬场景:begin_scope 恢复上次 page/search_id/processed

import asyncio
import os
import shutil
import tempfile

import pytest

# 把 checkpoint 的 sqlite 路径重定向到临时目录,避免污染真实库
_TMP_DIR = tempfile.mkdtemp(prefix="mc_ckpt_test_")
import checkpoint.store as _store
_store._DB_PATH = os.path.join(_TMP_DIR, "checkpoints.db")
_store._DB_URL = f"sqlite+aiosqlite:///{_store._DB_PATH}"
_store._engine = None
_store._SessionFactory = None


def teardown_module():
    shutil.rmtree(_TMP_DIR, ignore_errors=True)


# ---------- disabled manager ----------

async def test_disabled_manager_is_noop():
    from checkpoint import CheckpointManager
    m = CheckpointManager.disabled()
    assert m.enabled is False
    s = await m.begin_scope("kw1")
    assert s.last_page == 0 and s.search_id == "" and len(s.processed) == 0
    await m.save_page("kw1", 5, ["n1"], search_id="sid")  # 应 no-op,不抛
    assert m.is_processed("kw1", "n1") is False  # disabled 永远 False
    await m.complete()  # 不抛


# ---------- 任务生命周期 ----------

async def test_task_lifecycle():
    from checkpoint import store
    tid = await store.create_task("xhs", "search", {"keywords": "a,b"})
    task = await store.get_task(tid)
    assert task is not None
    assert task["platform"] == "xhs"
    assert task["status"] == "running"
    await store.mark_task_status(tid, "completed")
    task = await store.get_task(tid)
    assert task["status"] == "completed"
    assert task["finished_at"] is not None


async def test_get_task_not_found():
    from checkpoint import store
    assert await store.get_task("nonexistent") is None


# ---------- 断点读写 ----------

async def test_save_load_checkpoint():
    from checkpoint import store
    tid = await store.create_task("xhs", "search")
    await store.save_checkpoint(tid, "xhs", "kw1", last_page=3,
                                processed_note_ids=["n1", "n2"], last_search_id="sid99")
    cp = await store.load_checkpoint(tid, "kw1")
    assert cp is not None
    assert cp["last_page"] == 3
    assert cp["last_search_id"] == "sid99"
    assert set(cp["processed_note_ids"]) == {"n1", "n2"}


async def test_checkpoint_upsert_and_accumulate():
    from checkpoint import store
    tid = await store.create_task("xhs", "search")
    # 第一次写
    await store.save_checkpoint(tid, "xhs", "kw1", last_page=1, processed_note_ids=["n1"])
    # 第二次更新同一 scope(应 upsert,不新建行)
    await store.save_checkpoint(tid, "xhs", "kw1", last_page=2, processed_note_ids=["n1", "n2"])
    cp = await store.load_checkpoint(tid, "kw1")
    assert cp["last_page"] == 2
    assert set(cp["processed_note_ids"]) == {"n1", "n2"}


# ---------- CheckpointManager 续爬恢复 ----------

async def test_manager_resume_restores_state():
    from checkpoint import CheckpointManager
    # 模拟第一次运行:跑到第3页,处理了 n1/n2/n3,search_id=sid
    tid = await _store.create_task("xhs", "search")
    m1 = CheckpointManager(tid, "xhs", enabled=True)
    await m1.begin_scope("kw1")
    await m1.save_page("kw1", 1, ["n1"], search_id="sid")
    await m1.save_page("kw1", 2, ["n2"], search_id="sid")
    await m1.save_page("kw1", 3, ["n3"], search_id="sid")
    await m1.complete()

    # 模拟续爬:新 manager 同 task_id,begin_scope 应恢复
    m2 = CheckpointManager(tid, "xhs", enabled=True)
    state = await m2.begin_scope("kw1")
    assert state.last_page == 3           # 续爬从第4页开始
    assert state.search_id == "sid"       # search_id 复用(关键!)
    assert state.processed == {"n1", "n2", "n3"}
    # is_processed 应识别已处理项
    assert m2.is_processed("kw1", "n1") is True
    assert m2.is_processed("kw1", "n999") is False


async def test_manager_disabled_skips_db():
    """disabled manager 不应触发任何 DB 操作"""
    from checkpoint import CheckpointManager
    m = CheckpointManager.disabled()
    state = await m.begin_scope("any")
    await m.save_page("any", 10, ["x"] * 100)
    assert state.last_page == 0  # disabled 不更新内存状态
    # DB 里不应有 task_id="" 的记录(因 manager.disabled 的 task_id 为空)

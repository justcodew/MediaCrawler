# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1
#
# 多账号账号池测试
#
# 验证:
# 1. AccountPool disabled 时 acquire 返回 None
# 2. add_account / list_accounts / get_available_account CRUD
# 3. acquire 标记 in_use,串行取用不重复
# 4. release(success) 恢复 active;release(fail) 累计失败
# 5. CSV 导入/导出往返
# 6. resolve_user_data_dir_name 多账号隔离

import os
import shutil
import tempfile

import pytest

# 重定向 account sqlite 到临时目录
_TMP = tempfile.mkdtemp(prefix="mc_acc_test_")
import account.store as _store
_store._DB_PATH = os.path.join(_TMP, "accounts.db")
_store._DB_URL = f"sqlite+aiosqlite:///{_store._DB_PATH}"
_store._engine = None
_store._SessionFactory = None


def teardown_module():
    shutil.rmtree(_TMP, ignore_errors=True)


from account import AccountInfo, AccountPool, store  # noqa: E402


# ---------- disabled pool ----------

async def test_disabled_pool_acquire_returns_none():
    pool = AccountPool.disabled()
    assert await pool.acquire() is None
    assert await pool.size() == 0


# ---------- CRUD ----------

async def test_add_and_list_accounts():
    await store.add_account(AccountInfo("a1", "xhs", cookies="c1", nickname="acc1"))
    await store.add_account(AccountInfo("a2", "xhs", cookies="c2", nickname="acc2"))
    accounts = await store.list_accounts(platform="xhs")
    assert len(accounts) == 2
    ids = {a.account_id for a in accounts}
    assert ids == {"a1", "a2"}


async def test_get_available_picks_least_recently_used():
    await store.add_account(AccountInfo("b1", "dy"))
    await store.add_account(AccountInfo("b2", "dy"))
    acc = await store.get_available_account("dy")
    assert acc is not None
    assert acc.account_id in {"b1", "b2"}


# ---------- pool acquire/release ----------

async def test_pool_acquire_marks_in_use():
    await store.add_account(AccountInfo("c1", "ks", cookies="ck1"))
    pool = AccountPool("ks", enabled=True)
    acc = await pool.acquire()
    assert acc is not None
    # 再取应无可用(in_use 不算 active)
    acc2 = await pool.acquire()
    assert acc2 is None


async def test_pool_release_success_restores_active():
    await store.add_account(AccountInfo("d1", "wb"))
    pool = AccountPool("wb", enabled=True)
    acc = await pool.acquire()
    await pool.release(acc, success=True)
    # 释放后应可再次取到
    acc2 = await pool.acquire()
    assert acc2 is not None


async def test_pool_release_failure_accumulates():
    await store.add_account(AccountInfo("e1", "zhihu"))
    pool = AccountPool("zhihu", enabled=True, fail_threshold=3)
    acc = await pool.acquire()
    await pool.release(acc, success=False, error="risk")
    # 仍 active(失败计数未达阈值)
    acc2 = await pool.acquire()
    assert acc2 is not None


# ---------- CSV import/export ----------

async def test_csv_roundtrip(tmp_path):
    from account.manager import import_from_csv, export_to_csv
    csv_in = tmp_path / "in.csv"
    csv_in.write_text(
        "platform,account_id,nickname,cookies,user_agent,proxy_http,proxy_https\n"
        "xhs,f1,noteF,web_session=zz,,http://proxy:8080,\n"
        "xhs,f2,noteG,a1=yy,,,\n",
        encoding="utf-8-sig",
    )
    n = await import_from_csv(str(csv_in))
    assert n == 2
    csv_out = tmp_path / "out.csv"
    exported = await export_to_csv(str(csv_out), platform="xhs")
    assert exported >= 2
    content = csv_out.read_text(encoding="utf-8-sig")
    assert "f1" in content and "proxy:8080" in content


# ---------- user_data_dir 隔离 ----------

def _has_playwright():
    try:
        import playwright  # noqa: F401
        return True
    except Exception:
        return False


@pytest.mark.skipif(not _has_playwright(), reason="tools.crawler_util 依赖 playwright")
def test_resolve_user_data_dir_isolation():
    from tools.crawler_util import resolve_user_data_dir_name
    # 单账号
    assert resolve_user_data_dir_name("xhs") == "xhs_user_data_dir"
    # 多账号:带 account
    class FakeAcc:
        account_id = "acc999"
    name = resolve_user_data_dir_name("xhs", FakeAcc())
    assert name == "xhs_acc999_user_data_dir"


def test_account_info_user_data_dir_name():
    info = AccountInfo("acc1", "xhs")
    assert info.user_data_dir_name.endswith("xhs_acc1_user_data_dir")

# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Repository: https://github.com/NanmiCoder/MediaCrawler/blob/main/main.py
# GitHub: https://github.com/NanmiCoder
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1
#

# 声明：本代码仅供学习和研究目的使用。使用者应遵守以下原则：
# 1. 不得用于任何商业用途。
# 2. 使用时应遵守目标平台的使用条款和robots.txt规则。
# 3. 不得进行大规模爬取或对平台造成运营干扰。
# 4. 应合理控制请求频率，避免给目标平台带来不必要的负担。
# 5. 不得用于任何非法或不当的用途。
#
# 详细许可条款请参阅项目根目录下的LICENSE文件。
# 使用本代码即表示您同意遵守上述原则和LICENSE中的所有条款。

import sys
import io

# Force UTF-8 encoding for stdout/stderr to prevent encoding errors
# when outputting Chinese characters in non-UTF-8 terminals
if sys.stdout and hasattr(sys.stdout, 'buffer'):
    if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
if sys.stderr and hasattr(sys.stderr, 'buffer'):
    if sys.stderr.encoding and sys.stderr.encoding.lower() != 'utf-8':
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import asyncio
from typing import Optional, Type

import cmd_arg
import config
from database import db
from base.base_crawler import AbstractCrawler
from media_platform.bilibili import BilibiliCrawler
from media_platform.douyin import DouYinCrawler
from media_platform.kuaishou import KuaishouCrawler
from media_platform.tieba import TieBaCrawler
from media_platform.weibo import WeiboCrawler
from media_platform.xhs import XiaoHongShuCrawler
from media_platform.zhihu import ZhihuCrawler
from tools.async_file_writer import AsyncFileWriter
from var import crawler_type_var


class CrawlerFactory:
    CRAWLERS: dict[str, Type[AbstractCrawler]] = {
        "xhs": XiaoHongShuCrawler,
        "dy": DouYinCrawler,
        "ks": KuaishouCrawler,
        "bili": BilibiliCrawler,
        "wb": WeiboCrawler,
        "tieba": TieBaCrawler,
        "zhihu": ZhihuCrawler,
    }

    @staticmethod
    def create_crawler(platform: str) -> AbstractCrawler:
        crawler_class = CrawlerFactory.CRAWLERS.get(platform)
        if not crawler_class:
            supported = ", ".join(sorted(CrawlerFactory.CRAWLERS))
            raise ValueError(f"Invalid media platform: {platform!r}. Supported: {supported}")
        return crawler_class()


crawler: Optional[AbstractCrawler] = None


def _flush_excel_if_needed() -> None:
    if config.SAVE_DATA_OPTION != "excel":
        return

    try:
        from store.excel_store_base import ExcelStoreBase

        ExcelStoreBase.flush_all()
        print("[Main] Excel files saved successfully")
    except Exception as e:
        print(f"[Main] Error flushing Excel data: {e}")


async def _generate_wordcloud_if_needed() -> None:
    if config.SAVE_DATA_OPTION not in ("json", "jsonl") or not config.ENABLE_GET_WORDCLOUD:
        return

    try:
        file_writer = AsyncFileWriter(
            platform=config.PLATFORM,
            crawler_type=crawler_type_var.get(),
        )
        await file_writer.generate_wordcloud_from_comments()
    except Exception as e:
        print(f"[Main] Error generating wordcloud: {e}")


async def main() -> None:
    global crawler

    args = await cmd_arg.parse_cmd()
    if args.init_db:
        await db.init_db(args.init_db)
        print(f"Database {args.init_db} initialized successfully.")
        return

    # 数据库保存模式下自动建表，避免首次运行时出现 no such table 错误
    if config.SAVE_DATA_OPTION in ("sqlite", "mysql", "db", "postgres"):
        await db.init_db(config.SAVE_DATA_OPTION)

    # 多账号模式:从账号池轮转;否则单账号(原行为)
    if getattr(config, "ENABLE_ACCOUNT_POOL", False):
        await _run_with_account_pool()
    else:
        crawler = CrawlerFactory.create_crawler(platform=config.PLATFORM)
        await _run_crawler(crawler)

    _flush_excel_if_needed()

    # Generate wordcloud after crawling is complete
    # Only for JSON save mode
    await _generate_wordcloud_if_needed()


async def _run_crawler(c: AbstractCrawler, checkpoint_manager=None) -> None:
    """运行单个 crawler 实例。

    checkpoint_manager:若传入(多账号模式在编排层统一创建),直接注入;
    否则按 ENABLE_RESUME 自行创建/恢复(单账号模式)。
    """
    global crawler
    crawler = c  # 让 async_cleanup/_force_stop 引用的全局 crawler 指向当前实例

    # 断点续爬:注入 CheckpointManager
    if checkpoint_manager is not None:
        # 多账号模式:复用编排层已创建的 manager(所有账号共享同一 task_id)
        c.checkpoint_manager = checkpoint_manager
        crawler_type_var.set(config.CRAWLER_TYPE)
        await c.start()
    elif getattr(config, "ENABLE_RESUME", False):
        from checkpoint import CheckpointManager, store as ckpt_store
        resume_id = getattr(config, "RESUME_TASK_ID", "") or ""
        if resume_id:
            task = await ckpt_store.get_task(resume_id)
            if task is None:
                print(f"[Main] Resume task_id {resume_id!r} not found, starting a new task.")
                task_id = await ckpt_store.create_task(
                    config.PLATFORM, config.CRAWLER_TYPE,
                    {"keywords": config.KEYWORDS, "start_page": config.START_PAGE},
                )
            else:
                task_id = resume_id
                await ckpt_store.mark_task_status(task_id, "running")
            print(f"[Main] Resuming task: {task_id}")
        else:
            task_id = await ckpt_store.create_task(
                config.PLATFORM, config.CRAWLER_TYPE,
                {"keywords": config.KEYWORDS, "start_page": config.START_PAGE},
            )
            print(f"[Main] New task created: {task_id} (use --resume {task_id} to resume)")
        c.checkpoint_manager = CheckpointManager(task_id, config.PLATFORM, enabled=True)
        crawler_type_var.set(config.CRAWLER_TYPE)
        try:
            await c.start()
            await c.checkpoint_manager.complete()
        except Exception as e:
            await c.checkpoint_manager.complete(error_msg=str(e))
            raise
    else:
        await c.start()


async def _run_with_account_pool() -> None:
    """多账号编排:从账号池取账号 → 为每账号建独立 crawler(独立 user_data_dir) → 跑一轮 → 归还。

    失败(风控)时自动切换下一账号;池耗尽则退出。
    并发度由 config.ACCOUNT_CONCURRENCY 控制(默认1=串行轮转)。
    断点续爬:所有账号共享同一个 task_id(在编排层统一创建)。
    """
    from account import AccountPool
    from account.manager import import_from_csv, import_from_excel

    # 可选:启动时从文件导入账号
    import_file = getattr(config, "ACCOUNTS_IMPORT_FILE", "") or ""
    if import_file:
        try:
            if import_file.lower().endswith(".csv"):
                n = await import_from_csv(import_file)
            else:
                n = await import_from_excel(import_file)
            print(f"[Main] Imported {n} accounts from {import_file}")
        except Exception as e:
            print(f"[Main] Import accounts failed: {e}")

    pool = AccountPool(
        config.PLATFORM, enabled=True,
        fail_threshold=getattr(config, "ACCOUNT_POOL_FAIL_THRESHOLD", 3),
    )
    total = await pool.size()
    concurrency = max(1, getattr(config, "ACCOUNT_CONCURRENCY", 1))
    print(f"[Main] Account pool: {total} available account(s) for {config.PLATFORM}, concurrency={concurrency}")
    if total == 0:
        print("[Main] Account pool empty, fallback to single-account mode")
        await _run_crawler(CrawlerFactory.create_crawler(platform=config.PLATFORM))
        return

    # 断点续爬:在编排层统一创建 task_id,所有账号共享(避免碎片化)
    checkpoint_manager = None
    if getattr(config, "ENABLE_RESUME", False):
        from checkpoint import CheckpointManager, store as ckpt_store
        resume_id = getattr(config, "RESUME_TASK_ID", "") or ""
        if resume_id:
            task = await ckpt_store.get_task(resume_id)
            task_id = resume_id if task else await ckpt_store.create_task(
                config.PLATFORM, config.CRAWLER_TYPE,
                {"keywords": config.KEYWORDS, "start_page": config.START_PAGE},
            )
            if task:
                await ckpt_store.mark_task_status(task_id, "running")
        else:
            task_id = await ckpt_store.create_task(
                config.PLATFORM, config.CRAWLER_TYPE,
                {"keywords": config.KEYWORDS, "start_page": config.START_PAGE},
            )
        print(f"[Main] Shared checkpoint task: {task_id}")
        checkpoint_manager = CheckpointManager(task_id, config.PLATFORM, enabled=True)

    # 并发模式:用 semaphore 限制并发度,多账号同时跑
    if concurrency > 1:
        await _run_accounts_concurrent(pool, concurrency, checkpoint_manager)
    else:
        await _run_accounts_serial(pool, checkpoint_manager)

    # 断点续爬:任务完成
    if checkpoint_manager is not None:
        await checkpoint_manager.complete()


async def _run_accounts_serial(pool, checkpoint_manager) -> None:
    """串行轮转:一次用一个账号,失败切下一个,成功或池耗尽则结束。"""
    while True:
        account = await pool.acquire()
        if account is None:
            print("[Main] Account pool exhausted (no active account).")
            return
        print(f"[Main] Using account: {account.nickname} ({account.account_id})")
        c = CrawlerFactory.create_crawler(platform=config.PLATFORM)
        c._account_info = account  # 供 crawler 内部按账号隔离 user_data_dir/cookie
        try:
            await _run_crawler(c, checkpoint_manager=checkpoint_manager)
            await pool.release(account, success=True)
            print(f"[Main] Account {account.account_id} finished successfully")
            return  # 任务完成
        except Exception as e:
            await pool.mark_failed(account, error=str(e))
            print(f"[Main] Account {account.account_id} failed: {e}, rotating to next...")
            continue


async def _run_accounts_concurrent(pool, concurrency: int, checkpoint_manager) -> None:
    """并发模式:同时用 concurrency 个账号跑(各账号独立 user_data_dir)。

    注意:并发模式下 checkpoint 共享同一 task_id,多账号可能并发写同一 scope 的断点,
    故并发模式建议配合不同 keyword 分片,或关闭断点续爬。
    """
    sem = asyncio.Semaphore(concurrency)

    async def worker():
        while True:
            account = await pool.acquire()
            if account is None:
                return
            async with sem:
                print(f"[Main] Using account: {account.nickname} ({account.account_id})")
                c = CrawlerFactory.create_crawler(platform=config.PLATFORM)
                c._account_info = account
                try:
                    await _run_crawler(c, checkpoint_manager=checkpoint_manager)
                    await pool.release(account, success=True)
                    print(f"[Main] Account {account.account_id} finished successfully")
                except Exception as e:
                    await pool.mark_failed(account, error=str(e))
                    print(f"[Main] Account {account.account_id} failed: {e}")

    # 启动 concurrency 个 worker,直到所有账号用完
    workers = [asyncio.create_task(worker()) for _ in range(concurrency)]
    await asyncio.gather(*workers, return_exceptions=True)


async def async_cleanup() -> None:
    global crawler
    if crawler:
        if getattr(crawler, "cdp_manager", None):
            try:
                await crawler.cdp_manager.cleanup(force=True)
            except Exception as e:
                error_msg = str(e).lower()
                if "closed" not in error_msg and "disconnected" not in error_msg:
                    print(f"[Main] Error cleaning up CDP browser: {e}")

        elif getattr(crawler, "browser_context", None):
            try:
                await crawler.browser_context.close()
            except Exception as e:
                error_msg = str(e).lower()
                if "closed" not in error_msg and "disconnected" not in error_msg:
                    print(f"[Main] Error closing browser context: {e}")

    if config.SAVE_DATA_OPTION in ("db", "sqlite"):
        await db.close()

if __name__ == "__main__":
    from tools.app_runner import run

    def _force_stop() -> None:
        c = crawler
        if not c:
            return
        cdp_manager = getattr(c, "cdp_manager", None)
        launcher = getattr(cdp_manager, "launcher", None)
        if not launcher:
            return
        try:
            launcher.cleanup()
        except Exception:
            pass

    run(main, async_cleanup, cleanup_timeout_seconds=15.0, on_first_interrupt=_force_stop)

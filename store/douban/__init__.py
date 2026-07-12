# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1
# 豆瓣数据存储工厂

import config
from base.base_crawler import AbstractStore
from typing import List
from ._store_impl import (
    DoubanCsvStoreImplement, DoubanDbStoreImplement, DoubanJsonStoreImplement,
    DoubanJsonlStoreImplement, DoubanSqliteStoreImplement, DoubanMongoStoreImplement,
    DoubanExcelStoreImplement,
)


class DoubanStoreFactory:
    STORES = {
        "csv": DoubanCsvStoreImplement,
        "db": DoubanDbStoreImplement,
        "postgres": DoubanDbStoreImplement,
        "json": DoubanJsonStoreImplement,
        "jsonl": DoubanJsonlStoreImplement,
        "sqlite": DoubanSqliteStoreImplement,
        "mongodb": DoubanMongoStoreImplement,
        "excel": DoubanExcelStoreImplement,
    }

    @staticmethod
    def create_store() -> AbstractStore:
        store_class = DoubanStoreFactory.STORES.get(config.SAVE_DATA_OPTION)
        if not store_class:
            raise ValueError(f"[DoubanStoreFactory] 不支持的存储格式: {config.SAVE_DATA_OPTION}")
        return store_class()


async def update_douban_note(note_item) -> None:
    """保存/更新一条豆瓣帖子"""
    if not note_item:
        return
    store = DoubanStoreFactory.create_store()
    await store.store_content(note_item)


async def batch_update_douban_comments(topic_id: str, comments: List) -> None:
    """批量保存评论(callback 用)"""
    if not comments:
        return
    store = DoubanStoreFactory.create_store()
    for comment in comments:
        await store.store_comment(comment)

# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1
# 豆瓣数据存储实现

import json
import time
from typing import Dict

import config
from base.base_crawler import AbstractStore
from tools.async_file_writer import AsyncFileWriter
from var import crawler_type_var


def _note_to_dict(note) -> Dict:
    """DoubanNote 对象 → 存储 dict"""
    return {
        "topic_id": getattr(note, "topic_id", ""),
        "title": getattr(note, "title", ""),
        "desc": getattr(note, "desc", ""),
        "creator_hash": getattr(note, "creator_hash", ""),
        "user_nickname": getattr(note, "user_nickname", ""),
        "group_id": getattr(note, "group_id", ""),
        "group_name": getattr(note, "group_name", ""),
        "reply_count": getattr(note, "reply_count", 0),
        "like_count": getattr(note, "like_count", 0),
        "create_date_time": getattr(note, "create_date_time", ""),
        "note_url": getattr(note, "note_url", ""),
        "source_keyword": getattr(note, "source_keyword", ""),
        "last_modify_ts": int(time.time()),
    }


def _comment_to_dict(comment) -> Dict:
    """DoubanComment 对象 → 存储 dict"""
    return {
        "comment_id": getattr(comment, "comment_id", ""),
        "topic_id": getattr(comment, "topic_id", ""),
        "content": getattr(comment, "content", ""),
        "creator_hash": getattr(comment, "creator_hash", ""),
        "user_nickname": getattr(comment, "user_nickname", ""),
        "create_date_time": getattr(comment, "create_date_time", ""),
        "like_count": getattr(comment, "like_count", 0),
        "last_modify_ts": int(time.time()),
    }


class DoubanJsonlStoreImplement(AbstractStore):
    def __init__(self):
        self.writer = AsyncFileWriter(platform="douban", crawler_type=crawler_type_var.get())

    async def store_content(self, content_item: Dict):
        await self.writer.write_to_jsonl(_note_to_dict(content_item) if hasattr(content_item, "topic_id") else content_item, "contents")

    async def store_comment(self, comment_item: Dict):
        await self.writer.write_to_jsonl(_comment_to_dict(comment_item) if hasattr(comment_item, "comment_id") else comment_item, "comments")

    async def store_creator(self, creator: Dict):
        pass


class DoubanJsonStoreImplement(AbstractStore):
    def __init__(self):
        self.writer = AsyncFileWriter(platform="douban", crawler_type=crawler_type_var.get())

    async def store_content(self, content_item: Dict):
        await self.writer.write_single_item_to_json(_note_to_dict(content_item) if hasattr(content_item, "topic_id") else content_item, "contents")

    async def store_comment(self, comment_item: Dict):
        await self.writer.write_single_item_to_json(_comment_to_dict(comment_item) if hasattr(comment_item, "comment_id") else comment_item, "comments")

    async def store_creator(self, creator: Dict):
        pass


class DoubanCsvStoreImplement(AbstractStore):
    def __init__(self):
        self.writer = AsyncFileWriter(platform="douban", crawler_type=crawler_type_var.get())

    async def store_content(self, content_item: Dict):
        await self.writer.write_to_csv(_note_to_dict(content_item) if hasattr(content_item, "topic_id") else content_item, "contents")

    async def store_comment(self, comment_item: Dict):
        await self.writer.write_to_csv(_comment_to_dict(comment_item) if hasattr(comment_item, "comment_id") else comment_item, "comments")

    async def store_creator(self, creator: Dict):
        pass


# DB/SQLite 实现(复用 ORM,与现有平台同模式)
class DoubanDbStoreImplement(AbstractStore):
    async def store_content(self, content_item: Dict):
        from database import db_session
        from database.models import DoubanNote as NoteModel
        d = _note_to_dict(content_item) if hasattr(content_item, "topic_id") else content_item
        async with db_session.get_session() as session:
            if session is None:
                return
            existing = await session.execute(
                __import__("sqlalchemy").select(NoteModel).where(NoteModel.topic_id == d.get("topic_id"))
            )
            if existing.scalar_one_or_none():
                return
            session.add(NoteModel(**{k: v for k, v in d.items() if hasattr(NoteModel, k)}))
            await session.commit()

    async def store_comment(self, comment_item: Dict):
        from database import db_session
        from database.models import DoubanNoteComment as CommentModel
        d = _comment_to_dict(comment_item) if hasattr(comment_item, "comment_id") else comment_item
        async with db_session.get_session() as session:
            if session is None:
                return
            existing = await session.execute(
                __import__("sqlalchemy").select(CommentModel).where(CommentModel.comment_id == d.get("comment_id"))
            )
            if existing.scalar_one_or_none():
                return
            session.add(CommentModel(**{k: v for k, v in d.items() if hasattr(CommentModel, k)}))
            await session.commit()

    async def store_creator(self, creator: Dict):
        pass


class DoubanSqliteStoreImplement(DoubanDbStoreImplement):
    pass


class DoubanExcelStoreImplement(AbstractStore):
    async def store_content(self, content_item: Dict):
        pass  # Excel 由主流程 flush

    async def store_comment(self, comment_item: Dict):
        pass

    async def store_creator(self, creator: Dict):
        pass


class DoubanMongoStoreImplement(AbstractStore):
    async def store_content(self, content_item: Dict):
        pass  # MongoDB 可后续实现

    async def store_comment(self, comment_item: Dict):
        pass

    async def store_creator(self, creator: Dict):
        pass

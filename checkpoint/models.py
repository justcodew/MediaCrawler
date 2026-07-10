# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1
#
# 断点续爬 —— 数据模型 (SQLAlchemy ORM)
#
# 设计要点:checkpoint 表使用独立 sqlite 库(database/checkpoints.db),不依赖主库的
# SAVE_DATA_OPTION,这样即使数据存成 jsonl/csv,断点续爬也能正常工作。
#
# checkpoint 粒度:页面级(已确认)。每 (task_id, keyword 或 creator_id 或 detail_scope)
# 一行,记录 last_page / last_search_id / processed_note_ids。
# - search 模式:keyword 为搜索关键词
# - detail 模式:keyword 用 "__detail__" 固定串,note_id 在 processed_note_ids 里
# - creator 模式:keyword 为 creator 标识(user_id/url)

from sqlalchemy import Column, Integer, Text, String, BigInteger
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class CrawlTask(Base):
    """爬虫任务(一次 main.py 运行 = 一个 task)"""
    __tablename__ = "crawl_task"
    task_id = Column(String(64), primary_key=True, comment="任务ID(uuid)")
    platform = Column(String(32), nullable=False, index=True, comment="平台")
    crawler_type = Column(String(32), nullable=False, comment="search/detail/creator")
    config_snapshot = Column(Text, comment="任务配置快照(JSON)")
    status = Column(String(16), nullable=False, default="running",
                    comment="running/paused/completed/failed")
    started_at = Column(BigInteger, comment="开始时间戳")
    finished_at = Column(BigInteger, comment="结束时间戳")
    error_msg = Column(Text, comment="失败原因")


class CrawlCheckpoint(Base):
    """爬取进度断点(每个 keyword/creator/scope 一行)"""
    __tablename__ = "crawl_checkpoint"
    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String(64), nullable=False, index=True, comment="关联任务ID")
    platform = Column(String(32), nullable=False, index=True, comment="平台")
    scope = Column(String(255), nullable=False, comment="进度作用域: keyword/creator_id/__detail__")
    last_page = Column(Integer, default=0, comment="已完成的最后一页")
    last_search_id = Column(Text, comment="搜索ID(xhs 用,续爬需复用同一 search_id)")
    last_cursor = Column(Text, comment="游标(creator 模式翻页用)")
    processed_note_ids = Column(Text, comment="已处理的 note_id 列表(JSON 数组,去重跳过用)")
    updated_ts = Column(BigInteger, comment="最后更新时间戳")

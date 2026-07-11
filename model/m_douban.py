# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1

# 豆瓣数据模型

from typing import Optional


class DoubanNote:
    """豆瓣小组讨论帖"""
    topic_id: str = ""
    title: str = ""
    desc: str = ""           # 正文内容
    creator_hash: str = ""   # 作者匿名哈希
    user_nickname: str = ""  # 作者昵称(已脱敏)
    group_id: str = ""       # 所属小组 ID
    group_name: str = ""     # 所属小组名
    reply_count: int = 0     # 回复数
    like_count: int = 0      # 喜欢数
    create_time: int = 0     # 创建时间戳
    create_date_time: str = ""
    note_url: str = ""
    source_keyword: str = ""


class DoubanComment:
    """豆瓣讨论帖回复"""
    comment_id: str = ""
    topic_id: str = ""
    content: str = ""
    creator_hash: str = ""
    user_nickname: str = ""
    create_time: int = 0
    create_date_time: str = ""
    like_count: int = 0


class GroupUrlInfo:
    """小组 URL 解析结果(creator 模式用)"""
    group_id: str = ""

    def __init__(self, group_id: str = "") -> None:
        self.group_id = group_id

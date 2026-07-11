# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1

# 豆瓣 URL 解析 + HTML 提取器(parsel)

import re
from typing import Dict, List, Optional
from urllib.parse import urlparse

from parsel import Selector

from constant.douban import DOUBAN_GROUP_URL, DOUBAN_URL
from model.m_douban import DoubanComment, DoubanNote, GroupUrlInfo
from tools import utils
from tools.user_hash import anonymize_user_id, mask_nickname


def parse_topic_url(url: str) -> str:
    """从豆瓣帖子 URL 提取 topic_id。

    支持:
      https://www.douban.com/group/topic/492525633/
      https://www.douban.com/group/topic/492525633/?_spm_id=xxx
      纯数字: 492525633
    """
    if url.isdigit():
        return url
    m = re.search(r"/group/topic/(\d+)", url)
    if m:
        return m.group(1)
    raise ValueError(f"无法从 URL 解析 topic_id: {url}")


def parse_group_url(url: str) -> GroupUrlInfo:
    """从豆瓣小组 URL 提取 group_id。

    支持:
      https://www.douban.com/group/guangzhou/
      https://www.douban.com/group/5xx/
      纯 ID: guangzhou
    """
    url = url.strip()
    if not url.startswith("http"):
        return GroupUrlInfo(group_id=url)
    parsed = urlparse(url)
    path = parsed.path  # /group/guangzhou/ 或 /group/5xx/
    m = re.search(r"/group/([^/]+)/?", path)
    if m:
        return GroupUrlInfo(group_id=m.group(1))
    raise ValueError(f"无法从 URL 解析 group_id: {url}")


class DoubanExtractor:
    """豆瓣 HTML 页面提取器"""

    @staticmethod
    def _normalize_text(text: str) -> str:
        if not text:
            return ""
        return re.sub(r"\s+", " ", text).strip()

    def extract_search_results(self, html: str, keyword: str = "") -> List[DoubanNote]:
        """从小组搜索结果页提取帖子列表。

        豆瓣搜索结果结构(已确认):
          table.olt tr
            td[0]: 标题 + a(href=/group/topic/<id>/)
            td[1]: 时间
            td[2]: 回复数(如"12回复")
            td[3]: 小组名 + a(href=/group/<id>/)
        """
        sel = Selector(text=html)
        rows = sel.xpath("//table[contains(@class,'olt')]//tr")
        results: List[DoubanNote] = []
        for tr in rows:
            tds = tr.xpath(".//td")
            if len(tds) < 4:
                continue  # 跳过表头或不完整行
            # 标题 + topic_id
            title_a = tds[0].xpath(".//a")
            title = self._normalize_text(title_a.xpath("@title").get(default="") or
                                         title_a.xpath("string(.)").get(default=""))
            href = title_a.xpath("@href").get(default="")
            if not title or not href:
                continue
            try:
                topic_id = parse_topic_url(href)
            except ValueError:
                continue

            # 时间
            pub_time = self._normalize_text(tds[1].xpath("string(.)").get(default=""))
            # 回复数(如"12回复" → 12)
            reply_text = self._normalize_text(tds[2].xpath("string(.)").get(default=""))
            reply_count = 0
            m = re.search(r"(\d+)", reply_text)
            if m:
                reply_count = int(m.group(1))

            # 小组
            group_a = tds[3].xpath(".//a")
            group_name = self._normalize_text(group_a.xpath("string(.)").get(default=""))
            group_href = group_a.xpath("@href").get(default="")
            group_id = ""
            if group_href:
                try:
                    group_id = parse_group_url(group_href).group_id
                except ValueError:
                    pass

            note = DoubanNote()
            note.topic_id = topic_id
            note.title = title
            note.group_id = group_id
            note.group_name = group_name
            note.reply_count = reply_count
            note.create_date_time = pub_time
            note.note_url = f"{DOUBAN_GROUP_URL}/topic/{topic_id}/"
            note.source_keyword = keyword
            results.append(note)

        utils.logger.info(f"[DoubanExtractor.extract_search_results] 提取到 {len(results)} 条结果")
        return results

    def extract_topic_detail(self, html: str, topic_id: str = "") -> Optional[DoubanNote]:
        """从帖子详情页提取正文 + 元信息。

        豆瓣帖子页结构(标准模板):
          h1: 标题
          div.topic-content: 正文
          h3 span.author: 作者
          span.create-time: 发布时间
        """
        sel = Selector(text=html)
        note = DoubanNote()
        note.topic_id = topic_id

        # 标题
        note.title = self._normalize_text(
            sel.xpath("//div[@class='article']//h1/text()").get(default="")
        )

        # 正文(可能多个 div.topic-content)
        content_parts = sel.xpath(
            "//div[contains(@class,'topic-content')]//div[@class='topic-content']//text()"
        ).getall()
        note.desc = self._normalize_text(" ".join(content_parts))

        # 作者
        author_nick = self._normalize_text(
            sel.xpath("//h3//span[@class='author']//text()").get(default="")
        )
        if author_nick:
            note.user_nickname = mask_nickname(author_nick)
        author_id = sel.xpath("//h3//span[@class='author']//a/@href").get(default="")
        m = re.search(r"/people/([^/]+)/", author_id)
        if m:
            note.creator_hash = anonymize_user_id(m.group(1))

        # 发布时间
        note.create_date_time = self._normalize_text(
            sel.xpath("//span[@class='create-time']/text()").get(default="")
        )

        # 回复数(页面标题或 meta)
        reply_text = sel.xpath("//span[contains(@class,'reply')]/text()").get(default="")
        m = re.search(r"(\d+)", reply_text)
        if m:
            note.reply_count = int(m.group(1))

        note.note_url = f"{DOUBAN_GROUP_URL}/topic/{topic_id}/"
        return note

    def extract_comments(self, html: str, topic_id: str = "") -> List[DoubanComment]:
        """从帖子详情页提取回复列表。

        豆瓣回复结构:
          div#comments div.comment-item
            h4: 回复者(a href=/people/<id>/)
            span.pubtime: 回复时间
            p.reply-content: 回复内容
        """
        sel = Selector(text=html)
        items = sel.xpath("//div[@id='comments']//div[contains(@class,'comment-item')]")
        results: List[DoubanComment] = []
        for item in items:
            comment = DoubanComment()
            comment.topic_id = topic_id
            # comment_id(豆瓣的 comment-item id 格式: comment-XXXXX)
            comment.comment_id = item.xpath("@id").get(default="").replace("comment-", "")

            # 作者
            author_a = item.xpath(".//h4//a")
            author_nick = self._normalize_text(author_a.xpath("string(.)").get(default=""))
            comment.user_nickname = mask_nickname(author_nick) if author_nick else ""
            author_href = author_a.xpath("@href").get(default="")
            m = re.search(r"/people/([^/]+)/", author_href)
            if m:
                comment.creator_hash = anonymize_user_id(m.group(1))

            # 时间
            comment.create_date_time = self._normalize_text(
                item.xpath(".//span[@class='pubtime']/text()").get(default="")
            )

            # 内容
            comment.content = self._normalize_text(
                item.xpath(".//p[@class='reply-content']/text()").get(default="")
            )

            if comment.content:
                results.append(comment)

        return results

    def extract_group_topics(self, html: str, group_id: str = "") -> List[DoubanNote]:
        """从小组讨论列表页提取帖子(结构同搜索结果)。"""
        return self.extract_search_results(html)

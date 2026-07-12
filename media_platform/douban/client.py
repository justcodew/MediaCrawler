# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1

# 豆瓣 httpx 请求封装
# 豆瓣无签名算法,直接 httpx GET HTML 页面,用 parsel 解析。

import asyncio
from typing import Callable, Dict, List, Optional, Union
from urllib.parse import quote, urlencode

from playwright.async_api import BrowserContext
from tenacity import retry, stop_after_attempt, wait_fixed

import config
from base.base_crawler import AbstractApiClient
from proxy.proxy_mixin import ProxyRefreshMixin
from tools import utils
from tools.httpx_util import make_async_client

from .exception import DataFetchError, IPBlockError
from .help import DoubanExtractor, parse_topic_url

if False:  # TYPE_CHECKING
    from proxy.proxy_ip_pool import ProxyIpPool


class DoubanClient(AbstractApiClient, ProxyRefreshMixin):
    """豆瓣 HTTP 客户端:获取 HTML 页面,交给 Extractor 解析。"""

    def __init__(
        self,
        timeout: int = 15,
        proxy=None,
        *,
        headers: Dict[str, str],
        cookie_dict: Dict[str, str],
        proxy_ip_pool: Optional["ProxyIpPool"] = None,
    ) -> None:
        self.proxy = proxy
        self.timeout = timeout
        self.headers = headers
        self._host = "https://www.douban.com"
        self._group_host = "https://www.douban.com/group"
        self.cookie_urls = [self._host]
        self.cookie_dict = cookie_dict
        self._extractor = DoubanExtractor()
        self.init_proxy_pool(proxy_ip_pool)

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(1))
    async def request(self, method: str, url: str, **kwargs) -> str:
        """发请求,返回 HTML 文本。"""
        await self._refresh_proxy_if_expired()
        return_response = kwargs.pop("return_response", False)
        async with make_async_client(proxy=self.proxy) as client:
            resp = await client.request(method, url, timeout=self.timeout, **kwargs)

        if resp.status_code == 403:
            raise IPBlockError(f"豆瓣返回 403,可能需要登录或被限流: {url}")
        if resp.status_code != 200:
            raise DataFetchError(f"请求失败 status={resp.status_code} url={url}")

        if return_response:
            return resp.text
        return resp.text

    async def get_html(self, url: str) -> str:
        """获取页面 HTML。"""
        return await self.request("GET", url, headers=self.headers)

    # ===== 搜索 =====

    async def search_topics_by_keyword(
        self, keyword: str, start: int = 0
    ) -> List:
        """关键词搜索小组讨论帖。

        GET /group/search?cat=1013&q=<关键词>&start=<偏移>
        """
        from constant.douban import GROUP_SEARCH_CAT
        params = {"cat": GROUP_SEARCH_CAT, "q": keyword, "start": start}
        url = f"{self._group_host}/search?{urlencode(params)}"
        utils.logger.info(f"[DoubanClient.search] {url}")
        html = await self.get_html(url)
        return self._extractor.extract_search_results(html, keyword=keyword)

    # ===== 帖子详情 =====

    async def get_topic_detail(self, topic_id: str):
        """获取帖子详情(正文 + 元信息)。"""
        url = f"{self._group_host}/topic/{topic_id}/"
        utils.logger.info(f"[DoubanClient.get_topic_detail] {url}")
        html = await self.get_html(url)
        return self._extractor.extract_topic_detail(html, topic_id=topic_id)

    async def get_topic_comments(self, topic_id: str, start: int = 0) -> List:
        """获取帖子回复(豆瓣回复在详情页,翻页用 start)。"""
        url = f"{self._group_host}/topic/{topic_id}/"
        if start > 0:
            url = f"{url}?start={start}"
        html = await self.get_html(url)
        return self._extractor.extract_comments(html, topic_id=topic_id)

    async def get_all_topic_comments(
        self,
        topic_id: str,
        reply_count: int = 0,
        crawl_interval: float = 1.0,
        callback: Optional[Callable] = None,
        max_count: int = 50,
    ) -> List:
        """获取帖子的所有回复(按页翻)。"""
        from constant.douban import GROUP_PAGE_SIZE
        results: List = []
        start = 0
        # 豆瓣回复数 / 每页条数 = 页数,但回复可能不完整,用 max_count 兜底
        max_pages = max(1, reply_count // GROUP_PAGE_SIZE + 1) if reply_count else 3
        for _ in range(max_pages):
            if len(results) >= max_count:
                break
            try:
                comments = await self.get_topic_comments(topic_id, start=start)
                if not comments:
                    break
                if callback:
                    await callback(topic_id, comments)
                results.extend(comments)
                await asyncio.sleep(crawl_interval)
                start += GROUP_PAGE_SIZE
            except Exception as e:
                utils.logger.warning(f"[DoubanClient.get_all_topic_comments] {topic_id} 翻页失败: {e}")
                break
        return results[:max_count]

    # ===== 小组讨论列表(creator 模式) =====

    async def get_group_topics(self, group_id: str, start: int = 0) -> List:
        """获取小组的讨论列表。

        GET /group/<group_id>/discussion?start=<偏移>
        """
        url = f"{self._group_host}/{group_id}/discussion"
        params = {"start": start} if start > 0 else {}
        if params:
            url = f"{url}?{urlencode(params)}"
        utils.logger.info(f"[DoubanClient.get_group_topics] {url}")
        html = await self.get_html(url)
        return self._extractor.extract_group_topics(html, group_id=group_id)

    # ===== 登录态 =====

    async def pong(self) -> bool:
        """检查登录态:访问首页,看是否有登录链接。"""
        try:
            html = await self.get_html(self._host)
            # 已登录:页面含 "nav-user-account" 或 "我的豆瓣"
            # 未登录:含 "登录" 按钮
            if "登录" in html and "nav-user-account" not in html and "我的豆瓣" not in html:
                return False
            return "nav-user-account" in html or "我的豆瓣" in html
        except Exception as e:
            utils.logger.error(f"[DoubanClient.pong] 检查登录态失败: {e}")
            return False

    async def update_cookies(self, browser_context: BrowserContext, urls: Optional[list] = None):
        """从浏览器上下文更新 cookie。"""
        cookie_str, cookie_dict = await utils.convert_browser_context_cookies(
            browser_context, urls=urls or self.cookie_urls
        )
        self.headers["Cookie"] = cookie_str
        self.cookie_dict = cookie_dict

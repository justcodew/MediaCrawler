# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1

# 豆瓣 Crawler 编排

import asyncio
import os
from typing import Dict, List, Optional

from playwright.async_api import BrowserContext, BrowserType, Playwright

import config
from base.base_crawler import AbstractCrawler
from constant.douban import GROUP_PAGE_SIZE
from proxy.proxy_ip_pool import IpInfoModel, create_ip_pool
from tools import utils
from tools.crawler_util import resolve_user_data_dir_name
from tools.cdp_browser import CDPBrowserManager

from .client import DoubanClient
from .exception import DataFetchError
from .help import DoubanExtractor, parse_group_url, parse_topic_url
from .login import DoubanLogin

from store import douban as store


class DoubanCrawler(AbstractCrawler):

    def __init__(self) -> None:
        super().__init__()
        self.index_url = "https://www.douban.com"
        self.cookie_urls = [self.index_url]
        self.user_agent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
        self.cdp_manager = None
        self.ip_proxy_pool = None
        self.browser_context: Optional[BrowserContext] = None
        self.context_page = None
        self.douban_client: Optional[DoubanClient] = None

    async def start(self) -> None:
        playwright_proxy_format, httpx_proxy_format = None, None
        if config.ENABLE_IP_PROXY:
            self.ip_proxy_pool = await create_ip_pool(config.IP_PROXY_POOL_COUNT, enable_validate_ip=True)
            ip_proxy_info: IpInfoModel = await self.ip_proxy_pool.get_proxy()
            playwright_proxy_format, httpx_proxy_format = utils.format_proxy_info(ip_proxy_info)

        async with async_playwright() as playwright:
            if config.ENABLE_CDP_MODE:
                utils.logger.info("[DoubanCrawler] CDP 模式启动")
                self.browser_context = await self.launch_browser_with_cdp(
                    playwright, playwright_proxy_format, self.user_agent, headless=config.CDP_HEADLESS
                )
            else:
                utils.logger.info("[DoubanCrawler] 标准模式启动")
                chromium = playwright.chromium
                self.browser_context = await self.launch_browser(
                    chromium, playwright_proxy_format, self.user_agent, headless=config.HEADLESS
                )
                await self.browser_context.add_init_script(path="libs/stealth.min.js")

            self.context_page = await self.browser_context.new_page()
            await self.context_page.goto(self.index_url)
            # 反检测:注入 page
            self.anti_detect.attach_page(self.context_page)

            # 创建 client
            self.douban_client = await self.create_client(httpx_proxy_format)
            if not await self.douban_client.pong():
                login_obj = DoubanLogin(
                    login_type=config.LOGIN_TYPE,
                    browser_context=self.browser_context,
                    context_page=self.context_page,
                    cookie_str=config.COOKIES,
                )
                await login_obj.begin()
                await self.douban_client.update_cookies(self.browser_context)

            utils.logger.info(f"[DoubanCrawler] 登录态确认,开始 {config.CRAWLER_TYPE} 模式")
            if config.CRAWLER_TYPE == "search":
                await self.search()
            elif config.CRAWLER_TYPE == "detail":
                await self.get_specified_topics()
            elif config.CRAWLER_TYPE == "creator":
                await self.get_group_topics_and_details()
            utils.logger.info("[DoubanCrawler] 采集完成")

    # ===== search 模式 =====

    async def search(self) -> None:
        utils.logger.info("[DoubanCrawler.search] 开始搜索")
        ckpt = self.checkpoint_manager
        for keyword in config.KEYWORDS.split(","):
            keyword = keyword.strip()
            if not keyword:
                continue
            utils.logger.info(f"[DoubanCrawler.search] 关键词: {keyword}")
            scope_state = await ckpt.begin_scope(keyword)
            start = scope_state.last_page * GROUP_PAGE_SIZE if scope_state.last_page > 0 else 0
            page_num = scope_state.last_page + 1 if scope_state.last_page > 0 else 1

            while (page_num - 1) * GROUP_PAGE_SIZE < config.CRAWLER_MAX_NOTES_COUNT:
                try:
                    notes = await self.douban_client.search_topics_by_keyword(keyword, start=start)
                    if not notes:
                        utils.logger.info("[DoubanCrawler.search] 无更多结果")
                        break

                    # 跳过已处理
                    todo = [n for n in notes if not ckpt.is_processed(keyword, n.topic_id)]
                    if not todo:
                        utils.logger.info(f"[DoubanCrawler.search] 本页 {len(notes)} 条均已处理,翻页")
                        start += GROUP_PAGE_SIZE
                        page_num += 1
                        continue

                    topic_ids = []
                    for note in todo:
                        if len(topic_ids) >= config.CRAWLER_MAX_NOTES_COUNT:
                            break
                        # 获取详情
                        try:
                            detail = await self.douban_client.get_topic_detail(note.topic_id)
                            if detail:
                                note.desc = detail.desc or note.desc
                                note.creator_hash = detail.creator_hash
                                note.user_nickname = detail.user_nickname
                                note.create_date_time = detail.create_date_time or note.create_date_time
                            await store.update_douban_note(note)
                            topic_ids.append(note.topic_id)

                            # 获取评论
                            if config.ENABLE_GET_COMMENTS:
                                comments = await self.douban_client.get_all_topic_comments(
                                    note.topic_id, reply_count=note.reply_count,
                                    crawl_interval=config.CRAWLER_MAX_SLEEP_SEC,
                                    callback=store.batch_update_douban_comments,
                                    max_count=config.CRAWLER_MAX_COMMENTS_COUNT_SINGLENOTES,
                                )
                            # 反检测:拟人化停顿
                            await self.anti_detect.humanized_sleep(config.CRAWLER_MAX_SLEEP_SEC)
                        except Exception as e:
                            utils.logger.warning(f"[DoubanCrawler.search] 帖子 {note.topic_id} 失败: {e}")

                    # 断点续爬:记录本页完成
                    await ckpt.save_page(keyword, page_num, topic_ids)
                    utils.logger.info(f"[DoubanCrawler.search] 第 {page_num} 页完成,{len(topic_ids)} 条")

                    # 反检测:截图感知
                    risk = await self.anti_detect.check_risk()
                    if risk.is_risk:
                        action = await self.anti_detect.handle(risk)
                        if action == "stop":
                            from anti_detect import RiskControlError
                            raise RiskControlError(risk)
                    await self.anti_detect.simulate_browse()

                    start += GROUP_PAGE_SIZE
                    page_num += 1
                except DataFetchError as e:
                    utils.logger.error(f"[DoubanCrawler.search] 请求失败: {e}")
                    break

    # ===== detail 模式 =====

    async def get_specified_topics(self) -> None:
        utils.logger.info("[DoubanCrawler.get_specified_topics] 开始获取指定帖子")
        ckpt = self.checkpoint_manager
        scope = "__detail__"
        await ckpt.begin_scope(scope)
        for topic_url in config.DOUBAN_SPECIFIED_ID_LIST:
            try:
                topic_id = parse_topic_url(topic_url)
                if ckpt.is_processed(scope, topic_id):
                    utils.logger.info(f"[DoubanCrawler] 跳过已处理: {topic_id}")
                    continue
                detail = await self.douban_client.get_topic_detail(topic_id)
                if detail:
                    await store.update_douban_note(detail)
                    if config.ENABLE_GET_COMMENTS:
                        await self.douban_client.get_all_topic_comments(
                            topic_id, reply_count=detail.reply_count,
                            callback=store.batch_update_douban_comments,
                            max_count=config.CRAWLER_MAX_COMMENTS_COUNT_SINGLENOTES,
                        )
                await ckpt.save_page(scope, 1, [topic_id])
                await self.anti_detect.humanized_sleep(config.CRAWLER_MAX_SLEEP_SEC)
            except Exception as e:
                utils.logger.error(f"[DoubanCrawler.get_specified_topics] {topic_url} 失败: {e}")

    # ===== creator 模式(小组讨论列表) =====

    async def get_group_topics_and_details(self) -> None:
        utils.logger.info("[DoubanCrawler.get_group_topics_and_details] 开始获取小组讨论")
        ckpt = self.checkpoint_manager
        scope = "__creator__"
        await ckpt.begin_scope(scope)
        for group_url in config.DOUBAN_GROUP_ID_LIST:
            try:
                group_info = parse_group_url(group_url)
                group_id = group_info.group_id
                if ckpt.is_processed(scope, group_id):
                    utils.logger.info(f"[DoubanCrawler] 跳过已处理小组: {group_id}")
                    continue
                start = 0
                while start < config.CRAWLER_MAX_NOTES_COUNT * 2:
                    notes = await self.douban_client.get_group_topics(group_id, start=start)
                    if not notes:
                        break
                    for note in notes[:config.CRAWLER_MAX_NOTES_COUNT]:
                        try:
                            detail = await self.douban_client.get_topic_detail(note.topic_id)
                            if detail:
                                note.desc = detail.desc or note.desc
                                await store.update_douban_note(note)
                                if config.ENABLE_GET_COMMENTS:
                                    await self.douban_client.get_all_topic_comments(
                                        note.topic_id, reply_count=note.reply_count,
                                        callback=store.batch_update_douban_comments,
                                        max_count=config.CRAWLER_MAX_COMMENTS_COUNT_SINGLENOTES,
                                    )
                            await self.anti_detect.humanized_sleep(config.CRAWLER_MAX_SLEEP_SEC)
                        except Exception as e:
                            utils.logger.warning(f"[DoubanCrawler] 帖子 {note.topic_id} 失败: {e}")
                    start += GROUP_PAGE_SIZE
                await ckpt.save_page(scope, 1, [group_id])
            except Exception as e:
                utils.logger.error(f"[DoubanCrawler.get_group_topics_and_details] 小组 {group_url} 失败: {e}")

    # ===== 浏览器启动 =====

    async def launch_browser(
        self, chromium: BrowserType, playwright_proxy: Optional[Dict],
        user_agent: Optional[str], headless: bool = True
    ) -> BrowserContext:
        if config.SAVE_LOGIN_STATE:
            dir_name = resolve_user_data_dir_name("douban", getattr(self, "_account_info", None))
            user_data_dir = os.path.join(os.getcwd(), "browser_data", dir_name)
            return await chromium.launch_persistent_context(
                user_data_dir=user_data_dir, headless=headless, proxy=playwright_proxy,
                user_agent=user_agent, viewport={"width": 1920, "height": 1080},
            )
        browser = await chromium.launch(headless=headless, proxy=playwright_proxy)
        return await browser.new_context(user_agent=user_agent)

    async def launch_browser_with_cdp(
        self, playwright: Playwright, playwright_proxy: Optional[Dict],
        user_agent: Optional[str], headless: bool = True
    ) -> BrowserContext:
        try:
            self.cdp_manager = CDPBrowserManager()
            return await self.cdp_manager.launch_and_connect(
                playwright=playwright, playwright_proxy=playwright_proxy,
                user_agent=user_agent, headless=headless,
                account=getattr(self, "_account_info", None),
            )
        except Exception as e:
            utils.logger.error(f"[DoubanCrawler] CDP 失败,回退标准模式: {e}")
            return await self.launch_browser(playwright.chromium, playwright_proxy, user_agent, headless)

    async def create_client(self, httpx_proxy: Optional[str]) -> DoubanClient:
        cookie_str, cookie_dict = await utils.convert_browser_context_cookies(
            self.browser_context, urls=self.cookie_urls
        )
        return DoubanClient(
            proxy=httpx_proxy,
            headers={
                "User-Agent": self.user_agent,
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "zh-CN,zh;q=0.9",
                "Cookie": cookie_str,
                "Referer": self.index_url,
            },
            cookie_dict=cookie_dict,
            proxy_ip_pool=self.ip_proxy_pool,
        )

    async def close(self) -> None:
        if self.cdp_manager:
            await self.cdp_manager.cleanup()
        elif self.browser_context:
            await self.browser_context.close()


# 需要 import playwright(async_playwright),放在文件底部避免顶层依赖
from playwright.async_api import async_playwright  # noqa: E402

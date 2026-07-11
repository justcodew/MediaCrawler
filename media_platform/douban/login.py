# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1

# 豆瓣登录:CDP 扫码 + Cookie 注入

import asyncio
from typing import Optional

from playwright.async_api import BrowserContext, Page
from tenacity import retry, stop_after_attempt, wait_fixed

import config
from base.base_crawler import AbstractLogin
from tools import utils


class DoubanLogin(AbstractLogin):
    def __init__(
        self,
        login_type: str,
        browser_context: BrowserContext,
        context_page: Page,
        login_phone: str = "",
        cookie_str: str = "",
    ) -> None:
        self.login_type = login_type
        self.browser_context = browser_context
        self.context_page = context_page
        self.login_phone = login_phone
        self.cookie_str = cookie_str

    async def begin(self) -> None:
        utils.logger.info("[DoubanLogin.begin] 开始登录豆瓣...")
        if self.login_type == "qrcode":
            await self.login_by_qrcode()
        elif self.login_type == "cookie":
            await self.login_by_cookies()
        else:
            raise ValueError(f"不支持的登录方式: {self.login_type}")

    async def login_by_mobile(self) -> None:
        """豆瓣暂不支持手机号登录(预留)"""
        raise NotImplementedError("豆瓣暂不支持手机号登录,请用 qrcode 或 cookie 方式")

    async def login_by_qrcode(self) -> None:
        """CDP 模式下,用户在浏览器里手动登录(扫码或账密)。

        豆瓣登录页:https://accounts.douban.com/passport/login
        CDP 连接的是用户真实浏览器,用户在窗口里操作即可。
        """
        login_url = "https://accounts.douban.com/passport/login"
        utils.logger.info(f"[DoubanLogin.login_by_qrcode] 跳转登录页: {login_url}")
        await self.context_page.goto(login_url)

        # 等待用户登录成功(检测 URL 跳转回豆瓣首页或出现登录态)
        @retry(stop=stop_after_attempt(120), wait=wait_fixed(1))
        async def check_login() -> None:
            url = self.context_page.url
            # 登录成功后会跳转回 www.douban.com
            if "www.douban.com" in url and "accounts.douban.com" not in url:
                # 进一步确认登录态
                content = await self.context_page.content()
                if "nav-user-account" in content or "我的豆瓣" in content:
                    return
            raise Exception("等待登录中...")

        try:
            await check_login()
            utils.logger.info("[DoubanLogin.login_by_qrcode] 登录成功!")
        except Exception:
            utils.logger.warning("[DoubanLogin.login_by_qrcode] 登录超时(120s),继续尝试...")

    async def login_by_cookies(self) -> None:
        """Cookie 注入登录。"""
        if not self.cookie_str:
            utils.logger.error("[DoubanLogin.login_by_cookies] cookie_str 为空")
            return
        # 豆瓣关键 cookie: bid, dbcl2, ck
        cookies = []
        for item in self.cookie_str.split(";"):
            item = item.strip()
            if "=" not in item:
                continue
            k, v = item.split("=", 1)
            cookies.append({
                "name": k.strip(),
                "value": v.strip(),
                "domain": ".douban.com",
                "path": "/",
            })
        if cookies:
            await self.browser_context.add_cookies(cookies)
            utils.logger.info(f"[DoubanLogin.login_by_cookies] 注入 {len(cookies)} 个 cookie")

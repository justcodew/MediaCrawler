# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1
#
# 多账号 —— 账号数据模型与类型定义
#
# Account ORM 与账号池配合使用。cookies/user_agent 用于脱浏览器纯 httpx 请求(阶段四);
# proxy_config 用于给账号绑定独立代理。
#
# 注意:本表用于学习多账号轮转机制。cookies 字段仅在本地使用,不涉及任何对外服务。

import json
from typing import Any, Dict, Optional

from sqlalchemy import Column, Integer, Text, String, BigInteger
from sqlalchemy.orm import declarative_base

Base = declarative_base()

#: 账号状态机
#  active   - 可用
#  in_use   - 正在使用(池内锁定)
#  cooling  - 冷却中(刚触发风控,等待恢复)
#  disabled - 已禁用(手动/封号)
STATUS_ACTIVE = "active"
STATUS_IN_USE = "in_use"
STATUS_COOLING = "cooling"
STATUS_DISABLED = "disabled"


class Account(Base):
    """账号池账号"""
    __tablename__ = "account_pool"
    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(String(64), nullable=False, index=True, comment="账号标识(nickname 或自定义ID)")
    platform = Column(String(32), nullable=False, index=True, comment="平台")
    nickname = Column(Text, comment="账号备注名(已脱敏,仅用于辨识)")
    cookies = Column(Text, comment="登录态 Cookie 字符串")
    user_agent = Column(Text, comment="该账号登录时使用的 User-Agent")
    status = Column(String(16), nullable=False, default=STATUS_ACTIVE, index=True,
                    comment="active/in_use/cooling/disabled")
    proxy_config = Column(Text, comment="绑定的代理配置(JSON),如 {http,https}")
    fail_count = Column(Integer, default=0, comment="连续失败次数")
    success_count = Column(Integer, default=0, comment="累计成功次数")
    last_used_ts = Column(BigInteger, comment="最后使用时间戳")
    last_error = Column(Text, comment="最近一次错误信息")
    add_ts = Column(BigInteger, comment="添加时间戳")


class AccountInfo:
    """账号信息的轻量内存表示(供 AccountPool 使用)"""

    def __init__(
        self,
        account_id: str,
        platform: str,
        cookies: str = "",
        user_agent: str = "",
        nickname: str = "",
        proxy_config: Optional[Dict[str, Any]] = None,
        db_id: Optional[int] = None,
        fail_count: int = 0,
    ) -> None:
        self.account_id = account_id
        self.platform = platform
        self.cookies = cookies
        self.user_agent = user_agent
        self.nickname = nickname
        self.proxy_config = proxy_config or {}
        self.db_id = db_id  # ORM 主键,回写状态用
        self.fail_count = fail_count  # 连续失败次数(由 store 回填)

    @property
    def user_data_dir_name(self) -> str:
        """该账号专属的浏览器 user_data_dir 名(按账号隔离)"""
        from config import USER_DATA_DIR
        # 原 USER_DATA_DIR 形如 "%s_user_data_dir",按 (platform_account_id) 填充
        if "%s" in USER_DATA_DIR:
            return USER_DATA_DIR % f"{self.platform}_{self.account_id}"
        return f"{self.platform}_{self.account_id}_user_data_dir"

    @property
    def proxy_url(self) -> str:
        """从 proxy_config 取 http 代理 URL(httpx/CDP 通用)"""
        return (self.proxy_config or {}).get("http", "") or (self.proxy_config or {}).get("https", "")

    def __repr__(self) -> str:
        return f"AccountInfo(platform={self.platform!r}, account_id={self.account_id!r}, nickname={self.nickname!r})"


def account_orm_to_info(acc: "Account") -> AccountInfo:
    """ORM 行 -> AccountInfo 内存对象"""
    proxy_cfg = {}
    if acc.proxy_config:
        try:
            proxy_cfg = json.loads(acc.proxy_config)
        except (json.JSONDecodeError, TypeError):
            proxy_cfg = {}
    return AccountInfo(
        account_id=acc.account_id or f"acc_{acc.id}",
        platform=acc.platform,
        cookies=acc.cookies or "",
        user_agent=acc.user_agent or "",
        nickname=acc.nickname or "",
        proxy_config=proxy_cfg,
        db_id=acc.id,
        fail_count=acc.fail_count or 0,
    )

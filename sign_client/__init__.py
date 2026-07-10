# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1
#
# 爬虫侧签名服务客户端包
# 用法: from sign_client import get_client, is_enabled
#       if is_enabled(): signs = await get_client().sign_xhs(...)

from sign_client.client import SignServiceClient, get_client, is_enabled

__all__ = ["SignServiceClient", "get_client", "is_enabled"]

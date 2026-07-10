# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1
#
# providers 包:import 本包即触发所有平台 provider 的注册。
# app.py 启动时 `from sign_service.providers import registry` 即可拿到全部已注册 provider。

from sign_service.providers.base import ProviderRegistry, SignProvider, registry

# 导入各 provider 模块,触发 registry.register()
from sign_service.providers import (  # noqa: F401,E402
    bilibili_sign_provider,
    douyin_sign_provider,
    tieba_sign_provider,
    xhs_sign_provider,
    zhihu_sign_provider,
)

__all__ = ["ProviderRegistry", "SignProvider", "registry"]

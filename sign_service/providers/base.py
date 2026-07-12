# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1
#
# SignProvider 抽象基类与 provider 注册表
# 设计原则:provider 直接复用 media_platform 下已有的纯算法模块,不在服务里重复实现签名逻辑,
# 从而保证「本地签名」与「服务签名」输出完全一致。

from abc import ABC, abstractmethod
from typing import Dict, Type

from sign_service.models import SignRequest, SignResponse


class SignProvider(ABC):
    """各平台签名 provider 的统一接口

    子类实现 sign() 方法,从 SignRequest 选取本平台所需字段,调用对应的纯算法模块,
    返回 SignResponse(headers/params)。
    """

    #: 平台标识,子类必须设置(如 "xhs")
    platform: str = ""

    @abstractmethod
    def sign(self, req: SignRequest) -> SignResponse:
        """计算签名并返回 headers/params"""
        raise NotImplementedError


class ProviderRegistry:
    """provider 注册表,按平台名索引"""

    def __init__(self) -> None:
        self._providers: Dict[str, SignProvider] = {}

    def register(self, provider: SignProvider) -> None:
        if not provider.platform:
            raise ValueError(f"Provider {provider.__class__.__name__} 缺少 platform 属性")
        self._providers[provider.platform] = provider

    def get(self, platform: str) -> SignProvider:
        provider = self._providers.get(platform)
        if provider is None:
            supported = ", ".join(sorted(self._providers))
            raise KeyError(f"不支持的签名平台: {platform!r}, 已注册: {supported}")
        return provider

    def list_platforms(self) -> list[str]:
        return sorted(self._providers)


#: 全局注册表单例,app.py 启动时注册所有 provider
registry = ProviderRegistry()

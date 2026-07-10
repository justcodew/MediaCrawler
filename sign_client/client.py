# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1
#
# SignServiceClient —— 爬虫侧签名服务 HTTP 客户端
#
# 职责:在 crawler 进程中替代直接的 execjs/算法调用,改为请求 SignSrv。
# - 当 config.ENABLE_SIGN_SERVICE = True 且服务可达时,走 HTTP。
# - 服务不可达时,自动 fallback 到各平台原有的本地签名函数(向后兼容,零风险迁移)。
#
# 每个平台有独立的便捷方法(sign_xhs / sign_douyin / ...),封装各自的入参约定,
# 调用方(各平台 help.py / client.py)无需关心底层是 HTTP 还是本地。

import logging
from typing import Any, Dict, Optional

import httpx

import config

logger = logging.getLogger(__name__)

#: 单例缓存(全进程共享一个 client 实例 + 短连接池)
_singleton: Optional["SignServiceClient"] = None


class SignServiceClient:
    """签名服务客户端,带本地 fallback。

    用 get_client() 获取单例,不要直接实例化。
    """

    def __init__(self, base_url: str, timeout: float = 5.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        # 连接失败标记:一旦连续失败,短期内跳过 HTTP 直走 fallback,避免每个请求都等超时
        self._unavailable = False
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=timeout,
            # 失败快速返回,不重试(签名是高频调用,重试会拖慢爬虫)
        )

    async def _post_sign(self, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """请求签名服务,失败返回 None(不抛异常,交给 fallback)"""
        if self._unavailable:
            return None
        try:
            resp = await self._client.post("/sign", json=payload)
            if resp.status_code == 200:
                self._unavailable = False
                return resp.json()
            logger.warning(
                f"[SignClient] 签名服务返回 {resp.status_code}: {resp.text[:200]}, 本轮走 fallback"
            )
            return None
        except (httpx.ConnectError, httpx.ReadTimeout, httpx.ConnectTimeout, httpx.RemoteProtocolError) as e:
            # 服务未启动 / 端口不通 —— 标记不可用,后续直接 fallback
            if not self._unavailable:
                logger.warning(
                    f"[SignClient] 签名服务不可达 ({type(e).__name__}),已切换为本地签名 fallback。"
                    f"启动 SignSrv (sign_service/app.py) 并设 ENABLE_SIGN_SERVICE=True 可恢复。"
                )
            self._unavailable = True
            return None
        except Exception as e:
            logger.warning(f"[SignClient] 签名服务未知异常 ({type(e).__name__}): {e}, 走 fallback")
            return None

    async def close(self) -> None:
        await self._client.aclose()

    # ===== 各平台便捷方法 =====
    # 每个方法对应一个平台 provider 的入参约定。
    # fallback 分支通过 sign_service.providers.registry 直接调用对应 provider,
    # provider 内部用轻量加载器加载签名算法模块,从而保证「服务签名」与「本地 fallback 签名」
    # 走的是同一份算法代码,输出完全一致。这也避免 fallback 触发 media_platform 包的
    # 重型 __init__ 依赖(pandas/playwright 等)。

    async def sign_xhs(
        self, uri: str, data: Optional[Dict] = None, cookie_str: str = "", method: str = "POST"
    ) -> Dict[str, str]:
        """小红书签名,返回 {x-s, x-t, x-s-common, x-b3-traceid}"""
        resp = await self._post_sign({
            "platform": "xhs",
            "uri": uri,
            "method": method,
            "data": data,
            "cookies": cookie_str,
        })
        if resp is not None:
            return resp["raw"]
        # fallback: 进程内直接调 provider(经轻量加载器)
        from sign_service.models import SignRequest
        from sign_service.providers import registry
        return registry.get("xhs").sign(SignRequest(
            platform="xhs", uri=uri, method=method, data=data, cookies=cookie_str
        )).raw

    async def sign_douyin(self, url: str, params: str, user_agent: str) -> str:
        """抖音签名,返回 a_bogus 字符串"""
        resp = await self._post_sign({
            "platform": "douyin",
            "uri": url,
            "url": params,
            "user_agent": user_agent,
        })
        if resp is not None:
            return resp["params"]["a_bogus"]
        from sign_service.models import SignRequest
        from sign_service.providers import registry
        r = registry.get("douyin").sign(SignRequest(
            platform="douyin", uri=url, url=params, user_agent=user_agent
        ))
        return r.params["a_bogus"]

    async def sign_zhihu(self, url: str, cookies: str) -> Dict[str, str]:
        """知乎签名,返回 {x-zst-81, x-zse-96}"""
        resp = await self._post_sign({
            "platform": "zhihu",
            "url": url,
            "cookies": cookies,
        })
        if resp is not None:
            return resp["raw"]
        from sign_service.models import SignRequest
        from sign_service.providers import registry
        return registry.get("zhihu").sign(SignRequest(
            platform="zhihu", url=url, cookies=cookies
        )).raw

    async def sign_bilibili(
        self, req_data: Dict[str, Any], img_key: str, sub_key: str
    ) -> Dict[str, Any]:
        """B站 wbi 签名,返回补全后的 params(含 wts/w_rid)"""
        resp = await self._post_sign({
            "platform": "bilibili",
            "params": req_data,
            "extra": {"img_key": img_key, "sub_key": sub_key},
        })
        if resp is not None:
            return resp["params"]
        from sign_service.models import SignRequest
        from sign_service.providers import registry
        return registry.get("bilibili").sign(SignRequest(
            platform="bilibili", params=req_data,
            extra={"img_key": img_key, "sub_key": sub_key},
        )).params

    async def sign_tieba(
        self, params: Dict[str, Any], method: str = "GET", data: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """贴吧 PC 签名,返回补全后的 params(含 subapp_type/_client_type/sign)"""
        resp = await self._post_sign({
            "platform": "tieba",
            "method": method,
            "params": params,
            "data": data,
        })
        if resp is not None:
            return resp["params"]
        from sign_service.models import SignRequest
        from sign_service.providers import registry
        return registry.get("tieba").sign(SignRequest(
            platform="tieba", method=method, params=params, data=data
        )).params


def get_client() -> SignServiceClient:
    """获取全局单例 SignServiceClient(基于 config.SIGN_SERVICE_URL)"""
    global _singleton
    if _singleton is None:
        base_url = getattr(config, "SIGN_SERVICE_URL", "http://127.0.0.1:8888")
        _singleton = SignServiceClient(base_url)
    return _singleton


def is_enabled() -> bool:
    """是否启用签名服务(仅判断开关,不探测可用性)"""
    return bool(getattr(config, "ENABLE_SIGN_SERVICE", False))

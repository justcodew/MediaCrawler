# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1
#
# 百度贴吧签名 provider (PC 端 md5 签名,纯 Python)
# 复用 media_platform.tieba.client.BaiduTieBaClient._sign_pc_params 的逻辑。
#
# 说明:贴吧的 PC API 主要通过 playwright page.evaluate fetch 发请求(借浏览器登录态与同源优势),
# 签名只是其中一步(算 sign 参数)。本 provider 只负责计算 sign,不替浏览器发请求。
# 贴吧脱浏览器较复杂(需 STOKEN/BDUSS 等),阶段四再处理。

from sign_service.models import SignRequest, SignResponse
from sign_service.providers.base import SignProvider, registry

#: 与 media_platform/tieba/client.py:39 保持一致的签名盐值
PC_SIGN_SECRET = "36770b1f34c9bbf2e7d1a99d2b82fa9e"


def _sign_pc_params(params: dict) -> str:
    """复制自 media_platform/tieba/client.py:67 的 _sign_pc_params 逻辑"""
    import hashlib

    sign_text = ""
    for key in sorted(params):
        if key in {"sign", "sig"} or params[key] is None:
            continue
        sign_text += f"{key}={params[key]}"
    sign_text += PC_SIGN_SECRET
    return hashlib.md5(sign_text.encode("utf-8")).hexdigest()


class TiebaSignProvider(SignProvider):
    platform = "tieba"

    def sign(self, req: SignRequest) -> SignResponse:
        # client._fetch_json_by_browser 里:先给 sign_source 补 subapp_type/_client_type,再算 sign
        params = dict(req.params or {})
        method = (req.method or "GET").upper()
        # 与 client 保持一致:POST 用 data,GET 用 params 作为 sign_source
        sign_source = (req.data if method == "POST" else params) or params
        sign_source.setdefault("subapp_type", "pc")
        sign_source.setdefault("_client_type", "20")
        sign_source["sign"] = _sign_pc_params(sign_source)

        # 返回补全后的参数(含 subapp_type/_client_type/sign),client 可直接用
        return SignResponse(
            platform=self.platform,
            params={k: str(v) for k, v in sign_source.items()},
            raw={"sign": sign_source["sign"]},
        )


registry.register(TiebaSignProvider())

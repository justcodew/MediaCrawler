# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1
#
# 小红书签名 provider
# 复用 media_platform.xhs.playwright_sign.sign_with_xhshow (纯算法,依赖 xhshow 库)
# 该模块在 import 时会执行 monkey-patch(_patch_xhshow_a3_hash),故在服务侧 import 即可生效。

from sign_service.models import SignRequest, SignResponse
from sign_service.providers.base import SignProvider, registry


class XhsSignProvider(SignProvider):
    platform = "xhs"

    def sign(self, req: SignRequest) -> SignResponse:
        # 用轻量加载器加载签名模块,避免触发 media_platform/xhs/__init__.py 的重型依赖
        from sign_service._loader import get_attr
        sign_with_xhshow = get_attr("xhs", "media_platform.xhs.playwright_sign", "sign_with_xhshow")

        data = req.data if req.method.upper() == "POST" else req.params
        signs = sign_with_xhshow(
            uri=req.uri,
            data=data,
            cookie_str=req.cookies,
            method=req.method,
        )
        # 注意:返回的 key 与 client.py:_pre_headers 中 headers 字典保持一致(大写 X-S 等)
        headers = {
            "X-S": signs["x-s"],
            "X-T": signs["x-t"],
            "x-S-Common": signs["x-s-common"],
            "X-B3-Traceid": signs["x-b3-traceid"],
        }
        return SignResponse(platform=self.platform, headers=headers, raw=signs)


registry.register(XhsSignProvider())

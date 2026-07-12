# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1
#
# 知乎签名 provider
# 复用 media_platform.zhihu.help.sign (execjs 调 libs/zhihu.js)
# 知乎签名需要完整 url(含 query) + cookies。

from sign_service.models import SignRequest, SignResponse
from sign_service.providers.base import SignProvider, registry


class ZhihuSignProvider(SignProvider):
    platform = "zhihu"

    def sign(self, req: SignRequest) -> SignResponse:
        from sign_service._loader import get_attr
        sign = get_attr("zhihu", "media_platform.zhihu.help", "sign")

        sign_res = sign(req.url, req.cookies)
        # help.sign 返回 {"x-zst-81": ..., "x-zse-96": ...}
        headers = {
            "x-zst-81": sign_res.get("x-zst-81", ""),
            "x-zse-96": sign_res.get("x-zse-96", ""),
        }
        return SignResponse(platform=self.platform, headers=headers, raw=sign_res)


registry.register(ZhihuSignProvider())

# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1
#
# 抖音签名 provider
# 复用 media_platform.douyin.help.get_a_bogus_from_js (execjs 调 libs/douyin.js)
# 抖音签名依赖 UA,调用方必须传 user_agent。

from urllib.parse import urlencode

from sign_service.models import SignRequest, SignResponse
from sign_service.providers.base import SignProvider, registry


class DouyinSignProvider(SignProvider):
    platform = "douyin"

    def sign(self, req: SignRequest) -> SignResponse:
        from sign_service._loader import get_attr
        get_a_bogus_from_js = get_attr("douyin", "media_platform.douyin.help", "get_a_bogus_from_js")

        # client.py 中 query_string = urllib.parse.urlencode(params),这里保持一致
        params = req.params or {}
        query_string = req.url or urlencode(params)
        # client 传的 url 实际是 uri(get_a_bogus_from_js 内部仅用于判断 /reply 分支)
        url = req.uri or req.url
        a_bogus = get_a_bogus_from_js(url, query_string, req.user_agent)
        return SignResponse(
            platform=self.platform,
            params={"a_bogus": a_bogus},
            raw={"a_bogus": a_bogus},
        )


registry.register(DouyinSignProvider())

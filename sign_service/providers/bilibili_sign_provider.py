# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1
#
# B站签名 provider (wbi 签名算法,纯 Python)
# 复用 media_platform.bilibili.help.BilibiliSign
#
# 注意:BilibiliSign 需要 img_key/sub_key,这两个值通常来自浏览器 localStorage 的 wbi_img_urls。
# 在签名服务模式下,client 端需先从浏览器取到 img_key/sub_key,放入 req.extra 传过来。
# 服务本身不维护浏览器,无法自行获取 wbi keys。

from sign_service.models import SignRequest, SignResponse
from sign_service.providers.base import SignProvider, registry


class BilibiliSignProvider(SignProvider):
    platform = "bilibili"

    def sign(self, req: SignRequest) -> SignResponse:
        from sign_service._loader import get_attr
        BilibiliSign = get_attr("bilibili", "media_platform.bilibili.help", "BilibiliSign")

        extra = req.extra or {}
        img_key = extra.get("img_key", "")
        sub_key = extra.get("sub_key", "")
        if not img_key or not sub_key:
            raise ValueError(
                "bilibili 签名需要 img_key/sub_key,请通过 request.extra 传入 "
                "(来自浏览器 localStorage 的 wbi_img_urls 解析结果)"
            )

        # BilibiliSign.sign 会原地给 req_data 加 wts/w_rid 并返回
        req_data = dict(req.params or {})
        signed_params = BilibiliSign(img_key, sub_key).sign(req_data)
        # 全部参数(wts/w_rid 及原始参数)都需带回 client 拼到 query
        return SignResponse(
            platform=self.platform,
            params={k: str(v) for k, v in signed_params.items()},
            raw={"signed_params": signed_params},
        )


registry.register(BilibiliSignProvider())

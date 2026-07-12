# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1
#
# 签名服务 (SignSrv) 数据模型
# 将各平台签名逻辑解耦为独立 HTTP 微服务,降低 crawler 进程对 Node 运行时(execjs)的依赖。

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class SignRequest(BaseModel):
    """统一签名请求模型

    各平台签名所需的输入差异较大,这里用一组通用字段覆盖:
    - xhs: uri + method + data + cookies
    - douyin: url + params + user_agent
    - zhihu: url + cookies
    - bilibili: params (含 img_key/sub_key 由 provider 自取)
    - tieba: params + method

    所有平台共用同一请求体,provider 自行选取所需字段。
    """

    platform: str = Field(..., description="平台标识: xhs/douyin/zhihu/bilibili/tieba")
    uri: str = Field(default="", description="API 路径(不含 host),如 /api/sns/web/v1/search/notes")
    url: str = Field(default="", description="完整 URL(部分平台如知乎/抖音需要完整带 query 的 url)")
    method: str = Field(default="GET", description="请求方法 GET/POST")
    params: Optional[Dict[str, Any]] = Field(default=None, description="GET 查询参数")
    data: Optional[Dict[str, Any]] = Field(default=None, description="POST 请求体")
    cookies: str = Field(default="", description="Cookie 字符串")
    user_agent: str = Field(default="", description="User-Agent,抖音 a_bogus 签名必需")
    extra: Optional[Dict[str, Any]] = Field(default=None, description="扩展字段,如 bilibili 的 img_key/sub_key")


class SignResponse(BaseModel):
    """统一签名响应模型

    不同平台的签名产物不同:
    - xhs/zhihu: 产出 headers (x-s, x-zse-96 等)
    - bilibili/tieba: 产出 params (w_rid, sign 等)
    - douyin: 产出 params (a_bogus)

    用 headers + params 两个 dict 同时返回,client 端按平台取用。
    """

    platform: str
    headers: Dict[str, str] = Field(default_factory=dict, description="需注入请求头的签名字段")
    params: Dict[str, str] = Field(default_factory=dict, description="需追加到 URL query 的签名字段")
    raw: Optional[Dict[str, Any]] = Field(default=None, description="原始签名结果,调试用")


class HealthResponse(BaseModel):
    """健康检查响应"""

    status: str = "ok"
    providers: list[str] = Field(default_factory=list, description="已注册的平台 provider 列表")

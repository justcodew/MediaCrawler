# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1
#
# SignSrv 一致性测试
#
# 验证内容:
# 1. 签名服务启动正常,/health 返回已注册 provider
# 2. 纯 Python 算法平台(bilibili/tieba)的 provider 与 client fallback 输出结构一致
# 3. 依赖第三方库的平台(xhs→xhshow, douyin/zhihu→execjs)在库缺失时优雅 skip
# 4. SignServiceClient 在服务不可达时正确 fallback 到本地实现

import pytest
from fastapi.testclient import TestClient

from sign_service.app import app
from sign_service.models import SignRequest
from sign_service.providers import registry


# ---------- 依赖可用性探测 ----------

def _has_module(name: str) -> bool:
    try:
        __import__(name)
        return True
    except Exception:
        return False


HAS_XHSHOW = _has_module("xhshow")
HAS_EXECJS = _has_module("execjs")


# ---------- 服务基础设施 ----------

client = TestClient(app)


def test_health_returns_registered_providers():
    """健康检查应返回 5 个已注册平台"""
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    expected = {"xhs", "douyin", "zhihu", "bilibili", "tieba"}
    assert set(body["providers"]) == expected


def test_registry_lists_all_platforms():
    """注册表应包含全部 5 个平台"""
    assert set(registry.list_platforms()) == {"xhs", "douyin", "zhihu", "bilibili", "tieba"}


def test_unknown_platform_returns_400():
    """未知平台应返回 400 而非 500"""
    resp = client.post("/sign", json={"platform": "unknown", "uri": "/x"})
    assert resp.status_code == 400


# ---------- bilibili (纯 Python,无外部依赖) ----------

def test_bilibili_provider_signs_params():
    """B站 wbi 签名应在 params 中产出 w_rid 与 wts"""
    req = SignRequest(
        platform="bilibili",
        params={"foo": "bar", "page": 1},
        extra={"img_key": "7cd084941338484aae1ad9425b84077c",
               "sub_key": "4932caff0ff746eab6f01bf08b70ac45"},
    )
    resp = registry.get("bilibili").sign(req)
    assert "w_rid" in resp.params
    assert "wts" in resp.params
    assert len(resp.params["w_rid"]) == 32  # md5 hex


def test_bilibili_provider_requires_keys():
    """缺 img_key/sub_key 应抛 ValueError"""
    req = SignRequest(platform="bilibili", params={"foo": "bar"})
    with pytest.raises(ValueError):
        registry.get("bilibili").sign(req)


@pytest.mark.asyncio
async def test_bilibili_client_fallback_matches_provider():
    """SignServiceClient 在服务不可达时,fallback 的本地 wbi 签名应产出相同结构"""
    from sign_client.client import SignServiceClient

    sc = SignServiceClient("http://127.0.0.1:1")  # 不可达端口
    img_key, sub_key = "7cd084941338484aae1ad9425b84077c", "4932caff0ff746eab6f01bf08b70ac45"
    result = await sc.sign_bilibili({"foo": "bar"}, img_key, sub_key)
    assert "w_rid" in result and "wts" in result


# ---------- tieba (纯 Python,无外部依赖) ----------

def test_tieba_provider_signs_params():
    """贴吧签名应补全 subapp_type/_client_type/sign"""
    req = SignRequest(platform="tieba", params={"kz": "12345", "pn": 1})
    resp = registry.get("tieba").sign(req)
    assert resp.params.get("subapp_type") == "pc"
    assert resp.params.get("_client_type") == "20"
    assert len(resp.params["sign"]) == 32  # md5 hex


def test_tieba_sign_skips_existing_sign_field():
    """已有的 sign/sig 字段不参与签名计算"""
    req = SignRequest(platform="tieba", params={"kz": "12345", "sign": "old"})
    resp = registry.get("tieba").sign(req)
    # 新算出的 sign 不应等于旧值
    assert resp.params["sign"] != "old"


@pytest.mark.asyncio
async def test_tieba_client_fallback_matches_provider():
    """SignServiceClient 在服务不可达时 fallback 贴吧签名"""
    from sign_client.client import SignServiceClient

    sc = SignServiceClient("http://127.0.0.1:1")
    result = await sc.sign_tieba({"kz": "12345"})
    assert "sign" in result and result.get("subapp_type") == "pc"


# ---------- xhs/douyin/zhihu (依赖第三方库,缺失时 skip) ----------

@pytest.mark.skipif(not HAS_XHSHOW, reason="xhshow 库未安装")
def test_xhs_provider_returns_full_headers():
    """小红书签名应返回 x-s/x-t/x-s-common/x-b3-traceid 四个头"""
    req = SignRequest(
        platform="xhs",
        uri="/api/sns/web/v1/search/notes",
        method="POST",
        data={"keyword": "test", "page": 1},
        cookies="a1=abc",
    )
    resp = registry.get("xhs").sign(req)
    for key in ("X-S", "X-T", "x-S-Common", "X-B3-Traceid"):
        assert key in resp.headers


@pytest.mark.skipif(not HAS_XHSHOW, reason="xhshow 库未安装")
@pytest.mark.asyncio
async def test_xhs_client_fallback_matches_provider():
    """SignServiceClient fallback 小红书签名"""
    from sign_client.client import SignServiceClient

    sc = SignServiceClient("http://127.0.0.1:1")
    result = await sc.sign_xhs("/api/sns/web/v1/feed", {"note_id": "x"}, "a1=abc", "POST")
    assert "x-s" in result and "x-t" in result


@pytest.mark.skipif(not HAS_EXECJS, reason="execjs/Node 未安装")
def test_douyin_provider_returns_a_bogus():
    """抖音签名应返回 a_bogus"""
    req = SignRequest(
        platform="douyin",
        uri="/aweme/v1/web/general/search/item/",
        url="keyword=test",
        user_agent="Mozilla/5.0 (test)",
    )
    resp = registry.get("douyin").sign(req)
    assert "a_bogus" in resp.params and resp.params["a_bogus"]


@pytest.mark.skipif(not HAS_EXECJS, reason="execjs/Node 未安装")
def test_zhihu_provider_returns_headers():
    """知乎签名应返回 x-zst-81/x-zse-96"""
    req = SignRequest(
        platform="zhihu",
        url="https://www.zhihu.com/api/v4/search?q=test",
        cookies="d_c0=AAA...",
    )
    resp = registry.get("zhihu").sign(req)
    assert "x-zst-81" in resp.headers and "x-zse-96" in resp.headers


# ---------- HTTP 端点集成 ----------

def test_sign_endpoint_bilibili_via_http():
    """通过 HTTP /sign 调 bilibili provider 应正常返回"""
    resp = client.post("/sign", json={
        "platform": "bilibili",
        "params": {"foo": "bar"},
        "extra": {"img_key": "7cd084941338484aae1ad9425b84077c",
                  "sub_key": "4932caff0ff746eab6f01bf08b70ac45"},
    })
    assert resp.status_code == 200
    body = resp.json()
    assert "w_rid" in body["params"]


def test_sign_endpoint_bilibili_missing_keys_returns_422():
    """bilibili 缺 img_key 应返回 422(业务参数错误)"""
    resp = client.post("/sign", json={"platform": "bilibili", "params": {"foo": "bar"}})
    assert resp.status_code == 422

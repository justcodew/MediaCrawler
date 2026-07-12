# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1
#
# SignSrv —— 签名服务 (独立 HTTP 微服务)
#
# 将各平台的签名算法(execjs + JS / 纯 Python)封装为统一 HTTP 接口,crawler 进程通过
# sign_client.SignServiceClient 调用,从而把 Node 运行时依赖(execjs)收敛到本服务,
# crawler 主进程无需安装 Node。
#
# 启动方式:
#   uv run uvicorn sign_service.app:app --host 127.0.0.1 --port 8888
#   或: uv run python -m sign_service.app
#
# 设计说明:provider 直接复用 media_platform 下已有的纯算法模块,不在服务里重复实现签名,
# 保证「本地签名」与「服务签名」输出完全一致。

import logging

from fastapi import FastAPI, HTTPException

from sign_service.models import HealthResponse, SignRequest, SignResponse
# import 触发各 provider 注册到 registry
from sign_service.providers import registry

logger = logging.getLogger("sign_service")

app = FastAPI(
    title="MediaCrawler SignSrv",
    description="多平台签名服务 —— 将 crawler 的签名逻辑解耦为独立 HTTP 微服务",
    version="1.0.0",
)


@app.get("/health", response_model=HealthResponse, tags=["meta"])
async def health() -> HealthResponse:
    """健康检查 —— 返回已注册的平台 provider 列表"""
    return HealthResponse(status="ok", providers=registry.list_platforms())


@app.post("/sign", response_model=SignResponse, tags=["sign"])
async def sign(req: SignRequest) -> SignResponse:
    """统一签名接口

    请求体见 SignRequest,按 platform 路由到对应 provider。
    返回 SignResponse(headers / params),client 端按平台取用。
    """
    try:
        provider = registry.get(req.platform)
    except KeyError as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        return provider.sign(req)
    except ValueError as e:
        # 业务参数错误(如 bilibili 缺 img_key)
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.exception(f"[SignSrv] {req.platform} 签名失败")
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")


def main() -> None:
    """命令行入口: uv run python -m sign_service.app"""
    import uvicorn

    uvicorn.run(
        "sign_service.app:app",
        host="127.0.0.1",
        port=8888,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()

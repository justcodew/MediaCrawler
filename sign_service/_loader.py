# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1
#
# 轻量模块加载器:按文件路径加载 media_platform 下某个子模块,跳过其包 __init__.py。
#
# 背景:media_platform/<platform>/__init__.py 都会 from .core import *,而 core.py 依赖
# pandas/playwright 等重型库。SignSrv 只需要纯签名算法(help.py / *_sign.py),不应被迫
# 安装这些重型依赖。本加载器用 importlib 直接按文件加载目标模块,绕开包初始化副作用。
#
# 对同包内相对 import(如 playwright_sign.py 的 `from .xhs_sign import get_trace_id`),
# 加载器会先把依赖的兄弟模块按文件加载并登记到 sys.modules,使相对 import 能解析成功。

import importlib.util
import sys
import time
import types
from pathlib import Path
from types import ModuleType
from typing import Dict, Iterable, Tuple

#: 项目根目录(sign_service 的上两级)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _maybe_stub_tools_utils() -> None:
    """若 tools.utils 尚未加载,登记一个极轻量的 stub,避免被加载模块触发
    tools/utils.py → crawler_util → playwright 的重型依赖链。

    签名算法模块只用 utils 的少量纯函数(如 get_unix_timestamp / get_current_timestamp /
    get_user_agent / convert_browser_context_cookies / logger),这里按需补齐常用项。
    被 stub 的属性在真实 crawler 进程中不会被用到(那里 tools.utils 是完整加载的)。
    """
    if "tools.utils" in sys.modules:
        return
    if "tools" not in sys.modules:
        pkg = types.ModuleType("tools")
        pkg.__path__ = [str(_PROJECT_ROOT / "tools")]
        pkg.__package__ = "tools"
        sys.modules["tools"] = pkg

    stub = types.ModuleType("tools.utils")
    import logging
    stub.logger = logging.getLogger("sign_service")
    stub.get_unix_timestamp = lambda: int(time.time())
    stub.get_current_timestamp = lambda: int(time.time() * 1000)
    stub.get_user_agent = lambda: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    # 兜底:未命中的属性返回 None,避免签名路径外的引用直接报错
    stub.__getattr__ = lambda name: None  # type: ignore[attr-defined]
    sys.modules["tools.utils"] = stub
    # 同时让 `from tools import utils` 在已加载 tools 包上能取到
    sys.modules["tools"].utils = stub  # type: ignore[attr-defined]


def _maybe_stub_optional_deps() -> None:
    """对签名路径外的「可选重型依赖」(playwright 等)做宽容 stub。

    背景:部分平台的 help.py 顶部 `from playwright.async_api import Page` 仅用于类型注解
    (如 douyin/help.py 的 `page: Page = None`),签名本身不调用 playwright。
    SignSrv 轻量环境下未装 playwright 时,这类 import 会让加载失败。
    这里在它们缺失时注入一个「允许任意属性访问」的 stub,使注解 import 不报错;
    若真实调用到(不该在签名路径发生),会抛 AttributeError 提示。
    """
    _OPTIONAL_HEAVY = ("playwright", "playwright.async_api", "parsel")
    for modname in _OPTIONAL_HEAVY:
        if modname in sys.modules:
            continue
        try:
            __import__(modname)
        except Exception:
            stub = types.ModuleType(modname)
            # 允许任意属性访问(类型注解 import 不会报错);调用时返回的也是 stub
            stub.__getattr__ = lambda name, _mn=modname: _make_any_attr(_mn, name)  # type: ignore[attr-defined]
            sys.modules[modname] = stub


def _make_any_attr(modname: str, attr: str):
    """构造一个可被当作「任意类型」使用的占位对象。"""
    class _Any:
        def __init__(self):
            self.__name__ = f"{modname}.{attr}"
        def __call__(self, *a, **k):
            raise RuntimeError(
                f"SignSrv 轻量环境调用了未安装的可选依赖 {modname}.{attr};"
                f"若签名确实需要它,请安装该依赖。"
            )
        def __getattr__(self, name):
            return _Any()
    return _Any()

#: 平台 -> 加载计划:主模块 + 需预加载的兄弟模块(按文件相对路径, 全限定名)
#: 顺序即加载顺序,被依赖的兄弟模块必须排在前面。
_PLAN: Dict[str, Iterable[Tuple[str, str]]] = {
    "xhs": [
        ("media_platform/xhs/xhs_sign.py", "media_platform.xhs.xhs_sign"),
        ("media_platform/xhs/playwright_sign.py", "media_platform.xhs.playwright_sign"),
    ],
    "douyin": [
        ("media_platform/douyin/help.py", "media_platform.douyin.help"),
    ],
    "zhihu": [
        ("media_platform/zhihu/help.py", "media_platform.zhihu.help"),
    ],
    "bilibili": [
        ("media_platform/bilibili/help.py", "media_platform.bilibili.help"),
    ],
    "tieba": [
        ("media_platform/tieba/client.py", "media_platform.tieba.client"),
    ],
}


def _register_empty_pkg(pkg_full: str) -> None:
    """把包登记为「空包」(不执行其 __init__.py),仅设置 __path__,让 import 系统能解析子模块。

    例如注册 media_platform.xhs 为空包后,加载 media_platform.xhs.playwright_sign 时,
    其 `from .xhs_sign import ...` 会去找已登记的兄弟模块,而不是触发 xhs/__init__.py。
    """
    if pkg_full in sys.modules:
        existing = sys.modules[pkg_full]
        # 已存在的非空包(真实 __init__ 已执行过)保持原样,不覆盖
        if getattr(existing, "__path__", None) is None:
            return
        return
    # 推断包目录:按全限定名最后一段
    parts = pkg_full.split(".")
    pkg_dir = _PROJECT_ROOT.joinpath(*parts)
    pkg = types.ModuleType(pkg_full)
    pkg.__path__ = [str(pkg_dir)]
    pkg.__package__ = pkg_full
    sys.modules[pkg_full] = pkg


def _load_file_module(rel_path: str, full_name: str) -> ModuleType:
    """按文件路径加载模块并登记到 sys.modules"""
    if full_name in sys.modules:
        return sys.modules[full_name]

    file_path = _PROJECT_ROOT / rel_path
    spec = importlib.util.spec_from_file_location(full_name, file_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"无法加载模块 {full_name} @ {file_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[full_name] = module
    spec.loader.exec_module(module)
    return module


def load_platform(platform: str) -> Dict[str, ModuleType]:
    """按计划加载某平台的所有签名相关模块,返回 {full_name: module}。

    重复调用命中 sys.modules 缓存。父包会被登记为空包以隔离 __init__ 副作用。
    """
    plan = _PLAN.get(platform)
    if not plan:
        raise KeyError(f"未配置平台 {platform!r} 的模块加载计划")

    # 先把所有相关父包登记为空包(阻止 core.py 等 __init__ 副作用)
    for _, full_name in plan:
        parts = full_name.split(".")
        for i in range(1, len(parts)):
            _register_empty_pkg(".".join(parts[:i]))
    # media_platform 顶层包也登记为空包
    _register_empty_pkg("media_platform")
    # 预置轻量 tools.utils stub,避免签名模块触发 playwright 等重型依赖
    _maybe_stub_tools_utils()
    # 对签名路径外的可选重型依赖(playwright/parsel 等)做宽容 stub
    _maybe_stub_optional_deps()

    loaded: Dict[str, ModuleType] = {}
    for rel_path, full_name in plan:
        loaded[full_name] = _load_file_module(rel_path, full_name)
    return loaded


def get_attr(platform: str, full_name: str, attr: str):
    """加载平台模块并取出指定属性"""
    load_platform(platform)
    module = sys.modules[full_name]
    return getattr(module, attr)

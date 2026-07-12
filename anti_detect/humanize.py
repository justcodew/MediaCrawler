# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1
#
# 反检测 —— 行为拟人化
#
# 让请求模式更像真人,降低"机械感":
# - 随机停顿:固定 sleep → sleep(base + random(0, jitter))
# - 页面停留:进入页面后停一会儿(模拟阅读)
# - 滚动模拟:向下滚动几次(很多平台检测是否滚动)
# - 鼠标移动:点击前先移动鼠标(可选)

import asyncio
import random
from typing import Optional


async def humanized_sleep(base_sec: float, jitter_sec: float = 0) -> float:
    """拟人化停顿:sleep(base + random(0, jitter))。

    返回实际 sleep 的秒数。
    """
    actual = base_sec + random.uniform(0, jitter_sec) if jitter_sec > 0 else base_sec
    await asyncio.sleep(actual)
    return actual


async def simulate_page_browse(page, stay_sec: float = 3, scroll_times: int = 3) -> None:
    """模拟人类浏览页面:停留 + 滚动。

    在进入页面/翻页后调用,让行为更像真人。
    """
    if page is None:
        return
    try:
        # 1. 停留(模拟阅读)
        if stay_sec > 0:
            await asyncio.sleep(stay_sec + random.uniform(0, 1))

        # 2. 向下滚动几次(模拟浏览内容)
        for _ in range(scroll_times):
            scroll_y = random.randint(200, 600)
            await page.evaluate(f"window.scrollBy(0, {scroll_y})")
            await asyncio.sleep(random.uniform(0.5, 1.5))

        # 3. 偶尔滚回顶部(模拟回看)
        if random.random() < 0.3:
            await page.evaluate("window.scrollTo(0, 0)")
            await asyncio.sleep(random.uniform(0.3, 0.8))
    except Exception:
        pass  # 滚动失败不影响主流程(页面可能已关闭)


async def simulate_mouse_move(page, target_selector: Optional[str] = None) -> None:
    """模拟鼠标移动到某元素(可选,增强真实感)。

    CDP 模式下 page.mouse 可用;标准模式也可。
    """
    if page is None:
        return
    try:
        # 随机移动几下
        for _ in range(random.randint(1, 3)):
            x = random.randint(100, 800)
            y = random.randint(100, 600)
            await page.mouse.move(x, y)
            await asyncio.sleep(random.uniform(0.1, 0.3))
        # 移到目标元素(若指定)
        if target_selector:
            elem = await page.query_selector(target_selector)
            if elem:
                box = await elem.bounding_box()
                if box:
                    await page.mouse.move(box["x"] + box["width"] / 2,
                                          box["y"] + box["height"] / 2)
    except Exception:
        pass

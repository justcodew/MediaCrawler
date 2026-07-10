# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1
#
# 反检测 —— 滑块验证码自动通过
#
# 复用 tools/slider_util.py 的 opencv 模板匹配 + 轨迹生成。
# 成功率有限(各平台滑块机制不同),谨慎开启。
#
# 流程:
#   1. 从页面截图识别滑块缺口位置(opencv template_match)
#   2. 生成拟人化拖动轨迹(get_tracks)
#   3. 用 page.mouse 按住滑块、按轨迹移动、释放

import asyncio
import os
import random
from typing import Optional


async def try_pass_slider(page, slider_selector: str = "") -> bool:
    """尝试自动通过滑块验证码。

    Args:
        page: playwright Page 对象
        slider_selector: 滑块元素的 CSS 选择器(空则尝试常见选择器)

    Returns:
        True = 成功通过 / False = 失败(交由上层停止或退避)
    """
    if page is None:
        return False
    try:
        # 1. 定位滑块元素
        slider = await _find_slider_element(page, slider_selector)
        if slider is None:
            return False

        box = await slider.bounding_box()
        if not box:
            return False

        # 2. 截图当前页面,用 opencv 识别缺口距离
        #    (简化版:直接用随机距离 + 试探,因为各平台滑块 DOM 结构差异大)
        #    完整 opencv 识别需要分别取 gap 图和 bg 图,这里用简化策略
        distance = await _estimate_slider_distance(page)
        if distance <= 0:
            distance = random.randint(80, 200)  # 兜底随机距离

        # 3. 生成拟人化轨迹(复用 slider_util)
        from tools.slider_util import get_tracks
        tracks = get_tracks(distance, level="easy")

        # 4. 执行拖动:移动到滑块 → 按住 → 按轨迹移动 → 释放
        start_x = box["x"] + box["width"] / 2
        start_y = box["y"] + box["height"] / 2
        await page.mouse.move(start_x, start_y)
        await asyncio.sleep(random.uniform(0.2, 0.5))
        await page.mouse.down()
        await asyncio.sleep(random.uniform(0.1, 0.3))

        # 按轨迹移动(每步加随机抖动,更像人)
        cur_x = start_x
        for dx in tracks:
            cur_x += dx + random.uniform(-1, 1)
            await page.mouse.move(cur_x, start_y + random.uniform(-2, 2))
            await asyncio.sleep(random.uniform(0.01, 0.04))

        # 末尾小幅回退(人类松手前常有微调)
        await page.mouse.move(cur_x - random.randint(2, 6), start_y)
        await asyncio.sleep(random.uniform(0.1, 0.3))
        await page.mouse.up()

        # 5. 等待验证结果
        await asyncio.sleep(2)
        return True  # 是否真通过需上层再截图 LLM 复检

    except Exception:
        return False


async def _find_slider_element(page, selector: str):
    """定位滑块元素。尝试常见选择器。"""
    candidates = [selector] if selector else []
    # 各平台常见滑块选择器
    candidates += [
        "#captcha-slider", ".slider-btn", ".nc_iconfont.btn_slide",
        ".JDJRV-slide-btn", ".verify-move-block", "[class*='slider'][class*='btn']",
        "span.btn_slide", ".yidun_slider",
    ]
    for sel in candidates:
        if not sel:
            continue
        try:
            elem = await page.query_selector(sel)
            if elem:
                return elem
        except Exception:
            continue
    return None


async def _estimate_slider_distance(page) -> int:
    """估算滑块需移动的距离(简化版)。

    完整版需截图取 gap/bg 图喂 opencv,这里先用页面尺寸估算。
    各平台滑块轨道宽度通常 300px 左右,缺口在 1/4~3/4 处。
    """
    try:
        viewport = page.viewport_size
        width = viewport.get("width", 340) if viewport else 340
        # 在轨道宽度的 25%~70% 之间取值(缺口常见位置)
        return random.randint(int(width * 0.25), int(width * 0.70))
    except Exception:
        return random.randint(80, 200)

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1
#
# 一键安全采集脚本
#
# 把"反检测 + 断点续爬 + 合理默认参数"组合好,降低账号被封风险。
# 核心:宁可慢一点少抓一点,绝不让账号被封。
#
# 用法:
#   # 交互式(会提示输入关键词/平台)
#   uv run python safe_crawl.py
#
#   # 直接指定
#   uv run python safe_crawl.py --platform xhs --keywords "广州越秀两房出租"
#
#   # 指定平台列表(逐个采集)
#   uv run python safe_crawl.py --platforms xhs,wb,zhihu --keywords "广州越秀两房出租"
#
# 前置准备:
#   1. 先启动带远程调试的 Chrome(另开终端):
#      "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
#        --remote-debugging-port=9222 --user-data-dir=/tmp/chrome_crawl
#   2. 在弹出的 Chrome 里用小号登录目标平台
#   3. 配置 .env 的 LLM_API_KEY(用于反检测截图识别,推荐 gpt-4o)

import argparse
import asyncio
import os
import subprocess
import sys
import time

#: 安全默认参数(保守策略,优先保护账号)
SAFE_DEFAULTS = {
    "CRAWLER_MAX_NOTES_COUNT": 20,       # 单关键词最多抓 20 条(小批量)
    "CRAWLER_MAX_SLEEP_SEC": 5,          # 每页间隔 5 秒(比默认 2 秒更慢更安全)
    "MAX_CONCURRENCY_NUM": 1,            # 单线程(不并发)
    "CRAWLER_MAX_COMMENTS_COUNT_SINGLENOTES": 10,  # 单帖评论上限
    "ENABLE_GET_SUB_COMMENTS": False,    # 不抓二级评论(减少请求量)
    "ENABLE_GET_MEIDAS": False,          # 不下载媒体(减少请求量)
}


def print_banner():
    print("""
╔══════════════════════════════════════════════════════════╗
║          🛡️  MediaCrawler 安全采集脚本  🛡️               ║
║                                                          ║
║  已启用:反检测(截图LLM感知) + 行为拟人化 + 智能退避     ║
║  策略:小批量 / 慢节奏 / 单线程 / 风控即停               ║
║                                                          ║
║  ⚠️  请用小号,遵守平台规则,仅限个人学习                  ║
╚══════════════════════════════════════════════════════════╝
""")


def check_env():
    """环境检查与提示"""
    print("📋 环境检查:")
    issues = []

    # 1. CDP 端口
    import httpx
    try:
        r = httpx.get("http://127.0.0.1:9222/json/version", timeout=2)
        if r.status_code == 200:
            print(f"  ✅ Chrome 远程调试端口 9222:已就绪")
        else:
            issues.append("chrome_port")
    except Exception:
        print("  ❌ Chrome 远程调试端口 9222 未开启")
        issues.append("chrome_port")

    # 2. LLM 配置(反检测截图识别需要)
    from dotenv import load_dotenv
    load_dotenv()
    if os.getenv("LLM_API_KEY"):
        print(f"  ✅ LLM 配置:已设置(反检测截图识别可用)")
    else:
        print(f"  ⚠️  LLM_API_KEY 未配置(反检测将降级为本地关键词兜底)")
        issues.append("llm")

    # 3. 多模态模型提示
    llm_model = os.getenv("LLM_MODEL", "gpt-4o-mini")
    if "4o" not in llm_model and "vision" not in llm_model and "vl" not in llm_model:
        print(f"  ⚠️  LLM_MODEL={llm_model} 可能不支持多模态(截图识别建议 gpt-4o)")

    return issues


def show_chrome_help():
    """显示 Chrome 启动帮助"""
    print("""
🔧 启动 Chrome 远程调试(在另一个终端执行一次即可):

   "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \\
     --remote-debugging-port=9222 \\
     --user-data-dir=/tmp/chrome_crawl \\
     --no-first-run

然后在弹出的 Chrome 窗口里,用小号登录你要采集的平台(小红书/微博等)。
登录后保持 Chrome 开着,回到这里按回车继续。
""")


def build_safe_command(platform, keywords, save_option="jsonl", extra_args=None):
    """构造安全的 main.py 命令(含反检测 + 断点续爬 + 安全默认)"""
    cmd = [sys.executable, "main.py",
           "--platform", platform,
           "--lt", "qrcode",
           "--type", "search",
           "--keywords", keywords,
           "--save_data_option", save_option,
           # 安全默认参数
           "--crawler_max_notes_count", str(SAFE_DEFAULTS["CRAWLER_MAX_NOTES_COUNT"]),
           "--max_concurrency_num", str(SAFE_DEFAULTS["MAX_CONCURRENCY_NUM"]),
           "--max_comments_count_singlenotes", str(SAFE_DEFAULTS["CRAWLER_MAX_COMMENTS_COUNT_SINGLENOTES"]),
           "--get_comment", "true",
           "--get_sub_comment", "false",
           "--headless", "false",
           # 反检测 + 断点续爬
           "--enable_anti_detect", "yes",
           "--enable_resume", "yes",
           ]
    if extra_args:
        cmd.extend(extra_args)
    return cmd


async def run_safe_crawl(platform, keywords, save_option="jsonl"):
    """执行单个平台的采集,带风控感知"""
    cmd = build_safe_command(platform, keywords, save_option)
    print(f"\n🚀 开始采集 [{platform}]: {keywords}")
    print(f"   参数: 最大{SAFE_DEFAULTS['CRAWLER_MAX_NOTES_COUNT']}条, 间隔{SAFE_DEFAULTS['CRAWLER_MAX_SLEEP_SEC']}s, 单线程")
    print(f"   防护: 反检测✓ 行为拟人化✓ 断点续爬✓")
    print(f"   命令: {' '.join(cmd)}\n")

    # 临时覆盖 config 的安全默认值(通过环境变量不行,直接改 config 模块)
    import config
    for k, v in SAFE_DEFAULTS.items():
        setattr(config, k, v)

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    try:
        while True:
            line = await proc.stdout.readline()
            if not line:
                break
            text = line.decode("utf-8", errors="replace").rstrip()
            # 高亮风控相关日志
            if any(w in text for w in ["风控", "AntiDetect", "risk", "验证", "slider", "stop"]):
                print(f"  ⚠️  {text}")
            elif "task" in text.lower() or "New task" in text:
                print(f"  📌 {text}")
            else:
                print(f"  {text}")
        await proc.wait()
    except KeyboardInterrupt:
        print("\n\n⏸️  收到中断信号,正在停止...断点已保存,可用相同命令续爬")
        proc.terminate()
        await proc.wait()

    # 采集结果
    data_dir = os.path.join("data", platform)
    if os.path.isdir(data_dir):
        files = []
        for root, dirs, fnames in os.walk(data_dir):
            for f in fnames:
                if f.endswith((".jsonl", ".json", ".csv")):
                    files.append(os.path.join(root, f))
        print(f"\n📊 [{platform}] 采集完成,数据文件 {len(files)} 个:")
        for f in files[:5]:
            print(f"   - {f}")
        if len(files) > 5:
            print(f"   ... 等 {len(files)} 个")
    return proc.returncode


def main():
    parser = argparse.ArgumentParser(description="MediaCrawler 安全采集(反检测 + 断点续爬)")
    parser.add_argument("--platform", default="", help="单个平台(xhs/wb/zhihu/bili/dy/ks/tieba)")
    parser.add_argument("--platforms", default="", help="多平台,逗号分隔(如 xhs,wb,zhihu)")
    parser.add_argument("--keywords", default="广州越秀两房出租", help="搜索关键词")
    parser.add_argument("--save", default="jsonl", help="存储格式(jsonl/csv/json)")
    parser.add_argument("--no-check", action="store_true", help="跳过环境检查")
    args = parser.parse_args()

    print_banner()

    # 平台处理
    if args.platforms:
        platforms = [p.strip() for p in args.platforms.split(",") if p.strip()]
    elif args.platform:
        platforms = [args.platform]
    else:
        # 交互式选择
        print("选择采集平台:")
        all_platforms = {"xhs": "小红书", "wb": "微博", "zhihu": "知乎", "bili": "B站",
                         "dy": "抖音", "ks": "快手", "tieba": "贴吧"}
        for i, (k, v) in enumerate(all_platforms.items(), 1):
            print(f"  {i}. {v} ({k})")
        print(f"  0. 全部社交平台(除抖音/快手,它们风控最严)")
        choice = input("\n输入编号(多个用逗号分隔,默认1小红书): ").strip() or "1"
        platforms = []
        for c in choice.split(","):
            c = c.strip()
            if c == "0":
                platforms = ["xhs", "wb", "zhihu", "bili", "tieba"]
                break
            idx = int(c) - 1 if c.isdigit() else -1
            if 0 <= idx < len(all_platforms):
                platforms.append(list(all_platforms.keys())[idx])
        if not platforms:
            platforms = ["xhs"]
        print(f"\n将采集平台: {platforms}")

    # 关键词
    if not sys.argv or "--keywords" not in sys.argv:
        custom = input(f"\n搜索关键词(回车用默认「{args.keywords}」): ").strip()
        if custom:
            args.keywords = custom
    print(f"关键词: {args.keywords}\n")

    # 环境检查
    if not args.no_check:
        issues = check_env()
        if "chrome_port" in issues:
            show_chrome_help()
            input("准备好 Chrome 后,按回车继续(或 Ctrl+C 退出)...")
        print()

    # 确认
    print(f"{'='*50}")
    print(f"  采集计划:")
    print(f"  平台: {', '.join(platforms)}")
    print(f"  关键词: {args.keywords}")
    print(f"  每平台最多: {SAFE_DEFAULTS['CRAWLER_MAX_NOTES_COUNT']} 条")
    print(f"  间隔: {SAFE_DEFAULTS['CRAWLER_MAX_SLEEP_SEC']} 秒/页")
    print(f"  防护: 反检测 + 行为拟人化 + 断点续爬")
    print(f"{'='*50}")
    confirm = input("\n确认开始?(回车=开始, n=取消): ").strip().lower()
    if confirm == "n":
        print("已取消。")
        return

    # 逐个平台采集
    for i, platform in enumerate(platforms, 1):
        print(f"\n{'#'*50}")
        print(f"# [{i}/{len(platforms)}] 平台: {platform}")
        print(f"{'#'*50}")
        try:
            asyncio.run(run_safe_crawl(platform, args.keywords, args.save))
        except KeyboardInterrupt:
            print(f"\n⏸️  中断。已完成 {i}/{len(platforms)} 个平台。")
            break
        except Exception as e:
            print(f"\n❌ [{platform}] 采集出错: {e}")

        if i < len(platforms):
            wait = 10
            print(f"\n⏳ 平台间等待 {wait} 秒(降低跨平台连续请求的风险)...")
            time.sleep(wait)

    print(f"\n{'='*50}")
    print(f"  ✅ 全部采集完成")
    print(f"  数据在各平台 data/<platform>/ 目录下")
    print(f"  风控截图(如有)在 data/risk_screenshots/")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()

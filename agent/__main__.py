# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1
#
# AI 内容分析 Agent —— 命令行入口
#
# 用法:
#   uv run python -m agent --platform xhs --note <note_id>      # 分析单条
#   uv run python -m agent --platform xhs --limit 5            # 批量分析最近5条
#   uv run python -m agent --list-platforms                    # 列出有数据的平台
#   uv run python -m agent --list-reports                      # 列出已生成报告

import argparse
import asyncio
import os
import sys
from dotenv import load_dotenv

load_dotenv()  # 加载 .env 中的 LLM_API_KEY 等


def main():
    parser = argparse.ArgumentParser(description="MediaCrawler AI 内容分析 Agent")
    parser.add_argument("--platform", default="xhs", help="平台(xhs/douyin/bilibili/...)")
    parser.add_argument("--note", default="", help="单条内容的 note_id")
    parser.add_argument("--limit", type=int, default=5, help="批量分析条数(不指定 --note 时生效)")
    parser.add_argument("--list-platforms", action="store_true", help="列出有数据的平台")
    parser.add_argument("--list-reports", action="store_true", help="列出已生成报告")
    parser.add_argument("--save", action="store_true", help="保存报告到 data/analysis_reports/")
    args = parser.parse_args()

    if args.list_platforms:
        from agent import data_loader
        plats = data_loader.list_platforms()
        print("有数据的平台:", plats or "(无)")
        return

    if args.list_reports:
        from agent import content_remix
        reports = content_remix.list_reports()
        for r in reports[:20]:
            print(f"  {r['platform']} / {r['note_id']} / {r['ts']}")
        print(f"共 {len(reports)} 份报告")
        return

    from agent import config as agent_config, content_remix
    if not agent_config.is_configured():
        print("⚠️  LLM_API_KEY 未配置。请在 .env 设置:", file=sys.stderr)
        print("   LLM_API_KEY=sk-...", file=sys.stderr)
        print("   LLM_BASE_URL=https://api.openai.com/v1", file=sys.stderr)
        print("   LLM_MODEL=gpt-4o-mini", file=sys.stderr)
        sys.exit(1)

    async def run():
        if args.note:
            print(f"分析 {args.platform} / {args.note} ...")
            result = await content_remix.analyze_content(args.platform, args.note)
            results = [result]
        else:
            print(f"批量分析 {args.platform},最近 {args.limit} 条 ...")
            results = await content_remix.analyze_contents(args.platform, limit=args.limit)

        for r in results:
            print(f"\n{'='*60}")
            print(f"📌 {r['platform']} / {r['note_id']}")
            print(f"{'='*60}")
            print(r["content_text"])
            print(f"\n{'─'*60}")
            print("🤖 拆解报告")
            print(f"{'─'*60}")
            print(r["report"])
            if args.save:
                fpath = content_remix.save_report(r)
                print(f"\n💾 已保存: {fpath}")

    asyncio.run(run())


if __name__ == "__main__":
    main()

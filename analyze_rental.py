#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 房源数据分析 + Excel 导出
#
# 专门针对"租房笔记"做结构化提取:
#   - 价格(正则提取数字/范围)
#   - 区域(地铁站/地标)
#   - 户型(几房几厅)
#   - 亮点(电梯/地铁/精装/直租/押金)
# 然后做统计汇总 + 导出多 sheet Excel。

import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import List, Optional

#: 广州越秀及周边地铁站/地标(用于区域识别)
LANDMARKS = [
    "公园前", "农讲所", "淘金", "东山口", "区庄", "杨箕", "烈士陵园",
    "北京路", "海珠广场", "越秀公园", "动物园", "小北", "纪念堂",
    "建设大马路", "建设二马路", "建设六马路", "西门口", "中山纪念堂",
    "五羊邨", "珠江新城", "体育西",
]

#: 亮点关键词
HIGHLIGHTS = {
    "电梯": ["电梯", "电梯房"],
    "地铁": ["地铁", "🚇", "近地铁", "地铁口"],
    "精装": ["精装", "精装修", "装修很新"],
    "直租": ["直租", "房东直", "业主直", "无中介"],
    "免押": ["免押", "不用押", "0押", "免半个月押"],
    "拎包入住": ["拎包入住", "拎包"],
    "带阳台": ["阳台", "露台"],
    "民水电": ["民水电", "民水民电"],
    "采光好": ["采光", "南北对流"],
    "可明火": ["明火"],
}


def load_notes(path: str) -> List[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def load_comments(path: str) -> List[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def extract_price(text: str) -> Optional[int]:
    """从文本提取月租价格(元/月)。支持 2500/2.5k/1499 等格式。"""
    text = text or ""
    # 先匹配带 k 的(如 3.6k = 3600, 2k = 2000)
    m = re.search(r"(\d+(?:\.\d+)?)\s*[kK千](?:\+|\s|$)", text)
    if m:
        return int(float(m.group(1)) * 1000)
    # 匹配纯数字(4位数,租房价格区间 800~8000)
    m = re.search(r"(?<!\d)([1-9]\d{3})(?!\d)", text)
    if m:
        val = int(m.group(1))
        if 800 <= val <= 8000:
            return val
    # 匹配 3 位数(如 999,可能是 1499 的尾部,或低价)
    m = re.search(r"(\d{3})\+?", text)
    if m:
        val = int(m.group(1))
        if val >= 800:
            return val
    return None


def extract_rooms(text: str) -> Optional[str]:
    """提取户型(如 两房一厅、2房1厅)。"""
    text = text or ""
    # 两房一厅 / 2房1厅 / 两房 / 一房一厅
    num_map = {"一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "1": 1, "2": 2, "3": 3}
    m = re.search(r"([一二两三四1-4])\s*房\s*([一二两三1-3]?)\s*[厅室]?", text)
    if m:
        rooms = num_map.get(m.group(1), 0)
        living = num_map.get(m.group(2), 0) if m.group(2) else 0
        if rooms > 0:
            return f"{rooms}房{living}厅" if living else f"{rooms}房"
    return None


def extract_landmarks(text: str) -> List[str]:
    """提取提到的地标/地铁站。"""
    text = text or ""
    found = []
    for lm in LANDMARKS:
        if lm in text:
            found.append(lm)
    return found


def extract_highlights(text: str) -> List[str]:
    """提取亮点标签。"""
    text = text or ""
    found = []
    for tag, keywords in HIGHLIGHTS.items():
        if any(kw in text for kw in keywords):
            found.append(tag)
    return found


def extract_deposit(text: str) -> Optional[str]:
    """提取押金/付款方式。"""
    text = text or ""
    if "押一付一" in text or "压一付一" in text:
        return "押一付一"
    if "押二" in text:
        return "押二付一"
    if any(w in text for w in ["免押", "不用押", "0押", "免半个月押"]):
        return "免押金"
    return None


def analyze_notes(notes: List[dict]) -> List[dict]:
    """对每条笔记做结构化提取。"""
    results = []
    for n in notes:
        text = f"{n.get('title','')} {n.get('desc','')}"
        results.append({
            "note_id": n.get("note_id", ""),
            "标题": n.get("title", ""),
            "简介": (n.get("desc", "") or "")[:100],
            "月租(元)": extract_price(text),
            "户型": extract_rooms(text),
            "区域/地标": "、".join(extract_landmarks(text)),
            "亮点": "、".join(extract_highlights(text)),
            "押金": extract_deposit(text),
            "点赞": n.get("liked_count", 0),
            "收藏": n.get("collected_count", 0),
            "评论数": n.get("comment_count", 0),
            "标签": n.get("tag_list", ""),
            "昵称": n.get("nickname", ""),
            "链接": f"https://www.xiaohongshu.com/explore/{n.get('note_id','')}",
        })
    return results


def print_summary(analyzed: List[dict]) -> None:
    """打印统计汇总。"""
    print("=" * 60)
    print("📊 广州越秀两房出租 数据分析报告")
    print("=" * 60)

    # 价格分布
    prices = [a["月租(元)"] for a in analyzed if a["月租(元)"]]
    print(f"\n💰 价格分析(共 {len(prices)}/{len(analyzed)} 条提取到价格):")
    if prices:
        print(f"   最低: {min(prices)} 元/月")
        print(f"   最高: {max(prices)} 元/月")
        print(f"   均价: {sum(prices)//len(prices)} 元/月")
        # 价格区间分布
        ranges = {"1000以下": 0, "1000-2000": 0, "2000-3000": 0, "3000-4000": 0, "4000+": 0}
        for p in prices:
            if p < 1000: ranges["1000以下"] += 1
            elif p < 2000: ranges["1000-2000"] += 1
            elif p < 3000: ranges["2000-3000"] += 1
            elif p < 4000: ranges["3000-4000"] += 1
            else: ranges["4000+"] += 1
        print("   价格分布:")
        for r, c in ranges.items():
            bar = "█" * c
            print(f"     {r:12} {c}条 {bar}")

    # 区域分布
    all_lms = []
    for a in analyzed:
        all_lms.extend(a["区域/地标"].split("、") if a["区域/地标"] else [])
    lm_count = Counter([l for l in all_lms if l])
    print(f"\n🗺️  区域/地标 TOP(提及次数):")
    for lm, c in lm_count.most_common(8):
        print(f"   {lm}: {c}次")

    # 亮点分布
    all_hl = []
    for a in analyzed:
        all_hl.extend(a["亮点"].split("、") if a["亮点"] else [])
    hl_count = Counter([h for h in all_hl if h])
    print(f"\n✨ 亮点关键词:")
    for hl, c in hl_count.most_common():
        print(f"   {hl}: {c}条")

    # 押金方式
    deposits = [a["押金"] for a in analyzed if a["押金"]]
    dep_count = Counter(deposits)
    print(f"\n🔐 押金/付款方式:")
    for d, c in dep_count.most_common():
        print(f"   {d}: {c}条")

    # 互动数据
    total_likes = sum(a["点赞"] for a in analyzed if isinstance(a["点赞"], int))
    total_collects = sum(a["收藏"] for a in analyzed if isinstance(a["收藏"], int))
    print(f"\n📈 互动数据:")
    print(f"   总点赞: {total_likes}")
    print(f"   总收藏: {total_collects}")
    # 最热笔记
    top = sorted(analyzed, key=lambda x: x.get("点赞", 0) or 0, reverse=True)[:3]
    print(f"   🔥 热门 TOP3:")
    for i, a in enumerate(top, 1):
        print(f"     {i}. [{a['点赞']}赞] {a['标题'][:30]} ({a['月租(元)'] or '?'}元)")

    print("\n" + "=" * 60)


def export_excel(analyzed: List[dict], comments: List[dict], out_path: str,
                 llm_report: Optional[str] = None) -> None:
    """导出多 sheet Excel。"""
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment

    wb = Workbook()

    # 样式
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")

    # Sheet 1: 笔记详情
    ws1 = wb.active
    ws1.title = "房源笔记"
    headers1 = ["标题", "月租(元)", "户型", "区域/地标", "亮点", "押金",
                "点赞", "收藏", "评论数", "简介", "标签", "昵称", "链接"]
    ws1.append(headers1)
    for cell in ws1[1]:
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center")
    for a in analyzed:
        ws1.append([a[h] for h in headers1])
    # 列宽
    widths1 = [35, 10, 8, 18, 22, 10, 8, 8, 8, 50, 20, 12, 45]
    for i, w in enumerate(widths1, 1):
        ws1.column_dimensions[chr(64+i) if i <= 26 else "A"].width = w
    # 冻结首行
    ws1.freeze_panes = "A2"

    # Sheet 2: 价格统计
    ws2 = wb.create_sheet("价格统计")
    prices = [a["月租(元)"] for a in analyzed if a["月租(元)"]]
    ws2.append(["统计项", "数值"])
    for cell in ws2[1]:
        cell.font = header_font
        cell.fill = header_fill
    if prices:
        ws2.append(["房源总数", len(analyzed)])
        ws2.append(["提取到价格", len(prices)])
        ws2.append(["最低月租", min(prices)])
        ws2.append(["最高月租", max(prices)])
        ws2.append(["平均月租", sum(prices) // len(prices)])
        ws2.append([])
        ws2.append(["价格区间", "数量"])
        ranges = {"1000以下": 0, "1000-2000": 0, "2000-3000": 0, "3000-4000": 0, "4000+": 0}
        for p in prices:
            if p < 1000: ranges["1000以下"] += 1
            elif p < 2000: ranges["1000-2000"] += 1
            elif p < 3000: ranges["2000-3000"] += 1
            elif p < 4000: ranges["3000-4000"] += 1
            else: ranges["4000+"] += 1
        for r, c in ranges.items():
            ws2.append([r, c])
    ws2.column_dimensions["A"].width = 20
    ws2.column_dimensions["B"].width = 12

    # Sheet 3: 区域分布
    ws3 = wb.create_sheet("区域分布")
    ws3.append(["区域/地标", "提及次数"])
    for cell in ws3[1]:
        cell.font = header_font
        cell.fill = header_fill
    all_lms = []
    for a in analyzed:
        all_lms.extend(a["区域/地标"].split("、") if a["区域/地标"] else [])
    for lm, c in Counter([l for l in all_lms if l]).most_common():
        ws3.append([lm, c])
    ws3.column_dimensions["A"].width = 20
    ws3.column_dimensions["B"].width = 12

    # Sheet 4: 评论
    if comments:
        ws4 = wb.create_sheet("评论")
        headers4 = ["note_id", "评论内容", "点赞数", "昵称"]
        ws4.append(headers4)
        for cell in ws4[1]:
            cell.font = header_font
            cell.fill = header_fill
        for c in comments:
            ws4.append([
                c.get("note_id", ""),
                (c.get("content", "") or "")[:200],
                c.get("like_count", 0),
                c.get("nickname", ""),
            ])
        ws4.column_dimensions["B"].width = 60

    # Sheet 5: AI 市场报告(LLM 生成)
    if llm_report:
        ws5 = wb.create_sheet("AI市场报告")
        ws5.append(["🤖 AI 市场分析报告 (Agnes AI)"])
        ws5["A1"].font = Font(bold=True, size=14)
        ws5.append([])
        # Markdown 原文按行写入
        for line in llm_report.split("\n"):
            ws5.append([line])
        ws5.column_dimensions["A"].width = 100

    wb.save(out_path)


async def llm_market_analysis(notes: List[dict]) -> Optional[str]:
    """用 LLM 对房源做批量综合分析(1次调用),返回 Markdown 报告。

    需要 .env 配置 LLM_API_KEY。未配置返回 None。
    """
    try:
        from dotenv import load_dotenv
        load_dotenv()
        from agent.config import is_configured
        if not is_configured():
            return None
        from agent.llm import chat

        items = "\n".join(
            f"{i+1}. {n.get('title','')} | 价格相关:{(n.get('desc','') or '')[:55]}"
            for i, n in enumerate(notes)
        )
        prompt = f"""以下是从小红书采集的{len(notes)}条"广州越秀两房出租"笔记标题与简介:

{items}

请基于这些真实数据,生成一份简明的租房市场分析报告(Markdown 格式,600字内):
1. **价格区间总结**(从数据提取实际价格,给均价/区间)
2. **热门区域排行**(按出现频次)
3. **房源亮点特点**(电梯/地铁/精装/直租等占比)
4. **给租客的3条实用建议**(基于数据,不空话)
5. **给房东/中介的3条发布建议**(怎么发更容易被看到)

要求:务实、基于数据、不套话。"""
        return await chat(
            [{"role": "system", "content": "你是广州租房市场分析专家,擅长从真实数据提炼洞察"},
             {"role": "user", "content": prompt}],
            max_tokens=2000,
        )
    except Exception as e:
        print(f"  ⚠️  LLM 分析失败({e}),跳过 AI 报告")
        return None


def main():
    data_dir = Path("data/xhs/jsonl")
    notes_files = sorted(data_dir.glob("search_contents_*.jsonl"))
    if not notes_files:
        print("❌ 未找到笔记数据文件")
        sys.exit(1)
    notes_path = notes_files[-1]  # 取最新
    comments_files = sorted(data_dir.glob("search_comments_*.jsonl"))
    comments_path = comments_files[-1] if comments_files else ""

    print(f"📁 加载数据: {notes_path.name}")
    notes = load_notes(str(notes_path))
    comments = load_comments(str(comments_path)) if comments_path else []
    print(f"   笔记 {len(notes)} 条, 评论 {len(comments)} 条\n")

    analyzed = analyze_notes(notes)
    print_summary(analyzed)

    # LLM 综合分析(Agnes AI)
    print("\n🤖 调用 LLM 生成市场分析报告(Agnes AI)...")
    import asyncio
    llm_report = asyncio.run(llm_market_analysis(notes))
    if llm_report:
        print("\n" + "=" * 60)
        print("🤖 AI 市场分析报告")
        print("=" * 60)
        print(llm_report)
    else:
        print("  (LLM 未配置或失败,跳过 AI 报告)")

    # 导出 Excel(含 AI 报告 sheet)
    out_path = "data/广州越秀两房出租_分析报告.xlsx"
    export_excel(analyzed, comments, out_path, llm_report=llm_report)
    print(f"\n💾 Excel 已导出: {out_path}")
    sheets = ["房源笔记", "价格统计", "区域分布", "评论"]
    if llm_report:
        sheets.append("AI市场报告")
    print(f"   含 {len(sheets)} 个 sheet: {' / '.join(sheets)}")


if __name__ == "__main__":
    main()
    main()

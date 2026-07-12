---
name: mediacrawler-pro
description: 自媒体数据采集与爆款内容分析。支持小红书/抖音/B站/知乎等平台的关键词搜索、笔记详情、评论抓取,以及对已抓内容的 AI 爆款元素拆解。当用户需要采集某平台的内容、分析某篇笔记为什么火、或批量拆解内容时使用。
---

# MediaCrawler Pro —— 自媒体采集与内容分析 Skill

本 Skill 让 AI Agent(Claude Code / Cursor / OpenClaw 等)能够调用 MediaCrawler 进行自媒体数据采集,并对采集到的内容做爆款元素拆解。

## 能力

1. **数据采集**:关键词搜索、指定笔记/视频 ID 爬取、创作者主页爬取(小红书/抖音/B站/知乎/微博/快手/贴吧)
2. **内容分析**:对已抓取的笔记做「爆款拆解」(选题/情绪价值/结构/钩子/可复用建议)

## 使用前提

- 项目已 `uv sync` 安装依赖,且 Python 环境可用
- 采集需要登录态(首次用 CDP 连接 Chrome 扫码,或提供 cookie)
- 内容分析需要在 `.env` 配置 `LLM_API_KEY`(OpenAI 兼容接口)

## 采集数据

```bash
# 关键词搜索(小红书为例,二维码登录)
uv run main.py --platform xhs --lt qrcode --type search --keywords "编程副业"

# 指定笔记 ID
uv run main.py --platform xhs --lt cookie --type detail --cookies "web_session=xxx" --specified_id "note_id1,note_id2"

# 断点续爬(首次运行会打印 task_id,中断后用 --resume 继续)
uv run main.py --platform xhs --lt qrcode --type search --enable_resume yes
# 中断后:
uv run main.py --platform xhs --lt qrcode --type search --resume <task_id>

# 多账号轮转(需先导入账号 CSV)
uv run main.py --platform xhs --lt cookie --type search --enable_account_pool yes --accounts_file accounts.csv
```

数据落盘在 `data/<platform>/` 下(jsonl/csv/json 等,由 `--save_data_option` 控制)。

## 分析内容(爆款拆解)

```bash
# 分析单条(基于已抓取的数据)
uv run python -m agent --platform xhs --note <note_id> --save

# 批量分析最近 5 条
uv run python -m agent --platform xhs --limit 5 --save

# 列出有数据的平台 / 已生成报告
uv run python -m agent --list-platforms
uv run python -m agent --list-reports
```

## 典型工作流(Agent 执行)

当用户说"帮我采集小红书上关于 X 的内容并分析哪些是爆款"时,按以下步骤:

1. 运行采集:`uv run main.py --platform xhs --lt qrcode --type search --keywords "X" --save_data_option jsonl`
2. 等待采集完成(提示用户扫码登录)
3. 列出可分析内容:`uv run python -m agent --list-platforms` 确认 xhs 有数据
4. 批量拆解:`uv run python -m agent --platform xhs --limit 10 --save`
5. 读取 `data/analysis_reports/` 下的报告,汇总爆款共性给用户

## 重要约束

- 仅用于学习研究,**禁止商业用途**(见 LICENSE)
- 遵守目标平台 robots.txt 与使用条款,控制请求频率
- 不采集/不存储可识别个人的隐私字段(用户 ID/IP/头像等已脱敏)

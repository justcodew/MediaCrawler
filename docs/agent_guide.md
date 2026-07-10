# AI 内容分析 Agent 使用指南

MediaCrawler Pro 内置了一个**内容拆解 Agent**(ContentRemixAgent),能对已采集的自媒体内容做爆款元素分析,输出结构化报告。本文档介绍如何配置和使用。

## 1. 配置 LLM

Agent 走 **OpenAI 兼容接口**,支持 OpenAI / DeepSeek / 智谱 / 通义千问等。在项目根 `.env` 设置:

```bash
LLM_API_KEY=sk-xxxxxxxx
LLM_BASE_URL=https://api.openai.com/v1   # 或 https://api.deepseek.com/v1 等
LLM_MODEL=gpt-4o-mini                     # 或 deepseek-chat / glm-4-flash 等
LLM_TEMPERATURE=0.7
LLM_MAX_TOKENS=2000
```

> 没有配置 key 时,Agent 与 WebUI 的内容分析功能会提示「LLM 未配置」。

## 2. 命令行用法

```bash
# 先采集数据(以小红书为例)
uv run main.py --platform xhs --lt qrcode --type search --keywords "编程副业"

# 分析单条笔记
uv run python -m agent --platform xhs --note <note_id> --save

# 批量分析最近 5 条
uv run python -m agent --platform xhs --limit 5 --save

# 查看有数据的平台
uv run python -m agent --list-platforms

# 查看已生成的报告
uv run python -m agent --list-reports
```

报告保存在 `data/analysis_reports/<platform>_<note_id>_<ts>.json`。

## 3. WebUI 用法

启动后端 API(`uvicorn api.main:app`)与前端(`cd webui && npm run dev`)后,在 WebUI 顶部切换到 **🤖 内容分析** 视图:

1. 点击「刷新平台」加载已采集数据的平台列表
2. 选择平台,输入 note_id(单条)或留空批量
3. 点击「开始拆解」,等待 LLM 返回分析
4. 报告会展示在下方,同时保存到磁盘

## 4. 分析维度

Agent 会从以下维度拆解内容:

| 维度 | 说明 |
|------|------|
| **选题分析** | 核心方向、切入角度、亮点 |
| **情绪价值** | 触发的核心情绪(共鸣/好奇/焦虑/认同)及触发点 |
| **内容结构** | 整体结构(总分总/故事线/对比)、节奏 |
| **钩子设计** | 标题钩子、开头钩子(前3秒/前2行) |
| **互动分析** | 引导互动手法、数据表现解读 |
| **可复用建议** | 3 条可迁移到其他赛道的创作建议 |

## 5. 技术架构

```
data/<platform>/*.jsonl  ──► data_loader ──► content_to_text
                                                 │
                                                 ▼
                                      content_remix (工作流)
                                      ├─ LangGraph(已安装时)
                                      └─ 纯 async(fallback)
                                                 │
                                                 ▼
                                            llm.chat()
                                      (OpenAI 兼容 /v1/chat/completions)
                                                 │
                                                 ▼
                                          save_report → data/analysis_reports/
```

- **data_loader**:从 `data/` 读取已抓内容(jsonl/json/csv),统一字段名,转纯文本
- **content_remix**:拆解工作流。**优先用 LangGraph 编排**(若安装),否则纯 async 函数链实现等价流程——保证无 LangGraph 也能运行
- **llm**:httpx 直连 OpenAI 兼容接口,不强制依赖 openai SDK
- **API 路由**:`/api/analysis/*`(platforms / contents / remix / reports)
- **WebUI**:AnalysisPanel 组件,在 App.tsx 顶部视图切换

## 6. 扩展

- **新增分析节点**:在 `agent/content_remix.py` 的 LangGraph 版里加节点(如"生成选题建议"),纯 async 版同步加函数
- **换 LLM**:改 `.env` 的 `LLM_BASE_URL` / `LLM_MODEL` 即可,代码无需改
- **接视频转文字**:可在 data_loader 增加"从视频 URL 提取音频 → 转文字"的预处理节点(需额外依赖)

## 文件结构

```
agent/
├── __init__.py
├── __main__.py          # CLI 入口(uv run python -m agent)
├── config.py            # LLM 配置(从 env 读取)
├── data_loader.py       # 从 data/ 加载已抓内容
├── prompts.py           # 系统提示词 + 拆解模板
├── llm.py               # OpenAI 兼容接口封装
└── content_remix.py     # 拆解工作流(LangGraph + 纯 async fallback)

api/routers/analysis.py  # /api/analysis/* 路由
webui/src/components/analysis/AnalysisPanel.tsx  # WebUI 分析面板
SKILL.md                 # Claude Code / Cursor Agent Skill
```

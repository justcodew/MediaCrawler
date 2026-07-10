# MediaCrawler Pro 功能(社区增强版)

本仓库在开源 MediaCrawler 基础上,**渐进式** 实现了 Pro 版的核心功能。所有功能默认关闭,通过配置开关启用,与原有逻辑完全兼容。

> 声明:这些功能参考 MediaCrawlerPro 的设计思路在本仓库内独立实现,仅供学习研究,遵守 NON-COMMERCIAL LEARNING LICENSE 1.1。

## 功能总览

| 功能 | 开关 | 状态 | 文档 |
|------|------|------|------|
| 签名服务解耦 (SignSrv) | `ENABLE_SIGN_SERVICE` | ✅ | [sign_service/README.md](../sign_service/README.md) |
| 断点续爬 | `ENABLE_RESUME` | ✅ | [checkpoint/README.md](../checkpoint/README.md) |
| 多账号账号池 | `ENABLE_ACCOUNT_POOL` | ✅ | [account/README.md](../account/README.md) |
| 脱浏览器模式 (xhs/zhihu) | `ENABLE_HEADLESS_API` | ✅ | 本文 |
| AI 内容分析 Agent | `.env` LLM 配置 | ✅ | [agent_guide.md](agent_guide.md) |
| Claude Code / Cursor Skill | — | ✅ | [SKILL.md](../SKILL.md) |

## 快速上手

### 1. 签名服务(可选,降低 Node 依赖)

```bash
# 终端1:启动签名服务
uv run uvicorn sign_service.app:app --port 8888

# 终端2:启用签名服务跑爬虫(服务不可达时自动 fallback 本地签名)
uv run main.py --platform xhs --lt qrcode --type search --enable_sign_service yes
```

### 2. 断点续爬

```bash
# 首次运行,记录 task_id
uv run main.py --platform xhs --lt qrcode --type search --enable_resume yes
# 中断后续爬
uv run main.py --platform xhs --lt qrcode --type search --resume <task_id>
```

### 3. 多账号采集

```bash
# 准备账号 CSV(见 account/templates/accounts_template.csv)
uv run main.py --platform xhs --lt cookie --type search \
  --enable_account_pool yes --accounts_file my_accounts.csv
```

### 4. 脱浏览器模式(xhs/zhihu)

已有 cookie 时跳过浏览器,纯 httpx + 签名:

```bash
uv run main.py --platform xhs --lt cookie --type search \
  --cookies "web_session=xxx" --enable_headless_api yes --enable_sign_service yes
```

### 5. AI 内容分析

```bash
# 配置 .env 的 LLM_API_KEY 后
uv run python -m agent --platform xhs --limit 5 --save
# 或在 WebUI 切换到「🤖 内容分析」视图
```

## 架构关系

```
                    ┌─────────────────────────────────────┐
                    │  config/base_config.py (功能开关)    │
                    └───────────────┬─────────────────────┘
                                    │
   ┌───────────────┬────────────────┼────────────────┬───────────────┐
   ▼               ▼                ▼                ▼               ▼
sign_service   checkpoint        account         headless_api      agent
(签名微服务)   (断点续爬)        (账号池)         (脱浏览器)       (AI 分析)
   │               │                │                │               │
   │          database/         database/            │          data/*.jsonl
   │          checkpoints.db    accounts.db          │               │
   │               │                │                │               ▼
   └──────► media_platform/<platform>/core.py ◄──────┘        agent/data_loader
                    (7 平台爬虫)                                   │
                                                                   ▼
                                                          agent/content_remix
                                                          (LangGraph / 纯async)
                                                                   │
                                                                   ▼
                                                              agent/llm
                                                          (OpenAI 兼容接口)
```

## 设计原则

1. **渐进式**:所有功能默认关闭,开关启用,与原逻辑兼容
2. **独立存储**:checkpoint / account 用独立 sqlite 库,不与主库 `SAVE_DATA_OPTION` 耦合
3. **零重复**:签名服务直接复用 `media_platform` 下已有算法;Agent fallback 复用同一 provider
4. **轻量化**:SignSrv 用轻量加载器隔离 pandas/playwright 等重型依赖;Agent 的 LangGraph 可选(无则纯 async)

## 测试

```bash
# 签名服务测试(纯 Python 平台直接通过;xhs/douyin/zhihu 需对应库)
uv run pytest tests/test_sign_service.py -v

# 断点续爬测试
uv run pytest tests/test_checkpoint.py -v

# 账号池测试
uv run pytest tests/test_account_pool.py -v

# 全部
uv run pytest tests/test_sign_service.py tests/test_checkpoint.py tests/test_account_pool.py -v
```

## 各功能详细文档

- [签名服务 SignSrv](../sign_service/README.md)
- [断点续爬 Checkpoint](../checkpoint/README.md)
- [多账号 Account Pool](../account/README.md)
- [AI 内容分析 Agent](agent_guide.md)
- [Claude Code / Cursor Skill](../SKILL.md)

## 配置项速查(`config/base_config.py`)

```python
# 签名服务
ENABLE_SIGN_SERVICE = False
SIGN_SERVICE_URL = "http://127.0.0.1:8888"

# 断点续爬
ENABLE_RESUME = False
RESUME_TASK_ID = ""

# 多账号
ENABLE_ACCOUNT_POOL = False
ACCOUNT_POOL_FAIL_THRESHOLD = 3
ACCOUNT_CONCURRENCY = 1
ACCOUNTS_IMPORT_FILE = ""

# 脱浏览器
ENABLE_HEADLESS_API = False
```

`.env`(AI Agent):

```bash
LLM_API_KEY=
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini
```

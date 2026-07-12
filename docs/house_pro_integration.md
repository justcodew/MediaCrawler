# MediaCrawler ↔ 好房雷达(house_pro)对接文档

本文档说明如何让 MediaCrawler(多平台采集引擎)与好房雷达(house_pro,租房分析与推荐系统)对接,实现从采集到入库到评分的完整流水线。

## 1. 架构总览

```
┌─────────────────────────────────────────────────────────┐
│                    数据流向                             │
│                                                         │
│  MediaCrawler               house_pro 好房雷达          │
│  ┌───────────┐              ┌───────────────────┐       │
│  │ 8平台采集  │  方式1:API   │  Listing 表(PG)   │       │
│  │ xhs/douban │ ──HTTP直连─► │  ↓                 │       │
│  │ wb/zhihu.. │              │  评分引擎          │       │
│  │           │  方式2:文件   │  ↓                 │       │
│  │ 反检测     │ ──JSONL落盘─►│  Celery ETL 入库  │       │
│  │ 断点续爬   │              │  ↓                 │       │
│  │ 多账号     │              │  推荐 / 搜索 / 展示 │       │
│  └───────────┘              └───────────────────┘       │
│       ↓                                                 │
│  house_adapter                                           │
│  (字段提取:价格/户型/区域/面积/楼层/朝向/联系方式)       │
└─────────────────────────────────────────────────────────┘
```

**核心分工**:
- **MediaCrawler**:负责采集(8平台 + 反检测 + 断点续爬)+ 结构化字段提取
- **house_pro**:负责入库 + 评分 + 推荐 + 前端展示
- **对接层**:house_adapter(字段提取)+ API/文件(数据传输)

## 2. 两种对接方式

### 方式1:HTTP API 直连(推荐,实时)

house_pro 通过 HTTP 调 MediaCrawler 的接口,实时获取结构化 Listing 数据,直接入库。

```
house_pro                        MediaCrawler
   │                                │
   │  GET /api/house/listings       │
   │    ?platform=xhs&limit=20      │
   │ ─────────────────────────────► │
   │                                │  读取 data/xhs/ 已采集数据
   │                                │  → house_adapter 转换
   │  ← 200 OK                      │
   │    { listings: [...] }         │
   │                                │
   │  入库 Listing 表               │
```

**优点**:实时,无需文件中转,一条龙
**适用**:用户主动触发的即时采集

### 方式2:文件落盘(Celery 定时)

MediaCrawler 采集后把 Listing 格式的 JSONL 写到 house_pro 的 `data/xhs_raw/` 目录,house_pro 的 Celery 定时任务扫该目录做 ETL 入库。

```
MediaCrawler                     house_pro
   │                                │
   │  采集完成                       │
   │  → house_adapter 转换           │
   │  → 写 data/xhs_raw/*.jsonl     │
   │ ─────────────────────────────► │
   │                                │
   │                    Celery beat │
   │                    每30分钟扫描 │
   │                    → ETL 入库   │
   │                    → 触发评分   │
```

**优点**:完全解耦,两个进程独立运行
**适用**:后台定时采集

## 3. MediaCrawler 端配置

### 3.1 API 服务

MediaCrawler 的 API 已内置 house 对接路由(`api/routers/house.py`),随主 API 启动:

```bash
# 启动 MediaCrawler API(默认 8080 端口)
uv run uvicorn api.main:app --host 0.0.0.0 --port 8080
```

### 3.2 文件落盘配置(方式2)

在 `config/base_config.py` 设置:

```python
# house_pro 的 data/xhs_raw/ 目录路径(相对或绝对)
HOUSE_RAW_DIR = "../house_pro/data/xhs_raw"
```

采集后 MediaCrawler 会自动把 Listing 格式数据写到该目录。
设为空字符串则禁用文件落盘(只用 API 方式)。

## 4. house_pro 端配置

### 4.1 方式1:HTTP 直连

house_pro 的 Celery 任务或 API 直接调用:

```python
from app.services.crawler.mediacrawler_client import fetch_and_ingest

# 从 MediaCrawler 实时拉取并入库
stats = await fetch_and_ingest(
    db,
    platform="xhs",           # 或 douban
    base_url="http://localhost:8080",  # MediaCrawler API 地址
    limit=100,
)
# stats: {"fetched": 20, "ingested": 18, "skipped": 2, "errors": 0}
```

或直接调 MediaCrawler API:

```bash
# 获取有数据的平台
curl http://localhost:8080/api/house/platforms

# 获取小红书房源(已提取结构化字段)
curl "http://localhost:8080/api/house/listings?platform=xhs&limit=20&only_with_price=true"

# 导出到 house_pro 目录
curl -X POST http://localhost:8080/api/house/export \
  -H "Content-Type: application/json" \
  -d '{"platform":"xhs", "output_dir":"../house_pro/data/xhs_raw", "limit":50}'
```

### 4.2 方式2:文件落盘(现有 Celery)

house_pro 已有的 Celery 任务 `crawl_xiaohongshu` 会定时扫 `XHS_RAW_DIR`(默认 `data/xhs_raw/`)。只需确保:

1. MediaCrawler 的 `HOUSE_RAW_DIR` 指向该目录
2. house_pro 的 `backend/.env` 配置:

```bash
# house_pro/backend/.env
XHS_RAW_DIR=data/xhs_raw
```

Celery beat 配置(已有):

```python
# house_pro/backend/app/workers/celery_app.py
"crawl-xiaohongshu-every-30m": {
    "task": "app.workers.celery_app.crawl_xiaohongshu",
    "schedule": crontab(minute="*/30"),
}
```

## 5. API 接口文档

### GET /api/house/platforms

列出 MediaCrawler 已采集数据的平台。

**响应**:
```json
{
  "platforms": [
    {"platform": "douban", "source": "douban"},
    {"platform": "xhs", "source": "xiaohongshu"}
  ]
}
```

### GET /api/house/listings

获取已采集数据,返回 house_pro Listing 格式。

**参数**:
| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| platform | string | xhs | 平台标识(xhs/douban/wb/zhihu...) |
| limit | int | 100 | 最多返回条数(1-500) |
| only_with_price | bool | false | 只返回提取到价格的房源 |

**响应**:
```json
{
  "platform": "xhs",
  "source": "xiaohongshu",
  "total": 3,
  "listings": [
    {
      "source": "xiaohongshu",
      "source_id": "69e71574000000001f004148",
      "source_url": "https://www.xiaohongshu.com/explore/69e71574...",
      "poster_id": "a1b2c3...",
      "poster_name": "J***1",
      "title": "2500租越秀老小区两房后续",
      "content": "我是在小红书上偶然间刷到房东女儿...",
      "image_urls": ["https://...", "..."],
      "posted_at": "2026-04-21T06:13:08+00:00",
      "price": 2500,
      "price_unit": "元/月",
      "size_sqm": null,
      "layout": null,
      "area_name": "越秀区",
      "floor_info": null,
      "orientation": null,
      "contact_info": {},
      "status": "active",
      "raw_data": {
        "note": { ... },
        "is_agent_initial": false,
        "fields_pre_extracted": true
      }
    }
  ]
}
```

### POST /api/house/export

把已采集数据导出到 house_pro 目录(文件落盘)。

**请求**:
```json
{
  "platform": "xhs",
  "output_dir": "../house_pro/data/xhs_raw",
  "limit": 100
}
```

**响应**:
```json
{
  "status": "ok",
  "platform": "xhs",
  "source": "xiaohongshu",
  "exported": 20,
  "output_file": "../house_pro/data/xhs_raw/xiaohongshu_1783830610.jsonl"
}
```

## 6. 字段映射表

| MediaCrawler 原始字段 | house_pro Listing 字段 | 提取方式 | 示例 |
|---|---|---|---|
| note_id / topic_id | source_id | 直接映射 | "69e715740..." |
| title | title | 直接映射 | "2500租越秀老小区两房" |
| desc / content | content | 直接映射 | "我是在小红书上..." |
| creator_hash | poster_id | 直接映射(匿名哈希) | "a1b2c3..." |
| nickname | poster_name | 直接映射(已脱敏) | "J***1" |
| note_url | source_url | 直接映射 | "https://..." |
| image_list | image_urls | 逗号分割→数组 | ["https://..."] |
| time / create_time | posted_at | 毫秒时间戳→ISO | "2026-04-21T..." |
| —(extractor) | price | 正则提取(元/月) | 2500 |
| —(extractor) | layout | 正则提取(户型) | "2室1厅" |
| —(extractor) | area_name | 关键词匹配(区域) | "越秀区" |
| —(extractor) | size_sqm | 正则提取(面积) | 65 |
| —(extractor) | floor_info | 正则提取(楼层) | "6/12层" |
| —(extractor) | orientation | 正则提取(朝向) | "南向" |
| —(extractor) | contact_info | 正则提取(联系方式) | {"wechat":"xxx"} |

**平台标识映射**:
| MediaCrawler | house_pro source |
|---|---|
| xhs | xiaohongshu |
| douban | douban |
| wb | weibo |
| zhihu | zhihu |
| dy | douyin |
| ks | kuaishou |
| bili | bilibili |
| tieba | tieba |

## 7. house_pro ETL 适配说明

house_pro 的 `xiaohongshu.py` ETL 已适配两种输入格式:

### 格式1:MediaCrawler 原始 note(旧)
```json
{"note_id": "xxx", "title": "...", "desc": "...", "tag_list": [...]}
```
→ ETL 用 `extract_listing_fields` 提取结构化字段

### 格式2:house_adapter 预提取 Listing(新,推荐)
```json
{"source": "xiaohongshu", "source_id": "xxx", "price": 2500, "area_name": "越秀区",
 "raw_data": {"fields_pre_extracted": true}}
```
→ ETL 检测到 `fields_pre_extracted: true`,**跳过 extractor**,直接用已提取的字段入库

**优势**:两端 extractor 正则一致(MediaCrawler 的 house_adapter 复制自 house_pro),避免重复提取,且 MediaCrawler 端可结合采集上下文做更准的提取。

## 8. 完整使用流程

### 场景:采集"广州越秀两房出租"并入库好房雷达

```bash
# 步骤1:MediaCrawler 采集(需 Chrome + 登录)
cd MediaCrawler
python3 safe_crawl.py --platform xhs --keywords "广州越秀两房出租"

# 步骤2:启动 MediaCrawler API
uv run uvicorn api.main:app --port 8080 &

# 步骤3:house_pro 拉取数据入库
cd ../house_pro/backend
python3 -c "
import asyncio
from app.database import async_session
from app.services.crawler.mediacrawler_client import fetch_and_ingest

async def run():
    async with async_session() as db:
        stats = await fetch_and_ingest(db, platform='xhs', base_url='http://localhost:8080')
        print(stats)

asyncio.run(run())
"

# 步骤4:house_pro 自动评分(Celery 或手动触发)
# 新入库的 Listing 会被 _trigger_scoring_for_new 自动评分
```

### 或用文件落盘(无需 API):

```bash
# 步骤1:配置 MediaCrawler 写到 house_pro 目录
# config/base_config.py: HOUSE_RAW_DIR = "../house_pro/data/xhs_raw"

# 步骤2:MediaCrawler 采集(自动写文件)
python3 safe_crawl.py --platform xhs --keywords "广州越秀两房出租"

# 步骤3:house_pro Celery 自动扫描入库(无需手动操作)
# 或手动触发:
cd house_pro/backend
celery -A app.workers.celery_app call app.workers.celery_app.crawl_xiaohongshu
```

## 9. 文件清单

### MediaCrawler 端
| 文件 | 说明 |
|------|------|
| `house_adapter/extractor.py` | 正则提取结构化字段(与 house_pro 一致 + k 计价) |
| `house_adapter/converter.py` | note → Listing 格式转换 |
| `api/routers/house.py` | 3 个对接 API 端点 |
| `config/base_config.py` | `HOUSE_RAW_DIR` 配置 |

### house_pro 端
| 文件 | 说明 |
|------|------|
| `services/crawler/xiaohongshu.py` | ETL 适配(识别预提取格式 + .jsonl 兼容) |
| `services/crawler/mediacrawler_client.py` | HTTP 客户端(实时拉取入库) |

## 10. 常见问题

**Q: MediaCrawler 采集的数据在哪?**
A: `data/<platform>/jsonl/` 目录,如 `data/xhs/jsonl/search_contents_2026-07-11.jsonl`

**Q: house_pro 怎么拿到 MediaCrawler 的数据?**
A: 两种方式——HTTP API(`GET /api/house/listings`)或文件落盘(写到 `data/xhs_raw/`)。

**Q: 字段提取在哪一端做?**
A: MediaCrawler 端(house_adapter),提取后标记 `fields_pre_extracted: true`,house_pro ETL 检测到后跳过自己的 extractor,直接入库。

**Q: 支持哪些平台?**
A: 8 个平台(xhs/douban/wb/zhihu/dy/ks/bili/tieba),但租房信息主要来自小红书(xhs)和豆瓣(douban)。

**Q: 两端 extractor 正则一致吗?**
A: 是的,MediaCrawler 的 `house_adapter/extractor.py` 复制自 house_pro 的 `extractor.py`,并额外支持 k 计价(如 3.6k = 3600)。

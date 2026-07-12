# SignSrv — 多平台签名服务

将各平台的签名算法(execjs + JS / 纯 Python)解耦为独立 HTTP 微服务。crawler 主进程通过
`sign_client` 调用本服务,从而**不再依赖 Node 运行时(execjs)** 即可完成签名。

> 这是 Pro 版「签名服务解耦」特性的实现,是断点续爬、多账号、脱浏览器等后续阶段的基础设施。

## 支持的平台

| 平台 | 签名算法 | 产物 | 依赖 |
|------|---------|------|------|
| 小红书 (xhs) | xhshow 纯算法 | headers: `X-S` / `X-T` / `x-S-Common` / `X-B3-Traceid` | `xhshow` |
| 抖音 (douyin) | execjs + `libs/douyin.js` | params: `a_bogus` | Node + `execjs` |
| 知乎 (zhihu) | execjs + `libs/zhihu.js` | headers: `x-zst-81` / `x-zse-96` | Node + `execjs` |
| B站 (bilibili) | wbi 纯 Python 算法 | params: `w_rid` / `wts` | 无 |
| 贴吧 (tieba) | md5 纯 Python 算法 | params: `sign` (+ `subapp_type`/`_client_type`) | 无 |

微博 / 快手暂未纳入(其签名机制不同,留待后续阶段)。

## 架构

```
crawler 进程                          SignSrv (独立进程)
┌─────────────────┐                  ┌──────────────────────────┐
│ xhs/client.py   │   POST /sign     │ sign_service/app.py       │
│ douyin/help.py  │ ───────────────► │  └─ providers/            │
│ zhihu/client.py │   (httpx)        │      xhs/douyin/zhihu/... │
│ bilibili/...    │ ◄─────────────── │      ↑ 复用 media_platform│
│ tieba/...       │   签名结果        │        下的纯算法模块      │
└────────┬────────┘                  │      ↑ (经轻量加载器隔离)  │
         │ 服务不可达时                └──────────────────────────┘
         ▼ fallback: 进程内直接调 provider(同一份算法,输出一致)
```

**关键设计**:
- provider **直接复用** `media_platform/<platform>/` 下已有的纯算法模块(`help.py` / `*_sign.py`),
  不在服务里重复实现签名 —— 保证「本地签名」与「服务签名」输出完全一致。
- 轻量加载器(`_loader.py`)按文件路径加载算法模块,**绕开** `media_platform/<platform>/__init__.py`
  的 `from .core import *` 副作用(那会引入 pandas/playwright 等重型依赖),让 SignSrv 保持轻量。
- `sign_client` 的 fallback **不是另一套算法**,而是进程内直接调用同一个 provider,
  从根上保证 fallback 与服务输出一致。

## 启动

```shell
# 方式一:uvicorn
uv run uvicorn sign_service.app:app --host 127.0.0.1 --port 8888

# 方式二:模块入口
uv run python -m sign_service.app
```

## 在 crawler 侧启用

编辑 `config/base_config.py`:

```python
ENABLE_SIGN_SERVICE = True              # 开关(默认 False,渐进启用)
SIGN_SERVICE_URL = "http://127.0.0.1:8888"
```

启用后,各平台的签名调用会自动走 SignSrv。**若服务未启动或不可达,会自动 fallback
到本地签名**(进程序内调用同一 provider),功能不中断,无需回改配置。

## 接口契约

### `GET /health`
```json
{ "status": "ok", "providers": ["bilibili", "douyin", "tieba", "xhs", "zhihu"] }
```

### `POST /sign`
请求体(`SignRequest`):
```json
{
  "platform": "xhs",
  "uri": "/api/sns/web/v1/search/notes",
  "url": "",                          // 知乎/抖音需要完整带 query 的 url
  "method": "POST",                   // GET / POST
  "params": { ... },                  // GET 查询参数(bilibili/tieba/xhs-GET 用)
  "data": { ... },                    // POST 请求体(xhs-POST 用)
  "cookies": "web_session=xxx; a1=...",// xhs/zhihu 需要
  "user_agent": "Mozilla/5.0 ...",    // 抖音 a_bogus 必需
  "extra": { "img_key": "...", "sub_key": "..." }  // bilibili 需要(来自浏览器 wbi_img_urls)
}
```
响应(`SignResponse`):
```json
{
  "platform": "xhs",
  "headers": { "X-S": "...", "X-T": "...", "x-S-Common": "...", "X-B3-Traceid": "..." },
  "params": {},          // bilibili/tieba/douyin 的签名字段在此
  "raw": { ... }         // 原始签名结果(调试用)
}
```
- 未知平台 → `400`
- 业务参数错误(如 bilibili 缺 `img_key`)→ `422`
- 签名内部异常 → `500`

## 验证

```shell
# 单元测试(纯 Python 平台直接通过;xhs/douyin/zhihu 需对应库)
uv run pytest tests/test_sign_service.py -v
```

测试覆盖:
- 服务基础设施(`/health`、注册表、未知平台 400)
- bilibili/tieba provider 的签名输出结构与校验
- xhs/douyin/zhihu provider(依赖库就绪时)
- HTTP `/sign` 端点集成
- `sign_client` fallback 路径(服务不可达时)

## 文件结构

```
sign_service/
├── __init__.py
├── app.py              # FastAPI 应用: /health + /sign
├── models.py           # SignRequest / SignResponse / HealthResponse
├── _loader.py          # 轻量模块加载器(隔离重型 __init__ 依赖)
├── providers/
│   ├── __init__.py     # 导入即触发注册
│   ├── base.py         # SignProvider 抽象 + ProviderRegistry
│   ├── xhs_sign_provider.py
│   ├── douyin_sign_provider.py
│   ├── zhihu_sign_provider.py
│   ├── bilibili_sign_provider.py
│   └── tieba_sign_provider.py
└── README.md           # 本文件

sign_client/            # crawler 侧客户端(带 fallback)
├── __init__.py
└── client.py           # SignServiceClient + get_client() + is_enabled()
```

# 多账号账号池 (Account Pool)

支持多账号轮转采集,每账号独立 `user_data_dir` 与可选代理,失败自动切换。适合长时间、大规模采集。

## 配置

`config/base_config.py`:

```python
ENABLE_ACCOUNT_POOL = False            # 开关
ACCOUNT_POOL_FAIL_THRESHOLD = 3        # 连续失败次数达此值 → 账号冷却
ACCOUNT_CONCURRENCY = 1                # 并发账号数(1=串行轮转)
ACCOUNTS_IMPORT_FILE = ""              # 启动时从 CSV/Excel 导入(可选)
```

## 导入账号

账号存在独立 sqlite 库 `database/accounts.db`(与主库解耦)。三种导入方式:

### 方式 1:CSV 导入(推荐)

模板见 `account/templates/accounts_template.csv`:

```csv
platform,account_id,nickname,cookies,user_agent,proxy_http,proxy_https
xhs,acc001,账号A,web_session=xxx; a1=yyy,Mozilla/5.0 ...,,
xhs,acc002,账号B,web_session=zzz; a1=www,Mozilla/5.0 ...,http://proxy:8080,
```

启动时自动导入:

```bash
uv run main.py --platform xhs --lt cookie --type search \
  --enable_account_pool yes --accounts_file my_accounts.csv
```

### 方式 2:命令行工具(写脚本调用)

```python
import asyncio
from account import manager

async def main():
    n = await manager.import_from_csv("my_accounts.csv")
    print(f"导入 {n} 个账号")

asyncio.run(main())
```

### 方式 3:Excel 导入

```python
n = await manager.import_from_excel("accounts.xlsx")  # 需 openpyxl
```

## 运行

```bash
# 启用账号池(自动从 database/accounts.db 取账号轮转)
uv run main.py --platform xhs --lt cookie --type search --enable_account_pool yes

# 配合断点续爬
uv run main.py --platform xhs --lt cookie --type search \
  --enable_account_pool yes --enable_resume yes
```

## 工作机制

1. `main.py` 检测 `ENABLE_ACCOUNT_POOL`,创建 `AccountPool`
2. 循环 `acquire()` 取 active 账号 → 为每账号建独立 crawler(独立 `user_data_dir` = `browser_data/<platform>_<account_id>_user_data_dir`)
3. 账号的 cookie/UA 直接注入 client(配合脱浏览器模式可完全跳过浏览器)
4. 任务成功 → `release(success=True)`;失败 → `mark_failed`,连续达阈值进入 cooling
5. 池内账号全部 cooling/disabled → `acquire()` 返回 None,退出

## 账号状态机

```
active ──acquire──► in_use ──release(success)──► active
                       │
                       └──release(fail) ×N──► cooling ──(冷却期)──► active
                                              │
                                              └──disable──► disabled
```

| 状态 | 含义 |
|------|------|
| `active` | 可用,可被 acquire |
| `in_use` | 正在使用(池内锁定) |
| `cooling` | 冷却中(刚触发风控,10分钟后恢复) |
| `disabled` | 已禁用(封号/手动) |

## 文件结构

```
account/
├── __init__.py
├── types.py             # Account ORM + AccountInfo + 状态常量
├── store.py             # 独立 sqlite 存储引擎(database/accounts.db)
├── pool.py              # AccountPool(acquire/release/mark_failed)
├── manager.py           # CSV/Excel 导入导出 + 模板生成
├── templates/
│   └── accounts_template.csv
└── README.md            # 本文件
```

## 注意

- cookies 字段仅本地使用,不涉及对外服务
- 与代理池协同:每个账号可在 CSV 的 `proxy_http`/`proxy_https` 列绑定独立代理
- 并发模式(`ACCOUNT_CONCURRENCY > 1`)为预留扩展,当前实现为串行轮转

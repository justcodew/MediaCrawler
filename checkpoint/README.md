# 断点续爬 (Checkpoint Resume)

支持爬虫中断后从上次进度继续,避免重复抓取。适用于长时间采集任务。

## 配置

`config/base_config.py`:

```python
ENABLE_RESUME = False      # 开关
RESUME_TASK_ID = ""        # 续爬时填上次任务的 task_id
```

## 用法

```bash
# 首次运行:会生成并打印 task_id
uv run main.py --platform xhs --lt qrcode --type search --enable_resume yes
# 输出: [Main] New task created: a1b2c3d4... (use --resume a1b2c3d4... to resume)

# 中断后(Ctrl+C)续爬:
uv run main.py --platform xhs --lt qrcode --type search --resume a1b2c3d4...
```

`--resume <id>` 隐含 `--enable_resume yes`。

## 工作机制

- 进度存在独立 sqlite 库 `database/checkpoints.db`(不依赖 `SAVE_DATA_OPTION`,jsonl/csv 模式也能续)
- **页面级 checkpoint**:每 `(task_id, keyword)` 记录 `last_page` / `last_search_id` / 已处理 note_id
- 每页 `gather` 完成后写一次 checkpoint
- 续爬时:恢复 `page` 起始值、**复用 search_id**(关键,否则翻页错位)、跳过已处理 note_id

## 三种爬取模式的支持

| 模式 | 断点维度 |
|------|---------|
| `search` | 按 keyword 记录页码 + search_id + 已抓 note_id |
| `detail` | 按 `__detail__` scope 记录已处理 note_id(跳过) |
| `creator` | 同 detail(按 creator 标识) |

## 设计

```
main.py
  └─ create_task / resume_task → CheckpointManager(enabled=True)
                                  └─ crawler.checkpoint_manager = ...
                                     crawler.start()
                                       └─ 每个 keyword: await ckpt.begin_scope(keyword)
                                          分页循环: 每页 await ckpt.save_page(keyword, page, note_ids, search_id=...)
```

`CheckpointManager.enabled=False` 时所有方法 no-op,完全不影响原有逻辑(向后兼容)。

## 文件结构

```
checkpoint/
├── __init__.py
├── models.py     # CrawlTask + CrawlCheckpoint ORM
├── store.py      # 独立 sqlite 存储引擎(database/checkpoints.db)
├── manager.py    # CheckpointManager(begin_scope / save_page / complete)
└── README.md     # 本文件
```

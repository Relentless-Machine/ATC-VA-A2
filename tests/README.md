# A-2 测试框架说明

## 技术栈

`pytest` + `pytest-asyncio` + `httpx` + `pytest-mock` + `aiosqlite`

安装依赖：

```bash
pip install pytest pytest-asyncio httpx pytest-mock aiosqlite
```

运行全部测试：

```bash
pytest tests/ -v
```

---

## 目录结构

```
tests/
├── conftest.py                        # 全局配置
├── unit/
│   ├── test_storage.py                # StorageManagerService 单元测试
│   ├── test_callback.py               # A3CallbackService 单元测试
│   └── test_ingest.py                 # LiveATCIngestionService 单元测试
└── integration/
    ├── test_api_audio.py              # /api/v1/audio 路由集成测试
    ├── test_api_admin.py              # /api/v1/admin 路由集成测试
    ├── test_api_ingestion.py          # /api/v1/ingestion 路由集成测试
    └── test_api_callback.py           # /api/v1/a3/callback 路由集成测试
```

---

## 文件说明

### `conftest.py`

全局测试基础设施：
- 创建 `sqlite+aiosqlite:///:memory:` 内存数据库引擎（session 级别）
- 提供 `db_session` fixture（每个测试后自动 rollback）
- 提供 `client` fixture（httpx.AsyncClient + FastAPI 依赖重写 `get_db`）

---

### `unit/test_storage.py`

针对 [app/services/storage_service.py](../app/services/storage_service.py) 的单元测试。

| 测试用例 | 覆盖点 |
|---|---|
| `test_needs_cleanup_true` | 磁盘剩余 < 阈值时返回 True |
| `test_needs_cleanup_false` | 磁盘剩余 > 阈值时返回 False |
| `test_cleanup_lru_skips_locked_file` | `OSError` 时跳过并继续处理后续文件 |
| `test_cleanup_lru_no_files` | 无可清理文件时返回 0，不 commit |

Mock 目标：`shutil.disk_usage`、`os.path.exists`、`os.stat`、`asyncio.to_thread`、`AsyncSession`

---

### `unit/test_callback.py`

针对 [app/services/a3_callback_service.py](../app/services/a3_callback_service.py) 的单元测试。

| 测试用例 | 覆盖点 |
|---|---|
| `test_handle_callback_inserts_segments` | 正常回调插入 N 条 segment |
| `test_handle_callback_voice_file_not_found` | voice_file_id 不存在抛出 404 |
| `test_handle_callback_empty_segments` | segments 为空时正常返回 |

Mock 目标：`AsyncSession.get`、`AsyncSession.add`、`AsyncSession.commit`

---

### `unit/test_ingest.py`

针对 [app/services/ingestion_service.py](../app/services/ingestion_service.py) 的单元测试。

| 测试用例 | 覆盖点 |
|---|---|
| `test_register_realtime_capture` | 实时录音注册写入 DB |
| `test_register_historical_capture` | 历史录音注册写入 DB，Mock 目录创建 |

预留桩：`test_fetch_realtime_stream_stub`（RQ-A-2-10）、`test_schedule_historical_download_stub`（RQ-A-2-20）

---

### `integration/test_api_audio.py`

针对 [app/api/routes/audio.py](../app/api/routes/audio.py) 的集成测试。

| 测试用例 | 覆盖点 |
|---|---|
| `test_stream_audio_returns_206` | 命中 segment 返回 206 流式响应 |
| `test_stream_audio_no_segment_404` | 无 segment 返回 404 |
| `test_stream_audio_bad_range_400` | end <= start 返回 400 |

注意：Mock `asyncio.to_thread` 避免读取真实文件路径（防止 `FileNotFoundError`）。

---

### `integration/test_api_admin.py`

针对 [app/api/routes/admin.py](../app/api/routes/admin.py) 的集成测试。

| 测试用例 | 覆盖点 |
|---|---|
| `test_cleanup_when_needed` | 磁盘不足时触发清理 |
| `test_cleanup_not_needed` | 磁盘充足时 deleted_files=0 |

---

### `integration/test_api_ingestion.py`

针对 [app/api/routes/ingestion.py](../app/api/routes/ingestion.py) 的集成测试。

| 测试用例 | 覆盖点 |
|---|---|
| `test_register_realtime_file` | 实时注册返回 201 + voice_file_id |
| `test_register_historical_file` | 历史注册返回 201 + voice_file_id |

预留桩：LiveATC 实时监听触发（RQ-A-2-10）、历史下载调度（RQ-A-2-20）

---

### `integration/test_api_callback.py`

针对 [app/api/routes/callback.py](../app/api/routes/callback.py) 的集成测试，含 A-5 外键联调预留。

| 测试用例 | 覆盖点 |
|---|---|
| `test_callback_success_201` | 合法 payload + Token → 201，segment 写入 DB |
| `test_callback_invalid_token_401` | 错误 Token → 401 |
| `test_callback_missing_token_401` | 无 Token → 401 |
| `test_callback_fk_missing_404` | voice_file_id 不存在 → 404 |

预留桩：`test_callback_with_track_id_stub`（A-5 航迹外键）、`test_segment_author_id_stub`（A-5 用户外键）

---

## 关键注意事项

1. **`asyncio.to_thread` 隔离**：`AudioQueryService.iter_file_stream` 使用 `asyncio.to_thread` 读取文件，集成测试中必须 Mock，否则会尝试读取真实路径并抛出 `FileNotFoundError`。

2. **内存 DB 隔离**：所有集成测试通过 `app.dependency_overrides` 将 `get_db` 替换为内存 SQLite session，每个测试后自动 rollback，互不干扰。

3. **预留桩位置**：LiveATC 网络抓取（RQ-A-2-10/20）和 A-5 外键联调的测试桩以注释形式保留在对应文件末尾，接入真实实现后取消注释即可启用。

# A-2 测试框架说明

本文档集中说明 `tests/` 下的测试组织方式、常用运行方式和各类测试的用途。主项目 README 只保留测试入口，详细内容统一放在这里。

## 技术栈

`pytest` + `pytest-asyncio` + `pytest-timeout` + `httpx` + `aiosqlite` + `locust` + `psutil`

安装依赖：

```bash
pip install -r requirements.txt
```

## 分层与标记

已在项目根目录配置 [pytest.ini](../pytest.ini)，默认跳过 `network`、`e2e`、`longrun`。

可用标记：

- `unit`：单元测试
- `integration`：接口/模块集成测试
- `network`：真实 LiveATC 网络测试
- `e2e`：端到端测试
- `longrun`：长期稳定性测试

## 目录结构

```text
tests/
├── conftest.py
├── fixtures/
│   ├── api.py
│   ├── database.py
│   └── external_services.py
├── shared/
│   └── time_utils.py
├── unit/
│   └── services/
│       ├── test_a3_callback_service.py
│       ├── test_a3_integration_service.py
│       ├── test_a5_integration_service.py
│       ├── test_archive_adapter.py
│       ├── test_ingestion_scheduler.py
│       ├── test_ingestion_service.py
│       ├── test_liveatc_client.py
│       ├── test_query_service.py
│       └── test_storage_service.py
├── integration/
│   ├── api/
│   │   ├── test_a3_integration_routes.py
│   │   ├── test_a5_integration_routes.py
│   │   ├── test_admin_routes.py
│   │   ├── test_audio_routes.py
│   │   ├── test_callback_routes.py
│   │   ├── test_health_routes.py
│   │   └── test_ingestion_routes.py
│   └── flows/
│       └── test_ingestion_callback_audio_flow.py
├── e2e/
│   └── test_stability_liveatc.py
└── loadtest/
    ├── locustfile.py
    ├── soak_runner.py
    ├── scenarios/
    │   ├── peak_concurrent.py
    │   └── long_stability.py
    └── reports/
```

说明：

- `conftest.py` 仅保留跨全局生命周期夹具（数据库引擎、会话、HTTP client、配置覆盖）。
- `fixtures/` 放业务域可复用测试夹具（如 `seeded_audio`、`voice_file_id`、A-5 种子数据）。
- `fixtures/api.py` 放接口层复用夹具（如 A-3/A-5 headers、请求 payload 模板）。
- `fixtures/database.py` 放数据库种子夹具（如 VoiceFile/VoiceSegment、track_id、author_id 数据准备）。
- `fixtures/external_services.py` 放外部服务辅助夹具（如 network_guard、scheduler status payload）。
- `shared/` 放可复用辅助函数（如 UTC 时间构造）。
- `unit/services` 与 `app/services` 按语义一一对应，便于快速定位测试。
- `integration/api` 按路由域组织，避免文件命名歧义。
- `integration/flows` 用于跨路由链路测试，验证关键业务流程端到端衔接。

## 常用命令

快速回归（默认）：

```bash
pytest tests/ -v
```

推荐日常回归：

```bash
pytest tests/ -v -m "not network and not e2e and not longrun"
```

推荐的当前回归命令：

```bash
pytest tests/unit/services/test_a3_callback_service.py tests/unit/services/test_a3_integration_service.py tests/unit/services/test_a5_integration_service.py tests/unit/services/test_archive_adapter.py tests/unit/services/test_ingestion_scheduler.py tests/unit/services/test_query_service.py tests/unit/services/test_storage_service.py tests/integration/api/test_a3_integration_routes.py tests/integration/api/test_a5_integration_routes.py tests/integration/api/test_callback_routes.py tests/integration/api/test_audio_routes.py tests/integration/api/test_health_routes.py tests/integration/api/test_ingestion_routes.py -m "not network and not e2e and not longrun" -v
```

## 浏览器回退相关测试建议

当前仓库已经增加了 Playwright 会话导出、浏览器辅助 Cookie 获取和代理池回退。相关验证建议如下：

- 优先跑单元测试，确认下载服务的兜底逻辑和状态登记没有破坏。
- 只有在本机允许的前提下，再手工运行浏览器回退脚本。
- 网络测试仍应单独执行，避免把远端 403 或 Cloudflare 行为当成本地回归失败。
- 若修改了代理池或本机 profile 相关配置，建议补跑与下载服务有关的测试文件。

仅单元测试：

```bash
pytest -m unit -v
```

仅集成测试：

```bash
pytest -m integration -v
```

A-3/A-5 相关测试：

```bash
pytest tests/unit/services/test_a3_integration_service.py tests/unit/services/test_a5_integration_service.py tests/unit/services/test_archive_adapter.py tests/integration/api/test_a3_integration_routes.py tests/integration/api/test_a5_integration_routes.py -v
```

真实网络测试：

```bash
pytest -m network -v
```

如果网络波动较大，可以只跑单个文件，例如：

```bash
pytest tests/unit/services/test_liveatc_client.py -m network -v
```

限制单测超时（需要 `pytest-timeout`）：

```bash
pytest -m network -v --timeout=60
```

端到端长稳测试（手动触发）：

```bash
set A2_LONGRUN_SECONDS=7200
set A2_LONGRUN_INTERVAL_SECONDS=30
set A2_LONGRUN_INCLUDE_HISTORICAL=1
pytest -m "e2e and longrun" -v
```

说明：这类长跑测试默认不建议在常规回归里执行；本次修改后的常规验证可以直接跳过它们。

### 建议的执行顺序

1. 先跑 `pytest tests/ -v -m "not network and not e2e and not longrun"`。
2. 如果改动触及 A-3/A-5，再补跑对应服务与路由测试。
3. 需要验证 LiveATC 联网能力时，再跑 `-m network`。
4. 只有在需要做稳定性验证时，才执行 `e2e` / `longrun`。

### 常见注意事项

- `tests/conftest.py` 已配置内存数据库和依赖覆盖，通常不需要手动准备数据库。
- A-3/A-5 接口测试会用到 token 头，测试夹具里已经提供。
- 共享的固定主键种子数据在测试里要先清理再写入，避免不同用例互相污染。
- 长耗时测试默认应跳过，避免在日常回归里触发超时。

## Locust 压测

基础压测：

```bash
locust -f tests/loadtest/locustfile.py --host=http://127.0.0.1:8000
```

高并发场景：

```bash
locust -f tests/loadtest/scenarios/peak_concurrent.py --host=http://127.0.0.1:8000
```

长稳场景：

```bash
locust -f tests/loadtest/scenarios/long_stability.py --host=http://127.0.0.1:8000
```

启用历史下载任务压测：

```bash
set A2_LOCUST_ENABLE_HISTORICAL=1
locust -f tests/loadtest/locustfile.py --host=http://127.0.0.1:8000
```

## Soak 脚本

```bash
python tests/loadtest/soak_runner.py --base-url http://127.0.0.1:8000 --duration-minutes 120 --interval-seconds 30
```

如果需要记录服务进程指标，追加 `--pid <服务进程PID>`。

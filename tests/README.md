# A-2 测试框架说明

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

```
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
│       ├── test_ingestion_scheduler.py
│       ├── test_ingestion_service.py
│       ├── test_liveatc_client.py
│       ├── test_query_service.py
│       └── test_storage_service.py
├── integration/
│   ├── api/
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
- `fixtures/` 放业务域可复用测试夹具（如 `seeded_audio`、`voice_file_id`）。
- `fixtures/api.py` 放接口层复用夹具（如 callback headers、请求 payload 模板）。
- `fixtures/database.py` 放数据库种子夹具（如 VoiceFile/VoiceSegment 数据准备）。
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

仅单元测试：

```bash
pytest -m unit -v
```

仅集成测试：

```bash
pytest -m integration -v
```

真实网络测试：

```bash
pytest -m network -v
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

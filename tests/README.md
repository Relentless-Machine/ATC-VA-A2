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
├── unit/
│   ├── test_ingest.py
│   ├── test_ingestion_scheduler.py
│   ├── test_liveatc_client.py
│   ├── test_storage.py
│   └── test_callback.py
├── integration/
│   ├── test_api_audio.py
│   ├── test_api_admin.py
│   ├── test_api_ingestion.py
│   └── test_api_callback.py
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

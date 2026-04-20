# ATC-VA A-2 FastAPI Framework

A-2模块基础工程，使用Python + FastAPI

## 已包含组件

- 实时/历史采集登记骨架（`/api/v1/ingestion/*`）
- A-3回调入库接口（`/api/v1/a3/callback`）
- 按时间范围流式音频下发（`/api/v1/audio/stream`，按偏移估算字节区间返回206）
- 存储容量检测与LRU清理入口（`/api/v1/admin/cleanup`）
- LiveATC实时监听与历史下载调度（`/api/v1/ingestion/scheduler/*`）
- SQLite异步模型（语音文件、切片、清理日志）
- 历史文件命名时间解析（如 `Apr-13-2026-0000Z` 转UTC）
- 调度链路存储熔断（空间不足时跳过下载并触发清理）
- HTTP请求指数退避重试（含抖动）
- A-3回调切片幂等写入（同文件+同偏移区间更新，不重复插入）

## 启动

1. 安装依赖

```bash
pip install -r requirements.txt
```

1. 配置环境变量

```bash
copy .env.example .env
```

1. 运行服务

```bash
python run.py
```

1. 打开接口文档

```bash
http://127.0.0.1:8000/docs
```

## 调度接口

- `POST /api/v1/ingestion/scheduler/start`：启动后台任务
- `POST /api/v1/ingestion/scheduler/stop`：停止后台任务
- `GET /api/v1/ingestion/scheduler/status`：查看调度状态
- `POST /api/v1/ingestion/scheduler/trigger/realtime`：手动触发一次实时切片
- `POST /api/v1/ingestion/scheduler/trigger/historical`：手动触发一次历史下载

## 测试

默认测试命令（会跳过 `network`、`e2e`、`longrun`）：

```bash
pytest tests/ -v
```

真实 LiveATC 网络测试：

```bash
pytest -m network -v
```

长稳测试（手动触发）：

```bash
set A2_LONGRUN_SECONDS=7200
set A2_LONGRUN_INTERVAL_SECONDS=30
set A2_LONGRUN_INCLUDE_HISTORICAL=1
pytest -m "e2e and longrun" -v
```

更多说明见 [tests/README.md](tests/README.md)。

## 端到端压测

启动服务后执行：

```bash
locust -f tests/loadtest/locustfile.py --host=http://127.0.0.1:8000
```

高并发场景：

```bash
locust -f tests/loadtest/scenarios/peak_concurrent.py --host=http://127.0.0.1:8000
```

长稳压测场景：

```bash
locust -f tests/loadtest/scenarios/long_stability.py --host=http://127.0.0.1:8000
```

独立长稳采样脚本：

```bash
python tests/loadtest/soak_runner.py --base-url http://127.0.0.1:8000 --duration-minutes 120 --interval-seconds 30
```

## 后续任务

- 接入A-5用户与航迹外键联调（`track_id`、`author_id`）

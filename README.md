# ATC-VA A-2 FastAPI Framework

A-2模块基础工程骨架，使用Python + FastAPI

## 已包含组件

- 实时/历史采集登记骨架（`/api/v1/ingestion/*`）
- A-3回调入库接口（`/api/v1/a3/callback`）
- 按时间范围流式音频下发（`/api/v1/audio/stream`）
- 存储容量检测与LRU清理入口（`/api/v1/admin/cleanup`）
- LiveATC 实时监听与历史下载调度（`/api/v1/ingestion/scheduler/*`）
- SQLite异步模型（语音文件、切片、清理日志）

## 启动

1. 安装依赖

```bash
pip install -r requirements.txt
```

2. 配置环境变量

```bash
copy .env.example .env
```

3. 运行服务

```bash
python run.py
```

4.FastAPI的前端
```bash
http://127.0.0.1:8000/docs
```

## 调度接口
- `POST /api/v1/ingestion/scheduler/start`：启动后台任务
- `POST /api/v1/ingestion/scheduler/stop`：停止后台任务
- `GET /api/v1/ingestion/scheduler/status`：查看调度状态
- `POST /api/v1/ingestion/scheduler/trigger/realtime`：手动触发一次实时切片
- `POST /api/v1/ingestion/scheduler/trigger/historical`：手动触发一次历史下载

## 后续任务
-接入真实LiveATC实时监听与历史下载任务调度
-补充A-5用户与航迹外键联调
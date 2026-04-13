# ATC-VA A-2 FastAPI Framework

A-2模块基础工程骨架，使用Python + FastAPI

## 已包含组件

- 实时/历史采集登记骨架（`/api/v1/ingestion/*`）
- A-3回调入库接口（`/api/v1/a3/callback`）
- 按时间范围流式音频下发（`/api/v1/audio/stream`）
- 存储容量检测与LRU清理入口（`/api/v1/admin/cleanup`）
- SQLite异步模型（语音文件、切片、清理日志）

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

## 后续任务

- 接入真实LiveATC实时监听与历史下载任务调度
- 补充A-5用户与航迹外键联调
- 增加单元测试与集成测试

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
- **A-3集成** - 处理请求、状态查询、失败重试、标注同步（新增）
- **A-5集成** - 轨迹查询、标注者查询、标注同步、跨模块报告（新增）

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

## 使用 liveatc-downloader 辅助

当 LiveATC 页面解析被限制时，可用仓库内的 `liveatc-downloader/` 作为辅助工具，先探测台站标识（mount id）并下载历史音频样本，再回填到本项目配置。

示例命令（在项目根目录执行）：

```bash
cd liveatc-downloader
python main.py stations VHHH
python main.py download vhhh5 -o ./downloads
```

说明：

- `stations` 用于列出 ICAO 对应台站，输出的 `identifier` 可用于 `.env` 的 `A2_LIVEATC_MOUNT_IDS`。
- `download` 默认下载到 `liveatc-downloader/downloads/`，可用 `-o` 指定目录。
- `liveatc-downloader` 主要用于历史归档探测与下载；实时流采集仍通过本项目 `/api/v1/ingestion/scheduler/trigger/realtime` 完成。

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

## A-3 和 A-5 模块集成

A-2模块现已支持与A-3预处理模块和A-5数据库模块的完整集成。详见 [A3_A5_INTEGRATION.md](A3_A5_INTEGRATION.md)

### A-3集成接口

- `POST /api/v1/a3/request-processing` - 发起处理请求
- `GET /api/v1/a3/status/{voice_file_id}` - 查询处理状态
- `POST /api/v1/a3/retry/{voice_file_id}` - 重试失败的处理（指数退避）
- `POST /api/v1/a3/sync-annotations/{voice_file_id}` - 同步标注状态
- `GET /api/v1/a3/queue` - 查看处理队列

### A-5集成接口

- `GET /api/v1/tracks/{track_id}/metadata` - 获取轨迹元数据
- `GET /api/v1/users/{author_id}/metadata` - 获取用户元数据
- `GET /api/v1/audio/by-track/{track_id}` - 按轨迹查询音频
- `GET /api/v1/audio/by-annotator/{author_id}` - 按标注者查询音频
- `POST /api/v1/a5/sync-annotations-to-a5/{voice_file_id}` - 同步标注到A-5
- `POST /api/v1/a5/sync-annotations-from-a5/{voice_file_id}` - 从A-5接收更新
- `GET /api/v1/a5/cross-module-report` - 生成系统报告

### 集成特性

- A-3处理状态追踪（未启动 → 处理中 → 完成/失败）
- 自动重试机制，带指数退避和随机抖动
- 段落标注状态同步
- 按轨迹ID（A-1航迹）查询相关音频
- 按标注者ID查询标注记录
- 双向标注数据同步（推送和拉取）
- 跨模块系统报告（文件数、处理率、标注率等）
- 完整的测试覆盖（9个新增测试）

## 后续任务

- [ ] 接入A-1航迹数据实时同步（track_id自动匹配）
- [ ] A-4前端界面对接（音频流播放 + 轨迹展示 + 标注编辑）

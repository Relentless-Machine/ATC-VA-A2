# LiveATC 历史音频下载完整指南

## 概述

本项目包含一个完整的 LiveATC 历史音频下载解决方案，包括：

1. **liveatc-downloader/** - 独立的 CLI 工具，用于下载 LiveATC 历史音频
2. **app/services/ingestion_service.py** - 主应用的高级异步摄取服务
3. **app/services/ingestion_scheduler.py** - 自动化定时下载任务调度器

## 架构

```text
LiveATC 历史音频下载系统
├── CLI 工具 (liveatc-downloader/)
│   ├── 适用于手动下载
│   ├── 支持单个、列表、批量下载
│   └── 返回详细的错误和成功信息
│
└── 主应用异步系统 (app/)
    ├── 自动定时下载
    ├── 数据库集成
    └── API 端点支持
```

## 快速开始

### 方式 1：使用 CLI 工具（liveatc-downloader）

#### 安装依赖

```bash
cd liveatc-downloader
pip install -r requirements.txt
```

#### 获取 Cookie（推荐）

某些 LiveATC 节点受 Cloudflare 保护，需要 Cookie：

1. 打开浏览器访问 <https://www.liveatc.net/>
2. 按 F12 打开开发者工具
3. 在"网络"标签中刷新页面
4. 找到任何请求，复制 Cookie 头值
5. 保存到文件：

```bash
echo "your-cookie-value" > ./.local/liveatc_cookie.txt
```

#### 列出机场电台

```bash
# 香港赤鱲角机场 (VHHH)
python main.py stations VHHH --cookie-file ./.local/liveatc_cookie.txt
```

#### 下载单个音频

```bash
# 下载最近的音频
python main.py download vhhh5 -o ./downloads --cookie-file ./.local/liveatc_cookie.txt

# 下载特定日期和时间
python main.py download vhhh5 -d Oct-28-2024 -t 1200Z -o ./downloads --cookie-file ./.local/liveatc_cookie.txt
```

#### 列出可用的历史档案

```bash
python main.py list vhhh5 --cookie-file ./.local/liveatc_cookie.txt
```

#### 下载日期范围内的所有音频

```bash
# 下载 2024 年 10 月 25-28 日的所有音频（所有 30 分钟时段）
python main.py download-range vhhh5 \
  --start-date 2024-10-25 \
  --end-date 2024-10-28 \
  -o ./downloads \
  --cookie-file ./.local/liveatc_cookie.txt

# 只下载指定时间的音频
python main.py download-range vhhh5 \
  --start-date 2024-10-25 \
  --end-date 2024-10-28 \
  --times 0000Z,0600Z,1200Z,1800Z \
  -o ./downloads \
  --cookie-file ./.local/liveatc_cookie.txt
```

### 方式 2：使用主应用 API（自动化）

#### 启动定时下载任务

```bash
# 激活应用时自动启动
curl -X POST http://localhost:8000/api/v1/ingestion/scheduler/start
```

#### 查询任务状态

```bash
curl http://localhost:8000/api/v1/ingestion/scheduler/status
```

示例响应：

```json
{
  "running": true,
  "icao_code": "VHHH",
  "last_error": null,
  "last_historical_at": "2024-10-28T12:30:45.123456",
  "last_historical_found": 45,
  "last_historical_downloaded": 3,
  "last_historical_skipped": 42,
  "last_cookie_warmup_ok": true,
  "last_cookie_count": 2
}
```

#### 手动触发一次下载

```bash
curl -X POST http://localhost:8000/api/v1/ingestion/scheduler/trigger/historical
```

#### 注册历史下载

```bash
curl -X POST http://localhost:8000/api/v1/ingestion/historical/register \
  -H "Content-Type: application/json" \
  -d '{
    "file_name": "VHHH5-Oct-28-2024-1200Z.mp3",
    "source_url": "https://archive.liveatc.net/vhhh/VHHH5-Oct-28-2024-1200Z.mp3",
    "start_time_utc": "2024-10-28T12:00:00Z",
    "end_time_utc": "2024-10-28T12:30:00Z"
  }'
```

## 下载逻辑详解

### CLI 工具 (liveatc-downloader) 的下载流程

```text
用户命令
   ↓
┌─────────────────────────────────────┐
│ 1. 建立 HTTP 会话                    │
│    (包含 User-Agent 和 Cookie)       │
└──────────────┬──────────────────────┘
               ↓
┌─────────────────────────────────────┐
│ 2. 获取档案页面                      │
│    https://liveatc.net/archive.php  │
│    解析 HTML 获取档案标识符           │
└──────────────┬──────────────────────┘
               ↓
┌─────────────────────────────────────┐
│ 3. 构建下载 URL                      │
│    https://archive.liveatc.net/vhhh/ │
│    + 文件名 (编码)                   │
└──────────────┬──────────────────────┘
               ↓
┌─────────────────────────────────────┐
│ 4. 检查文件                          │
│    - 文件是否已存在                  │
│    - 下载后验证大小                  │
└──────────────┬──────────────────────┘
               ↓
┌─────────────────────────────────────┐
│ 5. 返回结果                          │
│    {                                │
│      'success': true/false,          │
│      'filename': '...',              │
│      'filepath': '...',              │
│      'url': '...',                   │
│      'size': 1234567,                │
│      'error': '...'  # 如果失败      │
│    }                                │
└─────────────────────────────────────┘
```

### 主应用异步下载流程

```text
定时任务触发 (每 hour/30min)
   ↓
┌──────────────────────────────┐
│ 检查存储空间                  │
│ (ensure_capacity)             │
└──────┬───────────────────────┘
       ↓
┌──────────────────────────────┐
│ Cookie 预热                   │
│ (ensure_public_session_cookie)│
└──────┬───────────────────────┘
       ↓
┌──────────────────────────────┐
│ 列出历史链接                  │
│ (list_historical_links)       │
└──────┬───────────────────────┘
       ↓
   ┌─┴─────────────────────┐
   │ 对每个链接循环         │
   ├─────────────────────┤
   │ 1. 检查 URL 是否存在   │
   │    (has_source_url)   │
   │ 2. 下载文件            │
   │ 3. 保存到数据库        │
   │    (register_download) │
   └─┬───────────────────┘
     ↓
┌──────────────────────────────┐
│ 记录统计信息                  │
│ - 找到的文件数                │
│ - 已下载数                    │
│ - 跳过数                      │
│ - 错误信息                    │
└──────────────────────────────┘
```

## 关键特性

### 1. 错误处理和恢复

- Cloudflare 绕过（Cookie + cloudscraper）
- 网络重试机制（指数退避）
- 部分下载清理
- 文件验证

### 2. 数据去重

- 源 URL 检查（避免重复下载）
- 文件名检查
- 数据库集成

### 3. 性能优化

- 异步 HTTP 请求
- 流式下载（避免内存溢出）
- 定时任务调度
- 存储容量管理

### 4. 时间戳处理

- 从文件名提取时间戳
- 自动 UTC 转换
- 半小时段识别

## 配置参数

### 环境变量 (在 .env 中)

```bash
# LiveATC 基础 URL
A2_LIVEATC_BASE_URL=https://www.liveatc.net

# 档案基础 URL
A2_LIVEATC_ARCHIVE_BASE_URL=https://archive.liveatc.net

# 搜索 URL 模板
A2_LIVEATC_SEARCH_URL=https://www.liveatc.net/search/?icao={icao}

# 电台标识符（逗号分隔）
A2_LIVEATC_MOUNT_IDS=vhhh5,vhhh_app,vhhh_gnd

# ICAO 代码
A2_ICAO_CODE=VHHH

# 历史下载配置
A2_HISTORICAL_INTERVAL_SECONDS=3600    # 每小时检查一次
A2_HISTORICAL_MAX_FILES_PER_RUN=10      # 每次最多下载 10 个文件

# 实时流配置
A2_REALTIME_INTERVAL_SECONDS=600       # 每 10 分钟捕获一次
A2_REALTIME_CAPTURE_SECONDS=600        # 每次捕获 10 分钟

# HTTP 配置
A2_HTTP_USER_AGENT=Mozilla/5.0 (Windows NT 10.0; Win64; x64)...
A2_HTTP_COOKIE=cf_clearance=xxx        # 可选的 Cloudflare Cookie
A2_HTTP_MAX_RETRIES=3                  # 重试次数
A2_HTTP_BACKOFF_BASE_SECONDS=2         # 指数退避基数
A2_HTTP_BACKOFF_MAX_SECONDS=60         # 最大等待时间

# 存储配置
A2_AUDIO_STORAGE=./storage/audio
A2_CHUNK_SIZE=8192                     # 下载块大小
```

## 故障排除

### 问题 1: 下载失败，返回 403

**原因**: Cloudflare 保护

**解决方案**:

1. 获取 Cookie 并使用 `--cookie-file`
2. 确保已安装 `pip install cloudscraper`
3. 等待几分钟后重试

### 问题 2: 无法找到电台

**原因**: 电台标识符错误或机场代码错误

**解决方案**:

```bash
python main.py stations VHHH  # 列出所有可用电台
```

### 问题 3: 下载缓慢或超时

**原因**: 网络问题或服务器繁忙

**解决方案**:

1. 检查网络连接
2. 尝试较短的时间范围
3. 增加重试次数: `A2_HTTP_MAX_RETRIES=5`

### 问题 4: 数据库错误

**原因**: 数据库连接问题

**解决方案**:

1. 检查数据库是否运行
2. 验证数据库连接字符串
3. 检查 SQLAlchemy 日志

## 示例脚本

### 批量下载并处理

```python
#!/usr/bin/env python3
import subprocess
from datetime import datetime, timedelta

station = "vhhh5"
start_date = datetime(2024, 10, 25)
end_date = datetime(2024, 10, 28)

cmd = [
    "python", "main.py", "download-range", station,
    "--start-date", start_date.strftime("%Y-%m-%d"),
    "--end-date", end_date.strftime("%Y-%m-%d"),
    "-o", "./downloads",
    "--cookie-file", "./.local/liveatc_cookie.txt"
]

result = subprocess.run(cmd, cwd="./liveatc-downloader/")
print(f"Exit code: {result.returncode}")
```

### API 集成示例

```python
import httpx
import asyncio

async def start_historical_download():
    async with httpx.AsyncClient() as client:
        # 启动定时任务
        await client.post("http://localhost:8000/api/v1/ingestion/scheduler/start")
        
        # 获取状态
        response = await client.get("http://localhost:8000/api/v1/ingestion/scheduler/status")
        print(response.json())
        
        # 手动触发一次
        response = await client.post("http://localhost:8000/api/v1/ingestion/scheduler/trigger/historical")
        print(response.json())

asyncio.run(start_historical_download())
```

## 参考资源

- [LiveATC.net](https://www.liveatc.net)
- [BeautifulSoup 文档](https://www.crummy.com/software/BeautifulSoup/)
- [cloudscraper](https://github.com/VeNoMouS/cloudscraper)

## 许可证

MIT

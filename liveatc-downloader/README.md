# LiveATC Downloader

从 LiveATC.net 下载存档的 ATC 录音。

**注意**: 这是一个正在开发中的工具，可能不适用于所有机场。

## 功能

- ✅ **列出电台** - 查看指定机场的所有可用电台
- ✅ **单个下载** - 下载特定电台在特定日期/时间的音频
- ✅ **批量列表** - 列出电台的所有历史音频档案
- ✅ **日期范围下载** - 一次性下载指定日期范围内的所有音频
- ✅ **Cloudflare 绕过** - 支持 Cookie 或 cloudscraper 库绕过 Cloudflare
- ✅ **完整错误处理** - 详细的错误提示和日志

## 安装

```bash
pip install -r requirements.txt
```

依赖项：
- `requests` - HTTP 请求
- `beautifulsoup4` - HTML 解析
- `cloudscraper` - 绕过 Cloudflare（可选）

## 使用方法

### 1. 列出机场的电台

```bash
python main.py stations VHHH --cookie-file ./.local/liveatc_cookie.txt
python main.py stations KPDX
```

输出示例：
```
[vhhh5] - Hong Kong RXJ_5 (Radar)
	Director - 135.6
	Tower - 118.1
	Ground - 121.9
...
```

### 2. 下载单个音频文件

下载最后一个 30 分钟时段的音频：
```bash
python main.py download vhhh5 -o ./downloads --cookie-file ./.local/liveatc_cookie.txt
```

下载特定日期和时间的音频：
```bash
python main.py download vhhh5 -d Oct-01-2021 -t 2000Z -o ./downloads --cookie-file ./.local/liveatc_cookie.txt
```

### 3. 列出电台的历史档案

```bash
python main.py list vhhh5 --cookie-file ./.local/liveatc_cookie.txt
```

输出示例：
```
找到 120 个档案:

1. VHHH5-Oct-28-2021-0000Z.mp3 (Oct-28-2021 0000Z)
2. VHHH5-Oct-28-2021-0030Z.mp3 (Oct-28-2021 0030Z)
...
```

### 4. 下载日期范围内的所有音频

下载 2021 年 10 月 1-5 日的所有 30 分钟时段音频：
```bash
python main.py download-range vhhh5 \
  --start-date 2021-10-01 \
  --end-date 2021-10-05 \
  -o ./downloads \
  --cookie-file ./.local/liveatc_cookie.txt
```

下载特定时间（例如仅下载整点和半点）：
```bash
python main.py download-range vhhh5 \
  --start-date 2021-10-01 \
  --end-date 2021-10-05 \
  --times 0000Z,0030Z,0100Z,0130Z \
  -o ./downloads \
  --cookie-file ./.local/liveatc_cookie.txt
```

### Archive base URL override (mirror)

If you have a mirror or local cache, override the archive host:

```bash
python main.py download vhhh5 -o ./downloads \
  --archive-base-url https://your-mirror.example.com \
  --cookie-file ./.local/liveatc_cookie.txt
```

You can also set `LIVEATC_ARCHIVE_BASE_URL` to apply it by default.

## Cookie 认证

某些 LiveATC 节点受 Cloudflare 保护，可能需要手动提供 Cookie：

### 获取 Cookie（使用浏览器开发者工具）

1. 打开 https://www.liveatc.net/
2. 按 F12 打开开发者工具
3. 切换到"网络"（Network）标签
4. 刷新页面
5. 查找任何请求（例如 search.php）
6. 在"请求标头"中找到 `Cookie` 字段
7. 复制整个 Cookie 值
8. 保存到文件：
```bash
echo "your-cookie-here" > ./.local/liveatc_cookie.txt
```

### 使用 Cookie

在任何命令中添加 `--cookie-file` 参数：
```bash
python main.py download vhhh5 -o ./downloads --cookie-file ./.local/liveatc_cookie.txt
```

或直接使用 `--cookie` 参数：
```bash
python main.py download vhhh5 -o ./downloads --cookie "cf_clearance=xxx; session=yyy"
```

### Browser-assisted cookie export (optional)

If you prefer a real browser session to capture cookies:

```bash
pip install -r requirements.txt
playwright install
python main.py cookie --output ./.local/liveatc_cookie.txt
```

This opens a browser window so you can complete any verification manually.
Once ready, press Enter in the terminal to save the Cookie file.

安全建议：不要将 Cookie 硬编码到代码或提交到仓库。推荐的安全做法：

- 将 Cookie 存为本地文件（例如 `./.local/liveatc_cookie.txt`），或在运行时通过环境变量传入。
- 在自动化或测试脚本中使用环境变量 `LIVEATC_COOKIE` 来提供 Cookie，例如：

```powershell
$env:LIVEATC_COOKIE = 'cf_clearance=...; other=...'
d:/path/to/venv/Scripts/python.exe main.py download vhhh5 -o ./downloads
```

- 确保 `.gitignore` 包含私密 Cookie 文件（例如 `/.local/`），避免误提交。

脚本和测试已改为优先从环境变量 `LIVEATC_COOKIE` 读取 Cookie，增强安全性。

## 注意事项

- **30 天限制**: LiveATC 仅保存最近 30 天的档案
- **时间格式**: 所有时间均为 Zulu（UTC）时间
- **日期格式**: 档案日期格式为 `Oct-01-2021` (月-日-年)
- **平台兼容性**: 在 Windows、macOS 和 Linux 上测试过

## 常见问题

### Q: 下载过程中遇到 403 错误怎么办？

A: 这通常是 Cloudflare 保护导致的。尝试：
1. 使用 `--cookie-file` 参数提供 Cookie
2. 确保安装了 `cloudscraper`: `pip install cloudscraper`
3. 等待几分钟后重试

### Q: 如何找到正确的电台标识符？

A: 使用 `stations` 命令列出所有电台：
```bash
python main.py stations VHHH
```

### Q: 为什么某些文件下载失败？

A: 可能的原因：
- 该时段没有可用的档案
- 网络连接问题
- Cookie 已过期

## 故障排除

启用详细日志（在代码中）并查看终端输出获取更多信息。

## 许可证

MIT

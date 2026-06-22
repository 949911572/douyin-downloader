# 抖音下载器 V2.0（Douyin Downloader）

![douyin-downloader](https://socialify.git.ci/jiji262/douyin-downloader/image?custom_description=%E6%8A%96%E9%9F%B3%E6%89%B9%E9%87%8F%E4%B8%8B%E8%BD%BD%E5%B7%A5%E5%85%B7%EF%BC%8C%E5%8E%BB%E6%B0%B4%E5%8D%B0%EF%BC%8C%E6%94%AF%E6%8C%81%E8%A7%86%E9%A2%91%E3%80%81%E5%9B%BE%E9%9B%86%E3%80%81%E4%BD%9C%E8%80%85%E4%B8%BB%E9%A1%B5%E6%89%B9%E9%87%8F%E4%B8%8B%E8%BD%BD%E3%80%82&description=1&font=Jost&forks=1&logo=https%3A%2F%2Fraw.githubusercontent.com%2Fjiji262%2Fdouyin-downloader%2Frefs%2Fheads%2FV1.0%2Fimg%2Flogo.png&name=1&owner=1&pattern=Circuit+Board&pulls=1&stargazers=1&theme=Light)

> 🔄 **本项目是 jiji262/douyin-downloader 的 fork 版本**，主要修改：
> - 移除了 `start_time` / `end_time` 时间范围配置
> - 改用 `scan_records.json` 中的 `last_scan_time` 实现增量更新
> - 单视频下载不写入扫描记录，仅用户主页下载才记录
> - 适合定期执行下载任务，自动获取上次扫描之后发布的新视频

一个面向实用场景的抖音下载工具，支持单条作品下载和作者主页批量下载，默认带进度展示、重试、数据库去重和浏览器兜底能力。

> 当前文档对应 **V2.0（main 分支）**。  
> 如需使用旧版，请切回 **V1.0**：`git fetch --all && git switch V1.0`

## 版本更新提醒

> ⚠️ 本项目已重大升级到 **V2.0**，后续功能迭代与问题修复将主要在 `main` 分支进行。  
> **V1.0 仍可使用**，但仅做低频维护，不会持续高频更新。

## 功能概览

### 已支持

- 单个视频下载：`/video/{aweme_id}`
- 单个图文下载：`/note/{note_id}`
- 短链自动解析：`https://v.douyin.com/...`
- 用户主页批量下载：`/user/{sec_uid}` + `mode: [post]`
- 无水印优先、封面/音乐/头像/JSON 元数据下载
- 可选视频转写（`transcript`，调用 OpenAI Transcriptions API）
- 并发下载、失败重试、速率限制
- SQLite 去重与增量下载（`increase.post`）
- 翻页受限时浏览器兜底抓取（支持人工过验证）
- 进度条展示（支持 `progress.quiet_logs` 静默模式）

### 暂未接入（请勿按已支持使用）

- `mode: like` 点赞下载
- `mode: mix` 合集下载
- `number.like` / `number.mix` / `increase.like` / `increase.mix`
- `collection/mix` 链接当前无对应下载器（会提示不支持）

## 快速开始

### 1) 环境准备

- Python 3.8+
- macOS / Linux / Windows

### 2) 安装依赖

```bash
pip install -r requirements.txt
```

### 3) 复制配置

```bash
cp config.example.yml config.yml
```

### 4) 获取 Cookie（推荐自动方式）

```bash
pip install playwright
python -m playwright install chromium
python -m tools.cookie_fetcher --config config.yml
```

登录抖音后回到终端按 Enter，程序会自动写入配置。

## 最小可用配置

```yaml
link:
  - https://www.douyin.com/user/MS4wLjABAAAAxxxx

path: ./Downloaded/
mode:
  - post

number:
  post: 0

thread: 5
retry_times: 3
database: true

progress:
  quiet_logs: true

cookies:
  msToken: ""
  ttwid: YOUR_TTWID
  odin_tt: YOUR_ODIN_TT
  passport_csrf_token: YOUR_CSRF_TOKEN
  sid_guard: ""

browser_fallback:
  enabled: true
  headless: false
  max_scrolls: 240
  idle_rounds: 8
  wait_timeout_seconds: 600

transcript:
  enabled: false
  model: gpt-4o-mini-transcribe
  output_dir: ""
  response_formats: ["txt", "json"]
  api_url: https://api.openai.com/v1/audio/transcriptions
  api_key_env: OPENAI_API_KEY
  api_key: ""
```

## 使用方式

### 方式一：使用 PowerShell 脚本（推荐）

```bash
# 使用默认配置
.\scripts\download_douyin.ps1

# 指定配置文件
.\scripts\download_douyin.ps1 -ConfigFile config_temp.yml
```

**PowerShell 脚本优势**：
- ✅ 自动检查配置文件是否存在
- ✅ 自动创建下载目录（如果不存在）
- ✅ 验证下载目录写入权限
- ✅ 自动设置 UTF-8 编码，避免中文乱码
- ✅ 下载完成后自动打开下载目录

### 方式二：直接运行 Python 脚本

```bash
# 使用默认配置
python run.py

# 指定配置文件
python run.py -c config.yml
```

> **注意**：如果直接运行 `python run.py`，脚本会检测到未使用推荐方式，并显示警告提示。建议使用 PowerShell 脚本以获得最佳体验。

### 命令行追加参数

```bash
python run.py -c config.yml \
  -u "https://www.douyin.com/video/7604129988555574538" \
  -t 8 \
  -p ./Downloaded
```

参数说明：

- `-u, --url`：追加下载链接（可重复传入）
- `-c, --config`：指定配置文件
- `-p, --path`：指定下载目录
- `-t, --thread`：指定并发数
- `--show-warnings`：显示 warning/error 日志
- `-v, --verbose`：显示 info/warning/error 日志

刷新 last_video_time 命令：

- `--refresh-video-time`：刷新所有用户的 last_video_time（跳过4小时限制，不进行下载）
- `--refresh-video-time "https://v.douyin.com/xxx/"`：刷新指定用户的 last_video_time

## 典型场景

### 下载单个视频

```yaml
link:
  - https://www.douyin.com/video/7604129988555574538
```

### 下载单个图文

```yaml
link:
  - https://www.douyin.com/note/7341234567890123456
```

### 批量下载作者主页作品

```yaml
link:
  - https://www.douyin.com/user/MS4wLjABAAAAxxxx
mode:
  - post
number:
  post: 50
```

### 全量抓取（不限制数量）

```yaml
number:
  post: 0
```

### 增量更新下载（定期执行）

本版本默认支持增量更新，无需额外配置。

```yaml
link:
  - https://www.douyin.com/user/MS4wLjABAAAAxxxx
mode:
  - post
number:
  post: 0  # 0 表示不限制数量
```

**增量更新工作机制：**

1. 首次下载：获取用户所有作品，并记录 `last_video_time`（最新视频发布时间）到 `data/scan_records.json`
2. 后续下载：仅获取 `last_video_time` 之后发布的新视频
3. 单视频/图文链接：不写入扫描记录，不影响增量更新

**扫描记录文件位置：** `data/scan_records.json`

**刷新视频时间（不下载）：**

```bash
# 刷新所有用户的 last_video_time（跳过4小时限制）
python run.py -c config.yml --refresh-video-time

# 刷新指定用户的 last_video_time
python run.py -c config.yml --refresh-video-time "https://v.douyin.com/xxx/"
```

**注意事项：**
- 仅用户主页链接（`/user/{sec_uid}`）才会记录扫描时间
- 删除 `scan_records.json` 可重新开始全量下载
- 可手动修改 `last_video_time` 字段调整增量更新起始时间

**跳过阈值配置（`skip_threshold_hours`）：**

默认配置文件中有一个 `skip_threshold_hours` 参数，用于控制短时间内重复扫描的行为：

```yaml
# config.yml
skip_threshold_hours: 4  # 4小时内已处理过的用户将被跳过
```

| 参数值 | 行为 |
|--------|------|
| `4`（默认） | 4小时内已成功处理的用户将被跳过 |
| `0` | 不跳过任何用户，每次都执行下载 |
| 空值 | 不跳过任何用户，每次都执行下载 |

**为什么下载不到新视频？**

如果发现下载脚本没有下载到新视频，可能是以下原因：

1. **`skip_threshold_hours` 限制**：用户在短时间内已处理过，被跳过了
   - 解决方案：设置 `skip_threshold_hours:` 为空或 `0`

2. **`last_video_time` 已更新**：上次扫描时已经记录了最新视频时间，新视频还未发布
   - 解决方案：等待新视频发布，或手动修改 `scan_records.json` 中的 `last_video_time`

3. **数据库去重**：视频已在数据库中标记为已下载
   - 解决方案：使用 `scripts/mark_failed_as_success.py` 检查失败记录，或删除数据库中的记录

## 辅助脚本说明

### scripts 目录下的脚本文件

| 脚本名称 | 类型 | 说明 |
|----------|------|------|
| `download_douyin.ps1` | PowerShell | **主下载脚本**，推荐的启动方式 |
| `refresh_cookies.ps1` | PowerShell | Cookie 刷新脚本，打开浏览器扫码登录 |
| `_refresh_cookies.py` | Python | Cookie 刷新核心逻辑（被 refresh_cookies.ps1 调用） |
| `mark_failed_as_success.py` | Python | 将失败视频标记为已下载 |

### 1. Cookie 刷新脚本

当 Cookie 过期导致下载失败时使用：

```bash
# 方式1：使用 PowerShell 脚本（推荐）
.\scripts\refresh_cookies.ps1

# 方式2：直接运行 Python 脚本
python scripts/_refresh_cookies.py
```

**功能特点**：
- 自动打开 Chrome 浏览器
- 等待用户扫码登录
- 自动提取 Cookie（包括 msToken）
- 自动更新 `config.yml` 文件

### 2. 失败视频处理脚本

处理下载失败的视频，将其标记为已下载：

```bash
# 处理所有失败文件
python scripts/mark_failed_as_success.py

# 处理指定失败文件
python scripts/mark_failed_as_success.py data/failed_videos/failed_20240101.json

# 处理但不清空失败文件
python scripts/mark_failed_as_success.py --no-clear

# 显示帮助
python scripts/mark_failed_as_success.py --help
```

**功能特点**：
- 自动查找 `data/failed_videos/` 目录下的失败文件
- 将失败视频标记为已下载（更新数据库）
- 可选是否清空失败文件

### 3. 浏览器登录状态检查脚本

检查当前 Cookie 的登录状态，可用于预检查登录有效性：

```bash
# 打开浏览器检查登录状态
python scripts/open_browser.py
```

**功能特点**：
- 打开 Chrome 浏览器访问抖音首页
- 加载当前配置中的 Cookie
- 检查右上角是否显示头像（已登录状态）
- 支持手动登录后自动同步 Cookie
- 关闭浏览器后自动更新配置文件

## 可选功能：视频转写（transcript）

当前实现仅对**视频作品**生效（图文不会生成转写）。

### 1) 开启方式

```yaml
transcript:
  enabled: true
  model: gpt-4o-mini-transcribe
  output_dir: ""        # 留空: 与视频同目录；非空: 镜像到指定目录
  response_formats:
    - txt
    - json
  api_key_env: OPENAI_API_KEY
  api_key: ""           # 可直接填，或使用环境变量
```

推荐通过环境变量提供密钥：

```bash
export OPENAI_API_KEY="sk-xxxx"
```

### 2) 输出文件

启用后会生成：

- `xxx.transcript.txt`
- `xxx.transcript.json`

若 `database: true`，会在数据库 `transcript_job` 表记录状态（`success/failed/skipped`）。

## 关键配置项（按当前代码实际生效）

- `mode`：当前仅 `post` 生效
- `number`：当前仅 `number.post` 生效
- `increase`：当前仅 `increase.post` 生效
- `folderstyle`：控制按作品维度创建子目录
- `browser_fallback.*`：`post` 翻页受限时启用浏览器兜底
- `progress.quiet_logs`：进度阶段静默日志，减少刷屏
- `transcript.*`：视频下载后的可选转写
- `auto_cookie`：预留字段，当前主流程未使用

## 输出目录

默认 `folderstyle: true` 时：

```text
Downloaded/
├── download_manifest.jsonl
└── 作者名/
    └── post/
        └── 2024-02-07_作品标题_aweme_id/
            ├── ...mp4
            ├── ..._cover.jpg
            ├── ..._music.mp3
            ├── ..._data.json
            ├── ..._avatar.jpg
            ├── ...transcript.txt      # transcript.enabled=true 且格式包含 txt
            └── ...transcript.json     # transcript.enabled=true 且格式包含 json
```

## 常见问题

### 1) 只能抓到 20 条作品怎么办？

这是翻页风控的常见现象。确保：

- `browser_fallback.enabled: true`
- `browser_fallback.headless: false`
- 浏览器弹窗出现后手动完成验证，不要立即关闭窗口

### 2) 进度条出现重复刷屏怎么办？

默认 `progress.quiet_logs: true` 会在进度阶段静默日志。  
调试时再临时加 `--show-warnings` 或 `-v`。

### 3) Cookie 失效怎么办？

重新执行：

```bash
python -m tools.cookie_fetcher --config config.yml
```

### 4) 为什么没有生成 transcript 文件？

请依次检查：

- `transcript.enabled` 是否为 `true`
- 是否下载的是视频（图文不转写）
- `OPENAI_API_KEY`（或 `transcript.api_key`）是否有效
- `response_formats` 是否包含 `txt` 或 `json`

## 旧版切换（V1.0）

如果你要继续使用老脚本风格（V1.0），可切换到旧分支：

```bash
git fetch --all
git switch V1.0
```

## 沟通群

![qun](./img/fuye.jpg)

## 免责声明

本项目仅用于技术研究、学习交流与个人数据管理。请在合法合规前提下使用：

- 不得用于侵犯他人隐私、版权或其他合法权益
- 不得用于任何违法违规用途
- 使用者应自行承担因使用本项目产生的全部风险与责任
- 如平台规则、接口策略变更导致功能失效，属于正常技术风险

如果你继续使用本项目，即视为已阅读并同意上述声明。

# 抖音下载器 V2.1（Douyin Downloader）

![douyin-downloader](https://socialify.git.ci/jiji262/douyin-downloader/image?custom_description=%E6%8A%96%E9%9F%B3%E6%89%B9%E9%87%8F%E4%B8%8B%E8%BD%BD%E5%B7%A5%E5%85%B7%EF%BC%8C%E5%8E%BB%E6%B0%B4%E5%8D%B0%EF%BC%8C%E6%94%AF%E6%8C%81%E8%A7%86%E9%A2%91%E3%80%81%E5%9B%BE%E9%9B%86%E3%80%81%E4%BD%9C%E8%80%85%E4%B8%BB%E9%A1%B5%E6%89%B9%E9%87%8F%E4%B8%8B%E8%BD%BD%E3%80%82&description=1&font=Jost&forks=1&logo=https%3A%2F%2Fraw.githubusercontent.com%2Fjiji262%2Fdouyin-downloader%2Frefs%2Fheads%2FV1.0%2Fimg%2Flogo.png&name=1&owner=1&pattern=Circuit+Board&pulls=1&stargazers=1&theme=Light)

> 🔄 **本项目是 jiji262/douyin-downloader 的 fork 版本**，主要差异：
> - 移除了 `start_time` / `end_time` 时间范围配置
> - 改用 `scan_records.json` 中的 `last_video_time` 实现增量更新
> - 单视频下载不写入扫描记录，仅用户主页下载才记录
> - 适合定期执行下载任务，自动获取上次扫描之后发布的新视频
> - 更多 fork 特性请查看下方「🍴 Fork 版本扩展功能」章节

一个面向实用场景的抖音下载工具，支持单条作品下载和作者主页批量下载，默认带进度展示、重试、数据库去重和浏览器兜底能力。

> 当前文档对应 **V2.1（main 分支）**。  
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
- 图文作品（图集）下载，支持多候选 URL 轮换容错 🍴
- 可选视频转写（`transcript`，调用 OpenAI Transcriptions API）
- 并发下载、失败重试、速率限制
- SQLite 去重与增量下载（基于 `scan_records.json`）🍴
- 进度条展示（支持 `progress.quiet_logs` 静默模式）
- 下载失败时自动写入详细错误日志 🍴
- 数据库一键备份 🍴

### 暂未接入（请勿按已支持使用）

- `mode: like` 点赞下载
- `mode: mix` 合集下载
- `number.like` / `number.mix`
- `collection/mix` 链接当前无对应下载器（会提示不支持）

## 快速开始

### 1) 环境准备

- Python 3.8+
- macOS / Linux / Windows

### 2) 安装依赖

```bash
pip install -r requirements.txt
```

### 3) 安装浏览器（Playwright 需要）

```bash
python -m playwright install chromium
```

> **说明**：`playwright` 包已在 requirements.txt 中，但浏览器二进制文件需要单独安装。此步骤会下载 Chromium 浏览器到本地缓存目录。

#### 浏览器使用说明 🍴

项目**统一使用 Playwright 安装的 Chromium 浏览器**，不依赖系统安装的 Chrome：

| 功能 | 使用浏览器 | 说明 |
|------|-----------|------|
| `verify-login` | Playwright Chromium | 打开浏览器，人工确认登录状态 |
| `refresh-cookies` | Playwright Chromium | 从 chrome_user_data 提取登录 Cookie |
| `fetch-links` | Playwright Chromium | 从浏览器获取收藏视频或用户主页链接 |

**用户数据目录**：`data/chrome_user_data/`
- 所有浏览器功能共享同一个用户数据目录
- 登录状态持久保存在此目录中，只需登录一次
- 删除此目录会导致登录状态丢失，需要重新登录

**浏览器参数**（统一配置）：
- User-Agent：`Chrome/120.0.0.0`
- Viewport：`1280x800`
- 禁用自动化检测、沙箱等反爬措施

### 4) 复制配置

```bash
cp config.example.yml config.yml
```

### 5) 获取 Cookie（推荐自动方式）

```bash
.\scripts\douyin.ps1 -Action refresh-cookies
```

登录抖音后，程序会自动检测登录状态并写入配置。

## 最小可用配置

> ⚠️ **安全提醒**：`config.yml` 包含敏感信息（Cookie、API Key 等），已加入 `.gitignore`，**切勿提交到版本控制**。

```yaml
link:
  - https://www.douyin.com/user/MS4wLjABAAAAxxxx

path: ./Downloaded/
mode:
  - post

number:
  post: 0

thread: 1
retry_times: 3
database: true

progress:
  quiet_logs: true

cookies:              # ⚠️ Cookie 包含账号敏感信息，请勿泄露
  msToken: ""
  ttwid: YOUR_TTWID
  odin_tt: YOUR_ODIN_TT
  passport_csrf_token: YOUR_CSRF_TOKEN
  sid_guard: ""

url_delay:
  enabled: true
  min_seconds: 2
  max_seconds: 5

skip_threshold_hours: 4

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

### 方式一：命令行直接运行

```bash
# 使用默认配置
python run.py

# 指定配置文件
python run.py -c config.yml
```

### 方式二：命令行追加参数

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

### 增量更新下载 🍴

本版本支持增量更新，基于 `scan_records.json` 中的 `last_video_time` 控制。

**增量更新工作机制：**
1. 首次下载：获取用户所有作品，并记录最新视频时间到扫描记录
2. 后续下载：仅获取上次扫描之后发布的新视频

**扫描记录文件位置：** `data/scan_records.json`

**注意**：增量更新仅对用户主页链接（`/user/{sec_uid}`）生效，单视频/图文链接不写入扫描记录。

## 辅助脚本说明

推荐使用 `douyin.ps1` 作为统一入口，支持所有操作模式。详细用法请查看下方「🍴 Fork 版本扩展功能」章节。

| 脚本名称 | 类型 | 说明 |
|----------|------|------|
| `douyin.ps1` | PowerShell | **统一入口脚本**（推荐），支持下载、重试、标记跳过、检查登录、刷新 Cookie 等所有操作 🍴 |
| `verify_login.py` | Python | 人工确认浏览器登录状态（打开浏览器，检查/完成登录） 🍴 |
| `fetch_links.py` | Python | 从浏览器获取收藏视频或用户主页链接 🍴 |
| `_refresh_cookies.py` | Python | Cookie 刷新核心逻辑 🍴 |

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
  api_key: ""           # ⚠️ 推荐使用环境变量，不要硬编码 API Key
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

- `mode`：当前仅 `post` 生效（`like` / `mix` / `collection` 为预留字段，尚未实现）
- `number`：当前仅 `number.post` 生效（`number.like` / `number.mix` / `number.music` / `number.allmix` 为预留字段，尚未实现）
- `increase`：当前仅 `increase.post` 生效（`increase.like` / `increase.mix` 等为预留字段，尚未实现）
- `folderstyle`：控制按作品维度创建子目录
- `progress.quiet_logs`：进度阶段静默日志，减少刷屏
- `transcript.*`：视频下载后的可选转写
- `skip_threshold_hours`：URL级别跳过阈值（默认4小时），详细逻辑见"下载跳过逻辑流程"🍴
- `url_delay.*`：URL间随机延迟配置，降低被限流风险🍴

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

### download_manifest.jsonl 说明

**文件用途**：记录每一个成功下载的视频/作品的详细元数据，作为独立于数据库的下载清单。

**格式**：JSONL（每行一条 JSON，append-only 追加写入）

**每条记录包含字段**：

| 字段 | 说明 |
|------|------|
| `date` | 作品发布日期 |
| `aweme_id` | 作品唯一标识 |
| `author_name` | 作者昵称 |
| `desc` | 作品描述/标题 |
| `media_type` | 媒体类型（video/gallery） |
| `tags` | 提取的标签列表 |
| `file_names` | 下载的文件名列表 |
| `file_paths` | 下载的文件相对路径 |
| `publish_timestamp` | 发布时间戳（可选） |
| `recorded_at` | 清单记录时间 |

**使用场景**：
- 下载记录追溯（即使数据库被删除）
- 跨设备/环境同步下载历史
- 标签/标题快速检索
- 文件完整性验证

**注意**：仅记录下载成功的作品，下载失败的作品记录在 `data/failed_videos/` 目录。

## 运行时数据目录 🍴

> ⚠️ **安全提醒**：`data/` 目录包含日志和数据库，可能记录视频链接和下载历史，已加入 `.gitignore`，**切勿提交到版本控制**。

### data/ 目录 🍴

```text
data/
├── error_logs/              # 详细错误日志（按执行时间分文件）🍴
│   ├── error_20260703_074804.log
│   └── ...
├── failed_videos/           # 下载失败视频记录（按日期分文件）🍴
│   ├── failed_20260701.json
│   └── ...
├── logs/                    # 运行日志和下载报告（按日期分文件）🍴
│   ├── douyin_downloader_20260701.log
│   ├── download_20260703_102631.txt      # 下载执行结果报告 🍴
│   └── ...
├── chrome_user_data/        # Chrome 用户数据目录（浏览器登录状态）🍴
├── scan_records.json        # 增量更新扫描记录（last_video_time）🍴
├── scan_records.json.bak    # 扫描记录备份 🍴
└── db_backup/               # 数据库备份（按时间分文件夹）🍴
    └── 20260702_1947/
        └── dy_downloader.db
```

### scan_records.json 字段说明 🍴

用于记录用户主页下载的扫描状态，支持增量更新和智能跳过：

| 字段 | 类型 | 说明 |
|------|------|------|
| `username` | string | 用户名 |
| `sec_uid` | string | 用户唯一标识 |
| `total` | int | 视频总数 |
| `success` | int | 成功下载数 |
| `failed` | int | 失败数 |
| `skipped` | int | 跳过数（已存在于数据库） |
| `parse_failed` | bool | URL解析是否失败（失败则不跳过，下次重试） |
| `last_scan_time` | string | 上次扫描时间（用于智能跳过判断） |
| `last_video_time` | string | 最新视频时间（用于增量更新） |

> **智能跳过逻辑**：4小时内已成功处理的用户主页会自动跳过，`parse_failed=true` 或 `failed>0` 的记录不会跳过。

### 下载报告 🍴

每次下载任务执行完成后，会自动生成下载执行结果报告，保存到 `data/logs/download_YYYYMMDD_HHMMSS.txt`。

**报告内容**：
- **目标目录**：下载文件保存路径
- **用户主页下载**：按用户分组显示下载明细（作者名、总数、跳过、成功、失败）
- **单视频链接下载**：按链接显示下载结果（链接、作者、状态、成功/失败视频列表）
- **解析失败链接**：无法解析的 URL 列表
- **智能跳过用户**：因跳过阈值限制被跳过的用户（仅用户主页下载）
- **总计统计**：各类下载的汇总数据
- **失败原因分类**：按错误类型统计（HTTP 404、HTTP 403、获取详情失败等）

**报告输出示例**：
```text
============================================================
  抖音下载 · 执行结果报告
============================================================
  目标目录:    ./Downloaded/

============================================================
【用户主页下载】（链接数：2）
============================================================

  1，用户名[sec_uid]/10/2/7/1
    成功下载视频 (7 个):
      - https://www.douyin.com/video/xxx | 标题... | 文件名.mp4
    下载失败视频 (1 个):
      - https://www.douyin.com/video/xxx | Download failed: HTTP 404

============================================================
【单视频链接下载】（链接数：5）
============================================================

  1，https://www.douyin.com/video/xxx
      作者: xxx
      状态: 总数 1 / 跳过 0 / 成功 1 / 失败 0
      成功下载:
        - https://www.douyin.com/video/xxx | 标题...

============================================================
【解析失败链接】（链接数：1）
============================================================
  1. https://xxx

============================================================
【总计统计】
============================================================
  用户主页下载:
      待下载: 10 个
      成功:   7 个
      跳过:   2 个
      失败:   1 个

  单视频链接下载:
      待下载: 5 个
      成功:   4 个
      跳过:   0 个
      失败:   1 个

  合计:
      待下载: 15 个
      成功:   11 个
      跳过:   2 个
      失败:   2 个

============================================================
【失败原因分类】
============================================================
  HTTP 404 - 资源未找到: 1 个
  HTTP 403 - 访问被拒绝: 1 个

  提示：HTTP 404/403 可能因视频源不可用、CDN资源过期或删除、地域限制、权限限制或临时网络问题导致
============================================================
```

### 数据库文件 🍴

项目根目录下的 `dy_downloader.db` 是 SQLite 数据库文件，用于记录下载历史和去重。

**aweme 表结构**（🍴 Fork 版本扩展）：

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| aweme_id | TEXT | 视频ID（唯一索引） |
| aweme_type | TEXT | 视频类型（video/note） |
| title | TEXT | 视频标题 |
| author_id | TEXT | 作者ID |
| author_name | TEXT | 作者名 |
| create_time | INTEGER | 视频发布时间戳 |
| download_time | INTEGER | 入库时间戳 🍴 |
| file_path | TEXT | 文件路径 |
| metadata | TEXT | 元数据JSON |
| **status** | TEXT | **下载状态：`downloaded`（真实下载）/ `skipped`（手动跳过）** 🍴 |

**去重逻辑**：下载前检查 `aweme_id` 是否存在于数据库中，存在则跳过。

**区分下载状态**：通过 `status` 字段区分视频是真实下载成功（`downloaded`）还是手动标记跳过（`skipped`），便于后续统计和排查。

## 常见问题

### 1) 只能抓到 20 条作品怎么办？

这是翻页风控的常见现象。批量下载过程中如果遇到分页受限，系统会跳过该用户并记录到下载日志中。需要手动使用浏览器扫描补充：

```bash
# 扫描用户主页，获取完整视频列表
.\scripts\douyin.ps1 -Action fetch-links -Url https://www.douyin.com/user/MS4wLjABAAAAxxxx
```

### 2) 进度条出现重复刷屏怎么办？

默认 `progress.quiet_logs: true` 会在进度阶段静默日志。  
调试时再临时加 `--show-warnings` 或 `-v`。

### 3) Cookie 失效怎么办？

按以下步骤操作：

```bash
# 1. 检查浏览器登录状态（确保已登录）
.\scripts\douyin.ps1 -Action verify-login

# 2. 刷新 Cookie（从浏览器提取最新 Cookie）
.\scripts\douyin.ps1 -Action refresh-cookies
```

下载前系统会自动检测 Cookie 有效性，如果 Cookie 不完整会提示上述步骤。

### 4) 为什么没有生成 transcript 文件？

请依次检查：

- `transcript.enabled` 是否为 `true`
- 是否下载的是视频（图文不转写）
- `OPENAI_API_KEY`（或 `transcript.api_key`）是否有效
- `response_formats` 是否包含 `txt` 或 `json`

---

## 🍴 Fork 版本扩展功能

> 以下是本 fork 版本在原项目基础上新增/修改的功能，上游版本可能不具备。

### 1. 增量更新机制（改进版）🍴

与上游不同，本 fork 版本的增量更新基于 `last_video_time`（实际视频发布时间），而非 `start_time` / `end_time`：

- 记录文件：`data/scan_records.json`
- 仅用户主页链接（`/user/{sec_uid}`）会记录扫描时间
- 单视频/图文链接不写入扫描记录，不影响增量更新
- 删除 `scan_records.json` 可重新开始全量下载
- 可手动修改 `last_video_time` 字段调整增量更新起始时间

**下载跳过逻辑流程：**

```
开始处理 URL
    ↓
┌─────────────────────────────────────────────────────┐
│ 阶段1: URL级别跳过（skip_threshold_hours）          │
│                                                     │
│ 满足以下所有条件才会跳过整个URL：                    │
│ ├─ skip_threshold_hours > 0（默认4小时）            │
│ ├─ 存在扫描记录（data/scan_records.json）           │
│ ├─ 上次扫描时间在阈值内（< 当前时间 - N小时）        │
│ ├─ sec_uid 完整                                    │
│ ├─ failed == 0（无失败记录）                        │
│ └─ parse_failed == False（解析未失败）             │
│                                                     │
│ 任一条件不满足 → 继续处理                           │
│ 全部条件满足 → 跳过整个URL，标记为 skipped          │
└─────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────┐
│ 阶段2: 用户作品列表过滤（仅用户主页）               │
│                                                     │
│ ├─ 增量更新过滤：根据 last_video_time 只保留         │
│    比上次最新视频更新的内容                         │
│ ├─ 数量限制过滤：根据 number.post 截取前N个视频     │
│ └─ 若所有视频都早于过滤时间，停止分页               │
└─────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────┐
│ 阶段3: 单个视频去重（数据库检查）                   │
│                                                     │
│ 查询数据库 aweme 表：                                │
│ SELECT id FROM aweme WHERE aweme_id = ?            │
│                                                     │
│ ├─ 已存在 → 跳过该视频，标记为 skipped              │
│ └─ 不存在 → 继续下载                               │
└─────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────┐
│ 阶段4: 辅助资源下载控制                             │
│                                                     │
│ 根据配置独立控制：                                   │
│ ├─ music: false → 跳过音乐下载                     │
│ ├─ cover: false → 跳过封面下载                     │
│ ├─ avatar: false → 跳过头像下载                    │
│ └─ json: false → 跳过元数据JSON文件下载            │
└─────────────────────────────────────────────────────┘
```

**跳过阈值（`skip_threshold_hours`）：**

控制短时间内重复扫描的行为，默认值 4 小时（代码默认，可在配置文件中覆盖）：

```yaml
# config.yml（可选，不写则默认 4 小时）
skip_threshold_hours: 4
```

| 参数值 | 行为 |
|--------|------|
| `4`（默认） | 4小时内已成功处理的用户将被跳过 |
| `0` | 不跳过任何用户，每次都执行下载 |
| 空值 | 不跳过任何用户，每次都执行下载 |

> **注意**：此参数控制的是"用户级别的跳过"（阶段1），与增量更新的 `last_video_time`（阶段2）不同。即使跳过了用户，也不会影响 `scan_records.json` 中的时间记录。

> **设计用途**：此配置主要为**定时任务**场景设计。当使用定时任务（如 Windows 计划任务、Linux cron）自动执行下载时，如果每次都扫描所有用户会导致资源占用过高。设置跳过阈值后，定时任务会智能跳过近期已处理的用户，只处理新的或长时间未更新的用户，降低系统负担。目前项目暂未集成定时任务功能，手动执行时此配置影响有限。

**为什么下载不到新视频？**

1. **阶段1 - `skip_threshold_hours` 限制**：用户在短时间内已处理过，被跳过了 → 设置为空或 `0`
2. **阶段2 - `last_video_time` 已更新**：上次扫描时已记录最新视频时间 → 等待新视频发布，或手动调整 `last_video_time`
3. **阶段3 - 数据库去重**：视频已在数据库中标记为已下载 → 使用 `--mark-skipped` 标记跳过，或删除数据库记录

### 2. 失败视频管理与重试 🍴

下载失败的视频（包括用户主页批量下载和单视频链接下载）会自动记录到 `data/failed_videos/` 目录，支持查看和重试：

```bash
# 列出所有未处理的失败视频
python run.py --list-failed

# 重试所有失败视频
python run.py --retry-failed -c config.yml

# 将指定视频标记为跳过（写入数据库，后续下载自动跳过）
python run.py --mark-skipped <aweme_id>
```

### 3. PowerShell 启动脚本（推荐 Windows 用户使用）🍴

提供 `scripts/douyin.ps1` 统一入口脚本，支持所有操作模式：

```bash
# 查看帮助
.\scripts\douyin.ps1 -Action help

# 下载（默认）
.\scripts\douyin.ps1

# 指定配置文件
.\scripts\douyin.ps1 -ConfigFile config_temp.yml

# 追加下载链接
.\scripts\douyin.ps1 -Url https://v.douyin.com/xxx/

# 指定线程数和下载路径
.\scripts\douyin.ps1 -Thread 8 -Path ./Downloaded

# 列出失败视频
.\scripts\douyin.ps1 -Action list-failed

# 重试失败视频
.\scripts\douyin.ps1 -Action retry-failed

# 备份数据库（重要操作前建议执行）
.\scripts\douyin.ps1 -Action backup-db

# 人工确认浏览器登录状态（打开浏览器检查是否已登录，不修改配置）
.\scripts\douyin.ps1 -Action verify-login

# 批量标记所有失败视频为跳过（执行前会自动备份数据库到 data/db_backup/）
.\scripts\douyin.ps1 -Action mark-all-failed-skipped

# 单个标记视频为跳过
.\scripts\douyin.ps1 -Action mark-skipped -MarkAwemeId 7656278130479029862
```

**脚本优势**：
- 自动检查配置文件是否存在
- 自动创建下载目录（如果不存在）
- 验证下载目录写入权限
- 自动设置 UTF-8 编码，避免中文乱码
- 自动解析相对路径为绝对路径

**日常使用流程** 🍴：

```bash
# 1. 备份数据库（可选但推荐）
.\scripts\douyin.ps1 -Action backup-db

# 2. 检查浏览器登录状态（首次使用或登录过期时执行）
.\scripts\douyin.ps1 -Action verify-login

# 3. 刷新 Cookie（首次使用或登录过期时执行）
.\scripts\douyin.ps1 -Action refresh-cookies

# 4. 执行下载（下载前会自动检测 Cookie 有效性）
.\scripts\douyin.ps1

# 5. 重试失败链接
.\scripts\douyin.ps1 -Action retry-failed

# 6. 批量标记无法下载的视频为跳过（人工确认后）
.\scripts\douyin.ps1 -Action mark-all-failed-skipped

# 7. 提取收藏视频或用户主页链接到临时配置
#    无参数：扫描收藏页面
.\scripts\douyin.ps1 -Action fetch-links
#    带参数：扫描指定用户主页
#    .\scripts\douyin.ps1 -Action fetch-links -Url https://www.douyin.com/user/MS4wLjABAAAAxxxx

# 8. 下载临时配置中的链接
.\scripts\douyin.ps1 -ConfigFile config_temp.yml
```

### 4. 数据库备份 🍴

提供 `backup-db` 命令，一键备份 `dy_downloader.db` 到 `data/db_backup/` 目录：

```bash
# 通过 PowerShell 脚本
.\scripts\douyin.ps1 -Action backup-db
```

每次备份生成独立的 `YYYYMMDD_HHMMSS` 时间戳目录，不会覆盖已有备份。建议在执行 `--mark-all-failed-skipped`、删除数据库记录等危险操作前手动备份。

### 5. 详细错误日志 🍴

下载失败时自动写入详细错误日志到 `data/error_logs/` 目录，每次执行生成一个 `.log` 文件（如 `error_20260703_074804.log`），包含：

- 作品 ID、错误类型、错误信息、发生时间
- 作品摘要信息（描述、作者、图片/视频数量、URL 特征等）
- 附加上下文信息（来源模块、失败原因等）
- 异常堆栈（如有）

覆盖的失败场景包括：视频无可播放 URL、图片下载失败、API 获取详情失败、用户作品列表获取失败、重试失败等。执行结束后如有错误，终端会提示日志文件路径。

#### HTTP 404/403 错误处理

当错误日志中出现 `HTTP 404` 或 `HTTP 403` 时，可能的原因包括：

- **CDN 资源过期或删除**：商业推广视频等资源生命周期较短，投放周期结束后可能被清理
- **会员视频**：视频内容需要抖音会员才能观看，普通账号无法获取播放地址
- **视频已删除**：作者已删除该作品
- **私密视频**：作者将作品设为私密，仅自己可见
- **CDN 临时故障**：抖音 CDN 节点临时不可用，稍后可能恢复
- **地域限制**：部分视频在特定地区不可访问
- **权限限制**：部分视频设置了访问权限，需要登录或特定账号才能观看

处理建议：

1. **人工确认**：将日志中的视频链接复制到浏览器中验证，确认视频是否确实无法访问
2. **批量标记为跳过**：确认所有失败链接都无法下载后，执行以下命令批量标记为已处理
   ```powershell
   # 批量标记所有失败视频为跳过（执行前会自动备份数据库到 data/db_backup/）
   .\scripts\douyin.ps1 -Action mark-all-failed-skipped
   ```
   该命令会将 `data/failed_videos/*.json` 中所有 `status` 为 `"failed"` 的条目标记为 `"skipped"`，并在数据库中对应记录的 `status` 设为 `"skipped"`，下次执行下载任务时会自动跳过这些记录

### 6. 图文作品下载修正 🍴

修复了图文作品（图集）下载的多个问题：

- **媒体类型检测**：优化 `_detect_media_type` 逻辑，当图片数量 ≤1 且存在视频时优先按视频处理，避免图文作品被误判
- **API 数据补全**：`get_video_detail` 在 aid=1128 返回数据不完整时自动用 aid=6383 重试，确保 `image_post_info` 数据完整
- **图片 URL 容错**：图集下载支持多候选 URL 轮换，某个 URL 下载失败立即尝试下一个，不做无意义重试，5 张图下载从 60+ 秒优化到约 5 秒

### 7. 文件命名调整 🍴

本 fork 版本对下载目录和文件命名做了以下调整：

- **不再拼接 aweme_id**：上游版本的目录名和文件名格式为 `{日期}_{标题}_{aweme_id}`，本 fork 去掉了末尾的 aweme_id，改为 `{日期}_{标题}`
- **原因**：aweme_id 是 19 位数字，拼接后目录名和文件名都会偏长，部分标题较长的作品在 Windows 下会触发 260 字符路径长度限制导致下载失败
- **标题截断**：标题超过 60 字符时自动截断（上游为 80），进一步避免路径过长
- **文件夹重复处理**：当两个作品日期和标题完全相同时，会自动在文件夹名末尾递增数字区分，如 `2025-09-14_标题`、`2025-09-14_标题_1`、`2025-09-14_标题_2`...
- **不影响去重**：aweme_id 仍记录在数据库和 `_data.json` 元数据中，去重逻辑不受影响
- **上游已有目录**：从上游升级的用户会注意到新下载的目录名不再带 aweme_id 后缀，已有目录不受影响

### 8. 数据库改动说明 🍴

- **status 字段**：`aweme` 表新增 `status` 字段（默认 `downloaded`），区分真实下载和手动跳过
- **download_time 字段**：插入记录时正确写入当前时间戳
- **去重逻辑**：下载前检查 `aweme_id` 是否存在，存在则跳过，不再重复下载
- **跳过标记**：`--mark-skipped` 和 `--mark-all-failed-skipped` 会将 `status` 设为 `skipped`，保留记录但不重复下载

### 9. URL 间随机延迟 🍴

在每个 URL 处理之间添加随机延迟，降低被限流风险：

```yaml
url_delay:
  enabled: true       # 是否启用
  min_seconds: 2       # 最小延迟秒数
  max_seconds: 5       # 最大延迟秒数
```

### 10. 数据库文件 🍴

本 fork 版本使用的数据库文件为项目根目录下的 `dy_downloader.db`。

### 11. 人工检查登录状态 🍴

建议在执行下载任务前，手动检查浏览器登录状态：

```powershell
.\scripts\douyin.ps1 -Action verify-login
```

此命令会打开浏览器，由人工确认是否已登录。浏览器用户数据目录为项目内的 `data/chrome_user_data`，而非系统默认目录。

**`data/chrome_user_data` 目录的重要性**：

这个目录是整个项目浏览器相关功能的核心，以下三个功能共享同一登录状态：

| 功能 | 命令 | 作用 |
|------|------|------|
| 登录验证 | `verify-login` | 打开浏览器，人工确认是否已登录 |
| Cookie 刷新 | `refresh-cookies` | 从 chrome_user_data 提取登录 Cookie，写入 `config.yml` |
| 链接提取 | `fetch-links` | 从浏览器获取收藏视频或用户主页链接 |

**工作流程**：

1. **首次登录**：执行 `verify-login`，浏览器打开后扫码登录，登录状态保存到 `data/chrome_user_data`
2. **提取 Cookie**：执行 `refresh-cookies`，脚本读取 `data/chrome_user_data` 中的登录状态，自动提取 Cookie 并写入 `config.yml`
3. **提取链接**：执行 `fetch-links`，脚本读取 `data/chrome_user_data` 中的登录状态，无需重新登录即可访问收藏页面或用户主页

> **重要提示**：只需登录一次，三个功能都可以共享这个登录状态。如果删除 `data/chrome_user_data` 目录，需要重新登录。

**为什么使用项目内的用户数据目录**：

- **远程调试限制**：Chrome 默认用户数据目录不允许远程调试（DevTools remote debugging），Playwright 无法正常启动
- **环境隔离**：与系统默认 Chrome 浏览器的登录状态相互独立，不会影响系统浏览器的账号
- **数据安全**：登录状态保存在项目目录内，便于管理和备份

### 12. 提取链接（收藏/用户主页）🍴

通过浏览器方式获取收藏视频或用户主页链接：

```bash
# 1. 获取收藏视频链接（无参数，写入 config_temp.yml）
.\scripts\douyin.ps1 -Action fetch-links

# 2. 获取指定用户主页链接（带 -Url 参数）
.\scripts\douyin.ps1 -Action fetch-links -Url https://www.douyin.com/user/MS4wLjABAAAAxxxx

# 3. 下载提取的链接
.\scripts\douyin.ps1 -ConfigFile config_temp.yml
```

**操作流程**：
1. 执行 `fetch-links` 后，浏览器会打开抖音收藏页面（无参数）或指定用户主页（带参数）
2. 脚本等待页面加载完成（收藏页会校验 URL 已切换到 `showTab=favorite_collection`）
3. 手动滚动到页面底部，加载所有需要采集的内容
4. 滚动完成后按 Enter 键，脚本从上往下一次性扫描并采集所有已加载的视频链接
5. 采集结果写入 `config_temp.yml`，使用 `download` 命令下载

**去重机制**：
- 自动跳过数据库中已下载/跳过的视频
- 自动跳过 `config_temp.yml` 中已有的链接
- 同一页面内重复出现的链接自动去重

**注意事项**：
- 需确保已登录抖音账号（登录状态保存在 `data/chrome_user_data`）
- 收藏页采集使用精确容器选择器 `div[data-e2e="user-favorite-list"]`，用户主页采集使用 `div[data-e2e="user-post-list"]`，只采集目标区域视频，不会误捕推荐页内容
- 滚动越到底部，收集的视频越完整
- 每次只扫描一个用户主页（通过 `-Url` 参数指定）

> **注意**：下载任务（`download`、`retry-failed`）不再自动检查登录状态，需用户手动确认。

---

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

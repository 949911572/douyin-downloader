# 抖音下载器 V2.1（Douyin Downloader）

<!-- 项目元数据（AI 易读） -->
<!--
meta:
  name: douyin-downloader
  version: 2.1.0
  upstream: jiji262/douyin-downloader
  fork_from: pengkunhy/douyin-downloader
  language: Python 3.8+
  database: SQLite (dy_downloader.db)
  browser: Playwright Chromium
  entry_point: run.py
  ps1_entry: scripts/douyin.ps1
  config_file: config.yml
  config_template: config.example.yml
  is_fork: true
-->

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

## 目录

- [功能概览](#功能概览)
- [快速开始](#快速开始)
- [核心术语表](#核心术语表)
- [项目架构](#项目架构)
- [最小可用配置](#最小可用配置)
- [使用方式](#使用方式)
- [典型场景](#典型场景)
- [辅助脚本说明](#辅助脚本说明)
- [可选功能：视频转写（transcript）](#可选功能视频转写transcript)
- [配置项完整参考](#配置项完整参考)
- [输出目录](#输出目录)
- [运行时数据目录](#运行时数据目录-🍴)
- [数据结构参考](#数据结构参考)
- [常见问题](#常见问题)
- [Fork 版本扩展功能](#-fork-版本扩展功能)

## 核心术语表

| 术语 | 类型 | 说明 |
|------|------|------|
| `aweme_id` | string | 抖音作品唯一标识（视频/图文通用），19位数字 |
| `sec_uid` | string | 抖音用户加密 UID，用户主页 URL 中的唯一标识 |
| `msToken` | string | 抖音请求签名所需 token，从页面源码或 Cookie 中获取 |
| `ttwid` | string | 抖音 Cookie 关键字段，用于标识访客/会话 |
| `odin_tt` | string | 抖音 Cookie 关键字段，设备/安装标识 |
| `passport_csrf_token` | string | 抖音登录态 CSRF 令牌 |
| `sid_guard` | string | 会话标识 Cookie，推荐填写以增强稳定性 |
| `a_bogus` / `x_bogus` | string | 抖音反爬签名参数，代码自动生成 |
| `scan_records.json` | file | 增量更新扫描记录文件，保存用户上次扫描时间和最新视频时间 |
| `dy_downloader.db` | file | SQLite 数据库文件，记录下载历史用于去重 |

## 项目架构

### 模块划分

| 层级 | 目录/文件 | 核心职责 | 关键文件 |
|------|----------|---------|---------|
| 入口层 | `run.py`, `cli/` | 命令行解析、启动流程、进度展示 | `cli/main.py`, `cli/progress_display.py` |
| 核心下载层 | `core/` | 下载器、API 客户端、URL 解析、转写管理 | `core/downloader_base.py`, `core/user_downloader.py`, `core/video_downloader.py`, `core/api_client.py` |
| 认证层 | `auth/` | Cookie 管理、msToken 管理 | `auth/cookie_manager.py`, `auth/ms_token_manager.py` |
| 配置层 | `config/` | 配置加载、默认配置 | `config/config_loader.py`, `config/default_config.py` |
| 存储层 | `storage/` | 数据库、文件管理、元数据处理 | `storage/database.py`, `storage/file_manager.py`, `storage/metadata_handler.py` |
| 控制层 | `control/` | 队列、重试、限流 | `control/queue_manager.py`, `control/retry_handler.py`, `control/rate_limiter.py` |
| 工具层 | `utils/` | 浏览器配置、错误日志、扫描记录等 | `utils/browser_config.py`, `utils/error_logger.py`, `utils/scan_record_manager.py`, `utils/failed_video_manager.py` |
| 脚本层 | `scripts/` | PowerShell 入口、辅助脚本 | `scripts/douyin.ps1`, `scripts/verify_login.py`, `scripts/fetch_links.py` |

### 核心类关系

```
run.py → cli/main.py
    ↓
DownloaderFactory → 根据 URL 类型创建下载器
    ├─ UserDownloader    (用户主页批量下载)
    └─ VideoDownloader   (单视频/图文下载)
    ↓  继承
DownloaderBase (下载逻辑基类)
    ├─ ApiClient         (抖音 API 请求)
    ├─ Database          (SQLite 去重与记录)
    ├─ RetryHandler      (重试控制)
    ├─ RateLimiter       (请求限流)
    └─ ErrorLogger       (错误日志)
```

### 数据流向

1. 读取 `config.yml` → 解析配置
2. 解析 `link` 中的 URL → 调用 `DownloaderFactory`
3. 用户主页 → `UserDownloader` → 调用 API 获取作品列表 → 逐个下载
4. 单视频 → `VideoDownloader` → 调用 API 获取详情 → 下载
5. 下载结果 → 写入 `dy_downloader.db` + `data/logs/` + `data/failed_videos/`
6. 增量更新信息 → 写入 `data/scan_records.json`

## 功能概览

### 已支持功能

| 功能 | 说明 | Fork扩展 |
|------|------|---------|
| 单个视频下载 | `/video/{aweme_id}` | ❌ |
| 单个图文下载 | `/note/{note_id}` | ❌ |
| 短链自动解析 | `https://v.douyin.com/...` | ❌ |
| 用户主页批量下载 | `/user/{sec_uid}` + `mode: [post]` | ❌ |
| 无水印优先下载 | 默认下载无水印版本 | ❌ |
| 辅助资源下载 | 封面/音乐/头像/JSON 元数据 | ❌ |
| 图文作品下载 | 图集下载，多候选 URL 轮换容错 | ✅ |
| 视频转写 | `transcript`，调用 OpenAI API | ❌ |
| 并发下载 | 多线程下载支持 | ❌ |
| 失败重试 | 自动重试失败任务 | ❌ |
| 速率限制 | 请求间隔控制 | ✅ |
| SQLite 去重 | 基于 `aweme_id` 去重 | ❌ |
| 增量下载 | 基于 `scan_records.json` | ✅ |
| 进度条展示 | 支持静默模式 | ❌ |
| 详细错误日志 | 下载失败自动记录 | ✅ |
| 数据库备份 | 一键备份功能 | ✅ |

### 暂未接入功能（请勿按已支持使用）

| 功能 | 说明 |
|------|------|
| `mode: like` | 点赞下载（未实现） |
| `mode: mix` | 合集下载（未实现） |
| `number.like` / `number.mix` | 点赞/合集数量限制（未实现） |
| `collection/mix` 链接 | 当前无对应下载器，会提示不支持 |

## 快速开始

### 步骤 1：环境准备

| 项目 | 要求 |
|------|------|
| Python 版本 | 3.8+ |
| 操作系统 | macOS / Linux / Windows |

### 步骤 2：安装依赖

```powershell
pip install -r requirements.txt
```

### 步骤 3：安装浏览器（Playwright 需要）

```powershell
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

### 步骤 4：复制配置

```powershell
# Windows
copy config.example.yml config.yml

# macOS / Linux
cp config.example.yml config.yml
```

### 步骤 5：获取 Cookie（推荐自动方式）

```powershell
.\scripts\douyin.ps1 -Action refresh-cookies
```

**步骤说明**：

| 步骤 | 操作 |
|------|------|
| 1 | 脚本打开 Playwright Chromium 浏览器 |
| 2 | 自动检查 `data/chrome_user_data/` 中的登录状态 |
| 3 | 如果已登录，从浏览器 Cookie 数据库中提取所需的 Cookie |
| 4 | 将提取的 Cookie 自动写入 `config.yml` |

> **注意**：如果 `chrome_user_data` 数据不完整（缺少必要的登录 Cookie），脚本会提示用户先执行 `.\scripts\douyin.ps1 -Action verify-login` 登录。

#### 手动获取 Cookie（备用方式）

如果自动方式失败，可以手动获取：

1. 打开浏览器访问 `https://www.douyin.com`
2. 登录账号
3. 打开开发者工具（F12）→ Application → Cookies → `https://www.douyin.com`
4. 复制以下字段的值到 `config.yml` 的 `cookies` 部分：
   - `ttwid`
   - `odin_tt`
   - `passport_csrf_token`
   - `sid_guard`（会话标识，推荐填写）
   - `msToken`（可在页面源码中搜索）

> **注意**：Cookie 包含账号敏感信息，请勿泄露。

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

increase:
  post: true

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

```powershell
# 使用默认配置
python run.py

# 指定配置文件
python run.py -c config.yml
```

### 方式二：命令行追加参数

```powershell
python run.py -c config.yml `
  -u "https://www.douyin.com/video/7604129988555574538" `
  -t 8 \
  -p ./Downloaded
```

### 命令行参数参考

#### 基础参数

| 参数 | 短选项 | 类型 | 默认值 | 说明 | Fork专属 |
|------|--------|------|--------|------|---------|
| `--url` | `-u` | string（可重复） | - | 追加下载链接，可多次传入 | ❌ |
| `--config` | `-c` | string | `config.yml` | 指定配置文件路径 | ❌ |
| `--path` | `-p` | string | - | 指定下载目录 | ❌ |
| `--thread` | `-t` | int | - | 指定并发数 | ❌ |
| `--show-warnings` | - | bool | `false` | 显示 warning/error 日志 | ❌ |
| `--verbose` | `-v` | bool | `false` | 显示 info/warning/error 日志 | ❌ |

#### 失败视频管理 🍴

| 参数 | 类型 | 说明 | Fork专属 |
|------|------|------|---------|
| `--list-failed` | bool | 列出所有未处理的失败视频 | ✅ |
| `--retry-failed` | bool | 重试所有失败视频 | ✅ |
| `--mark-skipped` | string | 将指定 aweme_id 标记为跳过（写入数据库） | ✅ |
| `--mark-all-failed-skipped` | bool | 批量标记所有失败视频为跳过（执行前自动备份数据库） | ✅ |

## 典型场景

### 下载方式说明

本项目支持两种下载方式，可根据需求选择：

| 方式 | 说明 | 适用场景 |
|------|------|---------|
| **普通下载** | 直接配置链接到 `link` 字段，脚本自动获取视频信息并下载 | 已知视频/用户链接，批量下载 |
| **浏览器获取下载** | 通过浏览器打开页面，手动滚动加载内容，脚本采集链接后下载 | 需要登录访问（收藏页、私密内容），或分页受限 |

---

### 下载单个视频

**方式一：普通下载（直接配置链接）**

```yaml
link:
  - https://www.douyin.com/video/7604129988555574538
```

**方式二：浏览器获取下载（通过浏览器采集）**

```powershell
# 1. 通过浏览器扫描获取链接（单视频无需浏览器方式）
# 2. 直接下载
.\scripts\douyin.ps1 -Action download -Url "https://www.douyin.com/video/7604129988555574538"
```

### 下载单个图文

**方式一：普通下载（直接配置链接）**

```yaml
link:
  - https://www.douyin.com/note/7341234567890123456
```

### 批量下载作者主页作品

**方式一：普通下载（直接配置链接）**

```yaml
link:
  - https://www.douyin.com/user/MS4wLjABAAAAxxxx
mode:
  - post
number:
  post: 50
```

**方式二：浏览器获取下载（分页受限时使用）**

```powershell
# 1. 通过浏览器扫描用户主页，获取完整视频链接
.\scripts\douyin.ps1 -Action fetch-links -Url https://www.douyin.com/user/MS4wLjABAAAAxxxx

# 2. 下载采集到的链接
.\scripts\douyin.ps1 -ConfigFile config_temp.yml
```

### 下载个人收藏视频

**方式：浏览器获取下载（收藏页需要登录访问）**

```powershell
# 1. 通过浏览器扫描收藏页面，获取收藏视频链接
.\scripts\douyin.ps1 -Action fetch-links

# 2. 下载采集到的链接
.\scripts\douyin.ps1 -ConfigFile config_temp.yml
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
| `check_cookies.py` | Python | 检查配置文件中 Cookie 字段是否完整 🍴 |
| `_refresh_cookies.py` | Python | Cookie 刷新核心逻辑（内部脚本，建议通过 douyin.ps1 调用） 🍴 |

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

```powershell
# Windows
$env:OPENAI_API_KEY="sk-xxxx"

# macOS / Linux
export OPENAI_API_KEY="sk-xxxx"
```

### 2) 输出文件

启用后会生成：

- `xxx.transcript.txt`
- `xxx.transcript.json`

若 `database: true`，会在数据库 `transcript_job` 表记录状态（`success/failed/skipped`）。

## 配置项完整参考

> 标注 🍴 为 Fork 版本扩展配置，上游可能不具备。
> 标注 [预留] 为尚未实现的配置项，仅做占位。

### 基础配置

| 配置路径 | 类型 | 默认值 | 说明 | Fork专属 | 状态 |
|---------|------|--------|------|---------|------|
| `link` | list[string] | `[]` | 下载链接列表，支持单视频、图文、用户主页链接 | ❌ | 已实现 |
| `path` | string | `./Downloaded/` | 下载目录，支持相对路径和绝对路径 | ❌ | 已实现 |
| `folderstyle` | bool | `true` | 是否按作者名和日期创建嵌套目录结构 | ❌ | 已实现 |
| `thread` | int | `1` | 并发线程数，建议设置为 1 以降低限流风险 | ❌ | 已实现 |
| `retry_times` | int | `3` | 单个任务重试次数（顶层配置） | ❌ | 已实现 |
| `database` | bool | `true` | 是否启用数据库去重 | ❌ | 已实现 |
| `skip_threshold_hours` | int | `4` | URL 级别跳过阈值，短时间内重复扫描的用户自动跳过 | ✅ | 已实现 |

### 辅助资源下载开关

| 配置路径 | 类型 | 默认值 | 说明 | Fork专属 | 状态 |
|---------|------|--------|------|---------|------|
| `music` | bool | `false` | 是否下载背景音乐 | ❌ | 已实现 |
| `cover` | bool | `false` | 是否下载封面图片 | ❌ | 已实现 |
| `avatar` | bool | `false` | 是否下载作者头像 | ❌ | 已实现 |
| `json` | bool | `false` | 是否下载元数据 JSON 文件 | ❌ | 已实现 |

### 下载模式配置

| 配置路径 | 类型 | 默认值 | 说明 | Fork专属 | 状态 |
|---------|------|--------|------|---------|------|
| `mode` | list[string] | `[post]` | 下载模式，目前仅支持 `post`（用户作品） | ❌ | 部分实现 |
| `mode[].post` | - | - | 用户作品下载 | ❌ | 已实现 |
| `mode[].like` | - | - | 点赞下载 | ❌ | [预留] 未实现 |
| `mode[].mix` | - | - | 合集下载 | ❌ | [预留] 未实现 |
| `mode[].allmix` | - | - | 全部合集 | ❌ | [预留] 未实现 |
| `mode[].music` | - | - | 音乐作品 | ❌ | [预留] 未实现 |

### 数量限制配置

| 配置路径 | 类型 | 默认值 | 说明 | Fork专属 | 状态 |
|---------|------|--------|------|---------|------|
| `number.post` | int | `0` | 用户作品数量限制，0 表示不限制 | ❌ | 已实现 |
| `number.like` | int | `0` | 点赞作品数量限制 | ❌ | [预留] 未实现 |
| `number.allmix` | int | `0` | 合集数量限制 | ❌ | [预留] 未实现 |
| `number.mix` | int | `0` | 单个合集下载数量限制 | ❌ | [预留] 未实现 |
| `number.music` | int | `0` | 音乐作品数量限制 | ❌ | [预留] 未实现 |

### 增量更新配置 🍴

| 配置路径 | 类型 | 默认值 | 说明 | Fork专属 | 状态 |
|---------|------|--------|------|---------|------|
| `increase.post` | bool | `true` | 用户作品增量更新，基于 `last_video_time` 只下载更新的内容 | ✅ | 已实现 |
| `increase.like` | bool | `false` | 点赞作品增量更新 | ❌ | [预留] 未实现 |
| `increase.allmix` | bool | `false` | 合集增量更新 | ❌ | [预留] 未实现 |
| `increase.mix` | bool | `false` | 单个合集增量更新 | ❌ | [预留] 未实现 |
| `increase.music` | bool | `false` | 音乐作品增量更新 | ❌ | [预留] 未实现 |

### 重试配置

| 配置路径 | 类型 | 默认值 | 说明 | Fork专属 | 状态 |
|---------|------|--------|------|---------|------|
| `retry.max_retries` | int | `3` | 最大重试次数 | ❌ | 已实现 |
| `retry.delay` | int | `5` | 重试间隔（秒） | ❌ | 已实现 |

### 进度显示配置

| 配置路径 | 类型 | 默认值 | 说明 | Fork专属 | 状态 |
|---------|------|--------|------|---------|------|
| `progress.quiet_logs` | bool | `true` | 是否启用静默模式，减少进度阶段的日志输出 | ❌ | 已实现 |

### 视频转写配置

| 配置路径 | 类型 | 默认值 | 说明 | Fork专属 | 状态 |
|---------|------|--------|------|---------|------|
| `transcript.enabled` | bool | `false` | 是否启用视频转写 | ❌ | 已实现 |
| `transcript.model` | string | `gpt-4o-mini-transcribe` | 转写模型 | ❌ | 已实现 |
| `transcript.output_dir` | string | `""` | 输出目录，留空则与视频同目录 | ❌ | 已实现 |
| `transcript.response_formats` | list[string] | `[txt, json]` | 输出格式 | ❌ | 已实现 |
| `transcript.api_url` | string | `https://api.openai.com/v1/audio/transcriptions` | API 地址 | ❌ | 已实现 |
| `transcript.api_key_env` | string | `OPENAI_API_KEY` | API Key 环境变量名 | ❌ | 已实现 |
| `transcript.api_key` | string | `""` | API Key（不推荐硬编码，使用环境变量） | ❌ | 已实现 |

### 浏览器兜底配置 🍴

| 配置路径 | 类型 | 默认值 | 说明 | Fork专属 | 状态 |
|---------|------|--------|------|---------|------|
| `browser_fallback.enabled` | bool | `true` | 是否启用浏览器兜底（API 获取失败时用浏览器方式获取） | ✅ | 已实现 |
| `browser_fallback.headless` | bool | `false` | 是否无头模式，false 显示浏览器窗口便于排错 | ✅ | 已实现 |
| `browser_fallback.max_scrolls` | int | `240` | 最大滚动次数 | ✅ | 已实现 |
| `browser_fallback.idle_rounds` | int | `8` | 空闲检测轮数 | ✅ | 已实现 |
| `browser_fallback.wait_timeout_seconds` | int | `600` | 等待超时时间（秒） | ✅ | 已实现 |

### 请求限流配置 🍴

| 配置路径 | 类型 | 默认值 | 说明 | Fork专属 | 状态 |
|---------|------|--------|------|---------|------|
| `url_delay.enabled` | bool | `true` | 是否启用 URL 间随机延迟 | ✅ | 已实现 |
| `url_delay.min_seconds` | int | `2` | 最小延迟秒数 | ✅ | 已实现 |
| `url_delay.max_seconds` | int | `5` | 最大延迟秒数 | ✅ | 已实现 |

### Cookie 配置

| 配置路径 | 类型 | 默认值 | 说明 | Fork专属 | 状态 |
|---------|------|--------|------|---------|------|
| `cookies.msToken` | string | `""` | msToken | ❌ | 已实现 |
| `cookies.ttwid` | string | `""` | ttwid（必需） | ❌ | 已实现 |
| `cookies.odin_tt` | string | `""` | odin_tt（必需） | ❌ | 已实现 |
| `cookies.passport_csrf_token` | string | `""` | passport_csrf_token（必需） | ❌ | 已实现 |
| `cookies.sid_guard` | string | `""` | sid_guard（推荐填写，增强稳定性） | ❌ | 已实现 |

## 输出目录

默认 `folderstyle: true` 时：

```text
Downloaded/
├── download_manifest.jsonl
└── 作者名/
    └── post/
        └── 2024-02-07_作品标题/
            ├── ...mp4
            ├── ..._cover.jpg
            ├── ..._music.mp3
            ├── ..._data.json
            ├── ..._avatar.jpg
            ├── ...transcript.txt      # transcript.enabled=true 且格式包含 txt
            └── ...transcript.json     # transcript.enabled=true 且格式包含 json
```

> 🍴 **Fork 说明**：目录名格式为 `{日期}_{标题}`，不再拼接 aweme_id，避免 Windows 路径长度限制。aweme_id 仍记录在数据库和 `_data.json` 元数据中，不影响去重。

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

**报告包含以下部分**：

| 部分 | 说明 |
|------|------|
| 目标目录 | 下载文件保存路径 |
| 用户主页下载 | 按用户分组显示下载明细（作者名、总数、跳过、成功、失败） |
| 单视频链接下载 | 按链接显示下载结果（链接、作者、状态、成功/失败视频列表） |
| 解析失败链接 | 无法解析的 URL 列表 |
| 智能跳过用户 | 因跳过阈值限制被跳过的用户（仅用户主页下载） |
| 总计统计 | 各类下载的汇总数据 |
| 失败原因分类 | 按错误类型统计（HTTP 404、HTTP 403、获取详情失败等） |

## 数据结构参考

### 数据库表（dy_downloader.db）🍴

项目根目录下的 `dy_downloader.db` 是 SQLite 数据库文件，用于记录下载历史和去重。

#### aweme 表

| 字段 | 类型 | 说明 | Fork扩展 |
|------|------|------|---------|
| `id` | INTEGER | 主键 | ❌ |
| `aweme_id` | TEXT | 作品ID（唯一索引） | ❌ |
| `aweme_type` | TEXT | 作品类型（video/note） | ❌ |
| `title` | TEXT | 作品标题 | ❌ |
| `author_id` | TEXT | 作者ID | ❌ |
| `author_name` | TEXT | 作者名 | ❌ |
| `create_time` | INTEGER | 作品发布时间戳 | ❌ |
| `download_time` | INTEGER | 入库时间戳 | ✅ |
| `file_path` | TEXT | 文件路径 | ❌ |
| `metadata` | TEXT | 元数据JSON | ❌ |
| `status` | TEXT | 下载状态：`downloaded`（真实下载）/ `skipped`（手动跳过） | ✅ |

**去重逻辑**：下载前检查 `aweme_id` 是否存在，存在则跳过。

#### transcript_job 表

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | INTEGER | 主键 |
| `aweme_id` | TEXT | 作品ID |
| `status` | TEXT | 转写状态：`success` / `failed` / `skipped` |

### scan_records.json 🍴

文件位置：`data/scan_records.json`

用于记录用户主页下载的扫描状态，支持增量更新和智能跳过。

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

**智能跳过逻辑**：4小时内已成功处理的用户主页会自动跳过，`parse_failed=true` 或 `failed>0` 的记录不会跳过。

### failed_videos 🍴

文件位置：`data/failed_videos/failed_YYYYMMDD.json`

按日期存储的下载失败视频记录。

| 字段 | 类型 | 说明 |
|------|------|------|
| `aweme_id` | string | 作品ID |
| `url` | string | 作品URL |
| `title` | string | 作品标题 |
| `author_name` | string | 作者名 |
| `sec_uid` | string | 用户sec_uid |
| `error_message` | string | 失败原因 |
| `failed_time` | string | 失败时间 |
| `status` | string | 状态：`failed` / `skipped` / `processed` |

### download_manifest.jsonl

文件位置：下载根目录下的 `download_manifest.jsonl`

记录每一个成功下载的作品的详细元数据，JSONL 格式（每行一条 JSON，append-only 追加写入）。

| 字段 | 类型 | 说明 |
|------|------|------|
| `date` | string | 作品发布日期 |
| `aweme_id` | string | 作品唯一标识 |
| `author_name` | string | 作者昵称 |
| `desc` | string | 作品描述/标题 |
| `media_type` | string | 媒体类型（video/gallery） |
| `tags` | list[string] | 提取的标签列表 |
| `file_names` | list[string] | 下载的文件名列表 |
| `file_paths` | list[string] | 下载的文件相对路径 |
| `publish_timestamp` | int | 发布时间戳（可选） |
| `recorded_at` | string | 清单记录时间 |

## 常见问题

| # | 问题 | 原因 | 解决方案 |
|---|------|------|---------|
| 1 | 只能抓到 20 条作品？ | 翻页风控限制，分页接口返回数据受限 | 使用**浏览器获取下载**方式补充：<br>1. `.\scripts\douyin.ps1 -Action fetch-links -Url <用户主页链接>`<br>2. `.\scripts\douyin.ps1 -ConfigFile config_temp.yml` |
| 2 | 进度条出现重复刷屏？ | 进度阶段日志输出过多 | 保持默认 `progress.quiet_logs: true`<br>调试时临时加 `--show-warnings` 或 `-v` |
| 3 | Cookie 失效怎么办？ | Cookie 过期或登录状态丢失 | 1. `.\scripts\douyin.ps1 -Action verify-login`（确认登录）<br>2. `.\scripts\douyin.ps1 -Action refresh-cookies`（刷新 Cookie）<br>下载前系统会自动检测 Cookie 有效性 |
| 4 | 为什么没有生成 transcript 文件？ | 转写功能未启用或配置有误 | 依次检查：<br>1. `transcript.enabled` 是否为 `true`<br>2. 是否下载的是视频（图文不转写）<br>3. `OPENAI_API_KEY`（或 `transcript.api_key`）是否有效<br>4. `response_formats` 是否包含 `txt` 或 `json` |
| 5 | 为什么下载不到新视频？🍴 | 增量更新机制跳过了已扫描内容 | 检查以下几项：<br>1. `skip_threshold_hours` 是否设置过小（设为 0 或空不跳过）<br>2. `last_video_time` 是否已更新（等待新视频或手动调整）<br>3. 数据库是否已有该 `aweme_id`（去重跳过） |

---

## 🍴 Fork 版本扩展功能

> 以下是本 fork 版本与上游的主要差异。详细用法请参考前文对应章节。

### 功能差异总览

| 分类 | 功能点 | 上游 | Fork版本 | 详细章节 |
|------|--------|------|----------|---------|
| **增量更新** | 增量更新机制 | `start_time` / `end_time` 时间范围 | 基于 `last_video_time` 的增量扫描 | [增量更新下载](#增量更新下载-🍴) |
| | 智能跳过阈值 | 无 | `skip_threshold_hours`（默认4小时） | [配置项完整参考](#增量更新配置-🍴) |
| **失败管理** | 失败视频记录 | 无 | `data/failed_videos/` 按日期存储 | [数据结构参考](#failed_videos-🍴) |
| | 失败重试命令 | 无 | `--list-failed` / `--retry-failed` | [命令行参数参考](#失败视频管理-🍴) |
| | 标记跳过 | 无 | `--mark-skipped` / `--mark-all-failed-skipped` | [命令行参数参考](#失败视频管理-🍴) |
| **数据库** | 数据库文件 | `data/douyin.db` 等 | `dy_downloader.db`（项目根目录） | [数据结构参考](#数据库表dy_downloaderdb🍴) |
| | aweme 表扩展 | 基础字段 | 新增 `download_time`、`status` 字段 | [数据结构参考](#aweme-表) |
| | 数据库备份 | 无 | `backup-db` 命令，自动备份到 `data/db_backup/` | [辅助脚本说明](#辅助脚本说明) |
| **日志系统** | 详细错误日志 | 无 | `data/error_logs/` 按执行时间分文件 | [运行时数据目录](#运行时数据目录-🍴) |
| | 下载报告 | 无 | `data/logs/download_YYYYMMDD_HHMMSS.txt` | [运行时数据目录](#下载报告-🍴) |
| **文件命名** | 目录命名 | `{日期}_{标题}_{aweme_id}` | `{日期}_{标题}`（避免路径过长） | [输出目录](#输出目录) |
| | 标题截断 | 80字符 | 60字符 | 输出目录 |
| **图文下载** | 图集下载优化 | 基础支持 | 多候选 URL 轮换、下载速度优化 | 功能概览 |
| **浏览器** | 浏览器选型 | 系统 Chrome | Playwright Chromium（统一安装） | [浏览器使用说明](#浏览器使用说明-🍴) |
| | 用户数据目录 | 系统默认 | `data/chrome_user_data/`（项目内共享） | [浏览器使用说明](#浏览器使用说明-🍴) |
| | 登录状态检查 | 自动脚本检测 | 人工确认（verify-login） | [辅助脚本说明](#辅助脚本说明) |
| | 链接提取（fetch-links） | 无 | 浏览器手动滚动采集，支持收藏页/用户主页 | [典型场景](#下载个人收藏视频) |
| **请求限流** | URL 间随机延迟 | 无 | `url_delay` 配置（默认2-5秒） | [配置项完整参考](#请求限流配置-🍴) |
| | 默认线程数 | 多线程 | `thread: 1`（单线程，降低限流风险） | [配置项完整参考](#基础配置) |
| **入口脚本** | PowerShell 脚本 | 无 | `scripts/douyin.ps1` 统一入口 | [辅助脚本说明](#辅助脚本说明) |
| **辅助资源** | 默认开关 | 开启 | 默认全部关闭（`music/cover/avatar/json: false`） | [配置项完整参考](#辅助资源下载开关) |

### 移除的功能

| 功能 | 说明 | 原因 |
|------|------|------|
| `start_time` / `end_time` | 时间范围过滤配置 | 改用 `last_video_time` 增量更新机制 |
| 自动登录状态检测 | 下载前自动检查登录 | 脚本检测不稳定，改为人工确认 |
| `favorites.json` | 收藏链接中间文件 | 改用 `config_temp.yml` + 数据库去重 |
| `--refresh-video-time` | 刷新扫描记录时间 | 破坏增量更新机制 |
| `--mark-processed` | 标记处理状态 | 功能无效，未正确写入数据库 |

---

## 旧版切换（V1.0）

如果你要继续使用老脚本风格（V1.0），可切换到旧分支：

```powershell
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

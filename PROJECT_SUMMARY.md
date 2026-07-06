# 项目实现总结（dy-downloader）

## 1. 项目概览

- **项目名称**: Douyin Downloader (`dy-downloader`)
- **版本**: `2.1.0`
- **更新时间**: `2026-07-06`
- **当前状态**: ✅ 核心功能可用，自动化测试通过


## 2. 当前实现能力（按代码现状）

### 2.1 已支持

- 单个视频下载（`/video/{aweme_id}`）
- 单个图文下载（`/note/{note_id}`）
- 抖音短链下载（`https://v.douyin.com/...`，会先解析后下载）
- 用户主页发布作品批量下载（`/user/{sec_uid}` + `mode: [post]`）
- 无水印优先下载，支持封面/音乐/头像/原始 JSON（独立开关控制）
- 并发下载、重试、速率限制
- URL 间随机延迟（`url_delay`），降低被限流风险
- 基于作品发布时间（`create_time`）生成文件名/目录日期前缀（`YYYY-MM-DD_...`）
- 生成独立下载清单文件 `download_manifest.jsonl`
- 数量限制（当前对 `number.post` 生效）
- SQLite 去重与增量下载（基于 `last_video_time`）
- 短时间重复扫描跳过（`skip_threshold_hours`，默认4小时）
- 翻页受限时的浏览器兜底（采集 `aweme_id` 并补全详情）
- 浏览器采集链接功能（`fetch-links`），支持收藏页和用户主页，使用精确容器选择器
- Cookie 刷新功能（`refresh-cookies`），直接读取 Chrome SQLite Cookie 数据库
- 失败视频管理与重试（`retry-failed`、`list-failed`、`mark-all-failed-skipped`）

### 2.2 暂未支持（配置项预留）

- 用户点赞下载（`mode: [like]`）
- 合集下载（`mode: [mix]` / `collection`）
- `number.like` / `number.mix` / `increase.like` / `increase.mix` 等预留字段


## 3. 架构与模块

```text
dy-downloader/
├── cli/               # CLI 入口与展示
├── core/              # 下载主流程、URL解析、API客户端
├── storage/           # 文件、元数据、数据库
├── auth/              # Cookie / token 管理
├── control/           # 限速、重试、并发队列
├── config/            # 配置加载与默认配置
├── scripts/           # PowerShell 入口脚本和辅助 Python 脚本
├── tools/             # 工具类（Cookie 抓取等）
└── utils/             # 日志与通用工具
```


## 4. 下载数据落盘策略

### 4.1 文件系统（主数据）

默认目录结构（`folderstyle: true`）：

```text
Downloaded/
├── download_manifest.jsonl
└── 作者名/
    └── post/
        └── 2024-02-07_作品标题/
            ├── 2024-02-07_作品标题.mp4
            ├── 2024-02-07_作品标题_cover.jpg（可选）
            ├── 2024-02-07_作品标题_music.mp3（可选）
            ├── 2024-02-07_作品标题_avatar.jpg（可选）
            └── 2024-02-07_作品标题_data.json（可选）
```

命名日期优先使用作品发布时间 `create_time`；若缺失或非法，会回退到当前日期并记录告警。

### 4.2 独立下载清单（新增）

- 文件：`{path}/download_manifest.jsonl`
- 形式：每行一条 JSON（append-only）
- 典型字段：
  - `date`（作品发布日期）
  - `aweme_id`
  - `author_name`
  - `desc`
  - `media_type`
  - `tags`（来自 `text_extra`、`cha_list`、`desc` 中 `#`）
  - `file_names`
  - `file_paths`
  - `publish_timestamp`（若可解析）
  - `recorded_at`（写入时间）

### 4.3 SQLite 数据库（可开关）

- 默认开关：`database: true`
- 默认库文件：`dy_downloader.db`
- 表结构：
  - `aweme`：作品明细、作者、发布时间、下载时间、保存路径、原始 metadata、status
  - `download_history`：每次任务 URL、类型、总数、成功数、配置快照

> 当 `database: false` 时，不写 SQLite，但**仍会写**媒体文件和 `download_manifest.jsonl`。

### 4.4 运行时数据

- 扫描记录：`data/scan_records.json`（增量更新和跳过阈值依据）
- 失败视频：`data/failed_videos/`（按时间戳命名的 JSON 文件）
- 错误日志：`data/error_logs/`（按时间戳命名的 `.log` 文件）
- Chrome 用户数据：`data/chrome_user_data`（Playwright 共享用户数据目录）


## 5. 关键流程（简版）

1. 读取配置（命令行 > 环境变量 > 配置文件 > 默认配置）
2. 初始化 Cookie 与 API 客户端
3. URL 级别跳过检查（`skip_threshold_hours`）
4. 解析链接类型（视频 / 图文 / 用户）
5. 拉取作品数据并应用时间/数量/增量规则
6. 单个视频去重检查（数据库 `aweme` 表）
7. 并发下载媒体文件
8. 按配置写入可选资源（音乐、封面、头像、JSON）
9. 追加写入 `download_manifest.jsonl`
10. 若开启数据库，写入 `aweme` 与 `download_history`
11. 更新扫描记录（`scan_records.json`）


## 6. 近期更新（2026-07-06）

- ✅ 新增 `skip_threshold_hours` 短时间重复扫描跳过机制（默认4小时）
- ✅ 增量更新基于 `last_video_time`（实际视频发布时间）
- ✅ 新增 `fetch-links` 浏览器采集功能，支持收藏页和用户主页
- ✅ 用户主页采集使用精确容器选择器 `div[data-e2e="user-post-list"]`
- ✅ 新增 `refresh-cookies` 功能，直接读取 Chrome SQLite Cookie 数据库
- ✅ 新增失败视频管理与重试机制
- ✅ 新增 `url_delay` URL 间随机延迟配置
- ✅ 统一使用 Playwright Chromium，共享用户数据目录 `data/chrome_user_data`
- ✅ 移除 `start_time` / `end_time` 时间范围配置
- ✅ 移除 `--refresh-video-time` 和 `--mark-processed` 无效操作
- ✅ README.md 新增下载跳过逻辑流程图


## 7. 测试与验证

执行命令：

```bash
PYTHONPATH=. pytest -q
```

结果：

```text
32 passed
```

说明：当前有 `pytest-asyncio` 的 deprecation warning（事件循环 scope 配置），不影响功能正确性。


## 8. 后续建议

1. 增加 `mode: like/mix` 的实际下载实现，打通预留配置。
2. 为 `download_manifest.jsonl` 增加轮转或归档策略（长期运行场景）。
3. 补充数据库查询 CLI（例如按作者/日期/标签检索）。
# 配置文件参考手册

## 基本配置

### link
- **类型**：字符串数组
- **默认值**：空数组
- **说明**：需要下载的抖音用户链接列表
- **示例**：
  ```yaml
  link:
    - https://v.douyin.com/DWBmsiq9j4Y/
    - https://www.douyin.com/user/MS4wLjABAAAAxxxx
  ```

### path
- **类型**：字符串
- **默认值**：无（必填）
- **说明**：视频保存路径
- **示例**：`path: C:\Users\sb\Desktop\抖音下载\Downloaded\`

### thread
- **类型**：整数
- **默认值**：5
- **说明**：下载线程数
- **范围**：1-10
- **示例**：`thread: 5`

## 内容配置

### music
- **类型**：布尔值
- **默认值**：true
- **说明**：是否下载视频背景音乐
- **示例**：`music: true`

### cover
- **类型**：布尔值
- **默认值**：true
- **说明**：是否下载视频封面
- **示例**：`cover: true`

### avatar
- **类型**：布尔值
- **默认值**：true
- **说明**：是否下载用户头像
- **示例**：`avatar: true`

### json
- **类型**：布尔值
- **默认值**：true
- **说明**：是否保存视频信息JSON文件
- **示例**：`json: true`

## 时间过滤配置

### start_time
- **类型**：字符串（YYYY-MM-DD）
- **默认值**：空字符串（不限制）
- **说明**：只下载该日期之后发布的视频
- **示例**：`start_time: '2026-06-03'`

### end_time
- **类型**：字符串（YYYY-MM-DD）
- **默认值**：空字符串（不限制）
- **说明**：只下载该日期之前发布的视频
- **示例**：`end_time: '2026-06-30'`

## 模式配置

### mode
- **类型**：字符串数组
- **默认值**：`["post"]`
- **说明**：下载模式，支持 post（作品）、like（喜欢）、allmix（全部合集）、mix（指定合集）、music（音乐）
- **示例**：`mode: ["post", "like"]`

### number
- **类型**：对象
- **说明**：各模式的下载数量限制（0表示不限制）
- **示例**：
  ```yaml
  number:
    post: 0
    like: 10
    allmix: 0
    mix: 0
    music: 0
  ```

### increase
- **类型**：对象
- **说明**：是否启用增量更新模式
- **示例**：
  ```yaml
  increase:
    post: true
    like: false
    allmix: false
    mix: false
    music: false
  ```

## 高级配置

### skip_threshold_hours
- **类型**：整数
- **默认值**：4
- **说明**：跳过阈值（小时），N小时内已成功处理的链接将跳过，0表示不限制
- **范围**：0-24
- **示例**：`skip_threshold_hours: 4`

### database
- **类型**：布尔值
- **默认值**：true
- **说明**：是否启用数据库记录下载历史
- **示例**：`database: true`

## 重试配置

### retry
- **类型**：对象
- **说明**：下载失败重试配置
- **示例**：
  ```yaml
  retry:
    max_retries: 3    # 最大重试次数
    delay: 5          # 重试间隔（秒）
  ```

## 进度配置

### progress
- **类型**：对象
- **说明**：进度显示配置
- **示例**：
  ```yaml
  progress:
    quiet_logs: true  # 是否静默控制台日志
  ```

## Cookie配置

### cookies
- **类型**：对象
- **说明**：抖音登录Cookie，用于访问需要登录的内容
- **示例**：
  ```yaml
  cookies:
    passport_csrf_token: xxx
    sid_guard: xxx
    sid_tt: xxx
    sessionid: xxx
    ttwid: xxx
    odin_tt: xxx
    msToken: xxx
  ```
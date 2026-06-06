# 故障排查指南

## 常见问题

### 问题：下载失败，提示"Cookie已过期"
**症状**：所有下载都失败，控制台显示Cookie相关错误

**解决方案**：
1. 打开浏览器，登录抖音官网
2. 按 F12 打开开发者工具
3. 切换到 Application（应用）标签
4. 在左侧找到 Cookies -> https://www.douyin.com
5. 复制以下Cookie值：
   - passport_csrf_token
   - sid_guard
   - sid_tt
   - sessionid
   - ttwid
   - odin_tt
   - msToken
6. 更新 config.yml 中的 cookies 配置

**相关文档**：[CONFIG_REFERENCE.md](CONFIG_REFERENCE.md)

---

### 问题：下载速度很慢
**症状**：单个视频下载时间超过1分钟

**可能原因**：
1. 网络连接不稳定
2. 线程数设置过低
3. 平台限流

**解决方案**：
1. 检查网络连接状态
2. 增加 `thread` 配置值（建议5-10）
3. 暂停一段时间后再继续下载
4. 检查是否有大量失败记录（可能触发限流）

**相关文档**：[CONFIG_REFERENCE.md](CONFIG_REFERENCE.md)

---

### 问题：数据库错误 "database locked"
**症状**：启动时报错 "database locked" 或下载过程中断

**解决方案**：
1. 关闭所有可能使用数据库的程序
2. 检查 `data/douyin.db` 文件是否存在
3. 确保没有其他进程占用数据库
4. 尝试删除数据库文件重新初始化（会丢失历史记录）

**相关文档**：[KNOWN_ISSUES.md](KNOWN_ISSUES.md)

---

### 问题：短链接解析失败
**症状**：提示"无法解析短链接"或链接无效

**解决方案**：
1. 检查链接是否正确
2. 手动在浏览器中打开该短链接，查看是否能正常访问
3. 如果链接已过期，获取新的链接
4. 检查网络代理设置（如果使用代理）

**相关文档**：[KNOWN_ISSUES.md](KNOWN_ISSUES.md)

---

### 问题：视频下载后无法播放
**症状**：下载的视频文件无法打开或播放

**可能原因**：
1. 下载未完成（文件损坏）
2. 视频格式不兼容
3. 文件扩展名错误

**解决方案**：
1. 删除损坏的文件，重新下载
2. 尝试使用不同的播放器（如 VLC）
3. 检查文件扩展名是否正确（应为.mp4）

---

### 问题：程序启动后无响应
**症状**：启动后没有任何输出或卡住

**可能原因**：
1. 配置文件错误
2. 数据库文件损坏
3. 网络连接问题

**解决方案**：
1. 检查配置文件格式是否正确（YAML格式）
2. 验证配置文件中的路径是否存在
3. 尝试删除 `data/douyin.db` 重新初始化
4. 检查网络连接

---

### 问题：日志文件过大
**症状**：logs 目录下的日志文件占用过多磁盘空间

**解决方案**：
1. 定期清理旧日志文件
2. 可以设置日志保留天数（未来功能）

---

## 调试技巧

### 1. 启用详细日志
运行时添加 `-v` 参数启用详细日志：
```bash
python main.py -v
```

### 2. 检查配置文件
使用以下命令验证配置文件语法：
```bash
python -c "import yaml; yaml.safe_load(open('config.yml'))"
```

### 3. 查看数据库内容
使用 SQLite 工具打开 `data/douyin.db` 查看记录：
```bash
sqlite3 data/douyin.db
```

### 4. 测试单个链接
使用 `-u` 参数测试单个链接：
```bash
python main.py -u https://v.douyin.com/DWBmsiq9j4Y/
```

---

## 紧急恢复

### 重置数据库
如果数据库损坏或出现问题，可以删除重新初始化：
```bash
rm data/douyin.db
```

### 重置扫描记录
如果跳过逻辑出现问题，可以删除扫描记录：
```bash
rm data/scan_records.json
```

### 清理失败视频记录
```bash
rm -rf data/failed_videos/
```
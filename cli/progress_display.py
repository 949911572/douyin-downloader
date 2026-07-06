from __future__ import annotations

import sys
import os
from datetime import datetime
from typing import Optional

from rich.table import Table

console = None


def _display_width(s: str) -> int:
    w = 0
    for c in s:
        if ord(c) > 0x2e80:
            w += 2
        else:
            w += 1
    return w


def _pad_str(s: str, target_width: int, align: str = '<') -> str:
    dw = _display_width(s)
    pad = max(target_width - dw, 0)
    if align == '>':
        return ' ' * pad + s
    elif align == '^':
        left = pad // 2
        right = pad - left
        return ' ' * left + s + ' ' * right
    else:
        return s + ' ' * pad


class ProgressDisplay:
    _URL_STEP_TOTAL = 6

    def __init__(self):
        self._url_index = 0
        self._url_total = 0
        self._url_step_completed = 0
        self._item_total = 0
        self._item_completed = 0
        self._item_stats = {"success": 0, "failed": 0, "skipped": 0}
        self._current_step = ""
        self._current_url = ""
        self._is_running = False

    def show_banner(self):
        banner = """
╔══════════════════════════════════════════╗
║     Douyin Downloader v2.0.0            ║
║     抖音批量下载工具                     ║
╚══════════════════════════════════════════╝
        """
        print(banner)

    def start_download_session(self, total_urls: int):
        self._is_running = True
        self._url_total = total_urls
        self._url_index = 0
        
        print(f"\n正在处理 {total_urls} 个 URL...", end='\r')

    def stop_download_session(self):
        if self._is_running:
            print()
            self._is_running = False

    def _print_progress(self, description: str, detail: str = ""):
        if not self._is_running:
            return
        
        progress = ""
        if self._url_total > 0:
            percentage = int((self._url_index / self._url_total) * 100)
            progress = f"[{percentage:3}%] "
        
        line = f"\r{progress}{description}"
        if detail:
            terminal_width = 80
            description_width = _display_width(f"{progress}{description}")
            available_width = terminal_width - description_width - 3
            if available_width > 0:
                detail = self._shorten(detail, max_len=available_width)
                line += f" | {detail}"
        
        sys.stdout.write(line)
        sys.stdout.flush()

    def start_url(self, index: int, total: int, url: str):
        self._url_index = index
        self._url_total = total
        self._url_step_completed = 0
        self._item_total = 0
        self._item_completed = 0
        self._item_stats = {"success": 0, "failed": 0, "skipped": 0}
        self._current_step = "待开始"
        self._current_url = url

        description = f"URL {index}/{total} · 待开始"
        self._print_progress(description, self._shorten(url, max_len=50))

    def complete_url(self, result=None):
        detail = ""
        if result:
            detail = f"成功 {result.success} / 失败 {result.failed} / 跳过 {result.skipped}"

        description = f"URL {self._url_index}/{self._url_total} · 完成"
        self._print_progress(description, detail)

    def skip_url(self, reason: str):
        description = f"URL {self._url_index}/{self._url_total} · 跳过"
        self._print_progress(description, reason)

    def fail_url(self, reason: str):
        description = f"URL {self._url_index}/{self._url_total} · 失败"
        self._print_progress(description, reason)

    def advance_step(self, step: str, detail: str = ""):
        self._url_step_completed = min(self._url_step_completed + 1, self._URL_STEP_TOTAL)
        self._current_step = step

        description = f"URL {self._url_index}/{self._url_total} · {step}"
        self._print_progress(description, detail or self._shorten(self._current_url, max_len=50))

    def update_step(self, step: str, detail: str = ""):
        self._current_step = step

        description = f"URL {self._url_index}/{self._url_total} · {step}"
        self._print_progress(description, detail or self._shorten(self._current_url, max_len=50))

    def set_item_total(self, total: int, detail: str = ""):
        self._item_total = max(total, 1)
        self._item_completed = 1 if total == 0 else 0
        self._item_stats = {"success": 0, "failed": 0, "skipped": 0}

        description = f"URL {self._url_index}/{self._url_total} · {self._current_step}"
        self._print_progress(description, f"共 {total} 个作品")

    def advance_item(self, status: str, detail: str = ""):
        if status in self._item_stats:
            self._item_stats[status] += 1
        if self._item_completed < self._item_total:
            self._item_completed += 1

        status_map = {"success": "成功", "failed": "失败", "skipped": "跳过"}
        status_text = status_map.get(status, status)
        item_detail = f"S:{self._item_stats['success']} F:{self._item_stats['failed']} K:{self._item_stats['skipped']} | 最近: {status_text} {self._shorten(detail, max_len=24)}"

        description = f"URL {self._url_index}/{self._url_total} · {self._current_step}"
        self._print_progress(description, item_detail)

    def show_result(self, result):
        table = Table(title="Download Summary", show_header=True, header_style="bold magenta")
        table.add_column("Metric", style="cyan")
        table.add_column("Count", justify="right", style="green")

        table.add_row("Total", str(result.total))
        table.add_row("Success", str(result.success))
        table.add_row("Failed", str(result.failed))
        table.add_row("Skipped", str(result.skipped))

        if result.total > 0:
            success_rate = (result.success / result.total) * 100
            table.add_row("Success Rate", f"{success_rate:.1f}%")

        print()
        from rich.console import Console
        Console().print(table)

    def show_final_summary(self, url_results, config, skipped_urls=None):
        now = datetime.now()
        now_str = now.strftime('%Y-%m-%d %H:%M:%S')
        timestamp = now.strftime('%Y%m%d_%H%M%S')

        target_path = config.get('path', '未设置')

        lines = []
        lines.append("=" * 64)

        user_links = []
        video_links = []
        failed_links = []
        
        user_total = 0
        user_skipped = 0
        user_success = 0
        user_failed = 0
        
        video_total = 0
        video_skipped = 0
        video_success = 0
        video_failed = 0

        for url, result, status in url_results:
            if status == "failed" or result is None:
                failed_links.append(url)
            else:
                sec_uid = getattr(result, 'sec_uid', '') or ''
                if sec_uid:
                    user_links.append((url, result))
                    user_total += result.total
                    user_skipped += result.skipped
                    user_success += result.success
                    user_failed += result.failed
                else:
                    video_links.append((url, result))
                    video_total += result.total
                    video_skipped += result.skipped
                    video_success += result.success
                    video_failed += result.failed

        user_count = len(user_links)
        video_count = len(video_links)
        failed_count = len(failed_links)
        skipped_count = len(skipped_urls) if skipped_urls else 0

        if user_count > 0 and video_count > 0:
            lines.append("  抖音下载 · 执行结果报告")
        elif user_count > 0:
            lines.append("  抖音批量下载 · 执行结果报告")
        else:
            lines.append("  抖音视频下载 · 执行结果报告")
        
        lines.append("=" * 64)
        lines.append(f"  目标目录:    {target_path}")
        lines.append("")

        if user_count > 0:
            lines.append("=" * 64)
            lines.append(f"【用户主页下载】（链接数：{user_count}）")
            lines.append("=" * 64)
            lines.append("")
            
            for idx, (url, result) in enumerate(user_links, 1):
                author = getattr(result, 'author_name', '') or '未知'
                sec_uid = getattr(result, 'sec_uid', '') or ''
                total = result.total
                skipped = result.skipped
                success = result.success
                failed = result.failed

                lines.append(f"  {idx}，{author}[{sec_uid}]/{total}/{skipped}/{success}/{failed}")
                
                downloaded_files = getattr(result, 'downloaded_files', []) or []
                success_items = [f for f in downloaded_files if f.get('success')]
                if success_items:
                    lines.append(f"    成功下载视频 ({len(success_items)} 个):")
                    for item in success_items:
                        aweme_id = item.get('aweme_id', '')
                        file_name = item.get('file_name', '')
                        desc_short = (item.get('desc', '') or '')[:30]
                        if aweme_id:
                            video_url = f"https://www.douyin.com/video/{aweme_id}"
                            lines.append(f"      - {video_url} | {desc_short}... | {file_name}")
                        else:
                            lines.append(f"      - {file_name} | {desc_short}...")
                
                failed_items = getattr(result, 'failed_items', []) or []
                if failed_items:
                    lines.append(f"    下载失败视频 ({len(failed_items)} 个):")
                    for aweme_id, error_desc in failed_items:
                        if aweme_id and aweme_id != 'unknown':
                            video_url = f"https://www.douyin.com/video/{aweme_id}"
                            lines.append(f"      - {video_url} | {error_desc}")
                        else:
                            lines.append(f"      - {error_desc}")
                
                lines.append("")

        if video_count > 0:
            lines.append("=" * 64)
            lines.append(f"【单视频链接下载】（链接数：{video_count}）")
            lines.append("=" * 64)
            lines.append("")

            for idx, (url, result) in enumerate(video_links, 1):
                author = getattr(result, 'author_name', '') or '未知'
                total = result.total
                skipped = result.skipped
                success = result.success
                failed = result.failed

                lines.append(f"  {idx}，{url}")
                if author != '未知':
                    lines.append(f"      作者: {author}")
                lines.append(f"      状态: 总数 {total} / 跳过 {skipped} / 成功 {success} / 失败 {failed}")
                
                downloaded_files = getattr(result, 'downloaded_files', []) or []
                success_items = [f for f in downloaded_files if f.get('success')]
                if success_items:
                    lines.append(f"      成功下载:")
                    for item in success_items:
                        aweme_id = item.get('aweme_id', '')
                        desc_short = (item.get('desc', '') or '')[:30]
                        if aweme_id:
                            video_url = f"https://www.douyin.com/video/{aweme_id}"
                            lines.append(f"        - {video_url} | {desc_short}...")
                        else:
                            file_name = item.get('file_name', '')
                            lines.append(f"        - {file_name} | {desc_short}...")
                
                failed_items = getattr(result, 'failed_items', []) or []
                if failed_items:
                    lines.append(f"      下载失败:")
                    for aweme_id, error_desc in failed_items:
                        if aweme_id and aweme_id != 'unknown':
                            video_url = f"https://www.douyin.com/video/{aweme_id}"
                            lines.append(f"        - {video_url} | {error_desc}")
                        else:
                            lines.append(f"        - {error_desc}")
                
                lines.append("")

        lines.append("=" * 64)
        lines.append(f"【解析失败链接】（链接数：{failed_count}）")
        lines.append("=" * 64)
        if failed_count > 0:
            for idx, url in enumerate(failed_links, 1):
                lines.append(f"  {idx}. {url}")
        lines.append("")

        if user_count > 0 and skipped_count > 0:
            lines.append("=" * 64)
            lines.append(f"【智能跳过用户】（用户数：{skipped_count}）")
            lines.append("=" * 64)
            if skipped_urls and len(skipped_urls) > 0:
                for idx, item in enumerate(skipped_urls, 1):
                    if len(item) >= 3:
                        url, username, sec_uid = item[0], item[1], item[2]
                        if sec_uid:
                            lines.append(f"  {idx}，{username}[{sec_uid}] - 本地记录显示4小时内已成功处理，本次跳过")
                        else:
                            lines.append(f"  {idx}，{username} - 本地记录显示4小时内已成功处理，本次跳过")
            lines.append("")

        restricted_users = []
        for url, result, status in url_results:
            if status != "failed" and result is not None:
                sec_uid = getattr(result, 'sec_uid', '') or ''
                if sec_uid and getattr(result, 'pagination_restricted', False):
                    restricted_users.append((url, result))

        if restricted_users:
            lines.append("=" * 64)
            lines.append(f"【分页受限用户】（用户数：{len(restricted_users)}）")
            lines.append("=" * 64)
            lines.append("  需要手动使用浏览器扫描补充的用户列表：")
            lines.append("")
            for idx, (url, result) in enumerate(restricted_users, 1):
                author = getattr(result, 'author_name', '') or '未知'
                sec_uid = getattr(result, 'sec_uid', '') or ''
                user_url = f"https://www.douyin.com/user/{sec_uid}" if sec_uid else url
                lines.append(f"  {idx}. 用户：{author}")
                lines.append(f"     地址：{user_url}")
                lines.append(f"     命令：.\\scripts\\douyin.ps1 -Action fetch-links -Url {user_url}")
                lines.append("")

        lines.append("=" * 64)
        lines.append("【总计统计】")
        lines.append("=" * 64)
        
        if user_count > 0:
            lines.append(f"  用户主页下载:")
            lines.append(f"      待下载: {user_total} 个")
            lines.append(f"      成功:   {user_success} 个")
            lines.append(f"      跳过:   {user_skipped} 个")
            lines.append(f"      失败:   {user_failed} 个")
        
        if video_count > 0:
            if user_count > 0:
                lines.append("")
            lines.append(f"  单视频链接下载:")
            lines.append(f"      待下载: {video_total} 个")
            lines.append(f"      成功:   {video_success} 个")
            lines.append(f"      跳过:   {video_skipped} 个")
            lines.append(f"      失败:   {video_failed} 个")
        
        total_all = user_total + video_total
        total_success = user_success + video_success
        total_skipped = user_skipped + video_skipped
        total_failed = user_failed + video_failed
        
        if total_all > 0:
            lines.append("")
            lines.append(f"  合计:")
            lines.append(f"      待下载: {total_all} 个")
            lines.append(f"      成功:   {total_success} 个")
            lines.append(f"      跳过:   {total_skipped} 个")
            lines.append(f"      失败:   {total_failed} 个")
        
        all_failed_items = []
        for url, result, status in url_results:
            if result is not None:
                failed_items = getattr(result, 'failed_items', []) or []
                all_failed_items.extend(failed_items)
        
        if all_failed_items:
            error_counts = {}
            for aweme_id, error_desc in all_failed_items:
                if "HTTP 404" in error_desc:
                    key = "HTTP 404 - 资源未找到"
                elif "HTTP 403" in error_desc:
                    key = "HTTP 403 - 访问被拒绝"
                elif "获取视频详情失败" in error_desc:
                    key = "获取视频详情失败"
                elif "视频无可播放URL" in error_desc:
                    key = "视频无可播放URL"
                elif "无法构建无水印视频URL" in error_desc:
                    key = "无法构建无水印视频URL"
                elif "图文作品无图片URL" in error_desc:
                    key = "图文作品无图片URL"
                elif "不支持的媒体类型" in error_desc:
                    key = "不支持的媒体类型"
                elif "Missing aweme_id" in error_desc:
                    key = "缺失视频ID"
                else:
                    key = "其他下载失败"
                error_counts[key] = error_counts.get(key, 0) + 1
            
            lines.append("")
            lines.append("=" * 64)
            lines.append("【失败原因分类】")
            lines.append("=" * 64)
            for key, count in error_counts.items():
                lines.append(f"  {key}: {count} 个")
            
            has_http_error = any("HTTP" in k for k in error_counts.keys())
            if has_http_error:
                lines.append("")
                lines.append("  提示：HTTP 404/403 可能因视频源不可用、CDN资源过期或删除、地域限制、权限限制或临时网络问题导致")
        
        lines.append("")
        lines.append("=" * 64)

        output = '\n'.join(lines)
        print(output)

        log_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data', 'logs'))
        os.makedirs(log_dir, exist_ok=True)
        log_filename = datetime.now().strftime('download_%Y%m%d_%H%M%S.txt')
        log_path = os.path.join(log_dir, log_filename)
        with open(log_path, 'w', encoding='utf-8') as f:
            f.write(output)

        from utils.failed_video_manager import FailedVideoManager
        failed_manager = FailedVideoManager()
        failed_count_total = failed_manager.get_failed_count()
        failed_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data', 'failed_videos'))

        print(f"\n详细下载日志已保存到: {log_path}")
        print(f"失败视频记录已保存到: {failed_dir}")
        print(f"当前未处理失败视频总数: {failed_count_total}")

    def print_info(self, message: str):
        if self._is_running:
            print()
        print(f"ℹ {message}")
        if self._is_running:
            self._print_progress(
                f"URL {self._url_index}/{self._url_total} · {self._current_step}",
                self._shorten(self._current_url, max_len=50)
            )

    def print_success(self, message: str):
        if self._is_running:
            print()
        print(f"✓ {message}")
        if self._is_running:
            self._print_progress(
                f"URL {self._url_index}/{self._url_total} · {self._current_step}",
                self._shorten(self._current_url, max_len=50)
            )

    def print_warning(self, message: str):
        if self._is_running:
            print()
        print(f"⚠ {message}")
        if self._is_running:
            self._print_progress(
                f"URL {self._url_index}/{self._url_total} · {self._current_step}",
                self._shorten(self._current_url, max_len=50)
            )

    def print_error(self, message: str):
        if self._is_running:
            print()
        print(f"✗ {message}")
        if self._is_running:
            self._print_progress(
                f"URL {self._url_index}/{self._url_total} · {self._current_step}",
                self._shorten(self._current_url, max_len=50)
            )

    @staticmethod
    def _shorten(text: str, max_len: int = 60) -> str:
        normalized = (text or "").strip()
        if len(normalized) <= max_len:
            return normalized
        return f"{normalized[: max_len - 3]}..."

from __future__ import annotations

from datetime import datetime
from typing import Optional

from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeRemainingColumn,
)
from rich.table import Table

console = Console()


def _display_width(s: str) -> int:
    """计算字符串在终端中的显示宽度，CJK字符计为2。"""
    w = 0
    for c in s:
        if ord(c) > 0x2e80:
            w += 2
        else:
            w += 1
    return w


def _pad_str(s: str, target_width: int, align: str = '<') -> str:
    """按显示宽度补齐字符串。"""
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
        self.console = console
        self._progress_ctx: Optional[Progress] = None
        self._progress: Optional[Progress] = None
        self._overall_task_id: Optional[int] = None
        self._url_task_id: Optional[int] = None
        self._item_task_id: Optional[int] = None
        self._url_index = 0
        self._url_total = 0
        self._url_step_completed = 0
        self._item_total = 0
        self._item_completed = 0
        self._single_url_item_mode = False
        self._item_stats = {"success": 0, "failed": 0, "skipped": 0}

    def show_banner(self):
        banner = """
╔══════════════════════════════════════════╗
║     Douyin Downloader v2.0.0            ║
║     抖音批量下载工具                     ║
╚══════════════════════════════════════════╝
        """
        self._active_console().print(banner, style="bold cyan")

    def create_progress(self) -> Progress:
        return Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeRemainingColumn(),
            TextColumn("[dim]{task.fields[detail]}"),
            console=self.console,
            transient=True,
            refresh_per_second=6,
        )

    def start_download_session(self, total_urls: int):
        if self._progress is not None:
            return

        self._progress_ctx = self.create_progress()
        self._progress = self._progress_ctx.__enter__()
        self._single_url_item_mode = False
        self._overall_task_id = self._progress.add_task(
            "总体进度",
            total=max(total_urls, 1),
            completed=0,
            detail=f"共 {total_urls} 个 URL",
        )

    def stop_download_session(self):
        self._cleanup_url_tasks()

        if self._progress_ctx is not None:
            self._progress_ctx.__exit__(None, None, None)

        self._progress_ctx = None
        self._progress = None
        self._overall_task_id = None
        self._single_url_item_mode = False

    def start_url(self, index: int, total: int, url: str):
        self._url_index = index
        self._url_total = total
        self._url_step_completed = 0
        self._item_total = 0
        self._item_completed = 0
        self._item_stats = {"success": 0, "failed": 0, "skipped": 0}

        self._cleanup_url_tasks()
        if not self._progress:
            return

        self._url_task_id = self._progress.add_task(
            self._format_url_description("待开始"),
            total=self._URL_STEP_TOTAL,
            completed=0,
            detail=self._shorten(url, max_len=72),
        )

    def complete_url(self, result=None):
        if self._progress and self._url_task_id is not None:
            detail = ""
            if result:
                detail = (
                    f"成功 {result.success} / 失败 {result.failed} / 跳过 {result.skipped}"
                )
            self._progress.update(
                self._url_task_id,
                completed=self._URL_STEP_TOTAL,
                description=self._format_url_description("完成"),
                detail=detail,
            )

        if self._progress and self._overall_task_id is not None:
            if self._single_url_item_mode:
                self._progress.update(
                    self._overall_task_id, completed=self._item_total or 1
                )
            else:
                self._progress.advance(self._overall_task_id, 1)

    def fail_url(self, reason: str):
        if self._progress and self._url_task_id is not None:
            self._progress.update(
                self._url_task_id,
                completed=self._URL_STEP_TOTAL,
                description=self._format_url_description("失败"),
                detail=reason,
            )

        if self._progress and self._overall_task_id is not None:
            if self._single_url_item_mode:
                self._progress.update(
                    self._overall_task_id, completed=self._item_total or 1
                )
            else:
                self._progress.advance(self._overall_task_id, 1)

    def advance_step(self, step: str, detail: str = ""):
        if not self._progress or self._url_task_id is None:
            return

        self._url_step_completed = min(self._url_step_completed + 1, self._URL_STEP_TOTAL)
        self._progress.update(
            self._url_task_id,
            completed=self._url_step_completed,
            description=self._format_url_description(step),
            detail=detail,
        )

    def update_step(self, step: str, detail: str = ""):
        if not self._progress or self._url_task_id is None:
            return

        self._progress.update(
            self._url_task_id,
            description=self._format_url_description(step),
            detail=detail,
        )

    def set_item_total(self, total: int, detail: str = ""):
        if not self._progress:
            return

        self._item_total = max(total, 1)
        self._item_completed = 1 if total == 0 else 0
        self._item_stats = {"success": 0, "failed": 0, "skipped": 0}

        if self._url_total == 1 and self._overall_task_id is not None:
            self._single_url_item_mode = True
            self._progress.update(
                self._overall_task_id,
                total=self._item_total,
                completed=self._item_completed,
                detail=f"共 {total} 个作品",
            )

        description = self._format_item_description()
        item_detail = detail or ("无待下载条目" if total == 0 else "")

        if self._item_task_id is None:
            self._item_task_id = self._progress.add_task(
                description,
                total=self._item_total,
                completed=self._item_completed,
                detail=item_detail,
            )
            return

        self._progress.update(
            self._item_task_id,
            total=self._item_total,
            completed=self._item_completed,
            description=description,
            detail=item_detail,
        )

    def advance_item(self, status: str, detail: str = ""):
        if not self._progress:
            return
        if self._item_task_id is None:
            self.set_item_total(1, "初始化条目进度")
        assert self._item_task_id is not None

        if status in self._item_stats:
            self._item_stats[status] += 1
        if self._item_completed < self._item_total:
            self._item_completed += 1

        status_map = {"success": "成功", "failed": "失败", "skipped": "跳过"}
        status_text = status_map.get(status, status)
        item_detail = f"最近: {status_text} {self._shorten(detail, max_len=36)}"

        self._progress.update(
            self._item_task_id,
            completed=self._item_completed,
            description=self._format_item_description(),
            detail=item_detail,
        )
        if self._single_url_item_mode and self._overall_task_id is not None:
            self._progress.update(
                self._overall_task_id,
                completed=self._item_completed,
                detail=f"共 {self._item_total} 个作品",
            )

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

        self._active_console().print(table)

    def show_final_summary(self, url_results, config):
        """Display comprehensive download summary in new format."""

        now = datetime.now()
        now_str = now.strftime('%Y-%m-%d %H:%M:%S')
        timestamp = now.strftime('%Y%m%d_%H%M%S')

        start_time = config.get('start_time', '') or '不限'
        end_time = config.get('end_time', '') or now_str
        target_path = config.get('path', '未设置')

        lines = []
        lines.append("=" * 64)
        lines.append("  抖音批量下载 · 执行结果报告")
        lines.append("=" * 64)
        lines.append(f"  下载时间段:  {start_time}  ~  {end_time}")
        lines.append(f"  目标目录:    {target_path}")
        lines.append("")

        # ---- 分类收集 ----
        resolved_links = []
        failed_links = []
        total_all = 0
        total_skipped = 0
        total_success = 0
        total_failed = 0

        for url, result, status in url_results:
            if status == "failed" or result is None:
                failed_links.append(url)
            else:
                resolved_links.append((url, result))
                total_all += result.total
                total_skipped += result.skipped
                total_success += result.success
                total_failed += result.failed

        resolved_count = len(resolved_links)
        failed_count = len(failed_links)

        # ---- 一，解析成功链接下载明细 ----
        if resolved_count > 0:
            lines.append(f"一，解析成功链接下载明细（链接总数：{resolved_count}）:")
            lines.append("")

            for idx, (url, result) in enumerate(resolved_links, 1):
                author = getattr(result, 'author_name', '') or '未知'
                total = result.total
                skipped = result.skipped
                success = result.success
                failed = result.failed

                lines.append(f"  {idx}，{author}/{total}/{skipped}/{success}/{failed}")
                lines.append("")
                lines.append("")

            # 下载失败视频具体链接
            failed_videos = []
            for url, result in resolved_links:
                downloaded_files = getattr(result, 'downloaded_files', [])
                for f in downloaded_files:
                    if not f.get('success', False):
                        failed_videos.append(url)
                        break

            if failed_videos:
                lines.append(" 2，下载失败视频具体链接：")
                lines.append("")
                for idx, url in enumerate(failed_videos, 1):
                    lines.append(f"    {idx}. {url}")
                lines.append("")

        # ---- 二，解析失败链接 ----
        lines.append(f"二，解析失败链接（链接总数：{failed_count}）:")
        if failed_count > 0:
            for idx, url in enumerate(failed_links, 1):
                lines.append(f"  {idx}. {url}")
        lines.append("")

        lines.append("=" * 64)

        output = '\n'.join(lines)
        print(output)

        # 保存到日志文件
        import os
        log_dir = os.path.join(os.path.dirname(__file__), '..', 'logs')
        os.makedirs(log_dir, exist_ok=True)
        log_filename = datetime.now().strftime('download_%Y%m%d_%H%M%S.txt')
        log_path = os.path.join(log_dir, log_filename)
        with open(log_path, 'w', encoding='utf-8') as f:
            f.write(output)
        print(f"\n日志已保存到: {log_path}")

        

    def print_info(self, message: str):
        self._active_console().print(f"[blue]ℹ[/blue] {message}")

    def print_success(self, message: str):
        self._active_console().print(f"[green]✓[/green] {message}")

    def print_warning(self, message: str):
        self._active_console().print(f"[yellow]⚠[/yellow] {message}")

    def print_error(self, message: str):
        self._active_console().print(f"[red]✗[/red] {message}")

    def _cleanup_url_tasks(self):
        if not self._progress:
            self._url_task_id = None
            self._item_task_id = None
            return

        if self._item_task_id is not None:
            self._progress.remove_task(self._item_task_id)
            self._item_task_id = None
        if self._url_task_id is not None:
            self._progress.remove_task(self._url_task_id)
            self._url_task_id = None

    def _format_url_description(self, step: str) -> str:
        return f"URL {self._url_index}/{self._url_total} · {step}"

    def _format_item_description(self) -> str:
        return (
            "作品下载 "
            f"S:{self._item_stats['success']} "
            f"F:{self._item_stats['failed']} "
            f"K:{self._item_stats['skipped']}"
        )

    def _active_console(self) -> Console:
        if self._progress:
            return self._progress.console
        return self.console

    @staticmethod
    def _shorten(text: str, max_len: int = 60) -> str:
        normalized = (text or "").strip()
        if len(normalized) <= max_len:
            return normalized
        return f"{normalized[: max_len - 3]}..."

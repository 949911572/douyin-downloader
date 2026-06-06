import asyncio
import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict

from config import ConfigLoader
from auth import CookieManager
from storage import Database, FileManager
from control import QueueManager, RateLimiter, RetryHandler
from core import DouyinAPIClient, URLParser, DownloaderFactory
from cli.progress_display import ProgressDisplay
from utils.logger import setup_logger, set_console_log_level
from utils.scan_record_manager import ScanRecordManager
from utils.failed_video_manager import FailedVideoManager

logger = setup_logger('CLI')
display = ProgressDisplay()


def _as_bool(value: Any, default: bool = True) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


async def download_url(
    url: str,
    config: ConfigLoader,
    cookie_manager: CookieManager,
    database: Database = None,
    progress_reporter: ProgressDisplay = None,
    last_scan_time: str = None,  # 上次最新视频时间，用于增量更新
    parsed_url: Dict[str, Any] = None,  # 预解析的URL结果
    api_client=None,  # 复用的API客户端
):
    if progress_reporter:
        progress_reporter.advance_step("初始化", "创建下载组件")
    file_manager = FileManager(config.get('path'))
    rate_limiter = RateLimiter(max_per_second=2)
    retry_handler = RetryHandler(max_retries=config.get('retry_times', 3))
    queue_manager = QueueManager(max_workers=int(config.get('thread', 5) or 5))

    original_url = url
    should_close_client = False

    # 如果没有传入API客户端，创建新的
    if api_client is None:
        should_close_client = True
        api_client = DouyinAPIClient(cookie_manager.get_cookies())
        await api_client._ensure_session()

    try:
        if progress_reporter:
            progress_reporter.advance_step("解析链接", "检查短链并解析 URL")
        
        # 如果没有预解析结果，进行解析
        if parsed_url is None:
            if url.startswith('https://v.douyin.com'):
                resolved_url = await api_client.resolve_short_url(url)
                if resolved_url:
                    url = resolved_url
                else:
                    if progress_reporter:
                        progress_reporter.update_step("解析链接", "短链解析失败")
                    display.print_error(f"Failed to resolve short URL: {url}")
                    return None

            parsed_url = URLParser.parse(url)
            if not parsed_url:
                if progress_reporter:
                    progress_reporter.update_step("解析链接", "URL 解析失败")
                display.print_error(f"Failed to parse URL: {url}")
                return None
        else:
            # 使用预解析结果
            if progress_reporter:
                progress_reporter.update_step("解析链接", "使用预解析结果")

        if not progress_reporter:
            display.print_info(f"URL type: {parsed_url['type']}")
        if progress_reporter:
            progress_reporter.advance_step("创建下载器", f"URL 类型: {parsed_url['type']}")

        downloader = DownloaderFactory.create(
            parsed_url['type'],
            config,
            api_client,
            file_manager,
            cookie_manager,
            database,
            rate_limiter,
            retry_handler,
            queue_manager,
            progress_reporter=progress_reporter,
        )

        if not downloader:
            if progress_reporter:
                progress_reporter.update_step("创建下载器", "未找到匹配下载器")
            display.print_error(f"No downloader found for type: {parsed_url['type']}")
            return None

        if progress_reporter:
            progress_reporter.advance_step("执行下载", "开始拉取与下载资源")
        
        # 传递 last_scan_time 支持增量更新
        if last_scan_time and parsed_url['type'] == 'user':
            result = await downloader.download(parsed_url, last_scan_time)
        else:
            result = await downloader.download(parsed_url)

        if progress_reporter:
            progress_reporter.advance_step(
                "记录历史",
                "写入数据库历史" if (result and database) else "数据库未启用，跳过",
            )
        if result and database:
            await database.add_history({
                'url': original_url,
                'url_type': parsed_url['type'],
                'total_count': result.total,
                'success_count': result.success,
                'config': json.dumps(config.config, ensure_ascii=False),
            })

        if progress_reporter:
            if result:
                progress_reporter.advance_step(
                    "收尾",
                    f"完成: {result.success} 成功, {result.failed} 失败, {result.skipped} 跳过",
                )
            else:
                progress_reporter.advance_step("收尾", "下载失败或链接无效")

        return result
    finally:
        if should_close_client and api_client:
            await api_client.close()


async def main_async(args):
    display.show_banner()

    if args.config:
        config_path = args.config
    else:
        config_path = 'config.yml'

    if not Path(config_path).exists():
        display.print_error(f"Config file not found: {config_path}")
        return

    config = ConfigLoader(config_path)

    if args.url:
        urls = args.url if isinstance(args.url, list) else [args.url]
    else:
        urls = config.get_links()

    if args.path:
        config.update(path=args.path)

    if args.thread:
        config.update(thread=args.thread)

    if not config.validate():
        display.print_error("Invalid configuration: missing required fields")
        return

    cookies = config.get_cookies()
    cookie_manager = CookieManager()
    cookie_manager.set_cookies(cookies)

    if not cookie_manager.validate_cookies():
        display.print_warning("Cookies may be invalid or incomplete")

    database = None
    if config.get('database'):
        database = Database()
        await database.initialize()
        display.print_success("Database initialized")

    display.print_info(f"Found {len(urls)} URL(s) to process")

    # 初始化扫描记录管理器（智能跳过N小时内已成功处理的用户）
    data_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
    skip_threshold_hours = config.get("skip_threshold_hours", 4)
    # 如果设置为空或0，则不限制跳过
    if skip_threshold_hours is None or skip_threshold_hours == 0:
        skip_threshold_hours = 0
    
    scan_record_manager = ScanRecordManager(
        os.path.join(data_dir, 'scan_records.json'),
        skip_threshold_hours=skip_threshold_hours
    )
    scan_record_manager.print_summary()

    progress_config = config.get("progress", {}) or {}
    quiet_by_config = _as_bool(progress_config.get("quiet_logs", True), default=True)
    quiet_progress_logs = quiet_by_config and not (args.verbose or args.show_warnings)
    if quiet_progress_logs:
        # Progress 运行期间若有大量错误日志会触发 rich 反复重绘，导致屏幕出现重复块。
        # 默认静默控制台日志，下载完成后再恢复。
        set_console_log_level(logging.CRITICAL)

    display.start_download_session(len(urls))
    url_results = []
    skipped_urls = []
    
    # 批量处理所有URL
    async with DouyinAPIClient(cookie_manager.get_cookies()) as api_client:
        for i, url in enumerate(urls, 1):
            display.start_url(i, len(urls), url)

            # 智能跳过检查：如果N小时内已成功处理，跳过该链接
            if scan_record_manager.should_skip(url):
                record = scan_record_manager.get_record(url)
                username = record.get('username', '未知') if record else '未知'
                sec_uid = record.get('sec_uid', '') if record else ''
                skipped_urls.append((url, username, sec_uid, "skipped"))
                display.skip_url(scan_record_manager.get_skip_reason(url))
                continue
            
            # 解析URL获取用户ID（只做一次）
            resolved_url = url
            parsed = None
            
            if url.startswith('https://v.douyin.com'):
                resolved_url = await api_client.resolve_short_url(url)
                if not resolved_url:
                    url_results.append((url, None, "failed"))
                    display.fail_url("短链解析失败")
                    scan_record_manager.mark_parse_failed(url)
                    continue

            # 获取扫描记录，用于增量更新
            record = scan_record_manager.get_record(url)
            
            parsed = URLParser.parse(resolved_url)
            if not parsed:
                url_results.append((url, None, "failed"))
                display.fail_url("URL解析失败")
                scan_record_manager.mark_parse_failed(url)
                continue

            # 执行下载（复用API客户端和预解析结果）
            # 获取上次最新视频时间，支持增量更新
            last_video_time = record.get('last_video_time', '') if record else ''
            result = await download_url(
                url,
                config,
                cookie_manager,
                database,
                progress_reporter=display,
                last_scan_time=last_video_time,  # 使用 last_video_time 作为增量更新阈值
                parsed_url=parsed,
                api_client=api_client,
            )
            if result:
                url_results.append((url, result, "success"))
                display.complete_url(result)
                
                # 更新本地扫描记录
                author_name = getattr(result, 'author_name', '') or '未知'
                sec_uid = getattr(result, 'sec_uid', '') or ''
                last_video_time = getattr(result, 'last_video_time', '') or ''
                scan_record_manager.update_record(
                    url,
                    author_name,
                    sec_uid,
                    result.total,
                    result.success,
                    result.failed,
                    result.skipped,
                    False,
                    last_video_time
                )
            else:
                url_results.append((url, None, "failed"))
                display.fail_url("下载失败或链接无效")
                scan_record_manager.mark_parse_failed(url)
    
    display.stop_download_session()
    if quiet_progress_logs:
        set_console_log_level(logging.ERROR)

    display.show_final_summary(url_results, config, skipped_urls)


def main():
    parser = argparse.ArgumentParser(description='Douyin Downloader - 抖音批量下载工具')
    parser.add_argument('-u', '--url', action='append', help='Download URL(s)')
    parser.add_argument('-c', '--config', help='Config file path (default: config.yml)')
    parser.add_argument('-p', '--path', help='Save path')
    parser.add_argument('-t', '--thread', type=int, help='Thread count')
    parser.add_argument('--show-warnings', action='store_true', help='Show warning logs in console')
    parser.add_argument('-v', '--verbose', action='store_true', help='Enable verbose console logs')
    parser.add_argument('--version', action='version', version='2.0.0')
    
    # 失败视频管理命令
    parser.add_argument('--list-failed', action='store_true', help='List all failed videos')
    parser.add_argument('--mark-processed', help='Mark a video as processed by aweme_id')
    parser.add_argument('--mark-skipped', help='Mark a video as skipped by aweme_id')
    parser.add_argument('--refresh-video-time', nargs='?', const=True, default=False, help='Refresh last_video_time for users without downloading (skips 4-hour limit). Optional: specify a URL to refresh single user')

    args = parser.parse_args()

    # 处理失败视频管理命令
    if args.list_failed:
        list_failed_videos()
        return
    elif args.mark_processed:
        mark_failed_video(args.mark_processed, 'processed')
        return
    elif args.mark_skipped:
        mark_failed_video(args.mark_skipped, 'skipped')
        return
    elif args.refresh_video_time is not False:
        # args.refresh_video_time 为 True 时刷新所有用户，为字符串时刷新指定URL
        asyncio.run(refresh_video_time_for_all_users(args.refresh_video_time if isinstance(args.refresh_video_time, str) else None))
        return

    if args.verbose:
        set_console_log_level(logging.INFO)
    elif args.show_warnings:
        set_console_log_level(logging.WARNING)
    else:
        set_console_log_level(logging.ERROR)

    try:
        asyncio.run(main_async(args))
    except KeyboardInterrupt:
        display.print_warning("\nDownload interrupted by user")
        sys.exit(0)
    except Exception as e:
        display.print_error(f"Fatal error: {e}")
        logger.exception("Fatal error occurred")
        sys.exit(1)


def list_failed_videos():
    """列出所有失败的视频"""
    failed_manager = FailedVideoManager()
    failed_videos = failed_manager.get_failed_videos(status='failed')
    
    if not failed_videos:
        print("没有未处理的失败视频")
        return
    
    print(f"未处理的失败视频数量: {len(failed_videos)}")
    print("-" * 80)
    for i, video in enumerate(failed_videos, 1):
        print(f"{i}. aweme_id: {video['aweme_id']}")
        print(f"   标题: {video['title']}")
        print(f"   作者: {video['author_name']}")
        print(f"   失败时间: {video['failed_time']}")
        print(f"   错误信息: {video.get('error_message', '未知')}")
        print("-" * 80)


def mark_failed_video(aweme_id: str, status: str):
    """标记失败视频的状态"""
    failed_manager = FailedVideoManager()
    
    if status == 'processed':
        success = failed_manager.mark_as_processed(aweme_id)
        action = '已处理'
    else:
        success = failed_manager.mark_as_skipped(aweme_id)
        action = '跳过'
        
        # 如果标记为跳过，同时记录到数据库（模拟已下载）
        if success:
            try:
                import asyncio
                import aiosqlite
                from datetime import datetime
                
                # 异步插入记录，表示该视频已"下载"，后续会跳过
                async def mark_in_db():
                    async with aiosqlite.connect('dy_downloader.db') as db:
                        await db.execute('''
                            INSERT OR IGNORE INTO aweme 
                            (aweme_id, aweme_type, title, author_id, author_name, create_time, download_time)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        ''', (aweme_id, 'video', '已跳过', '', '', 0, int(datetime.now().timestamp())))
                        await db.commit()
                
                asyncio.run(mark_in_db())
                print(f"同时将视频 {aweme_id} 记录到数据库，后续下载将跳过")
            except Exception as e:
                print(f"记录到数据库失败: {e}")
    
    if success:
        print(f"成功将视频 {aweme_id} 标记为 {action}")
    else:
        print(f"未找到视频 {aweme_id}")


async def refresh_video_time_for_all_users(target_url: str = None):
    """刷新用户的 last_video_time，不进行下载，跳过4小时限制
    
    Args:
        target_url: 可选，指定要刷新的用户URL，不指定则刷新所有用户
    """
    display.show_banner()
    
    config_path = 'config.yml'
    if not Path(config_path).exists():
        display.print_error(f"Config file not found: {config_path}")
        return
    
    config = ConfigLoader(config_path)
    
    cookies = config.get_cookies()
    cookie_manager = CookieManager()
    cookie_manager.set_cookies(cookies)
    
    # 加载扫描记录
    data_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
    scan_record_manager = ScanRecordManager(
        os.path.join(data_dir, 'scan_records.json'),
        skip_threshold_hours=0  # 跳过限制
    )
    
    records = scan_record_manager.get_all_records()
    if not records:
        display.print_info("没有扫描记录需要刷新")
        return
    
    # 如果指定了目标URL，只处理该URL
    if target_url:
        if target_url in records:
            records_to_process = {target_url: records[target_url]}
        else:
            display.print_error(f"未找到URL: {target_url}")
            return
    else:
        records_to_process = records
    
    display.print_info(f"找到 {len(records_to_process)} 条记录需要刷新 last_video_time")
    
    success_count = 0
    failed_count = 0
    
    async with DouyinAPIClient(cookie_manager.get_cookies()) as api_client:
        for i, (url, record) in enumerate(records_to_process.items(), 1):
            sec_uid = record.get('sec_uid', '')
            username = record.get('username', '未知')
            
            if not sec_uid:
                display.print_warning(f"[{i}/{len(records_to_process)}] 跳过 {username} - 缺少 sec_uid")
                continue
            
            display.print_info(f"[{i}/{len(records_to_process)}] 正在刷新 {username}")
            
            try:
                # 创建下载器
                file_manager = FileManager(config.get('path'))
                downloader = DownloaderFactory.create(
                    'user',
                    config,
                    api_client,
                    file_manager,
                    cookie_manager,
                    database=None,
                    rate_limiter=RateLimiter(max_per_second=2),
                    retry_handler=None,
                    queue_manager=QueueManager(max_workers=1),
                )
                
                if not downloader:
                    display.print_error(f"创建下载器失败")
                    failed_count += 1
                    continue
                
                # 调用刷新方法
                result = await downloader.refresh_last_video_time({'sec_uid': sec_uid})
                
                if result.last_video_time:
                    # 只更新 last_video_time，保留原有统计数据
                    scan_record_manager.update_last_video_time(
                        url,
                        result.last_video_time,
                        result.author_name  # 可选更新用户名
                    )
                    display.print_success(f"  ✓ 刷新成功: {result.last_video_time}")
                    success_count += 1
                else:
                    display.print_error(f"  ✗ 刷新失败: 无法获取视频时间")
                    failed_count += 1
            except Exception as e:
                display.print_error(f"  ✗ 刷新失败: {e}")
                failed_count += 1
    
    display.print_info(f"\n刷新完成: 成功 {success_count} 条, 失败 {failed_count} 条")


if __name__ == '__main__':
    main()

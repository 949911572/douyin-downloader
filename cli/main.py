import asyncio
import argparse
import json
import logging
import os
import random
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from config import ConfigLoader
from auth import CookieManager
from storage import Database, FileManager
from control import QueueManager, RateLimiter, RetryHandler
from core import DouyinAPIClient, URLParser, DownloaderFactory, VideoDownloader
from cli.progress_display import ProgressDisplay
from utils.logger import setup_logger, set_console_log_level
from utils.scan_record_manager import ScanRecordManager
from utils.failed_video_manager import FailedVideoManager
from utils.error_logger import ErrorLogger

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
    last_video_time: str = None,  # 上次最新视频时间，用于增量更新
    parsed_url: Dict[str, Any] = None,  # 预解析的URL结果
    api_client=None,  # 复用的API客户端
    error_logger: ErrorLogger = None,
):
    if progress_reporter:
        progress_reporter.advance_step("初始化", "创建下载组件")
    file_manager = FileManager(config.get('path'))
    rate_limiter = RateLimiter(max_per_second=2)
    retry_handler = RetryHandler(max_retries=config.get('retry_times', 3))
    queue_manager = QueueManager(max_workers=int(config.get('thread', 1) or 1))

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
            error_logger=error_logger,
        )

        if not downloader:
            if progress_reporter:
                progress_reporter.update_step("创建下载器", "未找到匹配下载器")
            display.print_error(f"No downloader found for type: {parsed_url['type']}")
            return None

        if progress_reporter:
            progress_reporter.advance_step("执行下载", "开始拉取与下载资源")
        
        # 传递 last_video_time 支持增量更新
        if last_video_time and parsed_url['type'] == 'user':
            result = await downloader.download(parsed_url, last_video_time)
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
    shared_error_logger = ErrorLogger()
    
    # 读取URL间延迟配置
    url_delay_config = config.get("url_delay", {}) or {}
    url_delay_enabled = _as_bool(url_delay_config.get("enabled", False), default=False)
    url_delay_min = float(url_delay_config.get("min_seconds", 2))
    url_delay_max = float(url_delay_config.get("max_seconds", 5))
    
    # 批量处理所有URL
    async with DouyinAPIClient(cookie_manager.get_cookies()) as api_client:
        for i, url in enumerate(urls, 1):
            # 解析URL获取用户ID（只做一次）
            resolved_url = url
            
            if url.startswith('https://v.douyin.com'):
                resolved_url = await api_client.resolve_short_url(url)
                if not resolved_url:
                    url_results.append((url, None, "failed"))
                    display.start_url(i, len(urls), url)
                    display.fail_url("短链解析失败")
                    scan_record_manager.mark_parse_failed(url)
                    continue

            display.start_url(i, len(urls), resolved_url)

            # URL间随机延迟（第一个URL不延迟）
            if i > 1 and url_delay_enabled:
                delay = random.uniform(url_delay_min, url_delay_max)
                display.print_info(f"等待 {delay:.1f} 秒后处理下一个链接...")
                await asyncio.sleep(delay)

            # 智能跳过检查：如果N小时内已成功处理，跳过该链接
            if scan_record_manager.should_skip(url):
                record = scan_record_manager.get_record(url)
                username = record.get('username', '未知') if record else '未知'
                sec_uid = record.get('sec_uid', '') if record else ''
                skipped_urls.append((url, username, sec_uid, "skipped"))
                display.skip_url(scan_record_manager.get_skip_reason(url))
                continue
            
            parsed = None

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
                last_video_time=last_video_time,  # 使用 last_video_time 作为增量更新阈值
                parsed_url=parsed,
                api_client=api_client,
                error_logger=shared_error_logger,
            )
            if result:
                url_results.append((url, result, "success"))
                display.complete_url(result)
                
                # 只有用户主页链接才更新扫描记录（单视频链接不写入 scan_records.json）
                if parsed['type'] == 'user':
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
                # 只有用户主页链接才记录失败状态（单视频链接不写入 scan_records.json）
                if parsed['type'] == 'user':
                    scan_record_manager.mark_parse_failed(url)
    
    display.stop_download_session()
    if quiet_progress_logs:
        set_console_log_level(logging.ERROR)

    display.show_final_summary(url_results, config, skipped_urls)
    if shared_error_logger.get_error_count() > 0:
        print(f"\n详细错误日志已保存到: {os.path.abspath(shared_error_logger._session_file)}")


def main():
    from utils.environment_check import run_environment_check
    
    if not run_environment_check():
        sys.exit(1)
    
    parser = argparse.ArgumentParser(description='Douyin Downloader - 抖音批量下载工具')
    parser.add_argument('-u', '--url', action='append', help='Download URL(s)')
    parser.add_argument('-c', '--config', help='Config file path (default: config.yml)')
    parser.add_argument('-p', '--path', help='Save path')
    parser.add_argument('-t', '--thread', type=int, help='Thread count')
    parser.add_argument('--show-warnings', action='store_true', help='Show warning logs in console')
    parser.add_argument('-v', '--verbose', action='store_true', help='Enable verbose console logs')
    parser.add_argument('--version', action='version', version='2.1.0')
    
    # 失败视频管理命令
    parser.add_argument('--list-failed', action='store_true', help='List all failed videos')
    parser.add_argument('--retry-failed', action='store_true', help='Retry all failed videos')
    parser.add_argument('--mark-skipped', help='Mark a video as skipped by aweme_id')
    parser.add_argument('--mark-all-failed-skipped', action='store_true', help='Mark all failed videos as skipped')

    args = parser.parse_args()

    # 处理失败视频管理命令
    if args.list_failed:
        list_failed_videos()
        return
    elif args.retry_failed:
        config_path = args.config or 'config.yml'
        asyncio.run(retry_failed_videos(config_path))
        return
    elif args.mark_skipped:
        mark_failed_video(args.mark_skipped)
        return
    elif args.mark_all_failed_skipped:
        asyncio.run(mark_all_failed_as_skipped())
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
        print(f"   链接: {video.get('url', '')}")
        print(f"   失败时间: {video['failed_time']}")
        print(f"   错误信息: {video.get('error_message', '未知')}")
        print("-" * 80)


async def retry_failed_videos(config_path: str = 'config.yml'):
    """重试所有失败的视频"""
    failed_manager = FailedVideoManager()
    error_logger = ErrorLogger()
    failed_videos = failed_manager.get_failed_videos(status='failed')
    
    if not failed_videos:
        print("没有未处理的失败视频")
        return
    
    print(f"找到 {len(failed_videos)} 个失败视频，开始重试...")
    print("-" * 80)
    
    config = ConfigLoader(config_path)
    cookies = config.get_cookies()
    cookie_manager = CookieManager()
    cookie_manager.set_cookies(cookies)
    database = Database()
    
    await database.initialize()
    
    success_count = 0
    fail_count = 0
    
    async with DouyinAPIClient(cookie_manager.get_cookies()) as api_client:
        for i, video in enumerate(failed_videos, 1):
            aweme_id = video['aweme_id']
            author_name = video.get('author_name', '未知')
            print(f"\n[{i}/{len(failed_videos)}] 重试: {aweme_id} ({author_name})")
            
            try:
                detail = await api_client.get_video_detail(aweme_id)
                if not detail:
                    print(f"  ✗ 无法获取视频详情，可能已删除或私密")
                    error_logger.log_error(
                        aweme_id,
                        "retry_api_detail_failed",
                        "无法获取视频详情，可能已删除或私密",
                        extra={
                            "source": "retry_failed",
                            "author_name": author_name,
                            "original_error": video.get('error_message', ''),
                        },
                    )
                    fail_count += 1
                    continue
                
                file_manager = FileManager(config.get('path'))
                rate_limiter = RateLimiter(max_per_second=2)
                retry_handler = RetryHandler(max_retries=config.get('retry_times', 3))
                queue_manager = QueueManager(max_workers=int(config.get('thread', 1) or 1))
                
                downloader = VideoDownloader(
                    config=config,
                    api_client=api_client,
                    file_manager=file_manager,
                    cookie_manager=cookie_manager,
                    database=database,
                    rate_limiter=rate_limiter,
                    retry_handler=retry_handler,
                    queue_manager=queue_manager,
                    error_logger=error_logger,
                )
                
                result = await downloader.download(detail)
                if result.success > 0:
                    total_files = sum(f.get("file_count", 1) for f in result.downloaded_files)
                    print(f"  ✓ 下载成功: {total_files} 个文件")
                    failed_manager.mark_as_processed(aweme_id)
                    success_count += 1
                elif result.skipped > 0:
                    print(f"  → 已跳过: 数据库已有记录，跳过下载")
                else:
                    if result.failed_items:
                        for aweme_id_failed, error_msg in result.failed_items:
                            print(f"  ✗ 下载失败: {error_msg}")
                            error_logger.log_error(
                                aweme_id_failed,
                                "retry_download_failed",
                                error_msg,
                                extra={
                                    "source": "retry_failed",
                                    "author_name": author_name,
                                    "original_error": video.get('error_message', ''),
                                },
                            )
                            fail_count += 1
                    else:
                        print(f"  ✗ 下载失败: 未知原因")
                        error_logger.log_error(
                            aweme_id,
                            "retry_download_failed_unknown",
                            "未知原因",
                            extra={
                                "source": "retry_failed",
                                "author_name": author_name,
                                "original_error": video.get('error_message', ''),
                            },
                        )
                        fail_count += 1
                    
            except Exception as e:
                import traceback
                print(f"  ✗ 重试异常: {e}")
                traceback.print_exc()
                error_logger.log_error(
                    aweme_id,
                    "retry_exception",
                    str(e),
                    extra={
                        "source": "retry_failed",
                        "author_name": author_name,
                        "original_error": video.get('error_message', ''),
                    },
                    exc_info=e,
                )
                fail_count += 1
    
    print("\n" + "=" * 80)
    print(f"重试完成: 成功 {success_count} 个, 失败 {fail_count} 个")
    print("=" * 80)
    if error_logger.get_error_count() > 0:
        print(f"\n详细错误日志已保存到: {os.path.abspath(error_logger._session_file)}")


def mark_failed_video(aweme_id: str):
    """标记单个失败视频为跳过"""
    failed_manager = FailedVideoManager()
    success = failed_manager.mark_as_skipped(aweme_id)
    
    if success:
        try:
            async def mark_in_db():
                from storage import Database
                database = Database()
                await database.initialize()
                await database.add_skipped_aweme(aweme_id)
            
            asyncio.run(mark_in_db())
            print(f"成功将视频 {aweme_id} 标记为跳过，已记录到数据库")
        except Exception as e:
            print(f"标记成功，但记录到数据库失败: {e}")
    else:
        print(f"未找到视频 {aweme_id} 的失败记录")


async def mark_all_failed_as_skipped():
    """批量标记所有失败视频为跳过"""
    import shutil
    
    db_path = 'dy_downloader.db'
    backup_dir = os.path.join('data', 'db_backup', datetime.now().strftime('%Y%m%d_%H%M'))
    os.makedirs(backup_dir, exist_ok=True)
    backup_path = os.path.join(backup_dir, 'dy_downloader.db')
    
    if os.path.exists(db_path):
        shutil.copy2(db_path, backup_path)
        print(f"✓ 数据库已备份到: {backup_path}")
    else:
        print(f"⚠ 未找到数据库文件: {db_path}")
    
    failed_manager = FailedVideoManager()
    failed_videos = failed_manager.get_failed_videos(status='failed')
    
    if not failed_videos:
        print("没有未处理的失败视频")
        return
    
    print(f"找到 {len(failed_videos)} 个失败视频，准备标记为跳过")
    print("-" * 80)
    
    database = Database()
    await database.initialize()
    
    success_count = 0
    fail_count = 0
    
    for video in failed_videos:
        aweme_id = video['aweme_id']
        author_name = video.get('author_name', '')
        
        try:
            failed_manager.mark_as_skipped(aweme_id)
            await database.add_skipped_aweme(aweme_id, author_name)
            success_count += 1
            print(f"✓ {aweme_id} - {author_name}")
        except Exception as e:
            fail_count += 1
            print(f"✗ {aweme_id} - {e}")
    
    print("-" * 80)
    print(f"完成: 成功标记 {success_count} 个, 失败 {fail_count} 个")


if __name__ == '__main__':
    main()

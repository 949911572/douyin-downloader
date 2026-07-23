"""
失败视频管理 CLI 命令模块

封装失败视频的列表展示、重试、跳过标记等 CLI 操作。
"""

from __future__ import annotations

import asyncio
import os
import shutil
import traceback
from datetime import datetime
from typing import Optional

from config import ConfigLoader
from auth import CookieManager
from storage import Database, FileManager
from control import QueueManager, RateLimiter, RetryHandler
from core import DouyinAPIClient, VideoDownloader
from utils.error_logger import ErrorLogger
from utils.failed_video_manager import FailedVideoManager


def list_failed_videos() -> None:
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


async def retry_failed_videos(config_path: str = 'config.yml') -> None:
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
        print(f"\n详细错误日志已保存到: {os.path.abspath(error_logger.session_file)}")


def mark_failed_video(aweme_id: str) -> None:
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


async def mark_all_failed_as_skipped() -> None:
    """批量标记所有失败视频为跳过"""
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

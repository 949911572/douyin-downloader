"""
单视频下载器模块
负责下载单个抖音视频，支持：
- 视频详情获取
- 视频资源下载（视频、封面、音乐等）
- 失败重试和错误记录
"""

from typing import Any, Dict, Optional

from core.downloader_base import BaseDownloader, DownloadResult
from utils.logger import setup_logger
from utils.failed_video_manager import FailedVideoManager

logger = setup_logger('VideoDownloader')


class VideoDownloader(BaseDownloader):
    async def download(
        self,
        parsed_url: Dict[str, Any],
        last_video_time: Optional[str] = None,
    ) -> DownloadResult:
        result = DownloadResult()

        aweme_id = parsed_url.get('aweme_id')
        if not aweme_id:
            logger.error("No aweme_id found in parsed URL")
            return result

        result.total = 1
        self._progress_set_item_total(1, "单视频下载")
        self._progress_update_step("下载作品", "单视频资源下载中")

        if not await self._should_download(aweme_id):
            logger.info(f"Video {aweme_id} already downloaded, skipping")
            result.skipped += 1
            self._progress_advance_item("skipped", str(aweme_id))
            return result

        await self.rate_limiter.acquire()

        aweme_data = await self.api_client.get_video_detail(aweme_id)
        if not aweme_data:
            logger.error(f"Failed to get video detail: {aweme_id}")
            self.error_logger.log_error(
                aweme_id,
                "api_detail_failed",
                "Failed to get video detail from API",
                extra={"source": "video_downloader"},
            )
            result.failed += 1
            result.failed_items.append((aweme_id, "获取视频详情失败"))
            self._progress_advance_item("failed", str(aweme_id))
            
            failed_manager = FailedVideoManager()
            failed_manager.record_failed_video(
                url=f"https://www.douyin.com/video/{aweme_id}",
                aweme_id=aweme_id,
                title="",
                author_name="unknown",
                sec_uid="",
                error_message="获取视频详情失败",
            )
            return result

        author = aweme_data.get('author', {})
        author_name = author.get('nickname', 'unknown')
        result.author_name = author_name
        
        desc = aweme_data.get('desc', '') or ''
        sec_uid = author.get('sec_uid', '') or ''

        asset_result = await self._download_aweme(aweme_data)
        if asset_result["success"]:
            result.success += 1
            self._progress_advance_item("success", str(aweme_id))
        else:
            error_message = self._extract_failure_reason(aweme_data, asset_result)
            
            result.failed += 1
            result.failed_items.append((aweme_id, error_message))
            self._progress_advance_item("failed", str(aweme_id))
            
            self.error_logger.log_error(
                aweme_id,
                "asset_download_failed",
                error_message,
                aweme_data=aweme_data,
                extra={"source": "video_downloader"},
            )
            
            failed_manager = FailedVideoManager()
            failed_manager.record_failed_video(
                url=f"https://www.douyin.com/video/{aweme_id}",
                aweme_id=aweme_id,
                title=desc,
                author_name=author_name,
                sec_uid=sec_uid,
                error_message=error_message,
            )

        result.downloaded_files.append(asset_result)
        return result

    def _extract_failure_reason(self, aweme_data: Dict[str, Any], asset_result: Dict[str, Any]) -> str:
        video = aweme_data.get("video", {})
        play_addr = video.get("play_addr", {})
        url_list = play_addr.get("url_list", [])
        uri = play_addr.get("uri") or video.get("vid") or video.get("download_addr", {}).get("uri")
        
        if not url_list and not uri:
            return "视频无可播放URL"
        
        media_type = self._detect_media_type(aweme_data)
        if media_type == "video":
            video_info = self._build_no_watermark_url(aweme_data)
            if not video_info:
                return "无法构建无水印视频URL"
        elif media_type == "gallery":
            image_urls = self._collect_image_urls(aweme_data)
            if not image_urls:
                return "图文作品无图片URL"
        else:
            return f"不支持的媒体类型: {media_type}"
        
        error = asset_result.get("error", "")
        if error:
            return error
        
        return "下载失败"

    async def _download_aweme(self, aweme_data: Dict[str, Any]) -> dict:
        author = aweme_data.get('author', {})
        author_name = author.get('nickname', 'unknown')
        return await self._download_aweme_assets(aweme_data, author_name)

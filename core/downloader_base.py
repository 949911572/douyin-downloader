"""
下载器基类模块
定义下载器的抽象接口和通用功能，包括：
- BaseDownloader: 所有下载器的抽象基类
- DownloadResult: 下载结果数据结构
- ProgressReporter: 进度报告协议

所有具体下载器（VideoDownloader、UserDownloader等）都继承自BaseDownloader
"""

import json
import re
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Protocol, Tuple, TypedDict
from urllib.parse import urlparse

from auth import CookieManager
from config import ConfigLoader
from control import QueueManager, RateLimiter, RetryHandler
from core.api_client import DouyinAPIClient
from core.transcript_manager import TranscriptManager
from storage import Database, FileManager, MetadataHandler
from utils.error_logger import ErrorLogger
from utils.logger import setup_logger
from utils.validators import sanitize_filename

logger = setup_logger("BaseDownloader")


class ProgressReporter(Protocol):
    def update_step(self, step: str, detail: str = "") -> None:
        ...

    def set_item_total(self, total: int, detail: str = "") -> None:
        ...

    def advance_item(self, status: str, detail: str = "") -> None:
        ...


class DownloadResult:
    def __init__(self):
        self.total: int = 0
        self.success: int = 0
        self.failed: int = 0
        self.skipped: int = 0
        self.failed_items: List[Tuple[str, str]] = []  # [(aweme_id, error_desc), ...]
        self.author_name: str = ""    # 抖音帐号名
        self.sec_uid: str = ""        # 用户唯一标识
        self.last_video_time: str = ""  # 最新视频上传时间
        self.downloaded_files: List[Dict[str, Any]] = []  # [{file_name, file_size, status, desc, publish_date}, ...]
        self.pagination_restricted: bool = False  # 分页是否受限，需要手动浏览器扫描

    def __str__(self):
        return f"Total: {self.total}, Success: {self.success}, Failed: {self.failed}, Skipped: {self.skipped}"


class AssetDownloadResult(TypedDict):
    success: bool
    file_name: str
    file_size: int
    file_count: int
    desc: str
    publish_date: str
    aweme_id: str
    save_dir: str
    error: Optional[str]


class BaseDownloader(ABC):
    def __init__(
        self,
        config: ConfigLoader,
        api_client: DouyinAPIClient,
        file_manager: FileManager,
        cookie_manager: CookieManager,
        database: Optional[Database] = None,
        rate_limiter: Optional[RateLimiter] = None,
        retry_handler: Optional[RetryHandler] = None,
        queue_manager: Optional[QueueManager] = None,
        progress_reporter: Optional[ProgressReporter] = None,
        error_logger: Optional[ErrorLogger] = None,
    ):
        self.config = config
        self.api_client = api_client
        self.file_manager = file_manager
        self.cookie_manager = cookie_manager
        self.database = database
        self.rate_limiter = rate_limiter or RateLimiter()
        # 从配置中读取重试参数
        retry_config = self.config.get("retry", {})
        max_retries = int(retry_config.get("max_retries", 3))
        retry_delay = int(retry_config.get("delay", 5))
        self.retry_handler = retry_handler or RetryHandler(max_retries=max_retries, retry_delay=retry_delay)
        thread_count = int(self.config.get("thread", 1) or 1)
        self.queue_manager = queue_manager or QueueManager(max_workers=thread_count)
        self.progress_reporter = progress_reporter
        self.metadata_handler = MetadataHandler()
        self.transcript_manager = TranscriptManager(
            self.config, self.file_manager, self.database
        )
        self.error_logger = error_logger or ErrorLogger()
        self._local_aweme_ids: Optional[set[str]] = None
        self._aweme_id_pattern = re.compile(r"(?<!\d)(\d{15,20})(?!\d)")
        self._local_media_suffixes = {
            ".mp4",
            ".jpg",
            ".jpeg",
            ".png",
            ".webp",
            ".gif",
            ".mp3",
            ".m4a",
        }
        # 控制终端错误日志量，避免进度条被大量日志打断后出现重复重绘。
        self._download_error_log_count = 0
        self._download_error_log_limit = 5

    def _progress_update_step(self, step: str, detail: str = "") -> None:
        if not self.progress_reporter:
            return
        try:
            self.progress_reporter.update_step(step, detail)
        except Exception as exc:
            logger.debug("Progress update_step failed: %s", exc)

    def _progress_set_item_total(self, total: int, detail: str = "") -> None:
        if not self.progress_reporter:
            return
        try:
            self.progress_reporter.set_item_total(total, detail)
        except Exception as exc:
            logger.debug("Progress set_item_total failed: %s", exc)

    def _progress_advance_item(self, status: str, detail: str = "") -> None:
        if not self.progress_reporter:
            return
        try:
            self.progress_reporter.advance_item(status, detail)
        except Exception as exc:
            logger.debug("Progress advance_item failed: %s", exc)

    def _log_download_error(self, log_fn, message: str) -> None:
        if self._download_error_log_count < self._download_error_log_limit:
            log_fn(message)
        elif self._download_error_log_count == self._download_error_log_limit:
            logger.error(
                "Too many download errors, switching to sampling mode (1 per 10)..."
            )
        elif self._download_error_log_count % 10 == 0:
            log_fn(message)
        self._download_error_log_count += 1

    def _download_headers(self, user_agent: Optional[str] = None) -> Dict[str, str]:
        headers = {
            "Referer": f"{self.api_client.BASE_URL}/",
            "Origin": self.api_client.BASE_URL,
            "Accept": "*/*",
        }

        headers["User-Agent"] = user_agent or self.api_client.headers.get(
            "User-Agent", ""
        )

        # 传递 Cookie，避免图片CDN返回403
        cookie_str = self.cookie_manager.get_cookie_string()
        if cookie_str:
            headers["Cookie"] = cookie_str

        return headers

    @abstractmethod
    async def download(
        self,
        parsed_url: Dict[str, Any],
        last_video_time: Optional[str] = None,
    ) -> DownloadResult:
        pass

    async def _should_download(self, aweme_id: str) -> bool:
        if self.database:
            if await self.database.is_downloaded(aweme_id):
                return False
        return True

    def _is_locally_downloaded(self, aweme_id: str) -> bool:
        if not aweme_id:
            return False

        if self._local_aweme_ids is None:
            self._build_local_aweme_index()

        assert self._local_aweme_ids is not None
        return aweme_id in self._local_aweme_ids

    def _build_local_aweme_index(self):
        base_path = self.file_manager.base_path
        aweme_ids: set[str] = set()

        if base_path.exists():
            for path in base_path.rglob("*"):
                if not path.is_file():
                    continue
                if path.suffix.lower() not in self._local_media_suffixes:
                    continue
                try:
                    if path.stat().st_size <= 0:
                        continue
                except OSError:
                    continue
                for match in self._aweme_id_pattern.finditer(path.name):
                    aweme_ids.add(match.group(1))

        self._local_aweme_ids = aweme_ids

    def _mark_local_aweme_downloaded(self, aweme_id: str):
        if not aweme_id:
            return

        if self._local_aweme_ids is None:
            self._local_aweme_ids = set()
        self._local_aweme_ids.add(aweme_id)

    def _limit_count(
        self, aweme_list: List[Dict[str, Any]], mode: str
    ) -> List[Dict[str, Any]]:
        number_config = self.config.get("number", {})
        limit = number_config.get(mode, 0)

        if limit > 0:
            return aweme_list[:limit]
        return aweme_list

    async def _download_aweme_assets(
        self,
        aweme_data: Dict[str, Any],
        author_name: str,
        mode: Optional[str] = None,
    ) -> AssetDownloadResult:
        aweme_id = aweme_data.get("aweme_id")
        if not aweme_id:
            logger.error("Missing aweme_id in aweme data")
            return {
                "success": False,
                "file_name": "",
                "file_size": 0,
                "file_count": 0,
                "desc": "",
                "publish_date": "",
                "aweme_id": "",
                "save_dir": "",
                "error": "Missing aweme_id",
            }

        desc = (aweme_data.get("desc", "no_title") or "").strip() or "no_title"
        if "\n" in desc:
            desc = desc.split("\n")[0].strip() or "no_title"
        publish_ts, publish_date = self._resolve_publish_time(
            aweme_data.get("create_time")
        )
        if not publish_date:
            publish_date = datetime.now().strftime("%Y-%m-%d")
            logger.warning(
                "Aweme %s missing/invalid create_time, fallback to current date %s",
                aweme_id,
                publish_date,
            )
        file_stem = sanitize_filename(f"{publish_date}_{desc}")

        save_dir = self.file_manager.get_save_path(
            author_name=author_name,
            mode=mode,
            aweme_title=desc,
            aweme_id=aweme_id,
            folderstyle=self.config.get("folderstyle", True),
            download_date=publish_date,
        )

        session = await self.api_client.get_session()
        media_type = self._detect_media_type(aweme_data)

        video_path: Optional[Path] = None
        first_image_path: Optional[Path] = None
        downloaded_files: List[Path] = []

        if media_type == "video":
            downloaded_files, video_path, error_result = await self._download_video_assets(
                aweme_data, aweme_id, desc, publish_date, file_stem, save_dir, session
            )
            if error_result is not None:
                return error_result
        elif media_type == "gallery":
            downloaded_files, first_image_path, error_result = await self._download_gallery_assets(
                aweme_data, aweme_id, desc, publish_date, file_stem, save_dir, session
            )
            if error_result is not None:
                return error_result
        else:
            logger.error(f"Unsupported media type for aweme {aweme_id}: {media_type}")
            self.error_logger.log_error(
                aweme_id,
                "unsupported_media_type",
                f"Unsupported media type: {media_type}",
                aweme_data=aweme_data,
            )
            return {
                "success": False,
                "file_name": f"{file_stem}.mp4",
                "file_size": 0,
                "file_count": 0,
                "desc": desc,
                "publish_date": publish_date,
                "aweme_id": aweme_id,
                "save_dir": str(save_dir),
                "error": f"不支持的媒体类型: {media_type}",
            }

        auxiliary_files = await self._download_auxiliary_resources(
            aweme_data, aweme_id, file_stem, save_dir, session
        )
        downloaded_files.extend(auxiliary_files)

        def _result(
            success: bool,
            file_path: Optional[Path] = None,
            expected_name: str = "",
            file_count: int = 0,
        ) -> AssetDownloadResult:
            """构建统一的返回值，从中提取主文件信息。

            Args:
                success: 下载是否成功
                file_path: 成功时的文件路径
                expected_name: 失败时的期望文件名
                file_count: 下载文件数量

            Returns:
                包含下载结果的字典
            """
            if success and file_path is not None and file_path.exists():
                return {
                    "success": True,
                    "file_name": file_path.name,
                    "file_size": file_path.stat().st_size,
                    "file_count": file_count or len(downloaded_files),
                    "desc": desc,
                    "publish_date": publish_date,
                    "aweme_id": aweme_id,
                    "save_dir": str(save_dir),
                    "error": None,
                }
            return {
                "success": False,
                "file_name": expected_name or f"{file_stem}.mp4",
                "file_size": 0,
                "file_count": 0,
                "desc": desc,
                "publish_date": publish_date,
                "aweme_id": aweme_id,
                "save_dir": str(save_dir),
                "error": None,
            }

        author = aweme_data.get("author", {})
        if self.database:
            metadata_json = json.dumps(aweme_data, ensure_ascii=False)
            await self.database.add_aweme(
                {
                    "aweme_id": aweme_id,
                    "aweme_type": media_type,
                    "title": desc,
                    "author_id": author.get("uid"),
                    "author_name": author.get("nickname", author_name),
                    "create_time": aweme_data.get("create_time"),
                    "file_path": str(save_dir),
                    "metadata": metadata_json,
                }
            )

        manifest_record = {
            "date": publish_date,
            "aweme_id": aweme_id,
            "author_name": author.get("nickname", author_name),
            "desc": desc,
            "media_type": media_type,
            "tags": self._extract_tags(aweme_data),
            "file_names": [path.name for path in downloaded_files],
            "file_paths": [self._to_manifest_path(path) for path in downloaded_files],
        }
        if publish_ts:
            manifest_record["publish_timestamp"] = publish_ts
        await self.metadata_handler.append_download_manifest(
            self.file_manager.base_path, manifest_record
        )

        if media_type == "video" and video_path is not None:
            transcript_result = await self.transcript_manager.process_video(
                video_path, aweme_id=aweme_id
            )
            transcript_status = transcript_result.get("status")
            if transcript_status == "skipped":
                reason = transcript_result.get("reason", "unknown")
                if reason != "disabled":
                    logger.info(
                        "Transcript skipped for aweme %s: %s",
                        aweme_id,
                        reason,
                    )
            elif transcript_status == "failed":
                logger.warning(
                    "Transcript failed for aweme %s: %s",
                    aweme_id,
                    transcript_result.get("error", "unknown"),
                )

        self._mark_local_aweme_downloaded(aweme_id)
        logger.info(f"Downloaded {media_type}: {desc} ({aweme_id})")
        if media_type == "video" and video_path is not None:
            return _result(True, file_path=video_path)
        if media_type == "gallery" and first_image_path is not None:
            return _result(True, file_path=first_image_path)
        return _result(True, file_path=downloaded_files[0] if downloaded_files else None)

    async def _download_video_assets(
        self,
        aweme_data: Dict[str, Any],
        aweme_id: str,
        desc: str,
        publish_date: str,
        file_stem: str,
        save_dir: Path,
        session: Any,
    ) -> Tuple[List[Path], Optional[Path], Optional[AssetDownloadResult]]:
        """Download video assets (video + cover + music).

        Returns:
            (downloaded_files, video_path, error_result). On success error_result is
            None; on failure it is a complete AssetDownloadResult with success=False
            that the caller can return verbatim.
        """
        downloaded_files: List[Path] = []

        video_info = self._build_no_watermark_url(aweme_data)
        if not video_info:
            logger.error(f"No playable video URL found for aweme {aweme_id}")
            self.error_logger.log_error(
                aweme_id,
                "no_video_url",
                "No playable video URL found",
                aweme_data=aweme_data,
                extra={"media_type": "video"},
            )
            return [], None, {
                "success": False,
                "file_name": f"{file_stem}.mp4",
                "file_size": 0,
                "file_count": 0,
                "desc": desc,
                "publish_date": publish_date,
                "aweme_id": aweme_id,
                "save_dir": str(save_dir),
                "error": "视频无可播放URL",
            }

        video_url, video_headers = video_info
        video_path = save_dir / f"{file_stem}.mp4"

        download_success, download_error = await self._download_with_retry(
            video_url, video_path, session, headers=video_headers
        )

        if not download_success:
            logger.warning(f"Download failed, retrying with fresh video detail: {aweme_id}")
            fresh_detail = await self.api_client.get_video_detail(aweme_id, suppress_error=True)
            if fresh_detail:
                fresh_video_info = self._build_no_watermark_url(fresh_detail)
                if fresh_video_info:
                    fresh_url, fresh_headers = fresh_video_info
                    download_success, download_error = await self._download_with_retry(
                        fresh_url, video_path, session, headers=fresh_headers
                    )
                    if download_success:
                        logger.info(f"Download succeeded with fresh URL: {aweme_id}")

        if not download_success:
            self.error_logger.log_error(
                aweme_id,
                "video_download_failed",
                f"Video download failed after retry: {download_error}",
                aweme_data=aweme_data,
                extra={"media_type": "video", "video_url": video_url[:120] if video_url else ""},
            )
            return [], None, {
                "success": False,
                "file_name": f"{file_stem}.mp4",
                "file_size": 0,
                "file_count": 0,
                "desc": desc,
                "publish_date": publish_date,
                "aweme_id": aweme_id,
                "save_dir": str(save_dir),
                "error": download_error,
            }
        downloaded_files.append(video_path)

        if self.config.get("cover"):
            cover_url = self._extract_first_url(
                aweme_data.get("video", {}).get("cover")
            )
            if cover_url:
                cover_path = save_dir / f"{file_stem}_cover.jpg"
                cover_success, _ = await self._download_with_retry(
                    cover_url,
                    cover_path,
                    session,
                    headers=self._download_headers(),
                    optional=True,
                )
                if cover_success:
                    downloaded_files.append(cover_path)
                else:
                    self.error_logger.log_error(
                        aweme_id,
                        "cover_download_failed",
                        "Failed downloading cover image",
                        aweme_data=aweme_data,
                    )

        if self.config.get("music"):
            music_url = self._extract_first_url(
                aweme_data.get("music", {}).get("play_url")
            )
            if music_url:
                music_path = save_dir / f"{file_stem}_music.mp3"
                music_success, _ = await self._download_with_retry(
                    music_url,
                    music_path,
                    session,
                    headers=self._download_headers(),
                    optional=True,
                )
                if music_success:
                    downloaded_files.append(music_path)
                else:
                    self.error_logger.log_error(
                        aweme_id,
                        "music_download_failed",
                        "Failed downloading background music",
                        aweme_data=aweme_data,
                    )

        return downloaded_files, video_path, None

    async def _download_gallery_assets(
        self,
        aweme_data: Dict[str, Any],
        aweme_id: str,
        desc: str,
        publish_date: str,
        file_stem: str,
        save_dir: Path,
        session: Any,
    ) -> Tuple[List[Path], Optional[Path], Optional[AssetDownloadResult]]:
        """Download gallery (image set) assets.

        Returns:
            (downloaded_files, first_image_path, error_result). On success error_result
            is None; on failure it is a complete AssetDownloadResult with success=False
            that the caller can return verbatim.
        """
        downloaded_files: List[Path] = []

        image_url_groups = self._collect_image_urls(aweme_data)
        if not image_url_groups:
            logger.error(f"No images found for aweme {aweme_id}")
            self.error_logger.log_error(
                aweme_id,
                "no_images_found",
                "No images found for gallery",
                aweme_data=aweme_data,
                extra={"media_type": "gallery"},
            )
            return [], None, {
                "success": False,
                "file_name": f"{file_stem}.jpg",
                "file_size": 0,
                "file_count": 0,
                "desc": desc,
                "publish_date": publish_date,
                "aweme_id": aweme_id,
                "save_dir": str(save_dir),
                "error": "图文作品无图片URL",
            }

        download_headers = self._download_headers()
        first_image_path: Optional[Path] = None
        for index, url_candidates in enumerate(image_url_groups, start=1):
            image_path: Optional[Path] = None
            success = False
            url_failures = []
            for image_url in url_candidates:
                suffix = Path(urlparse(image_url).path).suffix or ".jpg"
                image_path = save_dir / f"{file_stem}_{index}{suffix}"
                success, error_msg = await self.file_manager.download_file(
                    image_url, image_path, session, headers=download_headers
                )
                if success:
                    break
                url_failures.append({
                    "url": image_url[:150],
                    "error": error_msg,
                })
                logger.debug(
                    f"Image {index} URL failed ({error_msg}), trying next candidate: {aweme_id}"
                )
            if not success or image_path is None:
                error_msg = f"Failed downloading image {index} (tried {len(url_candidates)} URLs)"
                if url_failures:
                    last_error = url_failures[-1].get("error", "")
                    if last_error:
                        error_msg = last_error
                logger.error(
                    f"Failed downloading image {index} for aweme {aweme_id} "
                    f"(tried {len(url_candidates)} URLs)"
                )
                self.error_logger.log_error(
                    aweme_id,
                    "image_download_failed",
                    f"Failed downloading image {index} (tried {len(url_candidates)} URLs)",
                    aweme_data=aweme_data,
                    extra={
                        "media_type": "gallery",
                        "image_index": index,
                        "url_failures": url_failures,
                    },
                )
                return downloaded_files, None, {
                    "success": False,
                    "file_name": f"{file_stem}_{index}.jpg",
                    "file_size": 0,
                    "file_count": 0,
                    "desc": desc,
                    "publish_date": publish_date,
                    "aweme_id": aweme_id,
                    "save_dir": str(save_dir),
                    "error": error_msg,
                }
            downloaded_files.append(image_path)
            if first_image_path is None:
                first_image_path = image_path

        return downloaded_files, first_image_path, None

    async def _download_auxiliary_resources(
        self,
        aweme_data: Dict[str, Any],
        aweme_id: str,
        file_stem: str,
        save_dir: Path,
        session: Any,
    ) -> List[Path]:
        """Download auxiliary resources (avatar, metadata JSON). Returns list of downloaded files."""
        downloaded_files: List[Path] = []

        if self.config.get("avatar"):
            author = aweme_data.get("author", {})
            avatar_url = self._extract_first_url(author.get("avatar_larger"))
            if not avatar_url:
                avatar_url = self._extract_first_url(author.get("avatar_medium"))
            if not avatar_url:
                avatar_url = self._extract_first_url(author.get("avatar_thumb"))
            if avatar_url:
                avatar_path = save_dir / f"{file_stem}_avatar.jpg"
                avatar_success, _ = await self._download_with_retry(
                    avatar_url,
                    avatar_path,
                    session,
                    headers=self._download_headers(),
                    optional=True,
                )
                if avatar_success:
                    downloaded_files.append(avatar_path)
                else:
                    self.error_logger.log_error(
                        aweme_id,
                        "avatar_download_failed",
                        "Failed downloading author avatar",
                        aweme_data=aweme_data,
                    )

        if self.config.get("json"):
            json_path = save_dir / f"{file_stem}_data.json"
            if await self.metadata_handler.save_metadata(aweme_data, json_path):
                downloaded_files.append(json_path)
            else:
                self.error_logger.log_error(
                    aweme_id,
                    "json_save_failed",
                    "Failed saving metadata JSON file",
                    aweme_data=aweme_data,
                )

        return downloaded_files

    async def _download_with_retry(
        self,
        url: str,
        save_path: Path,
        session,
        *,
        headers: Optional[Dict[str, str]] = None,
        optional: bool = False,
    ) -> tuple:
        async def _task():
            success, error = await self.file_manager.download_file(
                url, save_path, session, headers=headers
            )
            if not success:
                raise RuntimeError(f"Download failed: {error}")
            return True

        try:
            await self.retry_handler.execute_with_retry(_task)
            return True, None
        except Exception as error:
            log_fn = logger.warning if optional else logger.error
            self._log_download_error(
                log_fn,
                f"Download error for {save_path.name}: {error}",
            )
            return False, str(error)

    def _detect_media_type(self, aweme_data: Dict[str, Any]) -> Literal["video", "gallery"]:
        image_post = aweme_data.get("image_post_info", {})
        images = image_post.get("images") if image_post else None
        if images is None:
            images = aweme_data.get("images") or []

        video_info = aweme_data.get("video", {})
        play_addr = video_info.get("play_addr", {})
        url_list = play_addr.get("url_list") or []
        has_video = bool(url_list)
        if has_video:
            first_url = url_list[0] if url_list else ""
            if "ies-music" in first_url or first_url.endswith(".mp3"):
                has_video = False

        if images and len(images) > 1:
            return "gallery"
        if has_video:
            return "video"
        if images:
            return "gallery"
        return "video"

    def _build_no_watermark_url(
        self, aweme_data: Dict[str, Any]
    ) -> Optional[Tuple[str, Dict[str, str]]]:
        video = aweme_data.get("video", {})
        play_addr = video.get("play_addr", {})
        url_candidates = [c for c in (play_addr.get("url_list") or []) if c]
        url_candidates.sort(key=lambda u: 0 if "watermark=0" in u else 1)

        fallback_candidate: Optional[Tuple[str, Dict[str, str]]] = None

        for candidate in url_candidates:
            parsed = urlparse(candidate)
            headers = self._download_headers()

            if parsed.netloc.endswith("douyin.com"):
                if "X-Bogus=" not in candidate:
                    signed_url, ua = self.api_client.sign_url(candidate)
                    headers = self._download_headers(user_agent=ua)
                    return signed_url, headers
                return candidate, headers

            fallback_candidate = (candidate, headers)

        uri = (
            play_addr.get("uri")
            or video.get("vid")
            or video.get("download_addr", {}).get("uri")
        )
        if uri:
            params = {
                "video_id": uri,
                "ratio": "1080p",
                "line": "0",
                "is_play_url": "1",
                "watermark": "0",
                "source": "PackSourceEnum_PUBLISH",
            }
            signed_url, ua = self.api_client.build_signed_path(
                "/aweme/v1/play/", params
            )
            return signed_url, self._download_headers(user_agent=ua)

        if fallback_candidate:
            return fallback_candidate

        return None

    def _collect_image_urls(self, aweme_data: Dict[str, Any]) -> List[List[str]]:
        image_url_groups: List[List[str]] = []
        image_post = aweme_data.get("image_post_info", {})
        images = image_post.get("images") or aweme_data.get("images") or []
        for item in images:
            url_list = item.get("url_list") if isinstance(item, dict) else None
            if url_list:
                image_url_groups.append(list(url_list))
        return image_url_groups

    @staticmethod
    def _extract_first_url(source: Any) -> Optional[str]:
        if isinstance(source, dict):
            url_list = source.get("url_list")
            if isinstance(url_list, list) and url_list:
                return url_list[0]
        elif isinstance(source, list) and source:
            return source[0]
        elif isinstance(source, str):
            return source
        return None

    @staticmethod
    def _resolve_publish_time(create_time: Any) -> Tuple[Optional[int], str]:
        if create_time in (None, ""):
            return None, ""

        try:
            publish_ts = int(create_time)
            if publish_ts <= 0:
                return None, ""
            return publish_ts, datetime.fromtimestamp(publish_ts).strftime("%Y-%m-%d")
        except (TypeError, ValueError, OSError, OverflowError):
            return None, ""

    @staticmethod
    def _extract_tags(aweme_data: Dict[str, Any]) -> List[str]:
        tags: List[str] = []

        def _append_tag(raw_tag: Any):
            if not raw_tag:
                return
            normalized_tag = str(raw_tag).strip().lstrip("#")
            if normalized_tag and normalized_tag not in tags:
                tags.append(normalized_tag)

        for item in aweme_data.get("text_extra") or []:
            if not isinstance(item, dict):
                continue
            _append_tag(item.get("hashtag_name"))
            _append_tag(item.get("tag_name"))

        for item in aweme_data.get("cha_list") or []:
            if not isinstance(item, dict):
                continue
            _append_tag(item.get("cha_name"))
            _append_tag(item.get("name"))

        desc = aweme_data.get("desc") or ""
        for hashtag in re.findall(r"#([^\s#]+)", desc):
            _append_tag(hashtag)

        return tags

    def _to_manifest_path(self, path: Path) -> str:
        try:
            return str(path.relative_to(self.file_manager.base_path))
        except ValueError:
            return str(path)

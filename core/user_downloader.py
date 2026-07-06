from typing import Any, Dict, List
from datetime import datetime

from core.downloader_base import BaseDownloader, DownloadResult
from utils.logger import setup_logger
from utils.failed_video_manager import FailedVideoManager
from utils.helpers import get_latest_video_time

logger = setup_logger("UserDownloader")


class UserDownloader(BaseDownloader):
    async def download(self, parsed_url: Dict[str, Any], last_video_time: str = None) -> DownloadResult:
        result = DownloadResult()

        sec_uid = parsed_url.get("sec_uid")
        if not sec_uid:
            logger.error("No sec_uid found in parsed URL")
            return result

        user_info = None
        
        # 先尝试从第一个视频获取用户信息（减少一次API调用）
        self._progress_update_step("获取作品列表", "尝试获取用户信息")
        first_page_data = await self.api_client.get_user_post(sec_uid, max_cursor=0, count=1)
        
        if not first_page_data:
            logger.error(f"Failed to get user post: {sec_uid}")
            self.error_logger.log_error(
                "unknown",
                "user_post_failed",
                f"获取用户作品列表失败: {sec_uid}",
                extra={"sec_uid": sec_uid, "source": "user_downloader"},
            )
            return result
        
        # 从返回结果中提取用户信息（如果有的话）
        user_info = first_page_data.get("user")
        if not user_info:
            # 如果没有用户信息，再单独调用 get_user_info
            self._progress_update_step("获取作者信息", f"sec_uid={sec_uid}")
            user_info = await self.api_client.get_user_info(sec_uid)
            if not user_info:
                logger.error(f"Failed to get user info: {sec_uid}")
                self.error_logger.log_error(
                    "unknown",
                    "user_info_failed",
                    f"获取用户信息失败: {sec_uid}",
                    extra={"sec_uid": sec_uid, "source": "user_downloader"},
                )
                return result
        else:
            self._progress_update_step("获取作者信息", "从作品列表中获取")

        modes = self.config.get("mode", ["post"])
        self._progress_update_step("下载模式", f"模式: {', '.join(modes)}")

        for mode in modes:
            if mode == "post":
                self._progress_update_step("下载模式", "开始处理 post 作品")
                mode_result = await self._download_user_post(sec_uid, user_info, last_video_time, first_page_data)
                result.total += mode_result.total
                result.success += mode_result.success
                result.failed += mode_result.failed
                result.skipped += mode_result.skipped
                result.downloaded_files.extend(mode_result.downloaded_files)
                if mode_result.author_name:
                    result.author_name = mode_result.author_name
                # 复制 last_video_time
                if mode_result.last_video_time:
                    result.last_video_time = mode_result.last_video_time

        # 确保 author_name 至少从 user_info 获取
        if not result.author_name:
            result.author_name = user_info.get("nickname", "unknown")
        
        # 设置 sec_uid
        result.sec_uid = sec_uid

        return result

    async def _download_user_post(
        self, sec_uid: str, user_info: Dict[str, Any], last_video_time: str = None, first_page_data: Dict[str, Any] = None
    ) -> DownloadResult:
        result = DownloadResult()
        aweme_list: List[Dict[str, Any]] = []
        max_cursor = 0
        has_more = True
        pagination_restricted = False

        increase_enabled = self.config.get("increase", {}).get("post", False)

        # 统一时间过滤阈值计算（使用 last_video_time 作为增量更新阈值）
        filter_timestamp = 0
        filter_reason = ""
        
        # 使用增量更新时间（last_video_time）
        if last_video_time:
            try:
                last_video_timestamp = int(datetime.strptime(last_video_time, '%Y-%m-%d %H:%M:%S').timestamp())
                filter_timestamp = last_video_timestamp
                filter_reason = f"上次最新视频时间 {last_video_time}"
                logger.info(f"增量更新模式：只获取 {last_video_time} 之后发布的视频")
            except ValueError:
                logger.warning(f"无效的上次最新视频时间格式: {last_video_time}")

        self._progress_update_step("拉取作品列表", "分页抓取中")
        
        # 如果已经有第一页数据，直接使用
        if first_page_data:
            data = first_page_data
            has_more = data.get("has_more", False)
            max_cursor = data.get("max_cursor", 0)
            
            not_login = (
                (data.get("not_login_module") or {}) if isinstance(data, dict) else {}
            )
            if isinstance(not_login, dict) and not_login.get("guide_login_tip_exist"):
                logger.warning(
                    "Detected login tip in user post response, pagination may be restricted"
                )

            aweme_items = data.get("aweme_list", [])
            if aweme_items:
                # 统一时间过滤逻辑
                if filter_timestamp > 0:
                    filtered_items = []
                    all_before = True
                    for item in aweme_items:
                        create_time = item.get("create_time", 0)
                        if create_time >= filter_timestamp:
                            filtered_items.append(item)
                            all_before = False
                    
                    if all_before:
                        logger.info(f"所有视频均早于 {filter_reason}，停止分页")
                        has_more = False
                    
                    aweme_items = filtered_items
                
                aweme_list.extend(aweme_items)
                self._progress_update_step(
                    "拉取作品列表", f"已抓取 {len(aweme_list)} 条"
                )
                
                if max_cursor == 0:
                    has_more = False
        
        while has_more:
            await self.rate_limiter.acquire()

            request_cursor = max_cursor
            data = await self.api_client.get_user_post(sec_uid, request_cursor)
            if not data:
                break

            not_login = (
                (data.get("not_login_module") or {}) if isinstance(data, dict) else {}
            )
            if isinstance(not_login, dict) and not_login.get("guide_login_tip_exist"):
                logger.warning(
                    "Detected login tip in user post response, pagination may be restricted"
                )

            aweme_items = data.get("aweme_list", [])
            if not aweme_items:
                if request_cursor and data.get("status_code") == 0:
                    pagination_restricted = True
                    logger.warning(
                        "User post pagination likely blocked at cursor=%s, will log for manual browser scan",
                        request_cursor,
                    )
                break

            # 统一时间过滤逻辑
            if filter_timestamp > 0:
                filtered_items = []
                all_before = True
                for item in aweme_items:
                    create_time = item.get("create_time", 0)
                    if create_time >= filter_timestamp:
                        filtered_items.append(item)
                        all_before = False
                
                if all_before:
                    # 本页所有视频都早于过滤时间，停止分页
                    logger.info(f"所有视频均早于 {filter_reason}，停止分页")
                    break
                
                aweme_items = filtered_items
            
            aweme_list.extend(aweme_items)
            self._progress_update_step(
                "拉取作品列表", f"已抓取 {len(aweme_list)} 条"
            )

            has_more = data.get("has_more", False)
            max_cursor = data.get("max_cursor", 0)
            if has_more and max_cursor == request_cursor:
                logger.warning(
                    "max_cursor did not advance (%s), stop paging to avoid loop",
                    max_cursor,
                )
                break

            number_limit = self.config.get("number", {}).get("post", 0)
            if number_limit > 0 and len(aweme_list) >= number_limit:
                aweme_list = aweme_list[:number_limit]
                break

        if pagination_restricted:
            author_name = user_info.get("nickname", "unknown")
            user_url = f"https://www.douyin.com/user/{sec_uid}"
            self._progress_update_step("拉取作品列表", "分页受限，跳过浏览器回补")
            logger.warning(
                f"用户 {author_name}({sec_uid}) 分页受限，建议手动使用浏览器扫描"
            )
            self.error_logger.log_error(
                sec_uid,
                "pagination_restricted",
                f"用户 {author_name} 分页受限，需要手动使用浏览器扫描补充",
                extra={
                    "sec_uid": sec_uid,
                    "author_name": author_name,
                    "url": user_url,
                    "source": "user_downloader",
                },
            )
            result.pagination_restricted = True

        aweme_list = self._limit_count(aweme_list, "post")

        result.total = len(aweme_list)
        self._progress_set_item_total(result.total, "作品待下载")
        self._progress_update_step("下载作品", f"待处理 {result.total} 条")

        author_name = user_info.get("nickname", "unknown")
        result.author_name = author_name
        result.sec_uid = sec_uid  # 记录用户唯一标识
        
        # 设置最新视频上传时间（优先从第一页数据获取，避免因时间过滤导致 aweme_list 为空）
        first_page_awemes = first_page_data.get("aweme_list", []) if first_page_data else []
        result.last_video_time = get_latest_video_time(first_page_awemes)
        
        # 兜底：从过滤后的列表获取
        if not result.last_video_time and aweme_list:
            result.last_video_time = get_latest_video_time(aweme_list)
            if result.last_video_time:
                logger.debug(f"从 aweme_list 获取 last_video_time: {result.last_video_time}")
        
        if not result.last_video_time:
            logger.debug(f"无法获取 last_video_time: sec_uid={sec_uid}, first_page_awemes_len={len(first_page_awemes)}, aweme_list_count={len(aweme_list)}")

        async def _process_aweme(item: Dict[str, Any]):
            aweme_id = item.get("aweme_id")
            desc = (item.get("desc", "") or "").strip()[:50]
            if not await self._should_download(aweme_id):
                self._progress_advance_item("skipped", str(aweme_id or "unknown"))
                return {
                    "status": "skipped",
                    "aweme_id": aweme_id,
                    "title": desc,
                    "error_message": "已在数据库中存在，跳过下载",
                }

            asset_result = await self._download_aweme_assets(item, author_name, mode="post")
            status = "success" if asset_result["success"] else "failed"
            
            # 记录失败原因
            error_message = ""
            if status == "failed":
                error_message = self._extract_failure_reason(item, asset_result)
                logger.warning(f"下载失败 aweme_id={aweme_id}: {error_message}")
            
            self._progress_advance_item(status, str(aweme_id or "unknown"))
            return {
                "status": status,
                "aweme_id": aweme_id,
                "title": desc,
                "asset_result": asset_result,
                "error_message": error_message,
            }

        download_results = await self.queue_manager.download_batch(
            _process_aweme, aweme_list
        )

        for entry in download_results:
            status = entry.get("status") if isinstance(entry, dict) else None
            aweme_id = entry.get("aweme_id", "unknown") if isinstance(entry, dict) else "unknown"
            if status == "success":
                result.success += 1
            elif status == "failed":
                result.failed += 1
                result.failed_items.append((aweme_id, f"用户{author_name}的作品下载失败"))
                
                # 记录失败视频到文件
                failed_manager = FailedVideoManager()
                failed_manager.record_failed_video(
                    url=f"https://www.douyin.com/video/{aweme_id}",
                    aweme_id=aweme_id,
                    title=entry.get("title", ""),
                    author_name=author_name,
                    sec_uid=sec_uid,
                    error_message=entry.get("error_message", ""),
                )
            elif status == "skipped":
                result.skipped += 1
            else:
                result.failed += 1
                result.failed_items.append(("unknown", "未知状态"))
                self._progress_advance_item("failed", "unknown")

            # 收集文件信息用于最终报告
            asset_result = entry.get("asset_result") if isinstance(entry, dict) else None
            if isinstance(asset_result, dict):
                result.downloaded_files.append(asset_result)

        return result

    def _extract_failure_reason(self, aweme_data: Dict[str, Any], asset_result: Dict[str, Any]) -> str:
        """提取下载失败的具体原因"""
        aweme_id = aweme_data.get("aweme_id", "unknown")
        
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

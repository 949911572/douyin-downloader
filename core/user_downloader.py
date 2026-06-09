from typing import Any, Dict, List
from datetime import datetime

from core.downloader_base import BaseDownloader, DownloadResult
from utils.logger import setup_logger
from utils.failed_video_manager import FailedVideoManager

logger = setup_logger("UserDownloader")


class UserDownloader(BaseDownloader):
    async def refresh_last_video_time(self, parsed_url: Dict[str, Any]) -> DownloadResult:
        """刷新最新视频时间，不进行任何下载
        
        Args:
            parsed_url: 解析后的URL信息，包含sec_uid
            
        Returns:
            DownloadResult: 包含last_video_time、author_name和sec_uid
        """
        result = DownloadResult()
        
        sec_uid = parsed_url.get("sec_uid")
        if not sec_uid:
            logger.error("No sec_uid found in parsed URL")
            return result
        
        # 获取第一页数据（只获取一条视频）
        first_page_data = await self.api_client.get_user_post(sec_uid, max_cursor=0, count=1)
        
        if not first_page_data:
            logger.error(f"Failed to get user post: {sec_uid}")
            return result
        
        # 获取用户信息
        user_info = first_page_data.get("user")
        if not user_info:
            user_info = await self.api_client.get_user_info(sec_uid)
            if not user_info:
                logger.error(f"Failed to get user info: {sec_uid}")
                return result
        
        result.author_name = user_info.get("nickname", "unknown")
        result.sec_uid = sec_uid
        
        # 提取最新视频时间
        first_page_awemes = first_page_data.get("aweme_list", [])
        if first_page_awemes:
            create_times = []
            for item in first_page_awemes:
                ct = item.get("create_time")
                if isinstance(ct, str):
                    try:
                        ct = int(ct)
                    except ValueError:
                        ct = 0
                create_times.append(ct if ct else 0)
            
            latest_create_time = max(create_times, default=0)
            if latest_create_time:
                result.last_video_time = datetime.fromtimestamp(latest_create_time).strftime('%Y-%m-%d %H:%M:%S')
                logger.info(f"刷新 last_video_time: {result.last_video_time}")
        
        return result
    
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
            return result
        
        # 从返回结果中提取用户信息（如果有的话）
        user_info = first_page_data.get("user")
        if not user_info:
            # 如果没有用户信息，再单独调用 get_user_info
            self._progress_update_step("获取作者信息", f"sec_uid={sec_uid}")
            user_info = await self.api_client.get_user_info(sec_uid)
            if not user_info:
                logger.error(f"Failed to get user info: {sec_uid}")
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
                        "User post pagination likely blocked at cursor=%s, switching to browser fallback",
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
            self._progress_update_step("拉取作品列表", "分页受限，尝试浏览器回补")
            await self._recover_user_post_with_browser(sec_uid, user_info, aweme_list, filter_timestamp, filter_reason)

        aweme_list = self._filter_by_time(aweme_list)
        aweme_list = self._limit_count(aweme_list, "post")

        result.total = len(aweme_list)
        self._progress_set_item_total(result.total, "作品待下载")
        self._progress_update_step("下载作品", f"待处理 {result.total} 条")

        author_name = user_info.get("nickname", "unknown")
        result.author_name = author_name
        result.sec_uid = sec_uid  # 记录用户唯一标识
        
        # 设置最新视频上传时间（从第一页数据获取，避免因时间过滤导致 aweme_list 为空）
        first_page_awemes = first_page_data.get("aweme_list", []) if first_page_data else []
        if first_page_awemes:
            create_times = []
            for item in first_page_awemes:
                ct = item.get("create_time")
                # 处理可能的字符串类型
                if isinstance(ct, str):
                    try:
                        ct = int(ct)
                    except ValueError:
                        ct = 0
                create_times.append(ct if ct else 0)
            
            latest_create_time = max(create_times, default=0)
            if latest_create_time:
                result.last_video_time = datetime.fromtimestamp(latest_create_time).strftime('%Y-%m-%d %H:%M:%S')
                logger.debug(f"成功获取 last_video_time: {result.last_video_time}")
        elif aweme_list:
            # 兜底：从过滤后的列表获取
            create_times = []
            for item in aweme_list:
                ct = item.get("create_time")
                if isinstance(ct, str):
                    try:
                        ct = int(ct)
                    except ValueError:
                        ct = 0
                create_times.append(ct if ct else 0)
            
            latest_create_time = max(create_times, default=0)
            if latest_create_time:
                result.last_video_time = datetime.fromtimestamp(latest_create_time).strftime('%Y-%m-%d %H:%M:%S')
                logger.debug(f"从 aweme_list 获取 last_video_time: {result.last_video_time}")
            else:
                logger.warning(f"aweme_list 存在但 create_time 无效: sec_uid={sec_uid}, aweme_list_len={len(aweme_list)}")
        else:
            logger.debug(f"无法获取 last_video_time: sec_uid={sec_uid}, first_page_data={bool(first_page_data)}, first_page_awemes_len={len(first_page_awemes) if first_page_data else 0}, aweme_list_count={len(aweme_list)}")

        async def _process_aweme(item: Dict[str, Any]):
            aweme_id = item.get("aweme_id")
            if not await self._should_download(aweme_id):
                self._progress_advance_item("skipped", str(aweme_id or "unknown"))
                return {"status": "skipped", "aweme_id": aweme_id}

            asset_result = await self._download_aweme_assets(item, author_name, mode="post")
            status = "success" if asset_result["success"] else "failed"
            self._progress_advance_item(status, str(aweme_id or "unknown"))
            return {
                "status": status,
                "aweme_id": aweme_id,
                "asset_result": asset_result,
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
                    url=f"https://www.douyin.com/user/{sec_uid}/video/{aweme_id}",
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

    async def _recover_user_post_with_browser(
        self,
        sec_uid: str,
        user_info: Dict[str, Any],
        aweme_list: List[Dict[str, Any]],
        filter_timestamp: int = 0,
        filter_reason: str = "",
    ) -> None:
        browser_cfg = self.config.get("browser_fallback", {}) or {}
        if not browser_cfg.get("enabled", True):
            return

        number_limit = self.config.get("number", {}).get("post", 0)
        # 在分页受限场景下，user_info.aweme_count 常常不可靠（经常只返回 20）
        # 因此仅在用户显式设置 number_limit 时才限制浏览器采集目标数量。
        expected_count = int(number_limit or 0)
        if expected_count and len(aweme_list) >= expected_count:
            return

        try:
            browser_aweme_ids = await self.api_client.collect_user_post_ids_via_browser(
                sec_uid,
                expected_count=expected_count,
                headless=bool(browser_cfg.get("headless", False)),
                max_scrolls=int(browser_cfg.get("max_scrolls", 240) or 240),
                idle_rounds=int(browser_cfg.get("idle_rounds", 8) or 8),
                wait_timeout_seconds=int(
                    browser_cfg.get("wait_timeout_seconds", 600) or 600
                ),
            )
        except Exception as exc:
            logger.error("Browser fallback failed: %s", exc)
            return

        browser_aweme_items: Dict[str, Dict[str, Any]] = {}
        browser_post_stats: Dict[str, int] = {}
        if hasattr(self.api_client, "pop_browser_post_aweme_items"):
            try:
                browser_aweme_items = (
                    self.api_client.pop_browser_post_aweme_items() or {}
                )
            except Exception as exc:
                logger.debug("Fetch browser post items skipped: %s", exc)
        if hasattr(self.api_client, "pop_browser_post_stats"):
            try:
                browser_post_stats = self.api_client.pop_browser_post_stats() or {}
            except Exception as exc:
                logger.debug("Fetch browser post stats skipped: %s", exc)

        if not browser_aweme_ids:
            logger.warning("Browser fallback returned no aweme_id")
            return

        existing_ids = {
            str(item.get("aweme_id")) for item in aweme_list if item.get("aweme_id")
        }
        missing_ids = [
            aweme_id for aweme_id in browser_aweme_ids if aweme_id not in existing_ids
        ]
        if not missing_ids:
            return

        logger.warning(
            "Recovering aweme details from browser list, missing count=%s",
            len(missing_ids),
        )
        detail_failed = 0
        detail_success = 0
        reused_from_browser_items = 0
        total_missing = len(missing_ids)
        for index, aweme_id in enumerate(missing_ids, start=1):
            if number_limit > 0 and len(aweme_list) >= number_limit:
                break

            if index == 1 or index == total_missing or index % 5 == 0:
                self._progress_update_step(
                    "浏览器回补", f"补全详情 {index}/{total_missing}"
                )

            detail = browser_aweme_items.get(str(aweme_id))
            if not detail:
                await self.rate_limiter.acquire()
                detail = await self.api_client.get_video_detail(
                    aweme_id, suppress_error=True
                )
                if detail:
                    detail_success += 1
            else:
                reused_from_browser_items += 1
            if not detail:
                detail_failed += 1
                continue
            author = detail.get("author", {}) if isinstance(detail, dict) else {}
            detail_sec_uid = author.get("sec_uid") if isinstance(author, dict) else None
            if detail_sec_uid and str(detail_sec_uid) != str(sec_uid):
                logger.warning(
                    "Skip aweme_id=%s due to mismatched sec_uid (%s)",
                    aweme_id,
                    detail_sec_uid,
                )
                continue
            
            # 时间过滤：只添加晚于 filter_timestamp 的视频
            if filter_timestamp > 0:
                create_time = detail.get("create_time", 0)
                if create_time < filter_timestamp:
                    logger.debug(f"跳过早于 {filter_reason} 的视频: aweme_id={aweme_id}, create_time={create_time}")
                    continue
            
            aweme_list.append(detail)

        self._progress_update_step(
            "浏览器回补",
            f"回补完成，复用 {reused_from_browser_items}，补拉成功 {detail_success}，失败 {detail_failed}",
        )
        logger.warning(
            "Browser fallback summary: merged_ids=%s selected_ids=%s post_items=%s post_pages=%s reused=%s detail_success=%s detail_failed=%s",
            browser_post_stats.get("merged_ids", 0),
            browser_post_stats.get("selected_ids", len(browser_aweme_ids)),
            browser_post_stats.get("post_items", len(browser_aweme_items)),
            browser_post_stats.get("post_pages", 0),
            reused_from_browser_items,
            detail_success,
            detail_failed,
        )

        if detail_failed > 0:
            logger.warning(
                "Browser fallback detail fetch failed: %s/%s",
                detail_failed,
                total_missing,
            )

        # 对浏览器回补的视频进行时间过滤
        if filter_timestamp > 0:
            original_length = len(aweme_list)
            aweme_list[:] = [item for item in aweme_list if item.get("create_time", 0) >= filter_timestamp]
            filtered_count = original_length - len(aweme_list)
            if filtered_count > 0:
                logger.info(f"浏览器回补后过滤了 {filtered_count} 个早于 {filter_reason} 的视频")

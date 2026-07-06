import os
import traceback
from datetime import datetime
from typing import Any, Dict, Optional


class ErrorLogger:
    def __init__(self, data_dir: str = "data"):
        self.error_dir = os.path.join(data_dir, "error_logs")
        os.makedirs(self.error_dir, exist_ok=True)
        self._session_time = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._session_file = os.path.join(
            self.error_dir, f"error_{self._session_time}.log"
        )
        self._error_count = 0

    def log_error(
        self,
        aweme_id: str,
        error_type: str,
        error_message: str,
        aweme_data: Optional[Dict[str, Any]] = None,
        extra: Optional[Dict[str, Any]] = None,
        exc_info: Optional[Exception] = None,
    ):
        lines = []
        lines.append("=" * 70)
        lines.append(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"作品ID: {aweme_id}")
        lines.append(f"错误类型: {error_type}")
        lines.append(f"错误信息: {error_message}")

        if aweme_data:
            lines.append(self._format_aweme_summary(aweme_data))

        if extra:
            lines.append("附加信息:")
            for key, value in extra.items():
                lines.append(f"  {key}: {value}")

        if exc_info:
            tb = "".join(
                traceback.format_exception(type(exc_info), exc_info, exc_info.__traceback__)
            )
            lines.append("异常堆栈:")
            lines.append(tb.rstrip())

        lines.append("=" * 70)
        lines.append("")

        content = "\n".join(lines) + "\n"
        self._write(content)
        self._error_count += 1

    def _format_aweme_summary(self, aweme_data: Dict[str, Any]) -> str:
        image_post = aweme_data.get("image_post_info", {})
        images = image_post.get("images") if image_post else None
        if images is None:
            images = aweme_data.get("images") or []

        video = aweme_data.get("video", {})
        play_addr = video.get("play_addr", {})
        url_list = play_addr.get("url_list") or []

        desc = (aweme_data.get("desc") or "")[:100]
        author = aweme_data.get("author", {}).get("nickname", "")

        lines = []
        lines.append("作品信息:")
        lines.append(f"  描述: {desc}")
        lines.append(f"  作者: {author}")
        lines.append(f"  图文作品: {'是' if image_post else '否'}")
        lines.append(f"  图片数量: {len(images)}")
        lines.append(f"  视频URL数量: {len(url_list)}")

        if url_list:
            first_url = url_list[0]
            is_music = "ies-music" in first_url or first_url.endswith(".mp3")
            lines.append(f"  首个URL: {first_url[:120]}")
            lines.append(f"  是否音乐URL: {'是' if is_music else '否'}")

        if images:
            for i, img in enumerate(images[:5], 1):
                if isinstance(img, dict):
                    img_urls = img.get("url_list", [])
                    has_video = bool(img.get("video"))
                    lines.append(f"  图片{i}: {len(img_urls)}个URL, 含视频: {'是' if has_video else '否'}")

        return "\n".join(lines)

    def _write(self, content: str):
        try:
            with open(self._session_file, "a", encoding="utf-8") as f:
                f.write(content)
        except Exception:
            pass

    def get_error_count(self) -> int:
        return self._error_count

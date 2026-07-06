import asyncio
from typing import Any, Dict, List

from control.queue_manager import QueueManager
from core.user_downloader import UserDownloader
from storage.file_manager import FileManager


def _make_aweme(aweme_id: str) -> Dict[str, Any]:
    return {
        "aweme_id": aweme_id,
        "desc": f"desc-{aweme_id}",
        "create_time": 1700000000,
        "author": {"nickname": "tester", "uid": "uid-1"},
        "video": {"play_addr": {"url_list": ["https://example.com/video.mp4"]}},
    }


class _FakeConfig:
    def __init__(self, data: Dict[str, Any]):
        self._data = data

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)


class _FakeCookieManager:
    pass


class _NoopRateLimiter:
    async def acquire(self):
        return


class _FakeProgressReporter:
    def __init__(self):
        self.step_updates: List[tuple[str, str]] = []
        self.item_totals: List[tuple[int, str]] = []
        self.item_events: List[tuple[str, str]] = []

    def update_step(self, step: str, detail: str = "") -> None:
        self.step_updates.append((step, detail))

    def set_item_total(self, total: int, detail: str = "") -> None:
        self.item_totals.append((total, detail))

    def advance_item(self, status: str, detail: str = "") -> None:
        self.item_events.append((status, detail))


class _FakeAPIClient:
    def __init__(self):
        self.user_post_calls: List[int] = []
        self.detail_calls: List[str] = []
        self.detail_call_kwargs: List[Dict[str, Any]] = []

    async def get_user_post(self, _sec_uid: str, max_cursor: int = 0, _count: int = 20):
        self.user_post_calls.append(max_cursor)
        if max_cursor == 0:
            return {
                "status_code": 0,
                "aweme_list": [_make_aweme("111")],
                "has_more": 1,
                "max_cursor": 123,
                "not_login_module": {"guide_login_tip_exist": True},
            }
        return {"status_code": 0}

    async def get_video_detail(self, aweme_id: str, **kwargs):
        self.detail_calls.append(aweme_id)
        self.detail_call_kwargs.append(kwargs)
        return _make_aweme(aweme_id)


def _build_downloader(
    tmp_path,
    api_client,
    progress_reporter=None,
    number_post: int = 0,
) -> UserDownloader:
    config_data = {
        "number": {"post": number_post},
        "increase": {"post": False},
        "mode": ["post"],
        "thread": 2,
    }
    config = _FakeConfig(config_data)
    file_manager = FileManager(str(tmp_path / "Downloaded"))
    downloader = UserDownloader(
        config=config,
        api_client=api_client,
        file_manager=file_manager,
        cookie_manager=_FakeCookieManager(),
        database=None,
        rate_limiter=_NoopRateLimiter(),
        retry_handler=None,
        queue_manager=QueueManager(max_workers=2),
    )
    downloader.progress_reporter = progress_reporter
    return downloader


def test_user_post_reports_step_and_item_progress(tmp_path, monkeypatch):
    api_client = _FakeAPIClient()
    reporter = _FakeProgressReporter()
    downloader = _build_downloader(
        tmp_path,
        api_client,
        progress_reporter=reporter,
    )

    async def _fake_should_download(aweme_id):
        return aweme_id != "222"

    async def _fake_download_aweme_assets(item, *_args, **_kwargs):
        return item.get("aweme_id") != "333"

    monkeypatch.setattr(downloader, "_should_download", _fake_should_download)
    monkeypatch.setattr(downloader, "_download_aweme_assets", _fake_download_aweme_assets)

    result = asyncio.run(
        downloader._download_user_post(
            "sec_uid_x",
            {"uid": "uid-1", "nickname": "tester", "aweme_count": 3},
        )
    )

    assert result.total == 3
    assert result.success == 1
    assert result.skipped == 1
    assert result.failed == 1
    assert reporter.item_totals == [(3, "作品待下载")]
    assert ("下载作品", "待处理 3 条") in reporter.step_updates
    statuses = [status for status, _detail in reporter.item_events]
    assert statuses.count("success") == 1
    assert statuses.count("skipped") == 1
    assert statuses.count("failed") == 1

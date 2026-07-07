"""
抖音API客户端模块
封装抖音API的异步请求，支持：
- 用户作品列表获取
- 视频详情获取
- 用户信息获取
- XBogus/ABogus签名生成
- Cookie管理和请求限流
"""

from __future__ import annotations

import asyncio
import random
from typing import Any, Dict, List, Optional, Tuple
import re
from urllib.parse import urlencode, urlparse, urlunparse

import aiohttp
from auth import MsTokenManager
from utils.cookie_utils import sanitize_cookies
from utils.logger import setup_logger
from utils.xbogus import XBogus

try:
    from utils.abogus import ABogus, BrowserFingerprintGenerator
except Exception:  # pragma: no cover - optional dependency
    ABogus = None
    BrowserFingerprintGenerator = None

logger = setup_logger("APIClient")


class DouyinAPIClient:
    BASE_URL = "https://www.douyin.com"
    _BROWSER_COOKIE_BLOCKLIST = {
        "sessionid",
        "sessionid_ss",
        "sid_tt",
        "sid_guard",
        "uid_tt",
        "uid_tt_ss",
        "passport_auth_status",
        "passport_auth_status_ss",
        "passport_assist_user",
        "passport_auth_mix_state",
        "passport_mfa_token",
        "login_time",
    }

    def __init__(self, cookies: Dict[str, str]):
        self.cookies = sanitize_cookies(cookies or {})
        self._session: Optional[aiohttp.ClientSession] = None
        self._browser_post_aweme_items: Dict[str, Dict[str, Any]] = {}
        self._browser_post_stats: Dict[str, int] = {}
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
            ),
            "Referer": "https://www.douyin.com/",
            "Accept": "application/json",
            "Accept-Encoding": "gzip, deflate",
            "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
            "Connection": "keep-alive",
        }
        self._signer = XBogus(self.headers["User-Agent"])
        self._ms_token_manager = MsTokenManager(user_agent=self.headers["User-Agent"])
        self._ms_token = (self.cookies.get("msToken") or "").strip()
        self._abogus_enabled = (
            ABogus is not None and BrowserFingerprintGenerator is not None
        )

    async def __aenter__(self) -> "DouyinAPIClient":
        await self._ensure_session()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.close()

    async def _ensure_session(self):
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers=self.headers,
                cookies=self.cookies,
                timeout=aiohttp.ClientTimeout(total=30),
                raise_for_status=False,
            )

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    async def _rate_limit(self):
        """请求限流延迟，避免触发平台限流"""
        delay = random.uniform(0.8, 2.0)  # 0.8-2秒随机延迟
        await asyncio.sleep(delay)

    async def get_session(self) -> aiohttp.ClientSession:
        await self._ensure_session()
        assert self._session is not None
        return self._session

    async def _ensure_ms_token(self) -> str:
        if self._ms_token:
            return self._ms_token

        token = await asyncio.to_thread(
            self._ms_token_manager.ensure_ms_token,
            self.cookies,
        )
        self._ms_token = token.strip()
        if self._ms_token:
            self.cookies["msToken"] = self._ms_token
            if self._session and not self._session.closed:
                self._session.cookie_jar.update_cookies({"msToken": self._ms_token})
        return self._ms_token

    async def _default_query(self) -> Dict[str, Any]:
        ms_token = await self._ensure_ms_token()
        return {
            "device_platform": "webapp",
            "aid": "6383",
            "channel": "channel_pc_web",
            "pc_client_type": "1",
            "version_code": "170400",
            "version_name": "17.4.0",
            "cookie_enabled": "true",
            "screen_width": "1920",
            "screen_height": "1080",
            "browser_language": "zh-CN",
            "browser_platform": "Win32",
            "browser_name": "Chrome",
            "browser_version": "123.0.0.0",
            "browser_online": "true",
            "engine_name": "Blink",
            "engine_version": "123.0.0.0",
            "os_name": "Windows",
            "os_version": "10",
            "cpu_core_num": "8",
            "device_memory": "8",
            "platform": "PC",
            "downlink": "10",
            "effective_type": "4g",
            "round_trip_time": "50",
            "msToken": ms_token,
        }

    def sign_url(self, url: str) -> Tuple[str, str]:
        signed_url, _xbogus, ua = self._signer.build(url)
        return signed_url, ua

    def build_signed_path(self, path: str, params: Dict[str, Any]) -> Tuple[str, str]:
        query = urlencode(params)
        base_url = f"{self.BASE_URL}{path}"
        ab_signed = self._build_abogus_url(base_url, query)
        if ab_signed:
            return ab_signed
        return self.sign_url(f"{base_url}?{query}")

    def _build_abogus_url(self, base_url: str, query: str) -> Optional[Tuple[str, str]]:
        if not self._abogus_enabled:
            return None

        try:
            browser_fp = BrowserFingerprintGenerator.generate_fingerprint("Edge")
            signer = ABogus(fp=browser_fp, user_agent=self.headers["User-Agent"])
            params_with_ab, _ab, ua, _body = signer.generate_abogus(query, "")
            return f"{base_url}?{params_with_ab}", ua
        except Exception as exc:
            logger.warning("Failed to generate a_bogus, fallback to X-Bogus: %s", exc)
            return None

    async def get_video_detail(
        self, aweme_id: str, *, suppress_error: bool = False
    ) -> Optional[Dict[str, Any]]:
        await self._ensure_session()

        for aid in ("1128", "6383"):
            await self._rate_limit()
            params = await self._default_query()
            params.update({"aweme_id": aweme_id, "aid": aid})

            signed_url, ua = self.build_signed_path(
                "/aweme/v1/web/aweme/detail/", params
            )

            try:
                async with self._session.get(
                    signed_url, headers={**self.headers, "User-Agent": ua}
                ) as response:
                    if response.status == 200:
                        data = await response.json(content_type=None)
                        detail = data.get("aweme_detail")
                        if detail:
                            return detail
                    else:
                        log_fn = logger.debug if suppress_error else logger.error
                        log_fn(
                            "Video detail request failed (aid=%s): %s, status=%s",
                            aid,
                            aweme_id,
                            response.status,
                        )
            except Exception as e:
                log_fn = logger.debug if suppress_error else logger.error
                log_fn(
                    "Failed to get video detail (aid=%s): %s, error: %s",
                    aid,
                    aweme_id,
                    e,
                )

        return None

    async def get_user_post(
        self, sec_uid: str, max_cursor: int = 0, count: int = 20
    ) -> Dict[str, Any]:
        await self._ensure_session()
        await self._rate_limit()
        params = await self._default_query()
        params.update(
            {
                "sec_user_id": sec_uid,
                "max_cursor": max_cursor,
                "count": count,
                "locate_query": "false",
                "show_live_replay_strategy": "1",
                "need_time_list": "1",
                "time_list_query": "0",
                "whale_cut_token": "",
                "cut_version": "1",
                "publish_video_strategy_type": "2",
            }
        )

        signed_url, ua = self.build_signed_path("/aweme/v1/web/aweme/post/", params)

        try:
            async with self._session.get(
                signed_url, headers={**self.headers, "User-Agent": ua}
            ) as response:
                if response.status == 200:
                    return await response.json(content_type=None)
                logger.error(
                    f"User post request failed: {sec_uid}, status={response.status}"
                )
        except Exception as e:
            logger.error(f"Failed to get user post: {sec_uid}, error: {e}")

        return {}

    async def get_user_info(self, sec_uid: str) -> Optional[Dict[str, Any]]:
        await self._ensure_session()
        await self._rate_limit()
        params = await self._default_query()
        params.update({"sec_user_id": sec_uid})

        signed_url, ua = self.build_signed_path(
            "/aweme/v1/web/user/profile/other/", params
        )

        try:
            async with self._session.get(
                signed_url, headers={**self.headers, "User-Agent": ua}
            ) as response:
                if response.status == 200:
                    data = await response.json(content_type=None)
                    return data.get("user")
                logger.error(
                    f"User info request failed: {sec_uid}, status={response.status}"
                )
        except Exception as e:
            logger.error(f"Failed to get user info: {sec_uid}, error: {e}")

        return None

    async def resolve_short_url(self, short_url: str) -> Optional[str]:
        try:
            await self._ensure_session()
            async with self._session.get(short_url, allow_redirects=True) as response:
                return str(response.url)
        except Exception as e:
            logger.error(f"Failed to resolve short URL: {short_url}, error: {e}")
            return None



    def _browser_cookie_payload(self) -> List[Dict[str, str]]:
        payload: List[Dict[str, str]] = []
        for name, value in self.cookies.items():
            if not name:
                continue
            if name in self._BROWSER_COOKIE_BLOCKLIST:
                continue
            payload.append(
                {
                    "name": str(name),
                    "value": str(value or ""),
                    "url": f"{self.BASE_URL}/",
                }
            )
        return payload

    async def _extract_aweme_ids_from_page(self, page) -> List[str]:
        script = """
() => {
  const result = [];
  const seen = new Set();
  const push = (id) => {
    if (!id || seen.has(id)) return;
    seen.add(id);
    result.push(id);
  };

  const collectFrom = (text, pattern) => {
    if (!text) return;
    let match;
    while ((match = pattern.exec(text)) !== null) {
      push(match[1]);
    }
  };

  const links = document.querySelectorAll("a[href]");
  for (const node of links) {
    const href = node.getAttribute("href") || "";
    collectFrom(href, /\\/video\\/(\\d{15,20})/g);
    collectFrom(href, /\\/note\\/(\\d{15,20})/g);
  }

  const html = document.documentElement ? document.documentElement.innerHTML : "";
  collectFrom(html, /"aweme_id":"(\\d{15,20})"/g);
  collectFrom(html, /"group_id":"(\\d{15,20})"/g);

  return result;
}
"""
        try:
            data = await page.evaluate(script)
            if isinstance(data, list):
                return [str(x) for x in data if x]
        except Exception as exc:
            logger.debug("Extract aweme_id from page failed: %s", exc)
        return []

    async def _wait_for_manual_verification(
        self, page, *, wait_timeout_seconds: int
    ) -> None:
        deadline = asyncio.get_running_loop().time() + max(
            30, int(wait_timeout_seconds)
        )
        while asyncio.get_running_loop().time() < deadline:
            if page.is_closed():
                logger.warning("Browser page closed while waiting manual verification")
                return
            title = ""
            try:
                title = await page.title()
            except Exception:
                pass
            if "验证码" not in title:
                logger.warning("验证码页面已退出，继续采集。")
                return
            await page.wait_for_timeout(1000)

        logger.warning(
            "等待手动验证超时（%ss），继续按当前页面状态采集。", wait_timeout_seconds
        )

    def _sync_browser_cookies(self, browser_cookies: List[Dict[str, Any]]) -> None:
        merged: Dict[str, str] = {}
        for cookie in browser_cookies or []:
            if not isinstance(cookie, dict):
                continue
            name = str(cookie.get("name") or "").strip()
            value = str(cookie.get("value") or "").strip()
            domain = str(cookie.get("domain") or "")
            if not name or not value:
                continue
            if "douyin.com" not in domain:
                continue
            merged[name] = value

        if not merged:
            return

        self.cookies.update(merged)
        if self._session and not self._session.closed:
            self._session.cookie_jar.update_cookies(merged)
        logger.warning("Synced %s browser cookie(s) back to API client", len(merged))

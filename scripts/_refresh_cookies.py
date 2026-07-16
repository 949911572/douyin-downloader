"""
抖音 Cookie 刷新脚本
基于 tools/cookie_fetcher.py 的成熟逻辑重写，完整移植 msToken 多源提取机制。
优先从 chrome_user_data 目录直接读取 Cookie，无需启动浏览器。
"""

import asyncio
import re
import sqlite3
import sys
import traceback
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

import yaml
from playwright.async_api import async_playwright

SCRIPT_DIR = Path(__file__).parent.resolve()
PROJECT_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_DIR))
from utils.cookie_utils import parse_cookie_header, sanitize_cookies
from utils.logger import setup_logger

logger = setup_logger('RefreshCookies')

CONFIG_PATH = PROJECT_DIR / "config.yml"
DOUYIN_URL = "https://www.douyin.com/"

BASE_REQUIRED = {"ttwid", "odin_tt", "passport_csrf_token"}
FULL_REQUIRED = BASE_REQUIRED | {"msToken"}
SUGGESTED = FULL_REQUIRED | {"sid_guard", "sessionid", "sid_tt"}

PRIMARY_WAIT_UNTIL = "domcontentloaded"
FALLBACK_WAIT_UNTIL = "domcontentloaded"
PRIMARY_TIMEOUT_MS = 30_000
FALLBACK_TIMEOUT_MS = 30_000
LOGIN_POLL_TIMEOUT_SEC = 300


def read_cookies_from_chrome_user_data(user_data_dir: str) -> dict:
    """直接从 Chrome 用户数据目录读取 Cookie（仅读取未加密的 value 字段）"""
    cookie_paths = [
        Path(user_data_dir) / "Default" / "Cookies",
        Path(user_data_dir) / "Default" / "Network" / "Cookies",
    ]
    
    cookies_db = None
    for path in cookie_paths:
        if path.exists():
            cookies_db = path
            break
    
    if not cookies_db:
        return {}
    
    try:
        conn = sqlite3.connect(str(cookies_db))
        conn.row_factory = sqlite3.Row
        
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name, value, host_key FROM cookies WHERE host_key LIKE '%douyin.com%'"
        )
        
        cookies = {}
        for row in cursor.fetchall():
            cookies[row['name']] = row['value']
        
        conn.close()
        return cookies
    except Exception as e:
        print(f"[WARN] 直接读取 Cookie 失败: {e}")
        return {}


def extract_ms_token_from_text(text: str) -> str | None:
    """从任意文本中用正则提取 msToken 值（移植自 cookie_fetcher.py）"""
    if not text:
        return None
    patterns = [
        r'(?:^|[;,&\s"\'])msToken=([^;,&\s"\']+)',
        r'"msToken"\s*:\s*"([^"]+)"',
        r"'msToken'\s*:\s*'([^']+)'",
    ]
    for pattern in patterns:
        m = re.search(pattern, text)
        if not m:
            continue
        token = (m.group(1) or "").strip()
        if token:
            return unquote(token)
    return None


def _is_timeout_error(exc: Exception) -> bool:
    return exc.__class__.__name__ == "TimeoutError" or "Timeout" in str(exc)


def _is_target_closed_error(exc: Exception) -> bool:
    return (
        exc.__class__.__name__ == "TargetClosedError"
        or "Target page, context or browser has been closed" in str(exc)
    )


async def _countdown(duration: int, stop_event: asyncio.Event):
    """显示倒计时，每秒更新一次"""
    for remaining in range(duration, 0, -1):
        if stop_event.is_set():
            break
        print(f"\r[步骤2] 浏览器加载中，剩余 {remaining} 秒...", end="", flush=True)
        await asyncio.sleep(1)
    if not stop_event.is_set():
        print(f"\r[步骤2] 浏览器加载中，剩余 0 秒...", end="", flush=True)


async def goto_with_fallback(page, url: str) -> str:
    """先尝试 domcontentloaded 30s，超时则继续执行"""
    print(f"[步骤2] 正在访问 {url} ...")

    stop_event = asyncio.Event()
    timeout_sec = PRIMARY_TIMEOUT_MS // 1000
    
    countdown_task = asyncio.create_task(_countdown(timeout_sec, stop_event))
    
    try:
        await page.goto(url, wait_until=PRIMARY_WAIT_UNTIL, timeout=PRIMARY_TIMEOUT_MS)
        stop_event.set()
        await countdown_task
        print(f"\r[步骤2] ✓ 页面加载完成")
        return PRIMARY_WAIT_UNTIL
    except Exception as exc:
        stop_event.set()
        await countdown_task
        if _is_target_closed_error(exc):
            print(f"\r[步骤2] [WARN] 浏览器/页面在导航期间被关闭，继续使用当前状态")
            return "target_closed"
        if _is_timeout_error(exc):
            print(f"\r[步骤2] [WARN] 页面加载超时 ({timeout_sec}s)，继续提取 msToken")
            return "timeout"
        print(f"\r[步骤2] [ERROR] 页面加载失败: {exc}")
        raise


async def try_extract_ms_token(
    page,
    cookies: dict,
    observed_cookie_headers: list,
    observed_mstokens: list,
) -> str | None:
    """
    按优先级尝试从多个来源提取 msToken：
    1. Cookie 中已有
    2. 网络请求 URL query 参数
    3. 网络请求头 Cookie
    4. document.cookie
    5. localStorage / sessionStorage
    """

    existing = cookies.get("msToken")
    if existing:
        print("[步骤3] msToken 已存在于 Cookie 存储中")
        return existing

    for token in reversed(observed_mstokens):
        token = (token or "").strip()
        if token:
            print("[步骤3] ✓ 从网络请求 URL 参数中提取到 msToken")
            return token

    for header in reversed(observed_cookie_headers):
        parsed = parse_cookie_header(header)
        token = (parsed.get("msToken") or "").strip()
        if token:
            print("[步骤3] ✓ 从网络请求头 Cookie 中提取到 msToken")
            return token
        extra = extract_ms_token_from_text(header)
        if extra:
            print("[步骤3] ✓ 从网络请求文本正则提取到 msToken")
            return extra

    try:
        doc_cookie = await page.evaluate("() => document.cookie || ''")
        parsed = parse_cookie_header(doc_cookie)
        token = (parsed.get("msToken") or "").strip()
        if token:
            print("[步骤3] ✓ 从 document.cookie 中提取到 msToken")
            return token
        extra = extract_ms_token_from_text(doc_cookie)
        if extra:
            print("[步骤3] ✓ 从 document.cookie 正则提取到 msToken")
            return extra
    except Exception as e:
        print(f"[步骤3] document.cookie 读取失败: {e}")

    js = """
() => {
  const values = [];
  const pushIf = (v) => {
    if (typeof v === 'string' && v.trim()) values.push(v.trim());
  };
  try {
    for (const key of Object.keys(localStorage || {})) {
      if (key.toLowerCase().includes('mstoken')) {
        pushIf(localStorage.getItem(key));
      }
    }
  } catch (e) {}
  try {
    for (const key of Object.keys(sessionStorage || {})) {
      if (key.toLowerCase().includes('mstoken')) {
        pushIf(sessionStorage.getItem(key));
      }
    }
  } catch (e) {}
  return values;
}
"""
    try:
        candidates = await page.evaluate(js)
        for candidate in candidates or []:
            if not isinstance(candidate, str):
                continue
            text = candidate.strip()
            if not text:
                continue
            parsed = parse_cookie_header(text)
            if parsed.get("msToken"):
                print("[步骤3] ✓ 从 localStorage/sessionStorage 中提取到 msToken")
                return parsed["msToken"]
            extra = extract_ms_token_from_text(text)
            if extra:
                print("[步骤3] ✓ 从 localStorage/sessionStorage 正则提取到 msToken")
                return extra
            if len(text) <= 2048 and all(
                ch not in text for ch in [";", " ", "\n", "\r", "\t"]
            ):
                print("[步骤3] ✓ 从 localStorage/sessionStorage 中提取到疑似 msToken")
                return text
    except Exception as e:
        print(f"[步骤3] localStorage/sessionStorage 读取失败: {e}")

    print("[WARN] 未能从任何来源提取 msToken")
    return None


async def main() -> int:
    print("=" * 52)
    print("  抖音 Cookie 刷新脚本")
    print(f"  导航超时: {PRIMARY_TIMEOUT_MS // 1000}s | 登录超时: {LOGIN_POLL_TIMEOUT_SEC}s")
    print("=" * 52)
    print()

    try:
        from utils.browser_config import USER_DATA_DIR, USER_AGENT, VIEWPORT, ensure_user_data_dir
        
        ensure_user_data_dir()

        c = read_cookies_from_chrome_user_data(USER_DATA_DIR)
        c = sanitize_cookies(c)

        print("[步骤1] 启动浏览器获取 Cookie...")

        async with async_playwright() as p:
            ctx = await p.chromium.launch_persistent_context(
                USER_DATA_DIR,
                headless=False,
                viewport=VIEWPORT,
                user_agent=USER_AGENT,
                args=["--disable-blink-features=AutomationControlled", "--disable-dev-shm-usage", "--no-sandbox"],
            )
            page = ctx.pages[0] if ctx.pages else await ctx.new_page()

            observed_cookie_headers: list[str] = []
            observed_mstokens: list[str] = []

            def _on_request(request):
                try:
                    headers = request.headers or {}
                    cookie_header = headers.get("cookie")
                    if cookie_header:
                        observed_cookie_headers.append(cookie_header)
                    url = request.url or ""
                    query = parse_qs(urlparse(url).query)
                    if "msToken" in query and query["msToken"]:
                        observed_mstokens.append((query["msToken"][0] or "").strip())
                    token = extract_ms_token_from_text(url)
                    if token:
                        observed_mstokens.append(token)
                except Exception as exc:
                    logger.warning("Request interception error: %s", exc)
                    return

            page.on("request", _on_request)

            await goto_with_fallback(page, DOUYIN_URL)

            browser_cookies = await ctx.cookies(DOUYIN_URL)
            
            for cookie in browser_cookies:
                name = cookie.get("name")
                value = cookie.get("value", "")
                if name:
                    c[name] = value

            ms_token = await try_extract_ms_token(
                page, c, observed_cookie_headers, observed_mstokens
            )
            if ms_token and not c.get("msToken"):
                c["msToken"] = ms_token

            await ctx.close()

            picked = {k: v for k, v in c.items() if k in SUGGESTED and v}

            missing = FULL_REQUIRED - picked.keys()
            if missing:
                print(f"[WARN] 缺少必要 Cookie: {sorted(missing)}")
                print(f"[WARN] 缺少这些可能导致 API 请求被风控拦截")

            print("[步骤2] 正在写入 config.yml ...")
            cfg = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}
            cfg["cookies"] = picked
            CONFIG_PATH.write_text(
                yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )

            print()
            print("=" * 52)
            print(f"  ✓ Cookie 刷新完成，已更新 {len(picked)} 个 Cookie")
            print(f"  Cookie 列表: {sorted(picked.keys())}")
            print(f"  配置文件: {CONFIG_PATH}")
            if missing:
                print(f"  ⚠ 缺失: {sorted(missing)}")
            print("=" * 52)

            return 0

    except Exception:
        print()
        print("[ERROR] 脚本执行异常，完整堆栈如下：")
        traceback.print_exc()
        return 2


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

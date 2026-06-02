"""
抖音 Cookie 刷新脚本
基于 tools/cookie_fetcher.py 的成熟逻辑重写，完整移植 msToken 多源提取机制。
"""

import asyncio
import re
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

CONFIG_PATH = PROJECT_DIR / "config.yml"
DOUYIN_URL = "https://www.douyin.com/"

BASE_REQUIRED = {"ttwid", "odin_tt", "passport_csrf_token"}
FULL_REQUIRED = BASE_REQUIRED | {"msToken"}
SUGGESTED = FULL_REQUIRED | {"sid_guard", "sessionid", "sid_tt"}

PRIMARY_WAIT_UNTIL = "networkidle"
FALLBACK_WAIT_UNTIL = "domcontentloaded"
PRIMARY_TIMEOUT_MS = 300_000
FALLBACK_TIMEOUT_MS = 300_000
LOGIN_POLL_TIMEOUT_SEC = 300


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


async def goto_with_fallback(page, url: str) -> str:
    """先尝试 networkidle 300s，超时则降级到 domcontentloaded 300s"""
    print(f"[步骤1] 正在访问 {url} ...")

    try:
        await page.goto(url, wait_until=PRIMARY_WAIT_UNTIL, timeout=PRIMARY_TIMEOUT_MS)
        print(f"[步骤1] 页面完全加载 (wait_until={PRIMARY_WAIT_UNTIL})")
        return PRIMARY_WAIT_UNTIL
    except Exception as exc:
        if _is_target_closed_error(exc):
            print("[WARN] 浏览器/页面在导航期间被关闭，继续使用当前状态")
            return "target_closed"
        if not _is_timeout_error(exc):
            raise
        print(
            f"[WARN] networkidle 超时 ({PRIMARY_TIMEOUT_MS}ms)，"
            f"降级到 {FALLBACK_WAIT_UNTIL}"
        )

    try:
        await page.goto(url, wait_until=FALLBACK_WAIT_UNTIL, timeout=FALLBACK_TIMEOUT_MS)
        print(f"[步骤1] 页面基本加载 (降级 wait_until={FALLBACK_WAIT_UNTIL})")
        return FALLBACK_WAIT_UNTIL
    except Exception as exc:
        if _is_target_closed_error(exc):
            print("[WARN] 浏览器/页面在降级导航中被关闭，继续使用当前状态")
            return "target_closed"
        if _is_timeout_error(exc):
            print(
                f"[WARN] domcontentloaded 也超时 ({FALLBACK_TIMEOUT_MS}ms)，"
                "继续等待登录"
            )
            return "timeout"
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

    async with async_playwright() as p:
        print("[步骤0] 启动 Chrome 浏览器...")
        browser = await p.chromium.launch(channel="chrome", headless=False)
        ctx = await browser.new_context()
        page = await ctx.new_page()

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
            except Exception:
                return

        page.on("request", _on_request)

        try:
            await goto_with_fallback(page, DOUYIN_URL)

            print(f"[步骤2] 请在浏览器中完成扫码登录")
            print(f"        超时时间: {LOGIN_POLL_TIMEOUT_SEC} 秒，检测间隔: 2 秒")
            print(f"        检测条件: {BASE_REQUIRED}")
            print()

            max_attempts = LOGIN_POLL_TIMEOUT_SEC // 2
            for i in range(max_attempts):
                await asyncio.sleep(2)
                elapsed = (i + 1) * 2

                cs = await ctx.cookies()
                c = sanitize_cookies(
                    {
                        x["name"]: x["value"]
                        for x in cs
                        if "douyin.com" in x.get("domain", "")
                    }
                )

                if BASE_REQUIRED.issubset(c.keys()):
                    print(f"[步骤2] ✓ 检测到登录 Cookie ({elapsed}s)")
                    print(f"[步骤2]   当前 Cookie: {sorted(c.keys())}")

                    print("[步骤3] 正在从多源提取 msToken...")
                    ms_token = await try_extract_ms_token(
                        page, c, observed_cookie_headers, observed_mstokens
                    )
                    if ms_token and not c.get("msToken"):
                        c["msToken"] = ms_token

                    picked = {k: v for k, v in c.items() if k in SUGGESTED}

                    missing = FULL_REQUIRED - picked.keys()
                    if missing:
                        print(f"[WARN] 缺少必要 Cookie: {sorted(missing)}")
                        print(f"[WARN] 缺少这些可能导致 API 请求被风控拦截")

                    print("[步骤4] 正在写入 config.yml ...")
                    cfg = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}
                    cfg["cookies"] = picked
                    CONFIG_PATH.write_text(
                        yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False),
                        encoding="utf-8",
                    )

                    print()
                    print("=" * 52)
                    print(f"  ✓ 登录成功，已更新 {len(picked)} 个 Cookie")
                    print(f"  Cookie 列表: {sorted(picked.keys())}")
                    print(f"  配置文件: {CONFIG_PATH}")
                    if missing:
                        print(f"  ⚠ 缺失: {sorted(missing)}")
                    print("=" * 52)

                    await browser.close()
                    return 0

                if elapsed % 20 == 0:
                    current_keys = sorted(c.keys()) if c else []
                    print(f"  [{elapsed}s] 等待登录...  当前Cookie: {current_keys}")

            print()
            print(f"[ERROR] 登录超时 ({LOGIN_POLL_TIMEOUT_SEC} 秒)")
            print(f"[ERROR] 最终检测到的 Cookie: {sorted(c.keys()) if c else '无'}")

            if c:
                missing = BASE_REQUIRED - c.keys()
                if missing:
                    print(f"[ERROR] 缺失: {sorted(missing)}")

            await browser.close()
            return 1

        except Exception:
            print()
            print("[ERROR] 脚本执行异常，完整堆栈如下：")
            traceback.print_exc()
            try:
                await browser.close()
            except Exception:
                pass
            return 2


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

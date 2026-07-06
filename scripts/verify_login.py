import asyncio
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()
PROJECT_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_DIR))


async def verify_login():
    print("=" * 60)
    print("  人工确认登录状态")
    print("=" * 60)
    print()

    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("请先安装 Playwright: pip install playwright && playwright install chromium")
        sys.exit(1)

    print("操作步骤:")
    print("1. 浏览器会打开抖音首页")
    print("2. 检查右上角是否显示头像（已登录状态）")
    print("3. 如未登录，请扫码登录")
    print("4. 确认登录后关闭浏览器窗口")
    print()
    print("按 Ctrl+C 可随时退出")
    print("=" * 60)

    from utils.browser_config import USER_DATA_DIR, USER_AGENT, VIEWPORT, ensure_user_data_dir

    async with async_playwright() as p:
        print("\n[启动] 正在打开浏览器...")
        ensure_user_data_dir()
        ctx = await p.chromium.launch_persistent_context(
            USER_DATA_DIR,
            headless=False,
            viewport=VIEWPORT,
            user_agent=USER_AGENT,
            args=["--disable-blink-features=AutomationControlled", "--disable-dev-shm-usage", "--no-sandbox"],
        )

        print("[说明] 使用项目内 Chrome 用户数据目录，登录状态保存在 data/chrome_user_data")

        page = ctx.pages[0] if ctx.pages else await ctx.new_page()

        print("[导航] 正在打开抖音首页...")
        try:
            await page.goto("https://www.douyin.com/", wait_until="domcontentloaded", timeout=60000)
        except Exception as e:
            print(f"[警告] 页面加载超时: {e}")

        print()
        print("=" * 60)
        print("  浏览器已打开")
        print("  请检查右上角是否显示头像（已登录）")
        print("  如未登录，请扫码登录")
        print("  确认登录后关闭浏览器窗口")
        print("=" * 60)
        print()

        try:
            while True:
                await page.wait_for_timeout(500)
        except (KeyboardInterrupt, Exception):
            print("\n[完成] 浏览器已关闭")

        await ctx.close()
        print("[完成] 脚本结束")


if __name__ == "__main__":
    asyncio.run(verify_login())

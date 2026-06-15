"""
打开浏览器用于检查登录状态
运行此脚本会打开一个 Chrome 浏览器窗口，加载抖音网站
可以在浏览器中检查登录状态，手动登录后关闭浏览器
"""
import asyncio
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()
PROJECT_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_DIR))

from config.config_loader import ConfigLoader
from utils.cookie_utils import sanitize_cookies


async def open_browser():
    """打开浏览器用于检查登录状态"""
    config_loader = ConfigLoader(str(PROJECT_DIR / "config.yml"))
    cookies = config_loader.get_cookies()
    
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("请先安装 Playwright: pip install playwright && playwright install chromium")
        return
    
    print("=" * 50)
    print("  打开浏览器检查登录状态")
    print("=" * 50)
    print()
    print("提示:")
    print("1. 浏览器会打开抖音首页")
    print("2. 检查是否已登录（右上角头像）")
    print("3. 如未登录，请扫码登录")
    print("4. 登录完成后关闭浏览器窗口")
    print("5. Cookie 会自动同步到配置文件")
    print()
    print("按 Ctrl+C 可随时退出")
    print("=" * 50)
    
    async with async_playwright() as p:
        print("\n[启动] 正在打开 Chrome 浏览器...")
        browser = await p.chromium.launch(channel="chrome", headless=False)
        ctx = await browser.new_context()
        
        # 添加现有 Cookie
        if cookies:
            cookie_list = [
                {"name": k, "value": v, "domain": ".douyin.com", "path": "/"}
                for k, v in cookies.items()
            ]
            await ctx.add_cookies(cookie_list)
            print(f"[Cookie] 已加载 {len(cookies)} 个 Cookie: {sorted(cookies.keys())}")
        
        page = await ctx.new_page()
        
        # 打开抖音首页
        print("[导航] 正在打开抖音首页...")
        try:
            await page.goto("https://www.douyin.com/", wait_until="domcontentloaded", timeout=60000)
        except Exception as e:
            print(f"[警告] 页面加载超时，继续使用当前状态: {e}")
        
        print()
        print("=" * 50)
        print("  浏览器已打开")
        print("  请检查右上角是否显示头像（已登录）")
        print("  如未登录，请扫码登录")
        print("  登录完成后关闭浏览器窗口")
        print("=" * 50)
        print()
        
        # 等待用户操作
        try:
            while not page.is_closed():
                await page.wait_for_timeout(1000)
        except KeyboardInterrupt:
            print("\n[中断] 用户按下 Ctrl+C")
        
        # 获取浏览器 Cookie 并同步
        if not page.is_closed():
            try:
                browser_cookies = await ctx.cookies()
                new_cookies = sanitize_cookies(
                    {
                        x["name"]: x["value"]
                        for x in browser_cookies
                        if "douyin.com" in x.get("domain", "")
                    }
                )
                
                if new_cookies:
                    # 更新配置文件中的 Cookie
                    import yaml
                    config_path = PROJECT_DIR / "config.yml"
                    cfg = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
                    cfg["cookies"] = new_cookies
                    config_path.write_text(
                        yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False),
                        encoding="utf-8",
                    )
                    print(f"\n[同步] 已更新 {len(new_cookies)} 个 Cookie 到配置文件")
                    print(f"[Cookie] {sorted(new_cookies.keys())}")
            except Exception as e:
                print(f"[错误] Cookie 同步失败: {e}")
        
        await browser.close()
        print("[完成] 浏览器已关闭")


if __name__ == "__main__":
    asyncio.run(open_browser())
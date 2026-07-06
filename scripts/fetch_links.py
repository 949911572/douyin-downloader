import asyncio
import sys
import re
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()
PROJECT_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_DIR))


async def fetch_links(target_url=None):
    """从浏览器获取视频链接
    
    如果 target_url 为空，扫描收藏页面
    如果 target_url 为用户主页地址，扫描该用户的作品页面
    """
    
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("请先安装 Playwright: pip install playwright && playwright install chromium")
        return
    
    is_favorites = target_url is None
    
    if is_favorites:
        title = "从浏览器获取收藏视频列表"
        page_url = "https://www.douyin.com/user/self?from_tab_name=main&showTab=favorite_collection"
        description = "收藏页面"
    else:
        title = "从浏览器获取用户作品列表"
        page_url = target_url
        description = f"用户主页: {target_url}"
    
    print("=" * 60)
    print(f"  {title}")
    print("=" * 60)
    print()
    
    if is_favorites:
        print("操作步骤:")
        print("1. 浏览器会打开抖音收藏页面")
        print("2. 确保已登录（右上角显示头像）")
        print("3. 手动滚动到需要采集的位置，加载所有目标内容")
        print("4. 滚动完成后按 Enter 键，脚本将从上往下采集所有已加载的视频链接")
        print("5. 采集完成后关闭浏览器窗口")
        print()
    else:
        print("操作步骤:")
        print(f"1. 浏览器会打开用户主页: {target_url}")
        print("2. 确保已登录（右上角显示头像）")
        print("3. 手动滚动到需要采集的位置，加载所有目标内容")
        print("4. 滚动完成后按 Enter 键，脚本将从上往下采集所有已加载的视频链接")
        print("5. 采集完成后关闭浏览器窗口")
        print()
    
    print("按 Ctrl+C 可随时退出")
    print("=" * 60)
    
    existing_aweme_ids = set()
    
    db_path = PROJECT_DIR / "dy_downloader.db"
    if db_path.exists():
        try:
            import sqlite3
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            cursor.execute("SELECT aweme_id FROM aweme")
            for row in cursor.fetchall():
                existing_aweme_ids.add(row[0])
            conn.close()
            print(f"[去重] 数据库中已有 {len(existing_aweme_ids)} 个视频记录")
        except Exception as e:
            print(f"[警告] 读取数据库失败: {e}")
    
    config_temp_path = PROJECT_DIR / "config_temp.yml"
    if config_temp_path.exists():
        try:
            import yaml
            with open(config_temp_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}
            config_link_count = 0
            if config.get("link"):
                for link in config["link"]:
                    match = re.search(r"/video/(\d+)", str(link))
                    if match:
                        existing_aweme_ids.add(match.group(1))
                        config_link_count += 1
            print(f"[去重] config_temp.yml 中已有 {config_link_count} 个视频链接")
        except Exception as e:
            print(f"[警告] 读取 config_temp.yml 失败: {e}")
    
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
        
        print(f"[导航] 正在打开{description}...")
        try:
            await page.goto(page_url, wait_until="domcontentloaded", timeout=60000)
        except Exception as e:
            print(f"[警告] 页面加载超时: {e}")

        if is_favorites:
            print("[验证] 等待收藏页面加载...")
            for attempt in range(20):
                current_url = page.url
                if "showTab=favorite_collection" not in current_url:
                    print(f"[等待] 页面跳转中... ({attempt + 1}/20)")
                    await page.wait_for_timeout(2000)
                    continue

                try:
                    video_count = await page.evaluate(
                        "document.querySelectorAll('div[data-e2e=\"user-favorite-list\"] a[href*=\"/video/\"]').length"
                    )
                    if video_count > 0:
                        print(f"[确认] 收藏页面已加载，检测到 {video_count} 个视频元素")
                        break
                except Exception:
                    pass

                print(f"[等待] 收藏内容加载中... ({attempt + 1}/20)")
                await page.wait_for_timeout(2000)
        else:
            print("[等待] 等待页面渲染完成...")
            await page.wait_for_timeout(5000)

        print(f"[调试] 当前URL: {page.url}")
        print()
        print("[提示] 请在浏览器中手动滚动到底部，加载所有需要采集的内容")
        print("[提示] 滚动完成后按 Enter 键开始采集")
        print()
        try:
            await asyncio.get_event_loop().run_in_executor(None, input, "")
        except:
            pass

        print("\n[采集] 开始扫描页面...")

        links = []

        try:
            if is_favorites:
                video_elements = await page.query_selector_all(
                    'div[data-e2e="user-favorite-list"] a[href*="/video/"]'
                )
            else:
                video_elements = await page.query_selector_all('div[data-e2e="user-post-list"] a[href*="/video/"]')

            print(f"[采集] 检测到 {len(video_elements)} 个视频元素")

            for elem in video_elements:
                try:
                    href = await elem.get_attribute("href")
                    if not href:
                        continue

                    match = re.search(r"/video/(\d+)", href)
                    if match:
                        aweme_id = match.group(1)

                        if aweme_id in existing_aweme_ids:
                            continue

                        url = f"https://www.douyin.com/video/{aweme_id}"

                        title = ""
                        try:
                            title_elem = await elem.query_selector("div[data-e2e='video-desc']")
                            if title_elem:
                                title = await title_elem.inner_text()
                        except:
                            pass

                        links.append({
                            "aweme_id": aweme_id,
                            "url": url,
                            "title": title.strip()[:100] if title else "",
                        })
                        print(f"  ✓ {aweme_id} - {title[:50]}..." if title else f"  ✓ {aweme_id}")
                except:
                    continue
        except Exception as e:
            print(f"[错误] 扫描失败: {e}")

        print(f"\n[完成] 共收集 {len(links)} 个新视频")
        print("[提示] 采集完成，请关闭浏览器窗口进行下一步")
        
        if links:
            config_temp_path = PROJECT_DIR / "config_temp.yml"
            if config_temp_path.exists():
                import yaml
                with open(config_temp_path, "r", encoding="utf-8") as f:
                    config = yaml.safe_load(f) or {}
                
                existing_links = set(config.get("link") or [])
                new_links = [link["url"] for link in links]
                
                all_links = list(existing_links)
                for link in new_links:
                    if link not in existing_links:
                        all_links.append(link)
                
                config["link"] = all_links
                
                with open(config_temp_path, "w", encoding="utf-8") as f:
                    yaml.safe_dump(config, f, allow_unicode=True, sort_keys=False)
                
                print(f"\n[配置] 已追加 {len(links)} 个链接到 config_temp.yml")
                print()
                print("=" * 60)
                print("  下一步操作")
                print("=" * 60)
                print(f"  1. 检查配置文件: config_temp.yml")
                print(f"     - 确认 link 列表包含正确的视频链接")
                print(f"     - 可根据需要调整 path 下载目录")
                print()
                print(f"  2. 执行下载命令:")
                print(f"     .\\scripts\\douyin.ps1 -Action download -ConfigFile config_temp.yml")
                print("=" * 60)
            
            print("\n[示例] 前5个视频:")
            for i, link in enumerate(links[:5], 1):
                print(f"  {i}. {link['url']}")
        
        try:
            await ctx.close()
        except Exception:
            pass
        print("\n[结束] 浏览器已关闭")


if __name__ == "__main__":
    target_url = sys.argv[1] if len(sys.argv) > 1 else None
    asyncio.run(fetch_links(target_url))
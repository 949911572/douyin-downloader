import os
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).parent.parent


def check_python_version() -> bool:
    if sys.version_info < (3, 9):
        print(f"❌ Python 版本过低: 当前 {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
        print(f"   影响: 无法运行项目，部分依赖要求 Python 3.9+")
        print(f"   建议: 升级 Python 到 3.9 或更高版本")
        return False
    print(f"✓ Python 版本: {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
    return True


def check_dependencies() -> bool:
    required_packages = [
        ('aiohttp', '3.9.0', 'aiohttp'),
        ('aiofiles', '23.2.1', 'aiofiles'),
        ('aiosqlite', '0.19.0', 'aiosqlite'),
        ('rich', '13.7.0', 'rich'),
        ('yaml', '6.0.1', 'pyyaml'),
        ('dateutil', '2.8.2', 'python-dateutil'),
        ('gmssl', '3.2.2', 'gmssl'),
        ('playwright', '1.40.0', 'playwright'),
    ]
    
    missing_packages = []
    for import_name, min_version, pkg_name in required_packages:
        try:
            __import__(import_name)
            print(f"✓ 依赖包: {pkg_name}")
        except ImportError:
            missing_packages.append((pkg_name, min_version))
    
    if missing_packages:
        print("\n❌ 缺少以下依赖包:")
        for pkg_name, min_version in missing_packages:
            print(f"   - {pkg_name} (>= {min_version})")
            print(f"     影响: 核心功能无法运行")
        print(f"\n   建议: 运行 pip install -r requirements.txt")
        return False
    
    return True


def check_playwright_browser() -> bool:
    try:
        from playwright.sync_api import sync_playwright
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            browser.close()
            print("✓ Playwright 浏览器: Chromium 已安装且可正常启动")
            return True
    except Exception as e:
        if "Executable doesn't exist" in str(e):
            print("❌ Playwright 浏览器: Chromium 未安装")
            print("   影响: 浏览器回退功能无法使用，分页受限的用户主页无法完整拉取")
            print("         fetch-favorites、refresh-cookies、verify-login 功能无法运行")
            print("   建议: 运行 python -m playwright install chromium")
        else:
            print(f"❌ Playwright 浏览器检查失败: {e}")
            print("   影响: 同上")
        return False


def check_config_file() -> bool:
    config_path = PROJECT_DIR / 'config.yml'
    if config_path.exists():
        print(f"✓ 配置文件: config.yml 存在")
        return True
    else:
        print("❌ 配置文件: config.yml 不存在")
        print("   影响: 无法读取下载配置")
        print("   建议: 复制 config.example.yml 并重命名为 config.yml")
        return False


def check_data_directories() -> bool:
    required_dirs = [
        ('data', '运行时数据目录'),
        ('data/logs', '下载日志目录'),
        ('data/error_logs', '错误日志目录'),
        ('data/failed_videos', '失败视频记录目录'),
        ('data/chrome_user_data', 'Chrome 用户数据目录'),
    ]
    
    missing_dirs = []
    for dir_name, description in required_dirs:
        dir_path = PROJECT_DIR / dir_name
        if dir_path.exists():
            print(f"✓ 目录: {dir_name} ({description})")
        else:
            missing_dirs.append((dir_name, description))
    
    if missing_dirs:
        print("\n❌ 缺少以下目录:")
        for dir_name, description in missing_dirs:
            print(f"   - {dir_name} ({description})")
            print(f"     影响: 相关功能无法保存数据")
        print(f"\n   建议: 运行脚本时会自动创建，或手动创建")
        return False
    
    return True


def check_cookie() -> bool:
    config_path = PROJECT_DIR / 'config.yml'
    if not config_path.exists():
        return True
    
    try:
        import yaml
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        cookies = config.get('cookies', '')
        if cookies and 'sessionid' in cookies:
            print("✓ Cookie: 已配置")
            return True
        else:
            print("⚠ Cookie: 未配置或不完整")
            print("   影响: 部分需要登录的视频可能无法下载")
            print("   建议: 运行 .\\scripts\\douyin.ps1 -Action refresh-cookies 获取 Cookie")
            return True
    except Exception as e:
        print(f"⚠ Cookie 检查失败: {e}")
        return True


def run_environment_check() -> bool:
    """运行完整的环境检查"""
    print("=" * 60)
    print("环境检查")
    print("=" * 60)
    
    checks = [
        check_python_version,
        check_dependencies,
        check_playwright_browser,
        check_config_file,
        check_data_directories,
        check_cookie,
    ]
    
    all_passed = True
    for check in checks:
        print()
        if not check():
            all_passed = False
    
    print("\n" + "=" * 60)
    if all_passed:
        print("✓ 所有检查通过，可以正常运行")
    else:
        print("✗ 部分检查未通过，请根据上述提示修复")
        print("\n修复后请重新运行脚本")
    
    return all_passed


if __name__ == '__main__':
    run_environment_check()
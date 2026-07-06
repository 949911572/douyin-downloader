import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()
PROJECT_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_DIR))

from config.config_loader import ConfigLoader


def check_cookies(config_path: str) -> bool:
    config_loader = ConfigLoader(config_path)
    cookies = config_loader.get_cookies()

    if not cookies:
        print("[ERROR] 配置文件中未找到Cookie")
        return False

    required_keys = {"ttwid", "odin_tt", "passport_csrf_token"}
    
    invalid = []
    for key in required_keys:
        if key not in cookies or not cookies.get(key):
            invalid.append(key)
    
    if invalid:
        print(f"[ERROR] Cookie以下字段值无效（缺失或为空）: {', '.join(invalid)}")
        print()
        print("请按以下步骤操作:")
        print("  1. .\\scripts\\douyin.ps1 -Action verify-login    (确保浏览器已登录)")
        print("  2. .\\scripts\\douyin.ps1 -Action refresh-cookies (刷新Cookie)")
        return False

    print("[OK] Cookie字段完整")
    return True


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python check_cookies.py <config_path>")
        sys.exit(1)

    config_path = sys.argv[1]
    success = check_cookies(config_path)
    sys.exit(0 if success else 1)

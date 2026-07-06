from pathlib import Path

PROJECT_DIR = Path(__file__).parent.parent

USER_DATA_DIR = str(PROJECT_DIR / "data" / "chrome_user_data")

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

VIEWPORT = {"width": 1280, "height": 800}

DEFAULT_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--disable-dev-shm-usage",
    "--no-sandbox",
]


def ensure_user_data_dir():
    Path(USER_DATA_DIR).mkdir(parents=True, exist_ok=True)
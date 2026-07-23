from pathlib import Path
from typing import Dict, List

PROJECT_DIR: Path = Path(__file__).parent.parent

USER_DATA_DIR: str = str(PROJECT_DIR / "data" / "chrome_user_data")

USER_AGENT: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

VIEWPORT: Dict[str, int] = {"width": 1280, "height": 800}

DEFAULT_ARGS: List[str] = [
    "--disable-blink-features=AutomationControlled",
    "--disable-dev-shm-usage",
    "--no-sandbox",
]


def ensure_user_data_dir() -> None:
    Path(USER_DATA_DIR).mkdir(parents=True, exist_ok=True)

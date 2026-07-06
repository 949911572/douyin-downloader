import os
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from utils.cookie_utils import parse_cookie_header, sanitize_cookies

from .default_config import DEFAULT_CONFIG


class ConfigLoader:
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path
        self.config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        config = deepcopy(DEFAULT_CONFIG)

        if self.config_path and os.path.exists(self.config_path):
            with open(self.config_path, "r", encoding="utf-8") as f:
                file_config = yaml.safe_load(f) or {}
                config = self._merge_config(config, file_config)

        env_config = self._load_env_config()
        if env_config:
            config = self._merge_config(config, env_config)

        return config

    def _merge_config(
        self, base: Dict[str, Any], override: Dict[str, Any]
    ) -> Dict[str, Any]:
        result = base.copy()
        for key, value in override.items():
            if (
                key in result
                and isinstance(result[key], dict)
                and isinstance(value, dict)
            ):
                result[key] = self._merge_config(result[key], value)
            else:
                result[key] = value
        return result

    def _load_env_config(self) -> Dict[str, Any]:
        env_config = {}
        if os.getenv("DOUYIN_COOKIE"):
            env_config["cookie"] = os.getenv("DOUYIN_COOKIE")
        if os.getenv("DOUYIN_PATH"):
            env_config["path"] = os.getenv("DOUYIN_PATH")
        if os.getenv("DOUYIN_THREAD"):
            env_config["thread"] = int(os.getenv("DOUYIN_THREAD"))
        return env_config

    def update(self, **kwargs):
        for key, value in kwargs.items():
            if key in self.config:
                if isinstance(self.config[key], dict) and isinstance(value, dict):
                    self.config[key].update(value)
                else:
                    self.config[key] = value
            else:
                self.config[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        return self.config.get(key, default)

    def get_cookies(self) -> Dict[str, str]:
        cookies_config = self.config.get("cookies") or self.config.get("cookie")

        if isinstance(cookies_config, str):
            if cookies_config == "auto":
                return {}
            return self._parse_cookie_string(cookies_config)
        elif isinstance(cookies_config, dict):
            return sanitize_cookies(cookies_config)
        return {}

    def _parse_cookie_string(self, cookie_str: str) -> Dict[str, str]:
        return sanitize_cookies(parse_cookie_header(cookie_str))

    def get_links(self) -> List[str]:
        links = self.config.get("link", [])
        if isinstance(links, str):
            return [links]
        return links

    def validate(self) -> bool:
        errors = []
        
        # 检查链接列表
        links = self.get_links()
        if not links:
            errors.append("配置错误：未配置任何下载链接 (link)")
        elif len(links) > 100:
            from utils.logger import setup_logger
            logger = setup_logger("ConfigLoader")
            logger.warning(f"链接数量较多 ({len(links)}个)，建议分批下载以提高稳定性")
        
        # 检查下载路径
        download_path = self.config.get("path")
        if not download_path:
            errors.append("配置错误：未配置下载路径 (path)")
        else:
            import os
            path = os.path.dirname(download_path) or download_path
            if not os.path.exists(path):
                try:
                    os.makedirs(path, exist_ok=True)
                except Exception as e:
                    errors.append(f"配置错误：无法创建下载目录 '{path}': {e}")
        
        # 检查重试配置
        retry_config = self.config.get("retry", {})
        max_retries = retry_config.get("max_retries", 3)
        retry_delay = retry_config.get("delay", 5)
        if not isinstance(max_retries, int) or max_retries < 0:
            errors.append(f"配置错误：retry.max_retries 应为非负整数，当前值: {max_retries}")
        if not isinstance(retry_delay, int) or retry_delay < 0:
            errors.append(f"配置错误：retry.delay 应为非负整数，当前值: {retry_delay}")
        
        # 输出错误信息
        if errors:
            from utils.logger import setup_logger
            logger = setup_logger("ConfigLoader")
            for error in errors:
                logger.error(error)
            return False
        
        return True

"""
重试处理器模块
提供异步操作的自动重试功能，支持：
- 可配置的最大重试次数
- 指数退避的重试延迟
- 不可重试异常类型识别
- 异常捕获和日志记录
"""

import asyncio
from typing import Callable, Any, TypeVar, Tuple, Type
from utils.logger import setup_logger

logger = setup_logger('RetryHandler')

T = TypeVar('T')

# 不可重试的异常类型：这些异常表示永久性失败，重试无意义
NON_RETRYABLE_EXCEPTIONS: Tuple[Type[Exception], ...] = (
    FileNotFoundError,
    PermissionError,
    ValueError,
    TypeError,
    KeyError,
)


class RetryHandler:
    def __init__(self, max_retries: int = 3, retry_delay: int = 5):
        self.max_retries = max_retries
        self.retry_delay = retry_delay

    def _is_retryable(self, error: Exception) -> bool:
        return not isinstance(error, NON_RETRYABLE_EXCEPTIONS)

    def _get_delay(self, attempt: int) -> float:
        return self.retry_delay * (2 ** attempt)

    async def execute_with_retry(self, func: Callable[..., T], *args, **kwargs) -> T:
        last_error = None

        for attempt in range(self.max_retries):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                last_error = e

                if not self._is_retryable(e):
                    logger.error(f"Non-retryable error: {e}")
                    raise

                if attempt < self.max_retries - 1:
                    delay = self._get_delay(attempt)
                    logger.warning(f"Attempt {attempt + 1} failed: {e}, retrying in {delay}s...")
                    await asyncio.sleep(delay)

        logger.error(f"All {self.max_retries} attempts failed: {last_error}")
        raise last_error

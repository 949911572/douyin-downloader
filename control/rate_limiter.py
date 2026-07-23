"""
请求限流模块
控制API请求频率，防止触发抖音反爬机制：
- 基于令牌桶算法的速率限制
- 可配置的最大请求频率
- 支持随机抖动，避免固定间隔被识别
- 线程安全的异步锁保护
"""

import asyncio
import random
import time


class RateLimiter:
    def __init__(self, max_per_second: float = 2, jitter: float = 0.5):
        self.max_per_second = max_per_second
        self.min_interval = 1.0 / max_per_second
        self.jitter = jitter
        self.last_request = 0
        self._lock = asyncio.Lock()

    async def acquire(self):
        async with self._lock:
            current = time.time()
            time_since_last = current - self.last_request

            if time_since_last < self.min_interval:
                wait_time = self.min_interval - time_since_last
                if self.jitter > 0:
                    wait_time += random.uniform(0, self.jitter)
                await asyncio.sleep(wait_time)

            self.last_request = time.time()

"""
任务队列管理器模块
管理并发下载任务，控制最大并发数：
- 基于Semaphore的并发控制
- 批量任务处理
- 异常捕获和错误返回
"""

import asyncio
from typing import List, Callable, Any, TypeVar
from utils.logger import setup_logger

logger = setup_logger('QueueManager')

T = TypeVar('T')


class QueueManager:
    def __init__(self, max_workers: int = 5):
        self.max_workers = max_workers
        self.semaphore = asyncio.Semaphore(max_workers)

    async def process_tasks(
        self, 
        tasks: List[Callable[..., Any]], 
        *args, 
        **kwargs
    ) -> List[Any]:
        """批量处理任务

        将相同的参数传递给每个任务，适合所有任务使用相同参数的场景。
        对于需要不同参数的任务，使用 download_batch 方法。

        Args:
            tasks: 可调用对象列表（支持异步函数）
            args: 传递给每个任务的位置参数
            kwargs: 传递给每个任务的关键字参数

        Returns:
            任务执行结果列表
        """
        async def _task_wrapper(task: Callable[..., Any]) -> Any:
            async with self.semaphore:
                try:
                    return await task(*args, **kwargs)
                except Exception as e:
                    logger.error(f"Task failed: {e}")
                    return None

        results = await asyncio.gather(*[_task_wrapper(task) for task in tasks], return_exceptions=True)
        return results

    async def download_batch(self, download_func: Callable, items: List[Any]) -> List[Any]:
        async def _download_wrapper(item):
            async with self.semaphore:
                try:
                    return await download_func(item)
                except Exception as e:
                    logger.error(f"Download failed for item: {e}")
                    return {'status': 'error', 'error': str(e), 'item': item}

        results = await asyncio.gather(*[_download_wrapper(item) for item in items], return_exceptions=False)
        return results

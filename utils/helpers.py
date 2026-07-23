from datetime import datetime
from typing import List, Optional, Union


def parse_timestamp(timestamp: Union[int, str], fmt: str = '%Y-%m-%d %H:%M:%S') -> str:
    try:
        if isinstance(timestamp, str):
            timestamp = int(timestamp)
        return datetime.fromtimestamp(timestamp).strftime(fmt)
    except (ValueError, TypeError, OSError):
        return str(timestamp)


def format_size(bytes_size: Union[int, float]) -> str:
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_size < 1024.0:
            return f"{bytes_size:.2f} {unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.2f} TB"


def format_duration(seconds: int) -> str:
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


def parse_video_timestamp(create_time) -> int:
    """解析视频的 create_time，返回时间戳整数
    
    Args:
        create_time: 可能是 int、str 或其他类型
        
    Returns:
        int: 时间戳，解析失败返回 0
    """
    if create_time is None:
        return 0
    if isinstance(create_time, str):
        try:
            return int(create_time)
        except ValueError:
            return 0
    try:
        return int(create_time)
    except (ValueError, TypeError):
        return 0


def get_latest_video_time(aweme_list: List[dict]) -> Optional[str]:
    """从视频列表中获取最新视频时间（格式化的字符串）
    
    Args:
        aweme_list: 视频列表，每个元素包含 create_time 字段
        
    Returns:
        str: 格式化的时间字符串 '%Y-%m-%d %H:%M:%S'，无有效数据返回 None
    """
    if not aweme_list:
        return None
    
    create_times = []
    for item in aweme_list:
        ct = parse_video_timestamp(item.get("create_time"))
        create_times.append(ct)
    
    latest = max(create_times, default=0)
    if latest:
        return datetime.fromtimestamp(latest).strftime('%Y-%m-%d %H:%M:%S')
    return None

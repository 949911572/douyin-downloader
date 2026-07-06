import json
import os
from datetime import datetime
from typing import Dict, List, Optional

class FailedVideoManager:
    """管理下载失败的视频列表"""
    
    def __init__(self, data_dir: str = "data"):
        self.failed_dir = os.path.join(data_dir, "failed_videos")
        os.makedirs(self.failed_dir, exist_ok=True)
    
    def record_failed_video(
        self,
        url: str,
        aweme_id: str,
        title: str,
        author_name: str,
        sec_uid: str,
        error_message: str = "",
    ):
        """记录下载失败的视频"""
        failed_video = {
            'aweme_id': aweme_id,
            'url': url,
            'title': title,
            'author_name': author_name,
            'sec_uid': sec_uid,
            'error_message': error_message,
            'failed_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'status': 'failed',  # failed, processed, skipped
        }
        
        # 按日期创建文件
        date_str = datetime.now().strftime('%Y%m%d')
        file_path = os.path.join(self.failed_dir, f"failed_{date_str}.json")
        
        # 读取现有数据
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                try:
                    data = json.load(f)
                except json.JSONDecodeError:
                    data = []
        else:
            data = []
        
        # 检查是否已存在
        existing = next((item for item in data if item['aweme_id'] == aweme_id), None)
        if existing:
            # 更新失败记录
            existing['error_message'] = error_message
            existing['failed_time'] = failed_video['failed_time']
            existing['status'] = 'failed'
        else:
            data.append(failed_video)
        
        # 保存
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def get_failed_videos(self, status: str = 'failed') -> List[Dict]:
        """获取失败视频列表"""
        all_videos = []
        
        for filename in os.listdir(self.failed_dir):
            if filename.startswith('failed_') and filename.endswith('.json'):
                file_path = os.path.join(self.failed_dir, filename)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        if status:
                            data = [item for item in data if item.get('status') == status]
                        all_videos.extend(data)
                except Exception as e:
                    print(f"读取失败视频文件失败: {filename}, error: {e}")
        
        return all_videos
    
    def mark_as_processed(self, aweme_id: str) -> bool:
        """标记视频为已处理"""
        return self._update_status(aweme_id, 'processed')
    
    def mark_as_skipped(self, aweme_id: str) -> bool:
        """标记视频为跳过（不需要下载）"""
        return self._update_status(aweme_id, 'skipped')
    
    def _update_status(self, aweme_id: str, status: str) -> bool:
        """更新视频状态"""
        updated = False
        
        for filename in os.listdir(self.failed_dir):
            if filename.startswith('failed_') and filename.endswith('.json'):
                file_path = os.path.join(self.failed_dir, filename)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    for item in data:
                        if item['aweme_id'] == aweme_id:
                            item['status'] = status
                            item['processed_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                            updated = True
                            break
                    
                    if updated:
                        with open(file_path, 'w', encoding='utf-8') as f:
                            json.dump(data, f, ensure_ascii=False, indent=2)
                except Exception as e:
                    print(f"更新失败视频状态失败: {filename}, error: {e}")
        
        return updated
    
    def get_failed_count(self) -> int:
        """获取未处理的失败视频数量"""
        videos = self.get_failed_videos(status='failed')
        return len(videos)
"""
扫描记录管理模块
记录每个链接对应的用户信息和扫描状态，用于智能跳过判断：
- 记录扫描时间和结果
- 根据阈值自动跳过近期已处理的链接
- 失败记录检测（有失败则不跳过）
"""

import os
import json
from datetime import datetime, timedelta
from typing import Dict, Optional, Any


class ScanRecordManager:
    """管理链接扫描记录，用于智能跳过判断"""
    
    def __init__(self, record_file: str = None, skip_threshold_hours: int = 4):
        if record_file is None:
            record_file = os.path.join(os.path.dirname(__file__), '..', 'data', 'scan_records.json')
        
        self.record_file = record_file
        self.skip_threshold_hours = skip_threshold_hours
        self.records: Dict[str, Dict] = {}
        self._load_records()
    
    def _load_records(self):
        """加载本地记录文件"""
        if os.path.exists(self.record_file):
            try:
                with open(self.record_file, 'r', encoding='utf-8') as f:
                    self.records = json.load(f)
            except Exception as e:
                print(f"加载扫描记录失败: {e}")
                self.records = {}
        else:
            # 确保目录存在
            os.makedirs(os.path.dirname(self.record_file), exist_ok=True)
            self.records = {}
    
    def _save_records(self):
        """保存记录到文件"""
        try:
            with open(self.record_file, 'w', encoding='utf-8') as f:
                json.dump(self.records, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存扫描记录失败: {e}")
    
    def get_record(self, url: str) -> Optional[Dict]:
        """获取指定链接的记录"""
        return self.records.get(url)
    
    def should_skip(self, url: str) -> bool:
        """判断是否应该跳过该链接（N小时内已成功处理）
        
        跳过条件：
        1. 阈值不为0
        2. 存在记录
        3. 上次扫描时间在阈值内
        4. 记录完整（有sec_uid）
        5. 无失败记录
        6. 解析未失败
        
        Args:
            url: 链接地址
            
        Returns:
            是否应该跳过
        """
        if self.skip_threshold_hours == 0:
            return False
        
        record = self.get_record(url)
        if not record:
            return False
        
        return (
            self._is_within_time_threshold(record)
            and self._is_record_complete(record)
            and not self._has_failure(record)
        )
    
    def _is_within_time_threshold(self, record: Dict) -> bool:
        """检查上次扫描时间是否在阈值内
        
        Args:
            record: 扫描记录
            
        Returns:
            是否在时间阈值内
        """
        last_scan_time = record.get('last_scan_time')
        if not last_scan_time:
            return False
        
        try:
            scan_time = datetime.strptime(last_scan_time, '%Y-%m-%d %H:%M:%S')
            cutoff_time = datetime.now() - timedelta(hours=self.skip_threshold_hours)
            return scan_time >= cutoff_time
        except ValueError:
            return False
    
    def _is_record_complete(self, record: Dict) -> bool:
        """检查记录是否完整（有sec_uid）
        
        Args:
            record: 扫描记录
            
        Returns:
            记录是否完整
        """
        sec_uid = record.get('sec_uid', '')
        return bool(sec_uid)
    
    def _has_failure(self, record: Dict) -> bool:
        """检查是否有失败记录
        
        Args:
            record: 扫描记录
            
        Returns:
            是否有失败
        """
        return record.get('failed', 0) > 0 or record.get('parse_failed', False)
    
    def get_skip_reason(self, url: str) -> str:
        """获取跳过原因"""
        record = self.get_record(url)
        if not record:
            return ""
        
        username = record.get('username', '未知')
        last_scan_time = record.get('last_scan_time', '')
        total = record.get('total', 0)
        success = record.get('success', 0)
        failed = record.get('failed', 0)
        
        reason = f"由于本地记录显示该用户在 {last_scan_time} 已成功处理（视频总数:{total}, 成功:{success}, 失败:{failed}）"
        reason += "，本次跳过"
        
        return reason
    
    def update_record(
        self,
        url: str,
        username: str,
        sec_uid: str,
        total: int = 0,
        success: int = 0,
        failed: int = 0,
        skipped: int = 0,
        parse_failed: bool = False,
        last_video_time: str = None
    ):
        """更新链接记录"""
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # 获取原有记录（用于保留上次的视频时间）
        existing_record = self.records.get(url, {})
        
        # 如果 last_video_time 为空字符串，说明是单视频下载或没有新视频
        if last_video_time == '':
            video_time = existing_record.get('last_video_time', '')
            scan_time = now
        else:
            # 只有在有新视频时才更新 last_video_time，否则保留原有记录
            video_time = last_video_time if last_video_time else existing_record.get('last_video_time', now)
            scan_time = now
        
        self.records[url] = {
            'username': username,
            'sec_uid': sec_uid,
            'total': total,
            'success': success,
            'failed': failed,
            'skipped': skipped,
            'parse_failed': parse_failed,
            'last_scan_time': scan_time,
            'last_video_time': video_time
        }
        
        self._save_records()
    
    def update_last_video_time(self, url: str, last_video_time: str, username: str = None):
        """只更新 last_video_time 和 last_scan_time，保留其他原有数据
        
        Args:
            url: 链接地址
            last_video_time: 最新视频时间
            username: 可选的用户名更新
        """
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        if url in self.records:
            # 保留原有数据，只更新时间字段
            record = self.records[url]
            record['last_video_time'] = last_video_time
            record['last_scan_time'] = now
            if username:
                record['username'] = username
        else:
            # 如果记录不存在，创建新记录
            self.records[url] = {
                'username': username or '',
                'sec_uid': '',
                'total': 0,
                'success': 0,
                'failed': 0,
                'skipped': 0,
                'parse_failed': False,
                'last_scan_time': now,
                'last_video_time': last_video_time
            }
        
        self._save_records()
    
    def mark_parse_failed(self, url: str):
        """标记解析失败"""
        record = self.get_record(url)
        if record:
            record['parse_failed'] = True
            record['last_scan_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            self._save_records()
        else:
            self.records[url] = {
                'username': '',
                'sec_uid': '',
                'total': 0,
                'success': 0,
                'failed': 0,
                'skipped': 0,
                'parse_failed': True,
                'last_scan_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'last_video_time': ''
            }
            self._save_records()
    
    def get_all_records(self) -> Dict[str, Dict]:
        """获取所有记录"""
        return self.records
    
    def print_summary(self):
        """打印记录摘要"""
        total_count = len(self.records)
        if total_count == 0:
            print("本地扫描记录：无记录")
            return
        
        success_count = sum(1 for r in self.records.values() if r.get('failed', 0) == 0 and not r.get('parse_failed', False))
        failed_count = sum(1 for r in self.records.values() if r.get('failed', 0) > 0 or r.get('parse_failed', False))
        
        print(f"\n📊 本地扫描记录摘要")
        print(f"   总记录数: {total_count}")
        print(f"   成功记录: {success_count}")
        print(f"   失败记录: {failed_count}")
        
        # 显示最近扫描的记录
        recent_records = sorted(
            self.records.items(),
            key=lambda x: x[1].get('last_scan_time', ''),
            reverse=True
        )[:5]
        
        if recent_records:
            print(f"\n   最近扫描记录:")
            for url, record in recent_records:
                username = record.get('username', '未知')
                last_scan = record.get('last_scan_time', '')
                print(f"   - {username} ({last_scan})")
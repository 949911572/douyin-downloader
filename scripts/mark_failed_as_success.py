#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
将失败视频标记为已下载脚本

用法:
    python scripts/mark_failed_as_success.py [失败文件路径]
    
如果不指定失败文件路径，则自动查找并处理 data/failed_videos/ 目录下的所有失败文件

功能:
    1. 读取失败视频列表
    2. 将视频标记为已下载（更新数据库）
    3. 清空失败文件（可选）
"""

import sqlite3
import json
import os
import sys
from datetime import datetime

def mark_failed_as_success(failed_file=None, clear_file=True):
    """
    将失败视频标记为已下载
    
    :param failed_file: 失败文件路径，为None时自动查找
    :param clear_file: 是否清空失败文件
    """
    failed_videos = []
    
    if failed_file:
        # 使用指定的失败文件
        if not os.path.exists(failed_file):
            print(f"错误：文件不存在: {failed_file}")
            return False
        
        with open(failed_file, 'r', encoding='utf-8') as f:
            failed_videos = json.load(f)
        
        files_processed = [failed_file]
    else:
        # 自动查找所有失败文件
        failed_dir = 'data/failed_videos'
        if not os.path.exists(failed_dir):
            print(f"错误：目录不存在: {failed_dir}")
            return False
        
        failed_files = [f for f in os.listdir(failed_dir) if f.startswith('failed_') and f.endswith('.json')]
        if not failed_files:
            print("未找到任何失败文件")
            return True
        
        files_processed = []
        for f in failed_files:
            file_path = os.path.join(failed_dir, f)
            with open(file_path, 'r', encoding='utf-8') as fp:
                videos = json.load(fp)
                failed_videos.extend(videos)
            files_processed.append(file_path)
    
    if not failed_videos:
        print("没有需要处理的失败视频")
        return True
    
    print(f"找到 {len(failed_videos)} 个失败视频，分布在 {len(files_processed)} 个文件中")
    
    # 连接数据库（与主程序使用相同的数据库路径）
    try:
        conn = sqlite3.connect('dy_downloader.db')
        cursor = conn.cursor()
    except Exception as e:
        print(f"数据库连接失败: {e}")
        return False
    
    success_count = 0
    fail_count = 0
    
    for video in failed_videos:
        try:
            aweme_id = video.get('aweme_id', '')
            author_name = video.get('author_name', '未知')
            sec_uid = video.get('sec_uid', '')
            
            if not aweme_id:
                print(f"跳过：缺少 aweme_id")
                fail_count += 1
                continue
            
            # 更新或插入记录为成功
            cursor.execute('''
                INSERT OR REPLACE INTO aweme 
                (aweme_id, author_name, sec_uid, downloaded, download_time, created_at)
                VALUES (?, ?, ?, 1, ?, ?)
            ''', (aweme_id, author_name, sec_uid, datetime.now().isoformat(), datetime.now().isoformat()))
            
            success_count += 1
            print(f'已标记: {aweme_id[:10]}... | {author_name}')
        
        except Exception as e:
            print(f"处理失败: {video.get('aweme_id', '未知')} - {e}")
            fail_count += 1
    
    conn.commit()
    conn.close()
    
    print(f'\n=== 处理结果 ===')
    print(f'成功标记: {success_count} 个')
    print(f'处理失败: {fail_count} 个')
    
    # 清空失败文件
    if clear_file:
        for file_path in files_processed:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump([], f)
                print(f'已清空: {os.path.basename(file_path)}')
            except Exception as e:
                print(f"清空文件失败 {file_path}: {e}")
    
    return True

if __name__ == '__main__':
    # 解析命令行参数
    failed_file = None
    clear_file = True
    
    if len(sys.argv) > 1:
        if sys.argv[1] == '-h' or sys.argv[1] == '--help':
            print(__doc__)
            sys.exit(0)
        elif sys.argv[1] == '--no-clear':
            clear_file = False
            if len(sys.argv) > 2:
                failed_file = sys.argv[2]
        else:
            failed_file = sys.argv[1]
    
    print("=" * 50)
    print("  将失败视频标记为已下载")
    print("=" * 50)
    
    success = mark_failed_as_success(failed_file, clear_file)
    
    print("=" * 50)
    if success:
        print("操作完成")
        sys.exit(0)
    else:
        print("操作失败")
        sys.exit(1)

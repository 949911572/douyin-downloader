#!/usr/bin/env python3
"""
合并两个数据库的去重信息
将 data/douyin_downloader.db 中的 aweme_id 合并到 dy_downloader.db
"""
import sqlite3
import os

def merge_databases(source_db, target_db):
    # 检查源数据库是否存在
    if not os.path.exists(source_db):
        print(f"源数据库不存在: {source_db}")
        return False
    
    # 检查目标数据库是否存在
    if not os.path.exists(target_db):
        print(f"目标数据库不存在: {target_db}")
        return False
    
    print(f"正在从 {source_db} 合并 aweme_id 到 {target_db}")
    
    try:
        # 连接目标数据库
        target_conn = sqlite3.connect(target_db)
        target_cursor = target_conn.cursor()
        
        # 连接源数据库
        source_conn = sqlite3.connect(source_db)
        source_cursor = source_conn.cursor()
        
        # 获取源数据库中的所有 aweme_id
        source_cursor.execute("SELECT aweme_id, author_name FROM aweme")
        rows = source_cursor.fetchall()
        
        if not rows:
            print("源数据库中没有记录")
            return True
        
        # 插入到目标数据库（使用 INSERT OR IGNORE 避免重复）
        insert_sql = """
            INSERT OR IGNORE INTO aweme (aweme_id, aweme_type, title, author_id, author_name, 
                                        create_time, download_time, file_path, metadata)
            VALUES (?, 'video', '', '', ?, 0, 0, '', '')
        """
        
        count = 0
        for aweme_id, author_name in rows:
            try:
                target_cursor.execute(insert_sql, (aweme_id, author_name))
                if target_cursor.rowcount > 0:
                    count += 1
            except Exception as e:
                pass
        
        target_conn.commit()
        target_conn.close()
        source_conn.close()
        
        print(f"合并完成！成功插入 {count} 条新记录")
        return True
        
    except Exception as e:
        print(f"合并失败: {e}")
        return False

if __name__ == '__main__':
    source_db = 'data/douyin_downloader.db'
    target_db = 'dy_downloader.db'
    
    if merge_databases(source_db, target_db):
        # 询问是否删除源数据库
        response = input("是否删除旧数据库文件 data/douyin_downloader.db？(y/N): ").strip().lower()
        if response == 'y':
            os.remove(source_db)
            print(f"已删除 {source_db}")
        else:
            print(f"保留 {source_db}")
    else:
        print("合并未成功")
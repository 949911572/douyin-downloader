#!/usr/bin/env python3
import sys
import os
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

os.chdir(project_root)

from utils.logger import setup_logger

logger = setup_logger('main')

def check_readme_recommendation():
    """检查是否通过推荐的方式运行脚本"""
    # 设置标准输出编码为 UTF-8，避免中文乱码
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    elif sys.platform.startswith('win'):
        # Windows 特殊处理
        try:
            import win32api
            import win32console
            win32console.SetConsoleOutputCP(65001)
        except ImportError:
            pass

    # 检查是否通过 PowerShell 脚本调用（通过检查环境变量）
    if os.environ.get('DOUYIN_DOWNLOADER_LAUNCHED_BY_PS1') != 'true':
        logger.warning("未使用推荐的运行方式，建议使用: .\\scripts\\douyin.ps1")
        logger.warning("PowerShell 脚本提供 UTF-8 编码设置、配置文件检查和自动打开下载目录等功能")

if __name__ == '__main__':
    check_readme_recommendation()
    from cli.main import main
    main()
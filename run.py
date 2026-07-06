#!/usr/bin/env python3
import sys
import os
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

os.chdir(project_root)

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
        print("=" * 60)
        print("  ⚠ 警告：未使用推荐的运行方式")
        print("=" * 60)
        print()
        print("根据 README.md，建议使用以下方式运行：")
        print("    .\\scripts\\douyin.ps1")
        print()
        print("PowerShell 脚本的优势：")
        print("  * 自动设置 UTF-8 编码，避免中文乱码")
        print("  * 自动检查配置文件和目录权限")
        print("  * 下载完成后自动打开下载目录")
        print()
        print("如果你清楚自己在做什么，可以忽略此警告...")
        print("=" * 60)
        print()

if __name__ == '__main__':
    check_readme_recommendation()
    from cli.main import main
    main()
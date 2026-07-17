#!/usr/bin/env python3
"""
项目初始化脚本
创建翻译项目的目录结构和配置文件
"""

import os
import sys
import shutil
from pathlib import Path
from datetime import datetime

# 模板目录路径：按本发布包所在位置自动定位
PACKAGE_DIR = Path(__file__).resolve().parents[1]
TEMPLATE_DIR = PACKAGE_DIR / "assets" / "project_template"


def create_project(project_path: str, project_name: str, source_lang: str, target_lang: str):
    """创建翻译项目目录结构"""
    
    project_dir = Path(project_path)
    
    # 创建目录结构
    directories = [
        "config",
        "source",
        "output", 
        "logs",
        "final"
    ]
    
    for d in directories:
        (project_dir / d).mkdir(parents=True, exist_ok=True)
    
    # 复制配置文件模板
    config_files = [
        "terms.yaml",
        "term_notes.yaml", 
        "summary.yaml",
        "check_config.yaml",
        "check_log.yaml"
    ]
    
    for f in config_files:
        src = TEMPLATE_DIR / f
        if f == "check_log.yaml":
            dst = project_dir / "logs" / f
        else:
            dst = project_dir / "config" / f
        
        if src.exists():
            shutil.copy(src, dst)
        else:
            # 如果模板不存在，创建空文件
            dst.touch()
    
    # 创建进度文件
    progress_content = f"""# 进度追踪
项目名: {project_name}
源语言: {source_lang}
目标语言: {target_lang}
总章数: 0
翻译模式: 单章模式
工作模式: 询问模式
当前状态: 初始化
创建时间: "{datetime.now().strftime('%Y-%m-%d %H:%M')}"

章节列表: []

断点信息:
  最后完成章节: 0
  下一章节: 1
  暂停原因: null
"""
    
    with open(project_dir / "config" / "progress.yaml", "w", encoding="utf-8") as f:
        f.write(progress_content)
    
    print(f"✓ 项目已创建: {project_dir}")
    print(f"  - config/    配置文件目录")
    print(f"  - source/    请将切分好的章节文件放入此目录")
    print(f"  - output/    翻译输出目录")
    print(f"  - logs/      自检日志目录")
    print(f"  - final/     最终合并文件目录")
    print()
    print("下一步: 将章节文件放入 source/ 目录，然后扫描初始化章节列表")


def scan_chapters(project_path: str):
    """扫描source目录，初始化章节列表"""
    
    project_dir = Path(project_path)
    source_dir = project_dir / "source"
    progress_file = project_dir / "config" / "progress.yaml"
    
    if not source_dir.exists():
        print(f"✗ source目录不存在: {source_dir}")
        return
    
    # 扫描章节文件（支持 txt/md/markdown）
    chapter_files = sorted(
        list(source_dir.glob("*.txt")) +
        list(source_dir.glob("*.md")) +
        list(source_dir.glob("*.markdown"))
    )

    if not chapter_files:
        print(f"✗ source目录中没有章节文件（txt/md/markdown）")
        return
    
    print(f"✓ 发现 {len(chapter_files)} 个章节文件:")
    for f in chapter_files:
        print(f"  - {f.name}")
    
    # 更新进度文件
    # 这里简化处理，实际使用时应该用yaml库
    print()
    print(f"请手动更新 {progress_file} 中的章节列表")
    print("或在翻译开始时由AI自动初始化")


def main():
    if len(sys.argv) < 2:
        print("用法:")
        print("  初始化项目: python init_project.py create <项目路径> <项目名> <源语言> <目标语言>")
        print("  扫描章节:   python init_project.py scan <项目路径>")
        print()
        print("示例:")
        print("  python init_project.py create ./my_translation 我的翻译项目 日语 中文")
        print("  python init_project.py scan ./my_translation")
        return
    
    command = sys.argv[1]
    
    if command == "create":
        if len(sys.argv) < 6:
            print("✗ 参数不足，需要: <项目路径> <项目名> <源语言> <目标语言>")
            return
        create_project(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5])
    
    elif command == "scan":
        if len(sys.argv) < 3:
            print("✗ 参数不足，需要: <项目路径>")
            return
        scan_chapters(sys.argv[2])
    
    else:
        print(f"✗ 未知命令: {command}")


if __name__ == "__main__":
    main()

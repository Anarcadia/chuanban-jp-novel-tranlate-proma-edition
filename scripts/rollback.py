#!/usr/bin/env python3
"""
回退功能脚本
将翻译进度回退到指定章节，重置后续章节状态
支持 .md 和 .txt 两种格式
"""

import os
import sys
import re
from pathlib import Path
from datetime import datetime


def natural_sort_key(s):
    """自然排序键"""
    return [int(text) if text.isdigit() else text.lower()
            for text in re.split(r'(\d+)', str(s))]


def extract_chapter_num(filename: str) -> int:
    """从文件名提取章节编号"""
    match = re.search(r'(\d+)', filename)
    if match:
        return int(match.group(1))
    return 0


def rollback(project_path: str, target_chapter: int, confirm: bool = False):
    """
    回退到指定章节
    
    Args:
        project_path: 项目目录路径
        target_chapter: 目标章节（该章及之后的章节都会被重置）
        confirm: 是否已确认执行
    """
    
    project_dir = Path(project_path)
    output_dir = project_dir / "output"
    progress_file = project_dir / "config" / "progress.yaml"
    
    if not output_dir.exists():
        print(f"✗ output目录不存在: {output_dir}")
        return
    
    # 获取所有已翻译的章节文件（支持 .md 和 .txt）
    translated_files_md = list(output_dir.glob("*_translated.md"))
    translated_files_txt = list(output_dir.glob("*_translated.txt"))
    translated_files = sorted(translated_files_md + translated_files_txt, key=natural_sort_key)
    
    # 找出需要删除的文件
    files_to_delete = []
    for f in translated_files:
        chapter_num = extract_chapter_num(f.name)
        if chapter_num >= target_chapter:
            files_to_delete.append(f)
    
    if not files_to_delete:
        print(f"没有找到第{target_chapter}章及之后的译文文件")
        return
    
    print(f"回退到第{target_chapter}章")
    print(f"以下 {len(files_to_delete)} 个文件将被删除:")
    print("-" * 50)
    for f in files_to_delete:
        print(f"  {f.name}")
    print("-" * 50)
    
    if not confirm:
        print()
        print("⚠️  警告: 此操作不可撤销！")
        print("如确认执行，请添加 --confirm 参数")
        print()
        print(f"  python rollback.py {project_path} {target_chapter} --confirm")
        return
    
    # 执行删除
    deleted_count = 0
    for f in files_to_delete:
        try:
            f.unlink()
            deleted_count += 1
            print(f"  ✓ 已删除: {f.name}")
        except Exception as e:
            print(f"  ✗ 删除失败: {f.name} - {e}")
    
    print("-" * 50)
    print(f"已删除 {deleted_count} 个文件")
    
    # 更新进度文件
    if progress_file.exists():
        print(f"\n请手动更新进度文件: {progress_file}")
        print("  - 将断点信息.最后完成章节 设为 " + str(target_chapter - 1))
        print("  - 将断点信息.下一章节 设为 " + str(target_chapter))
        print("  - 将第" + str(target_chapter) + "章及之后的章节状态改为 '未译'")
    
    # 记录回退操作到日志
    log_file = project_dir / "logs" / "check_log.yaml"
    if log_file.exists():
        log_entry = f"""
- 操作: 回退
  时间: "{datetime.now().strftime('%Y-%m-%d %H:%M')}"
  目标章节: {target_chapter}
  删除文件数: {deleted_count}
  删除文件列表:
"""
        for f in files_to_delete:
            log_entry += f"    - {f.name}\n"
        
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(log_entry)
        
        print(f"\n回退操作已记录到: {log_file}")
    
    print("\n✓ 回退完成")


def main():
    if len(sys.argv) < 3:
        print("用法:")
        print("  python rollback.py <项目路径> <目标章节> [--confirm]")
        print()
        print("说明:")
        print("  将翻译进度回退到指定章节")
        print("  目标章节及其后的所有译文文件将被删除")
        print("  必须添加 --confirm 参数才会实际执行")
        print()
        print("示例:")
        print("  python rollback.py ./my_translation 5           # 预览")
        print("  python rollback.py ./my_translation 5 --confirm # 执行")
        print()
        print("⚠️  警告: 此操作不可撤销，请谨慎使用！")
        return
    
    project_path = sys.argv[1]
    target_chapter = int(sys.argv[2])
    confirm = "--confirm" in sys.argv
    
    rollback(project_path, target_chapter, confirm)


if __name__ == "__main__":
    main()

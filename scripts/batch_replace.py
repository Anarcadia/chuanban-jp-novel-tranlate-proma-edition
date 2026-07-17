#!/usr/bin/env python3
"""
术语批量替换脚本
在所有已翻译章节中替换指定术语
支持 .md 和 .txt 两种格式
"""

import os
import sys
import re
from pathlib import Path
from datetime import datetime


def batch_replace(project_path: str, old_term: str, new_term: str, 
                  update_terms_file: bool = True, dry_run: bool = False):
    """
    在所有已翻译章节中批量替换术语
    
    Args:
        project_path: 项目目录路径
        old_term: 要替换的旧术语
        new_term: 替换后的新术语
        update_terms_file: 是否同时更新术语表
        dry_run: 试运行，只显示会修改的内容，不实际修改
    """
    
    project_dir = Path(project_path)
    output_dir = project_dir / "output"
    terms_file = project_dir / "config" / "terms.yaml"
    notes_file = project_dir / "config" / "term_notes.yaml"
    
    if not output_dir.exists():
        print(f"✗ output目录不存在: {output_dir}")
        return
    
    # 获取所有已翻译的章节文件（支持 .md 和 .txt）
    translated_files_md = list(output_dir.glob("*_translated.md"))
    translated_files_txt = list(output_dir.glob("*_translated.txt"))
    translated_files = sorted(translated_files_md + translated_files_txt)
    
    if not translated_files:
        print("✗ 没有找到已翻译的章节文件")
        return
    
    print(f"{'[试运行] ' if dry_run else ''}批量替换: '{old_term}' → '{new_term}'")
    print(f"将处理 {len(translated_files)} 个文件")
    print("-" * 50)
    
    total_replacements = 0
    modified_files = []
    
    for file_path in translated_files:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        # 统计替换次数
        count = content.count(old_term)
        
        if count > 0:
            total_replacements += count
            modified_files.append((file_path.name, count))
            
            if not dry_run:
                # 执行替换
                new_content = content.replace(old_term, new_term)
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(new_content)
            
            print(f"  {file_path.name}: {count} 处")
    
    print("-" * 50)
    print(f"共 {len(modified_files)} 个文件，{total_replacements} 处替换")
    
    if dry_run:
        print("\n[试运行模式，未实际修改文件]")
        print("确认无误后，移除 --dry-run 参数执行实际替换")
        return
    
    # 更新术语表
    if update_terms_file and terms_file.exists():
        print(f"\n更新术语表: {terms_file}")
        with open(terms_file, "r", encoding="utf-8") as f:
            terms_content = f.read()
        
        # 简单替换术语表中的译文字段
        # 实际使用时应该用yaml库精确修改
        if f"译文: {old_term}" in terms_content:
            terms_content = terms_content.replace(f"译文: {old_term}", f"译文: {new_term}")
            with open(terms_file, "w", encoding="utf-8") as f:
                f.write(terms_content)
            print(f"  ✓ 术语表已更新")
    
    # 记录到术语笔记
    if notes_file.exists():
        note_entry = f"""
- 条目: 批量替换_{old_term}
  决策: "{old_term}" → "{new_term}"
  理由: 用户要求批量替换
  来源: 用户指定
  章节: 批量
  执行时间: "{datetime.now().strftime('%Y-%m-%d %H:%M')}"
  影响文件数: {len(modified_files)}
  替换总数: {total_replacements}
"""
        with open(notes_file, "a", encoding="utf-8") as f:
            f.write(note_entry)
        print(f"  ✓ 术语笔记已记录")
    
    print("\n✓ 批量替换完成")


def main():
    if len(sys.argv) < 4:
        print("用法:")
        print("  python batch_replace.py <项目路径> <旧术语> <新术语> [选项]")
        print()
        print("选项:")
        print("  --dry-run       试运行，只显示会修改的内容")
        print("  --no-update     不更新术语表")
        print()
        print("示例:")
        print("  python batch_replace.py ./my_translation 张三 張三")
        print("  python batch_replace.py ./my_translation 张三 張三 --dry-run")
        return
    
    project_path = sys.argv[1]
    old_term = sys.argv[2]
    new_term = sys.argv[3]
    
    dry_run = "--dry-run" in sys.argv
    update_terms = "--no-update" not in sys.argv
    
    batch_replace(project_path, old_term, new_term, update_terms, dry_run)


if __name__ == "__main__":
    main()

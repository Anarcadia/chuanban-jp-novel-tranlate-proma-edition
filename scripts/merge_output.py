#!/usr/bin/env python3
"""
章节整合脚本
将所有已翻译章节合并为单一md文件
支持分段章节的智能合并（处理重叠部分）
支持 .md 和 .txt 两种格式输入，统一输出 .md
"""

import os
import sys
import re
import yaml
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from collections import defaultdict


def natural_sort_key(s):
    """自然排序键，处理数字排序"""
    return [int(text) if text.isdigit() else text.lower()
            for text in re.split(r'(\d+)', str(s))]


def load_segment_map(project_path: Path) -> Optional[Dict]:
    """加载分段映射配置"""
    segment_map_file = project_path / "config" / "segment_map.yaml"
    if segment_map_file.exists():
        with open(segment_map_file, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    return None


def parse_segment_filename(filename: str) -> Tuple[str, Optional[str]]:
    """
    解析文件名，提取章节ID和分段标识

    例如:
    - "001_第一章_xxx_translated.md" -> ("001", None)
    - "027_a_translated.md" -> ("027", "a")
    - "027_b_translated.md" -> ("027", "b")
    - "001_第一章_xxx_translated.txt" -> ("001", None)  # 兼容旧格式
    """
    # 兼容 .md 和 .txt 两种格式
    stem = filename.replace("_translated.md", "").replace("_translated.txt", "").replace("_translated", "")

    # 检查是否为分段文件（格式：数字_字母）
    match = re.match(r'^(\d+)_([a-z])$', stem)
    if match:
        return match.group(1), match.group(2)

    # 普通章节文件，提取章节号
    match = re.match(r'^(\d+)', stem)
    if match:
        return match.group(1), None

    return stem, None


def merge_segment_contents(segment_files: List[Path], segment_info: Dict,
                           overlap_lines: int = 3) -> str:
    """
    合并分段章节的内容，处理重叠部分

    Args:
        segment_files: 分段文件列表（已排序）
        segment_info: 分段映射信息
        overlap_lines: 重叠行数

    Returns:
        合并后的内容
    """
    if len(segment_files) == 1:
        with open(segment_files[0], 'r', encoding='utf-8') as f:
            return f.read().strip()

    merged_parts = []

    for i, file_path in enumerate(segment_files):
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read().strip()

        lines = content.split('\n')

        if i == 0:
            # 第一段：保留全部
            merged_parts.append(content)
        else:
            # 后续分段：跳过重叠部分
            # 重叠处理：去掉开头几行（与前一段末尾重复）
            if len(lines) > overlap_lines:
                # 跳过重叠行
                trimmed_lines = lines[overlap_lines:]
                merged_parts.append('\n'.join(trimmed_lines))
            else:
                # 内容太短，保留全部
                merged_parts.append(content)

    return '\n'.join(merged_parts)


def group_files_by_chapter(translated_files: List[Path]) -> Dict[str, List[Path]]:
    """
    将文件按章节分组

    Returns:
        章节ID -> 文件列表 的映射
    """
    groups = defaultdict(list)

    for file_path in translated_files:
        chapter_id, segment_id = parse_segment_filename(file_path.name)
        groups[chapter_id].append((segment_id or "", file_path))

    # 对每个章节内的文件按分段ID排序
    result = {}
    for chapter_id, files in groups.items():
        sorted_files = [f for _, f in sorted(files, key=lambda x: x[0])]
        result[chapter_id] = sorted_files

    return result


def get_chapter_display_name(chapter_id: str, source_dir: Path) -> str:
    """
    获取章节的显示名称
    尝试从 source 目录找到对应的源文件名
    """
    # 查找匹配的源文件
    for ext in ['md', 'txt']:
        pattern = f"{chapter_id}_*.{ext}"
        matches = list(source_dir.glob(pattern))
        if matches:
            # 返回文件名（去除扩展名）
            return matches[0].stem

    return f"第{chapter_id}章"


def merge_chapters(project_path: str, output_filename: str = None,
                   add_chapter_markers: bool = True, separator: str = "\n\n"):
    """
    合并所有已翻译章节为单一文件

    Args:
        project_path: 项目目录路径
        output_filename: 输出文件名，默认为 full_translation.txt
        add_chapter_markers: 是否添加章节分隔标记
        separator: 章节之间的分隔符
    """

    project_dir = Path(project_path)
    output_dir = project_dir / "output"
    source_dir = project_dir / "source"
    final_dir = project_dir / "final"

    if not output_dir.exists():
        print(f"✗ output目录不存在: {output_dir}")
        return

    # 加载分段映射
    segment_map = load_segment_map(project_dir)
    has_segments = segment_map and segment_map.get("summary", {}).get("chapters_need_segmentation", 0) > 0

    if has_segments:
        print("📊 检测到分段映射，将进行智能合并")
        overlap_lines = segment_map.get("config", {}).get("overlap_lines", 3)
    else:
        overlap_lines = 0

    # 获取所有已翻译的章节文件（优先 .md，兼容 .txt）
    translated_files_md = list(output_dir.glob("*_translated.md"))
    translated_files_txt = list(output_dir.glob("*_translated.txt"))
    translated_files = sorted(translated_files_md + translated_files_txt, key=natural_sort_key)

    if not translated_files:
        print("✗ 没有找到已翻译的章节文件")
        return

    print(f"找到 {len(translated_files)} 个翻译文件")

    # 按章节分组
    chapter_groups = group_files_by_chapter(translated_files)
    sorted_chapters = sorted(chapter_groups.keys(), key=natural_sort_key)

    print(f"共 {len(sorted_chapters)} 个章节")

    # 确保final目录存在
    final_dir.mkdir(parents=True, exist_ok=True)

    # 确定输出文件名（统一使用 .md 格式）
    if output_filename is None:
        output_filename = "full_translation.md"

    output_path = final_dir / output_filename

    # 合并内容
    merged_content = []
    segment_merge_count = 0

    for chapter_id in sorted_chapters:
        files = chapter_groups[chapter_id]

        # 获取章节显示名称
        chapter_name = get_chapter_display_name(chapter_id, source_dir)

        if len(files) > 1:
            # 多个分段文件，需要合并
            print(f"  合并分段: {chapter_name} ({len(files)} 段)")
            content = merge_segment_contents(files, segment_map, overlap_lines)
            segment_merge_count += 1
        else:
            # 单个文件，直接读取
            print(f"  处理: {chapter_name}")
            with open(files[0], "r", encoding="utf-8") as f:
                content = f.read().strip()

        if add_chapter_markers:
            marker = f"{'=' * 20} {chapter_name} {'=' * 20}"
            merged_content.append(marker)

        merged_content.append(content)

    # 写入合并文件
    final_content = separator.join(merged_content)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(final_content)

    # 统计信息
    total_chars = len(final_content)
    total_lines = final_content.count('\n') + 1

    print("-" * 50)
    print(f"✓ 合并完成: {output_path}")
    print(f"  总字符数: {total_chars:,}")
    print(f"  总行数: {total_lines:,}")
    print(f"  章节数: {len(sorted_chapters)}")
    if segment_merge_count > 0:
        print(f"  分段合并: {segment_merge_count} 个章节")


def main():
    if len(sys.argv) < 2:
        print("用法:")
        print("  python merge_output.py <项目路径> [输出文件名] [选项]")
        print()
        print("选项:")
        print("  --no-markers    不添加章节分隔标记")
        print()
        print("说明:")
        print("  自动检测 config/segment_map.yaml，对分段章节进行智能合并")
        print("  支持 .md 和 .txt 两种格式输入，统一输出 .md")
        print("  分段文件命名格式：027_a_translated.md, 027_b_translated.md")
        print()
        print("示例:")
        print("  python merge_output.py ./my_translation")
        print("  python merge_output.py ./my_translation my_novel.txt")
        print("  python merge_output.py ./my_translation output.txt --no-markers")
        return

    project_path = sys.argv[1]

    output_filename = None
    for arg in sys.argv[2:]:
        if not arg.startswith("--"):
            output_filename = arg
            break

    add_markers = "--no-markers" not in sys.argv

    merge_chapters(project_path, output_filename, add_markers)


if __name__ == "__main__":
    main()

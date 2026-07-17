#!/usr/bin/env python3
"""
翻译单元分段分析器
针对章节长度显著超出目标 token 数的情况，进行智能分段处理。

使用场景：
- 章节平均 token 数超过目标的 1.5 倍以上
- 单章 token 数为目标的数倍甚至十倍

分段策略：
1. 优先在场景边界切分（空行、分隔符、时间/地点跳跃）
2. 其次在段落边界切分
3. 确保每段有上下文重叠，便于翻译衔接
"""

import os
import sys
import re
import json
import yaml
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, asdict
from datetime import datetime


@dataclass
class Segment:
    """翻译分段"""
    id: str                    # 分段ID，如 "001_a", "001_b"
    start_line: int            # 起始行号（0-indexed）
    end_line: int              # 结束行号（不含）
    char_count: int            # 字符数
    token_estimate: int        # 预估 token 数
    break_type: str            # 切分类型: scene/paragraph/force


@dataclass
class ChapterAnalysis:
    """章节分析结果"""
    filename: str
    total_chars: int
    total_tokens: int
    needs_segmentation: bool   # 是否需要分段
    segments: List[Segment]    # 分段列表（若需要）


class SegmentAnalyzer:
    """分段分析器"""

    # 场景切换标识符
    SCENE_BREAK_PATTERNS = [
        r'^[\s]*[＊\*]{3,}[\s]*$',           # *** 或 ＊＊＊
        r'^[\s]*[—\-－]{3,}[\s]*$',          # --- 或 ———
        r'^[\s]*[#＃]{1,3}\s',               # 章节内小标题
        r'^[\s]*◇[\s]*$',                    # ◇ 分隔符
        r'^[\s]*◆[\s]*$',                    # ◆ 分隔符
        r'^[\s]*[○●◎]{1,3}[\s]*$',          # 圆形符号分隔
        r'^[\s]*[☆★]{1,3}[\s]*$',           # 星形符号分隔
        r'^\s*$',                             # 空行（连续多个）
    ]

    def __init__(self,
                 target_tokens: int = 3500,
                 max_tokens: int = 4500,
                 min_tokens: int = 1500,
                 overlap_lines: int = 3,
                 trigger_ratio: float = 1.5):
        """
        初始化分段分析器

        Args:
            target_tokens: 目标 token 数
            max_tokens: 单段最大 token 数（硬上限）
            min_tokens: 单段最小 token 数（避免过碎）
            overlap_lines: 分段重叠行数（用于上下文衔接）
            trigger_ratio: 触发分段的阈值比例（章节token/目标token）
        """
        self.target_tokens = target_tokens
        self.max_tokens = max_tokens
        self.min_tokens = min_tokens
        self.overlap_lines = overlap_lines
        self.trigger_ratio = trigger_ratio

        # 编译正则
        self.scene_patterns = [re.compile(p) for p in self.SCENE_BREAK_PATTERNS]

    def estimate_tokens(self, text: str) -> int:
        """
        估算文本的 token 数
        中文: 约 1 token / 1.5 字符
        日文: 约 1 token / 1.2 字符（含假名）
        英文: 约 1 token / 4 字符
        混合文本取中间值
        """
        if not text:
            return 0

        # 统计不同字符类型
        cjk_chars = len(re.findall(r'[\u4e00-\u9fff]', text))  # 中文
        jp_chars = len(re.findall(r'[\u3040-\u309f\u30a0-\u30ff]', text))  # 日文假名
        ascii_chars = len(re.findall(r'[a-zA-Z0-9]', text))  # ASCII
        other_chars = len(text) - cjk_chars - jp_chars - ascii_chars

        # 按类型估算
        tokens = (
            cjk_chars / 1.5 +      # 中文
            jp_chars / 1.2 +       # 日文
            ascii_chars / 4 +      # 英文
            other_chars / 2        # 其他（符号、空格等）
        )

        return int(tokens)

    def find_scene_breaks(self, lines: List[str]) -> List[int]:
        """
        找出场景切换点的行号
        返回可作为分段点的行号列表
        """
        breaks = []
        consecutive_empty = 0

        for i, line in enumerate(lines):
            # 检查空行（连续2个以上空行视为场景切换）
            if not line.strip():
                consecutive_empty += 1
                if consecutive_empty >= 2:
                    breaks.append(i)
            else:
                consecutive_empty = 0
                # 检查其他场景切换标识
                for pattern in self.scene_patterns[:-1]:  # 排除空行模式
                    if pattern.match(line):
                        breaks.append(i)
                        break

        return sorted(set(breaks))

    def find_paragraph_breaks(self, lines: List[str]) -> List[int]:
        """
        找出段落边界（空行位置）
        """
        breaks = []
        for i, line in enumerate(lines):
            if not line.strip():
                breaks.append(i)
        return breaks

    def segment_chapter(self, lines: List[str], chapter_id: str) -> List[Segment]:
        """
        对单个章节进行分段

        Args:
            lines: 章节内容（按行）
            chapter_id: 章节标识（如 "001"）

        Returns:
            分段列表
        """
        total_chars = sum(len(line) for line in lines)
        total_tokens = self.estimate_tokens('\n'.join(lines))

        # 如果不需要分段，返回单个完整段
        if total_tokens <= self.max_tokens:
            return [Segment(
                id=f"{chapter_id}",
                start_line=0,
                end_line=len(lines),
                char_count=total_chars,
                token_estimate=total_tokens,
                break_type="none"
            )]

        segments = []

        # 获取所有可能的切分点
        scene_breaks = set(self.find_scene_breaks(lines))
        para_breaks = set(self.find_paragraph_breaks(lines))

        current_start = 0
        segment_index = 0

        while current_start < len(lines):
            # 计算从 current_start 开始的累计 token
            accumulated_tokens = 0
            best_break = None
            best_break_type = None

            for i in range(current_start, len(lines)):
                line_tokens = self.estimate_tokens(lines[i])
                accumulated_tokens += line_tokens

                # 达到目标范围，开始寻找切分点
                if accumulated_tokens >= self.target_tokens:
                    # 优先找场景切换点
                    for j in range(i, min(i + 20, len(lines))):  # 向后看20行
                        if j in scene_breaks:
                            best_break = j + 1
                            best_break_type = "scene"
                            break

                    # 其次找段落边界
                    if not best_break:
                        for j in range(i, min(i + 10, len(lines))):
                            if j in para_breaks:
                                best_break = j + 1
                                best_break_type = "paragraph"
                                break

                    # 强制切分（如果超过硬上限还没找到合适点）
                    if not best_break and accumulated_tokens >= self.max_tokens:
                        # 回退找最近的段落边界
                        for j in range(i, current_start, -1):
                            if j in para_breaks:
                                best_break = j + 1
                                best_break_type = "paragraph"
                                break
                        if not best_break:
                            best_break = i + 1
                            best_break_type = "force"

                    if best_break:
                        break

            # 处理最后一段
            if not best_break:
                best_break = len(lines)
                best_break_type = "end"

            # 创建分段
            segment_lines = lines[current_start:best_break]
            segment_chars = sum(len(line) for line in segment_lines)
            segment_tokens = self.estimate_tokens('\n'.join(segment_lines))

            # 检查是否过小，如果是最后一段且过小，合并到前一段
            if segment_tokens < self.min_tokens and segments and best_break == len(lines):
                # 合并到前一段
                prev_segment = segments[-1]
                merged_lines = lines[prev_segment.start_line:best_break]
                segments[-1] = Segment(
                    id=prev_segment.id,
                    start_line=prev_segment.start_line,
                    end_line=best_break,
                    char_count=sum(len(line) for line in merged_lines),
                    token_estimate=self.estimate_tokens('\n'.join(merged_lines)),
                    break_type=prev_segment.break_type
                )
            else:
                segment_label = chr(ord('a') + segment_index)
                segments.append(Segment(
                    id=f"{chapter_id}_{segment_label}",
                    start_line=current_start,
                    end_line=best_break,
                    char_count=segment_chars,
                    token_estimate=segment_tokens,
                    break_type=best_break_type
                ))
                segment_index += 1

            # 设置下一段起点（考虑重叠）
            overlap_start = max(0, best_break - self.overlap_lines)
            next_start = best_break if best_break >= len(lines) else overlap_start
            current_start = best_break if next_start <= current_start else next_start

            # 防止无限循环
            if current_start >= len(lines):
                break

        return segments

    def analyze_project(self, project_path: str) -> Dict:
        """
        分析整个翻译项目的章节

        Args:
            project_path: 项目路径

        Returns:
            分析结果字典
        """
        project_dir = Path(project_path)
        source_dir = project_dir / "source"

        if not source_dir.exists():
            raise FileNotFoundError(f"源文件目录不存在: {source_dir}")

        # 扫描章节文件
        chapter_files = sorted(
            list(source_dir.glob("*.txt")) +
            list(source_dir.glob("*.md"))
        )

        if not chapter_files:
            raise FileNotFoundError(f"未找到章节文件: {source_dir}")

        results = {
            "analysis_time": datetime.now().isoformat(),
            "config": {
                "target_tokens": self.target_tokens,
                "max_tokens": self.max_tokens,
                "min_tokens": self.min_tokens,
                "overlap_lines": self.overlap_lines,
                "trigger_ratio": self.trigger_ratio,
            },
            "summary": {
                "total_chapters": len(chapter_files),
                "chapters_need_segmentation": 0,
                "total_segments": 0,
                "avg_chapter_tokens": 0,
            },
            "chapters": {}
        }

        total_tokens = 0

        for chapter_file in chapter_files:
            # 读取文件
            try:
                with open(chapter_file, 'r', encoding='utf-8') as f:
                    content = f.read()
            except UnicodeDecodeError:
                with open(chapter_file, 'r', encoding='gbk', errors='ignore') as f:
                    content = f.read()

            lines = content.split('\n')
            chapter_tokens = self.estimate_tokens(content)
            total_tokens += chapter_tokens

            # 提取章节ID
            chapter_id = chapter_file.stem.split('_')[0]  # 如 "001"

            # 判断是否需要分段
            needs_segmentation = chapter_tokens > (self.target_tokens * self.trigger_ratio)

            if needs_segmentation:
                segments = self.segment_chapter(lines, chapter_id)
                results["summary"]["chapters_need_segmentation"] += 1
                results["summary"]["total_segments"] += len(segments)
            else:
                segments = [Segment(
                    id=chapter_id,
                    start_line=0,
                    end_line=len(lines),
                    char_count=len(content),
                    token_estimate=chapter_tokens,
                    break_type="none"
                )]

            results["chapters"][chapter_file.name] = {
                "total_chars": len(content),
                "total_tokens": chapter_tokens,
                "needs_segmentation": needs_segmentation,
                "segment_count": len(segments),
                "segments": [asdict(s) for s in segments]
            }

        results["summary"]["avg_chapter_tokens"] = int(total_tokens / len(chapter_files))

        return results

    def save_segment_map(self, project_path: str, results: Dict):
        """保存分段映射到项目配置目录"""
        project_dir = Path(project_path)
        config_dir = project_dir / "config"
        config_dir.mkdir(parents=True, exist_ok=True)

        output_file = config_dir / "segment_map.yaml"

        with open(output_file, 'w', encoding='utf-8') as f:
            yaml.dump(results, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

        return output_file


def print_analysis_report(results: Dict):
    """打印分析报告"""
    print("\n" + "=" * 60)
    print("📊 翻译单元分段分析报告")
    print("=" * 60)

    summary = results["summary"]
    config = results["config"]

    print(f"目标 Token 数: {config['target_tokens']}")
    print(f"触发阈值: {config['trigger_ratio']}x (>{int(config['target_tokens'] * config['trigger_ratio'])} tokens)")
    print("-" * 60)
    print(f"总章节数: {summary['total_chapters']}")
    print(f"平均章节 Token: {summary['avg_chapter_tokens']}")
    print(f"需要分段的章节: {summary['chapters_need_segmentation']}")
    print(f"总分段数: {summary['total_segments']}")

    # 列出需要分段的章节
    if summary['chapters_need_segmentation'] > 0:
        print("-" * 60)
        print("需要分段的章节:")
        for filename, info in results["chapters"].items():
            if info["needs_segmentation"]:
                print(f"  • {filename}")
                print(f"    原始: {info['total_tokens']} tokens → 分为 {info['segment_count']} 段")
                for seg in info["segments"]:
                    print(f"      [{seg['id']}] {seg['token_estimate']} tokens ({seg['break_type']})")

    print("=" * 60)


def main():
    """命令行入口"""
    import argparse

    parser = argparse.ArgumentParser(description='翻译单元分段分析器')
    parser.add_argument('project_path', help='翻译项目路径')
    parser.add_argument('--target', type=int, default=3500, help='目标 token 数 (默认: 3500)')
    parser.add_argument('--max', type=int, default=4500, help='最大 token 数 (默认: 4500)')
    parser.add_argument('--min', type=int, default=1500, help='最小 token 数 (默认: 1500)')
    parser.add_argument('--ratio', type=float, default=1.5, help='触发分段的阈值比例 (默认: 1.5)')
    parser.add_argument('--overlap', type=int, default=3, help='分段重叠行数 (默认: 3)')
    parser.add_argument('--json', action='store_true', help='输出 JSON 格式')
    parser.add_argument('--save', action='store_true', help='保存分段映射到项目')

    args = parser.parse_args()

    try:
        analyzer = SegmentAnalyzer(
            target_tokens=args.target,
            max_tokens=args.max,
            min_tokens=args.min,
            overlap_lines=args.overlap,
            trigger_ratio=args.ratio
        )

        results = analyzer.analyze_project(args.project_path)

        if args.json:
            print(json.dumps(results, ensure_ascii=False, indent=2))
        else:
            print_analysis_report(results)

        if args.save:
            output_file = analyzer.save_segment_map(args.project_path, results)
            print(f"\n✓ 分段映射已保存: {output_file}")

        return 0

    except Exception as e:
        print(f"✗ 错误: {e}")
        return 1


if __name__ == "__main__":
    exit(main())

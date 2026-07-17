#!/usr/bin/env python3
"""
准备翻译源文件：自动识别 md/txt/epub，抽取章节，按长度实际拆分，
写入项目 source/，并同步更新 progress.yaml。
"""

import argparse
import html
import posixpath
import re
import sys
import zipfile
from dataclasses import dataclass
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import List
from urllib.parse import unquote
from xml.etree import ElementTree as ET

try:
    import yaml
except ImportError:
    print("需要安装 PyYAML: pip install pyyaml")
    sys.exit(1)

from segment_analyzer import SegmentAnalyzer


CHAPTER_PATTERNS = [
    r"^#{1,3}\s+.+",
    r"^第[0-9０-９]+[章話话].*",
    r"^第[一二三四五六七八九十百千万〇零]+[章話话].*",
    r"^(序章|終章|终章|幕間|幕间|閑話|闲话|プロローグ|エピローグ).*",
    r"^Chapter\s+\d+.*",
]


@dataclass
class Chapter:
    title: str
    content: str
    source_name: str = ""


class HtmlTextExtractor(HTMLParser):
    block_tags = {
        "p", "div", "br", "section", "article", "li",
        "h1", "h2", "h3", "h4", "h5", "h6",
    }

    def __init__(self):
        super().__init__()
        self.parts = []
        self.skip_depth = 0

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in {"script", "style"}:
            self.skip_depth += 1
            return
        if self.skip_depth:
            return
        if tag in self.block_tags:
            self.parts.append("\n")
        if tag == "img":
            attrs_dict = dict(attrs)
            alt = attrs_dict.get("alt") or attrs_dict.get("title") or ""
            if alt:
                self.parts.append(f"\n[image: {alt}]\n")

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in {"script", "style"} and self.skip_depth:
            self.skip_depth -= 1
            return
        if self.skip_depth:
            return
        if tag in self.block_tags:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.skip_depth:
            self.parts.append(data)

    def get_text(self) -> str:
        text = html.unescape("".join(self.parts))
        lines = [line.strip() for line in text.splitlines()]
        text = "\n".join(line for line in lines if line)
        return re.sub(r"\n{3,}", "\n\n", text).strip()


def read_text_file(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="gbk", errors="ignore")


def clean_title(line: str, fallback: str) -> str:
    title = re.sub(r"^#{1,6}\s*", "", line).strip()
    title = re.sub(r"\s+", " ", title)
    return title or fallback


def safe_filename(text: str, limit: int = 60) -> str:
    text = clean_title(text, "chapter")
    text = re.sub(r'[\\/:*?"<>|]', "_", text)
    text = re.sub(r"\s+", "_", text)
    text = text.strip("._ ")
    return (text or "chapter")[:limit]


def is_chapter_heading(line: str) -> bool:
    stripped = line.strip()
    return any(re.match(pattern, stripped, re.IGNORECASE) for pattern in CHAPTER_PATTERNS)


def split_text_chapters(content: str, fallback_title: str) -> List[Chapter]:
    lines = content.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    chapters = []
    current_title = None
    current_lines = []

    for line in lines:
        if is_chapter_heading(line):
            if current_lines:
                title = current_title or fallback_title
                chapters.append(Chapter(title=title, content="\n".join(current_lines).strip()))
            current_title = clean_title(line, fallback_title)
            current_lines = [line]
        else:
            current_lines.append(line)

    if current_lines:
        title = current_title or fallback_title
        chapters.append(Chapter(title=title, content="\n".join(current_lines).strip()))

    return [chapter for chapter in chapters if chapter.content.strip()]


def extract_epub_text(html_content: str) -> str:
    parser = HtmlTextExtractor()
    parser.feed(html_content)
    return parser.get_text()


def decode_zip_text(data: bytes) -> str:
    for encoding in ("utf-8", "utf-16", "shift_jis", "gbk"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="ignore")


def get_epub_spine_files(epub_path: Path) -> List[str]:
    with zipfile.ZipFile(epub_path) as zf:
        container = ET.fromstring(zf.read("META-INF/container.xml"))
        rootfile = container.find(".//{*}rootfile")
        if rootfile is None:
            raise ValueError("EPUB 缺少 rootfile")

        opf_path = rootfile.attrib["full-path"]
        opf_dir = posixpath.dirname(opf_path)
        opf = ET.fromstring(zf.read(opf_path))

        manifest = {}
        for item in opf.findall(".//{*}manifest/{*}item"):
            href = item.attrib.get("href")
            item_id = item.attrib.get("id")
            media_type = item.attrib.get("media-type", "")
            if href and item_id:
                manifest[item_id] = (href, media_type)

        files = []
        for itemref in opf.findall(".//{*}spine/{*}itemref"):
            idref = itemref.attrib.get("idref")
            if idref not in manifest:
                continue
            href, media_type = manifest[idref]
            full_path = posixpath.normpath(posixpath.join(opf_dir, unquote(href)))
            if "html" in media_type or full_path.lower().endswith((".xhtml", ".html", ".htm")):
                files.append(full_path)

        if files:
            return files

        return sorted(
            name for name in zf.namelist()
            if name.lower().endswith((".xhtml", ".html", ".htm"))
        )


def extract_epub_chapters(path: Path) -> List[Chapter]:
    files = get_epub_spine_files(path)
    chapters = []

    with zipfile.ZipFile(path) as zf:
        for file_name in files:
            text = extract_epub_text(decode_zip_text(zf.read(file_name)))
            if len(text) < 5:
                continue
            subchapters = split_text_chapters(text, Path(file_name).stem)
            if len(subchapters) > 1:
                for chapter in subchapters:
                    chapter.source_name = file_name
                chapters.extend(subchapters)
            else:
                title = clean_title(text.splitlines()[0], Path(file_name).stem)
                chapters.append(Chapter(title=title, content=text, source_name=file_name))

    return chapters


def load_chapters(input_path: Path) -> List[Chapter]:
    suffix = input_path.suffix.lower()
    if suffix in {".md", ".markdown", ".txt"}:
        return split_text_chapters(read_text_file(input_path), input_path.stem)
    if suffix == ".epub":
        return extract_epub_chapters(input_path)
    raise ValueError("仅支持 .md / .markdown / .txt / .epub")


def split_long_lines(lines: List[str], max_chars: int = 1800) -> List[str]:
    result = []
    sentence_pattern = re.compile(r".+?[。！？!?」』）)]|.+$")

    for line in lines:
        if len(line) <= max_chars:
            result.append(line)
            continue

        parts = sentence_pattern.findall(line)
        if not parts:
            parts = [line[i:i + max_chars] for i in range(0, len(line), max_chars)]

        current = ""
        for part in parts:
            if len(current) + len(part) > max_chars and current:
                result.append(current)
                current = part
            else:
                current += part
        if current:
            result.append(current)

    return result


def write_source_files(project_path: Path, chapters: List[Chapter], analyzer: SegmentAnalyzer, overwrite: bool):
    source_dir = project_path / "source"
    source_dir.mkdir(parents=True, exist_ok=True)

    existing = list(source_dir.glob("*.md")) + list(source_dir.glob("*.txt"))
    if existing and not overwrite:
        raise FileExistsError("source/ 已存在章节文件；如需覆盖，请加 --overwrite")
    if overwrite:
        for file_path in existing:
            file_path.unlink()

    source_files = []
    segment_map = {
        "prepared_at": datetime.now().isoformat(timespec="seconds"),
        "config": {
            "target_tokens": analyzer.target_tokens,
            "max_tokens": analyzer.max_tokens,
            "min_tokens": analyzer.min_tokens,
            "overlap_lines": analyzer.overlap_lines,
            "trigger_ratio": analyzer.trigger_ratio,
        },
        "summary": {
            "original_chapters": len(chapters),
            "source_units": 0,
            "chapters_split": 0,
            "chapters_need_segmentation": 0,
            "total_segments": 0,
            "avg_chapter_tokens": 0,
        },
        "chapters": {},
    }

    total_tokens = 0

    for chapter_index, chapter in enumerate(chapters, 1):
        chapter_id = f"{chapter_index:03d}"
        title = safe_filename(chapter.title)
        lines = split_long_lines(chapter.content.splitlines())
        token_count = analyzer.estimate_tokens("\n".join(lines))
        total_tokens += token_count
        needs_split = token_count > analyzer.target_tokens * analyzer.trigger_ratio
        segments = analyzer.segment_chapter(lines, chapter_id) if needs_split else []

        if not needs_split:
            filename = f"{chapter_id}_{title}.md"
            (source_dir / filename).write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
            source_files.append(filename)
            segment_count = 1
        else:
            segment_count = len(segments)
            segment_map["summary"]["chapters_split"] += 1
            segment_map["summary"]["chapters_need_segmentation"] += 1
            for segment in segments:
                segment_text = "\n".join(lines[segment.start_line:segment.end_line]).strip()
                filename = f"{segment.id}_{title}.md"
                (source_dir / filename).write_text(segment_text + "\n", encoding="utf-8")
                source_files.append(filename)

        segment_map["chapters"][chapter.title] = {
            "chapter_id": chapter_id,
            "source_name": chapter.source_name,
            "total_tokens": token_count,
            "needs_split": needs_split,
            "segment_count": segment_count,
        }

    segment_map["summary"]["source_units"] = len(source_files)
    segment_map["summary"]["total_segments"] = len(source_files)
    segment_map["summary"]["avg_chapter_tokens"] = int(total_tokens / len(chapters)) if chapters else 0
    return source_files, segment_map


def update_progress(project_path: Path, source_files: List[str]):
    progress_file = project_path / "config" / "progress.yaml"
    if progress_file.exists():
        with open(progress_file, "r", encoding="utf-8") as f:
            progress = yaml.safe_load(f) or {}
    else:
        progress = {}

    progress["总章数"] = len(source_files)
    progress["当前状态"] = "待翻译"
    progress["章节列表"] = [
        {
            "章节": index,
            "源文件": filename,
            "译文件": f"{Path(filename).stem}_translated.md",
            "状态": "未译",
            "翻译时间": None,
            "自检时间": None,
        }
        for index, filename in enumerate(source_files, 1)
    ]
    progress["断点信息"] = {
        "最后完成章节": 0,
        "下一章节": 1,
        "暂停原因": None,
    }

    progress_file.parent.mkdir(parents=True, exist_ok=True)
    with open(progress_file, "w", encoding="utf-8") as f:
        yaml.dump(progress, f, allow_unicode=True, sort_keys=False)


def save_segment_map(project_path: Path, segment_map: dict):
    config_dir = project_path / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    with open(config_dir / "segment_map.yaml", "w", encoding="utf-8") as f:
        yaml.dump(segment_map, f, allow_unicode=True, sort_keys=False)


def main():
    parser = argparse.ArgumentParser(description="准备小说翻译源文件")
    parser.add_argument("project_path", help="翻译项目路径")
    parser.add_argument("input_file", help="原始小说文件：md/txt/epub")
    parser.add_argument("--target", type=int, default=3500, help="目标 token 数")
    parser.add_argument("--max", type=int, default=4500, help="单段最大 token 数")
    parser.add_argument("--min", type=int, default=1500, help="单段最小 token 数")
    parser.add_argument("--ratio", type=float, default=1.5, help="触发拆分比例")
    parser.add_argument("--overlap", type=int, default=3, help="分段重叠行数")
    parser.add_argument("--overwrite", action="store_true", help="覆盖已有 source/ 章节文件")
    args = parser.parse_args()

    project_path = Path(args.project_path)
    input_path = Path(args.input_file)

    if not input_path.exists():
        print(f"✗ 输入文件不存在: {input_path}")
        return 1

    analyzer = SegmentAnalyzer(
        target_tokens=args.target,
        max_tokens=args.max,
        min_tokens=args.min,
        overlap_lines=args.overlap,
        trigger_ratio=args.ratio,
    )

    try:
        chapters = load_chapters(input_path)
        if not chapters:
            raise ValueError("未能抽取到有效章节")

        source_files, segment_map = write_source_files(project_path, chapters, analyzer, args.overwrite)
        segment_map["input_file"] = str(input_path)
        segment_map["input_format"] = input_path.suffix.lower().lstrip(".")
        update_progress(project_path, source_files)
        save_segment_map(project_path, segment_map)

        print("✓ 源文件准备完成")
        print(f"  输入格式: {segment_map['input_format']}")
        print(f"  原始章节: {segment_map['summary']['original_chapters']}")
        print(f"  翻译单元: {segment_map['summary']['source_units']}")
        print(f"  被拆章节: {segment_map['summary']['chapters_split']}")
        print(f"  输出目录: {project_path / 'source'}")
        print(f"  进度文件: {project_path / 'config' / 'progress.yaml'}")
        return 0
    except Exception as e:
        print(f"✗ 准备失败: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
将 TXT/Markdown 小说转换为 ePub，插入封面图片
用法: python create_epub.py <txt_file> [options]

检查项：
- 必需：TXT/Markdown 文件
- 可选：本地图片目录、Pixiv 封面
"""

import argparse
import re
import shutil
import zipfile
from pathlib import Path


def check_prerequisites(txt_path: Path, images_dir: Path = None):
    """检查必需文件"""
    
    # 检查小说文件
    if not txt_path.exists():
        raise FileNotFoundError(
            f"❌ 小说文件不存在: {txt_path}\n"
            "请提供已整理好的 TXT 或 Markdown 文件。"
        )
    
    # 检查文件类型
    valid_extensions = {'.txt', '.md', '.markdown'}
    if txt_path.suffix.lower() not in valid_extensions:
        raise ValueError(
            f"❌ 不支持的文件格式: {txt_path.suffix}\n"
            f"请提供以下格式之一: {', '.join(valid_extensions)}"
        )
    
    # 检查内容
    with open(txt_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    if len(content) < 100:
        raise ValueError("❌ 文件内容太短，可能不是有效的小说文件")
    
    # 检查图片标记
    image_markers = ['[uploadedimage:', '![', '<img']
    has_markers = any(marker in content for marker in image_markers)
    
    print("=" * 60)
    print("文件检查")
    print("=" * 60)
    print(f"✅ 小说文件: {txt_path}")
    print(f"   大小: {txt_path.stat().st_size / 1024:.1f} KB")
    print(f"   章节数: {content.count(chr(10) + '第') + content.count('第1章')}")
    
    if has_markers:
        print(f"✅ 检测到图片插入标记")
    else:
        print(f"⚠️ 未检测到图片插入标记，将只在章节开头插入封面")
    
    # 检查图片目录
    if images_dir and images_dir.exists():
        image_files = list(images_dir.glob('*.jpg')) + list(images_dir.glob('*.png'))
        print(f"✅ 图片目录: {images_dir} ({len(image_files)} 张图片)")
    elif images_dir:
        print(f"⚠️ 图片目录不存在: {images_dir}")
        print(f"   将只使用 TXT 中的文字内容")
    
    print("=" * 60)
    
    return content


def parse_chapters(content: str):
    """解析章节"""
    # 支持多种章节格式
    patterns = [
        r'^(第[0-9]+章)\s*$',           # 第X章
        r'^(第[一二三四五六七八九十]+章)\s*$',  # 中文数字
        r'^Chapter\s+\d+\s*$',          # Chapter X
    ]
    
    lines = content.split('\n')
    chapters = []
    current_chapter = None
    current_content = []
    
    for line in lines:
        is_chapter = False
        for pattern in patterns:
            if re.match(pattern, line.strip()):
                is_chapter = True
                break
        
        if is_chapter:
            if current_chapter and current_content:
                chapter_text = '\n'.join(current_content).strip()
                if chapter_text:
                    chapters.append({
                        'title': current_chapter,
                        'content': chapter_text
                    })
            current_chapter = line.strip()
            current_content = []
        else:
            current_content.append(line)
    
    if current_chapter and current_content:
        chapter_text = '\n'.join(current_content).strip()
        if chapter_text:
            chapters.append({
                'title': current_chapter,
                'content': chapter_text
            })
    
    return chapters


def process_content(content: str, image_map: dict) -> str:
    """处理内容，插入图片"""
    if not content or not content.strip():
        return '<p></p>'
    
    # 替换 [uploadedimage:数字] 格式
    pattern = r'\[uploadedimage:(\d+)\]'
    
    def replace_image(match):
        image_id = match.group(1)
        if image_id in image_map:
            ext = image_map[image_id]['ext']
            return f'{{IMG:{image_id}:{ext}}}'
        return ''
    
    processed = re.sub(pattern, replace_image, content)
    
    # HTML 转义
    processed = processed.replace('&', '&amp;')
    processed = processed.replace('<', '&lt;')
    processed = processed.replace('>', '&gt;')
    
    # 恢复图片占位符为 HTML
    def restore_image(match):
        image_id = match.group(1)
        ext = match.group(2)
        return f'<div class="illustration"><img src="images/{image_id}{ext}" alt="插图{image_id}" /></div>'
    
    processed = re.sub(r'\{IMG:(\d+):([^}]+)\}', restore_image, processed)
    
    # 处理 Markdown 图片 ![alt](path)
    md_pattern = r'!\[([^\]]*)\]\(([^)]+)\)'
    processed = re.sub(md_pattern, r'<div class="illustration"><img src="\2" alt="\1" /></div>', processed)
    
    # 处理段落
    paragraphs = processed.split('\n\n')
    html_paragraphs = []
    
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        if para.startswith('<div') and para.endswith('</div>'):
            html_paragraphs.append(para)
        else:
            para = para.replace('\n', '<br/>')
            html_paragraphs.append(f'<p>{para}</p>')
    
    return '\n'.join(html_paragraphs) if html_paragraphs else '<p></p>'


def find_chapter_cover(chapter_num: int, images_dir: Path) -> str:
    """查找章节封面"""
    if not images_dir or not images_dir.exists():
        return None
    
    # 尝试多种命名格式
    possible_names = [
        f'chapter_{chapter_num:03d}.jpg',
        f'chapter_{chapter_num}.jpg',
        f'cover_{chapter_num:03d}.jpg',
        f'{chapter_num:03d}.jpg',
    ]
    
    for name in possible_names:
        cover_path = images_dir / name
        if cover_path.exists():
            return name
    
    return None


def create_epub(txt_path: str, images_dir: str, output_path: str):
    """创建 ePub"""
    txt_path = Path(txt_path)
    images_dir = Path(images_dir) if images_dir else None
    output_path = Path(output_path)
    
    # 检查必需文件
    content = check_prerequisites(txt_path, images_dir)
    
    # 解析章节
    chapters = parse_chapters(content)
    print(f"\n📚 解析到 {len(chapters)} 个章节")
    
    if len(chapters) == 0:
        raise ValueError("❌ 未解析到任何章节，请检查文件格式")
    
    # 收集本地图片
    image_map = {}
    if images_dir and images_dir.exists():
        for img in images_dir.glob('*'):
            if img.suffix.lower() in {'.jpg', '.jpeg', '.png'}:
                image_id = img.stem
                image_map[image_id] = {'path': img, 'ext': img.suffix}
    
    # 创建 ePub
    print(f"\n📦 创建 ePub...")
    
    with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        # mimetype (无压缩)
        zf.writestr('mimetype', 'application/epub+zip', 
                    compress_type=zipfile.ZIP_STORED)
        
        # META-INF/container.xml
        container_xml = '''<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
    <rootfiles>
        <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
    </rootfiles>
</container>'''
        zf.writestr('META-INF/container.xml', container_xml)
        
        # CSS
        css = '''@charset "UTF-8";
body { font-family: "Noto Serif CJK SC", serif; line-height: 1.8; padding: 20px; margin: 0; }
h1 { text-align: center; font-size: 1.5em; margin-bottom: 30px; font-weight: bold; }
p { text-indent: 2em; margin: 0.5em 0; }
.illustration { text-align: center; margin: 20px 0; page-break-inside: avoid; }
.illustration img { max-width: 100%; height: auto; }
.chapter-cover { text-align: center; margin: 20px 0; page-break-inside: avoid; }
.chapter-cover img { max-width: 100%; height: auto; max-height: 80vh; }
'''
        zf.writestr('OEBPS/style.css', css)
        
        # 复制图片
        if images_dir and images_dir.exists():
            for img in images_dir.glob('*'):
                if img.suffix.lower() in {'.jpg', '.jpeg', '.png'}:
                    zf.write(img, f'OEBPS/images/{img.name}')
        
        # 生成章节文件
        manifest_items = []
        spine_items = []
        toc_items = []
        
        for i, chapter in enumerate(chapters):
            chapter_num = i + 1
            filename = f'chapter_{chapter_num:03d}.xhtml'
            
            # 检查是否有章节封面
            cover_html = ''
            if images_dir:
                cover_name = find_chapter_cover(chapter_num, images_dir)
                if cover_name:
                    cover_html = f'<div class="chapter-cover"><img src="images/{cover_name}" alt="章节封面"/></div>\n'
            
            chapter_html = f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
    <meta charset="UTF-8"/>
    <title>{chapter['title']}</title>
    <link rel="stylesheet" type="text/css" href="style.css"/>
</head>
<body>
    <h1>{chapter['title']}</h1>
    {cover_html}{process_content(chapter['content'], image_map)}
</body>
</html>'''
            
            zf.writestr(f'OEBPS/{filename}', chapter_html)
            
            manifest_items.append(f'    <item id="chapter_{chapter_num:03d}" href="{filename}" media-type="application/xhtml+xml"/>')
            spine_items.append(f'    <itemref idref="chapter_{chapter_num:03d}"/>')
            toc_items.append(f'            <li><a href="{filename}">{chapter["title"]}</a></li>')
        
        # content.opf
        manifest_str = '\n'.join(manifest_items)
        spine_str = '\n'.join(spine_items)
        
        content_opf = f'''<?xml version="1.0" encoding="UTF-8"?>
<package version="3.0" xmlns="http://www.idpf.org/2007/opf">
    <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
        <dc:identifier>{txt_path.stem[:20]}</dc:identifier>
        <dc:title>{txt_path.stem}</dc:title>
        <dc:language>zh-CN</dc:language>
    </metadata>
    <manifest>
    <item id="toc" href="toc.xhtml" media-type="application/xhtml+xml" properties="nav"/>
    <item id="style" href="style.css" media-type="text/css"/>
{manifest_str}
    </manifest>
    <spine toc="toc">
{spine_str}
    </spine>
</package>'''
        zf.writestr('OEBPS/content.opf', content_opf)
        
        # toc.xhtml
        toc_html = f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">
<head>
    <meta charset="UTF-8"/>
    <title>目录</title>
    <link rel="stylesheet" type="text/css" href="style.css"/>
</head>
<body>
    <h1>目录</h1>
    <nav epub:type="toc">
        <ol>
{chr(10).join(toc_items)}
        </ol>
    </nav>
</body>
</html>'''
        zf.writestr('OEBPS/toc.xhtml', toc_html)
    
    size_mb = output_path.stat().st_size / (1024 * 1024)
    print(f"✅ ePub 创建完成: {output_path}")
    print(f"   文件大小: {size_mb:.2f} MB")
    print(f"\n⚠️ 建议下一步：运行 fix_epub.py 进行质量检查")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='TXT/Markdown 转 ePub')
    parser.add_argument('txt_file', help='TXT/Markdown 文件路径（必需）')
    parser.add_argument('--images', '-i', default='images', help='图片目录（可选）')
    parser.add_argument('--output', '-o', default='output.epub', help='输出文件')
    
    args = parser.parse_args()
    
    try:
        create_epub(args.txt_file, args.images, args.output)
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        sys.exit(1)

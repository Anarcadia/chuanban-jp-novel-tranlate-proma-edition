#!/usr/bin/env python3
"""
修复 ePub 常见问题
用法: python fix_epub.py <input.epub> [output.epub]
"""

import argparse
import re
import shutil
import tempfile
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


def fix_xml_namespaces(content: str) -> str:
    """修复 XML 命名空间"""
    # 添加 epub 命名空间（如果使用了 epub:type）
    if 'epub:type' in content and 'xmlns:epub' not in content:
        content = content.replace(
            '<html xmlns="http://www.w3.org/1999/xhtml">',
            '<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">'
        )
    return content


def escape_special_chars(content: str) -> str:
    """转义特殊字符"""
    # 转义 & 字符（保留已转义的）
    content = re.sub(
        r'&(?!(amp|lt|gt|quot|apos|#[0-9]+|#x[0-9a-fA-F]+);)',
        '&amp;',
        content
    )
    return content


def fix_epub(input_path: str, output_path: str = None):
    """修复 ePub 文件"""
    input_path = Path(input_path)
    if not output_path:
        output_path = input_path.with_stem(input_path.stem + '_fixed')
    else:
        output_path = Path(output_path)
    
    with tempfile.TemporaryDirectory(prefix='epub_fix_') as temp_dir:
        extract_dir = Path(temp_dir)

        # 解压
        print(f"解压 {input_path}...")
        with zipfile.ZipFile(input_path, 'r') as zf:
            zf.extractall(extract_dir)

        # 修复所有 XHTML 文件
        xhtml_files = list((extract_dir / 'OEBPS').glob('*.xhtml'))
        fixed_files = []

        for xhtml_file in xhtml_files:
            with open(xhtml_file, 'r', encoding='utf-8') as f:
                content = f.read()

            original = content
            content = fix_xml_namespaces(content)
            content = escape_special_chars(content)

            if content != original:
                with open(xhtml_file, 'w', encoding='utf-8') as f:
                    f.write(content)
                fixed_files.append(xhtml_file.name)

        if fixed_files:
            print(f"修复了 {len(fixed_files)} 个文件:")
            for f in fixed_files:
                print(f"  - {f}")
        else:
            print("未发现需要修复的问题")

        # 重新打包
        print(f"\n重新打包到 {output_path}...")
        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            mimetype_path = extract_dir / 'mimetype'
            zf.write(mimetype_path, 'mimetype', compress_type=zipfile.ZIP_STORED)

            for file_path in extract_dir.rglob('*'):
                if not file_path.is_file() or file_path.name == 'mimetype':
                    continue
                arcname = str(file_path.relative_to(extract_dir))
                zf.write(file_path, arcname)
    
    # 验证
    print("\n验证修复结果...")
    with zipfile.ZipFile(output_path, 'r') as zf:
        xhtml_files = [f for f in zf.namelist() if f.endswith('.xhtml')]
        all_ok = True
        
        for file in xhtml_files:
            try:
                content = zf.read(file)
                ET.fromstring(content)
            except Exception as e:
                print(f"❌ {file}: {e}")
                all_ok = False
        
        if all_ok:
            print(f"✅ 所有 {len(xhtml_files)} 个 XHTML 文件格式正确")
    
    size_mb = output_path.stat().st_size / (1024 * 1024)
    print(f"\n📦 输出文件: {output_path}")
    print(f"📊 文件大小: {size_mb:.2f} MB")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='修复 ePub 常见问题')
    parser.add_argument('input', help='输入 ePub 文件')
    parser.add_argument('output', nargs='?', help='输出文件（可选）')
    
    args = parser.parse_args()
    fix_epub(args.input, args.output)

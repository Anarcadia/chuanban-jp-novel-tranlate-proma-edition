#!/usr/bin/env python3
"""
下载封面图片
用法: python download_covers.py <covers_json_file>

⚠️ 反爬措施：
- 单张图片下载间隔: 2-5 秒
- 下载后停顿: 1-2 秒
- 错误重试: 递增延迟（5秒×次数）
- 每小时上限: 120张
"""

import json
import os
import random
import sys
import time
from pathlib import Path

import requests


# 反爬配置
CONFIG = {
    'download_delay': (2.0, 5.0),    # 下载间隔：2-5 秒
    'after_download': (1.0, 2.0),    # 下载后停顿：1-2 秒
    'retry_base': 5,                  # 重试基础延迟：5 秒
    'max_retries': 3,                 # 最大重试次数
    'hourly_limit': 120,              # 每小时上限
}

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
    'Referer': 'https://www.pixiv.net/',
    'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
}

# 全局计数器
download_count = 0
start_time = time.time()


def check_rate_limit():
    """检查下载速率限制"""
    global download_count, start_time
    
    elapsed = time.time() - start_time
    if elapsed < 3600 and download_count >= CONFIG['hourly_limit']:
        wait_time = 3600 - elapsed
        print(f"\n⚠️ 达到每小时下载上限 ({CONFIG['hourly_limit']}张)")
        print(f"   请等待 {wait_time/60:.1f} 分钟后再继续...")
        return False
    
    if elapsed >= 3600:
        # 重置计数器
        download_count = 0
        start_time = time.time()
    
    return True


def download_image(url: str, filepath: Path, attempt: int = 0) -> bool:
    """
    下载单张图片（带反爬措施）
    
    Args:
        url: 图片 URL
        filepath: 保存路径
        attempt: 当前重试次数
    """
    global download_count
    
    # 检查速率限制
    if not check_rate_limit():
        return False
    
    # 下载前随机延迟
    delay = random.uniform(*CONFIG['download_delay'])
    time.sleep(delay)
    
    try:
        response = requests.get(url, headers=HEADERS, timeout=30)
        response.raise_for_status()
        
        with open(filepath, 'wb') as f:
            f.write(response.content)
        
        download_count += 1
        file_size = filepath.stat().st_size / 1024
        
        # 下载后停顿
        time.sleep(random.uniform(*CONFIG['after_download']))
        
        print(f"  ✅ {filepath.name} ({file_size:.1f} KB) [延迟: {delay:.1f}s]")
        return True
        
    except Exception as e:
        if attempt < CONFIG['max_retries']:
            retry_delay = CONFIG['retry_base'] * (attempt + 1)
            print(f"  ⚠️ {filepath.name} 失败: {e}")
            print(f"     等待 {retry_delay} 秒后重试...")
            time.sleep(retry_delay)
            return download_image(url, filepath, attempt + 1)
        else:
            print(f"  ❌ {filepath.name}: {e} (已重试{CONFIG['max_retries']}次)")
            return False


def main():
    if len(sys.argv) < 2:
        print("用法: python download_covers.py <covers_json_file>")
        print("\n⚠️ 反爬措施：")
        print(f"   - 下载间隔: {CONFIG['download_delay'][0]}-{CONFIG['download_delay'][1]} 秒")
        print(f"   - 每小时上限: {CONFIG['hourly_limit']} 张")
        sys.exit(1)
    
    json_file = sys.argv[1]
    
    if not os.path.exists(json_file):
        print(f"❌ 文件不存在: {json_file}")
        sys.exit(1)
    
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # 创建输出目录
    output_dir = Path('images')
    output_dir.mkdir(exist_ok=True)
    
    # 下载总封面
    if data.get('series_cover'):
        print("\n📚 下载总封面...")
        series_path = output_dir / 'series_cover.jpg'
        download_image(data['series_cover'], series_path)
    
    # 下载章节封面
    chapter_covers = data.get('chapter_covers', [])
    
    print(f"\n📖 下载章节封面 ({len(chapter_covers)} 个)...")
    print(f"   预计用时: {len(chapter_covers) * 3.5 / 60:.1f} - {len(chapter_covers) * 7 / 60:.1f} 分钟")
    print("   请勿关闭程序，正在慢速下载...")
    print()
    
    success_count = 0
    failed_items = []
    
    for i, item in enumerate(chapter_covers, 1):
        chapter_num = item['chapter']
        url = item['thumbUrl']
        
        filename = f"chapter_{chapter_num:03d}.jpg"
        filepath = output_dir / filename
        
        # 显示进度
        progress = f"[{i}/{len(chapter_covers)}]"
        print(f"{progress}", end=" ")
        
        if download_image(url, filepath):
            success_count += 1
        else:
            failed_items.append((chapter_num, url))
        
        # 显示统计
        if i % 10 == 0:
            elapsed = (time.time() - start_time) / 60
            print(f"\n   [统计] 已下载: {i}/{len(chapter_covers)}, "
                  f"成功: {success_count}, 用时: {elapsed:.1f}分钟")
    
    # 总结
    print("\n" + "=" * 60)
    print("下载完成")
    print("=" * 60)
    print(f"成功: {success_count}/{len(chapter_covers)}")
    
    if failed_items:
        print(f"失败: {len(failed_items)} 个")
        # 保存失败列表供后续重试
        failed_file = output_dir / 'failed_downloads.json'
        with open(failed_file, 'w') as f:
            json.dump(failed_items, f)
        print(f"失败列表保存到: {failed_file}")
    
    print(f"保存位置: {output_dir.absolute()}")
    print(f"总用时: {(time.time() - start_time) / 60:.1f} 分钟")


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""
从 Pixiv 小说系列页面提取封面信息
用法: python extract_covers.py <series_id>

⚠️ 反爬措施：
- 页面翻页间隔 >= 5 秒
- 滚动后等待 0.5-1.5 秒
- 随机停留 2-4 秒模拟阅读
"""

import asyncio
import json
import random
import sys
from pathlib import Path

from playwright.async_api import async_playwright


# 反爬延迟设置（秒）
DELAYS = {
    'page_turn': (5, 10),      # 翻页间隔：5-10 秒
    'scroll': (0.5, 1.5),      # 滚动后等待：0.5-1.5 秒
    'reading': (2, 4),         # 页面停留：2-4 秒
    'click': (2, 4),           # 点击后等待：2-4 秒
}


async def human_like_delay(delay_type: str):
    """模拟人类行为延迟"""
    min_delay, max_delay = DELAYS[delay_type]
    await asyncio.sleep(random.uniform(min_delay, max_delay))


async def human_like_scroll(page):
    """模拟人类缓慢滚动"""
    for _ in range(random.randint(2, 4)):
        await page.evaluate(f'window.scrollBy(0, {random.randint(200, 400)})')
        await human_like_delay('scroll')
    
    # 偶尔暂停阅读
    if random.random() > 0.6:
        await human_like_delay('reading')


async def extract_covers(series_id: str):
    """提取封面信息（带反爬措施）"""
    url = f"https://www.pixiv.net/novel/series/{series_id}"
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            viewport={'width': 1280, 'height': 800}
        )
        page = await context.new_page()
        
        print(f"访问: {url}")
        await page.goto(url)
        
        # 等待页面加载
        await human_like_delay('reading')
        
        # 等待用户登录（如果需要）
        print("\n⚠️ 如果页面显示登录框，请手动完成登录")
        print("登录完成后，按回车继续...")
        input()
        
        # 模拟阅读行为
        await human_like_scroll(page)
        
        # 获取总封面
        print("\n提取总封面...")
        await human_like_delay('reading')
        
        series_cover = await page.evaluate('''() => {
            const img = document.querySelector('figure img[src*="novel-cover-master"]');
            return img ? img.src : null;
        }''')
        
        # 获取章节封面
        chapter_covers = []
        page_num = 1
        max_pages = 10  # 安全限制
        
        while page_num <= max_pages:
            print(f"正在获取第 {page_num} 页...")
            
            # 模拟阅读当前页
            await human_like_scroll(page)
            await human_like_delay('reading')
            
            covers = await page.evaluate('''() => {
                const results = [];
                document.querySelectorAll('img').forEach(img => {
                    const src = img.src;
                    const alt = img.alt || '';
                    if (src && src.includes('novel-cover-master') && alt.includes('#')) {
                        const match = alt.match(/#(\\d+)/);
                        if (match) {
                            results.push({
                                chapter: parseInt(match[1]),
                                title: alt,
                                thumbUrl: src
                            });
                        }
                    }
                });
                return results;
            }''')
            
            chapter_covers.extend(covers)
            print(f"  本页提取到 {len(covers)} 个封面")
            
            # 检查是否有下一页
            next_btn = await page.query_selector('a[href*="?p="]:has-text("下一页")')
            if not next_btn:
                print("  已到达最后一页")
                break
            
            # 翻页前等待（严格反爬）
            print(f"  等待 {DELAYS['page_turn'][0]}-{DELAYS['page_turn'][1]} 秒后翻页...")
            await human_like_delay('page_turn')
            
            await next_btn.click()
            await page.wait_for_load_state('networkidle')
            page_num += 1
        
        await browser.close()
        
        # 去重并排序
        seen = set()
        unique_covers = []
        for cover in chapter_covers:
            if cover['chapter'] not in seen:
                seen.add(cover['chapter'])
                unique_covers.append(cover)
        
        unique_covers.sort(key=lambda x: x['chapter'])
        
        # 输出结果
        result = {
            'series_id': series_id,
            'series_cover': series_cover,
            'chapter_covers': unique_covers,
            'total_chapters': len(unique_covers),
            'extraction_date': str(Path().stat().st_mtime)
        }
        
        output_file = f'covers_{series_id}.json'
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        
        print(f"\n✅ 提取完成")
        print(f"   总封面: {'✓' if series_cover else '✗'}")
        print(f"   章节封面: {len(unique_covers)} 个")
        print(f"   保存到: {output_file}")
        
        return result


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("用法: python extract_covers.py <series_id>")
        print("示例: python extract_covers.py 14819239")
        print("\n⚠️ 注意：本脚本包含反爬措施，运行速度较慢，请勿急躁")
        sys.exit(1)
    
    series_id = sys.argv[1]
    
    print("=" * 60)
    print("Pixiv 封面提取工具")
    print("=" * 60)
    print("\n⚠️ 反爬措施已启用：")
    print(f"   - 翻页间隔: {DELAYS['page_turn'][0]}-{DELAYS['page_turn'][1]} 秒")
    print(f"   - 页面停留: {DELAYS['reading'][0]}-{DELAYS['reading'][1]} 秒")
    print(f"   - 滚动延迟: {DELAYS['scroll'][0]}-{DELAYS['scroll'][1]} 秒")
    print("\n请耐心等待，不要频繁操作浏览器...")
    print("=" * 60)
    
    asyncio.run(extract_covers(series_id))

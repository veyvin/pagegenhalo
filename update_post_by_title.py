#!/usr/bin/env python3
"""
根据文章标题更新标签和分类
"""

import os
import sys
import re
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.halo import get_halo_post, update_post_tags_and_categories, list_halo_posts
from app.services.deepseek import extract_tags_and_categories
from app.utils.logging import log_step

# 测试配置
HALO_TOKEN = os.getenv("HALO_TOKEN")

if not HALO_TOKEN:
    print("错误: 未设置 HALO_TOKEN 环境变量")
    sys.exit(1)

print("根据文章标题更新标签和分类")
print("=" * 50)

# 根据标题搜索文章
def search_post_by_title(title):
    """根据标题搜索文章，返回文章的metadata.name"""
    print(f"开始搜索文章: {title}")
    
    # 去除emoji和特殊字符，用于模糊匹配
    title_clean = re.sub(r'[\U00010000-\U0010ffff]', '', title)
    title_clean = title_clean.strip()
    
    if not title_clean:
        print("标题为空")
        return None
    
    # 搜索所有文章
    page = 0
    size = 50
    found_posts = []
    
    while True:
        posts, error = list_halo_posts(publish=None, page=page, size=size)
        if error or not posts:
            break
        
        for item in posts:
            post_obj = item.get("post") or {}
            post_title = post_obj.get("spec", {}).get("title", "")
            post_name = post_obj.get("metadata", {}).get("name")
            
            if not post_name or not post_title:
                continue
            
            # 模糊匹配标题
            post_title_clean = re.sub(r'[\U00010000-\U0010ffff]', '', post_title)
            
            if title_clean in post_title_clean or post_title_clean in title_clean:
                found_posts.append({
                    "name": post_name,
                    "title": post_title
                })
        
        if len(posts) < size:
            break
        page += 1
    
    if not found_posts:
        print("未找到匹配的文章")
        return None
    
    print(f"找到 {len(found_posts)} 篇匹配的文章:")
    for i, post in enumerate(found_posts, 1):
        print(f"  {i}. {post['title']} (name: {post['name']})")
    
    # 返回第一篇匹配的文章
    return found_posts[0]['name']

# 更新文章
def update_post(post_name):
    print(f"开始更新文章: {post_name}")
    print("-" * 30)
    
    debug_steps = []
    
    # 获取文章详情
    post, error = get_halo_post(post_name)
    if error:
        print(f"获取文章详情失败: {error}")
        return False
    
    if not post:
        print("未找到该文章")
        return False
    
    # 提取文章信息
    spec = post.get("spec", {})
    title = spec.get("title", "")
    
    # 尝试获取内容，可能不存在
    content_obj = post.get("content", {})
    content = content_obj.get("raw") or content_obj.get("content") or ""
    
    print(f"文章标题: {title}")
    print(f"内容长度: {len(content)} 字符")
    
    # 提取标签和分类，即使没有内容也使用标题
    tags, categories, ext_error = extract_tags_and_categories(
        title, content or title, debug_steps=debug_steps
    )
    
    if ext_error:
        print(f"提取标签/分类失败: {ext_error}")
        return False
    
    if not tags and not categories:
        print("未提取到标签和分类")
        return False
    
    print(f"提取的标签: {tags}")
    print(f"提取的分类: {categories}")
    
    # 更新文章
    updated_post, update_error = update_post_tags_and_categories(
        post_name, tags=tags, categories=categories, debug_steps=debug_steps
    )
    
    if update_error:
        print(f"更新失败: {update_error}")
        return False
    
    print("\n更新成功!")
    return True

if __name__ == "__main__":
    # 从命令行参数获取文章标题
    if len(sys.argv) > 1:
        post_title = " ".join(sys.argv[1:])
    else:
        # 默认标题
        post_title = "从像素到比特：视频编码的进化之旅与未来之战 🎬🚀"
    
    print(f"开始测试更新特定文章...")
    print(f"文章标题: {post_title}")
    print("=" * 50)
    
    # 搜索文章
    post_name = search_post_by_title(post_title)
    if not post_name:
        print("未找到匹配的文章")
        sys.exit(1)
    
    # 更新文章
    success = update_post(post_name)
    
    print("\n" + "=" * 50)
    print(f"测试{'完成' if success else '失败'}!")

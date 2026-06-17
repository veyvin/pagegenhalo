#!/usr/bin/env python3
"""
检查所有文章的标签和分类状态
"""

import os
import sys
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.halo import list_halo_posts, get_halo_post

# 测试配置
HALO_TOKEN = os.getenv("HALO_TOKEN")

if not HALO_TOKEN:
    print("错误: 未设置 HALO_TOKEN 环境变量")
    sys.exit(1)

print("检查所有文章的标签和分类状态")
print("=" * 50)
print(f"HALO_TOKEN: {'已设置' if HALO_TOKEN else '未设置'}")
print("=" * 50)

# 统计信息
stats = {
    "total_posts": 0,
    "with_tags_and_categories": 0,
    "without_tags": 0,
    "without_categories": 0,
    "without_both": 0,
    "error_getting_detail": 0,
    "missing_name_or_title": 0
}

# 分页获取所有文章
page = 0
size = 50
all_posts = []

print("开始获取所有文章...")
print("=" * 50)

while True:
    posts, error = list_halo_posts(publish=None, page=page, size=size)
    if error:
        print(f"获取第 {page} 页文章失败: {error}")
        break
    if not posts:
        break
    
    all_posts.extend(posts)
    print(f"已获取第 {page} 页，累计 {len(all_posts)} 篇文章")
    
    if len(posts) < size:
        break
    page += 1

print("=" * 50)
print(f"总共获取到 {len(all_posts)} 篇文章")
print("=" * 50)

# 检查每篇文章的状态
print("开始检查每篇文章的标签和分类状态...")
print("=" * 50)

for idx, item in enumerate(all_posts, 1):
    if not isinstance(item, dict):
        continue
    
    # 获取文章信息
    post_obj = item.get("post") or {}
    meta = post_obj.get("metadata") or {}
    spec = post_obj.get("spec") or {}
    post_name = meta.get("name")
    title = spec.get("title", "")
    
    # 获取标签和分类（从列表 API 中）
    categories = item.get("categories") or []
    tags = item.get("tags") or []
    
    # 确保是列表类型
    if not isinstance(categories, list):
        categories = []
    if not isinstance(tags, list):
        tags = []
    
    stats["total_posts"] += 1
    
    if not post_name or not title:
        stats["missing_name_or_title"] += 1
        print(f"{idx}. 缺少名称或标题")
        continue
    
    # 获取文章详情以确认标签和分类
    post_detail, error = get_halo_post(post_name)
    if error:
        stats["error_getting_detail"] += 1
        print(f"{idx}. {title[:50]}... - 获取详情失败: {error}")
        continue
    
    if post_detail:
        # 从详情中获取标签和分类
        detail_spec = post_detail.get("spec", {})
        detail_categories = detail_spec.get("categories", [])
        detail_tags = detail_spec.get("tags", [])
        
        if not isinstance(detail_categories, list):
            detail_categories = []
        if not isinstance(detail_tags, list):
            detail_tags = []
        
        has_tags = len(detail_tags) > 0
        has_categories = len(detail_categories) > 0
        
        if has_tags and has_categories:
            stats["with_tags_and_categories"] += 1
            if idx <= 5:  # 只打印前5篇的详细信息
                print(f"{idx}. {title[:50]}... - 已有的标签和分类: {len(detail_tags)} 标签, {len(detail_categories)} 分类")
        elif not has_tags and not has_categories:
            stats["without_both"] += 1
            print(f"{idx}. {title[:50]}... - 缺少标签和分类")
        elif not has_tags:
            stats["without_tags"] += 1
            print(f"{idx}. {title[:50]}... - 缺少标签")
        elif not has_categories:
            stats["without_categories"] += 1
            print(f"{idx}. {title[:50]}... - 缺少分类")

print("=" * 50)
print("检查完成！")
print("=" * 50)
print(f"总文章数: {stats['total_posts']}")
print(f"已有标签和分类: {stats['with_tags_and_categories']}")
print(f"缺少标签: {stats['without_tags']}")
print(f"缺少分类: {stats['without_categories']}")
print(f"缺少标签和分类: {stats['without_both']}")
print(f"获取详情失败: {stats['error_getting_detail']}")
print(f"缺少名称或标题: {stats['missing_name_or_title']}")
print("=" * 50)

if stats['without_both'] > 0 or stats['without_tags'] > 0 or stats['without_categories'] > 0:
    print(f"需要更新的文章数: {stats['without_both'] + stats['without_tags'] + stats['without_categories']}")
else:
    print("所有文章都已有标签和分类，无需更新！")
print("=" * 50)

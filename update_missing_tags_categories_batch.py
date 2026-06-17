#!/usr/bin/env python3
"""
分批更新缺少标签和分类的文章（高效版本）
"""

import os
import sys
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.halo import list_halo_posts, get_halo_post, update_post_tags_and_categories
from app.services.deepseek import extract_tags_and_categories

# 测试配置
HALO_TOKEN = os.getenv("HALO_TOKEN")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")

if not HALO_TOKEN:
    print("错误: 未设置 HALO_TOKEN 环境变量")
    sys.exit(1)

if not DEEPSEEK_API_KEY:
    print("错误: 未设置 DEEPSEEK_API_KEY 环境变量")
    sys.exit(1)

print("分批更新缺少标签和分类的文章")
print("=" * 50)
print(f"HALO_TOKEN: {'已设置' if HALO_TOKEN else '未设置'}")
print(f"DEEPSEEK_API_KEY: {'已设置' if DEEPSEEK_API_KEY else '未设置'}")
print("=" * 50)
print("目标：高效处理所有缺少标签和分类的文章")
print("=" * 50)

# 统计信息
stats = {
    "total_posts": 0,
    "posts_to_update": 0,
    "updated_successfully": 0,
    "update_failed": 0,
    "error_getting_detail": 0,
    "no_content": 0
}

# 分页获取所有文章
page = 0
size = 50
all_posts = []

print("步骤 1: 获取所有文章...")
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

# 筛选出缺少标签和分类的文章
posts_to_update = []

print("步骤 2: 筛选缺少标签和分类的文章...")
print("=" * 50)
print("正在检查每篇文章的标签和分类状态...")

for idx, item in enumerate(all_posts, 1):
    if not isinstance(item, dict):
        continue
    
    # 获取文章信息
    post_obj = item.get("post") or {}
    meta = post_obj.get("metadata") or {}
    spec = post_obj.get("spec") or {}
    post_name = meta.get("name")
    title = spec.get("title", "")
    
    if not post_name or not title:
        continue
    
    # 获取文章详情以确认标签和分类
    post_detail, error = get_halo_post(post_name)
    if error:
        stats["error_getting_detail"] += 1
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
        
        if not has_tags or not has_categories:
            posts_to_update.append({
                "name": post_name,
                "title": title,
                "post_detail": post_detail
            })

print("=" * 50)
print(f"找到 {len(posts_to_update)} 篇需要更新的文章")
print("=" * 50)

# 更新每篇文章（批量处理，每批10篇）
batch_size = 10

print("步骤 3: 批量更新文章...")
print(f"批处理大小: {batch_size} 篇/批")
print("=" * 50)

for batch_start in range(0, len(posts_to_update), batch_size):
    batch_end = min(batch_start + batch_size, len(posts_to_update))
    batch_posts = posts_to_update[batch_start:batch_end]
    
    print(f"处理批次 {batch_start//batch_size + 1}/{(len(posts_to_update)+batch_size-1)//batch_size} ({batch_start+1}-{batch_end}/{len(posts_to_update)})")
    print("-" * 50)
    
    for idx, item in enumerate(batch_posts, 1):
        post_name = item["name"]
        title = item["title"]
        post_detail = item["post_detail"]
        
        print(f"  {idx}. {title[:40]}...")
        
        # 获取文章内容
        content_obj = post_detail.get("content") or {}
        content = content_obj.get("raw") or content_obj.get("content") or ""
        
        if not content:
            stats["no_content"] += 1
        
        # 提取标签和分类
        tags, categories, ext_error = extract_tags_and_categories(
            title, content or title
        )
        
        if ext_error or (not tags and not categories):
            stats["update_failed"] += 1
            print(f"    ❌ 提取失败: {ext_error or '无标签分类'}")
            continue
        
        # 更新文章
        updated_post, update_error = update_post_tags_and_categories(
            post_name, tags=tags, categories=categories
        )
        
        if update_error:
            stats["update_failed"] += 1
            print(f"    ❌ 更新失败: {update_error}")
        else:
            stats["updated_successfully"] += 1
            print(f"    ✅ 更新成功")
    
    print("-" * 50)
    print()

print("=" * 50)
print("更新完成！")
print("=" * 50)
print(f"总文章数: {len(all_posts)}")
print(f"需要更新的文章: {len(posts_to_update)}")
print(f"成功更新: {stats['updated_successfully']}")
print(f"更新失败: {stats['update_failed']}")
print(f"获取详情失败: {stats['error_getting_detail']}")
print(f"文章内容为空: {stats['no_content']}")
print("=" * 50)

if stats['updated_successfully'] > 0:
    print(f"🎉 成功更新了 {stats['updated_successfully']} 篇文章的标签和分类！")
else:
    print("⚠️  没有成功更新任何文章，请检查错误信息。")
print("=" * 50)

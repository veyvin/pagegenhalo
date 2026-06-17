#!/usr/bin/env python3
"""
查找所有文章并打印详细信息
"""

import os
import sys
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.halo import list_halo_posts

# 测试配置
HALO_TOKEN = os.getenv("HALO_TOKEN")

if not HALO_TOKEN:
    print("错误: 未设置 HALO_TOKEN 环境变量")
    sys.exit(1)

print("查找所有文章并打印详细信息")
print("=" * 50)

# 查找文章
def find_all_posts():
    print("开始查找所有文章...")
    print("-" * 30)
    
    page = 0
    size = 50
    all_posts = []
    
    while True:
        posts, error = list_halo_posts(publish=None, page=page, size=size)
        if error:
            print(f"获取文章列表失败: {error}")
            break
        
        if not posts:
            break
        
        all_posts.extend(posts)
        print(f"第 {page + 1} 页: {len(posts)} 篇文章")
        
        if len(posts) < size:
            break
        
        page += 1
    
    print(f"\n共获取 {len(all_posts)} 篇文章")
    
    # 打印包含"视频编码"的文章
    print("\n包含'视频编码'的文章:")
    print("-" * 50)
    
    found = False
    for i, item in enumerate(all_posts, 1):
        post_obj = item.get("post") or {}
        post_title = post_obj.get("spec", {}).get("title", "")
        post_name = post_obj.get("metadata", {}).get("name")
        
        if not post_name or not post_title:
            continue
        
        if "视频编码" in post_title:
            found = True
            print(f"\n{i}. 标题: {post_title}")
            print(f"   名称: {post_name}")
            print(f"   分类数量: {len(item.get('categories', []))}")
            print(f"   标签数量: {len(item.get('tags', []))}")
    
    if not found:
        print("未找到包含'视频编码'的文章")
    
    return all_posts

if __name__ == "__main__":
    find_all_posts()
    print("\n" + "=" * 50)
    print("查找完成!")

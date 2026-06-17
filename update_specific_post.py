#!/usr/bin/env python3
"""
更新特定文章的标签和分类
"""

import os
import sys
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.halo import get_halo_post, update_post_tags_and_categories
from app.services.deepseek import extract_tags_and_categories
from app.utils.logging import log_step

# 测试配置
HALO_TOKEN = os.getenv("HALO_TOKEN")

if not HALO_TOKEN:
    print("错误: 未设置 HALO_TOKEN 环境变量")
    sys.exit(1)

print("更新特定文章的标签和分类")
print("=" * 50)

# 更新特定文章
def update_specific_post(post_name):
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
    content_obj = post.get("content", {})
    content = content_obj.get("raw") or content_obj.get("content") or ""
    
    print(f"文章标题: {title}")
    print(f"内容长度: {len(content)} 字符")
    
    if not content:
        print("文章内容为空")
        return False
    
    # 提取标签和分类
    tags, categories, ext_error = extract_tags_and_categories(
        title, content, debug_steps=debug_steps
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
    print(f"\n调试步骤:")
    for step in debug_steps:
        print(f"  - {step}")
    
    return True

if __name__ == "__main__":
    # 从命令行参数获取文章name
    if len(sys.argv) > 1:
        post_name = sys.argv[1]
    else:
        # 默认更新 post-drebofvi
        post_name = "post-drebofvi"
    
    print(f"开始测试更新特定文章...")
    print(f"文章 name: {post_name}")
    print("=" * 50)
    
    # 运行更新
    update_specific_post(post_name)
    
    print("\n" + "=" * 50)
    print("测试完成!")

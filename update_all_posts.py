#!/usr/bin/env python3
"""
更新所有没有标签和分类的文章
"""

import os
import sys
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.halo import find_and_update_posts_without_tags_categories
from app.utils.logging import log_step

# 测试配置
HALO_TOKEN = os.getenv("HALO_TOKEN")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")

if not HALO_TOKEN:
    print("错误: 未设置 HALO_TOKEN 环境变量")
    sys.exit(1)

if not DEEPSEEK_API_KEY:
    print("错误: 未设置 DEEPSEEK_API_KEY 环境变量")
    sys.exit(1)

print("更新所有没有标签和分类的文章")
print("=" * 50)
print(f"HALO_TOKEN: {'已设置' if HALO_TOKEN else '未设置'}")
print(f"DEEPSEEK_API_KEY: {'已设置' if DEEPSEEK_API_KEY else '未设置'}")
print("=" * 50)

# 运行更新
print("开始搜索并更新没有标签和分类的文章...")
print("=" * 50)
print("目标：处理所有 190 篇文章")
print("=" * 50)

debug_steps = []
results, error = find_and_update_posts_without_tags_categories(
    limit=200,  # 最多处理200篇文章（超过190）
    force_update=False,  # 只更新没有标签和分类的文章
    debug_steps=debug_steps
)

print("=" * 50)
print("更新完成！")
print("=" * 50)

if error:
    print(f"错误: {error}")
else:
    if not results:
        print("没有需要更新的文章")
    else:
        success_count = sum(1 for r in results if r.get("success"))
        print(f"共处理 {len(results)} 篇文章")
        print(f"成功: {success_count} 篇")
        print(f"失败: {len(results) - success_count} 篇")
        
        # 打印失败的文章
        failed_posts = [r for r in results if not r.get("success")]
        if failed_posts:
            print("\n失败的文章:")
            for post in failed_posts:
                print(f"- {post.get('title')}: {post.get('error')}")

print("\n" + "=" * 50)
print("任务完成！")

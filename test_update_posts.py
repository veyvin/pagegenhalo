#!/usr/bin/env python3
"""
测试更新没有标签和分类的文章
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

if not HALO_TOKEN:
    print("错误: 未设置 HALO_TOKEN 环境变量")
    sys.exit(1)

print("测试更新没有标签和分类的文章")
print("=" * 50)

# 运行更新函数
def test_update_posts():
    print("开始搜索并更新没有标签和分类的文章...")
    print("-" * 30)
    
    debug_steps = []
    
    # 运行更新函数
    results, error = find_and_update_posts_without_tags_categories(
        limit=100,  # 处理最多 100 篇文章
        force_update=False,  # 只更新没有标签和分类的文章
        debug_steps=debug_steps
    )
    
    # 打印调试步骤
    print("\n调试步骤:")
    for step in debug_steps:
        print(f"  - {step}")
    
    # 打印结果
    if error:
        print(f"\n执行失败: {error}")
        return False
    
    if not results:
        print("\n没有找到需要更新的文章")
        return True
    
    print(f"\n执行完成! 共处理 {len(results)} 篇文章:")
    success_count = 0
    for i, result in enumerate(results, 1):
        status = "成功" if result.get("success") else "失败"
        if result.get("success"):
            success_count += 1
        print(f"  {i}. [{status}] {result.get('title', '未知标题')}")
        if not result.get("success"):
            print(f"     错误: {result.get('error', '未知错误')}")
        if result.get("tags") or result.get("categories"):
            tags = result.get("tags", [])
            categories = result.get("categories", [])
            if tags:
                print(f"     标签: {tags}")
            if categories:
                print(f"     分类: {categories}")
    
    print(f"\n成功更新 {success_count}/{len(results)} 篇文章")
    return True

if __name__ == "__main__":
    print("开始测试更新没有标签和分类的文章...")
    print("=" * 50)
    
    # 运行测试
    test_update_posts()
    
    print("\n" + "=" * 50)
    print("测试完成!")

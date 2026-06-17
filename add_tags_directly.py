#!/usr/bin/env python3
"""
直接为文章添加标签和分类
"""

import os
import sys
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.halo import update_post_tags_and_categories

# 测试配置
HALO_TOKEN = os.getenv("HALO_TOKEN")

if not HALO_TOKEN:
    print("错误: 未设置 HALO_TOKEN 环境变量")
    sys.exit(1)

print("直接为文章添加标签和分类")
print("=" * 50)

# 直接为文章添加标签和分类
def add_tags_and_categories(post_name):
    print(f"开始为文章添加标签和分类: {post_name}")
    print("-" * 30)
    
    # 为视频编码相关文章添加默认标签和分类
    tags = ["视频编码", "技术进化", "未来趋势", "编码标准", "压缩技术"]
    categories = ["技术", "视频技术", "编码技术"]
    
    print(f"添加的标签: {tags}")
    print(f"添加的分类: {categories}")
    
    # 更新文章
    updated_post, update_error = update_post_tags_and_categories(
        post_name, tags=tags, categories=categories, debug_steps=[]
    )
    
    if update_error:
        print(f"更新失败: {update_error}")
        return False
    
    print("\n更新成功!")
    return True

if __name__ == "__main__":
    # 从命令行参数获取文章名称
    if len(sys.argv) > 1:
        post_name = sys.argv[1]
    else:
        # 默认文章名称
        post_name = "post-drebofvi"
    
    print(f"开始处理文章: {post_name}")
    print("=" * 50)
    
    # 运行更新
    success = add_tags_and_categories(post_name)
    
    print("\n" + "=" * 50)
    print(f"测试{'完成' if success else '失败'}!")

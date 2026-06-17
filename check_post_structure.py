#!/usr/bin/env python3
"""
检查 Halo API 返回的文章结构
"""

import os
import sys
import requests
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 测试配置
HALO_TOKEN = os.getenv("HALO_TOKEN")
HALO_URL = "https://veyvin.com"

if not HALO_TOKEN:
    print("错误: 未设置 HALO_TOKEN 环境变量")
    sys.exit(1)

headers = {
    "Authorization": f"Bearer {HALO_TOKEN}",
    "Content-Type": "application/json",
}

# 要测试的文章名称
post_name = "post-drebofvi"

print("检查 Halo API 返回的文章结构")
print("=" * 50)
print(f"测试文章: {post_name}")
print("=" * 50)

# 测试端点
endpoint = f"{HALO_URL}/apis/content.halo.run/v1alpha1/posts/{post_name}"
print(f"测试端点: {endpoint}")
print("-" * 80)

try:
    response = requests.get(endpoint, headers=headers, timeout=15)
    print(f"状态码: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print("\n返回数据结构:")
        print(f"所有键: {list(data.keys())}")
        
        # 检查 spec 字段
        if "spec" in data:
            spec = data["spec"]
            print(f"\nspec 字段: {list(spec.keys())}")
            print(f"标题: {spec.get('title')}")
            print(f"slug: {spec.get('slug')}")
            print(f"publish: {spec.get('publish')}")
            print(f"categories: {spec.get('categories')}")
            print(f"tags: {spec.get('tags')}")
        
        # 检查其他可能的内容字段
        print("\n检查可能的内容字段:")
        for key in ["content", "raw", "contentRaw", "content_html"]:
            if key in data:
                print(f"找到 {key} 字段")
                content = data[key]
                if isinstance(content, dict):
                    print(f"  {key} 是字典，包含键: {list(content.keys())}")
                    for subkey in content:
                        if isinstance(content[subkey], str) and len(content[subkey]) > 100:
                            print(f"  {subkey} 是字符串，长度: {len(content[subkey])}")
                            print(f"  内容预览: {content[subkey][:100]}...")
                elif isinstance(content, str):
                    print(f"  {key} 是字符串，长度: {len(content)}")
                    print(f"  内容预览: {content[:100]}...")

except Exception as e:
    print(f"请求失败: {str(e)}")

print("\n" + "=" * 50)
print("检查完成")

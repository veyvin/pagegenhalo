#!/usr/bin/env python3
"""
测试不同的 Halo API 端点以获取文章详情
"""

import os
import sys
import requests
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

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

# 测试的 API 端点模板
test_endpoints = [
    "{}/apis/api.console.halo.run/v1alpha1/posts/{}",
    "{}/apis/content.halo.run/v1alpha1/posts/{}",
    "{}/api/v1/posts/{}",
    "{}/api/v2/posts/{}",
    "{}/api/v3/posts/{}",
    "{}/api/content/posts/{}",
    "{}/apis/uc.api.content.halo.run/v1alpha1/posts/{}",
]

# 要测试的文章名称
post_name = "post-drebofvi"

print("测试不同的 Halo API 端点")
print("=" * 50)
print(f"测试文章: {post_name}")
print("=" * 50)

for endpoint_template in test_endpoints:
    url = endpoint_template.format(HALO_URL, post_name)
    print(f"\n测试端点: {url}")
    print("-" * 80)
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        print(f"状态码: {response.status_code}")
        print(f"响应头: {dict(response.headers)}")
        
        # 打印部分响应内容
        content = response.text
        if len(content) > 500:
            content = content[:500] + "..."
        print(f"响应内容: {content}")
        
    except Exception as e:
        print(f"请求失败: {str(e)}")

print("\n" + "=" * 50)
print("测试完成")

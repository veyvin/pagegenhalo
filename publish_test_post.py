#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
发布一篇带有分类和标签的测试文章到 Halo
使用 Halo RESTful API: https://api.halo.run/#/

若遇 500 错误：请检查 PAT 权限是否包含「创建文章」，或查看 Halo 服务端日志。
运行 python publish_test_post.py --debug 可排查 Token、分类/标签及接口连通性。
运行 python publish_test_post.py --cover 会获取封面图并上传到 Halo。可选 --cover-web 使用网络搜索，或通过 COVER_IMAGE_BACKEND=ollama/sd_webui 指定本地模型。
"""

import os
import re
import sys
from datetime import datetime

import requests
from dotenv import load_dotenv

load_dotenv()

HALO_URL = os.getenv("HALO_URL", "").rstrip("/")
HALO_TOKEN = os.getenv("HALO_TOKEN")
COVER_IMAGE_BACKEND = os.getenv("COVER_IMAGE_BACKEND", "ollama")
COVER_WEB_ENGINE = os.getenv("COVER_WEB_ENGINE", "bing_cn")  # bing_cn 国内无需代理 | duckduckgo
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434").rstrip("/")
OLLAMA_IMAGE_MODEL = os.getenv("OLLAMA_IMAGE_MODEL", "x/z-image-turbo")
SD_WEBUI_URL = os.getenv("SD_WEBUI_URL", "http://localhost:7860").rstrip("/")

if not HALO_URL:
    print("错误: 未设置 HALO_URL 环境变量")
    sys.exit(1)
if not HALO_TOKEN:
    print("错误: 未设置 HALO_TOKEN 环境变量")
    sys.exit(1)

HEADERS = {
    "Authorization": f"Bearer {HALO_TOKEN}",
    "Content-Type": "application/json; charset=utf-8",
}


def generate_slug(title: str) -> str:
    """生成 slug"""
    slug = title.lower()
    slug = re.sub(r"[^a-z0-9\-_\u4e00-\u9fa5]", "-", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")[:60]
    ts = datetime.now().strftime("%Y%m%d%H%M%S")
    return f"{slug or 'post'}-{ts}"


def list_categories() -> list:
    """获取分类列表"""
    url = f"{HALO_URL}/apis/content.halo.run/v1alpha1/categories"
    r = requests.get(url, headers=HEADERS, params={"size": 100}, timeout=15)
    if r.status_code != 200:
        print(f"获取分类失败: {r.status_code} - {r.text[:200]}")
        return []
    data = r.json()
    return data.get("items") or []


def list_tags() -> list:
    """获取标签列表"""
    url = f"{HALO_URL}/apis/content.halo.run/v1alpha1/tags"
    r = requests.get(url, headers=HEADERS, params={"size": 100}, timeout=15)
    if r.status_code != 200:
        print(f"获取标签失败: {r.status_code} - {r.text[:200]}")
        return []
    data = r.json()
    return data.get("items") or []


def to_ascii_slug(s: str) -> str:
    """生成 ASCII 安全 slug，用于 metadata.name"""
    s = re.sub(r"[^a-z0-9\-_\u4e00-\u9fa5]", "-", s.lower())
    s = re.sub(r"-+", "-", s).strip("-")
    if not s or not s[0].isascii():
        s = "cat-" + (s or "default")[:50]
    return (s or "default")[:63]


def create_category(display_name: str, slug: str) -> str | None:
    """创建分类，返回 metadata.name"""
    url = f"{HALO_URL}/apis/content.halo.run/v1alpha1/categories"
    name = to_ascii_slug(slug)
    payload = {
        "apiVersion": "content.halo.run/v1alpha1",
        "kind": "Category",
        "metadata": {"name": name},
        "spec": {
            "displayName": display_name,
            "slug": slug or name,
            "description": "",
            "cover": "",
            "template": "",
            "priority": 0,
            "children": [],
        },
    }
    r = requests.post(url, headers=HEADERS, json=payload, timeout=15)
    if r.status_code not in (200, 201):
        print(f"创建分类失败: {r.status_code} - {r.text[:200]}")
        return None
    data = r.json()
    return data.get("metadata", {}).get("name")


def create_tag(display_name: str, slug: str) -> str | None:
    """创建标签，返回 metadata.name"""
    url = f"{HALO_URL}/apis/content.halo.run/v1alpha1/tags"
    name = to_ascii_slug(slug)
    payload = {
        "apiVersion": "content.halo.run/v1alpha1",
        "kind": "Tag",
        "metadata": {"name": name},
        "spec": {
            "displayName": display_name,
            "slug": slug or name,
        },
    }
    r = requests.post(url, headers=HEADERS, json=payload, timeout=15)
    if r.status_code not in (200, 201):
        print(f"创建标签失败: {r.status_code} - {r.text[:200]}")
        return None
    data = r.json()
    return data.get("metadata", {}).get("name")


def ensure_category(display_name: str) -> str | None:
    """确保分类存在，返回 metadata.name。不存在则创建。"""
    slug = re.sub(r"[^a-z0-9\-_\u4e00-\u9fa5]", "-", display_name.lower())
    slug = re.sub(r"-+", "-", slug).strip("-") or "default"
    cats = list_categories()
    for c in cats:
        s = c.get("spec", {})
        if s.get("displayName") == display_name or s.get("slug") == slug:
            return c.get("metadata", {}).get("name")
    created = create_category(display_name, slug)
    if created:
        return created
    # fallback: 使用任意已有分类
    if cats:
        return cats[0].get("metadata", {}).get("name")
    return None


def ensure_tag(display_name: str) -> str | None:
    """确保标签存在，返回 metadata.name。不存在则创建。"""
    slug = re.sub(r"[^a-z0-9\-_\u4e00-\u9fa5]", "-", display_name.lower())
    slug = re.sub(r"-+", "-", slug).strip("-") or "default"
    tags = list_tags()
    for t in tags:
        s = t.get("spec", {})
        if s.get("displayName") == display_name or s.get("slug") == slug:
            return t.get("metadata", {}).get("name")
    created = create_tag(display_name, slug)
    if created:
        return created
    if tags:
        return tags[0].get("metadata", {}).get("name")
    return None


def _build_post_spec(title: str, slug: str, cat_ids: list, tag_ids: list, cover: str = "") -> dict:
    return {
        "title": title,
        "slug": slug,
        "categories": cat_ids,
        "tags": tag_ids,
        "cover": cover or "",
        "excerpt": {"autoGenerate": True},
        "allowComment": True,
        "publish": False,
        "pinned": False,
        "priority": 0,
        "visible": "PUBLIC",
        "deleted": False,
    }


def _search_cover_from_bing_cn(query: str) -> str | None:
    """必应中国搜索图片，国内可直接访问。"""
    from urllib.parse import quote

    try:
        url = f"https://cn.bing.com/images/async?q={quote(query)}&first=0&count=35"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }
        r = requests.get(url, headers=headers, timeout=30)
        r.raise_for_status()
        # Bing 返回 HTML 中 murl 以 &quot; 转义
        m = re.search(r'&quot;murl&quot;:&quot;(https?://[^&]+)&quot;', r.text)
        if m:
            return m.group(1)
    except Exception as e:
        print(f"   必应搜索错误: {e}")
    return None


def _search_cover_from_duckduckgo(query: str) -> str | None:
    """DuckDuckGo 图片搜索。"""
    try:
        from duckduckgo_search import DDGS

        with DDGS(timeout=30) as ddgs:
            results = list(ddgs.images(query, max_results=5))
        for r in results:
            url = r.get("image") or r.get("url") or r.get("thumbnail")
            if url and isinstance(url, str) and url.startswith("http"):
                return url
    except ImportError:
        print("   请安装 duckduckgo-search: pip install duckduckgo-search")
    except Exception as e:
        print(f"   DuckDuckGo 搜索错误: {e}")
    return None


def _search_cover_from_web(query: str) -> str | None:
    """从网上搜索适配图片。默认使用必应中国（国内无需代理）。"""
    if (COVER_WEB_ENGINE or "bing_cn").lower() == "duckduckgo":
        return _search_cover_from_duckduckgo(query)
    return _search_cover_from_bing_cn(query)


def _generate_cover_via_ollama(prompt: str) -> bytes | None:
    """Ollama 本地图片模型生成，返回图片字节。"""
    import base64
    import subprocess
    import tempfile
    try:
        r = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={"model": OLLAMA_IMAGE_MODEL, "prompt": prompt, "stream": False},
            timeout=120,
        )
        if r.status_code == 200:
            data = r.json()
            images = data.get("images")
            if isinstance(images, list) and images:
                b64 = images[0] if isinstance(images[0], str) else images[0].get("data")
                if b64:
                    return base64.b64decode(b64)
        # subprocess 备用
        with tempfile.TemporaryDirectory() as tmpdir:
            proc = subprocess.run(
                ["ollama", "run", OLLAMA_IMAGE_MODEL, prompt],
                cwd=tmpdir, capture_output=True, text=True, timeout=120,
            )
            if proc.returncode == 0:
                for f in sorted(os.listdir(tmpdir), key=lambda x: -os.path.getmtime(os.path.join(tmpdir, x))):
                    if f.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
                        with open(os.path.join(tmpdir, f), "rb") as fp:
                            return fp.read()
    except Exception as e:
        print(f"   Ollama 错误: {e}")
    return None


def _generate_cover_via_sd_webui(prompt: str) -> bytes | None:
    """Stable Diffusion WebUI (A1111) 生成，返回图片字节。"""
    import base64
    try:
        r = requests.post(
            f"{SD_WEBUI_URL}/sdapi/v1/txt2img",
            json={
                "prompt": prompt,
                "negative_prompt": "blurry, low quality",
                "steps": 20, "width": 768, "height": 512,
            },
            timeout=120,
        )
        if r.status_code == 200:
            images = r.json().get("images")
            if images:
                return base64.b64decode(images[0])
    except Exception as e:
        print(f"   SD WebUI 错误: {e}")
    return None


def _build_cover_query(title: str, excerpt: str, content: str = "", tags: list | None = None) -> str:
    """构建与文章内容相关的封面搜索/生成描述。有 DEEPSEEK_API_KEY 时用 AI 提取关键词。"""
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if api_key:
        try:
            text = re.sub(r"<[^>]+>", " ", (content or excerpt or ""))[:600].strip()
            prompt = f"根据以下博客文章，生成一句简短的图片搜索关键词（8-15字），用于搜索与文章主题相关的封面配图。只输出关键词本身，不要引号、不要解释。\n\n标题：{title}\n内容摘要：{text}"
            r = requests.post(
                os.getenv("DEEPSEEK_API_URL", "https://api.deepseek.com/chat/completions"),
                headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
                json={"model": "deepseek-chat", "messages": [{"role": "user", "content": prompt}], "temperature": 0.3, "max_tokens": 80, "stream": False},
                timeout=20,
            )
            if r.status_code == 200:
                raw = (r.json().get("choices", [{}])[0].get("message", {}).get("content") or "").strip()
                raw = re.sub(r'^["\']|["\']$', "", raw)
                if raw and len(raw) <= 80:
                    return raw[:100]
        except Exception:
            pass
    parts = [title]
    if tags:
        parts.extend(tags[:5])
    raw = re.sub(r"<[^>]+>", " ", (content or excerpt or title))
    raw = re.sub(r"\s+", " ", raw).strip()[:200]
    if raw:
        parts.append(raw)
    return " ".join(parts).strip()[:100] or title


def get_cover_for_post(title: str, excerpt: str, cover_source: str = "ollama", content: str = "", tags: list | None = None) -> str | None:
    """获取封面并上传到 Halo，返回封面 URL。content/tags 用于构建与文章相关的搜索描述。"""
    cover_source = (cover_source or COVER_IMAGE_BACKEND or "ollama").lower().strip()
    query = _build_cover_query(title, excerpt, content or excerpt, tags or [])

    if cover_source == "web_search":
        img_url = _search_cover_from_web(query)
        if not img_url:
            return None
        try:
            r = requests.get(img_url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code != 200:
                return None
            img_bytes = r.content
            if len(img_bytes) < 100:
                return None
            ext = "png"
            ct = r.headers.get("Content-Type", "")
            if "jpeg" in ct or "jpg" in ct:
                ext = "jpg"
            elif "webp" in ct:
                ext = "webp"
            return upload_cover_to_halo(img_bytes)
        except Exception:
            return None

    prompt = f"Blog cover image, modern minimal style, professional, about: {query}"[:500]
    if cover_source == "sd_webui":
        img_bytes = _generate_cover_via_sd_webui(prompt)
    else:
        img_bytes = _generate_cover_via_ollama(prompt)
    if img_bytes:
        return upload_cover_to_halo(img_bytes)
    return None


def upload_cover_to_halo_from_url(image_url: str) -> str | None:
    """从 URL 上传图片到 Halo。"""
    payload = {"url": image_url}
    for path in [
        f"{HALO_URL}/apis/uc.api.storage.halo.run/v1alpha1/attachments/-/upload-from-url",
        f"{HALO_URL}/apis/api.console.halo.run/v1alpha1/attachments/-/upload-from-url",
    ]:
        try:
            r = requests.post(path, headers=HEADERS, json=payload, timeout=60)
            if r.status_code in (200, 201):
                data = r.json()
                url = (data.get("status") or {}).get("url") or (data.get("spec") or {}).get("url") or data.get("url")
                if url:
                    return str(url)
                permalink = (data.get("status") or {}).get("permalink")
                if permalink:
                    return str(permalink)
        except Exception:
            continue
    return None


def upload_cover_to_halo(image_bytes: bytes) -> str | None:
    """将图片字节通过 multipart 上传到 Halo，返回封面 URL。"""
    headers = {"Authorization": f"Bearer {HALO_TOKEN}"}
    files = {"file": ("cover.png", image_bytes, "image/png")}
    for path in [
        f"{HALO_URL}/apis/uc.api.storage.halo.run/v1alpha1/attachments/-/upload",
        f"{HALO_URL}/apis/api.console.halo.run/v1alpha1/attachments/-/upload",
    ]:
        try:
            r = requests.post(path, headers=headers, files=files, timeout=60)
            if r.status_code in (200, 201):
                data = r.json()
                url = (data.get("status") or {}).get("url") or (data.get("spec") or {}).get("url") or data.get("url")
                if url:
                    return str(url)
                permalink = (data.get("status") or {}).get("permalink")
                if permalink:
                    return str(permalink)
        except Exception:
            continue
    return None


def draft_post_uc(
    title: str, content: str, category_names: list[str], tag_names: list[str], cover: str = ""
) -> dict | None:
    """使用 UC API 创建文章 (PAT 用户权限)"""
    slug = generate_slug(title)
    cat_ids = [ensure_category(c) for c in category_names]
    tag_ids = [ensure_tag(t) for t in tag_names]
    cat_ids = [x for x in cat_ids if x]
    tag_ids = [x for x in tag_ids if x]
    cats = list_categories()
    tags_list = list_tags()
    if not cat_ids and cats:
        cat_ids = [c.get("metadata", {}).get("name") for c in cats if c.get("metadata", {}).get("name")]
    if not tag_ids and tags_list:
        tag_ids = [t.get("metadata", {}).get("name") for t in tags_list if t.get("metadata", {}).get("name")]

    import json as _json
    content_json = {"content": content, "raw": re.sub(r"<[^>]+>", " ", content).strip() or content, "rawType": "HTML"}
    post = {
        "apiVersion": "content.halo.run/v1alpha1",
        "kind": "Post",
        "metadata": {
            "generateName": "post-",
            "annotations": {"content.halo.run/content-json": _json.dumps(content_json, ensure_ascii=False)},
        },
        "spec": _build_post_spec(title, slug, cat_ids, tag_ids, cover),
    }
    url = f"{HALO_URL}/apis/uc.api.content.halo.run/v1alpha1/posts"
    r = requests.post(url, headers=HEADERS, json=post, timeout=30)
    if r.status_code not in (200, 201):
        print(f"UC CreateMyPost failed: {r.status_code}")
        print(r.text[:800])
        return None
    return r.json()


def draft_post_console(
    title: str, content: str, category_names: list[str], tag_names: list[str], cover: str = ""
) -> dict | None:
    """使用 Console API 草稿文章 (需管理员权限)"""
    slug = generate_slug(title)
    cat_ids = [ensure_category(c) for c in category_names]
    tag_ids = [ensure_tag(t) for t in tag_names]
    cat_ids = [x for x in cat_ids if x]
    tag_ids = [x for x in tag_ids if x]
    cats = list_categories()
    tags_list = list_tags()
    if not cat_ids and cats:
        cat_ids = [c.get("metadata", {}).get("name") for c in cats if c.get("metadata", {}).get("name")]
    if not tag_ids and tags_list:
        tag_ids = [t.get("metadata", {}).get("name") for t in tags_list if t.get("metadata", {}).get("name")]

    raw = re.sub(r"<[^>]+>", " ", content).strip() or content
    payload = {
        "content": {"content": content, "raw": raw, "rawType": "HTML"},
        "post": {
            "apiVersion": "content.halo.run/v1alpha1",
            "kind": "Post",
            "metadata": {"generateName": "post-"},
            "spec": _build_post_spec(title, slug, cat_ids, tag_ids, cover),
        },
    }
    url = f"{HALO_URL}/apis/api.console.halo.run/v1alpha1/posts"
    r = requests.post(url, headers=HEADERS, json=payload, timeout=30)
    if r.status_code not in (200, 201):
        print(f"Console DraftPost failed: {r.status_code}")
        print(r.text[:800])
        return None
    return r.json()


def draft_post(
    title: str, content: str, category_names: list[str], tag_names: list[str], cover: str = ""
) -> dict | None:
    """草稿文章：优先 UC API，失败时尝试 Console API"""
    post = draft_post_uc(title, content, category_names, tag_names, cover)
    if post:
        return post
    print("Retrying with Console API...")
    return draft_post_console(title, content, category_names, tag_names, cover)


def update_post_content(post_name: str, content: str) -> bool:
    """更新文章内容"""
    url = f"{HALO_URL}/apis/api.console.halo.run/v1alpha1/posts/{post_name}/content"
    raw = re.sub(r"<[^>]+>", " ", content).strip()
    payload = {"content": content, "raw": raw or content, "rawType": "HTML"}
    r = requests.put(url, headers=HEADERS, json=payload, timeout=30)
    if r.status_code != 200:
        print(f"更新内容失败: {r.status_code} - {r.text[:200]}")
        return False
    return True


def publish_post(post_name: str) -> dict | None:
    """发布文章：优先 UC API，失败时尝试 Console API"""
    for api_name, path in [
        ("UC", f"{HALO_URL}/apis/uc.api.content.halo.run/v1alpha1/posts/{post_name}/publish"),
        ("Console", f"{HALO_URL}/apis/api.console.halo.run/v1alpha1/posts/{post_name}/publish"),
    ]:
        r = requests.put(path, headers=HEADERS, timeout=30)
        if r.status_code == 200:
            return r.json()
        print(f"  {api_name} publish: {r.status_code}")
    print(f"Publish failed: {r.text[:500]}")
    return None


def try_minimal_post() -> bool:
    """尝试极简请求以排查问题"""
    slug = generate_slug("minimal-test")
    cats = list_categories()
    tags_list = list_tags()
    cat_ids = [c.get("metadata", {}).get("name") for c in (cats or []) if c.get("metadata", {}).get("name")]
    tag_ids = [t.get("metadata", {}).get("name") for t in (tags_list or []) if t.get("metadata", {}).get("name")]
    print(f"  Using categories: {cat_ids[:3]}")
    print(f"  Using tags: {tag_ids[:3]}")
    url = f"{HALO_URL}/apis/uc.api.content.halo.run/v1alpha1/posts"
    payload = {
        "apiVersion": "content.halo.run/v1alpha1",
        "kind": "Post",
        "metadata": {"generateName": "post-"},
        "spec": {
            "title": "Minimal Test",
            "slug": slug,
            "categories": cat_ids[:1] if cat_ids else [],
            "tags": tag_ids[:1] if tag_ids else [],
            "excerpt": {"autoGenerate": True},
            "allowComment": True,
            "publish": False,
            "pinned": False,
            "priority": 0,
            "visible": "PUBLIC",
            "deleted": False,
        },
    }
    r = requests.post(url, headers=HEADERS, json=payload, timeout=30)
    print(f"UC CreateMyPost: {r.status_code}")
    if r.status_code in (200, 201):
        print("SUCCESS - minimal post works")
        return True
    print(r.text[:600])
    return False


def main():
    print("=" * 50)
    print("Publish test post with categories and tags")
    print(f"HALO_URL: {HALO_URL}")
    print("=" * 50)

    if "--debug" in sys.argv:
        print("\n[DEBUG] Verifying token...")
        r = requests.get(f"{HALO_URL}/apis/api.console.halo.run/v1alpha1/users/-", headers=HEADERS, timeout=15)
        print(f"  Get current user: {r.status_code}")
        if r.status_code == 200:
            u = r.json()
            print(f"  User: {u.get('spec', {}).get('displayName')}")
        else:
            print(f"  {r.text[:300]}")
        r2 = requests.get(f"{HALO_URL}/apis/content.halo.run/v1alpha1/categories", headers=HEADERS, params={"size": 5}, timeout=15)
        print(f"  List categories: {r2.status_code}")
        if r2.status_code == 200:
            items = (r2.json() or {}).get("items") or []
            print(f"  Count: {len(items)}")
        print("\n[DEBUG] Trying minimal post...")
        try_minimal_post()
        return

    title = "Test Post - Halo REST API"
    content = """
<h1>测试文章</h1>
<p>这是一篇通过 Halo RESTful API 发布的测试文章。</p>
<p>包含分类和标签，用于验证 API 集成是否正常工作。</p>
<p><strong>发布时间：</strong> """ + datetime.now().strftime("%Y-%m-%d %H:%M:%S") + """</p>
"""
    categories = ["技术", "测试"]
    tags = ["测试", "API", "自动发布"]
    use_cover = "--cover" in sys.argv

    cover = ""
    cover_source = os.getenv("COVER_IMAGE_BACKEND", "ollama")
    if "--cover-web" in sys.argv:
        cover_source = "web_search"
    elif "--cover-sd" in sys.argv:
        cover_source = "sd_webui"
    if use_cover:
        print(f"\n0. Getting cover image (source: {cover_source})...")
        excerpt = re.sub(r"<[^>]+>", " ", content).strip()[:150]
        cover = get_cover_for_post(title, excerpt, cover_source, content=content, tags=tags)
        if cover:
            print("   Cover image uploaded.")
        else:
            print("   Cover failed. For web_search ensure duckduckgo-search is installed; for ollama/sd_webui ensure service is running.")

    print("\n1. Preparing categories and tags...")
    for c in categories:
        name = ensure_category(c)
        print(f"   Category [{c}]: {name or 'failed'}")
    for t in tags:
        name = ensure_tag(t)
        print(f"   Tag [{t}]: {name or 'failed'}")

    print("\n2. Drafting post...")
    post = draft_post(title, content, categories, tags, cover)
    if not post:
        print("Draft failed. Run with --debug to troubleshoot.")
        print("Tip: Ensure PAT has 'create post' permission.")
        sys.exit(1)

    post_name = post.get("metadata", {}).get("name")
    print(f"   Post name: {post_name}")

    print("\n3. Publishing...")
    published = publish_post(post_name)
    if not published:
        print("发布失败")
        sys.exit(1)

    spec = published.get("spec", {})
    status = published.get("status", {})
    print("\n" + "=" * 50)
    print("Published successfully!")
    print("=" * 50)
    print(f"Title: {spec.get('title')}")
    print(f"Slug: {spec.get('slug')}")
    print(f"Categories: {spec.get('categories', [])}")
    print(f"Tags: {spec.get('tags', [])}")
    print(f"Status: {'Published' if spec.get('publish') else 'Draft'}")
    print(f"URL: {status.get('permalink', HALO_URL)}")
    print("=" * 50)


if __name__ == "__main__":
    main()

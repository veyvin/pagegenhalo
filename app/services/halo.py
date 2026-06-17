import re
from datetime import datetime
from typing import List, Optional, Tuple

import requests
from flask import current_app

from app.utils.logging import log_step


def _to_ascii_slug(s: str) -> str:
    """生成 ASCII 安全 slug，用于 metadata.name。"""
    s = re.sub(r"[^a-z0-9\-_\u4e00-\u9fa5]", "-", s.lower())
    s = re.sub(r"-+", "-", s).strip("-")
    if not s or not s[0].isascii():
        s = "cat-" + (s or "default")[:50]
    return (s or "default")[:63]


def _list_categories(halo_url: str, headers: dict) -> List[dict]:
    """获取分类列表。"""
    url = f"{halo_url.rstrip('/')}/apis/content.halo.run/v1alpha1/categories"
    r = requests.get(url, headers=headers, params={"size": 100}, timeout=15)
    if r.status_code != 200:
        return []
    data = r.json()
    return data.get("items") or []


def _list_tags(halo_url: str, headers: dict) -> List[dict]:
    """获取标签列表。"""
    url = f"{halo_url.rstrip('/')}/apis/content.halo.run/v1alpha1/tags"
    r = requests.get(url, headers=headers, params={"size": 100}, timeout=15)
    if r.status_code != 200:
        return []
    data = r.json()
    return data.get("items") or []


def _create_category(halo_url: str, headers: dict, display_name: str, slug: str) -> Optional[str]:
    """创建分类，返回 metadata.name。"""
    url = f"{halo_url.rstrip('/')}/apis/content.halo.run/v1alpha1/categories"
    name = _to_ascii_slug(slug)
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
    r = requests.post(url, headers=headers, json=payload, timeout=15)
    if r.status_code not in (200, 201):
        return None
    data = r.json()
    return data.get("metadata", {}).get("name")


def _create_tag(halo_url: str, headers: dict, display_name: str, slug: str) -> Optional[str]:
    """创建标签，返回 metadata.name。"""
    url = f"{halo_url.rstrip('/')}/apis/content.halo.run/v1alpha1/tags"
    name = _to_ascii_slug(slug)
    payload = {
        "apiVersion": "content.halo.run/v1alpha1",
        "kind": "Tag",
        "metadata": {"name": name},
        "spec": {"displayName": display_name, "slug": slug or name},
    }
    r = requests.post(url, headers=headers, json=payload, timeout=15)
    if r.status_code not in (200, 201):
        return None
    data = r.json()
    return data.get("metadata", {}).get("name")


def _ensure_category(halo_url: str, headers: dict, display_name: str) -> Optional[str]:
    """确保分类存在，返回 metadata.name。不存在则创建。"""
    slug = re.sub(r"[^a-z0-9\-_\u4e00-\u9fa5]", "-", display_name.lower())
    slug = re.sub(r"-+", "-", slug).strip("-") or "default"
    cats = _list_categories(halo_url, headers)
    for c in cats:
        s = c.get("spec", {})
        if s.get("displayName") == display_name or s.get("slug") == slug:
            return c.get("metadata", {}).get("name")
    created = _create_category(halo_url, headers, display_name, slug)
    if created:
        return created
    if cats:
        return cats[0].get("metadata", {}).get("name")
    return None


def _ensure_tag(halo_url: str, headers: dict, display_name: str) -> Optional[str]:
    """确保标签存在，返回 metadata.name。不存在则创建。"""
    slug = re.sub(r"[^a-z0-9\-_\u4e00-\u9fa5]", "-", display_name.lower())
    slug = re.sub(r"-+", "-", slug).strip("-") or "default"
    tags_list = _list_tags(halo_url, headers)
    for t in tags_list:
        s = t.get("spec", {})
        if s.get("displayName") == display_name or s.get("slug") == slug:
            return t.get("metadata", {}).get("name")
    created = _create_tag(halo_url, headers, display_name, slug)
    if created:
        return created
    if tags_list:
        return tags_list[0].get("metadata", {}).get("name")
    return None


def _resolve_categories_and_tags(
    halo_url: str,
    headers: dict,
    category_names: List[str],
    tag_names: List[str],
) -> Tuple[List[str], List[str]]:
    """将分类、标签显示名解析为 metadata.name，不存在则创建。"""
    cat_ids = [_ensure_category(halo_url, headers, c) for c in (category_names or [])]
    tag_ids = [_ensure_tag(halo_url, headers, t) for t in (tag_names or [])]
    cat_ids = [x for x in cat_ids if x]
    tag_ids = [x for x in tag_ids if x]
    cats = _list_categories(halo_url, headers)
    tags_list = _list_tags(halo_url, headers)
    if not cat_ids and cats:
        cat_ids = [c.get("metadata", {}).get("name") for c in cats if c.get("metadata", {}).get("name")]
    if not tag_ids and tags_list:
        tag_ids = [t.get("metadata", {}).get("name") for t in tags_list if t.get("metadata", {}).get("name")]
    return cat_ids, tag_ids


def generate_unique_slug(title: str) -> str:
    """生成唯一的 slug。"""
    slug = title.lower()
    slug = re.sub(r"[^a-z0-9\-_\u4e00-\u9fa5]", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    slug = slug.strip("-")
    if len(slug) > 60:
        slug = slug[:60].rstrip("-")

    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    return f"{slug}-{timestamp}"


def _build_post_spec(
    title: str,
    slug: str,
    cat_ids: List[str],
    tag_ids: List[str],
    excerpt: str,
    cover: str = "",
) -> dict:
    """构建 Post spec，草稿创建时 publish=False。"""
    now = datetime.now()
    publish_time = now.strftime("%Y-%m-%dT%H:%M:%S+08:00")
    return {
        "title": title,
        "slug": slug,
        "template": "",
        "cover": cover or "",
        "deleted": False,
        "publish": False,
        "publishTime": publish_time,
        "pinned": False,
        "allowComment": True,
        "visible": "PUBLIC",
        "priority": 0,
        "excerpt": {"autoGenerate": False, "raw": excerpt},
        "categories": cat_ids,
        "tags": tag_ids,
        "htmlMetas": [],
    }


def _draft_post_uc(
    halo_url: str,
    headers: dict,
    title: str,
    content: str,
    slug: str,
    cat_ids: List[str],
    tag_ids: List[str],
    excerpt: str,
    cover: str = "",
) -> Optional[dict]:
    """使用 UC API 创建草稿（PAT 用户权限）。"""
    import json as _json

    # raw 须与 content 一致保留完整 HTML，否则 Halo 编辑器会显示无结构的平铺文本
    content_json = {
        "content": content,
        "raw": content,
        "rawType": "HTML",
    }
    post = {
        "apiVersion": "content.halo.run/v1alpha1",
        "kind": "Post",
        "metadata": {
            "generateName": "post-",
            "annotations": {
                "content.halo.run/content-json": _json.dumps(content_json, ensure_ascii=False)
            },
        },
        "spec": _build_post_spec(title, slug, cat_ids, tag_ids, excerpt, cover),
    }
    url = f"{halo_url.rstrip('/')}/apis/uc.api.content.halo.run/v1alpha1/posts"
    r = requests.post(url, headers=headers, json=post, timeout=30)
    if r.status_code in (200, 201):
        return r.json()
    return None


def _draft_post_console(
    halo_url: str,
    headers: dict,
    title: str,
    content: str,
    slug: str,
    cat_ids: List[str],
    tag_ids: List[str],
    excerpt: str,
    cover: str = "",
) -> Optional[dict]:
    """使用 Console API 创建草稿（管理员权限）。"""
    # raw 须保留完整 HTML，否则 Halo 编辑器会显示无结构的平铺文本
    payload = {
        "content": {"content": content, "raw": content, "rawType": "HTML"},
        "post": {
            "apiVersion": "content.halo.run/v1alpha1",
            "kind": "Post",
            "metadata": {"generateName": "post-"},
            "spec": _build_post_spec(title, slug, cat_ids, tag_ids, excerpt, cover),
        },
    }
    url = f"{halo_url.rstrip('/')}/apis/api.console.halo.run/v1alpha1/posts"
    r = requests.post(url, headers=headers, json=payload, timeout=30)
    if r.status_code in (200, 201):
        return r.json()
    return None


def _publish_post(
    halo_url: str, headers: dict, post_name: str
) -> Optional[dict]:
    """发布已创建的草稿。"""
    for path in [
        f"{halo_url.rstrip('/')}/apis/uc.api.content.halo.run/v1alpha1/posts/{post_name}/publish",
        f"{halo_url.rstrip('/')}/apis/api.console.halo.run/v1alpha1/posts/{post_name}/publish",
    ]:
        r = requests.put(path, headers=headers, timeout=30)
        if r.status_code == 200:
            return r.json()
    return None


def publish_to_halo(
    title: str,
    content: str,
    tags: Optional[List[str]] = None,
    categories: Optional[List[str]] = None,
    publish: bool = True,
    generate_cover: bool = False,
    cover_source: Optional[str] = None,
    ollama_url: Optional[str] = None,
    sd_webui_url: Optional[str] = None,
    debug_steps: Optional[List[str]] = None,
) -> Tuple[Optional[dict], Optional[str]]:
    """发布文章到 Halo 或保存为草稿。分类、标签按显示名解析为 ID，不存在则创建。
    generate_cover=True 时根据 cover_source（web_search/ollama/sd_webui）生成或搜索封面图。"""
    halo_url = (current_app.config.get("HALO_URL") or "https://veyvin.com").rstrip("/")
    halo_token = current_app.config.get("HALO_TOKEN")

    if not halo_token:
        log_step(debug_steps, "Halo", "未找到 HALO_TOKEN 配置")
        return None, "未找到 HALO_TOKEN 配置"

    headers = {
        "Authorization": f"Bearer {halo_token}",
        "Content-Type": "application/json",
    }

    slug = generate_unique_slug(title)
    log_step(debug_steps, "Halo", f"生成 slug: {slug}")

    try:
        cat_ids, tag_ids = _resolve_categories_and_tags(
            halo_url, headers,
            category_names=categories or [],
            tag_names=tags or [],
        )
    except requests.exceptions.RequestException as exc:
        log_step(debug_steps, "Halo", f"解析分类/标签失败: {exc}")
        return None, f"解析分类/标签失败: {exc}"
    except Exception as exc:  # noqa: BLE001
        log_step(debug_steps, "Halo", f"解析分类/标签出错: {exc}")
        return None, f"解析分类/标签出错: {exc}"

    if not cat_ids:
        log_step(debug_steps, "Halo", "未找到可用分类，将使用空列表")
    if not tag_ids:
        log_step(debug_steps, "Halo", "未找到可用标签，将使用空列表")

    excerpt = re.sub(r"<[^>]+>", "", content)[:150]

    cover = ""
    if generate_cover:
        try:
            from app.services.cover_image import get_cover_for_post
            cover = get_cover_for_post(
                title, excerpt,
                cover_source=cover_source or "ollama",
                ollama_url=ollama_url,
                sd_webui_url=sd_webui_url,
                content=content,
                tags=tags or [],
            ) or ""
            if cover:
                log_step(debug_steps, "Halo", "已生成并上传封面图")
        except Exception:  # noqa: BLE001
            pass

    try:
        draft = _draft_post_uc(
            halo_url, headers, title, content, slug, cat_ids, tag_ids, excerpt, cover
        )
    except requests.exceptions.RequestException as exc:
        log_step(debug_steps, "Halo", f"UC API 请求失败: {exc}")
        draft = None

    if draft is None:
        log_step(debug_steps, "Halo", "UC API 创建草稿失败，尝试 Console API")
        try:
            draft = _draft_post_console(
                halo_url, headers, title, content, slug, cat_ids, tag_ids, excerpt, cover
            )
        except requests.exceptions.RequestException as exc:
            log_step(debug_steps, "Halo", f"Console API 请求失败: {exc}")
            return None, f"创建草稿失败: {exc}"

    if draft is None:
        log_step(debug_steps, "Halo", "创建草稿失败")
        return None, "创建草稿失败，请检查 HALO_TOKEN 权限及 Halo 服务"

    post_name = (draft.get("metadata") or {}).get("name")
    if not post_name:
        return None, "创建草稿成功但未获取到文章 name"

    log_step(debug_steps, "Halo", f"草稿创建成功: {post_name}")

    if publish:
        try:
            published = _publish_post(halo_url, headers, post_name)
        except requests.exceptions.RequestException as exc:
            log_step(debug_steps, "Halo", f"发布请求失败: {exc}")
            return draft, f"草稿已保存，但发布失败: {exc}"
        if published is None:
            return draft, "草稿已保存，但发布失败，可在 Halo 后台手动发布"
        log_step(debug_steps, "Halo", "文章已发布")
        return published, None

    return draft, None


def list_halo_posts(
    publish: Optional[bool] = None,
    page: int = 0,
    size: int = 20,
) -> Tuple[Optional[List[dict]], Optional[str]]:
    """从 Halo 拉取文章列表。publish=False 仅草稿，True 仅已发布，None 全部。"""
    # 优先使用传入的参数，其次使用应用配置
    try:
        from flask import current_app
        halo_url = current_app.config.get("HALO_URL", "https://veyvin.com")
        halo_token = current_app.config.get("HALO_TOKEN")
    except RuntimeError:
        # 不在应用上下文内，使用默认值
        halo_url = "https://veyvin.com"
        # halo_token 必须提供
        import os
        halo_token = os.getenv("HALO_TOKEN")

    if not halo_token:
        return None, "未找到 HALO_TOKEN 配置"

    headers = {
        "Authorization": f"Bearer {halo_token}",
        "Content-Type": "application/json",
    }
    url = f"{halo_url}/apis/api.console.halo.run/v1alpha1/posts"
    params = {"page": str(page), "size": str(min(size, 50))}
    if publish is not None:
        params["publish"] = "true" if publish else "false"

    try:
        response = requests.get(url, headers=headers, params=params, timeout=15)
        if response.status_code != 200:
            return None, f"Halo API 错误: {response.status_code} - {response.text[:200]}"
        data = response.json()
        items = data.get("items")
        if not isinstance(items, list):
            items = data.get("result") if isinstance(data.get("result"), list) else []
        # 若 API 未按 publish 过滤，在本地过滤草稿
        if publish is False and items:
            items = [i for i in items if isinstance(i, dict) and (i.get("spec") or {}).get("publish") is False]
        return items, None
    except requests.exceptions.RequestException as exc:
        return None, f"请求失败: {str(exc)}"
    except Exception as exc:  # noqa: BLE001
        return None, f"解析失败: {str(exc)}"


def get_halo_post(name: str) -> Tuple[Optional[dict], Optional[str]]:
    """根据文章 name（metadata.name）获取单篇详情（含正文）。"""
    # 优先使用传入的参数，其次使用应用配置
    try:
        from flask import current_app
        halo_url = current_app.config.get("HALO_URL", "https://veyvin.com")
        halo_token = current_app.config.get("HALO_TOKEN")
    except RuntimeError:
        # 不在应用上下文内，使用默认值
        halo_url = "https://veyvin.com"
        # halo_token 必须提供
        import os
        halo_token = os.getenv("HALO_TOKEN")

    if not halo_token:
        return None, "未找到 HALO_TOKEN 配置"
    if not name or not name.strip():
        return None, "文章 name 不能为空"

    headers = {
        "Authorization": f"Bearer {halo_token}",
        "Content-Type": "application/json",
    }
    
    # 测试多个 API 端点
    endpoints = [
        f"{halo_url}/apis/content.halo.run/v1alpha1/posts/{name.strip()}",
        f"{halo_url}/apis/uc.api.content.halo.run/v1alpha1/posts/{name.strip()}",
    ]

    try:
        for url in endpoints:
            response = requests.get(url, headers=headers, timeout=15)
            if response.status_code == 200:
                return response.json(), None
        
        # 所有端点都失败
        return None, "未找到该文章"
    except requests.exceptions.RequestException as exc:
        return None, f"请求失败: {str(exc)}"
    except Exception as exc:  # noqa: BLE001
        return None, f"解析失败: {str(exc)}"


def update_post_tags_and_categories(
    post_name: str,
    tags: Optional[List[str]] = None,
    categories: Optional[List[str]] = None,
    debug_steps: Optional[List[str]] = None,
) -> Tuple[Optional[dict], Optional[str]]:
    """更新文章的标签和分类。"""
    # 优先使用传入的参数，其次使用应用配置
    try:
        from flask import current_app
        halo_url = current_app.config.get("HALO_URL", "https://veyvin.com")
        halo_token = current_app.config.get("HALO_TOKEN")
    except RuntimeError:
        # 不在应用上下文内，使用默认值
        halo_url = "https://veyvin.com"
        # halo_token 必须提供
        import os
        halo_token = os.getenv("HALO_TOKEN")

    if not halo_token:
        log_step(debug_steps, "Halo", "未找到 HALO_TOKEN 配置")
        return None, "未找到 HALO_TOKEN 配置"
    if not post_name or not post_name.strip():
        return None, "文章 name 不能为空"

    headers = {
        "Authorization": f"Bearer {halo_token}",
        "Content-Type": "application/json",
    }

    # 先获取文章详情
    post, error = get_halo_post(post_name)
    if error:
        log_step(debug_steps, "Halo", f"获取文章失败: {error}")
        return None, f"获取文章失败: {error}"

    if not post:
        return None, "未找到该文章"

    spec = post.get("spec") or {}
    content_obj = post.get("content") or {}
    title = spec.get("title", "")
    slug = spec.get("slug", "")
    content = content_obj.get("raw") or content_obj.get("content") or ""
    excerpt_obj = spec.get("excerpt") or {}
    excerpt = excerpt_obj.get("raw") or ""
    cover = spec.get("cover") or ""

    # 解析标签和分类
    try:
        cat_ids, tag_ids = _resolve_categories_and_tags(
            halo_url, headers,
            category_names=categories or [],
            tag_names=tags or [],
        )
    except requests.exceptions.RequestException as exc:
        log_step(debug_steps, "Halo", f"解析分类/标签失败: {exc}")
        return None, f"解析分类/标签失败: {exc}"
    except Exception as exc:  # noqa: BLE001
        log_step(debug_steps, "Halo", f"解析分类/标签出错: {exc}")
        return None, f"解析分类/标签出错: {exc}"

    # 构建更新的 spec
    updated_spec = _build_post_spec(title, slug, cat_ids, tag_ids, excerpt, cover)
    # 保留原有的 publish 状态和其他字段
    updated_spec["publish"] = spec.get("publish", False)
    updated_spec["publishTime"] = spec.get("publishTime", updated_spec.get("publishTime"))
    updated_spec["pinned"] = spec.get("pinned", False)
    updated_spec["allowComment"] = spec.get("allowComment", True)
    updated_spec["visible"] = spec.get("visible", "PUBLIC")
    updated_spec["priority"] = spec.get("priority", 0)
    updated_spec["deleted"] = spec.get("deleted", False)
    updated_spec["template"] = spec.get("template", "")
    updated_spec["htmlMetas"] = spec.get("htmlMetas", [])

    # 更新文章 - 测试多个 API 端点
    update_endpoints = [
        f"{halo_url}/apis/content.halo.run/v1alpha1/posts/{post_name}",
        f"{halo_url}/apis/uc.api.content.halo.run/v1alpha1/posts/{post_name}",
    ]
    
    payload = {
        "apiVersion": "content.halo.run/v1alpha1",
        "kind": "Post",
        "metadata": post.get("metadata", {}),
        "spec": updated_spec,
    }

    try:
        for url in update_endpoints:
            log_step(debug_steps, "Halo", f"更新文章标签和分类: {post_name} (端点: {url})")
            response = requests.put(url, headers=headers, json=payload, timeout=30)
            if response.status_code == 200:
                log_step(debug_steps, "Halo", "文章更新成功")
                return response.json(), None
        
        # 所有端点都失败
        return None, f"Halo API 错误: 所有端点都失败"
    except requests.exceptions.RequestException as exc:
        log_step(debug_steps, "Halo", f"更新请求失败: {exc}")
        return None, f"请求失败: {str(exc)}"
    except Exception as exc:  # noqa: BLE001
        log_step(debug_steps, "Halo", f"更新失败: {exc}")
        return None, f"更新失败: {str(exc)}"


def find_and_update_posts_without_tags_categories(
    limit: int = 100,
    force_update: bool = False,
    debug_steps: Optional[List[str]] = None,
) -> Tuple[List[dict], Optional[str]]:
    """搜索所有没有标签和分类的文章，并根据内容自动添加标签和分类。
    
    Args:
        limit: 最多处理的文章数量
        force_update: 如果为 True，强制更新所有文章（即使已有标签和分类）
        debug_steps: 调试步骤列表
    
    返回 (更新结果列表, 错误信息)
    """
    from app.services.deepseek import extract_tags_and_categories

    log_step(debug_steps, "任务", "开始搜索没有标签和分类的文章")

    # 获取所有文章（包括已发布和草稿）
    all_posts = []
    page = 0
    size = 50

    while len(all_posts) < limit:
        posts, error = list_halo_posts(publish=None, page=page, size=size)
        if error:
            return [], f"获取文章列表失败: {error}"
        if not posts:
            break
        all_posts.extend(posts)
        if len(posts) < size:
            break
        page += 1

    log_step(debug_steps, "任务", f"共获取 {len(all_posts)} 篇文章")

    # 筛选出没有标签和分类的文章
    # 注意：列表 API 可能不返回完整信息，需要获取每篇文章的详情
    posts_to_update = []
    posts_with_tags_or_cats = 0
    posts_without_name_or_title = 0
    posts_get_detail_failed = 0
    posts_processed = 0
    
    for idx, item in enumerate(all_posts[:limit], 1):
        if not isinstance(item, dict):
            continue
        
        # Halo API 返回的数据结构：{post: {...}, categories: [...], tags: [...]}
        post_obj = item.get("post") or {}
        meta = post_obj.get("metadata") or {}
        spec = post_obj.get("spec") or {}
        post_name = meta.get("name")
        title = spec.get("title", "")
        
        # categories 和 tags 在顶层
        categories = item.get("categories") or []
        tags = item.get("tags") or []
        
        # 确保是列表类型
        if not isinstance(categories, list):
            categories = []
        if not isinstance(tags, list):
            tags = []
        
        if not post_name or not title:
            posts_without_name_or_title += 1
            if posts_without_name_or_title <= 3 and debug_steps is not None:
                log_step(debug_steps, "调试", f"第 {idx} 篇文章缺少 name 或 title: name={post_name}, title={title}")
            continue
        
        posts_processed += 1
        
        # 调试：记录前几篇文章的标签和分类情况
        if posts_processed <= 3 and debug_steps is not None:
            log_step(debug_steps, "调试", f"文章 {idx}: {title[:30]}...")
            log_step(debug_steps, "调试", f"  categories数量: {len(categories)}, tags数量: {len(tags)}")
            log_step(debug_steps, "调试", f"  categories内容: {[c.get('spec', {}).get('displayName', '') if isinstance(c, dict) else str(c)[:20] for c in categories[:2]]}")
            log_step(debug_steps, "调试", f"  tags内容: {[t.get('spec', {}).get('displayName', '') if isinstance(t, dict) else str(t)[:20] for t in tags[:2]]}")
        
        # 检查是否有标签或分类（数组长度大于0）
        has_categories = len(categories) > 0
        has_tags = len(tags) > 0
        
        # 如果强制更新模式，或者没有标签和分类，都需要处理
        if not force_update and (has_categories or has_tags):
            posts_with_tags_or_cats += 1
            continue
        
        # 需要获取文章详情以获取内容（用于提取标签和分类）
        post_detail, error = get_halo_post(post_name)
        if error:
            posts_get_detail_failed += 1
            if posts_get_detail_failed <= 5 and debug_steps is not None:
                log_step(debug_steps, "调试", f"获取文章 {post_name} ({title}) 详情失败: {error}")
            continue
        
        if not post_detail:
            posts_get_detail_failed += 1
            continue
        
        # 添加到待更新列表
        posts_to_update.append({
            "name": post_name,
            "title": title,
            "post": post_detail,  # 使用完整详情以获取内容
            "has_existing_tags": has_tags,
            "has_existing_categories": has_categories,
        })

    log_step(debug_steps, "任务", f"处理了 {posts_processed} 篇文章，找到 {len(posts_to_update)} 篇需要更新的文章")
    log_step(debug_steps, "任务", f"统计：{posts_with_tags_or_cats} 篇已有标签/分类，{posts_without_name_or_title} 篇缺少名称或标题，{posts_get_detail_failed} 篇获取详情失败")

    if not posts_to_update:
        return [], None

    # 更新每篇文章
    results = []
    for idx, item in enumerate(posts_to_update, 1):
        post_name = item["name"]
        title = item["title"]
        log_step(debug_steps, "任务", f"处理第 {idx}/{len(posts_to_update)} 篇: {title}")

        # 获取文章完整内容
        post_detail, error = get_halo_post(post_name)
        if error:
            results.append({
                "name": post_name,
                "title": title,
                "success": False,
                "error": f"获取文章内容失败: {error}",
            })
            continue

        content_obj = post_detail.get("content") or {}
        content = content_obj.get("raw") or content_obj.get("content") or ""

        # 提取标签和分类，即使没有内容也使用标题
        tags, categories, ext_error = extract_tags_and_categories(
            title, content or title, debug_steps=debug_steps
        )
        if ext_error or (not tags and not categories):
            results.append({
                "name": post_name,
                "title": title,
                "success": False,
                "error": f"提取标签/分类失败: {ext_error or '未提取到标签和分类'}",
                "tags": tags,
                "categories": categories,
            })
            continue

        # 更新文章
        updated_post, update_error = update_post_tags_and_categories(
            post_name, tags=tags, categories=categories, debug_steps=debug_steps
        )
        if update_error:
            results.append({
                "name": post_name,
                "title": title,
                "success": False,
                "error": update_error,
                "tags": tags,
                "categories": categories,
            })
        else:
            results.append({
                "name": post_name,
                "title": title,
                "success": True,
                "tags": tags,
                "categories": categories,
            })
            log_step(debug_steps, "任务", f"✓ 成功更新: {title}")

    success_count = sum(1 for r in results if r.get("success"))
    log_step(debug_steps, "任务", f"完成！成功更新 {success_count}/{len(results)} 篇文章")

    return results, None


# 博客生成与发布相关路由

from flask import Blueprint, current_app, render_template, request

from app.services.deepseek import extract_tags_and_categories, generate_post_with_deepseek
from app.services.halo import (
    find_and_update_posts_without_tags_categories,
    get_halo_post,
    list_halo_posts,
    publish_to_halo,
)
from app.services.history import add_record, get_list, get_one
from app.utils.logging import log_step
from app.utils.response import fail, ok

blog_bp = Blueprint("blog", __name__)


@blog_bp.route("/health", methods=["GET"])
def health():
    """健康检查，供负载均衡/监控调用，无需登录。"""
    return ok(status="ok", service="flask")


@blog_bp.route("/")
def index():
    """主页。"""
    templates = current_app.config.get("WRITING_TEMPLATES", {})
    labels = current_app.config.get("TEMPLATE_LABELS", {})
    template_options = [{"id": k, "label": labels.get(k, k)} for k in templates]
    return render_template("index.html", template_options=template_options)


@blog_bp.route("/api/generate", methods=["POST"])
def api_generate():
    """生成文章并保存为草稿到 Halo。"""
    steps = []
    log_step(steps, "API", "收到生成草稿请求")

    data = request.get_json(silent=True)
    if not data:
        log_step(steps, "API", "请求体为空或解析失败")
        return fail("请求数据格式错误", 400, steps=steps)

    user_prompt = data.get("prompt", "")
    use_template = data.get("use_template", True)
    template_id = data.get("template_id", "default")
    language = data.get("language", "zh")
    auto_extract_tags = data.get("auto_extract_tags", False)
    generate_cover = data.get("generate_cover", False)
    cover_source = data.get("cover_source") or "ollama"
    ollama_url = data.get("ollama_url") or None
    sd_webui_url = data.get("sd_webui_url") or None
    tags = list(data.get("tags") or [])
    categories = list(data.get("categories") or [])
    log_step(steps, "API", f"参数：generate_cover={generate_cover}, cover_source={cover_source}, 标签={tags}, 分类={categories}")

    if not user_prompt:
        log_step(steps, "API", "缺少 prompt")
        return fail("请输入 prompt", 400, steps=steps)

    title, content, error = generate_post_with_deepseek(
        user_prompt, use_template, template_id=template_id, language=language, debug_steps=steps
    )
    if error:
        log_step(steps, "API", f"生成文章失败: {error}")
        current_app.logger.error("api_generate_failed", extra={"error": error})
        return fail(error, 500, steps=steps)
    if not title or not content:
        log_step(steps, "API", "生成的标题或内容为空")
        return fail("文章生成失败：标题或内容为空", 500, steps=steps)

    if auto_extract_tags:
        auto_tags, auto_cats, ext_err = extract_tags_and_categories(title, content, debug_steps=steps)
        if not ext_err:
            tags = list(dict.fromkeys(tags + auto_tags))[:10]
            categories = list(dict.fromkeys(categories + auto_cats))[:5]

    result, publish_error = publish_to_halo(
        title, content, tags, categories, publish=False,
        generate_cover=generate_cover,
        cover_source=cover_source,
        ollama_url=ollama_url,
        sd_webui_url=sd_webui_url,
        debug_steps=steps,
    )
    if publish_error:
        log_step(steps, "API", f"保存到 Halo 失败: {publish_error}")
        current_app.logger.error("api_generate_halo_failed", extra={"error": publish_error})
        return fail(
            f"生成成功，但保存到 Halo 失败: {publish_error}",
            500,
            title=title,
            content=content,
            steps=steps,
        )

    add_record(title, content, status="draft")
    return ok(
        data=result,
        message="文章已生成并保存为草稿到 Halo",
        title=title,
        content=content,
        tags=tags,
        categories=categories,
        steps=steps,
    )


@blog_bp.route("/api/generate-only", methods=["POST"])
def api_generate_only():
    """仅生成文章（不保存到 Halo），用于预览后再决定发布。"""
    steps = []
    log_step(steps, "API", "收到仅生成请求")

    data = request.get_json(silent=True)
    if not data:
        return fail("请求数据格式错误", 400, steps=steps)

    user_prompt = data.get("prompt", "")
    use_template = data.get("use_template", True)
    template_id = data.get("template_id", "default")
    language = data.get("language", "zh")
    auto_extract_tags = data.get("auto_extract_tags", False)
    log_step(steps, "API", f"参数：use_template={use_template}, template_id={template_id}, language={language}, auto_extract={auto_extract_tags}")

    if not user_prompt:
        return fail("请输入 prompt", 400, steps=steps)

    title, content, error = generate_post_with_deepseek(
        user_prompt, use_template, template_id=template_id, language=language, debug_steps=steps
    )
    if error:
        log_step(steps, "API", f"生成失败: {error}")
        current_app.logger.error("api_generate_only_failed", extra={"error": error})
        return fail(error, 500, steps=steps)
    if not title or not content:
        return fail("文章生成失败：标题或内容为空", 500, steps=steps)

    extracted_tags, extracted_categories = [], []
    if auto_extract_tags:
        auto_tags, auto_cats, ext_err = extract_tags_and_categories(title, content, debug_steps=steps)
        if not ext_err:
            extracted_tags, extracted_categories = auto_tags, auto_cats

    add_record(title, content, status="preview")
    return ok(
        message="文章已生成，可在下方预览后点击「发布当前预览」",
        title=title,
        content=content,
        extracted_tags=extracted_tags,
        extracted_categories=extracted_categories,
        steps=steps,
    )


@blog_bp.route("/api/publish", methods=["POST"])
def api_publish():
    """发布已有内容到 Halo。"""
    data = request.get_json(silent=True)
    if not data:
        return fail("请求数据格式错误", 400)

    title = data.get("title", "")
    content = data.get("content", "")
    tags = data.get("tags", [])
    categories = data.get("categories", [])
    generate_cover = data.get("generate_cover", False)
    cover_source = data.get("cover_source") or "ollama"
    ollama_url = data.get("ollama_url") or None
    sd_webui_url = data.get("sd_webui_url") or None

    if not title or not content:
        return fail("标题和内容不能为空", 400)

    result, error = publish_to_halo(
        title, content, tags, categories, publish=True,
        generate_cover=generate_cover,
        cover_source=cover_source,
        ollama_url=ollama_url,
        sd_webui_url=sd_webui_url,
    )
    if error:
        current_app.logger.error("api_publish_failed", extra={"error": error})
        return fail(error, 500)
    return ok(data=result, message="文章发布成功")


@blog_bp.route("/api/drafts", methods=["GET"])
def api_drafts():
    """从 Halo 拉取草稿列表。"""
    page = request.args.get("page", "0")
    size = request.args.get("size", "20")
    try:
        page = int(page)
        size = min(int(size), 50)
    except (TypeError, ValueError):
        page, size = 0, 20

    items, error = list_halo_posts(publish=False, page=page, size=size)
    if error:
        current_app.logger.warning("api_drafts_failed", extra={"error": error})
        return fail(error, 500)

    # 规范为前端需要的字段：name, title, slug, publish
    result = []
    for it in items or []:
        if not isinstance(it, dict):
            continue
        meta = it.get("metadata") or {}
        spec = it.get("spec") or {}
        result.append({
            "name": meta.get("name", ""),
            "title": spec.get("title", ""),
            "slug": spec.get("slug", ""),
            "publish": bool(spec.get("publish", False)),
        })
    return ok(data=result)


@blog_bp.route("/api/drafts/<name>", methods=["GET"])
def api_draft_detail(name):
    """获取 Halo 单篇草稿/文章内容，用于加载到预览。"""
    raw, error = get_halo_post(name)
    if error:
        return fail(error, 404 if "未找到" in error else 500)

    spec = (raw or {}).get("spec") or {}
    content_obj = (raw or {}).get("content") or {}
    title = spec.get("title", "")
    content = content_obj.get("raw") or content_obj.get("content") or ""
    return ok(title=title, content=content, name=name)


@blog_bp.route("/api/history", methods=["GET"])
def api_history():
    """返回最近生成历史列表（不含正文）。"""
    try:
        limit = min(int(request.args.get("limit", 20)), 50)
    except (TypeError, ValueError):
        limit = 20
    items = get_list(limit=limit)
    return ok(data=items, message=None)


@blog_bp.route("/api/history/<record_id>", methods=["GET"])
def api_history_item(record_id):
    """根据 id 返回一条完整记录（含 title、content），用于加载到预览。"""
    record = get_one(record_id)
    if not record:
        return fail("未找到该记录", 404)
    return ok(
        title=record["title"],
        content=record["content"],
        created_at=record["created_at"],
        status=record["status"],
    )


@blog_bp.route("/api/generate-and-publish", methods=["POST"])
def api_generate_and_publish():
    """生成并发布文章（一步完成）。"""
    steps = []
    log_step(steps, "API", "收到生成并发布请求")

    data = request.get_json(silent=True)
    if not data:
        log_step(steps, "API", "请求体为空或解析失败")
        return fail("请求数据格式错误", 400, steps=steps)

    user_prompt = data.get("prompt", "")
    use_template = data.get("use_template", True)
    template_id = data.get("template_id", "default")
    language = data.get("language", "zh")
    auto_extract_tags = data.get("auto_extract_tags", False)
    generate_cover = data.get("generate_cover", False)
    cover_source = data.get("cover_source") or "ollama"
    ollama_url = data.get("ollama_url") or None
    sd_webui_url = data.get("sd_webui_url") or None
    tags = list(data.get("tags") or [])
    categories = list(data.get("categories") or [])
    log_step(steps, "API", f"参数：generate_cover={generate_cover}, cover_source={cover_source}, 标签={tags}, 分类={categories}")

    if not user_prompt:
        log_step(steps, "API", "缺少 prompt")
        return fail("请输入 prompt", 400, steps=steps)

    title, content, error = generate_post_with_deepseek(
        user_prompt, use_template, template_id=template_id, language=language, debug_steps=steps
    )
    if error:
        log_step(steps, "API", f"生成文章失败: {error}")
        current_app.logger.error("api_generate_and_publish_failed", extra={"error": error})
        return fail(f"生成文章失败: {error}", 500, steps=steps)
    if not title or not content:
        log_step(steps, "API", "生成的标题或内容为空")
        return fail("文章生成失败：标题或内容为空", 500, steps=steps)

    if auto_extract_tags:
        auto_tags, auto_cats, ext_err = extract_tags_and_categories(title, content, debug_steps=steps)
        if not ext_err:
            tags = list(dict.fromkeys(tags + auto_tags))[:10]
            categories = list(dict.fromkeys(categories + auto_cats))[:5]

    result, publish_error = publish_to_halo(
        title, content, tags, categories, publish=True,
        generate_cover=generate_cover,
        cover_source=cover_source,
        ollama_url=ollama_url,
        sd_webui_url=sd_webui_url,
        debug_steps=steps,
    )
    if publish_error:
        log_step(steps, "API", f"发布到 Halo 失败: {publish_error}")
        current_app.logger.error("api_generate_and_publish_halo_failed", extra={"error": publish_error})
        return fail(
            f"发布失败: {publish_error}",
            500,
            title=title,
            content=content,
            steps=steps,
        )

    add_record(title, content, status="published")
    return ok(
        data=result,
        message="文章生成并发布成功",
        title=title,
        content=content,
        steps=steps,
    )


@blog_bp.route("/api/auto-tag-posts", methods=["GET", "POST"])
def api_auto_tag_posts():
    """搜索所有没有标签和分类的文章，并根据内容自动添加标签和分类。"""
    steps = []
    log_step(steps, "API", "收到自动添加标签和分类请求")

    # 支持 GET 和 POST 两种方式
    if request.method == "GET":
        limit = request.args.get("limit", "100")
        dry_run = request.args.get("dry_run", "false").lower() == "true"
        force_update = request.args.get("force_update", "false").lower() == "true"
    else:
        data = request.get_json(silent=True) or {}
        limit = data.get("limit", 100)
        dry_run = data.get("dry_run", False)
        force_update = data.get("force_update", False)
    
    try:
        limit = min(int(limit), 200)  # 最多处理200篇
    except (TypeError, ValueError):
        limit = 100

    log_step(steps, "API", f"限制处理数量: {limit}, 预览模式: {dry_run}, 强制更新: {force_update}")

    # 如果是预览模式，只返回需要更新的文章列表，不实际更新
    if dry_run:
        from app.services.halo import get_halo_post, list_halo_posts
        all_posts = []
        page = 0
        size = 50
        
        while len(all_posts) < limit:
            posts, error = list_halo_posts(publish=None, page=page, size=size)
            if error:
                return fail(f"获取文章列表失败: {error}", 500, steps=steps)
            if not posts:
                break
            all_posts.extend(posts)
            if len(posts) < size:
                break
            page += 1
        
        # 调试：查看第一篇文章的实际数据结构
        if all_posts and len(all_posts) > 0:
            first_post = all_posts[0]
            if isinstance(first_post, dict):
                log_step(steps, "调试", f"第一篇文章的所有键: {list(first_post.keys())}")
                if "metadata" in first_post:
                    log_step(steps, "调试", f"metadata 的键: {list((first_post.get('metadata') or {}).keys())}")
                if "spec" in first_post:
                    log_step(steps, "调试", f"spec 的键: {list((first_post.get('spec') or {}).keys())}")
        
        preview_results = []
        # Halo API 返回的数据结构：{post: {...}, categories: [...], tags: [...]}
        for idx, item in enumerate(all_posts[:limit], 1):
            if not isinstance(item, dict):
                continue
            
            # 从新的数据结构中提取信息
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
            
            if not post_name:
                log_step(steps, "预览", f"第 {idx} 篇文章缺少 name，跳过")
                continue
            
            preview_results.append({
                "name": post_name,
                "title": title,
                "has_categories": bool(categories),
                "has_tags": bool(tags),
                "categories": categories if categories else [],
                "tags": tags if tags else [],
                "needs_update": not categories and not tags,
            })
        
        needs_update = [p for p in preview_results if p["needs_update"]]
        return ok(
            data={
                "preview": True,
                "posts": preview_results,
                "summary": {
                    "total": len(preview_results),
                    "needs_update": len(needs_update),
                    "has_tags_or_cats": len(preview_results) - len(needs_update),
                },
            },
            message=f"预览模式：共 {len(preview_results)} 篇文章，{len(needs_update)} 篇需要更新",
            steps=steps,
        )

    results, error = find_and_update_posts_without_tags_categories(
        limit=limit, force_update=force_update, debug_steps=steps
    )
    if error:
        log_step(steps, "API", f"批量更新失败: {error}")
        current_app.logger.error("api_auto_tag_posts_failed", extra={"error": error})
        return fail(error, 500, steps=steps)

    success_count = sum(1 for r in results if r.get("success"))
    total_count = len(results)

    return ok(
        data={
            "results": results,
            "summary": {
                "total": total_count,
                "success": success_count,
                "failed": total_count - success_count,
            },
        },
        message=f"处理完成：成功更新 {success_count}/{total_count} 篇文章",
        steps=steps,
    )

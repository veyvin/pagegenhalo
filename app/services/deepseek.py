import json
import re
from typing import List, Optional, Tuple

import requests
from flask import current_app

from app.utils.logging import log_step
from app.utils.text import build_prompt, extract_title_and_content, format_code_blocks


def extract_tags_and_categories(
    title: str,
    content: str,
    debug_steps: Optional[List[str]] = None,
) -> Tuple[List[str], List[str], Optional[str]]:
    """根据文章标题和正文，用 DeepSeek 自动提取标签与分类。返回 (tags, categories, error)。"""
    # 优先使用应用配置，其次使用环境变量
    try:
        from flask import current_app
        api_key = current_app.config.get("DEEPSEEK_API_KEY")
        api_url = current_app.config.get(
            "DEEPSEEK_API_URL", "https://api.deepseek.com/chat/completions"
        )
    except RuntimeError:
        # 不在应用上下文内，使用环境变量
        import os
        api_key = os.getenv("DEEPSEEK_API_KEY")
        api_url = os.getenv("DEEPSEEK_API_URL", "https://api.deepseek.com/chat/completions")
    
    if not api_key:
        return [], [], "未找到 DEEPSEEK_API_KEY 配置"

    # 正文取前一段，避免过长
    text_snippet = re.sub(r"<[^>]+>", " ", content)[:800].strip()
    prompt = f"""根据以下文章标题和正文摘要，提取适合作为博客标签和分类的词语。

标题：{title}
正文摘要：{text_snippet}

请严格只返回一个 JSON 对象，不要其他说明，格式如下：
{{"tags": ["标签1", "标签2", "标签3"], "categories": ["分类1", "分类2"]}}
要求：
- tags：3～5 个简短标签，与文章主题相关
- categories：1～2 个分类，比标签更概括
- 仅使用中文或英文词语，不要标点
"""

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    payload = {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
        "max_tokens": 500,
        "stream": False,
    }

    try:
        log_step(debug_steps, "DeepSeek", "自动提取标签与分类")
        response = requests.post(api_url, headers=headers, json=payload, timeout=30)
        if response.status_code != 200:
            return [], [], f"提取请求失败: {response.status_code}"

        result = response.json()
        raw = result.get("choices", [{}])[0].get("message", {}).get("content", "")
        # 去掉 markdown 代码块包裹
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```\s*$", "", raw)
        # 从第一个 { 到最后一个 } 截取
        start = raw.find("{")
        if start >= 0:
            end = raw.rfind("}")
            if end > start:
                raw = raw[start : end + 1]
        obj = json.loads(raw)
        tags = obj.get("tags")
        categories = obj.get("categories")
        if not isinstance(tags, list):
            tags = []
        if not isinstance(categories, list):
            categories = []
        tags = [str(t).strip() for t in tags if t and str(t).strip()][:5]
        categories = [str(c).strip() for c in categories if c and str(c).strip()][:2]
        log_step(debug_steps, "DeepSeek", f"提取到标签: {tags}, 分类: {categories}")
        return tags, categories, None
    except json.JSONDecodeError as e:
        log_step(debug_steps, "DeepSeek", f"解析提取结果失败: {e}")
        return [], [], f"解析提取结果失败: {str(e)}"
    except requests.exceptions.RequestException as exc:
        return [], [], f"请求失败: {str(exc)}"


def extract_cover_keywords(
    title: str,
    content: str,
    debug_steps: Optional[List[str]] = None,
) -> Tuple[Optional[str], Optional[str]]:
    """根据文章标题和内容，用 DeepSeek 提取用于封面图搜索的关键词。返回 (keywords, error)。"""
    api_key = current_app.config.get("DEEPSEEK_API_KEY")
    api_url = current_app.config.get(
        "DEEPSEEK_API_URL", "https://api.deepseek.com/chat/completions"
    )
    if not api_key:
        return None, "未找到 DEEPSEEK_API_KEY"

    text = re.sub(r"<[^>]+>", " ", content)[:600].strip()
    prompt = f"""根据以下博客文章，生成一句简短的图片搜索关键词（8-15字），用于搜索与文章主题相关的封面配图。
只输出关键词本身，不要引号、不要解释、不要标点。可用中英文混合。

标题：{title}
内容摘要：{text}
"""

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    payload = {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
        "max_tokens": 80,
        "stream": False,
    }

    try:
        log_step(debug_steps, "DeepSeek", "提取封面关键词")
        response = requests.post(api_url, headers=headers, json=payload, timeout=20)
        if response.status_code != 200:
            return None, f"请求失败: {response.status_code}"

        result = response.json()
        raw = result.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
        raw = re.sub(r'^["\']|["\']$', "", raw)
        if raw and len(raw) <= 80:
            log_step(debug_steps, "DeepSeek", f"封面关键词: {raw}")
            return raw, None
        return None, "关键词为空或过长"
    except requests.exceptions.RequestException as exc:
        return None, f"请求失败: {str(exc)}"


def generate_post_with_deepseek(
    user_prompt: str,
    use_template: bool = True,
    template_id: str = "default",
    language: str = "zh",
    debug_steps: Optional[List[str]] = None,
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """使用 DeepSeek API 生成博客文章。"""
    api_key = current_app.config.get("DEEPSEEK_API_KEY")
    api_url = current_app.config.get(
        "DEEPSEEK_API_URL", "https://api.deepseek.com/chat/completions"
    )

    if not api_key:
        log_step(debug_steps, "DeepSeek", "未找到 DEEPSEEK_API_KEY 配置")
        return None, None, "未找到 DEEPSEEK_API_KEY 配置"

    full_prompt = build_prompt(user_prompt, use_template, template_id, language)

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    payload = {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": full_prompt}],
        "temperature": 0.7,
        "max_tokens": 8000,
        "stream": False,
    }

    try:
        log_step(debug_steps, "DeepSeek", "开始请求 DeepSeek API")
        response = requests.post(api_url, headers=headers, json=payload, timeout=60)
        log_step(debug_steps, "DeepSeek", f"DeepSeek API 响应状态: {response.status_code}")

        if response.status_code == 200:
            result = response.json()
            raw_content = result["choices"][0]["message"]["content"]
            log_step(debug_steps, "DeepSeek", "成功获取生成内容，开始解析标题和正文")

            title, content = extract_title_and_content(raw_content)

            if not title:
                title = "自动生成的文章"
                log_step(debug_steps, "DeepSeek", "未能提取标题，使用默认标题")

            content = format_code_blocks(content)
            log_step(debug_steps, "DeepSeek", "完成代码块格式化")

            return title, content, None

        error_msg = f"DeepSeek API 错误: {response.status_code} - {response.text[:200]}"
        log_step(debug_steps, "DeepSeek", error_msg)
        return None, None, error_msg

    except requests.exceptions.RequestException as exc:
        error_msg = f"网络请求错误: {str(exc)}"
        log_step(debug_steps, "DeepSeek", error_msg)
        return None, None, error_msg


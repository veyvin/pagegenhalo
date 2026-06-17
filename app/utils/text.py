import re
from typing import Tuple

from bs4 import BeautifulSoup


def format_code_blocks(content: str) -> str:
    """将 markdown 风格的代码块转换为 HTML 格式。"""
    content = re.sub(
        r"```(\w+)?\s*\n(.*?)\n```",
        lambda m: f'<pre><code class="language-{m.group(1) or ""}">{m.group(2)}</code></pre>',
        content,
        flags=re.DOTALL,
    )

    # 处理行内代码 `code`
    content = re.sub(r"`([^`]+)`", r"<code>\1</code>", content)

    return content


def extract_title_and_content(full_content: str) -> Tuple[str, str]:
    """从模型返回的内容中提取标题和正文。"""
    if full_content.strip().startswith("<!DOCTYPE") or full_content.strip().startswith(
        "<html"
    ):
        try:
            soup = BeautifulSoup(full_content, "html.parser")

            title_tag = soup.find("h1")
            if title_tag:
                title = title_tag.get_text().strip()
            else:
                title_tag = soup.find("title")
                title = title_tag.get_text().strip() if title_tag else ""

            body_tag = soup.find("body")
            if body_tag:
                content = str(body_tag)
            else:
                content = full_content

            return title, content
        except Exception:
            title_match = re.search(
                r"<title[^>]*>(.*?)</title>",
                full_content,
                re.IGNORECASE | re.DOTALL,
            )
            title = title_match.group(1).strip() if title_match else ""

            body_match = re.search(
                r"<body[^>]*>(.*?)</body>",
                full_content,
                re.IGNORECASE | re.DOTALL,
            )
            content = body_match.group(1) if body_match else full_content

            return title, content

    lines = full_content.strip().split("\n")
    title = ""
    content = full_content

    for line in lines:
        clean_line = line.strip()
        if clean_line and len(clean_line) < 100:
            clean_title = re.sub(r"<[^>]+>", "", clean_line)
            if clean_title and len(clean_title) > 5:
                title = clean_title
                break

    return title, content


# 多语言指令：拼在模板前，约束输出语言
LANGUAGE_INSTRUCTIONS = {
    "zh": "请全文使用中文撰写。",
    "en": "Please write the entire article in English.",
}


def build_prompt(
    user_prompt: str,
    base_template: bool = True,
    template_id: str = "default",
    language: str = "zh",
) -> str:
    """构建完整的 prompt，结合用户输入、语言和所选写作模板。"""
    if not base_template:
        return user_prompt

    from flask import current_app

    templates = current_app.config.get("WRITING_TEMPLATES", {})
    base_prompt = templates.get(template_id) or templates.get("default", "")
    if not base_prompt.strip():
        base_prompt = (
            "第一行为标题（无 HTML），第二行起为 HTML 正文。"
            "不要返回 <!DOCTYPE>/<html>/<body>，直接返回标题+正文。"
        )

    lang_instruction = LANGUAGE_INSTRUCTIONS.get(
        (language or "zh").lower(), LANGUAGE_INSTRUCTIONS["zh"]
    )
    return f"{user_prompt}\n\n{lang_instruction}\n\n{base_prompt}"


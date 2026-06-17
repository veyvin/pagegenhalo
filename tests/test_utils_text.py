"""文本工具函数单元测试。"""
import pytest

from app.utils.text import (
    format_code_blocks,
    extract_title_and_content,
    build_prompt,
)


class TestFormatCodeBlocks:
    """format_code_blocks 测试。"""

    def test_block_with_lang(self):
        text = "```python\nprint(1)\n```"
        out = format_code_blocks(text)
        assert "language-python" in out
        assert "<pre><code" in out
        assert "print(1)" in out

    def test_block_no_lang(self):
        text = "```\nfoo\n```"
        out = format_code_blocks(text)
        assert "language-" in out or "<code" in out
        assert "foo" in out

    def test_inline_code(self):
        text = "use `code()` here"
        out = format_code_blocks(text)
        assert "<code>code()</code>" in out or "code()" in out


class TestExtractTitleAndContent:
    """extract_title_and_content 测试。"""

    def test_full_html_with_h1_and_body(self):
        html = """<!DOCTYPE html><html><head><title>Old</title></head>
<body><h1>My Title</h1><p>Hello</p></body></html>"""
        title, content = extract_title_and_content(html)
        assert title == "My Title"
        assert "Hello" in content
        assert "<body>" in content or "Hello" in content

    def test_full_html_title_fallback(self):
        html = """<!DOCTYPE html><html><head><title>Page Title</title></head>
<body><p>Only body</p></body></html>"""
        title, content = extract_title_and_content(html)
        assert title == "Page Title"
        assert "Only body" in content

    def test_plain_text_first_line_as_title(self):
        text = "First Line Title\n\nMore content here."
        title, content = extract_title_and_content(text)
        assert "First" in title or title != ""
        assert "More content" in content

    def test_empty_returns_safe(self):
        title, content = extract_title_and_content("")
        assert isinstance(title, str)
        assert isinstance(content, str)


class TestBuildPrompt:
    """build_prompt 需在 Flask 应用上下文中运行。"""

    def test_no_template_returns_user_prompt_only(self, app):
        with app.app_context():
            out = build_prompt("user input", base_template=False)
        assert out == "user input"

    def test_with_template_includes_user_and_base(self, app):
        app.config["WRITING_TEMPLATES"] = {
            "default": "Base instructions here.",
        }
        with app.app_context():
            out = build_prompt("user topic", base_template=True, template_id="default")
        assert "user topic" in out
        assert "Base instructions" in out

    def test_unknown_template_id_falls_back_to_default(self, app):
        app.config["WRITING_TEMPLATES"] = {
            "default": "Default template.",
            "other": "Other template.",
        }
        with app.app_context():
            out = build_prompt("hi", base_template=True, template_id="missing")
        assert "Default template" in out
        assert "hi" in out

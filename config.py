import os
from datetime import timedelta


class BaseConfig:
    """通用配置，从环境变量集中读取。"""

    # Flask 基础配置
    SECRET_KEY = os.getenv("FLASK_SECRET_KEY", os.urandom(24).hex())
    JSON_AS_ASCII = False

    # 会话过期时间（分钟）
    SESSION_LIFETIME_MINUTES = int(os.getenv("SESSION_LIFETIME_MINUTES", "60"))
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=SESSION_LIFETIME_MINUTES)

    # DeepSeek
    DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
    DEEPSEEK_API_URL = os.getenv(
        "DEEPSEEK_API_URL", "https://api.deepseek.com/chat/completions"
    )

    # Halo
    HALO_URL = os.getenv("HALO_URL", "https://veyvin.com")
    HALO_TOKEN = os.getenv("HALO_TOKEN")

    # 封面图生成（本地模型，非商业 API）
    COVER_IMAGE_BACKEND = os.getenv("COVER_IMAGE_BACKEND", "ollama")  # ollama | sd_webui
    COVER_WEB_ENGINE = os.getenv("COVER_WEB_ENGINE", "bing_cn")  # bing_cn 国内无需代理 | duckduckgo
    OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
    OLLAMA_IMAGE_MODEL = os.getenv("OLLAMA_IMAGE_MODEL", "x/z-image-turbo")
    SD_WEBUI_URL = os.getenv("SD_WEBUI_URL", "http://localhost:7860")

    # Google Authenticator / 登录相关
    GOOGLE_AUTH_SECRET = os.getenv("GOOGLE_AUTH_SECRET")
    CONFIG_PREVIEW_PASSWORD = os.getenv("CONFIG_PREVIEW_PASSWORD", "admin123")

    # 写作模板：id -> 模板说明/约束（会拼在用户 prompt 后）
    WRITING_TEMPLATES = {
        "default": """
✨ 写作要求：
1. 文章标题请直接写在第一行，不要包含任何 HTML 标签。标题要吸引人，可以包含1-2个相关的有趣图标（如 🤖 🚀 🛠️ ⚡ 🎨 🔥 💡 📦 🌟 等）
2. 正文内容从第二行开始，使用 HTML 格式
3. 文章长度1000-2000字，要有实质内容，不要空泛
4. 正文中使用适当的 HTML 标签：<p>, <h2>, <h3>, <ul>, <li>, <code>, <strong>, <em>, <blockquote> 等
5. 所有标题标签必须包含 id 属性，例如：<h2 id="introduction">介绍</h2>
6. 不要返回完整的 HTML 文档结构（不要有 <!DOCTYPE>, <html>, <head>, <body> 标签）
7. 直接返回文章内容，不要有其他说明文字
8. 使用专业但易懂的技术语言，要有趣味性和可读性
9. 添加一些代码以增加可读性和趣味性，添加一些适当的图标如 📦 🚀 🛠️ 等以增加趣味性

🎨 增加趣味性的建议：
- 开头可以用一个有趣的故事、场景或问题引入
- 适当使用技术梗、开发趣事或生动的比喻
- 添加一些开发者会有共鸣的细节
- 使用生动的例子和场景描述
- 在合适的地方添加表情符号（但不要过度使用）

💻 代码格式要求：
- 所有代码块必须使用 <pre><code> 标签包裹
- 不要使用 ``` 来包裹代码块
- 行内代码使用 <code> 标签
- 代码要有适当的缩进和语法高亮提示（class="language-xxx"）

请严格按照这个格式返回：文章标题（第一行，不要HTML标签）
<html内容>（从第二行开始）
""",
        "tutorial": """
✨ 教程风格要求：
1. 第一行为文章标题（无 HTML），可带 1–2 个图标
2. 正文从第二行开始，使用 HTML：<p>, <h2>, <h3>, <ul>, <li>, <code>, <pre> 等
3. 结构清晰：简介 → 步骤/要点 → 小结，每步有标题 id
4. 长度 800–1500 字，偏实操，带简短代码示例
5. 不要返回 <!DOCTYPE>/<html>/<head>/<body>
6. 直接返回内容，无多余说明
""",
        "summary": """
✨ 总结/归纳风格要求：
1. 第一行为文章标题（无 HTML）
2. 正文从第二行开始，使用 HTML 标签，条理分明
3. 以要点、对比或列表为主，可配简短代码
4. 长度 600–1200 字，信息密度高
5. 不要返回完整文档结构，直接返回标题+正文
""",
    }
    TEMPLATE_LABELS = {
        "default": "默认（技术博客）",
        "tutorial": "教程风格",
        "summary": "总结风格",
    }


class DevConfig(BaseConfig):
    """开发环境配置。"""

    DEBUG = True
    ENV = "development"


class ProdConfig(BaseConfig):
    """生产环境配置。"""

    DEBUG = False
    ENV = "production"


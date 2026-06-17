import logging
import os

from dotenv import load_dotenv
from flask import Flask

from config import DevConfig, ProdConfig

load_dotenv()


def create_app(config_class=None) -> Flask:
    """应用工厂，根据环境选择配置并注册各模块。"""
    if config_class is None:
        env = os.getenv("FLASK_ENV") or os.getenv("APP_ENV") or "development"
        if env.lower() in ("prod", "production"):
            config_class = ProdConfig
        else:
            config_class = DevConfig

    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    template_folder = os.path.join(root_dir, "templates")

    app = Flask(__name__, template_folder=template_folder)
    app.config.from_object(config_class)

    app.secret_key = app.config["SECRET_KEY"]
    app.permanent_session_lifetime = app.config["PERMANENT_SESSION_LIFETIME"]

    from .auth.routes import auth_bp, require_authentication
    from .blog.routes import blog_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(blog_bp)
    app.before_request(require_authentication)

    from .errors import register_error_handlers

    register_error_handlers(app)

    if not app.config.get("DEBUG"):
        app.logger.setLevel(logging.INFO)

    return app


# 供 gunicorn / flask run 等使用：app:app
app = create_app()


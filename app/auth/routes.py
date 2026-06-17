# 认证相关路由与全局鉴权

from flask import Blueprint, redirect, render_template, request, session, url_for
from flask import current_app

from app.auth.utils import (
    generate_qr_code_data,
    generate_qr_code_url,
    get_google_authenticator_secret,
    verify_otp,
)

auth_bp = Blueprint("auth", __name__)


def require_authentication():
    """在每个请求前检查用户是否已认证（由 create_app 注册为 before_request）。"""
    # 不检查登录页、登出、隐藏配置、健康检查与静态资源
    if request.endpoint in (
        "auth.login",
        "auth.logout",
        "auth.hide_config",
        "blog.health",
        "static",
    ):
        return None
    if request.endpoint is None:
        return None

    if not session.get("authenticated"):
        if request.path.startswith("/api"):
            from flask import Response
            import json
            return Response(
                json.dumps({"success": False, "error": "未认证或会话已过期，请重新登录。"}, ensure_ascii=False),
                mimetype="application/json; charset=utf-8"
            ), 401
        return redirect(url_for("auth.login"))
    return None


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """登录页面，Google Authenticator 验证。"""
    if session.get("authenticated"):
        return redirect(url_for("blog.index"))

    show_config = session.get("show_config", False)
    valid_password = current_app.config.get("CONFIG_PREVIEW_PASSWORD", "admin123")

    if request.method == "POST":
        if "show_config_password" in request.form:
            config_password = request.form.get("show_config_password", "")
            if config_password == valid_password:
                session["show_config"] = True
                show_config = True
            else:
                return render_template(
                    "login.html",
                    preverify_error="密码错误，无法显示配置信息",
                    show_config=show_config,
                )

        token = request.form.get("token", "")
        if token and verify_otp(token):
            session.permanent = True
            session["authenticated"] = True
            return redirect(url_for("blog.index"))
        if token:
            current_app.logger.warning("login_otp_failed", extra={"reason": "invalid_or_expired"})
            return render_template(
                "login.html",
                error="验证码错误，请重试。请确保输入的是当前有效的 6 位验证码。",
                show_config=show_config,
            )

    qr_code_url = generate_qr_code_url() if show_config else None
    qr_code_data = generate_qr_code_data() if show_config else None
    secret = get_google_authenticator_secret() if show_config else None

    return render_template(
        "login.html",
        qr_code_url=qr_code_url,
        secret=secret,
        qr_code_data=qr_code_data,
        show_config=show_config,
    )


@auth_bp.route("/hide-config")
def hide_config():
    """隐藏配置信息。"""
    session.pop("show_config", None)
    return redirect(url_for("auth.login"))


@auth_bp.route("/logout")
def logout():
    """登出。"""
    session.pop("authenticated", None)
    return redirect(url_for("auth.login"))

from flask import Response, request
import json


def register_error_handlers(app):
    """注册全局错误处理器，API 路由返回 JSON，页面路由返回简单文本。"""

    @app.errorhandler(400)
    def handle_400(error):  # noqa: ARG001
        if request.path.startswith("/api"):
            return (
                Response(
                    json.dumps(
                        {
                            "success": False,
                            "error": "请求参数错误",
                        },
                        ensure_ascii=False
                    ),
                    mimetype="application/json; charset=utf-8"
                ),
                400,
            )
        return "400 Bad Request", 400

    @app.errorhandler(401)
    def handle_401(error):  # noqa: ARG001
        if request.path.startswith("/api"):
            return (
                Response(
                    json.dumps(
                        {
                            "success": False,
                            "error": "未认证或会话已过期，请重新登录。",
                        },
                        ensure_ascii=False
                    ),
                    mimetype="application/json; charset=utf-8"
                ),
                401,
            )
        return "401 Unauthorized", 401

    @app.errorhandler(403)
    def handle_403(error):  # noqa: ARG001
        if request.path.startswith("/api"):
            return (
                Response(
                    json.dumps(
                        {
                            "success": False,
                            "error": "无权限访问该资源",
                        },
                        ensure_ascii=False
                    ),
                    mimetype="application/json; charset=utf-8"
                ),
                403,
            )
        return "403 Forbidden", 403

    @app.errorhandler(500)
    def handle_500(error):  # noqa: ARG001
        app.logger.exception(error)
        if request.path.startswith("/api"):
            return (
                Response(
                    json.dumps(
                        {
                            "success": False,
                            "error": "服务器内部错误，请稍后再试",
                        },
                        ensure_ascii=False
                    ),
                    mimetype="application/json; charset=utf-8"
                ),
                500,
            )
        return "500 Internal Server Error", 500


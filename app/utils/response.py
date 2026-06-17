from flask import jsonify, Response
import json


def ok(data=None, message: str | None = None, **extra):
    """统一成功响应格式。"""
    payload: dict = {"success": True}
    if message is not None:
        payload["message"] = message
    if data is not None:
        payload["data"] = data
    payload.update(extra)
    # 使用 ensure_ascii=False 确保中文正确显示
    return Response(
        json.dumps(payload, ensure_ascii=False),
        mimetype="application/json; charset=utf-8"
    )


def fail(message: str, code: int = 400, **extra):
    """统一失败响应格式。"""
    payload: dict = {"success": False, "error": message}
    payload.update(extra)
    # 使用 ensure_ascii=False 确保中文正确显示
    return Response(
        json.dumps(payload, ensure_ascii=False),
        mimetype="application/json; charset=utf-8"
    ), code


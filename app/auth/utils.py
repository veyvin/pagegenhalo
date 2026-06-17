import base64
import os
from datetime import datetime, timedelta
from typing import Optional

import pyotp
from flask import current_app


def get_google_authenticator_secret() -> str:
    """获取或生成 Google Authenticator 密钥。"""
    secret = current_app.config.get("GOOGLE_AUTH_SECRET")
    if not secret:
        # 生成新的 20 字节随机密钥，仅用于开发/临时用途
        secret = base64.b32encode(os.urandom(20)).decode("utf-8")
        print("=" * 60)
        print("⚠️  警告：未设置 GOOGLE_AUTH_SECRET 环境变量")
        print(f"📝 生成的临时密钥: {secret}")
        print("💡 请将此密钥保存到 .env：GOOGLE_AUTH_SECRET=... 否则重启后无法登录")
        print("=" * 60)
    return secret


def verify_otp(token: str, window: int = 2) -> bool:
    """验证 OTP 令牌。"""
    if not token or len(token) != 6 or not token.isdigit():
        print(f"验证码格式错误: {token}")
        return False

    secret = get_google_authenticator_secret()
    totp = pyotp.TOTP(secret)

    current_time = datetime.now()
    expected_token = totp.now()

    is_valid = totp.verify(token, valid_window=window)

    if not is_valid:
        print(f"验证失败 - 当前时间: {current_time}")
        print(f"服务器预期验证码: {expected_token}")
        print(f"用户输入验证码: {token}")

        for i in range(-window, window + 1):
            check_time = current_time + timedelta(seconds=i * 30)
            check_token = totp.at(check_time)
            print(f"时间窗口 {i}: {check_time} - 验证码: {check_token}")

    return is_valid


def generate_qr_code_url() -> str:
    """生成 Google Authenticator 的二维码 URL。"""
    secret = get_google_authenticator_secret()
    issuer_name = "OnDayGitHub 网站"
    account_name = "管理员"
    return (
        f"otpauth://totp/{issuer_name}:{account_name}"
        f"?secret={secret}&issuer={issuer_name}"
    )


def generate_qr_code_data() -> Optional[str]:
    """生成二维码图片的 base64 数据（用于在网页中直接显示）。"""
    try:
        import qrcode
        from io import BytesIO

        qr_url = generate_qr_code_url()
        qr = qrcode.QRCode(version=1, box_size=10, border=4)
        qr.add_data(qr_url)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        img_str = base64.b64encode(buffer.getvalue()).decode()
        return f"data:image/png;base64,{img_str}"
    except ImportError:
        return None


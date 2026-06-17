"""路由集成测试（无需真实 DeepSeek/Halo）。"""

import pytest


class TestHealth:
    """GET /health 无需登录。"""

    def test_health_returns_200_and_json(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        data = r.get_json()
        assert data is not None
        assert data.get("status") in ("ok", "healthy") or "status" in data


class TestAuthRequired:
    """未登录时受保护路由应 302 或 401。"""

    def test_index_redirects_to_login_when_not_authenticated(self, client):
        r = client.get("/", follow_redirects=False)
        assert r.status_code == 302
        assert "login" in r.location or r.location.endswith("/login")

    def test_api_generate_returns_401_when_not_authenticated(self, client):
        r = client.post(
            "/api/generate",
            json={"prompt": "test", "use_template": True},
            headers={"Content-Type": "application/json"},
        )
        assert r.status_code == 401
        data = r.get_json()
        assert data is not None and data.get("success") is False
        assert "error" in data or "未认证" in str(data)

    def test_api_history_returns_401_when_not_authenticated(self, client):
        r = client.get("/api/history")
        assert r.status_code == 401


class TestLoginPage:
    """登录页可访问。"""

    def test_login_page_returns_200(self, client):
        r = client.get("/login")
        assert r.status_code == 200
        assert b"Authenticator" in r.data or b"token" in r.data.lower() or b"form" in r.data.lower()

"""Pytest 配置与公共 fixture。"""
import pytest

from app import create_app
from config import DevConfig


@pytest.fixture
def app():
    """创建测试用 Flask 应用（开发配置）。"""
    return create_app(config_class=DevConfig)


@pytest.fixture
def client(app):
    """Flask 测试客户端。"""
    return app.test_client()


@pytest.fixture
def runner(app):
    """CLI 运行器（可选）。"""
    return app.test_cli_runner()

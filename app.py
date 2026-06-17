"""
应用入口：使用工厂函数创建 Flask 应用并启动。
"""
from app import app

if __name__ == "__main__":
    app.run(debug=app.config.get("DEBUG", False), host="0.0.0.0", port=5555)

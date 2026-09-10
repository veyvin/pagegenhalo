# pagegen / Flask — app2docker 兼容镜像
# 构建: docker build -t pagegen:latest .
# 运行: docker run -d -p 5555:5555 --env-file .env --name pagegen pagegen:latest
# app2docker 会识别 EXPOSE + HEALTHCHECK + $PORT，本镜像默认监听 0.0.0.0:${PORT:-5555}

FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    APP_ENV=production \
    FLASK_ENV=production \
    PORT=5555

WORKDIR /app

# curl 仅用于 HEALTHCHECK；--no-install-recommends 保持镜像精简
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 先复制依赖，利用层缓存加速二次构建
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir "gunicorn>=21.0.0"

# 再复制应用源码（app/__init__.py 内 templates 指向 /app/templates）
COPY app.py config.py ./
COPY app/ ./app/
COPY templates/ ./templates/

# 非 root 运行，兼容受限 PaaS / app2docker 安全策略
RUN useradd -m -u 10001 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 5555

# /health 无需登录（见 app/blog/routes.py），供 app2docker / LB 探活
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:${PORT:-5555}/health || exit 1

# app/__init__.py 末尾暴露了 `app = create_app()`，即 gunicorn 的 app:app
# 用 sh -c 包一层以支持 ${PORT} 动态端口（app2docker 常注入 PORT）
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT:-5555} --workers 2 --threads 4 --timeout 120 app:app"]

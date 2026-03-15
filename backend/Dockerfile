# ── 构建阶段 ──────────────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /app

# 安装系统构建依赖
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 安装 uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# 先复制依赖声明，利用 Docker 缓存
COPY pyproject.toml uv.lock ./

# 安装依赖到 .venv（不安装项目本身，只装依赖）
RUN uv sync --frozen --no-install-project --no-dev

# 复制应用代码并安装项目
COPY . .
RUN uv sync --frozen --no-dev

# ── 运行时阶段 ────────────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

WORKDIR /app

# 安装运行时系统依赖
RUN apt-get update && apt-get install -y \
    libpq5 \
    ffmpeg \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

# 从构建阶段复制虚拟环境和应用代码
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/app /app/app

# 设置环境变量
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH="/app" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# 创建非 root 用户
RUN groupadd -r appuser && useradd -r -g appuser appuser \
    && mkdir -p /app/storage /app/uploads \
    && chown -R appuser:appuser /app

USER appuser

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:3090/health').read()" || exit 1

EXPOSE 3090

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "3090", "--workers", "4"]

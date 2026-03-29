# ── 构建阶段 ──────────────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /app

# 换用阿里云 apt 镜像（Debian trixie），加速国内构建
RUN sed -i 's|http://deb.debian.org/debian|https://mirrors.aliyun.com/debian|g; s|http://deb.debian.org/debian-security|https://mirrors.aliyun.com/debian-security|g' \
    /etc/apt/sources.list.d/debian.sources 2>/dev/null; \
    echo 'Types: deb\nURIs: https://mirrors.aliyun.com/debian\nSuites: trixie trixie-updates\nComponents: main contrib non-free non-free-firmware\nSigned-By: /usr/share/keyrings/debian-archive-keyring.gpg' \
    > /etc/apt/sources.list.d/debian.sources

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

# 安装依赖到 .venv（使用清华 PyPI 镜像）
RUN UV_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple \
    uv sync --frozen --no-install-project --no-dev

# 复制应用代码并安装项目
COPY . .
RUN UV_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple \
    uv sync --frozen --no-dev

# ── 运行时阶段 ────────────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

WORKDIR /app

# 换用阿里云 apt 镜像（Debian trixie）
RUN echo 'Types: deb\nURIs: https://mirrors.aliyun.com/debian\nSuites: trixie trixie-updates\nComponents: main contrib non-free non-free-firmware\nSigned-By: /usr/share/keyrings/debian-archive-keyring.gpg' \
    > /etc/apt/sources.list.d/debian.sources

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

# workers 数量建议 = CPU 核心数，默认 1（单核场景）
# 可通过环境变量覆盖：UVICORN_WORKERS=4
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port 3090 --workers ${UVICORN_WORKERS:-1}"]

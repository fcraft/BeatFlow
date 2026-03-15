# ECG/PCG 平台后端

基于 FastAPI 的心音心电数据管理平台后端服务。

## 功能特性

- 🔐 JWT 认证与授权（管理员/普通用户/访客）
- 📁 项目管理与文件上传（WAV/MP4）
- 📊 波形文件解析与元数据提取
- 🏷️ 标记系统（自动/手动标记S1/S2/QRS等）
- 🎥 音视频同步处理
- 🔧 自动算法集成（心音心电检测）
- 💾 存储适配层（本地存储 + S3/COS）
- 📈 API 文档（自动生成）

## 技术栈

- **框架**：FastAPI + Uvicorn
- **数据库**：PostgreSQL + SQLAlchemy 2.0
- **缓存**：内存缓存
- **音频处理**：Librosa
- **视频处理**：OpenCV + MoviePy
- **云存储**：Boto3（S3） + 腾讯云COS
- **认证**：JWT (python-jose)

## 项目结构

```
backend/
├── app/
│   ├── api/              # API路由
│   ├── core/             # 核心配置和依赖
│   ├── crud/             # 数据库操作
│   ├── db/               # 数据库模型和会话
│   ├── models/           # Pydantic模型
│   ├── schemas/          # SQLAlchemy模型
│   ├── services/         # 业务逻辑服务
│   └── utils/            # 工具函数
├── alembic/              # 数据库迁移
├── tests/                # 测试文件
└── pyproject.toml        # 项目依赖
```

## 快速开始

### 环境配置

1. 安装 Python 3.10+
2. 安装 [uv](https://docs.astral.sh/uv/) 包管理器

```bash
# 安装 uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# 安装依赖
cd backend
uv sync
```

### 数据库配置

创建 PostgreSQL 数据库：

```bash
createdb ecg_pcg_platform
```

### 环境变量

复制 `.env.example` 为 `.env` 并配置：

```bash
cp .env.example .env
# 编辑 .env 文件
```

### 启动服务

```bash
# 开发模式
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 访问 API 文档
http://localhost:8000/docs
```

## API 文档

启动服务后访问：
- Swagger UI: `/docs`
- ReDoc: `/redoc`

## 开发指南

### 数据库迁移

```bash
# 生成迁移文件
alembic revision --autogenerate -m "描述"

# 应用迁移
alembic upgrade head

# 回滚迁移
alembic downgrade -1
```

### 代码格式化

```bash
# 使用 black
black .

# 使用 ruff
ruff check --fix

# 类型检查
mypy .
```

### 运行测试

```bash
pytest
```

## 部署

### Docker 部署

```bash
# 构建镜像
docker build -t ecg-pcg-backend .

# 运行容器
docker run -p 8000:8000 ecg-pcg-backend
```

### 生产配置

1. 配置 HTTPS
2. 设置合适的 CORS 策略
3. 启用性能监控
4. 配置日志聚合

## 许可证

[待定]
# 🫀 BeatFlow — ECG/PCG 心音心电数据管理平台

一个现代化的心音心电数据采集、分析与协作平台，面向医学研究和临床数据分析场景。

![Backend-FastAPI](https://img.shields.io/badge/Backend-FastAPI-green)
![Frontend-Vue3](https://img.shields.io/badge/Frontend-Vue3-4fc08d)
![License-MIT](https://img.shields.io/badge/License-MIT-yellow)

## 技术栈

| 层 | 技术 |
|---|---|
| 后端 | FastAPI · SQLAlchemy 2.0 (async) · PostgreSQL · asyncpg |
| 前端 | Vue 3 · TypeScript · Vite · Pinia · Tailwind CSS v3 |
| 实时通信 | WebSocket |
| 信号处理 | scipy · numpy |

## 核心功能

- **数据管理**：WAV/MP4/ECG 多格式上传，自动解析元数据，波形实时预览
- **智能标记**：S1/S2 心音、QRS 波自动检测，支持手动精标与版本管理
- **分析工具**：频谱分析、心率变异性计算、多段波形对比
- **协作系统**：WebSocket 实时同步、项目权限管理、审计日志

## 快速开始

### Docker 一键启动（推荐）

仅需安装 Docker 及 Docker Compose，无需本地配置 Python / Node / PostgreSQL。

```bash
# 启动所有服务（PostgreSQL + 后端 + 前端）
docker-compose up -d --build

# 查看运行状态
docker-compose ps

# 查看日志
docker-compose logs -f
```

服务启动后：
- 前端：http://localhost:3000
- 后端 API 文档：http://localhost:3090/docs

---

### 本地开发启动

#### 环境要求

- Python 3.11，Node.js 20+（pnpm）
- PostgreSQL 14+

### 启动后端

```bash
cd backend
cp .env.example .env          # 按需编辑环境变量
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 3090 --reload
```

### 启动前端

```bash
cd frontend
pnpm install
pnpm dev
# → https://localhost:3080/
```

> 前端以 HTTPS 启动（自签名证书），AudioWorklet 等安全上下文 API 需在 HTTPS/localhost 下才可用。

### 环境变量（`backend/.env`）

```bash
DATABASE_URL=postgresql+asyncpg://beat_flow_user:beat_flow_password@localhost:5432/beat_flow
JWT_SECRET_KEY=your-secret-key
UPLOAD_DIR=./uploads
```

## 项目结构

```
BeatFlow/
├── backend/
│   ├── app/
│   │   ├── api/v1/        # REST API 路由
│   │   ├── engine/        # 信号处理引擎
│   │   ├── models/        # SQLAlchemy 模型
│   │   ├── schemas/       # Pydantic 模型
│   │   └── services/      # 业务逻辑
│   └── tests/
├── frontend/
│   └── src/
│       ├── api/           # API 调用层
│       ├── components/    # 通用组件
│       ├── views/         # 页面视图
│       └── store/         # Pinia Store
├── docs/                  # 功能与架构文档
└── scripts/               # 运维脚本
```

## 测试

```bash
# 后端
cd backend
.venv/bin/pytest tests/ -v --ignore=tests/test_ws_endpoint.py

# 前端单元测试
cd frontend
pnpm vitest run

# 前端类型检查
npx vue-tsc --noEmit
```

## API 文档

服务启动后访问：
- Swagger UI：http://localhost:3090/docs
- ReDoc：http://localhost:3090/redoc

## 许可证

MIT License

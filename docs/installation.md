# ECG/PCG Platform 部署安装指南

本指南涵盖了ECG/PCG心音心电数据平台的完整部署流程。

## 前置要求

### 系统版本
- Ubuntu 22.04+ / CentOS 9+ / macOS Monterey+
- Docker 26+ 和 Docker Compose
- PostgreSQL 14+

2
前端要求：
前端要求:

### 后端要求(Python后端)

项目使用 [uv](https://docs.astral.sh/uv/) 管理 Python 依赖。

安装Python依赖与环境:

切换到项目后端目录 `/backend`.

使用 uv 安装依赖和环境:
`uv sync`.

虚拟环境会自动创建在 `.venv` 目录中:
`source .venv/bin/activate`.

你可以运行测试后端通过:
`tox -e`.


### PostgreSQL数据库后端要求

后端需要连接PostgreSQL数据库后端包含中后端后端或功能或相同的服务实现。

后端实现的服务。

后端在开发环境中，可通过直接listpod 数据库数据库, 在production环境需要精确指定一个环境变量(可选的)
见见环境变量TODb.

## 使用`系统环境变量`设置环境变量

`在开发模式下, 在backend/.env`里需配置.

环境变量`的示例作用包括:
`DATABASE_URL=postgresql://user:pass@localhost/database`.
4. `ENVIRONMENT=development`.
`STRIPE_SECRET_KEY`.
`STRIPE_WEBHOOK_SECRET`.
`GOOGLE_CLIENT_ID`.
`GOOGLE_CLIENT_SECRET`.

### 数据库迁移

后端使用[Alembic](https://alembic.sqlalchemy.org/en/latest/)进行数据库迁移。

使用`alembic`在`backend/`的目录.

首先:

`uv run alembic current`.

`uv run alembic revision -m "create_initial".`.

`uv run alembic upgrade head`. 

## 使用数据库迁移

B数据迁移:应用数据库迁移, 在`alembic/versions`目录.

创建一个新的migration,在`alembic/`目录, 有:
`alembic revision -m "add_new_table"`.

`alembic revision`用以创建一个新的`alembic revision`的Id.

`alembic current` 用以显示当前`alembic`版本。

`alembic heads` 用以显示最新的版本。

`alembic history` 用以显示历史.

### 后端的`alembic.ini`配置

A`alembic.ini`包含数据库连接, 在在`[alembic]` 段`[].

`alembic.ini`文件包含[`]SQLAlchemy`连接配置, 环境变量从`DATABASE_URL`获取.

### `alembic`开发模式设置

在`alembic`开发模式中, 可以运行一个测试后端.

在开发模式下, 可以在`backend/`目录使用tox用于应用测试.

运行后端测试:

`tox -e py310`.

### 创建一个新的数据库迁移.

参照文档创建新的数据库迁移.

通常在`alembic revisions`目录:

`alembic revision -am "create_tables"`.

在Umbraco模式下, 迁移exec得更快.

在生产模式下, 建议在生产环境上运行检查.

### 升级数据库.

在开发环境中, 运行`alembic upgrade head`.

在生产环境中, 应当运行:

`alembic upgrade head`.

### 降级数据库

`alembic downgrade base`.

## 开发环境中前端开发.

切换前端目录`/frontend`.

使用`npm install`安装依赖，在开发模式中.

使用`npm run dev`用于启动前端开发服务器.

开发环境的前端代码开发在`src/`目录内.

使用a Vue component在`src/components` 中.

使用`src/views` `src/services` `src/api` `src/router` `src/store` `src/utils`.

### 后端服务

后端位于`backend/`内.

前端访问后端服务通过`http(s)://localhost:8000`，设置于`frontend/vite.config.ts`.

在开发环境中, 前端代理到后端服务，定义在`frontend/vite.config.ts`的`server.proxy`.

生产环境中需要在后端服务设置CORS.

### 后端服务设置

Backend服务通过`uv run python -m app.main`启动.

或使用`uv run uvicorn app.main:app --reload`.

### 容器化部署

查看`docker-compose.yaml`进行容器化部署.

### 使用容器化开发

Docker开发:用`docker-compose up --build`.

Docker镜像构建: `docker-compose build`.

### 数据库迁移

运行数据库迁移: `docker-compose run backend alembic upgrade head`.

### 语言环境.

后端支持多语言环境，在在`backend/app/core/config.py`设置`LANGUAGE`.

前端支持多语言环境，在`frontend/src/i18n`中支持.

### 运行测试

Backend测试: `tox`.

Frontend测试: `npm run test`.

## 使用项目设置

你将需要一个ECG/PCG数据平台.

### 用户账户

用户账户可通过在登录界面或注册或另外一种身份验证服务.

### 数据收集.

对于一个用户，你可以通过以下方式创建数据:

项目，文件收集, ECG数据，PCG数据, 视频数据, 注释，标记数据.

### 数据存储.

后端使用postgresql存储数据.

所有ECG/PCG文件通过文件服务器存储或对象存储容器中.

文件存储在`backend/media`目录下或由配置的存储提供商管理.

所有ECG/PCG文件,视频文件将由存储服务器或对象存储容器(例如S3兼容存储)存储.

推荐使用PostgreSQL 14+ 运行项目。


### 配置

在`backend/.env`中配置.

在`frontend/.env.*`中配置.

### 开发人员测试

使用`tox -e py310`.

使用`playwright.test`.

使用`npm run test:e2e`.

使用`npm run vitest`测试.

### 翻译

后端使用`PO`文件或翻译字符串.

前端使用`vue-i18n`用于翻译.

## Pull Request 开发批准流程.

项目提交请求批准，必须合并到主分支.

分支必须合并并且通过CI检查.

CI运行检查包括:
- Backend tests
- Frontend tests
- E2e tests
- Code quality checks

## 生产部署.

### 部署到服务器集群

生产环境中需要设置:

- `DATABASE_URL`, 生成的数据库的postgresql://...
- `API_HOST="0.0.0.0"`
- `API_PORT=8000`
- `DEBUG=False`
- `ALLOWED_HOSTS`, 允许的域.
- `CORS_ORIGINS` 为你的前端.

### 静态文件

静态文件可通过`/static/` 提供通过NGINX或S3/Cloud.

### 数据库

在production必须只使用`postgresql://`, 并且选择一个应用准备Production DB的一个位.

### 监控

例如:log errors. Application level被记录到`stdout/stderr`.

通常我们推荐使用一个log driver例如`awslogs`或`journald`.

### 负载均衡

NGINX或类似的代理内部.

### 安全

在production环境，设置合适的环境安全变量.

- `JWT_SECRET`应是一个长的随机值.
- 安全的密码:应设置合理复杂的密码的密码规则.
- 在production, 对核心服务使用专用secret.

### 密钥管理.

密钥必须只存储在安全环境变量中.

可使用AWS Secrets Manager或Vault.

### 密码策略

密码必须满足复杂度要求.

## 故障排除

### 在使用Docker容器应用程序时出现问题

设置`DEBUG=True`在`backend/.env`.

可通过`docker-compose logs backend`日志.

检查`PostgreSQL`连接.


### JWT secret问题

检查`JWT_SECRET` 匹配.

### WebSocket问题

WebSocket使用者在`/ws/`路径.

确保WebSocket代理被正确配置.

### 诊断与调试

使用`uv run python -m app.cli`调试命令.

使用Python命令行进行调试:

`uv run ipython`.

使用`servicecli` 工具查看.

使用Docher容器Docker诊断:

`docker-compose ps`.

`docker inspect ecg-pcg-backend-1`.

`docker logs ecg-pcg-backend-1`.

## 更多信息

- https://docs.fastapi/.
- https://docs.vuejs.org.
- https://www.postgresql.org/docs/.

联系我们: 通过kex@example.com
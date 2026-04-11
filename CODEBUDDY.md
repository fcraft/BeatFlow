# BeatFlow 项目规则

## 项目概述
BeatFlow 是 ECG/PCG 心音心电数据管理平台。
- 后端：FastAPI + SQLAlchemy 2.0（async）+ PostgreSQL + asyncpg，端口 3090
- 前端：Vue 3 + Vite + Pinia + Tailwind CSS v3，端口 3080

## 文档维护规则（强制）

**每次功能性变更后，必须同步更新以下文档：**

| 变更类型 | 必须更新的文档 |
|----------|--------------|
| 新增/修改/删除 API 接口 | `docs/features.md` 对应模块的接口列表 |
| 新增/修改/删除数据库模型或字段 | `docs/architecture.md` 的 Schema 部分 |
| 新增/修改/删除前端页面或路由 | `docs/features.md` 的"前端页面说明"章节 |
| 新增/修改前端组件 | `docs/features.md` 的"全局组件"或"项目相关组件"列表 |
| 新增/修改 Pinia Store | `docs/features.md` 的"Pinia Store"章节 |
| 功能模块上线/下线 | `docs/features.md` 的"功能模块总览"表格 |

文档路径：
- 功能文档：`/qqvip/proj/BeatFlow/docs/features.md`
- 架构文档：`/qqvip/proj/BeatFlow/docs/architecture.md`

## 关键约束

### 后端
1. **模型注册**：新增 SQLAlchemy 模型时，**必须**在 `backend/app/models/__init__.py` 中导入，否则关系解析会失败
2. **异步 DB**：所有数据库操作必须使用 `async/await`，使用 `AsyncSession`
3. **路由注册**：新增 endpoint 模块后，在 `backend/app/api/v1/__init__.py` 中注册

### 前端
1. **API 路径**：所有请求使用相对路径 `/api/v1/...`，**不要**硬编码 `http://localhost:3090`
2. **Toast 通知**：使用 `useToastStore` (`src/store/toast.ts`)，不要用 alert/console
3. **Modal 模式**：AppModal 使用 `v-model` 控制显示（`update:modelValue` 事件）
4. **样式**：使用 Tailwind CSS v3 工具类，**不要**引入 PrimeVue 或其他 UI 框架
5. **浏览器 API 防御性编程**：使用 AudioContext、WebSocket、WebGL 等浏览器高级 API 时，**必须**先检测可用性再调用，并提供降级方案。不可假设 API 一定存在（例如 AudioWorklet 仅在安全上下文 HTTPS/localhost 可用）
6. **测试必须覆盖降级路径**：单元测试中 mock 浏览器 API 时，**必须同时测试 API 可用和不可用两种场景**，不能只 mock 正常路径
7. **新增 UI 公共组件**：在 `src/components/ui/` 下新增公共组件后，**必须**在 `src/views/dev/ComponentTestView.vue`（`/dev/components` 页面）中添加对应的演示区块，确保组件可被可视化预览和测试
8. **浮层 z-index 管理**：所有 Teleport 浮层（下拉/Popover/Modal）使用 `nextZIndex()`（`src/constants/zIndex.ts`）动态获取层级，**不要**硬编码 `z-[9999]`。Toast 使用固定 `Z_TOAST = 99999`
9. **组件选择**：`src/components/ui/` 中已经封装了很多 UI 组件，不要重复编写代码。如有必要新增组件时，需要考虑是否可以抽象为公共组件
10. **Store 优先**：数据获取优先使用已有的 Pinia Store（如 `useProjectStore` 的 `fetchProjects`/`fetchProjectFiles`），**不要**在页面中重复编写 `fetch('/api/v1/...')` 调用已有 Store 能力覆盖的接口

## 开发完成检查清单（强制）

**每次功能开发或 Bug 修复后，必须依次执行以下步骤：**

### 1. 运行后端测试
```bash
cd /qqvip/proj/BeatFlow/backend
.venv/bin/pytest tests/ -v --ignore=tests/test_ws_endpoint.py
```
- 所有测试必须通过（test_ws_endpoint.py 需要运行中的服务端，可单独跑）
- 若修改了引擎/模型/API，须编写对应的 pytest 用例

### 2. 运行前端单元测试
```bash
cd /qqvip/proj/BeatFlow/frontend
pnpm vitest run
```
- 所有 vitest 测试必须通过
- 新增 composable / store / 工具函数时，须编写 `*.spec.ts` 测试文件

### 3. 运行前端类型检查
```bash
cd /qqvip/proj/BeatFlow/frontend
npx vue-tsc --noEmit
```
- 不得引入新的类型错误

### 4. 重启服务并验证
```bash
# 后端
cd /qqvip/proj/BeatFlow/backend
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 3090 --reload

# 前端
cd /qqvip/proj/BeatFlow/frontend
pnpm dev
```
- 确认后端 "Application startup complete" 无报错
- 确认前端 Vite dev server 正常启动

### 5.（可选）运行 E2E 测试
```bash
cd /qqvip/proj/BeatFlow/frontend
npx playwright test e2e/
```
- 需前后端均已启动
- 涉及 UI 交互变更时建议执行

### 6. 更新文档
- 按照上方"文档维护规则"同步更新 `docs/features.md` 和 `docs/architecture.md`

### 测试框架概览
| 层 | 框架 | 配置文件 | 测试目录 |
|----|------|----------|----------|
| 后端单元测试 | pytest + pytest-asyncio | `backend/pytest.ini` | `backend/tests/` |
| 前端单元测试 | vitest + @vue/test-utils | `frontend/vitest.config.ts` | `frontend/src/**/*.spec.ts` |
| E2E 测试 | Playwright | `frontend/playwright.config.ts` | `frontend/e2e/` |

---

## 启动命令

```bash
# 后端
cd /qqvip/proj/BeatFlow/backend
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 3090 --reload

# 前端（HTTPS，自签名证书，AudioWorklet 等安全上下文 API 需要）
cd /qqvip/proj/BeatFlow/frontend
pnpm dev
# → https://localhost:3080/
```

## 环境信息
- Python：3.11，venv 在 `backend/.venv`
- Node：v20.19.4（nvm），包管理器：pnpm
- PostgreSQL：localhost:5432，db=beat_flow，user=beat_flow_user，password=beat_flow_password
- ML 依赖：scipy + numpy **已安装**，满足所有信号处理需求；librosa、moviepy、opencv 已从 pyproject.toml 移除（代码中无任何调用）

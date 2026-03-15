# BeatFlow 技术架构文档

> 最后更新：2026-03-28 (Engine V3 重构 — 参数化 3 层管线取代 V2 6 层物理管线)

---

## ECG/PCG 同步机制修复（2026-03-27）

### 修复内容
1. **后端 clock-aligned sleep**：`pipeline.py` 的 `_stream_loop` 从 `asyncio.sleep(0.1)` 改为基于 `time.monotonic()` 的绝对时间对齐，消除长时间运行的累积漂移
2. **simTime 实时更新**：`virtualHuman.ts` 在 JSON 和 binary 消息处理中添加 `connectionStore.updateSimTime(serverElapsedSec)` 调用，修复顶栏 simTime 永远显示 00:00 的 bug
3. **Tab 后台恢复优化**：`useScrollingCanvas.ts` 将硬重置阈值从 0.5s 提升到 2.0s，新增 0.5-2.0s 区间的加速校正（15% 权重），避免短暂切 Tab 后波形跳跃

## 系统概述

BeatFlow 是 ECG/PCG 心音心电数据管理平台，采用前后端分离架构。前端 Vue 3 + Tailwind CSS，后端 FastAPI + PostgreSQL（asyncpg 异步驱动），通过 Vite dev proxy 代理 API 请求。

## 整体架构图

```
┌─────────────────────────────────────────────────────────────┐
│                    前端 (Vue 3 + Vite)                       │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐           │
│  │  用户界面   │  │ 波形可视化 │  │ 视频播放器 │           │
│  └────────────┘  └────────────┘  └────────────┘           │
│          │             │                   │               │
│          └─────────────┼───────────────────┘               │
│                        │ (Web Audio API / Canvas)          │
│                        ▼                                   │
│             ┌─────────────────────┐                       │
│             │   状态管理(Pinia)    │                       │
│             └─────────────────────┘                       │
│                        │                                   │
│                        ▼                                   │
│             ┌─────────────────────┐                       │
│             │  fetch(/api/v1/...)  │ ← Vite proxy到3090   │
│             └─────────────────────┘                       │
└─────────────────────────┼─────────────────────────────────┘
                          │ HTTP/WebSocket
┌─────────────────────────┼─────────────────────────────────┐
│              后端 (FastAPI :3090)                          │
│  ┌──────────────────────────────────────────┐           │
│  │              API路由层 (8个路由模块)        │           │
│  └──────────────────────────────────────────┘           │
│          │             │                   │               │
│  ┌───────▼─────┐ ┌─────▼──────┐ ┌─────────▼──────┐       │
│  │  认证中间件  │ │ 业务逻辑层 │ │ 信号处理引擎   │       │
│  │  (JWT)      │ │ (endpoints)│ │ (scipy/librosa)│       │
│  └─────────────┘ └────────────┘ └────────────────┘       │
│          │             │                   │               │
│          └─────────────┼───────────────────┘               │
│                        ▼                                   │
│             ┌──────────────────────┐                      │
│             │  PostgreSQL (async)   │                      │
│             │  SQLAlchemy 2.0 ORM  │                      │
│             └─────────────────────┘                       │
└─────────────────────────────────────────────────────────┘
```

---

## 技术栈

### 后端
| 层级 | 技术 | 版本 |
|------|------|------|
| Web 框架 | FastAPI | 0.104+ |
| 服务器 | Uvicorn | 0.24+ |
| 数据库 | PostgreSQL | 10 (本地安装) |
| ORM | SQLAlchemy | 2.0+（async） |
| 异步驱动 | asyncpg | latest |
| 认证 | python-jose + bcrypt | latest |
| 信号处理 | scipy（已安装） | latest |
| 可选依赖 | librosa, neurokit2, wfdb | 未安装（按需） |

### 前端
| 层级 | 技术 | 版本 |
|------|------|------|
| 框架 | Vue 3 | 3.4+ |
| 构建 | Vite | 5.0+ |
| 语言 | TypeScript | 5.3+ |
| 状态管理 | Pinia | 2.1+ |
| 路由 | Vue Router | 4.2+ |
| 样式 | Tailwind CSS | 3.4+ |
| 图标 | lucide-vue-next | latest |
| 包管理 | pnpm | latest |

---

## 项目目录结构

```
BeatFlow/
├── backend/
│   ├── app/
│   │   ├── main.py                    # FastAPI 应用入口
│   │   ├── api/v1/
│   │   │   ├── __init__.py            # 路由注册中心
│   │   │   └── endpoints/
│   │   │       ├── auth.py            # 认证接口
│   │   │       ├── users.py           # 用户接口
│   │   │       ├── projects.py        # 项目接口（含 email 邀请）
│   │   │       ├── files.py           # 文件接口（含波形/检测）
│   │   │       ├── annotations.py     # 标注接口
│   │   │       ├── associations.py    # 关联组接口
│   │   │       ├── community.py       # 社区接口
│   │   │       ├── simulate.py        # 模拟生成接口（心音合成 v3：多模态随机相位衰减振荡 + 带限噪声 + 急起缓落包络）
│   │   │       ├── notifications.py   # 通知/收件箱接口
│   │   │       ├── admin.py           # 管理后台接口（含系统设置）
│   │   │       ├── websocket.py       # WebSocket 协作
│   │   │       ├── virtual_human.py   # 虚拟人体 WebSocket 端点
│   │   │       └── virtual_human_profiles.py  # 虚拟人档案 CRUD REST API
│   │   ├── services/                   # 业务服务层
│   │   │   ├── storage.py             # 存储抽象（Local/S3/COS 后端）
│   │   │   └── storage_manager.py     # 存储后端工厂（从 DB 配置构建）
│   │   ├── engine/                    # 虚拟人体引擎包 (V3 参数化管线)
│   │   │   ├── __init__.py            # 导出 SimulationPipeline as VirtualHuman
│   │   │   ├── constants.py           # 采样率/chunk/生理常量
│   │   │   ├── exercise_physiology.py # 运动生理模型（Tanaka HR_max + 体能/年龄/漂移/疲劳/脱水效应）
│   │   │   ├── ws_binary_protocol.py  # 二进制 WebSocket 帧编码器/解码器
│   │   │   ├── core/                  # V3 核心管线
│   │   │   │   ├── types.py           # 层间数据类型（frozen dataclass）
│   │   │   │   ├── protocols.py       # 3 层 Protocol 接口
│   │   │   │   ├── parametric_conduction.py  # Layer 1: 参数化传导网络（timing-based，无 ODE）
│   │   │   │   ├── ecg_synthesizer.py        # Layer 2a: Gaussian 基函数 12 导联 ECG 合成
│   │   │   │   ├── parametric_pcg.py         # Layer 2b: 参数化 PCG 合成（Weissler LVET + 模态分解 + AGC）
│   │   │   │   ├── algebraic_hemo.py         # Layer 3: 代数血流动力学（无 ODE）
│   │   │   │   ├── qt_dynamics.py            # QT 动态适配（Bazett + 电解质/药物/缺血效应）
│   │   │   │   ├── hrv_generator.py          # HRV 频域生成器（LF/HF 逆 FFT + RSA）
│   │   │   │   └── lttb.py                   # LTTB 下采样（可视化压缩）
│   │   │   ├── simulation/            # 管线运行时
│   │   │   │   ├── pipeline.py        # V3 编排器（beat_loop + stream_loop + 自主神经/药代闭环）
│   │   │   │   └── validator.py       # 物理不变量校验器（11 项检查）
│   │   │   ├── mechanical/            # 杂音配置
│   │   │   │   └── murmur_config.py   # 7 种杂音声学剖面
│   │   │   ├── modulation/            # 自主神经 + 药代动力学 + 交互状态
│   │   │   │   ├── autonomic_reflex.py        # 4 通路 ANS 控制器（压力/化学/温度/RAAS）
│   │   │   │   ├── pharmacokinetics.py        # 一室药代动力学引擎（4 种药物）
│   │   │   │   ├── physiology_modulator.py    # 因素→Modifiers 统一映射
│   │   │   │   ├── interaction_state.py       # InteractionState 数据类（用户意图层）
│   │   │   │   ├── transition_engine.py       # TransitionSmoother 指数平滑引擎
│   │   │   │   └── coronary_model.py          # 冠脉循环 + CPP 缺血级联
│   │   │   └── respiratory/           # 呼吸系统
│   │   │       ├── respiratory_model.py       # 呼吸力学 + 化学感受器驱动 RR
│   │   │       └── gas_exchange.py            # O₂-Hb 解离 + Henderson-Hasselbalch pH
│   │   │   └── legacy/                # 旧引擎实现（过渡期保留）
│   │   │       └── (原有引擎文件副本)
│   │   ├── analysis/                  # 信号分析模块（从 files.py 提取）
│   │   │   ├── ecg_detector.py        # ECG 检测（scipy/neurokit2/wfdb）
│   │   │   └── pcg_detector.py        # PCG 检测 + S1/S2 分类
│   │   ├── core/
│   │   │   ├── config.py              # 配置（DB URL、JWT、CORS 等）
│   │   │   ├── deps.py                # 依赖注入（get_current_user 等）
│   │   │   ├── middleware.py          # RequestID、日志、异常中间件
│   │   │   └── logger.py             # 结构化日志
│   │   ├── db/
│   │   │   └── session.py             # 异步 SQLAlchemy 会话
│   │   ├── models/
│   │   │   ├── __init__.py            # ⚠️ 必须导入所有 ORM 模型
│   │   │   ├── user.py                # User 模型
│   │   │   ├── project.py             # 7 个业务模型
│   │   │   ├── notification.py        # Notification 模型
│   │   │   └── system_setting.py      # SystemSetting KV 模型
│   │   ├── schemas/                   # Pydantic 请求/响应模型
│   │   │   ├── base.py
│   │   │   ├── user.py
│   │   │   ├── project.py
│   │   │   ├── notification.py
│   │   │   ├── admin.py
│   │   │   ├── media.py
│   │   │   ├── annotation.py
│   │   │   └── settings.py            # 系统设置相关 Schema
│   │   └── crud/
│   │       ├── base.py                # 泛型 CRUD
│   │       └── user.py
│   ├── .venv/                         # Python 3.11 虚拟环境
│   └── .env                           # 环境变量
│
├── frontend/
│   ├── src/
│   │   ├── views/                     # 12 个页面组件（含 virtual-human/VirtualHumanView）
│   │   ├── components/                # 25 个 UI 组件（含 virtual-human/ 7 个）
│   │   ├── composables/               # Composables（含 useScrollingCanvas.ts [Catmull-Rom 插值 + Bezier 渲染 + 高斯平滑], useVirtualHumanRecorder.ts）
│   │   ├── lib/                       # 工具库
│   │   │   └── wsBinaryProtocol.ts    # 二进制 WS 帧前端解码器（decodeBinaryFrame + VitalsDelta 合并）
│   │   ├── store/                     # 5 个 Pinia Store（含 virtualHuman.ts）
│   │   ├── router/index.ts            # 路由配置（含 /inbox, /admin）
│   │   └── types/                     # TypeScript 类型定义（含 notification.ts）
│   └── vite.config.ts                 # Vite 配置（含 /api 代理）
│
└── docs/
    ├── features.md                    # 功能文档
    ├── architecture.md                # 技术架构（本文件）
    └── installation.md                # 安装说明
```

---

## 数据库 Schema

### 连接信息
- 数据库：`ecg_pcg_platform`
- 用户：`ecg_pcg_user` / 密码：`ecg_pcg_password`
- 主键类型：UUID（所有表）

### 表关系图
```
users
  ├─[1:N]─ projects (owner_id)
  ├─[1:N]─ project_members (user_id)
  ├─[1:N]─ annotations (user_id)
  ├─[1:N]─ community_posts (author_id)
  ├─[1:N]─ post_comments (author_id)
  ├─[1:N]─ file_associations (created_by)
  ├─[1:N]─ notifications (recipient_id)
  ├─[1:N]─ notifications (sender_id, nullable)
  └─[1:N]─ virtual_human_profiles (user_id)

projects
  ├─[1:N]─ project_members (project_id)
  ├─[1:N]─ media_files (project_id)
  └─[1:N]─ file_associations (project_id)

media_files
  ├─[1:N]─ annotations (file_id)
  ├─[1:N]─ analysis_results (file_id)
  ├─[1:N]─ file_shares (file_id)
  └─[1:N]─ community_posts (file_id, optional)

file_shares
  ├─[N:1]─ media_files (file_id)
  └─[N:1]─ users (created_by)

file_association_shares
  ├─[N:1]─ file_associations (association_id)
  └─[N:1]─ users (created_by)

community_posts
  └─[1:N]─ post_comments (post_id)

file_associations
  ├─[N:1]─ media_files (ecg_file_id)
  ├─[N:1]─ media_files (pcg_file_id)
  └─[N:1]─ media_files (video_file_id)
```

### 表结构

**users**
```sql
id UUID PK, email VARCHAR UNIQUE, username VARCHAR,
password_hash VARCHAR, role VARCHAR(20), is_active BOOLEAN,
created_at TIMESTAMP, updated_at TIMESTAMP
```

**projects**
```sql
id UUID PK, owner_id UUID FK→users,
name VARCHAR(100), description VARCHAR(500),
is_public BOOLEAN, created_at, updated_at
```

**project_members**
```sql
id UUID PK, project_id UUID FK→projects, user_id UUID FK→users,
role VARCHAR(20) -- owner|admin|member|viewer, created_at
```

**media_files**
```sql
id UUID PK, project_id UUID FK→projects,
filename VARCHAR(255), original_filename VARCHAR(255),
file_type VARCHAR(20) -- audio|video|ecg|pcg|other,
file_size BIGINT, file_path VARCHAR(500),
storage_backend VARCHAR(20) DEFAULT 'local' -- local|cos,
duration FLOAT, sample_rate FLOAT, channels INT, bit_depth INT,
width INT, height INT, frame_rate FLOAT,
file_metadata JSON, created_at, updated_at
```

**annotations**
```sql
id UUID PK, file_id UUID FK→media_files, user_id UUID FK→users,
annotation_type VARCHAR(20) -- s1|s2|qrs|p_wave|t_wave|murmur|other,
start_time FLOAT, end_time FLOAT, label VARCHAR(100),
confidence FLOAT, source VARCHAR(20) -- manual|auto,
annotation_metadata JSON, created_at, updated_at
```

**analysis_results**
```sql
id UUID PK, file_id UUID FK→media_files,
analysis_type VARCHAR(50), result_data JSON, created_at
```

**community_posts**
```sql
id UUID PK, author_id UUID FK→users,
title VARCHAR(200), content VARCHAR(5000),
file_id UUID FK→media_files (nullable),
tags JSON, like_count INT, view_count INT, created_at, updated_at
```

**post_comments**
```sql
id UUID PK, post_id UUID FK→community_posts,
author_id UUID FK→users, content VARCHAR(2000), created_at
```

**file_associations**
```sql
id UUID PK, project_id UUID FK→projects, created_by UUID FK→users,
name VARCHAR(200),
ecg_file_id UUID FK→media_files (nullable),
pcg_file_id UUID FK→media_files (nullable),
video_file_id UUID FK→media_files (nullable),
pcg_offset FLOAT, video_offset FLOAT,
notes VARCHAR(1000), created_at, updated_at
```

**notifications**
```sql
id UUID PK,
recipient_id UUID FK→users (CASCADE DELETE),
sender_id UUID FK→users (SET NULL, nullable),
notification_type VARCHAR(50),  -- project_invite|system_announcement|community_interaction|analysis_complete
title VARCHAR(200),
content VARCHAR(1000),
is_read BOOLEAN DEFAULT false,
status VARCHAR(20) DEFAULT 'pending',  -- pending|accepted|rejected|done
data JSONB,  -- 附加数据 {project_id, member_role, project_name 等}
created_at TIMESTAMP
```

**file_shares**
```sql
id UUID PK, 
file_id UUID FK→media_files (CASCADE DELETE),
created_by UUID FK→users (CASCADE DELETE),
share_code VARCHAR(20) UNIQUE, -- URL-safe share code
share_code_hash VARCHAR(64) UNIQUE, -- SHA256 hash for security
expires_at TIMESTAMP (nullable), -- null = never expires
is_code_required BOOLEAN DEFAULT true,
max_downloads INT (nullable), -- null = no limit
download_count INT DEFAULT 0,
view_count INT DEFAULT 0,
created_at TIMESTAMP,
last_accessed_at TIMESTAMP (nullable)
```

**file_association_shares**
```sql
id UUID PK,
association_id UUID FK→file_associations (CASCADE DELETE),
created_by UUID FK→users (CASCADE DELETE),
share_code VARCHAR(20) UNIQUE,
share_code_hash VARCHAR(64) UNIQUE,
expires_at TIMESTAMP (nullable),
is_code_required BOOLEAN DEFAULT true,
max_downloads INT (nullable),
download_count INT DEFAULT 0,
view_count INT DEFAULT 0,
created_at TIMESTAMP,
last_accessed_at TIMESTAMP (nullable)
```

**system_settings**
```sql
key VARCHAR(100) PK,      -- e.g. "storage_type", "cos_bucket_name"
value TEXT (nullable),
updated_at TIMESTAMP
```

**virtual_human_profiles**
```sql
id UUID PK,
user_id UUID FK→users (CASCADE DELETE),
name VARCHAR(100),
state_snapshot JSONB (nullable),  -- PhysioState.to_snapshot() 完整快照
settings JSONB DEFAULT '{}',      -- 引擎配置预留
is_active BOOLEAN DEFAULT true,
created_at TIMESTAMP,
updated_at TIMESTAMP
```

---

## 关键架构设计

### 异步优先
所有数据库操作使用 SQLAlchemy 2.0 async + asyncpg：
```python
async def get_projects(db: AsyncSession, user_id: UUID):
    result = await db.execute(select(Project).where(...))
    return result.scalars().all()
```

### 依赖注入认证
```python
# 在 endpoint 中使用
@router.get("/me")
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user
```

### ⚠️ 重要：模型注册
`backend/app/models/__init__.py` 必须导入所有 ORM 模型，否则 SQLAlchemy 关系解析失败：
```python
from app.models.user import User
from app.models.project import (
    Project, ProjectMember, MediaFile, Annotation,
    AnalysisResult, CommunityPost, PostComment, FileAssociation
)
from app.models.shares import FileShare, FileAssociationShare
from app.models.notification import Notification
```

### 前端 API 请求规范
所有 API 请求使用相对路径，由 Vite dev proxy 转发：
```typescript
// ✅ 正确
fetch('/api/v1/projects/')
// ❌ 错误 - 不要硬编码 host
fetch('http://localhost:3090/api/v1/projects/')
```

### 虚拟人体实时流架构
- 后端 `BeatByBeatGenerator` 使用 **PCG 4000Hz 作为主样本时钟**，ECG 通过分数残差校正到 500Hz，减少长期累计漂移
- 单拍生成时，ECG 的 `R` 峰位置和 PCG 的 `S1/S2` 位置由同一 `BeatTimeline` 推导，降低电-机械不同步
- **信号连续性优化 v2.1**：
  - **拍间 crossfade**：每拍追加到缓冲区前，头部与上一拍尾部做余弦交叉淡入淡出（ECG 12ms / PCG 8ms 窗口），消除逐拍拼接阶跃
  - **Phase-coherent 基线/噪声**：呼吸基线漂移、电极漂移和肌电噪声使用全局样本计数器 (`_ecg_global_sample_idx`) 驱动的多频正弦波，在拍边界自然连续；所有拍型（正常/P-only/VF/Asystole/静默 PCG）统一使用
  - **PCG 全局 AGC**：取消逐拍硬归一化到 0.85，改用 EMA 峰值跟踪 (α=0.4) 做平滑增益控制，首拍直接初始化 EMA，后续拍保留拍间自然幅度差异同时防止信号过载
- WebSocket `signal` 帧采用 **`sample-clock-v2`** 协议，包含 `seq`、`ecg_start_sample`、`pcg_start_sample`、`chunk_duration_ms`
- 前端波形与音频都按 `start_sample` 消费；音频端有队列上限与自动重同步，避免 PCG 因排队而越播越晚
- PVC 调度器输出的不仅有时序，还包含 **形态学参数**（多形态、融合波、插入性 PVC、NSVT），供 ECG 与 PCG 共同使用
- **ExercisePhysiologyModel**（`engine/exercise_physiology.py`）：替代固定 `exercise_intensity → HR` 线性公式，提供逐拍精确的运动 HR 仿真。Tanaka 公式（HR_max=208-0.7×age）+ 体能等级压缩斜率（fitness_level） + 心脏漂移（持续运动时 HR 渐进增加）+ 疲劳累积效应 + 脱水 +7 bpm/1%BW。通过 `set_fitness` / `set_age` 命令写入 PhysioState

### 二进制 WebSocket 推流协议

`engine/ws_binary_protocol.py`（后端）+ `frontend/src/lib/wsBinaryProtocol.ts`（前端）实现约 **75% 带宽压缩**（2800 B→~700 B/帧）。

**协议协商**：WS 连接 URL 添加 `?protocol=binary` 查询参数启用；默认为 JSON 向后兼容模式。

**二进制帧结构**：
```
[20B 定长头]
  magic       2B  = 0xBF01 (帧标识)
  version     1B  = 0x01
  flags       1B  (bit0=has_vitals_delta, bit1=has_ecg, bit2=has_pcg)
  seq         4B  uint32 (帧序号)
  ts_ms       8B  int64  (UNIX 毫秒时间戳)
  payload_len 4B  uint32

[可变 Payload]
  ECG int16[] × N_ecg   (float × 32767，±1.0 归一化空间)
  PCG int16[] × N_pcg
  Vitals Delta TLV[]    (field_id:1B + value:4B float32，仅推送变更字段)
```

**前端解码**：`decodeBinaryFrame(buf: ArrayBuffer)` → 返回与 JSON signal 帧兼容的 TypeScript 接口；vitals delta 通过 `mergeVitalsDelta()` 增量合并到上一帧完整 vitals，Store 无需感知帧格式。



### v2 物理管线架构（PIPELINE_VERSION=v2）

通过环境变量 `PIPELINE_VERSION=v2` 启用。替代上述旧引擎，使用 6 层物理管线：

```
Layer 1: CellModel (Mitchell-Schaeffer 离子通道)
  ↓ ActionPotential (Vm, h, Ca²⁺, vm_trace)
Layer 2: ConductionNetwork (4节点 SA→AV→His→Purkinje，每节点运行 CellModel)
  ↓ ConductionResult (激活时间, PR/QRS/QT, beat_kind)
Layer 3: EcgSynthesizer (AP→12导联 ECG，Dower 矩阵投影)
  ↓ EcgFrame (dict[lead → NDArray], 500Hz)
Layer 4: ExcitationContractionCouplerV2 (Hill 激活 + Frank-Starling + 损伤缩放)
  ↓ ContractionForce (force_curve, elastance_curve, 5000Hz)
Layer 5: HemodynamicEngineV2 (时变弹性 P-V 环 ODE + Windkessel 后负荷 + 物理瓣膜状态机)
  ↓ HemodynamicState (LV压力/容积, 瓣膜事件, BP/CO/EF/SV)
Layer 6: AcousticGeneratorV2 (瓣膜事件→M1/T1 + A2/P2 分裂 + S3/S4 奔马律 + 杂音)
  ↓ PcgFrame (NDArray, 4000Hz) + channels: dict[str, NDArray] (4 通道多位置输出: aortic/pulmonic/tricuspid/mitral)
```

**Phase 1B 新增闭环模块**：
- **AutonomicReflexController**：压力感受器反射（sigmoid firing rate → 交感/副交感张力），交感延迟 τ=2s，副交感延迟 τ=0.5s，circuit breaker 防止振荡
- **PharmacokineticsEngine**：一室 Bateman 方程药代动力学（beta_blocker, amiodarone, digoxin, atropine），支持地高辛-低钾交互
- **compute_modifiers()**：统一因素→Modifiers 映射（ANS 效应 + 药物映射 + 用户命令 + 损伤传递）
- **check_beat_invariants()**：8 项物理不变量校验（HR/SBP>DBP/EF/SV/CO/SpO2/RR/P-V 环面积），错误仅记录日志不阻断

**Phase 2 交互重构 + PCG 升级模块**：
- **InteractionState** (`modulation/interaction_state.py`)：纯数据类（~30 字段），保存用户意图（exercise_intensity, rhythm_override, potassium_level 等）。`apply_command()` 只写 InteractionState，不再直接写 Modifiers，消除了"每拍 copy-back 20 字段"反模式
- **TransitionSmoother** (`modulation/transition_engine.py`)：per-parameter 指数平滑引擎。每个参数有独立 tau_seconds（如 exercise=3s, rhythm=instant, electrolytes=5s），每拍调用 `update(intent, rr_sec)` 输出平滑后的 InteractionState
- **compute_modifiers(interaction=)** (`modulation/physiology_modulator.py`)：新增 `interaction` 关键字参数，接收 TransitionSmoother 输出，替代旧 `user_commands` dict 路径（旧路径仍保留向后兼容）
- **AcousticGeneratorV2 升级**：多模态合成（M1 3模态/T1 2模态/A2 3模态/P2 2模态/S3 2模态/S4 2模态）、RMS-based AGC（target=0.12, gain clamp [0.3, 3.0]）、5ms 余弦拍间 crossfade、PR-S1 耦合（短PR放大S1）、呼吸相位驱动 A2-P2 分裂
- **HR-adaptive valve debounce** (`mechanical/valve_model.py`)：`debounce_ms = max(40, min(200, rr_ms * 0.20))`，确保 HR>150bpm 时瓣膜仍能完成开合周期
- **Pipeline 数据流**：`apply_command() → self._intent → TransitionSmoother.update() → compute_modifiers(interaction=smoothed) → physics layers`

**接口隔离**：每层通过 Python `Protocol` 定义接口（`engine/core/protocols.py`），可独立替换实现。

**编排时序**：beat_loop 以 per-beat 频率运行，内部 Layer 1+2 的 ODE 积分在 5000Hz（dt=0.2ms）完成。stream_loop 以 10Hz（100ms）从缓冲区切片发送 WebSocket 帧。

**WebSocket 协议**：v2 管线发送 `stream_protocol: "sample-clock-v3"` init 帧，信号帧格式向下兼容 v2。

**引擎架构**：V3 参数化管线（`SimulationPipeline`），3 层架构：参数化传导 → ECG+PCG → 代数血流动力学。不再有版本切换或 legacy fallback。

### v2 管线数据流暴露现状

> 完整演进路线图见 [`docs/v2-engine-roadmap.md`](./v2-engine-roadmap.md)

v2 管线 `_run_one_beat()` 内部计算了丰富的层间数据。**P1 实现后**，以下数据已通过 `physiology_detail` 字段暴露给前端（每拍一次，LTTB 降采样至 ~200 点）：

```
Layer 1 CellModel
  ├── vm_trace[] (4 节点)         ──→ ✅ physiology_detail.action_potentials (LTTB ~200pt)
  ├── calcium_trace[] (4 节点)    ──→ ❌ 未推送（钙瞬变）
  └── apd_ms (4 节点)             ──→ ❌ 未推送（APD 测量值）

Layer 4 ExcitationContractionCoupler
  ├── peak_force                  ──→ ❌ 未推送
  ├── time_to_peak_ms             ──→ ❌ 未推送
  └── calcium_peak                ──→ ❌ 未推送

Layer 5 HemodynamicEngine
  ├── lv_pressure[]               ──→ ✅ physiology_detail.pv_loop.pressure (LTTB ~200pt)
  ├── lv_volume[]                 ──→ ✅ physiology_detail.pv_loop.volume (LTTB ~200pt)
  ├── aortic_pressure[]           ──→ ✅ physiology_detail.cardiac_cycle.aortic_pressure (LTTB ~200pt)
  └── valve_events[]              ──→ ❌ 未推送（瓣膜开合时序）

Modulation
  ├── baroreflex firing_rate      ──→ ❌ 仅内部使用
  ├── pharma _active_doses        ──→ ❌ 仅输出 level 标量
  └── invariant_violations[]      ──→ ❌ 仅 logger.warning()
```

**已实现的 signal 帧扩展**（P1）：每拍完成时 `physiology_detail` 子对象包含 LTTB 降采样数据（`lttb.py`，~200 点/曲线）：
- `pv_loop`: `{pressure: float[], volume: float[]}` — P-V 环
- `action_potentials`: `{sa: float[], av: float[], his: float[], purkinje: float[]}` — 4 节点 AP 轨迹
- `cardiac_cycle`: `{lv_pressure: float[], aortic_pressure: float[], lv_volume: float[]}` — Wiggers 图

非新拍帧中该字段为 `null`，避免带宽浪费。前端通过 3 个浮动面板组件（`PvLoopChart.vue`、`ActionPotentialChart.vue`、`CardiacCycleChart.vue`）实时渲染。

### v2 PCG 声学实现现状

> 完整 TODO 清单（15 项）见 [`docs/v2-engine-roadmap.md` P1-PCG 章节](./v2-engine-roadmap.md#p1-pcg--pcg-多位置听诊真实性提升)。PCG-1/2（多位置差异化输出）和 PCG-13（位置专属杂音）已实现。

**已解决**（P1-PCG 实现）：后端 `AcousticGeneratorV2` 现在基于**成分权重矩阵**生成 4 通道位置差异化 PCG。每个心音成分（S1_M1, S1_T1, S2_A2, S2_P2, S3, S4, murmur）按解剖学权重分配到 4 个听诊位置。

**V2 vs Legacy 声学特性对比**：

| 特性 | Legacy | V2 当前 | 备注 |
|------|:------:|:-------:|:----:|
| 多模态合成（3-5 频率模态） | ✅ | ✅ Phase 2 已实现 | M1/T1/A2/P2/S3/S4 各 2-3 阻尼正弦模态 |
| PR-S1 耦合 | ✅ | ✅ Phase 2 已实现 | 短 PR 放大 S1（factor 0.5-1.5） |
| 呼吸调制 A2-P2 分裂 | ✅ | ✅ Phase 2 已实现 | 呼吸相位驱动 A2-P2 间隔 10-60ms |
| 全局 AGC + crossfade | ✅ | ✅ Phase 2 已实现 | RMS AGC + 5ms 余弦拍间 crossfade |
| 4 层噪声模型 | ✅ | 部分 | 基础环境噪声已实现 |
| 听诊器滤波 | ✅ | 部分 | 前端 BiquadFilter 模拟 |
| **多位置差异化输出** | ❌ | ✅ PCG-1/2 已实现 | 4 通道解剖学加权 |
| **位置专属杂音** | ❌ | ✅ PCG-13 已实现 | 瓣膜狭窄位置差异化 |
| **胸壁传播物理模型** | ❌ | ✅ PCG-14 已实现 | 频率依赖衰减 + 指数距离衰减 + 时延 |

**已实现的 PcgFrame 结构**（`engine/core/types.py`）：
```python
@dataclass(frozen=True)
class PcgFrame:
    samples: NDArray[np.float64]                        # 默认混合 PCG（向后兼容）
    channels: dict[str, NDArray[np.float64]]            # 4 通道: aortic/pulmonic/tricuspid/mitral
```

**位置权重矩阵**（`engine/mechanical/acoustic_generator.py :: POSITION_WEIGHTS`）：
```python
POSITION_WEIGHTS = {
    "aortic":    {"S1_M1": 0.3, "S1_T1": 0.2, "S2_A2": 1.0, "S2_P2": 0.4, "S3": 0.2, "S4": 0.3, "murmur": 0.6},
    "pulmonic":  {"S1_M1": 0.2, "S1_T1": 0.3, "S2_A2": 0.4, "S2_P2": 1.0, "S3": 0.3, "S4": 0.2, "murmur": 0.4},
    "tricuspid": {"S1_M1": 0.4, "S1_T1": 1.0, "S2_A2": 0.3, "S2_P2": 0.3, "S3": 0.8, "S4": 0.7, "murmur": 0.5},
    "mitral":    {"S1_M1": 1.0, "S1_T1": 0.3, "S2_A2": 0.3, "S2_P2": 0.2, "S3": 1.0, "S4": 1.0, "murmur": 1.0},
}
```

**WebSocket 协议**：signal 帧中 `pcg_channels` 字段推送 4 通道 PCG 数据（`{aortic: float[], pulmonic: float[], tricuspid: float[], mitral: float[]}`）。前端 `PcgWaveform.vue` 监听 `auscultationMode`/`auscultationArea` 切换并通过 `registerPcgPositionCallback` 订阅对应通道。

### v2 命令覆盖现状

`SimulationPipeline.apply_command()` 处理全部 49 个命令（P0 已完成）：
- ✅ 运动（7）：rest / walk / jog / run / sprint / cycle / swim
- ✅ 药物（4）：beta_blocker / amiodarone / digoxin / atropine
- ✅ 参数（5）：set_damage_level / set_heart_rate / set_preload / set_contractility / set_tpr
- ✅ 情绪（7）：calm / stress / anxiety / panic / anger / joy / sadness
- ✅ 心脏病变（14）：pvc / svt / af / vt / vf / av_block_1 / av_block_2 / av_block_3 / asystole / mitral_regurgitation / aortic_stenosis / mitral_stenosis / aortic_regurgitation / normal_rhythm
- ✅ 紧急干预（2）：defibrillation / cardioversion
- ✅ 电解质（4）：hyperkalemia / hypokalemia / hypercalcemia / hypocalcemia
- ✅ 体内状态（7）：fever / hypothermia / caffeine / alcohol / dehydration / sleep_deprivation / fatigue
- ✅ 基底/设置（4）：reset / af_substrate / svt_substrate / vt_substrate

**P0 命令全部已实现**：情绪全部（7 个）✅、心脏病变全部（14 个）✅、紧急干预全部（2 个）✅、电解质全部（4 个）✅、体内状态全部（7 个）✅、运动全部 ✅、设置全部 ✅、药物全部 ✅、基底全部 ✅。

`Modifiers` dataclass 新增 23 个字段支持 P0 命令：rhythm_override, av_block_degree, hr_override, pvc_pattern, emotional_arousal, exercise_intensity, caffeine_level, alcohol_level, temperature, dehydration_level, sleep_debt, fatigue_level, potassium_level, calcium_level, murmur_type, murmur_severity, af_substrate, svt_substrate, vt_substrate, defibrillation_count 等。

详见 [`docs/v2-engine-roadmap.md` 附录](./v2-engine-roadmap.md#附录v2-命令覆盖现状对照表) 的完整对照表。

### ECG Gaussian 超位合成（v2 实现）
- `EcgSynthesizerV2._build_lead_ii()` 接收 `ConductionResult`，根据 `beat_kind` 分派到专门的形态生成器
- **Sinus/SVT/AF 形态**（`_build_sinus_morphology`）：
  - P 波：SA 激活时刻 + σ=40ms（主) + σ=30ms (尾)
  - QRS：His 激活时刻作为中心，Q(-0.10@-10ms) + R(1.20@+5ms) + S(-0.15@+20ms)，σ=4-5ms
  - T 波：Purkinje 复极后 110ms 开始，两个高斯分量 (σ=45/40ms, amp=0.25/0.10)
  - P 波仅在 `p_wave_present=True` 时绘制
- **VT 形态**（`_build_vt_morphology`）：
  - 无 P 波（心室起搏器驱动）
  - QRS 中心于 Purkinje 激活 + 40ms，宽怪异形态：σ=12-20ms，包含 R' 切迹
  - 倒置 T 波（与 QRS 极性相反）
- **PVC 形态**（`_build_pvc_morphology`）：
  - 可选 P 波（可能进行性）
  - QRS 中心于 Purkinje 激活 + 20ms，宽 σ=10-15ms
  - 倒置 T 波（继发性改变）
- **VF 形态**（`_build_vf_morphology`）：
  - 8 个随机频率正弦波 (2-8Hz)，随机相位和幅度
  - 包络调制 (waxing/waning)，整体幅度 0.6× 正常 R 峰
- **基线校正**：减去第 5 百分位数，确保零均值，防止 DC 漂移
- **幅度归一化**：峰值规范化后乘以 `_MV_SCALE (≈1.8mV R 峰值)`

---

### QT 间期联动与 PCG 耦合
- ConductionEvent 包含 `qt_interval_ms`，由 Bazett 公式 QT = 400ms × √RR 计算
- PCG S1 强度受 PR 间期调制：短 PR → S1 响亮（瓣膜全开），长 PR → S1 柔和（瓣膜半闭）
- PCG S2 位置融合 70% timeline 原始位置 + 30% QT 衍生位置

### QRS-S1 时间对齐与心率自适应收缩时间

**问题**：EC 耦合层生成的 elastance 曲线从采样点 0 开始上升（代表肌动蛋白激活），但电气上 QRS（心室除极）在 His/Purkinje 激活时刻（通常 100-150ms）才开始。结果：二尖瓣关闭（S1）发生在心拍开始，不在 QRS 后，违反生理学。

**解决方案**（Pipeline._align_elastance_to_qrs）：
1. 从 `ConductionResult` 获取 QRS 发起时刻：
   - Sinus/SVT/AF：His 激活时刻
   - VT/PVC：Purkinje 激活时刻（对VT额外+20ms防止心拍边界）
2. Elastance 曲线预填充（pad）diastolic 基线 E_MIN，延迟收缩上升至 QRS 时刻
   - 输入：`elastance_curve` 长度 N，总拍长 total_samples
   - 输出：`[E_MIN] × pad_samples + elastance_curve[:available] + [E_MIN] × tail_samples`
3. 心率自适应缩放：应用 Weissler 关系式调整左室射出时间（LVET）
   - 目标 LVET = max(100ms, -1.7 × HR + 413ms)
   - 72 bpm: 291ms；50 bpm: 328ms；180 bpm: 107ms
   - Elastance 曲线经线性插值重采样到目标时长，保留形状
4. 结果：S1 发生在 QRS 之后 ~10-30ms（生理正确），S1-S2 间期随 HR 自适应缩放

### Phase 6: VF/Asystole + 除颤/电复律
- **PhysioState 新字段**：
  - `_hr_override: float | None` — 临床场景（VF/Asystole）直接覆盖 HR 值，绕过正常 HR 计算
  - `defibrillation_count: int` — 累计除颤尝试次数，在 vitals 中推送给前端
- **VF/Asystole 传导类型** (`cardiac_conduction.py`)：VF 和 Asystole 作为新的 ConductionType，VF 时传导系统产生无序激活，Asystole 时无电活动
- **VF/Asystole 波形生成** (`signal_gen.py`)：VF → 多频混沌叠加 ECG + 无心音 PCG；Asystole → 平坦线 ECG + 静默 PCG
- **统一 HR 公式** (`HemodynamicCouplingRule`)：HR = f(exercise_intensity, emotional_arousal, temperature, dehydration, caffeine, potassium, drugs)，取代原 MedicationHemodynamicsRule 的独立 HR 修改
- **VtToVfDeteriorationRule**：VT 持续 >30 拍后按概率恶化为 VF
- **除颤** (`defibrillate`)：仅对 VF/VT 生效，~55% 基础成功率，成功后恢复窦性心律
- **同步电复律** (`cardiovert`)：对 AF/SVT/VT 生效，~80-92% 成功率

### SVT 高心率反卡顿优化

**问题**：SVT (180-200 bpm) 时，每拍 RR ~300-330ms，Python GIL 竞争导致异步事件循环偶发延迟（WebSocket 流传输不稳定）。

**解决方案**（Pipeline._beat_loop + _run_batch_beats）：
1. **批量心跳生成**：检测缓冲区状态，高心率时在单个 executor 调用中生成多拍
   - 低于 3 chunks：生成 3 拍（HR>120）或 2 拍（HR≤120）
   - 低于 8 chunks：生成 2 拍（HR>120）或 1 拍
   - 8-20 chunks：单拍生成
   - 超过 20 chunks：单拍生成，长睡眠
2. **条件跳过昂贵计算**：缓冲区低于 5 chunks 时跳过 physiology_detail 生成（LTTB 下采样 ~10ms 开销）
3. **改进自适应睡眠**：
   - 低缓冲时：1-5ms 快速醒醒
   - 中等缓冲：RR 的 30-50%（HR>120 时 30%，否则 50%）
   - 高缓冲：RR 的 90%
4. **结果**：缓冲区维持 5-20 chunks 稳定状态，WebSocket 推流无卡顿

- **药物** (4 种)：β-blocker (PR↑ HR↓)、Amiodarone (QT↑↑)、Digoxin (PR↑ 高剂量致 AVB)、Atropine (PR↓ HR↑)
- **电解质** (4 种)：高钾 (QRS↑ T 尖)、低钾 (异位灶↑)、高钙 (QT↓)、低钙 (QT↑)
- 状态动力学规则自动处理药物浓度衰减（指数衰减）和电解质缓慢回归基线
- 传导系统 `_apply_drug_effects()` 统一处理 QRS 增宽、QT 延长/缩短

### 血流动力学耦合规则
- **MedicationHemodynamicsRule**：（已移除，功能合并入 HemodynamicCouplingRule）
- **HemodynamicCouplingRule**：**统一 HR/BP/SpO2/RR 计算来源**。HR 由统一公式计算：HR = f(exercise_intensity, emotional_arousal, temperature, dehydration, caffeine, potassium, drugs)。同时处理以下联动：
  - 运动 → 收缩压升高（最大 +40mmHg）
  - 心动过缓（HR<55）→ 血压下降 + SpO2 下降
  - 心动过速（HR>130）→ 血压下降（舒张充盈不足）+ SpO2 下降
  - AF → SpO2 下降（心房失去泵功能）
  - VT → SpO2 显著下降
  - VF/Asystole → HR=0, BP=0, SpO2 急降
  - 心脏损伤 → SpO2 下降
  - 运动/高 HR → 呼吸频率上升
  - 酒精/脱水 → 血压下降

### HRV 自然波动（PhysioState.tick()）
- 指数平滑后对 HR、BP、SpO2、RR 叠加高斯微噪声，模拟真实生理信号的 beat-to-beat 变异性
- **心率**：HRV 振幅随副交感张力缩放，范围 ±0.5 bpm（高交感/运动）至 ±2.0 bpm（静息/高迷走），符合临床 HRV 频域特征
- **血压**：收缩压 ±0.8 mmHg、舒张压 ±0.5 mmHg 微波动（Mayer 波模拟）
- **SpO2**：±0.15% 微波动
- **呼吸频率**：±0.2 次/min 微波动

### 逐拍标注与趋势追踪
- `VirtualHuman._beat_loop` 收集每拍标注（PR/QRS/QT/beat_type/conducted），通过 signal frame 的 `beat_annotations` 字段推送给前端
- `_conduction_history`（300 拍环形缓冲）每 5 秒发送趋势摘要
- 前端 `ConductionTrendChart.vue` 绘制 PR/QRS/QT 折线图
- 前端 `SyncRuler.vue` 在 ECG-PCG 之间显示时序对齐信息

---

## 运行方式

### 启动后端
```bash
cd /qqvip/proj/BeatFlow/backend
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 3090 --reload
```

### 启动前端
```bash
cd /qqvip/proj/BeatFlow/frontend
pnpm dev
# 访问 http://localhost:3080
```

### API 文档
- Swagger UI：http://localhost:3090/docs
- OpenAPI JSON：http://localhost:3090/openapi.json

---

## 安全设计

1. **认证**：JWT Access Token（短期）+ Refresh Token（长期）
2. **授权**：RBAC，项目级别细粒度权限控制
3. **密码**：bcrypt 哈希存储
4. **API**：CORS 配置、Pydantic 输入校验、SQLAlchemy ORM 防 SQL 注入
5. **文件**：上传类型/大小校验

---

## 开发规范

### 新增 API 端点
1. 在 `schemas/` 中定义 Pydantic 请求/响应模型
2. 在 `endpoints/` 中实现路由函数
3. 在 `api/v1/__init__.py` 中注册 router（如新文件）
4. **更新 `docs/features.md` 中对应模块的接口列表**

### 新增数据库模型
1. 在 `models/project.py`（或新文件）中定义 SQLAlchemy 模型
2. **必须** 在 `models/__init__.py` 中导入
3. 在 `schemas/` 中定义对应的 Pydantic Schema
4. **更新 `docs/architecture.md` 的 Schema 部分**

### 新增前端页面
1. 在 `views/` 中创建 `.vue` 文件
2. 在 `router/index.ts` 中注册路由
3. 如需新的状态，在 `store/` 中创建 Pinia store
4. **更新 `docs/features.md` 的前端页面说明表**

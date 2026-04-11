# BeatFlow 功能文档

> **维护说明**：本文档须在每次功能性变更后同步更新。
> 最后更新：2026-03-27 (Phase 3+: 生理建模重构 — 呼吸系统/HRV/QT/双心室/冠脉/增强ANS)

---

## 目录
1. [功能模块总览](#功能模块总览)
2. [用户认证与授权](#用户认证与授权)
3. [项目管理](#项目管理)
4. [媒体文件管理](#媒体文件管理)
5. [波形标注](#波形标注)
6. [文件关联与同步播放](#文件关联与同步播放)
7. [临时分享](#临时分享)
8. [信号模拟生成](#信号模拟生成)
9. [社区平台](#社区平台)
10. [通知与收件箱](#通知与收件箱)
11. [系统管理后台](#系统管理后台)
12. [实时协作](#实时协作)
13. [虚拟人体模型](#虚拟人体模型)
14. [前端页面说明](#前端页面说明)

---

## 功能模块总览

| 模块 | 描述 | 状态 |
|------|------|------|
| 认证系统 | JWT 登录/注册/刷新/密码修改 | ✅ 已实现 |
| 项目管理 | 创建/编辑项目，成员权限管理 | ✅ 已实现 |
| 文件上传 | WAV/MP3/OGG/FLAC 音频（MP3 等自动转 WAV）、MP4/AVI/MOV 视频 | ✅ 已实现 |
| 波形查看 | Canvas 渲染波形，支持缩放 | ✅ 已实现 |
| 自动检测 | 4 种算法检测心音/心电事件 | ✅ 已实现 |
| BPM 分析 | BPM 统计 + 突变检测 + 自适应重探查 | ✅ 已实现 |
| 手动标注 | 点击/拖拽创建标记 | ✅ 已实现 |
| 文件关联 | ECG+PCG+Video 多轨同步播放 | ✅ 已实现 |
| 临时分享 | 生成过期时间可控的分享链接，支持下载限制与访问统计 | ✅ 已实现 |
| 信号模拟 | 生成合成 ECG/PCG 数据 | ✅ 已实现 |
| 虚拟人体 | 实时生理模型仿真 (WebSocket 流式 ECG/PCG + 交互 + 心音音频播放 + 听诊模式 + 降噪优化 + 多实例持久化 + 状态动力学 + PVC 调度器 + **心脏电生理传导模型** + **录制功能** + **活动状态可视化** + **动画平滑** + **信号平滑** + **12 导联 ECG** + **Phase 1B 血流动力学面板(CO/EF/SV)** + **预负荷/收缩力/TPR 控制** + **一屏深色布局(VitalsBar+ControlDrawer)** + **VT 宽 QRS 波形修复** + **短阵心律失常触发系统(PAF/PSVT/NSVT)** + **Phase 6: VF/Asystole + 除颤/电复律 + 统一 HR 公式** + **P1: 临床报警系统 + ECG 卡尺测量 + 节律条导出** + **P0: 49 条命令覆盖（运动/情感/病变/干预/电解质/基质）** + **P1: 临床可视化（P-V 环/AP 波形/Wiggers 图）** + **P1-PCG: 4 通道多位置听诊** + **Command Center V2 指挥中心式界面（左右分栏 + 脉冲侧栏 + 全屏 Overlay 控制面板 + 时间线轨道）** + **同步机制修复：clock-aligned sleep + simTime 实时更新 + Tab 恢复优化**) | ✅ 已实现 |
| 社区论坛 | 帖子/评论/点赞/标签 | ✅ 已实现 |
| 通知收件箱 | 项目邀请/系统公告通知，接受/拒绝邀请 | ✅ 已实现 |
| 系统管理后台 | 用户管理/文件管理/社区管理/统计/系统设置（仅 admin） | ✅ 已实现 |
| 实时协作 | WebSocket 多用户同步 | ✅ 已实现 |
| 云端存储 | 统一存储抽象（本地/COS/S3），运行时动态配置 | ✅ 已实现 |

---

## 用户认证与授权

### 功能描述
基于 JWT 的无状态认证系统，支持 Access Token + Refresh Token 双令牌机制。

### 接口列表
| 方法 | 路径 | 描述 |
|------|------|------|
| POST | `/api/v1/auth/register` | 用户注册 |
| POST | `/api/v1/auth/login` | 用户登录，返回 JWT |
| POST | `/api/v1/auth/refresh` | 刷新 Access Token |
| GET | `/api/v1/auth/me` | 获取当前用户信息 |
| POST | `/api/v1/auth/change-password` | 修改密码 |
| POST | `/api/v1/auth/forgot-password` | 发送密码重置邮件 |
| POST | `/api/v1/auth/reset-password` | 重置密码 |
| GET/PUT | `/api/v1/users/me` | 查看/更新个人资料 |

### 认证流程
```
用户登录 → POST /auth/login
  → 返回 { access_token, refresh_token, id, email, username, role, ... }
  → 前端存入 localStorage('token')
  → 后续请求带 Authorization: Bearer {access_token}
  → Token 过期 → 全局 401 拦截器自动触发 logout + Toast 提醒 + 跳转登录页
  → 登录页支持 ?redirect= 参数，登录后自动返回原页面
```

### 角色权限
| 角色 | 说明 |
|------|------|
| `admin` | 系统管理员，全局权限 |
| `user` | 普通用户，默认角色 |

### 项目内成员角色
| 角色 | 权限 |
|------|------|
| `owner` | 全部权限，可删除项目 |
| `admin` | 管理成员，上传/修改/删除文件 |
| `member` | 上传文件，创建标注 |
| `viewer` | 只读 |

---

## 项目管理

### 功能描述
项目是数据管理的核心容器，用于组织 ECG/PCG/Video 文件及其标注。

### 接口列表
| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/api/v1/projects/` | 获取我的项目列表 |
| POST | `/api/v1/projects/` | 创建项目 |
| GET | `/api/v1/projects/{id}` | 获取项目详情（含文件列表） |
| PUT | `/api/v1/projects/{id}` | 更新项目信息 |
| DELETE | `/api/v1/projects/{id}` | 删除项目（仅 owner） |
| GET | `/api/v1/projects/{id}/members` | 获取项目成员 |
| POST | `/api/v1/projects/{id}/members` | 通过 email 邀请成员（发送通知）或 user_id 直接添加 |
| PUT | `/api/v1/projects/{id}/members/{userId}` | 修改成员角色 |
| DELETE | `/api/v1/projects/{id}/members/{userId}` | 移除成员 |
| GET | `/api/v1/projects/{id}/files` | 获取项目文件列表（支持 `?q=` 文件名搜索、`?file_type=` 类型筛选） |
| POST | `/api/v1/projects/{id}/files/upload` | 上传文件到项目（MP3/OGG/FLAC 自动转 WAV） |

### 数据模型
```
Project {
  id: UUID
  owner_id: UUID
  name: string (max 100)
  description: string (max 500)
  is_public: boolean
  created_at, updated_at: datetime
}
```

---

## 媒体文件管理

### 功能描述
支持多种音视频格式的上传、存储和元数据提取，是标注和分析的基础。

### 支持格式
- **音频**：WAV（原生）、MP3/OGG/FLAC（上传时自动转换为 WAV）
- **不支持**：M4A/AAC/WMA（需用户手动转换后上传）
- **视频**：MP4、AVI、MOV

### 接口列表
| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/api/v1/files/{id}` | 获取文件元数据 |
| PATCH | `/api/v1/files/{id}` | 更新文件信息（如 file_type） |
| DELETE | `/api/v1/files/{id}` | 删除文件 |
| GET | `/api/v1/files/{id}/download` | 下载原始文件 |
| GET | `/api/v1/files/{id}/waveform` | 获取波形数据；支持 `?max_points=N&start_time=s&end_time=s` 区间采样，响应含 `region_start`/`region_end` 字段 |
| POST | `/api/v1/files/{id}/detect` | 运行自动检测算法 |
| POST | `/api/v1/files/{id}/analyze` | BPM 分析 + 突变检测 + 自适应重探查 |
| GET | `/api/v1/files/algorithms` | 获取可用检测算法列表 |

### 文件元数据字段
```
MediaFile {
  id, project_id: UUID
  filename, original_filename: string
  file_type: "audio" | "video" | "ecg" | "pcg" | "other"
  file_size: int (bytes)
  file_path: string          // 相对存储 key，如 "{project_id}/{filename}"
  storage_backend: "local" | "cos"  // 文件实际存储后端（上传时记录）
  duration: float (seconds)
  sample_rate: float (Hz)
  channels: int
  bit_depth: int
  width, height: int (video)
  frame_rate: float (video)
  file_metadata: JSON
}
```

### 存储后端
- 文件上传时根据系统设置（`SystemSetting.storage_type`）决定存到本地或 COS
- 每个文件记录 `storage_backend` 字段，读取/下载/删除时按该字段选择后端
- 切换全局存储配置后，旧文件仍可正常访问（per-file tracking）
- COS 文件通过后端代理流式传输（`StreamingResponse`），避免 presigned URL + Authorization header 冲突

### 信号处理流水线
```
上传文件
  → MP3/OGG/FLAC? → soundfile 读取 → PCM int16 WAV 写出（单声道、归一化）
  → 提取元数据 (duration, sample_rate, channels)
  → 自动重采样（ECG→500Hz，PCG→2000Hz）
  → 带通滤波
  → 存储处理后波形供前端渲染
```

### 自动检测算法
| 算法名 | 适用信号 | 说明 |
|--------|----------|------|
| `scipy` | ECG/PCG | scipy 信号处理（Pan-Tompkins / Hilbert 包络） |
| `neurokit2` | ECG/PCG | NeuroKit2 AI增强检测（DWT 波形细分） |
| `wfdb` | ECG | PhysioNet WFDB/XQRS 算法 |
| `auto` | ECG/PCG | 自动选择最佳算法（默认 neurokit2） |

### 可检测事件类型
`s1` / `s2`（心音）、`qrs`（QRS 复合波）、`p_wave`、`t_wave`、`q_wave`、`s_wave`、`murmur`（杂音）、`other`

### BPM 分析 (`POST /files/{id}/analyze`)
| 功能 | 说明 |
|------|------|
| BPM 统计 | 均值/中位数/最值/标准差 |
| 逐拍 BPM 序列 | `instant_bpm[]` + `bpm_times[]`，可绘趋势图 |
| 突变检测 | 相邻 RR 间期变化率 > 阈值（默认 20%）的位置 |
| 突变分类 | `acceleration`（加速）/ `deceleration`（减速） |
| 自适应重探查 | 对突变段自动用 neurokit2 高精度算法重新检测，判断 `false_positive` / `confirmed_anomaly` |
| 结果持久化 | 写入 `analysis_results` 表（`analysis_type="bpm"`） |

---

## 波形标注

### 功能描述
支持手动和自动两种方式在波形的指定时间区间上打标记。

### 接口列表
| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/api/v1/annotations/` | 获取标注列表（按 file_id 过滤） |
| POST | `/api/v1/annotations/` | 创建标注 |
| PUT | `/api/v1/annotations/{id}` | 更新标注 |
| DELETE | `/api/v1/annotations/{id}` | 删除标注 |

### 数据模型
```
Annotation {
  id, file_id, user_id: UUID
  annotation_type: "s1" | "s2" | "qrs" | "p_wave" | "t_wave" | "murmur" | "other"
  start_time: float (seconds)
  end_time: float (seconds)
  label: string (max 100)
  confidence: float (0~1，自动检测时填写)
  source: "manual" | "auto"
  annotation_metadata: JSON
}
```

---

## 文件关联与同步播放

### 功能描述
将同一项目内的 ECG、PCG、Video 文件关联在一起，支持时间偏移微调，实现多轨同步播放。

### 接口列表
| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/api/v1/associations/` | 获取项目的所有关联组 |
| POST | `/api/v1/associations/` | 创建关联 |
| GET | `/api/v1/associations/{id}` | 获取关联详情 |
| PUT | `/api/v1/associations/{id}` | 更新关联（如调整偏移） |
| DELETE | `/api/v1/associations/{id}` | 删除关联 |
| GET | `/api/v1/associations/{id}/sync-data` | 获取同步后的多轨波形数据 |

### 数据模型
```
FileAssociation {
  id, project_id, created_by: UUID
  name: string
  ecg_file_id: UUID | null
  pcg_file_id: UUID | null
  video_file_id: UUID | null
  pcg_offset: float   // PCG 相对 ECG 的时间偏移（秒）
  video_offset: float // Video 相对 ECG 的时间偏移（秒）
  notes: string
}
```

### 同步播放规则
- 以 ECG 时间线为基准（offset=0）
- PCG 和 Video 通过 offset 对齐
- **总时长计算**：`totalDuration = max(ecgDuration, pcgDuration + pcgOffset, videoDuration + videoOffset)`，确保 offset 导致的延长也被正确覆盖
- 前端 SyncViewerView 实现多轨同步滚动/播放
- **播放时动态加载波形 detail**：播放中主动检查 detail 覆盖范围，预取窗口会先按文件实际时长裁剪，避免短文件触发高频重复 `waveform` 请求
- **媒体下载支持 HTTP Range**：`/api/v1/files/{id}/download` 以及分享流接口会返回 `206 Partial Content` / `Accept-Ranges: bytes`，保证浏览器 seek 能读取目标时间段的数据
- **起播前先完成 seek**：恢复播放或点击主进度条后，前端会先等待 PCG/Video seek 到当前 `playPos` 对应位置，再调用 `.play()`，避免媒体先从旧位置短暂起播
- **播放位置漂移修正**：RAF 循环中周期性从 PCG audio `currentTime` 修正 `playPos`，阈值 0.15s，防止波形播放头与音频脱同步
- **播放结束显式停止**：进度条到达终点时，显式调用 `pcgAudio.pause()` 和 `videoDisplay.pause()`，防止音频在进度归零后继续播放
- **ECG/PCG 同步缩放**：ECG 和 PCG 波形轨道共享缩放级别和视口起点。滚轮缩放、拖拽平移、自动跟随播放头、重置视图均同步操作两个轨道
- 空格键播放/暂停快捷键

---

## 临时分享

### 功能描述
为文件和文件关联生成带过期时间的分享链接，支持下载次数限制和访问统计。无需认证即可通过分享链接访问文件。

### 接口列表

#### 文件分享
| 方法 | 路径 | 描述 | 认证 |
|------|------|------|------|
| POST | `/api/v1/files/{file_id}/share` | 创建文件分享 | 需要 |
| GET | `/api/v1/files/{file_id}/shares` | 列出文件的所有分享 | 需要 |
| DELETE | `/api/v1/file-shares/{share_id}` | 删除文件分享 | 需要 |
| GET | `/api/v1/share/file/{share_code}` | 访问文件分享 (获取元数据) | 无需 |
| GET | `/api/v1/share/file/{share_code}/download` | 下载共享文件 | 无需 |
| GET | `/api/v1/share/file/{share_code}/stream` | 流式播放共享文件 | 无需 |

#### 关联分享
| 方法 | 路径 | 描述 | 认证 |
|------|------|------|------|
| POST | `/api/v1/associations/{assoc_id}/share` | 创建关联分享 (同时分享所有关联文件) | 需要 |
| GET | `/api/v1/associations/{assoc_id}/shares` | 列出关联的所有分享 | 需要 |
| DELETE | `/api/v1/association-shares/{share_id}` | 删除关联分享 | 需要 |
| GET | `/api/v1/share/association/{share_code}` | 访问关联分享 (获取元数据) | 无需 |
| GET | `/api/v1/share/association/{share_code}/file/{type}/stream` | 流式播放关联中的单个文件 | 无需 |

### 数据模型

#### FileShare
```json
{
  "id": "uuid",
  "file_id": "uuid",
  "created_by": "uuid",
  "share_code": "AbC123def_GhI456",
  "share_code_hash": "sha256_hash",
  "expires_at": "2026-04-01T00:00:00Z",
  "is_code_required": true,
  "max_downloads": 10,
  "download_count": 3,
  "view_count": 15,
  "created_at": "2026-03-21T09:00:00Z",
  "last_accessed_at": "2026-03-21T10:30:00Z"
}
```

#### FileAssociationShare
同 FileShare 结构，但 `file_id` 替换为 `association_id`

### 创建分享查询参数

| 参数 | 类型 | 说明 | 默认值 |
|------|------|------|--------|
| `share_code` | string (6-20) | 自定义分享码 (可选) | 自动生成 |
| `expires_in_hours` | int | 有效期 (小时) | - |
| `expires_in_days` | int | 有效期 (天) | - |
| `expires_at_custom` | ISO 8601 | 自定义过期时间 | - |
| `is_code_required` | bool | 是否需要分享码访问 | true |
| `max_downloads` | int | 最大下载次数 (可选，null = 无限制) | null |

**优先级**: `expires_at_custom` > `expires_in_hours` > `expires_in_days` > 不设置(永不过期)

### 访问流程

1. **获取分享信息**：`GET /share/file/{share_code}` → 返回文件元数据和统计
2. **下载文件**：`GET /share/file/{share_code}/download` → 增加 `download_count` 和 `view_count`
3. **验证逻辑**：
   - 检查 `expires_at` (若设置)
   - 检查 `max_downloads` 是否已达上限
   - 支持对同一分享多次访问，每次都增加计数

### 分享 URL 格式

- 文件分享：`{BASE_URL}/share/file/{share_code}`
- 关联分享：`{BASE_URL}/share/association/{share_code}`

### 权限要求

| 操作 | 最低权限 |
|------|----------|
| 创建分享 | 项目成员 (member+) |
| 删除分享 | 创建者或项目管理员 (admin+) |
| 访问分享 | 无 (公开) |

---


### 功能描述
生成合成的 ECG/PCG 信号数据，用于算法测试和演示，可自动保存到指定项目。

### 接口
| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/api/v1/simulate/templates` | 获取预设模板列表（23 个） |
| POST | `/api/v1/simulate/generate` | 生成合成信号 |

### 模板系统
- **模板总数**：23 个（正常:6, 心律失常:11, 瓣膜病:6）
- **前端筛选**：分类 Tab（全部/正常/心律失常/瓣膜病）+ 文本搜索 + 折叠/展开
- **默认显示**：折叠时仅显示前 6 个模板，点击"展开全部"查看所有
- **已选提示**：折叠后 header 显示当前选中模板名称 badge

### 模板列表
| ID | 名称 | 分类 |
|----|------|------|
| `normal_adult` | 正常成人窦性心律 | normal |
| `elderly_resting` | 老年人静息心率 | normal |
| `anxiety_fever` | 焦虑/发热心率 | normal |
| `exercise_treadmill_moderate` | 平板运动试验（Bruce Stage 2） | normal |
| `exercise_treadmill_peak` | 平板运动试验（Bruce Stage 4） | normal |
| `exercise_cycle_peak` | 功率自行车运动试验（峰值负荷） | normal |
| `sinus_tachycardia` | 窦性心动过速 | arrhythmia |
| `sinus_bradycardia` | 窦性心动过缓 | arrhythmia |
| `sinus_arrhythmia` | 窦性心律不齐 | arrhythmia |
| `af` | 心房颤动 (AF) | arrhythmia |
| `pvc` | 室性早搏 (PVC) | arrhythmia |
| `frequent_pvc` | 频发室性早搏 (>30%) | arrhythmia |
| `svt` | 室上性心动过速 (SVT) | arrhythmia |
| `vt` | 室性心动过速 (VT) | arrhythmia |
| `ron_t_vt` | R-on-T → 室速 (VT) | arrhythmia |
| `ron_t_vf` | R-on-T → 室颤 (VF) | arrhythmia |
| `ron_t_random` | R-on-T（随机结局） | arrhythmia |
| `systolic_murmur` | 收缩期杂音（二尖瓣关闭不全） | valvular |
| `diastolic_murmur` | 舒张期杂音（主动脉瓣关闭不全） | valvular |
| `s3_gallop` | S3 奔马律（心力衰竭） | valvular |
| `s4_gallop` | S4 奔马律（高血压性心脏病） | valvular |
| `split_s2` | S2 分裂 | valvular |
| `combined_valvular` | 复合瓣膜病（收缩期杂音 + S3） | valvular |

### 支持的心律类型
`normal`（正常窦律 60-100bpm）、`tachycardia`（窦性心动过速 100-300bpm）、`bradycardia`（窦性心动过缓 30-60bpm）、`sinus_arrhythmia`（窦性心律不齐）、`af`（心房颤动）、`pvc`（室性早搏）、`svt`（室上性心动过速）、`vt`（室性心动过速）、`ron_t`（R-on-T → VT/VF）

> 窦性心律三分类遵循临床标准定义，心率范围互不重叠。切换心律类型时自动 clamp 心率到目标范围。

### R-on-T 现象模拟
| 特性 | 说明 |
|------|------|
| **生理学原理** | PVC 恰好落在 T 波"易损期"（QT 的 70-100%），触发折返性心律失常 |
| **信号结构** | `正常窦律 → R-on-T PVC → [概率] VT 或 VF → [概率] 窦律恢复` |
| **VT 触发概率** | `ron_t_vt_probability` 参数控制（0-1，默认 0.6） |
| **VF 比例** | `ron_t_vf_ratio` 参数控制（0=全 VT, 1=全 VF，默认 0.4） |
| **VT 形态** | 规则宽 QRS 快速节律（160-220bpm），50% 概率自行恢复窦律 |
| **VT PCG** | VT 段保留 S1/S2 心音（VT 仍有协调性心室收缩），但节律加快 |
| **VF 形态** | 3-10Hz 多频混沌叠加 + 幅度指数衰减（粗颤→细颤） |
| **VF PCG** | VF 段仅有低幅混沌噪声（5-50Hz），无离散 S1/S2（无协调性心室收缩） |
| **VT→VF 过渡** | VF 前可有 0.5-2s 短暂 VT 过渡段 |
| **事件标记** | 自动生成 `ron_t`（R-on-T PVC）、`vt`（室速段）、`vf`（室颤段）、`other`（窦律恢复）标记 |
| **预设模板** | R-on-T→VT、R-on-T→VF、R-on-T 随机结局 |

### ECG 合成引擎（v2 VCG 架构）
| 特性 | 说明 |
|------|------|
| **VCG 中间表示** | 构建 X/Y/Z 三正交分量（心脏电向量环），通过 Dower 逆变换矩阵投影到 12 标准导联 |
| **导联独立形态** | V1 呈 rS 形态（小 r+深 S），V2-V3 过渡 RS，V4-V6 呈 qRs（高 R+小 s），各导联 P/T 波极性独立 |
| **Gaussian 基函数** | 三分量均用高斯基函数叠加 P/QRS/T 波，避免伪影和尖锐脉冲 |
| **节奏感知形态** | beat_kind 驱动 VCG 形态选择：sinus (三分量 P-QRS-T) / VT (三分量宽异常QRS) / PVC / VF (三分量独立混沌) |
| **Einthoven 精确保证** | III = II - I 计算得出（非独立投影），相关系数 > 0.99 |
| **缺血导联特异性** | ST 改变同时作用 Y（→下壁）和 Z（→前壁 V1-V4）分量，自然产生区域性 ST 改变 |
| **电解质导联差异** | 高钾 T 波在三分量均变尖变窄；低钾 T 波在 Y/Z 变平 + U 波 |
| **QRS-S1 时间对齐** | elastance 曲线预填充，使 S1 (二尖瓣闭合) 在 QRS 发生后 10-30ms |
| **心率自适应收缩时间** | Weissler 关系式 LVET ≈ -1.7 × HR + 413ms |
| **P-on-T 融合** | 三分量各自维护 T 波溢出缓冲区，高心率时跨拍衔接 |
| **基线校正** | Y 分量减去第5百分位数确保零均值，X/Z 同步缩放 |
| **幅度归一化** | Y 分量峰值规范化到 _MV_SCALE (≈1.8mV)，X/Z 按比例缩放 |

### 请求参数
```json
{
  "project_id": "uuid",
  "ecg_rhythm": "normal",
  "heart_rate": 72,
  "heart_rate_std": 2,
  "noise_level": 0.01,
  "duration": 10,
  "generate_pcg": true,
  "pcg_abnormalities": [],
  "pcg_sample_rate": 8000,
  "stethoscope_mode": true,
  "auto_detect": true
}
```

---

## 社区平台

### 功能描述
用户可以分享分析结果、心音/心电案例，支持讨论和点赞。

### 接口列表
| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/api/v1/community/posts` | 获取帖子列表（支持 `?q=` 关键词搜索、`?tag=` 标签筛选、分页） |
| POST | `/api/v1/community/posts` | 创建帖子 |
| GET | `/api/v1/community/posts/{id}` | 获取帖子详情 |
| DELETE | `/api/v1/community/posts/{id}` | 删除帖子 |
| POST | `/api/v1/community/posts/{id}/like` | 点赞 |
| GET | `/api/v1/community/posts/{id}/comments` | 获取评论 |
| POST | `/api/v1/community/posts/{id}/comments` | 发表评论 |
| DELETE | `/api/v1/community/comments/{id}` | 删除评论 |

### 数据模型
```
CommunityPost {
  id, author_id: UUID
  title: string (max 200)
  content: string (max 5000)
  file_id: UUID | null   // 可选：关联一个 MediaFile 分享波形
  tags: string[]         // 如 ["ECG", "异常"]
  like_count, view_count: int
}
```

---

## 通知与收件箱

### 功能描述
基于通知模型的异步消息系统，支持项目邀请、系统公告等多类型通知，用户可在收件箱接受/拒绝邀请。

### 接口列表
| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/api/v1/notifications/` | 获取我的通知列表（分页，支持 `?unread_only=true`、`?notification_type=`）|
| GET | `/api/v1/notifications/unread-count` | 获取未读通知数量 |
| PATCH | `/api/v1/notifications/{id}/read` | 标记通知为已读 |
| PATCH | `/api/v1/notifications/read-all` | 全部标为已读 |
| POST | `/api/v1/notifications/{id}/accept` | 接受项目邀请（自动创建 ProjectMember）|
| POST | `/api/v1/notifications/{id}/reject` | 拒绝项目邀请 |
| DELETE | `/api/v1/notifications/{id}` | 删除通知 |

### 通知类型
| 类型 | 说明 |
|------|------|
| `project_invite` | 项目邀请，status 流转：pending → accepted/rejected |
| `system_announcement` | 管理员发送的系统公告，status=done |
| `community_interaction` | 社区互动（预留） |
| `analysis_complete` | 分析完成（预留） |

---

## 系统管理后台

### 功能描述
仅限 `admin` 角色或 `is_superuser=true` 的用户访问，提供全局用户/文件/社区管理能力。

### 接口列表
| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/api/v1/admin/stats` | 系统统计（用户/项目/文件/帖子数量，存储量）|
| GET | `/api/v1/admin/users` | 用户列表（分页+`?q=`搜索）|
| PATCH | `/api/v1/admin/users/{id}/toggle-active` | 激活/封禁用户账号 |
| PATCH | `/api/v1/admin/users/{id}/role` | 修改用户角色（admin/member）|
| GET | `/api/v1/admin/files` | 全局文件列表（分页+`?q=`搜索）|
| DELETE | `/api/v1/admin/files/batch` | 批量删除文件（含存储文件）|
| DELETE | `/api/v1/admin/files/{id}` | 强制删除文件（含存储文件）|
| GET | `/api/v1/admin/community/posts` | 全局帖子列表（分页）|
| DELETE | `/api/v1/admin/community/posts/{id}` | 删除帖子 |
| POST | `/api/v1/admin/announcements` | 发送系统公告（写入所有活跃用户通知）|
| GET | `/api/v1/admin/settings` | 获取所有系统设置（存储配置等）|
| PUT | `/api/v1/admin/settings` | 批量更新系统设置 |
| POST | `/api/v1/admin/settings/test-storage` | 测试存储连接（上传/下载/删除测试文件）|

---

## 实时协作

### 功能描述
通过 WebSocket 实现项目内多用户的实时状态同步。

### 接口
| 协议 | 路径 | 描述 |
|------|------|------|
| WebSocket | `/ws/collaboration/{project_id}` | 加入项目协作频道 |

### 消息类型
- 用户加入/离开通知
- 标注创建/更新/删除广播
- 文件上传通知
- 光标/播放位置同步

---

## 虚拟人体模型

### 功能描述
实时运行的虚拟人体生理模型引擎，通过 WebSocket 持续输出 ECG 和 PCG 信号，并支持交互式生理状态调节。支持多实例持久化（每用户可创建多个虚拟人档案）。

### 核心能力

> **v2 物理管线**（`PIPELINE_VERSION=v2`，**默认启用**，Phase 1A+1B 已完成）：
> - **Mitchell-Schaeffer 离子通道细胞模型**：替代状态机，2 变量 ODE + RK4 积分，动作电位/不应期从物理模型自然浮现
> - **物理驱动传导网络**：4 节点（SA→AV→His→Purkinje）各运行独立细胞模型实例，传导延迟/PVC/AV 阻滞由细胞参数控制
> - **AP 投影 ECG 合成**：从节点动作电位波形直接投影到体表 12 导联，满足 Einthoven 关系（I+III≈II, corr>0.95）
>
> **P0 命令覆盖**（Phase 1.2 已完成）：新增 49 条交互命令，覆盖：
> - 6 条运动命令（rest/walk/jog/run/climb_stairs/squat）
> - 5 条情感命令（startle/anxiety/relaxation/stress/fatigue）  
> - 12 条心脏病变命令（condition_normal/af/pvc/tachycardia/bradycardia/valve_disease/heart_failure/svt/vt/av_block_1/2/3）
> - 2 条紧急干预命令（defibrillate/cardiovert，具有概率性成功/失败逻辑）
> - 7 条体内状态命令（caffeine/alcohol/fever/sleep_deprivation/dehydration/hydrate/sleep）
> - 4 条药物命令（beta_blocker/amiodarone/digoxin/atropine）
> - 4 条电解质命令（hyperkalemia/hypokalemia/hypercalcemia/hypocalcemia）  
> - 3 条心律失常基质命令（set_af_substrate/set_svt_substrate/set_vt_substrate）
> - 6 条参数设置命令（set_damage_level/set_heart_rate/set_preload/set_contractility/set_tpr/set_pvc_pattern）
>
> **P1 临床可视化**（Phase 2.x 已完成）：通过实时浮动面板展示 3 层生理学数据：
> - **P-V 环**：心室压力-容积环，实时跟踪收缩/舒张周期  
> - **动作电位**：4 节点（SA/AV/His/Purkinje）堆叠 AP 波形，显示传导延迟  
> - **Wiggers 图**：心动周期压力曲线（LV/Ao）+ 容积曲线，临床标准显示  
>
> **P1-PCG 多位置听诊**（Phase 3.x 已完成）：4 通道解剖学加权 PCG 输出：
> - 主动脉位（Aortic）：A2 高，S1_M1 低  
> - 肺动脉位（Pulmonic）：P2 高，S1_M1 低  
> - 三尖位（Tricuspid）：S1_T1 高，S2_A2 低  
> - 二尖位（Mitral）：S1_M1 高，S3/S4 高，杂音最明显
> - **Layer 4 — ExcitationContractionCouplerV2**：Hill 激活模型（n=2）+ Frank-Starling 机制（preload → 力增 10-25%）+ 损伤缩放（E_max × contractility × (1-damage)）+ 钙离子调制
> - **Layer 5 — HemodynamicEngineV2**：时变弹性 P-V 环 ODE（E(t) × (V(t)-V0)），Windkessel 后负荷模型（C·dP_Ao/dt = Q_aortic - P_Ao/R），物理瓣膜状态机（压力判据开关），从实际曲线推导 SBP/DBP/MAP/SV/EF/CO，beat 间状态持久化，NaN/Inf 安全后备
> - **Layer 6 — AcousticGeneratorV2**：S1=M1(100Hz,80ms)+T1(55Hz,60ms) 从 mitral close 触发，S2=A2+P2（副交感调制 30-60ms 分裂），S3 奔马律（damage>0.3），S4 奔马律（damage>0.5），瓣膜狭窄杂音（valve_areas<1.0 → 带限噪声）
> - **AutonomicReflexController**：压力感受器反射（MAP → sigmoid firing → 交感/副交感），交感 τ=2s / 副交感 τ=0.5s 指数滤波，circuit breaker 防振荡
> - **PharmacokineticsEngine**：一室 Bateman 方程（4 种药物：beta_blocker, amiodarone, digoxin, atropine），地高辛-低钾交互（低 K → 有效浓度升高 30%/0.5mEq），可序列化
> - **PhysiologyModulator (compute_modifiers)**：ANS → HR/contractility/TPR 映射，药物效应（β阻→HR↓/contr↓，胺碘酮→HR↓/APD↑，地高辛→contr↑/HR↓，阿托品→HR↑），用户命令叠加，损伤传递
> - **InvariantValidator**：8 项 Level 0 物理不变量（HR范围/SBP>DBP/EF/SV/CO/SpO2/RR/P-V环面积），每拍检查，违反仅记录日志
> - **Pipeline 集成**：_ensure_layers() 根据 PIPELINE_LAYER_VERSION 实例化 v2 或 legacy 层，_run_one_beat() 后调用 autonomic.update()+pharma.step()+compute_modifiers()+check_invariants()，apply_command() 支持药物给药路由到 PK 引擎，snapshot 包含 autonomic+pharma+hemo 状态
> - **前端监护仪容器（MonitorShell）**：毛玻璃（Glassmorphism）风格全屏容器，统一 WaveformStrip 组件，RingBuffer 波形存储
> - **Layer 4-6 桥接适配器**：简化的兴奋-收缩耦合 + 血流动力学 + 声学模型，Phase 1B 将替换为完整 P-V 环
> - **新增前端 Store**：`useConnectionStore`（WS 生命周期）、`useWaveformStore`（通道配置 + 缓冲区）
> - **analysis/ 独立模块**：ECG/PCG 检测算法从 `files.py` 提取为可复用纯函数

**旧引擎能力（PIPELINE_VERSION=legacy，可选回退）**：
- **实时信号生成**：逐拍合成 ECG (500Hz) + PCG (4000Hz)，每 100ms 推送一帧
- **心脏电生理传导模型**：完整 SA node → AV node → His bundle → Purkinje fibers 四级传导系统，各节点具有固有自律性、绝对/相对不应期、传导延迟、自主神经调制；支持 SVT 折返（AVNRT）、PVC 逆行传导、AV 阻滞 (I/II/III 度)、逸搏节律；交感/阿托品充分缩短 AV/SA/His/Purkinje ARP 避免高心率下功能性 2:1 AV 传导阻滞
- **ECG P 波形态**：宽高斯参数（σ=38ms/28ms）生成平滑圆润 P 波，FWHM ~90ms，符合临床 80-120ms 时程
- **PCG 高信噪比**：S1/S2 基础幅度 0.60/0.40，噪声层降至 3-5% of S1，逐拍归一化到 0.85 峰值确保输出接近满量程
- **心音实时播放**：通过 AudioWorklet 将 PCG 信号上采样并低延迟播放，支持播放/静音切换和音量调节
- **PCG 降噪优化**：后端听诊器频响滤波（20-800Hz 带通 + 60-120Hz 共鸣增强）+ tanh 软限幅；前端可选降噪模式（50/60Hz 陷波 + 更陡带通）
- **听诊模式**：4 个经典心脏听诊区域（主动脉瓣/肺动脉瓣/三尖瓣/二尖瓣），SVG 胸廓示意图选择，区域专用滤波参数模拟真实听诊器听感，支持实时区域切换
- **平滑状态过渡**：所有生理参数使用指数平滑趋近目标值，无突变
- **HRV 自然波动**：指数平滑后叠加高斯微噪声——HR 波动幅度随副交感张力缩放（±0.5-2.0 bpm），BP 微波动（±0.8/0.5 mmHg），SpO2 微波动（±0.15%），RR 微波动（±0.2/min），模拟真实生理信号的 beat-to-beat 变异性
- **状态动力学引擎**：规则驱动的衍生状态自动更新（交感/副交感张力、异位灶易激惹性、血流动力学耦合等）
- **PVC 调度器**：临床合理的 PVC 时序（提前出现 + 代偿间歇），支持 isolated/bigeminy/trigeminy/couplets 模式
- **SVT 电生理模型**：AV 节折返心动过速（AVNRT），窄 QRS + 逆行 P 波 + 规则快速心律 150-220bpm
- **体内状态模拟**：咖啡因、酒精、发热、脱水、睡眠欠债等影响生理参数
- **涌现行为**：长时间高强度运动 + 高 irritability → PVC 频率激增 → 可能触发短阵室速 (NSVT)
- **录制功能**：实时录制 ECG + PCG 信号，编码为双路 16-bit PCM WAV，支持保存到项目、自动创建关联、自动检测
- **听诊模式录制**：开启听诊模式时，PCG 录制应用区域专用滤波（纯数学 Biquad IIR，无 AudioContext 依赖）
- **膜片效果**：录制中切换听诊区域时，自动插入 fade-out(200ms) → silence(100ms) → fade-in(200ms) 过渡效果
- **多实例持久化**：每用户可创建多个虚拟人档案，断开自动保存，重连恢复状态
- **活动状态可视化**：从后端 vitals 派生所有活动效果（运动/情绪/病变/药物/体内状态/电解质），ActiveEffectsBar 药丸条一览全局状态，Tab 自动高亮匹配当前生理状态的按钮，ControlPanel Tab 标签显示数字徽章，VitalsDashboard 新增电解质/药物浓度/心脏结构面板
- **动画平滑**：波形渲染使用中点二次贝塞尔曲线，消除阶梯感；QRS 尖峰保护（Y差>25%自动回退 lineTo 保持锐利）；渐进 drift 软校正（小偏差每 chunk 修正 20%，大偏差硬重置）；**帧锁定虚拟播放头**（draw 内每帧固定步长推进 + 2% 柔性修正，替代 performance.now 推算，消除峰值闪烁）；**非对称 Y 轴缩放**（扩展快 0.3 / 收缩慢 0.02，防止垂直抖动）
- **信号平滑选项**：前端可选高斯平滑滤波（off/low/high），低档 3 点核 [0.15,0.70,0.15]，高档 7 点核 [0.03,0.10,0.22,0.30,0.22,0.10,0.03]，有效减少噪声同时保留 QRS 形态
- **12 导联 ECG**：后端通过 VCG（心脏电向量）中间表示 + Dower 逆变换合成 12 标准导联，各导联具有独立生理形态（V1 rS→V6 qRs 过渡、V1 双相 P 波、aVR 倒置），满足 Einthoven 约束（III=II-I）；缺血/电解质异常在不同导联有差异化表现；前端导联选择器支持 5 种预设组合（Lead II / 肢体6导 / 胸前6导 / 标准12导 / 节律监测 II+V1+V5）+ 肢体/胸前分组全选 + 自适应 grid 布局（1/2/4 列）
- **临床报警系统**：5 项生命体征（HR/SBP/SpO2/RR/Temp）双级阈值（warning/critical）+ 3 种致命节律（VF/VT/Asystole）自动报警；Web Audio API 合成蜂鸣音（warning 440Hz / critical 880Hz 重复），无 AudioContext 时静默降级；报警横幅 + VitalsBar 闪烁动画 + 静音按钮
- **ECG 卡尺测量**：冻结当前波形 → 点击放置标记点（最多 3 对）→ 像素距离自动换算为毫秒间期和等效 BPM；彩色连线可视化
- **节律条导出**：一键截取当前 ECG canvas → 叠加患者生命体征和导联标注 header → PNG 下载
- **交互式控制**：运动/情绪/心脏病变/体内状态/直接参数调节，31 种内置交互
- **Phase 1B 血流动力学**：VitalsDashboard 新增折叠式血流动力学面板（心输出量 CO / 射血分数 EF / 每搏量 SV），颜色阈值实时预警；SettingsTab 新增预负荷(Preload)/收缩力(Contractility)/TPR(总外周阻力) 滑块；v2 pipeline 支持 `set_damage_level`/`set_heart_rate`/`set_preload`/`set_contractility`/`set_tpr`/`reset` 命令；InteractionRegistry 已注册 `set_preload`/`set_contractility`/`set_tpr`（hemodynamics 类别），PhysioState 持有 override 字段并在 vitals 中推送简化 Frank-Starling 模型计算的 CO/EF/SV
- **可扩展架构**：装饰器注册模式 + 规则引擎，新增交互/状态规则无需改动任何现有代码

### v2 引擎已知差距与演进路线图

> 详细 TODO 清单见 [`docs/v2-engine-roadmap.md`](./v2-engine-roadmap.md)

#### 🚨 P0 — v2 命令覆盖缺口（功能回退）

v2 `SimulationPipeline.apply_command()` 仅实现 12/48 个交互命令（25%），以下命令类别在 v2 中完全缺失：

| 命令类别 | 缺失命令 | 任务编号 |
|----------|----------|----------|
| 情绪 | calm/stress/anxiety/panic/startle/relaxation/fatigue | P0-1 |
| 心脏病变 | condition_normal/af/pvc/tachycardia/bradycardia/valve_disease/heart_failure/svt/vt/av_block_1~3/vf/asystole | P0-2 |
| 紧急干预 | defibrillate/cardiovert | P0-3 |
| 电解质 | hyperkalemia/hypokalemia/hypercalcemia/hypocalcemia | P0-4 |
| 体内状态 | caffeine/alcohol/fever/sleep_deprivation/dehydration/hydrate/sleep | P0-5 |
| 运动（部分） | sprint/climb_stairs/squat | P0-6 |
| 设置 | set_pvc_pattern/set_af_substrate/set_svt_substrate/set_vt_substrate | P0-7 |

#### 📊 P1 — 引擎已计算但前端未展示的高价值数据

| 数据 | 产出层 | 说明 | 任务编号 |
|------|--------|------|----------|
| P-V 环曲线 | Layer 5 HemodynamicEngineV2 | `lv_pressure[]` + `lv_volume[]` + `aortic_pressure[]` 数组未包含在 WebSocket signal 帧中 | P1-1/P1-2 |
| 细胞 AP 轨迹 | Layer 1 MitchellSchaefferCell | 4 节点各产生 `vm_trace[]` + `calcium_trace[]` + `apd_ms`，完全未推送 | P1-3/P1-4 |
| 瓣膜开合事件 | Layer 5 ValveStateMachine | `ValveEvent[]`（valve, action, at_sample, dp_dt, area_ratio）仅内部使用 | P1-5/P1-6 |
| 收缩力指标 | Layer 4 ExcitationContractionCouplerV2 | `peak_force` / `time_to_peak_ms` / `calcium_peak` 未推送 | P1-5 |

#### 🔊 P1-PCG — PCG 多位置听诊真实性提升（15 项，Phase 2 大幅推进）

后端 `AcousticGeneratorV2` 已基于**成分权重矩阵**生成 4 通道位置差异化 PCG。**Phase 2** 进一步升级声学引擎，补齐了多模态合成、PR-S1 耦合、呼吸 A2-P2 分裂、AGC+crossfade 等关键特性。

| 方向 | 关键项目 | 状态 |
|------|----------|------|
| 后端声学升级 | 多位置 PCG 生成 + 位置振幅权重矩阵 (PCG-1/2) | ✅ 已实现 |
| 后端声学升级 | 多模态合成 v3: M1/T1/A2/P2/S3/S4 各 2-3 阻尼正弦模态 (PCG-3) | ✅ Phase 2 已实现 |
| 后端声学升级 | PR-S1 耦合: 短 PR 放大 S1 factor 0.5-1.5 (PCG-4) | ✅ Phase 2 已实现 |
| 后端声学升级 | 呼吸调制 A2-P2 分裂: 呼吸相位驱动间隔 10-60ms (PCG-5) | ✅ Phase 2 已实现 |
| 后端声学升级 | RMS-based AGC + 5ms 余弦拍间 crossfade (PCG-8) | ✅ Phase 2 已实现 |
| 后端声学升级 | 4 层噪声模型 (PCG-6) / 听诊器滤波 (PCG-7) | 部分（基础噪声+前端BiquadFilter） |
| 类型与协议扩展 | PcgFrame 多通道扩展 + WebSocket 按位置推送 (PCG-9/10) | ✅ 已实现 |
| 前端适配 | Store 多位置命令 + 音频播放适配 + 简化客户端滤波 (PCG-11/12) | ✅ 已实现 |
| 高级声学建模 | 位置专属杂音 (PCG-13) | ✅ 已实现 |
| 高级声学建模 | 胸壁传播物理模型 (PCG-14) + 右心瓣膜音触发 + 单元测试 (PCG-15) | ✅ 已实现 |

**Phase 2 交互系统重构**（已完成）：
- **InteractionState**: 纯数据类（~30 字段）保存用户意图，`apply_command()` 只写 intent 不直接写 Modifiers
- **TransitionSmoother**: per-parameter 指数平滑（exercise tau=3s, rhythm=instant, electrolytes=5s），每拍平滑输出
- **HR-adaptive valve debounce**: `debounce_ms = max(40, min(200, rr_ms*0.20))`，HR>150bpm 瓣膜正常开合
- **Pipeline 数据流**: `apply_command() -> intent -> TransitionSmoother -> compute_modifiers(interaction=smoothed) -> physics`
- 消除了旧 "每拍 copy-back 20 字段" 反模式，快照包含 `intent_state` + `transition_state`

#### 📈 P2 — 现有展示增强

| 项目 | 说明 | 任务编号 |
|------|------|----------|
| 药代动力学曲线图 | 前端仅显示 `level` 进度条，无 Bateman 方程浓度-时间曲线 | P2-1 |
| 物理验证告警 | `InvariantViolation` 仅在服务器日志中，前端无感知 | P2-2 |
| conduction 细节 UI | Store 中 `sa_rate`/`av_refractory_ms`/`his_delay_ms`/`purkinje_delay_ms`/`svt_reentry_count`/`av_block_occurred` 未在 UI 渲染 | P2-3 |
| 自主神经反射弧可视化 | 仅展示 tone 值，无压力感受器→中枢→效应器全链条可视化 | P2-4 |
| S3/S4 奔马律指标 | 声学引擎生成了 S3/S4，未作为独立临床指标推送 | P2-5 |

#### 🔬 P3 — 生理模型升级（Phase 3+ 已完成）

| 方向 | 关键项目 | 状态 |
|------|----------|:------:|
| 呼吸系统 | 呼吸力学（正弦 ITP 周期 + 化学感受器驱动 RR）+ O₂-Hb 解离曲线 (Hill) + Henderson-Hasselbalch pH | ✅ 已实现 |
| 心电动态 | HRV 频域生成器（LF/HF 逆 FFT → RR 偏移 + RSA）+ QT 动态适应（Bazett + 一阶滞后 + 电解质/药物/缺血效应）| ✅ 已实现 |
| 血流动力学 | 双心室 ODE（LV+RV 弹性 P-V 环 + 系统/肺 Windkessel + ITP 调制）+ 四瓣膜（三尖瓣+肺动脉瓣）| ✅ 已实现 |
| 冠脉循环 | CPP=DBP-LVEDP + O₂供需比 + 缺血级联（sigmoid + 一阶滞后）+ 冠脉狭窄 | ✅ 已实现 |
| 自主神经 | 增强 ANS：PaCO₂/PaO₂/pH 三路化学感受器 + 体温调节 + 简化 RAAS（τ=60/120s）| ✅ 已实现 |
| 管线集成 | pipeline.py 编排呼吸/HRV/QT/冠脉模块 + ANS 新反馈 + 17 个新 vitals 字段 + 11 个新不变量 | ✅ 已实现 |
| 声学升级 | 胸壁传播物理模型（频率依赖低通 + 指数衰减 + 时延）+ 右心瓣膜音触发 | ✅ 已实现 |
| 前端面板 | Store 17 新字段 + VitalsBar 呼吸/右心/冠脉面板 + ConditionTab 缺血/肺高压/右心衰 + SettingsTab FiO₂/Mg²⁺ | ✅ 已实现 |

### 架构
- 后端引擎包：`backend/app/engine/`
  - `VirtualHuman` — 主控制器（asyncio beat_loop + stream_loop），支持快照恢复
  - `PhysioState` — 生理状态管理（target/current 双值 + tick 指数平滑 + HRV/BP/SpO2/RR 微波动 + snapshot 序列化）
  - `BeatByBeatGenerator` — 逐拍 ECG/PCG 信号生成器（复用 simulate.py 函数），**信号连续性优化 v2.1**：拍间余弦 crossfade（ECG 12ms / PCG 8ms）消除拍边界阶跃 + phase-coherent 多频正弦噪声替代逐拍独立白噪声 + 全局样本计数器驱动连续基线（呼吸漂移/电极漂移/肌电噪声跨拍无缝）+ PCG 全局 AGC（EMA 峰值跟踪替代逐拍硬归一化，保留拍间自然幅度差异）。PCG 心音合成 v3：多模态随机相位阻尼振荡（4-6 个频率模态，各自独立衰减率和相位）+ 带限噪声填充 + 急起缓落非对称包络 + S1/S2 子成分拆分（二尖瓣+三尖瓣、主动脉瓣+肺动脉瓣）+ 生理性 A2-P2 呼吸分裂 + 4 层真实感噪声 + 听诊器滤波 + 温和软限幅
  - `InteractionRegistry` — 可扩展交互注册表
  - `StateDynamicsEngine` — 状态动力学规则引擎（含 VtToVfDeteriorationRule、统一 HemodynamicCouplingRule）
  - `PvcScheduler` — PVC 调度器（coupling interval + 代偿间歇 + NSVT 触发）
  - `lead_synthesis` — 12 导联 ECG 合成模块（VCG 三分量中间表示 + Dower 逆变换投影，各导联独立形态）
- 数据模型：`VirtualHumanProfile` — 虚拟人档案（user_id, name, state_snapshot JSONB）
- WebSocket 端点：支持 profile_id 参数，有档案时加载快照/断开自动保存
- REST API：档案 CRUD 端点

### 接口列表
| 方法 | 路径 | 描述 |
|------|------|------|
| WS | `/api/v1/ws/virtual-human?token=&profile_id=` | 实时仿真 WebSocket |
| POST | `/api/v1/virtual-human/profiles` | 创建虚拟人档案 |
| GET | `/api/v1/virtual-human/profiles` | 列出当前用户所有档案 |
| GET | `/api/v1/virtual-human/profiles/{id}` | 获取单个档案详情 |
| PATCH | `/api/v1/virtual-human/profiles/{id}` | 修改档案名称/设置 |
| DELETE | `/api/v1/virtual-human/profiles/{id}` | 删除档案 |

### 运动生理模型（ExercisePhysiologyModel）

`backend/app/engine/exercise_physiology.py` — 替代固定运动 HR 公式，提供生理学精确的心率响应仿真。

| 特性 | 说明 |
|------|------|
| **Tanaka 最大心率公式** | HR_max = 208 − 0.7 × age（取代固定 220 − age），age 范围 10-100 岁 |
| **体能等级影响** | fitness_level ∈ [0,1]，高体能者在相同运动强度下 HR 上升幅度更小（乘以 1 − 0.3×fitness） |
| **心脏漂移（Cardiac Drift）** | 持续运动时 HR 随时间缓慢上升（每分钟约 +2-5 bpm），模拟脱水/体温升高导致的渐进增加 |
| **疲劳累积** | 高强度运动（intensity > 0.6）加速疲劳累积，疲劳升高额外推高 HR（+5-10 bpm） |
| **脱水效应** | 每 1% 体重减少（dehydration_level 单位）HR 额外 +7 bpm |
| **恢复动力学** | 运动停止后 HR 按指数衰减回落，τ ≈ 3s（浅运动）至 30s（剧烈运动后） |

**新增交互命令**：
| 命令 | 参数 | 说明 |
|------|------|------|
| `set_fitness` | `value: float [0,1]` | 设置体能水平（0=久坐，0.5=普通，1=运动员） |
| `set_age` | `value: int [10,100]` | 设置年龄（影响 HR_max 和 HR 储备范围） |

### 二进制 WebSocket 推流协议

`backend/app/engine/ws_binary_protocol.py` + `frontend/src/lib/wsBinaryProtocol.ts`

相较 JSON 帧约节省 **~75% 带宽**（2800 B → ~700 B/帧）。

**协议协商**：WS 连接 URL 追加 `?protocol=binary` 开启二进制模式；不传或传 `?protocol=json` 则保持原 JSON 格式（向后兼容）。

**帧格式**：
```
初始化帧（Init）：始终使用 JSON 格式推送（含 interactions 列表、采样率等配置）

信号帧（Signal）：二进制模式下使用以下结构
┌────────────────────────────────── 20 字节定长头 ──────────────────────────────────┐
│ magic(2B)=0xBF01 │ version(1B) │ flags(1B) │ seq(4B) │ ts_ms(8B) │ payload_len(4B) │
└──────────────────────────────────────────────────────────────────────────────────┘
┌──────────── 可变长 Payload ────────────────────────────────────────────────────────┐
│ ECG int16 × N_ecg  │ PCG int16 × N_pcg  │ Vitals Delta（仅变更字段，TLV 编码）      │
└──────────────────────────────────────────────────────────────────────────────────┘
```

| 技术要点 | 说明 |
|----------|------|
| **ECG/PCG 量化** | float32 信号 × 32767 → int16（±1.0 归一化空间），解码端除以 32767 还原 |
| **Vitals Delta 编码** | 只传输与上一帧相比发生变化的 vitals 字段，字段 ID(1B) + 值(4B float32)，无变化时仅 0 字节 |
| **向后兼容** | JSON 模式 init 帧格式不变；binary 模式 init 帧仍为 JSON，仅 signal 帧二进制化 |
| **前端解码** | `wsBinaryProtocol.ts` 提供 `decodeBinaryFrame(buf)` 函数，返回与 JSON 帧相同的 TypeScript 接口 |

### WebSocket 协议（更新）
| 方向 | 类型 | 内容 |
|------|------|------|
| Server→Client | `init` | 首帧：vitals、interactions 列表、采样率配置、profile 信息、available_leads、selected_leads（始终 JSON） |
| Server→Client | `signal` | 每 100ms：ecg[50]、pcg[400]、vitals 快照；多导联模式下追加 ecg_leads:{lead_name:[50],...}（JSON 模式）；`?protocol=binary` 时发送二进制帧（20B 头 + int16 ECG/PCG + Vitals Delta TLV） |
| Server→Client | `save_result` | 保存结果：`{success: bool}` |
| Client→Server | `command` | 交互命令：`{command, params}`；特殊命令 `set_leads` 设置活动导联 |
| Client→Server | `save` | 显式保存当前状态到 DB |

### 内置交互（48 种）
| 分类 | 交互 |
|------|------|
| 运动 | rest, walk, jog, run, climb_stairs, squat |
| 情绪 | startle, anxiety, relaxation, stress, fatigue |
| 心脏病变 | condition_normal, condition_af, condition_pvc, condition_tachycardia, condition_bradycardia, condition_valve_disease, condition_heart_failure, condition_svt, condition_vt, condition_av_block_1, condition_av_block_2, condition_av_block_3, condition_vf, condition_asystole |
| 紧急干预 | defibrillate, cardiovert |
| 药物 | beta_blocker, amiodarone, digoxin, atropine |
| 电解质 | hyperkalemia, hypokalemia, hypercalcemia, hypocalcemia |
| 体内状态 | caffeine, alcohol, fever, sleep_deprivation, dehydration, hydrate, sleep |
| 设置 | set_damage_level, set_heart_rate, set_pvc_pattern, reset |
| 血流动力学 | set_preload, set_contractility, set_tpr |
| 心律失常基质 | set_af_substrate, set_svt_substrate, set_vt_substrate |
| 运动生理 | set_fitness, set_age |

### 生理状态参数
| 参数 | 基线 | 范围 | 说明 |
|------|------|------|------|
| heart_rate, systolic_bp, diastolic_bp, spo2, temperature, respiratory_rate | 健康成人 | 各有生理范围 | 基础生命体征 |
| exercise_intensity, emotional_arousal, damage_level, murmur_severity | 0 | [0,1] | 活动/损伤指标 |
| fatigue_accumulated | 0 | [0,1] | 累积疲劳（运动积累、休息恢复） |
| caffeine_level | 0 | [0,1] | 咖啡因浓度代理（指数衰减） |
| alcohol_level | 0 | [0,1] | 酒精浓度代理 |
| dehydration_level | 0 | [0,1] | 脱水程度 |
| sleep_debt | 0 | [0,1] | 睡眠欠债 |
| beta_blocker_level | 0 | [0,1] | β-受体阻滞剂浓度（指数衰减 τ≈15s） |
| amiodarone_level | 0 | [0,1] | 胺碘酮浓度（指数衰减 τ≈30s） |
| digoxin_level | 0 | [0,1] | 地高辛浓度（指数衰减 τ≈20s） |
| atropine_level | 0 | [0,1] | 阿托品浓度（指数衰减 τ≈10s） |
| potassium_level | 4.0 | [3.0,7.0] | 血钾 mEq/L（正常 3.5-5.0） |
| calcium_level | 9.5 | [6.0,14.0] | 血钙 mg/dL（正常 8.5-10.5） |
| sympathetic_tone | 0.5 | [0,1] | 交感张力（自动计算） |
| parasympathetic_tone | 0.5 | [0,1] | 副交感张力（自动计算） |
| ectopic_irritability | 0 | [0,1] | 异位灶易激惹性（自动计算） |
| pvc_pattern | isolated | — | PVC 模式：isolated/bigeminy/trigeminy/couplets |
| af_substrate | 0 | [0,1] | 房颤基质（触发 PAF 的概率权重） |
| svt_substrate | 0 | [0,1] | SVT 基质（触发 PSVT 的概率权重） |
| vt_substrate | 0 | [0,1] | VT 基质（触发 NSVT 的概率权重） |
| arrhythmia_episode_type | "" | — | 当前发作类型："" / "paf" / "psvt" / "nsvt" |
| arrhythmia_episode_beats | 0 | — | 发作剩余拍数 |
| defibrillation_count | 0 | — | 累计除颤次数 |
| fitness_level | 0.5 | [0,1] | 体能水平（影响运动时 HR 响应斜率；高体能→同强度下 HR 更低） |
| age | 35 | [10,100] | 年龄（岁），用于 Tanaka 公式推算最大心率：HR_max = 208 − 0.7 × age） |
| pao2 | 95.0 | [30,120] | 动脉氧分压 (mmHg)，由 O₂-Hb 解离曲线物理模型计算 |
| paco2 | 40.0 | [20,80] | 动脉二氧化碳分压 (mmHg)，由呼吸模型计算 |
| ph | 7.40 | [6.8,7.8] | 动脉 pH，由 Henderson-Hasselbalch 方程计算 |
| fio2 | 0.21 | [0.21,1.0] | 吸入氧浓度 (21%=室内空气) |
| magnesium_level | 2.0 | [0.5,4.0] | 血清镁 (mg/dL，正常 1.7-2.2)，低镁→QT延长 |
| intrathoracic_pressure | -5.0 | [-20,30] | 胸腔内压 (mmHg)，呼吸周期正弦波动 |
| coronary_perfusion_pressure | 70.0 | [0,120] | 冠脉灌注压 CPP=DBP-LVEDP (mmHg) |
| ischemia_level | 0 | [0,1] | 心肌缺血程度，由冠脉供需比计算 |
| qt_adapted_ms | 0 | [280,700] | QT 动态适应值 (ms)，Bazett+一阶滞后+电解质/药物 |
| hrv_rr_offset_ms | 0 | [-100,100] | HRV 频域生成器逐拍 RR 偏移 (ms) |
| rv_ejection_fraction | 55.0 | [5,95] | 右心室射血分数 (%) |
| pa_systolic | 25.0 | [5,80] | 肺动脉收缩压 (mmHg) |
| pa_diastolic | 10.0 | [3,40] | 肺动脉舒张压 (mmHg) |
| pa_mean | 15.0 | [5,50] | 平均肺动脉压 (mmHg) |
| rv_stroke_volume | 70.0 | [10,200] | 右心室每搏量 (mL) |
| coronary_stenosis | 0 | [0,1] | 冠脉狭窄程度 (用户可调) |
| raas_activation | 0 | [0,1] | RAAS 激活程度（低MAP/低CO时缓慢激活） |

### 状态动力学规则
| 规则 | 逻辑 |
|------|------|
| ExerciseFatigueRule | 运动强度>0.3 时疲劳累积，休息时衰减 |
| AutonomicToneRule | 交感 = f(运动, 情绪, 咖啡因)；副交感 = f(休息, 睡眠) |
| EctopicIrritabilityRule | irritability = f(疲劳, 咖啡因, 损伤, 交感, 酒精, 缺觉, 脱水) |
| FeverRule | 发热 → HR 每升 1°C +10，脱水加速 |
| CaffeineDecayRule | 咖啡因指数衰减（τ=15s） |
| AlcoholRule | 酒精：抑制副交感、升 irritability、降 BP |
| DehydrationRule | 脱水 → HR↑ BP↓ |
| SleepDeprivationRule | 通过 irritability 间接影响心律失常 |
| NsvtTriggerRule | 高强度运动>120s + irritability>0.7 → PVC 模式升级为 couplets |
| MedicationHemodynamicsRule | （已移除，合并入 HemodynamicCouplingRule） |
| HemodynamicCouplingRule | **统一 HR/BP/SpO2/RR 计算来源**：HR = f(exercise_intensity, emotional_arousal, temperature, dehydration, caffeine, potassium, drugs)；运动→SBP↑；心动过缓→BP↓/SpO2↓；心动过速→BP↓/SpO2↓；AF→SpO2↓；VT→SpO2↓；VF/Asystole→HR=0, BP=0, SpO2 急降；damage→SpO2↓；运动/高HR→RR↑；酒精/脱水→BP↓ |
| ParoxysmalAfTriggerRule | af_substrate>0.2 且 rhythm==normal 且 cooldown==0 时按概率触发 PAF（30-300拍），caffeine ×1.5，alcohol ×2.0 |
| ParoxysmalSvtTriggerRule | svt_substrate>0.2 且 rhythm==normal 且 cooldown==0 时按概率触发 PSVT（20-200拍），caffeine ×2.0 |
| ParoxysmalVtTriggerRule | vt_substrate>0.3 且 rhythm==normal 且 cooldown==0 时按概率触发 NSVT（6-60拍），damage ×2.0，低K ×1.5 |
| VtToVfDeteriorationRule | VT 持续 >30 拍后可恶化为 VF（概率随持续时间递增） |
| EpisodeCooldownRule | 每 tick 递减 arrhythmia_episode_cooldown，episode 终止后 10-30s 冷却 |

### 前端组件
| 组件 | 说明 |
|------|------|
| `VirtualHumanView.vue` | 主页面（一屏布局：合并顶栏 + 波形全屏 + VitalsBar 底部薄条 + ControlDrawer 弹出抽屉） |
| `MonitorShell.vue` | 全屏深色监护仪容器（slot-based: topbar/waveforms/bottom），100vh 毛玻璃风格 |
| `VitalsBar.vue` | 底部常驻生命体征薄条（HR/BP/SpO2/Temp/RR/CO 单行 + 可展开详情面板：血流动力学/电生理/生理/电解质/药物/心脏结构）；报警集成（超阈值参数闪烁 critical-pulse/warning-pulse 动画） |
| `ControlDrawer.vue` | 底部弹出毛玻璃抽屉（Teleport + 遮罩 + slide-up 动画，包裹 ControlPanel） |
| `ProfileSelector.vue` | 档案选择器（列出/新建/删除虚拟人，演示模式，深色主题） |
| `CmdProfileSelector.vue` | V2 指挥中心档案选择器（卡片式布局，展示 HR/节律/SpO2 摘要体征，内联创建表单，响应式双列 grid，支持删除确认） |
| `EcgWaveform.vue` | Canvas 实时 ECG 滚动波形，内置 `cachedAnnotation` 缓存上次有效逐拍标注，防止 `store.beatAnnotations` 更新间隙 UI 闪烁；支持信号平滑级别选择（off/low/high）；卡尺模式叠加 overlay canvas（冻结+标记+间期测量） |
| `EcgLeadSelector.vue` | 12 导联选择器（逐导联 toggle + 全部 12 导快捷按钮，肢体导联绿色/胸导联蓝色高亮） |
| `EcgLeadStrip.vue` | 单导联 ECG 波形条（独立 useScrollingCanvas 实例，用于多导联 grid 布局） |
| `EcgMultiLeadDisplay.vue` | 多导联 ECG grid 显示（自适应列数：1/2/4 列，≥7导联时按临床 4×3 标准排列） |
| `PcgWaveform.vue` | Canvas 实时 PCG 滚动波形 + 音频播放控制（AudioWorklet），联动听诊模式显示区域标签和降噪状态 |
| `VitalsDashboard.vue` | 生命体征卡片（已废弃，逻辑移入 VitalsBar.vue；保留文件但不再导入） |
| `ControlPanel.vue` | 交互控制面板（运动/情绪/病变/体内状态/药物/听诊/设置 7 个 Tab + 活动效果数量徽章，Tab 状态存 store 切换不丢失，深色主题） |
| `ActiveEffectsBar.vue` | 活动效果药丸条（从 store.derivedActiveStates 读取，深色毛玻璃配色，点击导航对应 Tab，空时显示"正常基线"） |
| `AuscultationPanel.vue` | 听诊模式面板（SVG 胸廓示意图 + 4 听诊区域选择 + 降噪开关 + 临床提示，深色主题） |
| `RecordingPanel.vue` | 录制控制 Popover（顶栏触发按钮 + 弹出面板；集成 ProjectPicker 组件做项目选择，支持搜索与新建；开始/暂停/停止/取消 + 上传进度） |
| `BodyStateTab.vue` | 体内状态控制（咖啡因/酒精/发热/熬夜/脱水 + 剂量滑块 + 补水/睡觉恢复） |
| `SettingsTab.vue` | 直接参数控制（心脏损伤程度/目标心率/预负荷 Preload/收缩力 Contractility/TPR 总外周阻力/FiO₂ 吸入氧浓度/Mg²⁺ 血清镁 + 重置基线） |
| `ConditionTab.vue` | 心脏病变选择（含 VF/Asystole/心肌缺血/肺高压/右心衰）+ PVC 模式子选项（孤立/二联律/三联律/成对）+ 心律失常基质滑块（AF/SVT/VT）+ 发作状态指示 + 紧急干预面板（除颤/同步电复律按钮） |
| `ConnectionStatus.vue` | WebSocket 连接状态指示器 |
| `AlarmBanner.vue` | 报警横幅（顶部显示活动报警列表，critical 红色/warning 黄色闪烁动画，slide 过渡） |
| `ExerciseTab.vue` | 运动控制 Tab（运动强度按钮组 + **体能等级滑块(0-1)** + **年龄滑块(15-85)** + 实时 HR_max 预览） |

---

## 前端页面说明

### 路由表
| 路径 | 组件 | 认证 | 描述 |
|------|------|------|------|
| `/` | HomeView | 否 | 首页/仪表盘 |
| `/login` | LoginView | 否 | 用户登录 |
| `/register` | RegisterView | 否 | 用户注册 |
| `/projects` | ProjectListView | ✅ | 项目列表 |
| `/projects/:id` | ProjectDetailView | ✅ | 项目详情（文件/成员/设置） |
| `/files/:id` | FileViewerView | ✅ | 单文件波形查看与标注 |
| `/sync/:id` | SyncViewerView | ✅ | 多轨同步播放（关联组） |
| `/community` | CommunityView | ✅ | 社区论坛 |
| `/simulate` | SimulatorView | ✅ | 信号模拟生成器 |
| `/virtual-human-legacy` | VirtualHumanView | ✅ | 虚拟人体实时仿真（旧版上下堆叠布局） |
| `/virtual-human` | VirtualHumanV2View | ✅ | 虚拟人体 Command Center V2（左右分栏+响应式移动端布局） |
| `/inbox` | InboxView | ✅ | 收件箱（通知/邀请管理） |
| `/admin` | AdminView | ✅（admin） | 系统管理后台 |

### 全局组件
| 组件 | 路径 | 说明 |
|------|------|------|
| `AppLayout` | `components/layout/AppLayout.vue` | 主布局（侧边栏+顶栏+内容区） |
| `AppToast` | `components/ui/AppToast.vue` | 全局 Toast 通知（磨砂玻璃暗色质感，左侧彩色条+图标+进度条，支持 action 按钮；桌面端右上角、移动端底部弹出；多条堆叠） |
| `AppModal` | `components/ui/AppModal.vue` | 通用对话框，v-model 控制显示 |
| `BpmPanel` | `components/ui/BpmPanel.vue` | 心率数值显示面板 |
| `DetectionPanel` | `components/ui/DetectionPanel.vue` | 自动检测结果展示 |
| `ProjectPicker` | `components/ui/ProjectPicker.vue` | 项目选择器（基于 AppSelect，搜索+内联创建新项目，支持暗色模式） |
| `AppSelect` | `components/ui/AppSelect.vue` | 通用下拉选择器（毛玻璃风格，Teleport 挂载到 body，支持搜索、图标、badge、暗色模式、footer slot） |
| `AppCheckbox` | `components/ui/AppCheckbox.vue` | 自定义复选框（圆角方框 + SVG 勾选动画 + v-model 双向绑定，支持 label/disabled） |
| `AppSegment` | `components/ui/AppSegment.vue` | 分段选择器（互斥按钮组，支持 xs/sm/md 尺寸，block 撑满模式） |
| `AppMiniSelect` | `components/ui/AppMiniSelect.vue` | 紧凑原生 select 封装（统一样式 + xs/sm/md 尺寸 + numeric 模式自动转数字） |
| `AppDropdown` | `components/ui/AppDropdown.vue` | 通用下拉菜单（Teleport + nextZIndex 动态层级 + click-outside，trigger/default slot） |

### 项目相关组件
| 组件 | 说明 |
|------|------|
| `FileManager.vue` | 文件上传列表管理（含搜索和类型筛选） |
| `FileDetail.vue` | 文件元数据展示 + 下载 + 删除 |
| `MemberManager.vue` | 成员邀请/角色管理 |
| `AssociationManager.vue` | 文件关联配置 |
| `ProjectSettings.vue` | 项目设置（名称/描述/公开性） |

### Virtual Human V2 组件（Command Center 布局）
| 组件 | 路径 | 说明 |
|------|------|------|
| `CmdStatusBar` | `virtual-human-v2/CmdStatusBar.vue` | 极简顶部状态条，移动端精简（隐藏录制/卡尺/导出按钮） |
| `CmdWaveflowPanel` | `virtual-human-v2/CmdWaveflowPanel.vue` | 波形流容器，ECG/PCG 限高（var(--cmd-ecg-max-height) / var(--cmd-pcg-max-height)），多余空间给趋势图 |
| `CmdEcgWaveform` | `virtual-human-v2/CmdEcgWaveform.vue` | ECG Canvas（复用 useScrollingCanvas） |
| `CmdPcgWaveform` | `virtual-human-v2/CmdPcgWaveform.vue` | PCG Canvas + 音频控制 |
| `CmdVitalsSidebar` | `virtual-human-v2/CmdVitalsSidebar.vue` | 右侧生命体征卡片（桌面端 200px，移动端隐藏） |
| `CmdMobileVitals` | `virtual-human-v2/CmdMobileVitals.vue` | 移动端底部水平生命体征条 + 详情抽屉（替代 sidebar） |
| `CmdControlOverlay` | `virtual-human-v2/CmdControlOverlay.vue` | 控制面板：桌面居中 Overlay / 移动端底部 Sheet |
| `CmdWaveformToolbar` | `virtual-human-v2/CmdWaveformToolbar.vue` | 波形工具条，移动端隐藏趋势/PV/AP/Wiggers |
| `CmdTimelineTrack` | `virtual-human-v2/CmdTimelineTrack.vue` | 底部时间线（桌面端可见） |
| `CmdSyncIndicator` | `virtual-human-v2/CmdSyncIndicator.vue` | ECG-PCG 同步时序薄条 |
| `CmdProfileSelector` | `virtual-human-v2/CmdProfileSelector.vue` | 档案选择器（含搜索/创建/删除） |
| `cmd-tokens.css` | `virtual-human-v2/cmd-tokens.css` | 设计 Token（CSS 变量 + 移动端断点覆盖 + 工具类） |

**响应式策略**：`cmd-tokens.css` 中 `@media (max-width: 767px)` 覆盖 CSS 变量（sidebar=0, 波形限高缩小），`.cmd-desktop-only` / `.cmd-mobile-only` 工具类控制元素显隐。

### Composables
| Composable | 文件 | 职责 |
|------------|------|------|
| `installAuthInterceptor` | `composables/useAuthInterceptor.ts` | 全局 fetch 401 拦截：登录过期自动 logout + Toast 提醒 + 跳转登录页 |
| `useScrollingCanvas` | `composables/useScrollingCanvas.ts` | 实时滚动波形 Canvas 渲染（环形缓冲区 + requestAnimationFrame + `start_sample` 驱动的平滑播放时钟 + 帧锁定虚拟播放头 + 非对称 Y 轴缩放） |
| `useAudioPlayback` | `composables/useAudioPlayback.ts` | PCG 心音实时音频播放（4000Hz 上采样 + AudioWorklet/ScriptProcessor + `start_sample` 调度 + 队列限流 + 降噪模式 + 听诊区域滤波） |
| `useAuscultation` | `composables/useAuscultation.ts` | 听诊模式（4 区域定义 + 滤波参数 + 状态管理 + 区域切换回调） |
| `useVirtualHumanRecorder` | `composables/useVirtualHumanRecorder.ts` | 虚拟人体录制（ECG/PCG 双路缓冲 + 16-bit PCM WAV 编码 + 纯数学 Biquad 听诊滤波 + 膜片过渡效果） |
| `useAlarmSystem` | `composables/useAlarmSystem.ts` | 临床报警系统（evaluateAlarms 纯函数评估 5 项生命体征阈值 + 3 种致命节律，createAlarmAudio Web Audio API 蜂鸣合成 + 无 AudioContext 降级，useAlarmSystem 响应式 composable 自动监听 vitals 触发音频报警 + 静音支持） |
| `useEcgCaliper` | `composables/useEcgCaliper.ts` | ECG 卡尺测量工具（pixelToMs/msToRate 纯函数像素↔时间↔BPM 换算，冻结波形 + 标记点放置/拖拽 + 最多 3 对间期计算，彩色连线显示） |
| `useRhythmStripExport` | `composables/useRhythmStripExport.ts` | 节律条 PNG 导出（Canvas 截图 + 生命体征/导联/速度标头叠加 + Blob 下载） |

### Pinia Store
| Store | 文件 | 职责 |
|-------|------|------|
| `useAuthStore` | `store/auth.ts` | 认证状态（token、user、login/logout） |
| `useProjectStore` | `store/project.ts` | 项目和文件数据 |
| `useToastStore` | `store/toast.ts` | Toast 通知队列（success/error/warning/info），支持 action 按钮和 ToastOptions 配置 |
| `useNotificationStore` | `store/notification.ts` | 未读通知数量，fetchUnreadCount/markAllRead |
| `useVirtualHumanStore` | `store/virtualHuman.ts` | 虚拟人体 WebSocket 连接管理、实时 vitals（含药物/电解质/defibrillation_count 字段）、听诊模式状态（区域/降噪）、档案 CRUD、信号回调分发（多订阅者模式）、`derivedActiveStates` 派生活动效果、`activeCountByCategory` 分类计数、`controlPanelTab` 控制面板 Tab 状态、`alarmMuted` 报警静音、`caliperMode` 卡尺测量模式 |

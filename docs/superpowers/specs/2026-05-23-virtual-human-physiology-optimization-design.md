# Virtual Human 生理仿真优化设计

**日期**: 2026-05-23
**状态**: Draft
**目标场景**: 个人医学体验 — 观察各种状态下 ECG/PCG 变化，获取真实自然的心音

---

## 1. 当前架构评估

### 1.1 架构概览

BeatFlow 后端采用 **V3 参数化三层管线** 架构生成虚拟人数据：

| 层级 | 模块 | 方式 |
|------|------|------|
| Layer 1 | Parametric Conduction Network | 代数计算激活时序 + 概率性心律失常触发 |
| Layer 2a | ECG Synthesizer (VCG→Dower→12-lead) | VCG 中间表示 + 高斯基函数合成 |
| Layer 2b | Parametric PCG Synthesizer | 模态分解 + murmur 噪声整形 + AGC |
| Layer 3 | Algebraic Hemodynamics | 代数公式计算血压/心输出量/EF/SV |

跨领域模块：自主神经反射控制、药代动力学引擎、生理调制器（compute_modifiers）、HRV 生成器、QT 动态、冠状动脉模型、运动生理学、呼吸模型+气体交换、InteractionState + TransitionSmoother。

### 1.2 优势

- 分层清晰、职责明确、模块可独立替换
- 闭环反馈丰富（压力感受器、化学感受器、体温调节、RAAS）
- Intent-based 架构 + TransitionSmoother 实现平滑参数过渡
- 代数公式高效，适合实时 WebSocket 流式推流
- 支持 38 个用户命令覆盖常见干预场景

### 1.3 关键问题

| 维度 | 问题根因 |
|------|---------|
| **PCG 品质** | 模态分解使用纯阻尼正弦波，缺少真实心音的谐波复杂度和非线性特征；单频段 AGC 粗暴压缩动态范围；stethoscope 滤波器过于简化（仅 800Hz 低通） |
| **ECG 真实度** | VCG→Dower 变换使用固定的高斯基函数，缺少个体差异和病理形态变异（Brugada、Wellens、Delta 波等）；QRS 形态过于模板化 |
| **生理响应** | 变化是"开关式"的参数映射，缺少多系统级联效应。beta_blocker → 直接改 `sa_rate_modifier`，而非 β1阻断→HR↓→CO↓→反射性SVR↑→逐渐稳态 |
| **变化可见性** | 前端收到 42 字段 vitals 字典，但缺少"此变化由什么触发"的因果链信息 |

---

## 2. 总体优化路线

四阶段渐进式优化，优先提升用户体感最强的维度：

```
Phase 1: PCG 品质升级      Phase 2: ECG 形态增强      Phase 3: 生理级联响应     Phase 4: 因果可视化
    ↓                          ↓                          ↓                       ↓
物理建模合成                病理形态库                因果图引擎               因果追踪面板
多频段动态压缩              ST段动态演化              级联延迟链               前端可视化
胸腔传递函数                个体变异性                 多系统协同
```

**原则**：
- 保持现有三层架构不变，每阶段仅改动目标模块
- 向后兼容 — 现有 API、WebSocket 协议、前端组件不受破坏
- 每阶段独立可交付、可测试

---

## 3. Phase 1: PCG 心音品质升级

### 3.1 激励-谐振物理模型

**现状**: `_add_modal_burst()` 使用固定频率/阻尼的正弦波叠加（3 个 mode × S1/S2），声音过于"干净"，缺乏真实心音的瞬态响应和非线性谐波。

**改动**: 新增 `PhysicalPcgSynthesizer` 类（保留 `ParametricPcgSynthesizer` 作为 fallback）：

- **激励信号**: 短时冲击脉冲，模拟瓣膜关闭瞬间的压力梯度变化，幅度由 contractility × (1 - damage) 决定
- **谐振体**: 多段级联的二阶 IIR 谐振器，模拟心室壁、血管壁、胸腔的复合频率响应
  - S1: 4-6 个谐振器，中心频率 30-180 Hz
  - S2: 3-5 个谐振器，中心频率 60-250 Hz
  - 每个谐振器的 Q 值和中心频率可被 damage/contractility 调制
- **非线性饱和**: 添加 soft-clipping 模拟组织的非线性声学响应

### 3.2 多频段动态压缩

**现状**: 单频段 AGC（target RMS=0.08, gain clamp=0.3-3.0），心音和 murmur 共享同一增益，murmur 强时心音被整体压低。

**改动**: 替换为 4 频段 WDRC（Wide Dynamic Range Compression）：

| 频段 | 范围 | 用途 |
|------|------|------|
| Band 1 | 20-100 Hz | S3/S4 低频心音 |
| Band 2 | 100-250 Hz | S1/S2 主体 |
| Band 3 | 250-500 Hz | 高频心音 + murmur |
| Band 4 | 500-800 Hz | 呼吸音 + 摩擦音 |

每频段独立压缩（threshold/ratio/attack=5ms/release=50ms 可配），保留心音自然动态的同时防止 murmur 掩盖。

### 3.3 胸腔传递函数

**现状**: 4 个听诊位置共享相同的 stethoscope 低通滤波（800Hz），通过简单加权区分位置。

**改动**: 为 4 个听诊位置（aortic/pulmonic/tricuspid/mitral）分别应用不同的 FIR 滤波器：

- **Aortic (右第二肋间)**: 高频衰减较少，S2 的 A2 成分最强
- **Pulmonic (左第二肋间)**: 类似 aortic 但 S2 的 P2 成分更强，A2-P2 分裂更清晰
- **Tricuspid (左第四肋间)**: 中低频为主，S1 的 T1 成分最明显
- **Mitral (心尖)**: S1 最强，S2 最弱，适合听 S3/S4 和 mitral murmur

### 3.4 呼吸调制增强

**现状**: 仅在噪声层添加了呼吸调制（`resp_env = 1.0 + 0.3 * sin(respiratory_phase + ...)`）。

**改动**:
- **S2 分裂**: 吸气时 A2-P2 分裂增宽（静脉回流↑ → 右室射血延长 → P2 延迟），分裂从 20ms 增加到 50ms+
- **心音幅度**: 吸气时心音幅度降低 5-10%（肺充气 → 心脏与胸壁距离增加）
- **S3/S4 幅度**: 呼吸变异 ±15%

### 3.5 文件变更

| 文件 | 操作 | 说明 |
|------|------|------|
| `backend/app/engine/core/physical_pcg.py` | 新增 | PhysicalPcgSynthesizer 类 |
| `backend/app/engine/core/acoustic_resonator.py` | 新增 | 级联 IIR 谐振器 + 非线性饱和 |
| `backend/app/engine/core/band_compressor.py` | 新增 | 4 频段 WDRC |
| `backend/app/engine/core/chest_transfer.py` | 新增 | 胸腔传递函数 FIR 滤波器组 |
| `backend/app/engine/simulation/pipeline.py` | 修改 | 添加 PCG 引擎切换逻辑（physical vs parametric） |
| `docs/features.md` | 修改 | 更新 PCG 合成模块说明 |

---

## 4. Phase 2: ECG 波形形态增强

### 4.1 病理形态库

**现状**: VCG 合成使用固定的高斯基函数（P/QRS/T 各一组 sigma/amplitude），缺少病理特征。

**改动**: 新增 `PathologicalMorphConfig` 数据类和 `MorphLibrary` 形态库：

```python
@dataclass
class PathologicalMorphConfig:
    name: str                              # "lbbb" / "brugada_type1" / "wellens"
    p_wave: PConfig | None
    qrs: QRSConfig                         # 含不同分量的参数数组
    st_segment: STConfig | None
    t_wave: TConfig | None
    applicable_leads: list[str] | None     # 限定导联
    severity_modulation: dict[str, float]  # 严重程度映射
```

覆盖的病理形态：

| 形态 | 关键 VCG 改动 | 特征 ECG 表现 |
|------|-------------|-------------|
| LBBB | X 分量 QRS 增宽至 120-160ms | V1 深 S、V6 宽 R 切迹 |
| RBBB | QRS 终末部增宽 | V1 rSR'、I/aVL 宽 S |
| WPW | QRS 起始 delta 分量 | PR 短 + delta 波 + QRS 宽 |
| Brugada Type 1/2 | Z 分量穹窿型 ST 抬高 | V1-V3 ST 抬高 |
| Wellens | V2-V3 T 波双相/深倒 | LAD 临界狭窄特征 |
| 高钾血症 | T 波窄高尖 + P 波低平 + QRS 增宽 | 帐篷 T 波 |
| 低钾血症 | T 波低平 + U 波显著 + ST 压低 | 显著 U 波 |
| 心梗演化 | ST/T/Q 随时间阶段变化 | 见 4.2 |

### 4.2 ST 段动态演化模型

**现状**: ischemia 通过固定 ST 压低高斯实现，不随时间演变。

**改动**: 新增 `STEvolutionModel` 类，跟踪 ST 段从超急性期到陈旧期的完整演进：

| 阶段 | 时间 | ST 段 | T 波 | Q 波 |
|------|------|-------|------|------|
| 超急性期 | 0-30 min | 无明显变化 | 高尖对称 | 无 |
| 急性期 | 30 min-6 h | ST 抬高 ≥1mm | 开始倒置 | 无或浅 |
| 亚急性期 | 6 h-72 h | ST 回落 | 深倒置 | 出现 Q 波 |
| 陈旧期 | >72 h | ST 回到基线 | 可永久倒置 | 病理性 Q 波 |

演化速度由 `coronary_stenosis` 控制，狭窄越重演进越快。可在前端实时观察 STEMI 的时间进程。

### 4.3 个体变异性

**现状**: 所有虚拟人 ECG 形态完全一致。

**改动**: 新增 `MorphVarianceConfig` 在初始化时随机生成个体参数（可存储到 profile）：

| 参数 | 随机范围 | 影响 |
|------|---------|------|
| 心脏电轴 | -30° ~ +90° (正态 μ=45° σ=25°) | 旋转 VCG → Dower 之间的向量 |
| 胸壁厚度 | 0.7 ~ 1.5 | 所有导联振幅缩放 |
| 心脏转位 | 顺钟向/正常/逆钟向 | Z 分量偏移，影响胸前导联 R 波过渡 |
| 年龄 | 18-80 | R 波幅度↓、T 波幅度↓、QRS 电轴左偏 |
| 性别 | M/F | QRS 振幅差异（男性略高） |

### 4.4 12 导联约束

**现状**: Dower 矩阵保证 `III = II - I`，但缺少胸前导联的递增约束。

**改动**: 在 `EcgSynthesizerV2.synthesize()` 末尾添加约束检查：
- V1-V6 的 R/S 比单调递增验证（钟向转位除外）
- aVR 负性 QRS 约束（正常时 aVR 主波必须为负）
- 违反约束时输出 warning log，并自动微调相关 VCG 分量

### 4.5 文件变更

| 文件 | 操作 | 说明 |
|------|------|------|
| `backend/app/engine/core/ecg_morph_library.py` | 新增 | MorphLibrary + PathologicalMorphConfig |
| `backend/app/engine/core/st_evolution.py` | 新增 | STEvolutionModel |
| `backend/app/engine/core/morph_variance.py` | 新增 | MorphVarianceConfig 个体变异 |
| `backend/app/engine/core/ecg_synthesizer.py` | 修改 | 集成形态库和 ST 演化 |
| `backend/app/engine/simulation/pipeline.py` | 修改 | 初始化个体变异参数，传递给 ECG 合成器 |
| `docs/features.md` | 修改 | 更新 ECG 合成模块说明 |

---

## 5. Phase 3: 生理级联响应

### 5.1 事件驱动生理因果图

**现状**: `compute_modifiers()` 将 autonomic + pharma + interaction → 直接映射到 modifiers，缺失中间级联。

**改动**: 重构为 `PhysiologyCausalGraph`，将有向图建模生理系统间的因果关系：

```
干预层 (InteractionState)
    ↓
一级效应层 (Primary Effects)
    β1阻断 → HR↓, 收缩力↓
    运动 → 骨骼肌泵↑, 代谢需求↑
    ↓
二级代偿层 (Compensatory Reflexes)
    压力感受器 → MAP↓ → 交感↑ 副交感↓
    化学感受器 → PaO2↓ → 呼吸驱动↑
    RAAS → 低灌注 → ATII↑ → SVR↑
    ↓
三级效应层 (Integrated Physiology)
    HR, SV, SVR, 呼吸 → CO, BP, SpO2
    ↓ feedback
→ 回到一级效应层（闭环）
```

核心数据结构：

```python
class CausalNode:
    name: str
    inputs: list[str]
    outputs: list[str]
    transfer_fn: Callable
    delay_ms: float
    time_constant_ms: float

class PhysiologyCausalGraph:
    nodes: list[CausalNode]
    state: dict[str, float]
    
    def step(self, dt_ms: float) -> dict[str, float]: ...
```

### 5.2 级联延迟链

真实的生理响应时间尺度差异巨大，需要精细化建模：

| 通路 | 延迟 | 时间常数 τ |
|------|------|-----------|
| 压力感受器反射 | 1-2 beats | 2-5s |
| 化学感受器 | 5-10s | 20-60s |
| RAAS | 15-30 min | 数小时 |
| 药物 IV 起效 | 1-5 min | 随药物 |
| 药物口服起效 | 30-90 min | 随药物 |
| 运动 HR 响应 | ~1s | 30s 达稳态 |
| 运动 HR 恢复 | 立即 | 快相 30s + 慢相数分钟 |
| 体温调节 | 数分钟 | 数十分钟 |
| 电解质平衡 | 数小时 | 数天 |

### 5.3 多系统协同响应场景

**运动协同**: 运动强度↑ 时同时触发：
- 心血管: HR↑ + 收缩力↑ + 骨骼肌血管扩张 + 内脏血管收缩
- 呼吸: RR↑ + Vt↑ + 支气管扩张
- 代谢: O₂消耗↑ + CO₂产生↑ + 乳酸堆积（> 无氧阈）
- 体温: 产热↑ → 皮肤血管扩张 → 散热↑

**新增场景 — 低血容量**:
- 静脉回流↓ → SV↓ → CO↓ → BP↓
- 代偿: 压力反射 → HR↑ + SVR↑（除心/脑外血管收缩）
- 激素: RAAS↑ + 肾上腺素↑
- 体征: 皮肤苍白湿冷

**新增场景 — 脓毒症**:
- 早期（暖休克）: SVR↓ → CO↑（代偿） → 宽脉压
- 晚期（冷休克）: 心肌抑制 → CO↓ → 乳酸↑ → 器官低灌注

### 5.4 慢性适应与稳态漂移

当前模型倾向于回到固定基线，缺少长期适应：

- **慢性高血压**: 长期高 SVR → 心肌肥厚 → 舒张功能↓ → 左房压↑
- **药物耐受**: 持续 beta_blocker → 受体上调 → 药效逐渐减弱
- **去适应**: 长期卧床 → 压力反射敏感度↓、立位耐力↓

实现：为持续存在的状态添加慢速适应变量（τ = 数小时-数天），逐步漂移基线。

### 5.5 文件变更

| 文件 | 操作 | 说明 |
|------|------|------|
| `backend/app/engine/core/causal_graph.py` | 新增 | PhysiologyCausalGraph + CausalNode |
| `backend/app/engine/modulation/physiology_modulator.py` | 重写 | 从直接映射改为图遍历计算 |
| `backend/app/engine/modulation/hemorrhage_model.py` | 新增 | 低血容量场景 |
| `backend/app/engine/modulation/sepsis_model.py` | 新增 | 脓毒症场景 |
| `backend/app/engine/modulation/chronic_adaptation.py` | 新增 | 慢性适应/药物耐受 |
| `backend/app/engine/simulation/pipeline.py` | 修改 | 替换 compute_modifiers 调用 |
| `docs/features.md` | 修改 | 更新生理调制说明 |

---

## 6. Phase 4: 因果追踪可视化

### 6.1 因果事件数据结构

每个状态变更记录为 `CausalEvent`：

```python
@dataclass
class CausalEvent:
    id: str
    timestamp_ms: float
    source: str                  # "command" / "exercise_model" / "baroreceptor" / …
    source_detail: str           # "jog" / "beta_blocker_1.0"
    target: str                  # "heart_rate" / "sa_rate_modifier"
    target_path: str             # "vitals.heart_rate" / "modifiers.sa_rate_modifier"
    old_value: float | str | None
    new_value: float | str
    delta: float | None
    mechanism: str               # 人类可读的机制描述
    confidence: float            # 0-1
    parent_event_id: str | None  # 上游事件 ID
```

### 6.2 事件来源层级

| 层级 | source | 示例 |
|------|--------|------|
| L1 用户指令 | `command` | 慢跑、给药、情绪 |
| L2 直接生理效应 | `exercise_model`, `pharmacokinetics`, `electrolyte` | HR↑、药物浓度 |
| L3 反射性代偿 | `baroreceptor`, `chemoreceptor`, `raas` | 交感激活 |
| L4 系统整合 | `hemodynamics`, `respiratory`, `coronary` | CO、BP |
| L5 信号形态 | `ecg_morphology`, `pcg_acoustics` | ST 演变 |

### 6.3 后端改动

在 `pipeline.py` 中维护 `_causal_buffer: deque[CausalEvent]`（maxlen=100），每次推送帧时附带最近 20 个事件：

```python
message["causal_events"] = [
    {"id": e.id, "source": e.source, "detail": e.source_detail,
     "target": e.target, "delta": e.delta, "mechanism": e.mechanism,
     "parent_id": e.parent_event_id}
    for e in self._causal_buffer[-20:]
]
```

### 6.4 前端因果图面板

新增 `CausalityPanel.vue` 组件（`src/components/ui/CausalityPanel.vue`）：

- **实时事件流**: 顶部显示最近 5 个事件，带过渡动画
- **因果链树**: 点击事件展开完整因果链
- **系统状态图**: 力导向图展示活跃生理通路
  - 节点大小 = 偏离基线程度
  - 连线粗细 = 因果强度
  - 颜色 = 激活（红）/抑制（蓝）
- **时间轴**: 拖动回放过去 N 秒内各变量的变化及触发原因

### 6.5 文件变更

| 文件 | 操作 | 说明 |
|------|------|------|
| `backend/app/engine/core/causal_event.py` | 新增 | CausalEvent 数据类 + CausalTracker |
| `backend/app/engine/simulation/pipeline.py` | 修改 | 集成因果事件记录和推送 |
| `frontend/src/components/ui/CausalityPanel.vue` | 新增 | 因果图面板 |
| `frontend/src/views/dev/ComponentTestView.vue` | 修改 | 添加 CausalityPanel 演示区块 |
| `docs/features.md` | 修改 | 更新组件列表和 API 说明 |

---

## 7. 实施顺序与依赖

```
Phase 1 (独立)
├── Phase 2 (独立)
│   ├── Phase 3 (可复用 Phase 2 的形态库)
│   │   ├── Phase 4 (依赖 Phase 3 的因果图)
```

- Phase 1 和 Phase 2 无相互依赖，可并行开发
- Phase 3 的因果图引擎为 Phase 4 提供数据来源
- 每阶段独立提交、独立测试、独立上线

## 8. 风险与缓解

| 风险 | 影响 | 缓解 |
|------|------|------|
| PCG 物理模型计算量过大 | 实时流式卡顿 | 使用 IIR 而非 FIR 滤波器；预计算谐振器冲激响应；保留 parametric 模式作为 fallback |
| 病理形态库覆盖不全 | ECG 形态仍然不够丰富 | 设计为可扩展的注册表模式，新形态只需添加 config 即可 |
| 因果图性能 | 每 beat step 复杂度高 | 节点数控制在 <30 个，图拓扑预计算排序 |
| 前端因果面板渲染性能 | 大量 SVG 动画卡顿 | 使用 Canvas 渲染力导向图；事件流限制 20 条/帧 |

## 9. 成功标准

| 阶段 | 验收标准 |
|------|---------|
| Phase 1 | 心音听感明显改善；4 听诊位置可辨别；murmur 不掩盖正常心音 |
| Phase 2 | 至少 8 种病理形态可切换；STEMI 时间演化可观察；不同虚拟人 ECG 有个体差异 |
| Phase 3 | beta_blocker 给药后可见 HR↓→CO↓→反射性代偿的完整过程；运动时多系统协同变化 |
| Phase 4 | 前端可看到每条 vitals 变化的触发原因和完整因果链 |

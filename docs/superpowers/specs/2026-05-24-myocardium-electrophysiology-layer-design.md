# MyocardiumState — 心肌电生理共享底层设计

**日期：** 2026-05-24
**分支：** v2
**状态：** 设计阶段

## 1. 背景与动机

### 问题现状

当前 Virtual Human v2 Pipeline 的生理模型丰富但互不感知：

```
ExercisePhysiologyModel → hr_delta (一个数)
Arrhythmia Triggers      → rhythm_override (一个字符串)
CausalGraph             → 5 个 modifier 数字
Pharmacokinetics        → 4 个 drug 浓度曲线
```

模型之间的唯一交互界面是 `Modifiers`（5 个浮点数：sa_rate_modifier、contractility_modifier、tpr_modifier、av_delay_modifier、preload_modifier），靠 `ParametricConductionNetwork` 中的 `rhythm_override` 字符串做节律切换。

这导致无法回答真实生理中自然发生的交互问题：
- 跑步时 SVT 发作：心率该由窦房结还是折返环决定？SVT 能被运动终止吗？
- 低能量电复律对正常窦律的作用：可能诱发什么？
- 药物在不同生理状态下的差异化效应

### 核心洞察

所有生理状态（运动、情绪、药物、电解质、缺血）最终都作用在相同的**心脏电生理底层**——不应期、传导速度、自律性、触发活动阈值。当前系统缺少这个"共享底层"，每个模型只能各自输出高级别指令（"心率+20%"、"切换到 SVT"），无法自然交互。

## 2. 设计目标

1. **共享电生理状态对象** — `MyocardiumState` 作为所有上层模型写入、所有下层模型读取的唯一状态层
2. **自主神经-组织映射** — `AutonomicTissueMapper` 将交感和副交感张力转化为各心肌区域的电生理参数变化
3. **多起搏点竞争** — `PacemakerCompetition` 取代 `rhythm_override` 字符串切换，允许多个起搏点（窦房结/折返环/异位灶/逸搏）在共享不应期场上自然竞速
4. **向后兼容** — 现有 CausalGraph 和 legacy modifier 路径保留，通过 `engine_mode` 配置切换

## 3. 架构总览

### 数据流

```text
InteractionState
       ↓
TransitionSmoother (现有，不变)
       ↓
┌─────────────────────────────────────┐
│    CausalGraph / AutonomicReflex    │  → sympathetic_tone
│         (现有，不变)                  │    parasympathetic_tone
└──────────────┬──────────────────────┘
               ↓
┌─────────────────────────────────────┐
│     AutonomicTissueMapper           │  ← NEW: Phase 1
│     交感/副交感 → 组织 EP 映射       │
└──────────────┬──────────────────────┘
               ↓
┌─────────────────────────────────────┐
│       MyocardiumState               │  ← NEW: Phase 1
│     共享电生理底层                    │
│     (不应期/传导/自律性/触发易损性)     │
└──────────────┬──────────────────────┘
        ↑                ↓
   ┌────┴────┐    ┌──────┴──────────┐
   │ Exercise│    │ Pacemaker       │  ← NEW: Phase 1
   │ Drugs   │    │ Competition     │
   │ Electrol│    │ 多起搏点竞争     │
   │ Ischemia│    └──────┬──────────┘
   │ Emotion │           ↓
   └─────────┘  ┌─────────────────────┐
                │ ConductionNetwork   │  (现有，改造)
                │ ECG/PCG Synthesizer │  (现有，不变)
                │ Hemodynamics        │  (现有，不变)
                └─────────────────────┘
```

### 关键设计原则

- **MyocardiumState 是单一数据源** — 任何上层模型要影响心脏，必须修改 MyocardiumState 的某个字段，不允许直接"override"最终输出
- **Pacemaker 竞争是节律的唯一来源** — 不存在 `rhythm_override` 字符串，所有节律都是起搏点竞争的结果
- **每个区域对调节信号的敏感性不同** — AVN 对副交感高度敏感，心室几乎不敏感，这自然产生差异化的生理行为
- **外部物理作用通过机械-血流动力学路径影响心脏** — 胸内压、体位、外力压迫先改变前负荷/后负荷，再经由压力反射-自主神经-心肌状态链条传递，不直接"写入"电生理参数

### 完整的输入-输出路径

```
ExternalPhysicalAction            Autonomic Modulators        Pharmacological
(体位/Valsalva/外力/调搏)         (运动/情绪/睡眠)            (药物/电解质)
         │                              │                         │
         ↓                              ↓                         ↓
┌────────────────┐            ┌──────────────────┐    ┌──────────────────┐
│ PhysioMechanical│          │AutonomicTissueMapper│    │  Pharmacokinetics │
│    Mapper       │          │  (ANS→组织 EP)     │    │  (浓度曲线)       │
└───────┬────────┘            └────────┬─────────┘    └────────┬─────────┘
        │                              │                       │
        │  preload/afterload           │  erp/cv/auto           │  erp/cv/dad
        ↓                              ↓                       ↓
┌────────────────────────────────────────────────────────────────────┐
│                        MyocardiumState                              │
│  (不应期 / 传导速度 / 自律性 / 触发易损性)                            │
└────────────────────────────────┬───────────────────────────────────┘
                                 │
                    ┌────────────┴────────────┐
                    │   PacemakerCompetition  │
                    │   (多起搏点竞争)          │
                    └────────────┬────────────┘
                                 ↓
                      Conduction / ECG / PCG
                                 ↓
                      AlgebraicHemodynamics
                      (SV, CO, MAP — 反馈到压力反射)
```

物理路径（左侧）和神经/药理路径（中/右）在 MyocardiumState 汇合。血流动力学结果通过压力反射反馈回自主神经系统，形成闭环。

## 4. Section 1: MyocardiumState

### 数据结构

```python
@dataclass
class MyocardiumState:
    """心肌电生理共享状态 — 所有上层模型通过修改此状态来影响心脏行为。"""

    # ── 不应期（ms）──
    atrial_erp: float = 200.0          # 心房有效不应期
    avn_fast_path_erp: float = 320.0   # AVN 快径 ERP
    avn_slow_path_erp: float = 280.0   # AVN 慢径 ERP（Phase 2 启用）
    his_purkinje_erp: float = 380.0
    ventricular_erp: float = 250.0

    # ── 传导速度（归一化，1.0 = 基线）──
    atrial_cv: float = 1.0
    avn_cv: float = 1.0                # AVN 传导速度
    his_purkinje_cv: float = 1.0
    ventricular_cv: float = 1.0

    # ── 自律性（bpm）──
    sinus_rate: float = 70.0           # 窦房结固有频率
    junctional_escape_rate: float = 40.0
    ventricular_escape_rate: float = 25.0

    # ── 触发活动易损性 [0, 1] ──
    dad_susceptibility: float = 0.0    # 延迟后除极（洋地黄、儿茶酚胺）
    ead_susceptibility: float = 0.0    # 早期后除极（长 QT、低钾）

    # ── 折返基质 ──
    erp_dispersion: float = 0.0        # 不应期离散度（折返基质）
    conduction_anisotropy: float = 0.0 # 各向异性传导

    # ── 旁路（Phase 2）──
    accessory_pathway_erp: float | None = None  # None = 无旁路
    accessory_pathway_cv: float = 1.0
```

### Baseline 值来源

- 从 `constants.py` 的基准状态推导
- 年龄/性别通过 `MorphVarianceConfig` 调整基线值
- 个体差异：±15% 高斯噪声，基于 `virtual_human_profile_id` 种子

## 5. Section 2: AutonomicTissueMapper

### 职责

将 ANS 输出（sympathetic_tone [0,1]、parasympathetic_tone [0,1]）映射为各心肌区域的电生理参数变化。

### 映射规则

真实生理依据：

| 参数 | 交感↑ (β1+β2) | 副交感↑ (M2) | 备注 |
|------|-------------|-------------|------|
| sinus_rate | ↑↑↑ (+80 bpm max) | ↓↓↓ (−40 bpm max) | 窦房结对两者最敏感，β1+M2 共表达 |
| atrial_erp | ↓↓ (−30%) | ↑ (+15%) | 心房有 M2 但密度不如 AVN |
| avn_erp (fast path) | ↓ (−15%) | ↑↑↑ (+40%) | AVN 对副交感主导 |
| avn_erp (slow path) | ↓ (−10%) | ↑↑↑ (+35%) | 慢径对副交感更敏感 |
| avn_cv | ↑↑ (+20%) | ↓↓↓ (−50%) | AVN 传导速度受副交感强烈抑制 |
| his_purkinje_erp | ↓ (−10%) | — | 希浦系几乎没有副交感支配 |
| ventricular_erp | ↓ (−15%) | — | 心室几乎没有副交感支配 |
| junctional_rate | ↑↑ (+30 bpm) | ↓↓ (−20 bpm) | |
| dad_susceptibility | ↑↑↑ (+0.6 max) | — | 儿茶酚胺→cAMP→DAD |
| ead_susceptibility | − (−0.1) | ↑ (+0.2) | 长 RR→APD 延长→EAD 风险 |
| erp_dispersion | ↑ (+0.3) | ↓ (−0.2) | 交感激化离散度 |

### 交互效应

运动时的"cardiac autonomic conflict"（交感+副交感共激活）自然建模：
- 窦房结 α=β1 vs M2，净效应通常交感占优→心率↑
- AVN 传导 β1↑ vs M2↓↓↓，副交感占优→PR 延长→可能产生 Wenckebach
- 这解释了"运动时出现文氏现象"的真实临床观察

```python
class AutonomicTissueMapper:
    def apply(self, baseline: MyocardiumState, symp: float, para: float) -> MyocardiumState:
        """将自主神经张力映射到心肌状态，返回新实例（不修改 baseline）。"""
        state = copy(baseline)

        # 窦房结 — β1+M2 平衡
        symp_hr_delta = symp * 80.0   # 最大+80bpm
        para_hr_delta = para * 40.0   # 最大-40bpm
        state.sinus_rate = baseline.sinus_rate + symp_hr_delta - para_hr_delta

        # AVN 传导 — 副交感主导
        state.avn_cv = baseline.avn_cv * (1 + 0.2 * symp - 0.5 * para)
        state.avn_fast_path_erp = baseline.avn_fast_path_erp * (1 - 0.15 * symp + 0.4 * para)

        # ERP 离散度 — 交感增加离散
        state.erp_dispersion = baseline.erp_dispersion + 0.3 * symp - 0.2 * para

        # ... 其余参数
        return state.clamp_to_physiological_ranges()
```

## 6. Section 3: PacemakerCompetition

### 废弃 `rhythm_override`

当前 `InteractionState.rhythm_override: str` 将在 `myocardium` 模式下废弃。节律来源改为多起搏点竞争。

### Pacemaker 数据结构

```python
@dataclass
class Pacemaker:
    id: str                          # 唯一标识
    kind: PacemakerKind              # sinus | avnrt | avrt | atrial_tachy | vt | pvc | escape_junctional | escape_ventricular | af | vf
    intrinsic_rate: float            # 固有频率 (bpm)
    origin: str                      # 'sa_node' | 'atrium' | 'avn_reentry' | 'accessory_reentry' | 'ventricle'
    retrograde_p: bool               # 是否逆传心房产生逆行 P 波
    reset_by_capture: bool           # 是否被捕获重置（默认 True）
    protected: bool                  # 传入阻滞保护（并行心律，默认 False）
    coupling_interval: float | None  # 联律间期（早搏类，None = 自动）
    activation_threshold_ms: float   # 达到阈值所需时间
    life: PacemakerLife              # transient | sustained | permanent
    beats_remaining: int | None      # 剩余心搏数（episodic 的）
    conditions: dict[str, float]     # 维持条件（如 'min_erp_dispersion': 0.1）

class PacemakerKind(str, Enum):
    SINUS = "sinus"
    ATRIAL_TACHY = "atrial_tachy"
    AVNRT = "avnrt"
    AVRT = "avrt"
    VT = "vt"
    PVC = "pvc"
    JUNCTIONAL_ESCAPE = "junctional_escape"
    VENTRICULAR_ESCAPE = "ventricular_escape"
    AF = "af"
    VF = "vf"

class PacemakerLife(str, Enum):
    TRANSIENT = "transient"    # 单次/短阵
    SUSTAINED = "sustained"    # 持续但可终止
    PERMANENT = "permanent"    # 始终存在（窦房结）
```

### ElectrotonicModel（电紧张调制器）

```python
class ElectrotonicModel:
    """
    不应期和传导的正态化模型。
    计算起搏点输出电压和心肌的响应特性。
    """
    def compute_impulse(self, pm: Pacemaker, state: MyocardiumState, t: float) -> ActivationImpulse:
        """给定起搏点、心肌状态和时间，返回激活脉冲。"""

    def is_excitable(self, region: str, state: MyocardiumState, t_last_activated: float, t: float) -> bool:
        """检查区域在给定时间内是否可兴奋（已脱离不应期）。"""

    def effective_rate(self, pm: Pacemaker, state: MyocardiumState) -> float:
        """返回一个起搏点在给定心肌状态下的有效速率。
        考虑传导延迟、不应期和可能的阻滞。"""
```

### 竞争算法

```python
class PacemakerCompetition:
    def __init__(self, state: MyocardiumState, electrotonic: ElectrotonicModel):
        self.state = state
        self.electrotonic = electrotonic
        self.pacemakers: list[Pacemaker] = []
        self.sinus_pacemaker: Pacemaker = ...  # 总是存在

    def register(self, pm: Pacemaker):
        """注册一个活跃起搏点。"""

    def resolve(self, t: float, dt: float) -> CompetitionResult:
        """
        决定本心动周期的主导起搏点。
        
        算法：
        1. 对每个起搏点，计算有效速率（考虑不应期和传导延迟）
        2. 按有效速率排序
        3. 最快到达阈值的起搏点捕获心室
        4. 捕获脉冲重置所有未保护的起搏点周期
        5. 并行心律（protected=True）保持独立节律
        6. 返回 CompetitionResult（主导起搏点 + 融合信息）
        """
```

### 竞争规则

1. **最快到达阈值者胜出** — 不仅是 rate 最高，还需考虑传导延迟和不应期状态
2. **捕获重置** — 夺获脉冲侵入其他起搏点，重置其周期（除非传入阻滞保护）
3. **并行心律保护** — `protected=True` 的 pacemaker 节律独立，可能产生融合波
4. **隐匿性传导** — AVN 部分穿透但不产生 QRS，仍重置 AVN 不应期
5. **融合波** — 两个 pacemaker 几乎同时激活心室时产生（QRS 形态介于两者之间）
6. **AF/VF 特殊处理** — 心房/心室以 >350bpm 的随机多重子波活动，不建模个体 pacemaker

### 竞争结果

```python
@dataclass
class CompetitionResult:
    winner: Pacemaker              # 主导起搏点
    beat_kind: BeatKind            # 映射到现有 BeatKind
    p_wave_mode: PWaveMode         # 映射到现有 PWaveMode
    effective_rate: float          # 有效心率 (bpm)
    fusion: bool = False           # 是否有融合
    fusion_partner: Pacemaker | None = None
    concealed_conduction: bool = False
    retrograde_capture: bool = False
```

## 7. Section 4: External Physical Action Layer（外部物理作用层）

### 设计动机

自主神经、药物、电解质这三条输入路径（Section 6 数据流中/右两条线）无法覆盖以下场景：
- 食道调搏（外部电流捕获心房）
- Valsalva maneuver + 下蹲（胸内压变化→静脉回流→前负荷）
- 杯子压迫心脏（外力→心脏几何→前负荷+机械刺激）
- 体位变化（站立/平卧/头低脚高→静脉回流重分布）
- 咳嗽诱发心律失常（胸内压骤变→压敏通道激活）

这些场景的共性是：**外部物理/机械力 → 血流动力学变化 → 压力反射 → 自主神经 → 心肌电生理。** 需要一条独立的输入路径。

### ExternalPhysicalAction 类型

```python
class PhysicalActionKind(str, Enum):
    EXTERNAL_PACING = "external_pacing"         # 食道调搏/经皮起搏
    THORACIC_PRESSURE = "thoracic_pressure"      # Valsalva / Mueller / 憋气
    POSTURE_CHANGE = "posture_change"            # 站立 / 下蹲 / 平卧
    EXTERNAL_COMPRESSION = "external_compression" # 杯子压迫 / 胸部按压
    ACCELERATION = "acceleration"                # G 力（未来扩展）


@dataclass
class ExternalPhysicalAction:
    kind: PhysicalActionKind
    start_time: float = 0.0         # 开始时刻 (simulation time)
    duration_sec: float | None = None  # None = 手动结束

    # External Pacing 参数
    pacing_rate: float = 100.0      # bpm
    pacing_current_ma: float = 10.0 # 电流 (mA)
    pacing_site: str = "atrium"     # 'atrium' | 'ventricle' | 'av_sequential'
    pacing_mode: str = "fixed"      # 'fixed' | 'burst' | 'ramp' | 'overdrive'

    # Thoracic Pressure 参数
    pressure_mmhg: float = 40.0     # Valsalva 典型 40mmHg
    pressure_profile: str = "square" # 'square' | 'ramp' | 'valsalva'（四相）

    # Posture 参数
    posture: str = "standing"       # 'standing' | 'squatting' | 'supine' | 'trendelenburg'

    # Compression 参数
    compression_force_n: float = 0.0 # 牛顿
    compression_area_cm2: float = 1.0
    compression_site: str = "precordium"
```

### 胸内压模型 (ThoracicPressureModel)

Valsalva maneuver 的经典四相生理：

```text
Phase I (0-2s):  胸内压↑ → 肺静脉受压 → 短暂 preload↑ → MAP↑
Phase II (2-30s): 胸内压维持 → 静脉回流受阻 → preload↓ → CO↓ → MAP↓ → baroreflex HR↑
Phase III (释放瞬时): 胸内压↓ → 肺血管床扩张 → preload 进一步短暂↓ → MAP↓
Phase IV (2-60s): 静脉回流恢复 → preload↑↑ → BP 反跳 → baroreflex HR↓↓（特征性心动过缓）
```

```python
@dataclass
class ThoracicPressureState:
    phase: str = "baseline"          # 'baseline' | 'I' | 'II' | 'III' | 'IV'
    intrathoracic_pressure_mmhg: float = -5.0  # 正常呼吸末为负压
    venous_return_factor: float = 1.0  # 1.0 = 正常，<1.0 = 回流受阻
    time_in_maneuver: float = 0.0

class ThoracicPressureModel:
    def apply(
        self,
        action: ExternalPhysicalAction,
        state: ThoracicPressureState,
        dt_sec: float,
    ) -> ThoracicPressureState:
        """
        根据 Valsalva 四相模型更新胸内压状态。
        
        输出影响：
        - state.intrathoracic_pressure_mmhg → 直接改变 intrathoracic pressure
        - state.venous_return_factor → 改变前负荷
        """
```

### 体位-静脉回流映射

体位变化通过重力重分布血容量来改变静脉回流：

| 体位 | venous_return_factor | 说明 |
|------|---------------------|------|
| supine (平卧) | 1.0 | 基线 |
| standing (站立) | 0.7 | ~500ml 血液淤积下肢 |
| squatting (下蹲) | 1.3 | 下肢静脉受压+腹部压迫→回流↑ |
| trendelenburg (头低脚高) | 1.15 | 重力辅助回流 |
| leg_raise (被动抬腿) | 1.2 | 容量负荷试验 |

体位变化时 `venous_return_factor` 有过渡时间（tau ≈ 3-5 秒，自主神经代偿约 30 秒启动）。

### 外压模型 (ExternalCompressionModel)

```python
class ExternalCompressionModel:
    """
    外力作用于胸壁/心前区的影响。
    
    对心脏的作用取决于：
    - 力度 (N)
    - 作用面积 (cm²)
    - 作用位置（心前区最敏感）
    """
    def compute_effects(
        self,
        action: ExternalPhysicalAction,
        dt_sec: float,
    ) -> CompressionEffects:
        """
        返回：
        - preload_reduction: float    # 前负荷减低比例 [0, 1]
        - mechanical_irritation: float # 机械刺激致 PVC 概率 [0, 1]
        - pain_response: float         # 疼痛→交感激活 [0, 1]
        """
```

杯子压迫的典型效应链：
```
外力 5N, 面积 5cm², 心前区
  → preload_reduction = 0.15           (15% 前负荷降低)
  → mechanical_irritation = 0.05       (5% 概率诱发 PVC)
  → pain_response = 0.2                (轻度不适 → 交感轻度激活)
  → 血流动力学: SV↓ → MAP↓ → baroreflex HR↑
  → 心电: 与机械刺激诱发的 PVC 竞争
```

### 机械-电反馈模型 (MechanoElectricalFeedbackModel)

**这是物理路径与心肌电生理之间的关键耦合桥梁。**

剧烈运动后+Valsalva 释放+下蹲诱发短阵 VT 的机制：

```
剧烈运动后                     Valsalva 释放                下蹲
儿茶酚胺高位                   胸内压骤降                   静脉回流↑↑
交感亢进                       preload↓↓                   preload↑↑↑
    ↓                              ↓                           ↓
心室 ERP 缩短              ←── 心肌被急剧拉伸 ──→       机械-电反馈
不应期离散度↑              牵张激活阳离子通道(SACs)            ↓
DAD 易损性↑                    ↓                      细胞内 Ca²⁺ 超载
                          Na⁺/Ca²⁺ 内流              触发后除极
                              ↓                           ↓
┌──────────────────────────────────────────────────────────────────┐
│  条件耦合：高儿茶酚胺 + 快速 preload 变化 + 机械牵张                │
│  → DAD 幅度 > 阈电位 → 触发 PVC / 短阵 VT                         │
│  → 多灶早搏 + ERP 离散度 → 功能性折返 → 持续 VT                     │
└──────────────────────────────────────────────────────────────────┘
```

核心生理原理：
- **牵张激活通道 (SACs)**：心肌细胞膜上的非选择性阳离子通道，在细胞拉伸时开放
- **机械-电反馈**：心肌长度变化直接改变动作电位波形——拉伸导致 APD 延长 + 后除极
- **Ca²⁺ 超载**：牵张 + 高儿茶酚胺 → 肌浆网 Ca²⁺ 泄漏 → DAD
- **ERP 离散度增加**：右心室（薄壁）比左心室更易被拉伸 → 不均匀不应期 → 折返基质

```python
class MechanoElectricalFeedbackModel:
    """
    将前负荷变化率(dPreload/dt)和心肌牵张映射为致心律失常性。
    
    不直接创建 pacemaker——而是修改 MyocardiumState 的触发易损性，
    让 PacemakerCompetition 根据更新后的心肌状态自然产生 PVC/VT。
    """

    def compute_stretch_effects(
        self,
        preload_history: list[float],  # 最近 N 秒的前负荷序列
        dt_sec: float,
        catecholamine_level: float,    # 儿茶酚胺水平 (运动/情绪)
        baseline_state: MyocardiumState,
    ) -> StretchEffect:
        """
        参数:
        - preload_history: 滑动窗口内的前负荷值（用于计算 dPreload/dt）
        - catecholamine_level: [0, 1] 儿茶酚胺水平
        
        返回 StretchEffect:
        - dad_susceptibility_delta: float     # DAD 易损性增量
        - ead_susceptibility_delta: float     # EAD 易损性增量
        - erp_dispersion_delta: float         # 不应期离散度增量
        - stretch_pvc_probability: float      # 牵张直接诱发 PVC 概率
        - vt_sustainability_score: float      # VT 可维持性评分 [0, 1]
        """

    def _compute_d_preload_dt(
        self, preload_history: list[float], dt_sec: float
    ) -> float:
        """
        计算前负荷变化率 (normalized units/sec)。
        
        阈值：
        - |dPreload/dt| < 0.05 → 变化平缓，几乎无机械-电效应
        - |dPreload/dt| > 0.2  → 快速变化，SACs 激活
        - |dPreload/dt| > 0.5  → 剧烈变化（如 Valsalva 释放+下蹲叠加），
          相当于前负荷在 1-2 秒内从 0.5 跳到 1.3
        """

    def _compute_stretch_dad_susceptibility(
        self,
        d_preload_dt: float,
        preload_current: float,
        catecholamine_level: float,
    ) -> float:
        """
        牵张→DAD 易损性映射。
        
        关键非线性：DAD 需要两个条件同时满足：
        1. 快速牵张 (SACs 开放) → Ca²⁺ 内流
        2. 高儿茶酚胺 (cAMP/PKA) → 肌浆网 Ca²⁺ 泄漏
        
        单独牵张或单独高儿茶酚胺 → 轻度 DAD (可能不触发)
        两者同时 → DAD 幅度乘性放大 → 阈上除极 → PVC
        
        公式：
        dad_delta = stretch_factor * catecholamine_factor
        stretch_factor = sigmoid(d_preload_dt, threshold=0.2, steepness=4)
        catecholamine_factor = 0.1 + 0.9 * catecholamine_level
        
        这解释了为什么:
        - 安静时 Valsalva → 牵张但低儿茶酚胺 → 偶尔 PVC
        - 运动刚结束 → 高儿茶酚胺但无牵张 → 低风险（无 SACs 激活）
        - 运动后+Valsalva+下蹲 → 两者叠加 → DAD 量大 → PVC/短阵 VT ← 你体验到的！
        """

    def _compute_erp_dispersion_delta(
        self,
        d_preload_dt: float,
    ) -> float:
        """
        快速不均匀牵张 → ERP 离散度增加。
        
        机制：RV vs LV 壁厚不同 → 同等牵张下扩张程度不同
        → 不应期缩短不均匀 → 离散度↑
        → 当离散度 > 阈值时 → 功能性折返 → VT 可维持
        """
```

### 体位+憋气+下蹲+吐气 完整交互链

将上述模型串联到 PhysiolMechanicalMapper 中，构建完整路径：

```text
初始状态: 刚结束剧烈运动
  → catecholamine = 0.8 (高位)
  → sinus_rate = 150 (高位)
  → myocardial_state.ventricular_erp = 缩短 (交感效应)
  → myocardial_state.dad_susceptibility = 0.4 (高儿茶酚胺基线)

用户执行: 憋气 (Valsalva Phase II, 持续 10s)
  → thoracic_pressure = +40mmHg
  → venous_return = 0.6 → preload = 0.6
  → 前负荷梯度: 平缓下降 (dPreload/dt ≈ -0.03) → 无明显牵张

用户执行: 猛烈吐气 (Valsalva Phase III → 0.5s)
  → thoracic_pressure = -10mmHg (骤降)
  → pulmonary vein squeeze → preload 从 0.6 跳到 0.9
  → dPreload/dt = (0.9-0.6)/0.5 = 0.6 → 超过阈值 0.5!

用户同时: 下蹲
  → posture venous_return = 1.3
  → preload 从 0.9 跳到 1.3
  → dPreload/dt = (1.3-0.9)/0.5 = 0.8 → 极度剧烈牵张!

合并时间线 (吐气+下蹲几乎同时):
  dPreload/dt ≈ 0.7  (剧烈牵张)
  catecholamine = 0.8 (高位)
  
MechanoElectricalFeedbackModel 计算:
  stretch_factor = sigmoid(0.7, 0.2, 4) ≈ 0.88
  catecholamine_factor = 0.1 + 0.9*0.8 = 0.82
  dad_susceptibility_delta = 0.88 * 0.82 = 0.72
  
  myocardial_state.dad_susceptibility = 基线 0.4 + delta 0.72 = 1.12 (clamped to 1.0)
  myocardial_state.erp_dispersion += 0.4
  
结果:
  → DAD 易损性 = 1.0 (max) → 高概率触发 PVC
  → ERP 离散度 > 阈值 → 折返条件满足
  → PacemakerCompetition 可同时注册: 窦性 + 多个 PVC + 短阵 VT pacemaker
  → 竞争结果: VT pacemaker 获胜（超速抑制窦房结）
  → 用户感知: 剧烈心悸 + 短暂 VT
```

### PhysioMechanicalMapper

```python
class PhysioMechanicalMapper:
    """
    将 ExternalPhysicalAction 翻译为：
    1. 前负荷/后负荷变化 → 输入 AlgebraicHemodynamics  
    2. 外部 Pacemaker → 注册进 PacemakerCompetition
    3. 机械刺激 PVC → 配置 PVC Pacemaker
    4. 前负荷变化率 → 机械-电反馈 → MyocardiumState 致心律失常性  ← NEW
    """

    def __init__(
        self,
        thoracic_model: ThoracicPressureModel,
        compression_model: ExternalCompressionModel,
        me_feedback_model: MechanoElectricalFeedbackModel,  # NEW
    ):
        ...

    def apply(
        self,
        action: ExternalPhysicalAction | None,
        dt_sec: float,
        catecholamine_level: float,  # NEW: 来自运动/情绪模型
        preload_history: list[float],  # NEW: 滚动窗口，用于 dPreload/dt
    ) -> MechanicalEffect:
        """
        返回 MechanicalEffect:
        - preload_modifier: float
        - afterload_modifier: float  
        - external_pacemakers: list[Pacemaker]
        - pvc_probability: float            # 机械刺激 + 牵张触发
        - autonomic_modifier: float         # 疼痛/应激
        - me_feedback: StretchEffect | None # NEW: 机械-电反馈
        """
```

### 食道调搏的建模

食道调搏创建一个人工 Pacemaker：

```python
def create_esophageal_pacer(action: ExternalPhysicalAction) -> Pacemaker:
    capture_threshold = 8.0  # mA，食道调搏典型阈值
    effective_current = action.pacing_current_ma

    capture_probability = sigmoid(
        effective_current - capture_threshold,
        steepness=2.0,
    )
    # 10mA → capture_prob ≈ 0.88
    # 15mA → capture_prob ≈ 0.98
    # <5mA → capture_prob ≈ 0.01

    return Pacemaker(
        kind="external_pacing",
        intrinsic_rate=action.pacing_rate,
        origin="atrium",  # 食道电极紧贴左房后壁
        retrograde_p=False,
        reset_by_capture=True,
        protected=True,   # 外部电流源，不受心脏内电活动影响
        life=PacemakerLife.SUSTAINED,
        conditions={
            "min_capture_probability": capture_probability,
            "pacing_mode": action.pacing_mode,  # 'fixed' | 'burst' | 'ramp' | 'overdrive'
        },
    )
```

调搏模式：
- **fixed**：固定频率起搏
- **burst**：短阵高频起搏（诱发/终止折返）
- **ramp**：频率递增（测量窦房结恢复时间）
- **overdrive**：以高于窦律 10-20bpm 的频率持续起搏

### 直接心肌电刺激（外源性非同步起搏变体）

食道调搏是"近心脏"的同步起搏。但存在更极端的场景：电极直接接触心肌（针尖在心肌内），
与体表电极片形成回路，通过非心脏专用设备（如 TENS 理疗仪）供电。

```
解剖: 针尖 (~0.1mm²) → 心肌内
      体表电极 (~10cm²) → 胸壁皮肤
设备: 典型 TENS: 1-100mA, 1-250Hz, 脉宽 50-250µs

针尖电流密度 = 1mA / (π×0.05²mm²) ≈ 127 A/cm²
——是心脏起搏阈值的 1000-10000 倍
```

关键差异：

| 特性 | 食道调搏 | 针尖心肌刺激 |
|------|---------|------------|
| capture_threshold | ~8 mA | ~0.05 mA (µA 级) |
| 脉冲与心动周期同步 | 可同步 | **完全非同步** |
| 电流密度 (A/cm²) | ~0.1 | **~100-1000** |
| 夺获失败可能性 | 有（低于阈值时） | **几乎必然夺获** |

**R-on-T 风险建模：**

```python
def compute_r_on_t_risk(
    pacer: Pacemaker,
    myocardium: MyocardiumState,
    t_last_activation: float,
    t: float,
) -> float:
    """
    非同步脉冲落于 T 波（易损期）的概率。
    
    在 T 波顶端前后 30ms 的易损窗内受到电击 →
    R-on-T 现象 → 多形性 VT / VF 高风险。
    
    易损窗占比 ≈ 60ms / (60/HR)s ≈ HR * 0.001
    在 HR=70 时约 7% 概率命中。
    
    但这是 PER PULSE 的概率。TENS 以 100Hz 输出意味着每秒 100 个脉冲，
    必然有一个落在 T 波上。
    """
    
    vulnerable_window_ms = 60.0  # T 波易损窗
    rr_ms = 60000.0 / myocardium.sinus_rate
    fraction_vulnerable = vulnerable_window_ms / rr_ms
    
    # 每个脉冲落于 T 波的概率
    p_single = fraction_vulnerable  # ~7% at HR 70
    
    # N 个非同步脉冲至少一个命中 T 波的概率
    pulse_rate_hz = pacer.intrinsic_rate / 60.0  # TENS 频率可能是 100Hz
    pulses_per_beat = pulse_rate_hz * (rr_ms / 1000.0)
    p_at_least_one = 1 - (1 - p_single) ** pulses_per_beat
    
    # 在 100Hz TENS + HR 70: pulses_per_beat ≈ 85
    # p_at_least_one ≈ 1 - 0.93^85 ≈ 0.998 → 99.8%
    
    return p_at_least_one
```

**场景分类：**

| 条件 | 模型行为 | 临床结果 |
|------|---------|---------|
| 低频率 TENS (<50Hz)，低电流 | 脉冲频率低于窦律，窦律主导，但落在 T 波上的脉冲 → R-on-T → 可能 VT/VF | 不规整夺获 + VF 风险 |
| 高频率 TENS (>100Hz) | 大量非同步脉冲 → 每次 T 波被命中 → 多形 VT → 退化为 VF | **VF** |
| 任何频率，针尖直接心肌 | capture_prob = 1.0（必然夺获），竞争胜利 → 外部 pacing 为主导节律 | 超速起搏 → VT |
| 针尖同时造成心肌损伤 | 额外叠加 `damage_level` ↑ + 局部炎症 → erp_dispersion ↑ → 折返基质 | VF 可诱导性更高 |

**在 ExternalPacing 工厂中的实现：**

```python
def create_intracardiac_pacer(
    action: ExternalPhysicalAction,
    myocardium: MyocardiumState,
) -> Pacemaker:
    """
    针尖心肌电极 + 非心脏专用设备。
    关键：capture_probability ≈ 1.0（必然夺获），
    但脉冲与心动周期完全非同步 → R-on-T 高概率。
    """
    # 针尖在心肌内 → 捕获阈值 µA 级
    # 理疗仪输出 mA 级 → 远超阈值 → 必然捕获
    capture_prob = 1.0  # 必然夺获

    return Pacemaker(
        kind="external_pacing",
        intrinsic_rate=action.pacing_rate,  # TENS 典型 100-250Hz
        origin="ventricle",                  # 针尖通常在右室
        retrograde_p=True,                   # 可逆传心房
        reset_by_capture=False,              # 非同步 — 不感知自身心律
        protected=True,                      # 外部电流源
        life=PacemakerLife.SUSTAINED,
        conditions={
            "capture_probability": capture_prob,
            "pacing_mode": "asynchronous",   # 非同步模式
            "r_on_t_risk": compute_r_on_t_risk(...),  # R-on-T 风险
        },
    )
```

**PacemakerCompetition 中的 R-on-T 处理：**

当 `pacing_mode == "asynchronous"` 且脉冲落在 T 波易损窗时：

```text
1. External pacing pacemaker 以固定间期发射（非同步）
2. 脉冲落在 T 波上 → R-on-T
3. 触发 VF 启动条件：
   - 心室不应期被强制打破 → 多子波折返
   - VF pacemaker 被注册（random reentry, rate > 350 bpm）
4. VF pacemaker 无条件的持续获胜（最高"有效"频率）
5. 有效输出: VF → ECG 显示室颤波形 → 血流动力学崩溃
```

## 8. Section 5: Bigeminy/Trigeminy as Emergent Behavior

二联律和三联律不需要单独的状态机或命令——它们是 `PacemakerCompetition` 的 capture-reset 循环自然产生的结果。

### 机制

```
时刻 0:   窦性 beat → 捕获心室 → 重置 PVC pacemaker 的周期 (PVC 被抑制)
时刻 500ms: PVC 的 coupling_interval 到期 → PVC 激活 → 捕获心室
           → 重置窦房结 pacemaker 的周期 (窦房结被抑制)
时刻 1000ms (sinus周期): 窦房结被重置，从时刻 500ms 重新计时
           → 下一个窦性 beat 将在 500+1000=1500ms 发生
时刻 1500ms: 窦性 beat → 捕获心室 → 重置 PVC
时刻 2000ms: PVC 激活 → ...
```

这就是二联律："窦-PVC-窦-PVC" 交替，无需任何硬编码。

三联律是同样的机制，只是 PVC 发生频率不同（每第三个心搏为 PVC），取决于 PVC 固有周期与基础窦性周期的比例关系。

### 诱发方式

用户通过修改 PVC pacemaker 参数来诱发：

```
# 二联律
set_pvc pattern=bigeminy coupling_interval=400  → 创建 coupling_interval=400ms 的 PVC pacemaker
   在基础 HR=60bpm (rr=1000ms) 下：
   PVC 在 t=400ms 发射 → 夺获 → 重置窦房结 → 下一个窦性在 t=400+1000=1400ms
   → 下一个 PVC 在 t=400+440=840ms? 不，PVC 被窦性捕获重置了
   
   实际模式：窦(t=0) → PVC(t=400) → 窦(t=400+1000=1400) → PVC(t=1400+400=1800) → ...
   这就是二联律。
```

### 与其他状态的交互

二联律在运动时会怎样？这自然由竞争模型处理：
- 运动 → 交感↑ → sinus_rate↑ (比如 60→120bpm, rr=1000→500ms)
- PVC coupling_interval 不变 (400ms)
- 当 sinu_rate 快到使得 rr < coupling_interval+PVC_refractory 时，PVC 被持续抑制
- 这就是"运动抑制 PVC"的真实生理现象

反过来，如果 PVC coupling_interval 很短 (300ms)，即使在运动时也能保持二联律：
- 窦(t=0) → PVC(t=300) → 窦(t=300+500=800) → PVC(t=800+300=1100) → ...
- 有效心率 = 60/0.55s = 109bpm，但其中一半是 PVC

### 测试用例

```python
def test_bigeminy_emerges_from_pvc_and_sinus_competition():
    state = MyocardiumState(sinus_rate=60)
    sinus = Pacemaker(kind="sinus", intrinsic_rate=60, origin="sa_node")
    pvc = Pacemaker(kind="pvc", intrinsic_rate=60, origin="ventricle",
                    coupling_interval=400, life=PacemakerLife.SUSTAINED)
    
    comp = PacemakerCompetition(state, ElectrotonicModel())
    comp.register(sinus)
    comp.register(pvc)
    
    # 运行20个心动周期
    results = [comp.resolve(t, dt) for t in ...]
    winners = [r.winner.kind for r in results]
    
    # 验证：二联律为 "sinus, pvc, sinus, pvc, ..." 交替
    for i in range(1, len(winners)):
        assert winners[i] != winners[i-1], f"Beat {i}: expected alternation, got {winners[i]}"
```

## 9. Section 6: 平板负荷试验 (ExerciseProtocol)

平板负荷试验在 ExercisePhysiologyModel 之上增加协议调度层：

```python
@dataclass
class BruceStage:
    stage: int
    duration_min: float
    speed_mph: float
    grade_percent: float
    mets: float                       # METs 预估值

BRUCE_PROTOCOL = [
    BruceStage(1, 3, 1.7, 10, 4.6),
    BruceStage(2, 3, 2.5, 12, 7.0),
    BruceStage(3, 3, 3.4, 14, 10.2),
    BruceStage(4, 3, 4.2, 16, 12.1),
    BruceStage(5, 3, 5.0, 18, 14.9),
    BruceStage(6, 3, 5.5, 20, 17.0),
]

class ExerciseProtocolRunner:
    def __init__(self, protocol: list[BruceStage]):
        self.stages = protocol
        self.current_stage_idx = 0
        self.stage_elapsed_sec = 0.0

    def step(self, dt_sec: float) -> float:
        """推进协议，返回当前 intensity [0, 1]。"""
        self.stage_elapsed_sec += dt_sec
        current_stage = self.stages[self.current_stage_idx]

        if self.stage_elapsed_sec >= current_stage.duration_min * 60:
            self.current_stage_idx = min(self.current_stage_idx + 1, len(self.stages) - 1)
            self.stage_elapsed_sec = 0.0

        mets = self.stages[self.current_stage_idx].mets
        # 将 METs 映射到 intensity: 1 MET(静息) → 0, ~20 METs(极限) → 1
        intensity = min((mets - 1) / 19, 1.0)
        return intensity
```

## 10. Section 7: 与现有 Pipeline 的集成

### InteractionState 变更

```diff
- rhythm_override: str = ''       # 移除
- hr_override: float | None       # 移除（替换为 sinus_rate_modulation）
+ arrhythmia_command: ArrhythmiaCommand | None  # 新增：诱发指令
+ intervention: Intervention | None             # 新增：干预指令
+ physical_action: ExternalPhysicalAction | None # 新增：外部物理作用
+ sinus_rate_modulation: float = 0.0            # 新增：对窦性心率的调制（bpm）
```

```python
@dataclass
class ArrhythmiaCommand:
    kind: ArrhythmiaKind  # 'svt' | 'af' | 'vt' | 'vf' | 'pvc' | 'brady'
    svt_type: str = ''    # 'avnrt' | 'avrt' | 'at' (当 kind=svt 时)
    duration_beats: int | None = None  # None = 手动终止
    induction_params: dict[str, float] = field(default_factory=dict)

@dataclass  
class Intervention:
    kind: InterventionKind  # 'cardioversion' | 'defibrillation' | 'drug_bolus'
    energy_j: float = 0.0       # 电击能量
    drug_name: str = ''          # 药物名称
    drug_dose_mg: float = 0.0
```

### 新增命令

```python
# 心律失常诱发
("induce_avnrt", "诱发 AVNRT"),
("induce_avrt", "诱发 AVRT"),
("induce_atrial_tachy", "诱发房速"),
("induce_af", "诱发房颤"),
("induce_vt", "诱发室速"),
("induce_vf", "诱发室颤"),
("induce_pvc", "诱发室早（指定模式）"),
("terminate_arrhythmia", "终止当前心律失常"),

# 干预
("cardiovert", "电复律（指定能量 J）"),
("defibrillate", "除颤"),
("drug_adenosine", "腺苷推注（6mg/12mg）"),
("drug_verapamil", "维拉帕米推注"),
("drug_isoproterenol", "异丙肾推注"),
("drug_lidocaine", "利多卡因推注"),

# 外部物理作用
("esophageal_pace", "食道调搏（rate, current_mA, mode）"),
("valsalva", "Valsalva 动作（pressure_mmHg, duration_sec）"),
("breath_hold", "憋气（duration_sec）"),
("squat", "下蹲动作"),
("stand", "站立动作"),
("supine", "平卧"),
("external_compression", "外力压迫心脏（force_N, area_cm2）"),
("cough", "咳嗽（诱发/终止心律失常）"),

# 负荷试验
("start_protocol", "开始负荷试验协议（bruce | modified_bruce）"),
("stop_protocol", "停止负荷试验"),

# 模式
("set_engine_mode", "切换引擎模式（myocardium | legacy）"),
```

### Pipeline._run_one_beat() 新流程

```text
1.  Accumulate exercise state (现有)
2.  Update respiratory / gas exchange (现有)
3.  HRV offset (现有)
4.  QT dynamics (现有)
5.  ST evolution (现有)
6.  Scenario models (现有 - 出血/败血症等)
    ↓
7.  [NEW] Apply physical actions to hemodynamics:
    7a. ExternalPhysicalAction → PhysioMechanicalMapper.apply()
    7b. → preload_modifier / afterload_modifier
    7c. → External pacemakers registered
    7d. → Mechanical PVC probability
    7e. Posture → venous_return_factor
    7f. Thoracic pressure → intrathoracic_pressure → preload
    ↓
8.  [NEW] Apply upper-layer effects to MyocardiumState:
    8a. Exercise → sinus_rate, symp_tone
    8b. Drugs → AVN ERP/CV, DAD susceptibility
    8c. Electrolytes → ERP, CV, EAD susceptibility
    8d. Emotion → symp_tone
    8e. Ischemia → ventricular_erp, erp_dispersion
    ↓
9.  [NEW] AutonomicTissueMapper.apply(myocardium_state, symp, para)
    ↓
10. [NEW] Evaluate arrhythmia maintenance conditions:
    - 如果 pacemaker.conditions 不满足 → pacemaker 终止
    - 如果 ArrhythmiaCommand 激活 → 配置新 pacemaker
    - 外部 pacing pacemaker 按 pacing_mode 配置
    ↓
11. [NEW] PacemakerCompetition.resolve(t, dt) → CompetitionResult
    ↓
12. Existing: Conduction network with CompetitionResult
13. Existing: ECG synthesize
14. Existing: PCG synthesize
15. Existing: Hemodynamics — 使用 PhysioMechanicalMapper 输出的 preload/afterload
16. Existing: Coronary update
17. Existing: Update modulation (ANS, PK, transitions)
    — Baroreflex 接收 Hemodynamics 输出的 MAP → 反馈调节 symp/para
    — 闭合物理→血流动力学→神经→电生理 的完整反馈环
```

### 模式切换（向后兼容）

```python
# 在 SimulationPipeline.__init__ 中：
self.engine_mode: str = 'myocardium'  # 'myocardium' | 'legacy'

# set_engine_mode 命令可热切换
```

- `myocardium` 模式：使用 MyocardiumState → PacemakerCompetition 全路径
- `legacy` 模式：使用现有 CausalGraph → 5 modifiers → rhythm_override 路径，行为不
  变

### 现有 CausalGraph 的定位

CausalGraph 在 `myocardium` 模式下仍然发挥作用——它计算 `sympathetic_tone` 和
`parasympathetic_tone`，这两个值输入到 `AutonomicTissueMapper`。现有 graph 中的
`exercise_effects`、`drug_effects` 节点也继续工作，只是输出目标从 5 个 modifier
变成 MyocardiumState 的字段。

## 11. 文件清单

### 新增文件

| 文件 | 职责 |
|------|------|
| `backend/app/engine/myocardium/__init__.py` | 包初始化 |
| `backend/app/engine/myocardium/state.py` | MyocardiumState 数据类 |
| `backend/app/engine/myocardium/autonomic_mapper.py` | AutonomicTissueMapper |
| `backend/app/engine/myocardium/pacemaker.py` | Pacemaker 数据类 + PacemakerKind/PacemakerLife |
| `backend/app/engine/myocardium/competition.py` | PacemakerCompetition + CompetitionResult |
| `backend/app/engine/myocardium/electrotonic.py` | ElectrotonicModel |
| `backend/app/engine/myocardium/physio_mechanical.py` | ExternalPhysicalAction 类型 + PhysioMechanicalMapper |
| `backend/app/engine/myocardium/thoracic_pressure.py` | ThoracicPressureModel（Valsalva 四相） |
| `backend/app/engine/myocardium/external_compression.py` | ExternalCompressionModel |
| `backend/app/engine/myocardium/mechano_electrical.py` | MechanoElectricalFeedbackModel（牵张→DAD/EAD/离散度） |
| `backend/app/engine/myocardium/external_pacing.py` | 食道调搏/经皮起搏 Pacemaker 工厂 |
| `backend/app/engine/myocardium/exercise_protocol.py` | 平板负荷试验协议（Bruce 等） |
| `backend/app/engine/myocardium/pipeline_integration.py` | Pipeline 集成函数 |

### 改造文件

| 文件 | 变更 |
|------|------|
| `engine/simulation/pipeline.py` | _run_one_beat 流程改造，新增命令，模式切换，物理作用集成 |
| `engine/modulation/interaction_state.py` | 移除 rhythm_override/hr_override，新增 arrhythmia_command/intervention/physical_action |
| `engine/modulation/transition_engine.py` | 新增 TransitionConfig 用于新字段 |
| `engine/core/parametric_conduction.py` | 改造为接收 CompetitionResult，移除 substrate 随机触发 |
| `engine/core/types.py` | BeatKind / PWaveMode 扩展（新增 paced、fusion） |
| `engine/modulation/causal_graph.py` | 输出交感/副交感张力（已有），调整 drug_effects 节点输出到 MyocardiumState |
| `engine/modulation/physiology_modulator.py` | 新增 myocardium 模式分支 |
| `engine/core/algebraic_hemo.py` | 接收 MechanicalEffect 的 preload/afterload 修正 |
| `engine/__init__.py` | 导出新模块 |
| `engine/constants.py` | 新增生理参数基线值 |

### 测试文件

| 文件 | 内容 |
|------|------|
| `tests/test_myocardium_state.py` | MyocardiumState 单位测试，生理范围验证 |
| `tests/test_autonomic_mapper.py` | ANS→组织映射正确性，cardiac conflict 场景 |
| `tests/test_pacemaker_competition.py` | 单起搏点、竞争、融合、隐匿传导、二联律/三联律涌现 |
| `tests/test_physio_mechanical.py` | 体位/胸内压/外力压迫的机械效应映射 |
| `tests/test_thoracic_pressure.py` | Valsalva 四相模型正确性 |
| `tests/test_external_pacing.py` | 食道调搏：捕获概率、burst/ramp/overdrive 模式 |
| `tests/test_external_compression.py` | 外压→前负荷+机械刺激 |
| `tests/test_mechano_electrical.py` | 机械-电反馈：牵张→DAD/EAD + 儿茶酚胺协同 |
| `tests/test_exercise_protocol.py` | Bruce 协议推进、METs→intensity 映射 |
| `tests/test_myocardium_integration.py` | Pipeline 集成测试（运动+SVT、Valsalva+下蹲、药物+电击等组合） |
| `tests/test_physiology_invariants.py` | 生理不变量（扩充现有） |

## 12. 测试策略

### 生理不变量

```python
# 即使在心律失常下也必须满足的不变量：
def test_sinus_rate_physiological_range():
    """sinus_rate 始终在 20-250 bpm 内。"""

def test_erp_never_negative():
    """所有不应期必须 >= 0。"""

def test_no_two_winners_per_beat():
    """每个心动周期只能有一个主导起搏点。"""

def test_capture_resets_unprotected():
    """捕获必须重置未保护起搏点的周期。"""

def test_protected_pacemaker_independent():
    """并行心律起搏点不受捕获影响。"""

def test_sinus_is_always_active():
    """窦房结 pacemaker 始终存在。"""

def test_preload_stays_positive():
    """前负荷乘数始终 > 0（机械作用不会把 venous_return 压到负值）。"""

def test_valsalva_four_phases_order():
    """Valsalva 动作必须经过 Phase I→II→III→IV 的时序。"""
```

### 电生理场景测试

```python
async def test_exercise_ramp_up_sinus_rate():
    """运动强度增加→交感↑→sinus_rate 平滑上升。"""

async def test_svt_during_exercise_natural_competition():
    """运动+AVNRT：交感改变 AVN ERP→可能终止或加速 AVNRT，
    更快的起搏点胜出。"""

async def test_cardioversion_on_normal_sinus():
    """低能量（5J）电复律对正常窦律：
    - 落在不应期外可能诱发 PVC/短阵 VT
    - 概率随能量增加
    - 概率 = f(能量, 心肌不应期相位)"""

async def test_adenosine_terminates_avnrt():
    """腺苷→副交感激活→AVN ERP↑→AVNRT 终止。"""

async def test_hyperkalemia_widens_qrs():
    """高钾→传导速度↓→QRS 增宽→心室 ERP↓。"""

async def test_bigeminy_emerges_from_competition():
    """二联律不是硬编码——是 PVC pacemaker + 窦房结 pacemaker 竞争的自然结果。
    验证：20 个心搏中 winner 序列为 sinus/pvc/sinus/pvc 交替。"""

async def test_trigeminy_emerges_from_competition():
    """三联律：每第三搏为 PVC。验证 pattern = sinus/sinus/pvc 重复。"""

async def test_bigeminy_suppressed_by_exercise():
    """运动→窦性加速→当 sinus rate 快到覆盖 PVC coupling_interval 时，
    PVC 被抑制，二联律消失。"""
```

### 物理作用场景测试

```python
async def test_valsalva_bradycardia_overshoot():
    """Valsalva Phase IV → BP 反跳 → baroreflex → 窦性心率骤降 15-30bpm。"""

async def test_squat_increases_venous_return():
    """下蹲 → venous_return_factor 1.3 → preload↑ → SV↑ → MAP↑ → baroreflex HR↓。"""

async def test_stand_decreases_venous_return():
    """站立 → venous_return_factor 0.7 → preload↓ → baroreflex HR↑ (>15bpm 增加)。"""

async def test_breath_hold_squat_exhale_sequence():
    """憋气 (Valsalva Phase II) + 下蹲 + 猛烈吐气：
    Phase II 胸内压↑ → venous_return↓ → CO↓ → MAP↓
    → 下蹲 → venous_return↑↑ → preload↑
    → 猛烈吐气 → 胸内压骤降 → 静脉回流突增 → BP 反跳 → 强力副交感激活 → HR 骤降
    预期：心率从高位（运动+憋气）骤降到远低于基线。"""

async def test_external_compression_pvc():
    """杯子压迫心前区 → mechanical_irritation > 0 → PVC 概率 > 0。
    验证：持续压迫时 PVC pacemaker 被注册到竞争。"""

async def test_esophageal_pacing_capture():
    """食道调搏 100bpm, 15mA → capture_prob ≈ 0.98 → pacing pacemaker 持续获胜。
    验证：主导节律 = 100bpm 外部起搏。"""

async def test_esophageal_burst_termination():
    """burst 起搏 (300bpm × 2s) 终止 AVNRT：
    burst → AVN 不应期被高频侵入 → 折返环阻断 → AVNRT pacemaker 条件破坏 → 终止。"""

async def test_cough_terminates_avnrt():
    """咳嗽 → 胸内压骤变 → 压敏反射 → 迷走短暂激活 → AVN ERP↑ → AVNRT 终止。"""

async def test_stretch_dad_no_catecholamine():
    """安静状态 → Valsalva+下蹲 → 牵张但低儿茶酚胺：
    dPreload/dt=0.7, catecholamine=0.0 → dad_delta < 0.1 → 几乎不诱发。"""

async def test_stretch_dad_high_catecholamine():
    """运动后 → Valsalva+下蹲 → 剧烈牵张 + 高儿茶酚胺：
    dPreload/dt=0.7, catecholamine=0.8 → dad_delta > 0.7 → 高概率 PVC+VT。"""

async def test_stretch_dad_multiplicative():
    """验证 DAD 易损性 = stretch_factor * catecholamine_factor 的乘法关系。
    单一因素都不足以触发，两者叠加才产生临床显著性。"""

async def test_rapid_preload_change_erp_dispersion():
    """不均匀牵张 → ERP 离散度↑ → 功能性折返条件满足。
    当 erp_dispersion > 0.4 → VT pacemaker 可维持。"""

async def test_post_exercise_valsalva_squat_vt_chain():
    """完整场景：剧烈运动刚结束 (catecholamine=0.8)
    → Valsalva 释放 (dPreload/dt=0.6)
    → 下蹲 (dPreload/dt=0.8 叠加)
    → MechanoElectricalFeedback: DAD↑ + ERP离散度↑
    → 多灶 PVC pacemakers + VT pacemaker
    → PacemakerCompetition: VT 胜出
    → 短阵 VT 持续 3-10 秒后自发终止（儿茶酚胺代谢 + preload 稳定）"""

async def test_intracardiac_needle_r_on_t_to_vf():
    """针尖心肌刺激 + TENS 100Hz 非同步脉冲：
    → capture_prob = 1.0（针尖直接在心肌内）
    → pacing_mode = 'asynchronous'
    → 每秒 100 个脉冲，每个心动周期约 85 个脉冲
    → 至少一个命中 T 波的概率 ≈ 99.8%
    → R-on-T → VF pacemaker 被注册
    → VF > 350bpm → 竞争必然获胜
    → ECG: 室颤波形 + 血流动力学崩溃"""

async def test_intracardiac_needle_low_rate_still_dangerous():
    """即使低频率 (10Hz) 针尖刺激，非同步性质仍危险：
    → 心率 70bpm 下每个心动周期约 8.5 个脉冲
    → p_at_least_one = 1 - 0.93^8.5 ≈ 0.47
    → 近 50% 概率在每次心搏中产生 R-on-T
    → VF 在数秒内几乎必然触发"""

async def test_bruce_protocol_progression():
    """Bruce 协议 0→3 min stage 1 → stage 2: intensity 应在每阶段递增。
    Stage 1 → 2 时 METs: 4.6 → 7.0 → intensity: 0.19 → 0.32。"""
```

## 13. 风险与缓解

| 风险 | 缓解 |
|------|------|
| 模型复杂度大幅增加，调试困难 | 每个新模块独立可测试，生理不变量锚定边界 |
| 性能：每搏多起搏点竞争开销 | Pacemaker 数量有限（通常 2-5 个），竞争算法 O(n) |
| 现有 ECG/PCG 波形走样 | 保留 legacy 模式开关，可即时回退 |
| Phase 1 范围膨胀 | Phase 1 限定：自主神经映射 + 基本竞争 + 体位（站立/下蹲/平卧）+ Valsalva + 食道调搏。杯子压迫和负荷试验可推迟到 Phase 2 |
| 物理-血流动力学耦合可能产生非生理震荡 | 严格的压力反射-血流动力学闭环验证（已有 validator.py 框架可扩展） |
| 外部起搏的 Pacemaker 行为不同于生物性起搏点 | `protected=True` 标志确保外部起搏不会因夺获重置，正确模拟电流源特性 |

## 14. Phase 2-3 预览

### Phase 2: 传导系统深化
- AVN 双径路显式建模（快径短 ERP 慢传导 / 慢径长 ERP 快传导）
- 旁路建模（WPW 预激，delta 波）
- 频率依赖性传导阻滞（3 相/4 相阻滞）
- Gap 现象（超常传导窗）
- 隐匿性传导完整建模
- G 力 / 加速度模型（重力对静脉回流的影响）
- 咳嗽完整生理链（压敏通道→迷走反射）

### Phase 3: 干预与药理扩展
- 电复律/除颤：能量-成功率-心肌损伤模型
- 药物扩展：腺苷、维拉帕米、异丙肾、利多卡因、多巴酚丁胺
- 药物交互：协同/拮抗（β-blocker+维拉帕米→严重负性肌力）
- 毒性建模：洋地黄→DAD→双向性室速，奎尼丁→QT 延长→TdP
- 缺血-再灌注心律失常
- 心包积液/填塞（外压模型的特殊案例）

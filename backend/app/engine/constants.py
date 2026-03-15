"""
虚拟人体引擎 — 常量与基线配置

所有采样率、推送间隔、生理参数范围、默认基线值集中定义于此。
"""
from __future__ import annotations

# ── 信号采样率 ─────────────────────────────────────────────────
ECG_SR = 500       # Hz  (与 simulate.py 一致)
PCG_SR = 4000      # Hz

# ── 流式推送 ──────────────────────────────────────────────────
CHUNK_INTERVAL_SEC = 0.1                      # 100 ms 推送一帧
ECG_CHUNK_SIZE = int(ECG_SR * CHUNK_INTERVAL_SEC)   # 50 samples
PCG_CHUNK_SIZE = int(PCG_SR * CHUNK_INTERVAL_SEC)   # 400 samples

# ── 缓冲区 ───────────────────────────────────────────────────
BUFFER_SECONDS = 30  # 环形缓冲区保留 30 秒信号

# ── 生理参数范围 (用于 clamp) ─────────────────────────────────
VITAL_RANGES = {
    "heart_rate":          (30.0,  300.0),
    "systolic_bp":         (60.0,  250.0),
    "diastolic_bp":        (30.0,  150.0),
    "spo2":                (50.0,  100.0),
    "temperature":         (34.0,   42.0),
    "respiratory_rate":    (4.0,    60.0),
    "exercise_intensity":  (0.0,    1.0),
    "emotional_arousal":   (0.0,    1.0),
    "damage_level":        (0.0,    1.0),
    "murmur_severity":     (0.0,    1.0),
    # ── Phase 1.1 新增参数 ──
    "fatigue_accumulated": (0.0,    1.0),
    "caffeine_level":      (0.0,    1.0),
    "alcohol_level":       (0.0,    1.0),
    "dehydration_level":   (0.0,    1.0),
    "sleep_debt":          (0.0,    1.0),
    "sympathetic_tone":    (0.0,    1.0),
    "parasympathetic_tone": (0.0,   1.0),
    "ectopic_irritability": (0.0,   1.0),
    # ── Phase 4 药物与电解质 ──
    "beta_blocker_level":  (0.0,    1.0),
    "amiodarone_level":    (0.0,    1.0),
    "digoxin_level":       (0.0,    1.0),
    "atropine_level":      (0.0,    1.0),
    "potassium_level":     (3.0,    7.0),
    "calcium_level":       (6.0,   14.0),
    "fitness_level":       (0.0,    1.0),
}

# ── 默认时间常数 τ (秒)，决定参数趋近目标的速度 ─────────────
# current(t+dt) = current + (target - current) * (1 - exp(-dt/τ))
DEFAULT_TAU: dict[str, float] = {
    "heart_rate":           3.0,   # 自主神经 ~3-5s
    "systolic_bp":          8.0,   # 压力反射 ~10s
    "diastolic_bp":         8.0,
    "spo2":                15.0,   # 血红蛋白饱和度滞后
    "temperature":         60.0,   # 体温调节极慢
    "respiratory_rate":     4.0,   # 化学感受器
    "exercise_intensity":   2.0,   # 机械性递增
    "emotional_arousal":    1.5,   # 交感神经快速
    "damage_level":        10.0,   # 渐进性病变
    "murmur_severity":      5.0,   # 逐渐加重
    # ── Phase 1.1 新增参数 τ ──
    "fatigue_accumulated": 30.0,   # 疲劳缓慢累积/恢复
    "caffeine_level":      15.0,   # 咖啡因代谢
    "alcohol_level":       20.0,   # 酒精代谢
    "dehydration_level":   25.0,   # 脱水变化慢
    "sleep_debt":          60.0,   # 睡眠恢复极慢
    "sympathetic_tone":     2.0,   # 交感张力快速
    "parasympathetic_tone": 3.0,   # 副交感张力
    "ectopic_irritability": 5.0,   # 异位灶易激惹性
    # ── Phase 4 药物与电解质 τ ──
    "beta_blocker_level":  15.0,   # β-blocker 半衰期
    "amiodarone_level":    30.0,   # 胺碘酮 长半衰期
    "digoxin_level":       20.0,   # 地高辛 中等半衰期
    "atropine_level":      10.0,   # 阿托品 短半衰期
    "potassium_level":     30.0,   # 钾离子正常化缓慢
    "calcium_level":       30.0,   # 钙离子正常化缓慢
    "fitness_level":       600.0,  # 体能变化极慢（训练效应）
}

# ── 静息基线 (健康成人) ───────────────────────────────────────
BASELINE_STATE: dict[str, float | str | None] = {
    "heart_rate":           72.0,
    "systolic_bp":         120.0,
    "diastolic_bp":         80.0,
    "spo2":                 98.0,
    "temperature":          36.6,
    "respiratory_rate":     16.0,
    "exercise_intensity":    0.0,
    "emotional_arousal":     0.0,
    "damage_level":          0.0,
    "murmur_severity":       0.0,
    # ── Phase 1.1 新增参数基线 ──
    "fatigue_accumulated":   0.0,
    "caffeine_level":        0.0,
    "alcohol_level":         0.0,
    "dehydration_level":     0.0,
    "sleep_debt":            0.0,
    "sympathetic_tone":      0.5,
    "parasympathetic_tone":  0.5,
    "ectopic_irritability":  0.0,
    # ── Phase 4 药物与电解质基线 ──
    "beta_blocker_level":    0.0,
    "amiodarone_level":      0.0,
    "digoxin_level":         0.0,
    "atropine_level":        0.0,
    "potassium_level":       4.0,
    "calcium_level":         9.5,
    "fitness_level":         0.5,   # 中等体能
    "age":                   30,    # 默认年龄
    # 离散状态
    "rhythm":               "normal",
    "murmur_type":          None,
    "pvc_pattern":          "isolated",
}

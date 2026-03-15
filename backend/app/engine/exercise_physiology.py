"""
运动生理模型 — 基于真实心肺生理学的运动心率响应。

核心公式：
  HR_delta = HR_reserve × intensity_factor × (1 - fitness_discount) × drift × fatigue_boost × dehydration_boost

关键生理概念：
- Tanaka 公式：HR_max = 208 - 0.7 × age
- Karvonen 公式：HR_target = HR_rest + %intensity × HR_reserve
- Cardiac drift：长时间亚极量运动中 HR 持续上升（~3-5% per hour）
- 体能影响：VO2max 越高 → 相同强度下 HR 占 HR_reserve 比例越低
- 疲劳代偿：肌肉疲劳 → 每搏量↓ → HR 代偿性↑
- 脱水效应：每 1% 体重丢失 → HR +7 bpm（血浆容量↓）
"""
from __future__ import annotations

import math


class ExercisePhysiologyModel:
    """运动心率响应模型。"""

    def __init__(
        self,
        age: float = 30.0,
        fitness_level: float = 0.5,
        resting_hr: float = 72.0,
    ) -> None:
        self.age = max(10.0, min(100.0, age))
        self.fitness_level = max(0.0, min(1.0, fitness_level))
        self.resting_hr = resting_hr

    @property
    def hr_max(self) -> float:
        """最大心率 (Tanaka 公式: 208 - 0.7 × age)。"""
        return 208.0 - 0.7 * self.age

    @property
    def hr_reserve(self) -> float:
        """心率储备 = HR_max - HR_rest。"""
        return max(10.0, self.hr_max - self.resting_hr)

    def compute_hr_delta(
        self,
        intensity: float,
        elapsed_sec: float,
        fatigue: float,
        dehydration: float,
    ) -> float:
        """计算运动导致的 HR 增量 (bpm)。返回 [0, hr_reserve]。"""
        if intensity <= 0.01:
            return 0.0

        intensity = max(0.0, min(1.0, intensity))

        # 1. 基础强度响应 — 轻度非线性（×0.8 基础缩放，使高强度 HR 处于生理范围）
        intensity_factor = 0.8 * (intensity ** 1.1)

        # 2. 体能折扣
        fitness_discount = 0.2 - 0.35 * self.fitness_level
        intensity_factor *= (1.0 + fitness_discount)

        # 3. 心率漂移 — 饱和曲线 tau=1200s
        drift_fraction = 1.0 - math.exp(-elapsed_sec / 1200.0)
        drift_factor = 1.0 + 0.18 * intensity * drift_fraction

        # 4. 疲劳代偿
        fatigue = max(0.0, min(1.0, fatigue))
        fatigue_factor = 1.0 + 0.18 * fatigue

        # 5. 脱水效应 (0-1 → 0-3% body weight → 0-21 bpm)
        dehydration = max(0.0, min(1.0, dehydration))
        dehydration_bpm = dehydration * 3.0 * 7.0

        hr_delta = (
            self.hr_reserve * intensity_factor * drift_factor * fatigue_factor
            + dehydration_bpm
        )

        return min(hr_delta, self.hr_reserve)

    def compute_fatigue_delta(
        self,
        intensity: float,
        dt: float,
        current_fatigue: float,
    ) -> float:
        """计算 dt 秒内的疲劳变化量。正=累积, 负=恢复。"""
        if intensity > 0.05:
            base_rate = 0.0005 * (intensity ** 1.5)
            fitness_factor = max(0.4, 1.0 - 0.6 * self.fitness_level)
            accumulation = base_rate * fitness_factor * dt
            accumulation *= max(0.0, 1.0 - current_fatigue)
            return accumulation
        else:
            base_recovery = 0.0002
            fitness_boost = 1.0 + self.fitness_level
            recovery = -base_recovery * fitness_boost * dt * current_fatigue
            return recovery

    def get_recovery_time_constants(
        self,
        pre_exercise_hr_delta: float,
        fatigue: float,
    ) -> tuple[float, float, float]:
        """获取运动后恢复的双指数时间常数。返回 (tau_fast, tau_slow, fast_fraction)。"""
        tau_fast = 60.0 - 30.0 * self.fitness_level
        tau_slow = 180.0 + 300.0 * fatigue + 120.0 * (pre_exercise_hr_delta / max(self.hr_reserve, 10.0))
        tau_slow = min(600.0, tau_slow)
        fast_fraction = 0.5 + 0.3 * self.fitness_level
        fast_fraction = min(0.85, fast_fraction)
        return tau_fast, tau_slow, fast_fraction

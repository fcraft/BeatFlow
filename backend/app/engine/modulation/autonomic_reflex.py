"""Enhanced autonomic reflex controller.

Implements multi-pathway autonomic regulation:
1. **Baroreceptor reflex**: MAP-based sigmoid → sympathetic/parasympathetic
2. **Chemoreceptor** (NEW): PaCO₂ / PaO₂ / pH → sympathetic drive
3. **Thermoregulation** (NEW): core temperature → HR/vasodilation
4. **Simplified RAAS** (NEW): low MAP + low CO → angiotensin-mediated TPR/preload
5. **Circuit breaker**: cumulative change limiter

Reference:
- Guyton & Hall. Textbook of Medical Physiology, Ch. 18 (Nervous Regulation).
- Schmidt & Thews. Human Physiology, Ch. 20 (Chemoreceptors).
"""
from __future__ import annotations

import math
from typing import Any


class AutonomicReflexController:
    """Enhanced autonomic reflex controller with baroreceptor, chemoreceptor,
    thermoregulation, and simplified RAAS pathways.
    """

    # ---- Baroreceptor ----
    MAP_SETPOINT: float = 93.0
    BARO_GAIN: float = 0.06

    # ---- Time constants ----
    TAU_SYMPATHETIC: float = 2.0
    TAU_PARASYMPATHETIC: float = 0.5

    # ---- Resting tones ----
    SYMP_REST: float = 0.5
    PARA_REST: float = 0.5

    # ---- Circuit breaker ----
    MAX_CHANGE_PER_BEAT: float = 0.1
    CIRCUIT_BREAKER_THRESHOLD: float = 0.4
    CIRCUIT_BREAKER_LIMIT: float = 0.05

    # ---- Chemoreceptor gains ----
    CHEMO_PACO2_GAIN: float = 0.02     # Per mmHg above 40
    CHEMO_PAO2_GAIN: float = 0.005     # Per mmHg below 80
    CHEMO_PH_GAIN: float = 1.5         # Per 0.1 pH below 7.35

    # ---- Thermoregulation ----
    THERMO_GAIN: float = 0.06          # Per °C above 37.0

    # ---- RAAS ----
    RAAS_TAU: float = 60.0             # Slow onset (seconds)
    RAAS_DECAY_TAU: float = 120.0      # Even slower decay

    def __init__(self) -> None:
        self._sympathetic: float = self.SYMP_REST
        self._parasympathetic: float = self.PARA_REST
        self._recent_changes: list[float] = []
        self._ans_fatigue: float = 0.0
        # RAAS state
        self._raas_activation: float = 0.0  # [0, 1]

    def update(
        self,
        map_mmhg: float,
        dt: float,
        *,
        cardiac_output: float = 5.0,
        spo2: float = 97.0,
        paco2: float = 40.0,
        pao2: float = 95.0,
        ph: float = 7.40,
        temperature: float = 36.6,
    ) -> tuple[float, float]:
        """Update ANS tones for one beat.

        Args:
            map_mmhg: Mean arterial pressure (mmHg).
            dt: RR interval (seconds).
            cardiac_output: Cardiac output (L/min).
            spo2: SpO₂ percentage (legacy compatibility).
            paco2: Arterial CO₂ partial pressure (mmHg).
            pao2: Arterial O₂ partial pressure (mmHg).
            ph: Arterial pH.
            temperature: Core body temperature (°C).

        Returns:
            (sympathetic_tone, parasympathetic_tone) both in [0, 1].
        """
        # ---- 1. Baroreceptor: MAP → firing rate ----
        deviation = map_mmhg - self.MAP_SETPOINT
        firing_rate = 1.0 / (1.0 + math.exp(-self.BARO_GAIN * deviation))

        symp_target = 1.0 - firing_rate
        para_target = firing_rate

        # ---- 2. Chemoreceptor: PaCO₂ / PaO₂ / pH → sympathetic ----
        chemo_drive = 0.0

        # Hypercapnia: PaCO₂ > 40 → sympathetic activation
        if paco2 > 40.0:
            chemo_drive += self.CHEMO_PACO2_GAIN * (paco2 - 40.0)

        # Hypoxia: PaO₂ < 80 → sympathetic activation (steep below 60)
        if pao2 < 80.0:
            chemo_drive += self.CHEMO_PAO2_GAIN * (80.0 - pao2)
            if pao2 < 60.0:
                chemo_drive += self.CHEMO_PAO2_GAIN * 2.0 * (60.0 - pao2)

        # Acidosis: pH < 7.35 → sympathetic activation
        if ph < 7.35:
            chemo_drive += self.CHEMO_PH_GAIN * (7.35 - ph)

        # Legacy SpO₂ pathway (backward compat)
        if spo2 < 97.0:
            chemo_drive += 0.03 * max(0.0, 97.0 - spo2)

        symp_target += chemo_drive

        # Low cardiac output → sympathetic
        if cardiac_output < 5.0:
            co_drive = 0.04 * max(0.0, 5.0 - cardiac_output)
            symp_target += co_drive

        # Chemoreceptor also activates parasympathetic (bradycardia reflex)
        # — mainly via PaO₂ (diving reflex analog)
        if pao2 < 60.0:
            para_target += 0.1 * min(1.0, (60.0 - pao2) / 30.0)

        # ---- 3. Thermoregulation ----
        if temperature > 37.0:
            # Hyperthermia → sympathetic activation + vasodilation
            delta_t = temperature - 37.0
            symp_target += self.THERMO_GAIN * delta_t
            # Cutaneous vasodilation reduces effective TPR (parasympathetic-like)
            para_target += 0.02 * delta_t
        elif temperature < 35.0:
            # Hypothermia → initial sympathetic activation (shivering)
            delta_t = 35.0 - temperature
            symp_target += 0.03 * delta_t
            # Severe hypothermia → bradycardia
            if temperature < 33.0:
                para_target += 0.1 * (33.0 - temperature)

        # ---- 4. Simplified RAAS ----
        # Low MAP and low CO activate renin release → angiotensin II
        raas_stimulus = 0.0
        if map_mmhg < 80.0:
            raas_stimulus += 0.02 * (80.0 - map_mmhg)
        if cardiac_output < 4.0:
            raas_stimulus += 0.05 * (4.0 - cardiac_output)

        # RAAS evolves slowly
        if raas_stimulus > self._raas_activation:
            raas_alpha = 1.0 - math.exp(-dt / self.RAAS_TAU)
        else:
            raas_alpha = 1.0 - math.exp(-dt / self.RAAS_DECAY_TAU)
        self._raas_activation += raas_alpha * (raas_stimulus - self._raas_activation)
        self._raas_activation = max(0.0, min(1.0, self._raas_activation))

        # RAAS → mild sympathetic activation + vasoconstriction (captured by symp)
        symp_target += 0.15 * self._raas_activation

        # ---- Clamp targets ----
        symp_target = max(0.0, min(1.0, symp_target))
        para_target = max(0.0, min(1.0, para_target))

        # ---- Exponential smoothing ----
        alpha_symp = 1.0 - math.exp(-dt / self.TAU_SYMPATHETIC)
        alpha_para = 1.0 - math.exp(-dt / self.TAU_PARASYMPATHETIC)

        new_symp = self._sympathetic + alpha_symp * (symp_target - self._sympathetic)
        new_para = self._parasympathetic + alpha_para * (para_target - self._parasympathetic)

        # ---- ANS fatigue ----
        if self._sympathetic > 0.7:
            fatigue_rate = (self._sympathetic - 0.7) / 0.3
            self._ans_fatigue = min(1.0, self._ans_fatigue + fatigue_rate * dt / 300.0)
        else:
            self._ans_fatigue = max(0.0, self._ans_fatigue - dt / 600.0)
        new_symp *= (1.0 - self._ans_fatigue * 0.4)

        # ---- Circuit breaker ----
        delta_symp = abs(new_symp - self._sympathetic)
        delta_para = abs(new_para - self._parasympathetic)
        total_delta = delta_symp + delta_para

        self._recent_changes.append(total_delta)
        if len(self._recent_changes) > 3:
            self._recent_changes.pop(0)

        cumulative = sum(self._recent_changes)
        max_change = self.CIRCUIT_BREAKER_LIMIT if cumulative > self.CIRCUIT_BREAKER_THRESHOLD else self.MAX_CHANGE_PER_BEAT

        d_symp = new_symp - self._sympathetic
        d_para = new_para - self._parasympathetic

        if abs(d_symp) > max_change:
            d_symp = max_change if d_symp > 0 else -max_change
        if abs(d_para) > max_change:
            d_para = max_change if d_para > 0 else -max_change

        self._sympathetic = max(0.0, min(1.0, self._sympathetic + d_symp))
        self._parasympathetic = max(0.0, min(1.0, self._parasympathetic + d_para))

        return (self._sympathetic, self._parasympathetic)

    @property
    def sympathetic_tone(self) -> float:
        return self._sympathetic

    @property
    def parasympathetic_tone(self) -> float:
        return self._parasympathetic

    @property
    def raas_activation(self) -> float:
        """Current RAAS activation level [0, 1]."""
        return self._raas_activation

    def get_state(self) -> dict[str, Any]:
        return {
            "sympathetic": self._sympathetic,
            "parasympathetic": self._parasympathetic,
            "recent_changes": list(self._recent_changes),
            "ans_fatigue": self._ans_fatigue,
            "raas_activation": self._raas_activation,
        }

    def set_state(self, state: dict[str, Any]) -> None:
        self._sympathetic = state.get("sympathetic", self.SYMP_REST)
        self._parasympathetic = state.get("parasympathetic", self.PARA_REST)
        self._recent_changes = list(state.get("recent_changes", []))
        self._ans_fatigue = state.get("ans_fatigue", 0.0)
        self._raas_activation = state.get("raas_activation", 0.0)

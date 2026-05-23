"""Chronic adaptation and drug tolerance model — Phase 3B.

Models long-term physiological adaptations that occur over hours to days,
as opposed to the beat-to-beat or minute-to-minute responses handled by
the CausalGraph.

Mechanisms:
  1. Chronic hypertension adaptation:
     - Sustained high SVR → LV hypertrophy → diastolic dysfunction
     - Over days-weeks: LV mass↑, compliance↓, LA pressure↑

  2. Drug tolerance (tachyphylaxis):
     - Sustained beta-blockade → β-receptor upregulation
     - Drug effect diminishes over days
     - Abrupt withdrawal → rebound tachycardia

  3. Deconditioning / bed rest:
     - Prolonged inactivity → baroreflex sensitivity↓
     - Orthostatic intolerance
     - Reduced exercise capacity

Usage:
    model = ChronicAdaptation()
    for each beat (or slower, e.g., every 60s):
        model.update(dt_sec, intent, modifiers)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class ChronicAdaptationState:
    """Snapshot of chronic adaptation status (serializable)."""

    # Hypertension adaptation
    lv_hypertrophy: float = 0.0            # 0-1 (relative LV mass increase)
    diastolic_dysfunction: float = 0.0     # 0-1 (impaired relaxation)
    la_pressure_increase_mmhg: float = 0.0 # Left atrial pressure rise

    # Drug tolerance
    beta_blocker_tolerance: float = 0.0    # 0-1 receptor upregulation
    beta_blocker_effective_dose: float = 0.0  # Effective concentration after tolerance

    # Deconditioning
    baroreflex_sensitivity: float = 1.0    # 1.0 = normal, <1.0 = impaired
    orthostatic_tolerance: float = 1.0     # 1.0 = normal, <1.0 = orthostatic intolerance

    def to_dict(self) -> dict:
        return {
            "lv_hypertrophy": round(self.lv_hypertrophy, 2),
            "diastolic_dysfunction": round(self.diastolic_dysfunction, 2),
            "la_pressure_increase_mmhg": round(self.la_pressure_increase_mmhg, 1),
            "beta_blocker_tolerance": round(self.beta_blocker_tolerance, 2),
            "baroreflex_sensitivity": round(self.baroreflex_sensitivity, 2),
            "orthostatic_tolerance": round(self.orthostatic_tolerance, 2),
        }


class ChronicAdaptation:
    """Models slow physiological adaptations (hours to weeks).

    Designed to be called less frequently than the beat loop — every
    60 seconds of simulation time is sufficient for most adaptations.

    Time constants (tau):
      - LV hypertrophy:      7 days   (604,800 s)
      - Diastolic dysfunction: 14 days (1,209,600 s)
      - Beta-blocker tolerance: 3 days  (259,200 s)
      - Deconditioning:       5 days   (432,000 s)
      - Recovery:             14 days  (1,209,600 s)
    """

    TAU_HYPERTROPHY = 604_800.0      # 7 days
    TAU_DIASTOLIC = 1_209_600.0      # 14 days
    TAU_BB_TOLERANCE = 259_200.0     # 3 days
    TAU_DECONDITIONING = 432_000.0   # 5 days
    TAU_RECOVERY = 1_209_600.0       # 14 days

    def __init__(self) -> None:
        self._state = ChronicAdaptationState()

    @property
    def state(self) -> ChronicAdaptationState:
        return self._state

    # ------------------------------------------------------------------
    # Per-tick update (call every ~60s of sim time)
    # ------------------------------------------------------------------

    def update(
        self,
        dt_sec: float,
        modifiers: object,
        pharma_levels: dict[str, float] | None = None,
    ) -> None:
        """Advance chronic adaptations by dt_sec.

        Reads current modifiers to detect sustained hypertension or drug
        exposure, and updates internal adaptation state.
        """
        # --- Hypertension adaptation ---
        # Sustained high SVR (>1.3) → LV hypertrophy
        tpr = getattr(modifiers, 'tpr_modifier', 1.0)
        if tpr > 1.3:
            target_hypertrophy = min(1.0, (tpr - 1.0) * 3.0)
            alpha = 1.0 - np.exp(-dt_sec / self.TAU_HYPERTROPHY)
            self._state.lv_hypertrophy += alpha * (target_hypertrophy - self._state.lv_hypertrophy)
        elif tpr < 1.1:
            # Recovery
            alpha = 1.0 - np.exp(-dt_sec / self.TAU_RECOVERY)
            self._state.lv_hypertrophy += alpha * (0.0 - self._state.lv_hypertrophy)

        # LV hypertrophy → diastolic dysfunction + LA pressure↑
        self._state.diastolic_dysfunction = self._state.lv_hypertrophy * 0.8
        self._state.la_pressure_increase_mmhg = self._state.lv_hypertrophy * 8.0

        # Apply to modifiers
        if self._state.lv_hypertrophy > 0.05:
            # Hypertrophy reduces ventricular compliance → reduces preload effect
            modifiers.preload_modifier *= (1.0 - 0.15 * self._state.lv_hypertrophy)
            # Diastolic dysfunction impairs filling → slight contractility penalty
            modifiers.contractility_modifier *= (1.0 - 0.1 * self._state.diastolic_dysfunction)

        # --- Drug tolerance ---
        if pharma_levels:
            bb = pharma_levels.get("beta_blocker", 0.0)
            if bb > 0.01:
                # Sustained beta-blockade → receptor upregulation
                alpha_bb = 1.0 - np.exp(-dt_sec / self.TAU_BB_TOLERANCE)
                self._state.beta_blocker_tolerance += alpha_bb * (
                    min(1.0, bb * 2.0) - self._state.beta_blocker_tolerance
                )
            else:
                # Withdrawal → tolerance slowly fades
                alpha_bb = 1.0 - np.exp(-dt_sec / (self.TAU_BB_TOLERANCE * 2.0))
                self._state.beta_blocker_tolerance += alpha_bb * (
                    0.0 - self._state.beta_blocker_tolerance
                )

            # Tolerance reduces effective drug concentration
            self._state.beta_blocker_effective_dose = bb * (1.0 - 0.5 * self._state.beta_blocker_tolerance)

            # If drug withdrawn while tolerance exists → rebound
            if bb < 0.01 and self._state.beta_blocker_tolerance > 0.1:
                # Rebound tachycardia from unopposed receptor upregulation
                rebound = self._state.beta_blocker_tolerance * 0.3
                modifiers.sa_rate_modifier *= (1.0 + rebound)
                logger.debug(
                    "BB withdrawal rebound: tolerance=%.2f, HR rebound=%.2f",
                    self._state.beta_blocker_tolerance, rebound,
                )

        # --- Deconditioning ---
        ex = getattr(modifiers, 'exercise_intensity', 0.0)
        if ex < 0.1:
            # Sedentary → gradual deconditioning
            alpha_decond = 1.0 - np.exp(-dt_sec / self.TAU_DECONDITIONING)
            self._state.baroreflex_sensitivity += alpha_decond * (
                0.5 - self._state.baroreflex_sensitivity
            )
            self._state.orthostatic_tolerance += alpha_decond * (
                0.4 - self._state.orthostatic_tolerance
            )
        elif ex > 0.5:
            # Regular exercise → maintains or improves conditioning
            alpha_recov = 1.0 - np.exp(-dt_sec / self.TAU_RECOVERY)
            self._state.baroreflex_sensitivity += alpha_recov * (
                1.0 - self._state.baroreflex_sensitivity
            )
            self._state.orthostatic_tolerance += alpha_recov * (
                1.0 - self._state.orthostatic_tolerance
            )

    def reset(self) -> None:
        """Reset all adaptations to baseline."""
        self._state = ChronicAdaptationState()

"""Hypovolemia / Hemorrhage model — Phase 3B.

Models progressive blood volume loss and its compensatory physiological
responses.  Intended to be called per-beat in the pipeline to update
Modifiers fields based on internal hemorrhage state.

Physiology:
  1. Volume loss → venous return↓ → preload↓ → SV↓ → CO↓ → MAP↓
  2. Compensatory: baroreflex → HR↑ + SVR↑ (handled by CausalGraph)
  3. Hormonal: RAAS activation (handled by CausalGraph)
  4. Progressive: ongoing bleed → worsening state if not stopped

Usage:
    model = HypovolemiaModel(blood_volume_ml=5000)
    model.start_hemorrhage(rate_ml_per_min=50.0)
    for each beat:
        model.update(rr_sec, modifiers)  # modifies preload_modifier, etc.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class HypovolemiaState:
    """Snapshot of current hypovolemia status (serializable)."""

    active: bool = False
    total_volume_ml: float = 5000.0        # Current estimated blood volume
    initial_volume_ml: float = 5000.0       # Starting blood volume
    blood_loss_ml: float = 0.0              # Cumulative loss
    hemorrhage_rate_ml_per_min: float = 0.0 # Current bleed rate
    preload_factor: float = 1.0             # Multiplier on preload
    compensation_hr_bpm: float = 0.0        # HR increase from compensation
    compensation_svr_factor: float = 1.0    # SVR increase from compensation
    phase: str = "none"                     # none / class_I / class_II / class_III / class_IV

    def to_dict(self) -> dict:
        return {
            "active": self.active,
            "total_volume_ml": round(self.total_volume_ml, 0),
            "blood_loss_ml": round(self.blood_loss_ml, 0),
            "hemorrhage_rate_ml_per_min": round(self.hemorrhage_rate_ml_per_min, 1),
            "preload_factor": round(self.preload_factor, 3),
            "compensation_hr_bpm": round(self.compensation_hr_bpm, 1),
            "compensation_svr_factor": round(self.compensation_svr_factor, 2),
            "phase": self.phase,
        }


class HypovolemiaModel:
    """Progressive hemorrhage model with compensatory physiology.

    Models 4 classes of hemorrhagic shock based on % blood volume loss:
      Class I:   <15%  — minimal signs, compensated
      Class II:  15-30% — tachycardia, narrowed pulse pressure
      Class III: 30-40% — hypotension, marked tachycardia, oliguria
      Class IV:  >40%  — severe hypotension, cardiovascular collapse

    The model updates Modifiers.preload_modifier each beat.  The baroreflex
    and RAAS compensation are handled by the CausalGraph reacting to the
    resulting MAP drop, so this module only needs to model the primary
    volume→preload→SV→CO→MAP chain.
    """

    def __init__(self, blood_volume_ml: float = 5000.0) -> None:
        self._state = HypovolemiaState(
            total_volume_ml=blood_volume_ml,
            initial_volume_ml=blood_volume_ml,
        )

    @property
    def state(self) -> HypovolemiaState:
        return self._state

    @property
    def active(self) -> bool:
        return self._state.active

    # ------------------------------------------------------------------
    # Control
    # ------------------------------------------------------------------

    def start_hemorrhage(self, rate_ml_per_min: float = 50.0) -> None:
        """Begin active hemorrhage at the given bleed rate."""
        self._state.active = True
        self._state.hemorrhage_rate_ml_per_min = max(0.0, rate_ml_per_min)
        logger.info(
            "Hemorrhage started: rate=%.0f mL/min, initial volume=%.0f mL",
            rate_ml_per_min, self._state.total_volume_ml,
        )

    def stop_hemorrhage(self) -> None:
        """Stop active bleeding (e.g., tourniquet applied, surgical control)."""
        self._state.hemorrhage_rate_ml_per_min = 0.0
        logger.info("Hemorrhage stopped: total loss=%.0f mL", self._state.blood_loss_ml)

    def administer_fluids(self, volume_ml: float) -> None:
        """Administer IV fluid bolus (crystalloid/colloid)."""
        # Crystalloids: ~25% stays intravascular after 30min
        effective = volume_ml * 0.3
        self._state.total_volume_ml = min(
            self._state.initial_volume_ml * 1.3,
            self._state.total_volume_ml + effective,
        )
        self._state.blood_loss_ml = max(
            0.0, self._state.blood_loss_ml - effective,
        )
        logger.info(
            "Fluid bolus: %.0f mL (effective %.0f mL), volume now %.0f mL",
            volume_ml, effective, self._state.total_volume_ml,
        )

    def reset(self) -> None:
        """Reset to normal blood volume."""
        self._state = HypovolemiaState(
            total_volume_ml=self._state.initial_volume_ml,
            initial_volume_ml=self._state.initial_volume_ml,
        )

    # ------------------------------------------------------------------
    # Per-beat update
    # ------------------------------------------------------------------

    def update(self, dt_sec: float, modifiers: object) -> None:
        """Advance hemorrhage model by one beat.

        Modifies modifiers.preload_modifier in-place.  Also adjusts
        modifiers.sympathetic_tone slightly to model the direct baroreflex
        compensation (in addition to what the CausalGraph computes from MAP).
        """
        if not self._state.active:
            return

        # Blood loss
        loss_this_beat = self._state.hemorrhage_rate_ml_per_min * dt_sec / 60.0
        self._state.total_volume_ml = max(500.0, self._state.total_volume_ml - loss_this_beat)
        self._state.blood_loss_ml += loss_this_beat

        # Volume loss fraction
        loss_frac = self._state.blood_loss_ml / self._state.initial_volume_ml

        # Preload reduction: venous return ↓ as volume ↓
        # Exponential relationship: small losses have small effect,
        # large losses cause precipitous drop
        if loss_frac < 0.15:
            self._state.preload_factor = 1.0 - 0.5 * loss_frac
        else:
            self._state.preload_factor = max(
                0.15, 0.925 - 0.8 * (loss_frac - 0.15) ** 0.7
            )

        # Shock class
        if loss_frac < 0.15:
            self._state.phase = "class_I"
            self._state.compensation_hr_bpm = 10.0 * loss_frac / 0.15
            self._state.compensation_svr_factor = 1.0 + 0.1 * loss_frac / 0.15
        elif loss_frac < 0.30:
            self._state.phase = "class_II"
            self._state.compensation_hr_bpm = 10.0 + 20.0 * (loss_frac - 0.15) / 0.15
            self._state.compensation_svr_factor = 1.1 + 0.2 * (loss_frac - 0.15) / 0.15
        elif loss_frac < 0.40:
            self._state.phase = "class_III"
            self._state.compensation_hr_bpm = 30.0 + 20.0 * (loss_frac - 0.30) / 0.10
            self._state.compensation_svr_factor = 1.3 + 0.3 * (loss_frac - 0.30) / 0.10
        else:
            self._state.phase = "class_IV"
            self._state.compensation_hr_bpm = min(50.0, 50.0 + 20.0 * (loss_frac - 0.40) / 0.10)
            self._state.compensation_svr_factor = min(2.0, 1.6 + 0.4 * (loss_frac - 0.40) / 0.10)

        # Apply to modifiers
        modifiers.preload_modifier *= self._state.preload_factor

        if self._state.blood_loss_ml % 100.0 < loss_this_beat:
            logger.debug(
                "Hemorrhage: %.0f mL lost (%.0f%%), phase=%s, preload=%.2f",
                self._state.blood_loss_ml, loss_frac * 100,
                self._state.phase, self._state.preload_factor,
            )

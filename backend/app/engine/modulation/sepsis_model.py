"""Sepsis model.

Models the progression from early (hyperdynamic / warm) to late
(hypodynamic / cold) septic shock.

Physiology:
  Early (warm shock, 0-6h):
    - Systemic vasodilation → SVR↓ (pathological)
    - Compensatory ↑HR + ↑CO to maintain MAP
    - Wide pulse pressure, bounding pulses
    - Warm extremities, flushed skin

  Late (cold shock, 6-24h+):
    - Myocardial depression → CO↓
    - Persistent vasodilation + pump failure → MAP↓↓
    - Lactic acidosis → chemoreflex activation
    - Cold extremities, mottled skin
    - Multi-organ dysfunction

Usage:
    model = SepsisModel()
    model.start_sepsis(severity=0.7)
    for each beat:
        model.update(rr_sec, modifiers)  # modifies tpr_modifier, contractility
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class SepsisState:
    """Snapshot of current sepsis status (serializable)."""

    active: bool = False
    severity: float = 0.0               # 0-1 (pathogen load / immune response)
    elapsed_hours: float = 0.0          # Time since sepsis onset
    phase: str = "none"                 # early / late / resolving
    svr_factor: float = 1.0            # Multiplier on SVR (↓ in sepsis)
    myocardial_depression: float = 0.0  # 0-1 contractility reduction
    lactate_mmol: float = 1.0          # Serum lactate (normal <2.0)
    temperature_c: float = 37.0        # Core temperature

    def to_dict(self) -> dict:
        return {
            "active": self.active,
            "severity": round(self.severity, 2),
            "elapsed_hours": round(self.elapsed_hours, 2),
            "phase": self.phase,
            "svr_factor": round(self.svr_factor, 3),
            "myocardial_depression": round(self.myocardial_depression, 2),
            "lactate_mmol": round(self.lactate_mmol, 1),
            "temperature_c": round(self.temperature_c, 1),
        }


class SepsisModel:
    """Progressive sepsis model with early→late phase transition.

    Severity (0-1) controls speed of progression:
      - 0.3: mild, compensated
      - 0.5: moderate, gradual progression to late phase
      - 0.8: severe, rapid decompensation
    """

    EARLY_DURATION_H = 6.0    # Hours before late-phase transition begins
    LATE_TRANSITION_H = 12.0  # Hours to full late-phase

    def __init__(self) -> None:
        self._state = SepsisState()

    @property
    def state(self) -> SepsisState:
        return self._state

    @property
    def active(self) -> bool:
        return self._state.active

    # ------------------------------------------------------------------
    # Control
    # ------------------------------------------------------------------

    def start_sepsis(self, severity: float = 0.5) -> None:
        """Initiate septic process with given severity [0-1]."""
        self._state.active = True
        self._state.severity = max(0.1, min(1.0, severity))
        self._state.elapsed_hours = 0.0
        self._state.phase = "early"
        self._state.lactate_mmol = 1.0 + 1.5 * severity
        logger.info("Sepsis started: severity=%.2f", severity)

    def resolve_sepsis(self) -> None:
        """Begin resolution (e.g., antibiotics + source control)."""
        self._state.phase = "resolving"
        logger.info("Sepsis resolving at %.1f h", self._state.elapsed_hours)

    def reset(self) -> None:
        """Reset to non-septic state."""
        self._state = SepsisState()

    # ------------------------------------------------------------------
    # Per-beat update
    # ------------------------------------------------------------------

    def update(self, dt_sec: float, modifiers: object) -> None:
        """Advance sepsis model by one beat.

        Modifies modifiers.tpr_modifier, modifiers.contractility_modifier,
        and modifiers.temperature in-place.
        """
        if not self._state.active:
            return

        sev = self._state.severity

        # Advance time (scaled by severity)
        self._state.elapsed_hours += dt_sec / 3600.0 * sev

        elapsed = self._state.elapsed_hours

        # Phase determination
        if self._state.phase == "resolving":
            # Gradual recovery
            recovery_progress = min(1.0, (elapsed - self._state.elapsed_hours
                                          + dt_sec / 3600) / 24.0)
            self._state.svr_factor = self._state.svr_factor + 0.01 * (1.0 - self._state.svr_factor)
            self._state.myocardial_depression *= 0.99
            self._state.lactate_mmol *= 0.995
            if recovery_progress > 0.8:
                self._state.phase = "none"
                self._state.active = False
        elif elapsed < self.EARLY_DURATION_H:
            # Early (warm) phase: vasodilation dominates
            self._state.phase = "early"
            progress = elapsed / self.EARLY_DURATION_H

            # SVR drops progressively
            self._state.svr_factor = 1.0 - 0.5 * sev * progress

            # Minimal myocardial depression yet
            self._state.myocardial_depression = 0.05 * sev * progress

            # Lactate rises slowly
            self._state.lactate_mmol = (1.0 + 1.5 * sev
                                        + 1.0 * sev * progress)

            # Fever
            self._state.temperature_c = 37.0 + 2.0 * sev * progress

        else:
            # Late (cold) phase: myocardial depression emerges
            self._state.phase = "late"
            late_progress = min(
                1.0,
                (elapsed - self.EARLY_DURATION_H) / self.LATE_TRANSITION_H,
            )

            # SVR stays low
            self._state.svr_factor = max(
                0.3, 1.0 - 0.5 * sev - 0.15 * sev * late_progress,
            )

            # Myocardial depression worsens
            self._state.myocardial_depression = min(
                0.6, 0.05 * sev + 0.55 * sev * late_progress,
            )

            # Lactate climbs with organ hypoperfusion
            self._state.lactate_mmol = (
                1.0 + 1.5 * sev + 3.0 * sev * late_progress
            )

            # Temperature may drop as shock deepens
            self._state.temperature_c = (
                37.0 + 2.0 * sev - 3.0 * sev * late_progress
            )

        # Apply to modifiers
        modifiers.tpr_modifier *= self._state.svr_factor
        modifiers.contractility_modifier *= (1.0 - self._state.myocardial_depression)

        if self._state.temperature_c > 37.5:
            modifiers.temperature = max(
                modifiers.temperature, self._state.temperature_c,
            )

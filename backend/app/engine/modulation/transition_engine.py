"""Transition engine — exponential smoothing for interaction parameter changes.

The ``TransitionSmoother`` takes a target ``InteractionState`` (the user's
intent) and smooths numeric parameters over time using exponential decay,
so that parameter changes ramp gradually instead of snapping instantly.

Each parameter has its own ``TransitionConfig`` that defines:
- ``tau_seconds``: time constant (63% convergence in tau seconds)
- ``instant``: if True, no smoothing is applied (e.g., rhythm_override)
"""
from __future__ import annotations

import math
from dataclasses import dataclass, fields
from typing import Any

from app.engine.modulation.interaction_state import InteractionState


@dataclass(frozen=True)
class TransitionConfig:
    """Per-parameter transition timing."""
    tau_seconds: float = 2.0
    instant: bool = False


# ---------------------------------------------------------------------------
# Default transition configs — organized by category
# ---------------------------------------------------------------------------

TRANSITION_CONFIGS: dict[str, TransitionConfig] = {
    # ------ Instant (structural / rhythm changes) ------
    'rhythm_override':       TransitionConfig(instant=True),
    'av_block_degree':       TransitionConfig(instant=True),
    'pvc_pattern':           TransitionConfig(instant=True),
    'defibrillation_count':  TransitionConfig(instant=True),
    'murmur_type':           TransitionConfig(instant=True),

    # ------ Fast transitions (0.5–2 sec) ------
    'emotional_arousal':     TransitionConfig(tau_seconds=1.0),
    'hr_override':           TransitionConfig(tau_seconds=1.5),

    # ------ Medium transitions (2–5 sec) ------
    'exercise_intensity':    TransitionConfig(tau_seconds=3.0),
    'caffeine_level':        TransitionConfig(tau_seconds=2.0),
    'alcohol_level':         TransitionConfig(tau_seconds=2.0),
    'dehydration_level':     TransitionConfig(tau_seconds=3.0),
    'temperature':           TransitionConfig(tau_seconds=5.0),
    'damage_level':          TransitionConfig(tau_seconds=2.0),
    'fatigue_level':         TransitionConfig(tau_seconds=2.0),
    'sleep_debt':            TransitionConfig(tau_seconds=3.0),
    'preload_override':      TransitionConfig(tau_seconds=2.0),
    'contractility_override': TransitionConfig(tau_seconds=2.0),
    'tpr_override':          TransitionConfig(tau_seconds=2.0),
    'chest_wall_attenuation': TransitionConfig(tau_seconds=1.0),

    # ------ Slow transitions (5–15 sec) ------
    'murmur_severity':       TransitionConfig(tau_seconds=5.0),
    'potassium_level':       TransitionConfig(tau_seconds=8.0),
    'calcium_level':         TransitionConfig(tau_seconds=8.0),
    'magnesium_level':       TransitionConfig(tau_seconds=8.0),
    'fio2':                  TransitionConfig(tau_seconds=3.0),
    'coronary_stenosis':     TransitionConfig(tau_seconds=10.0),
    'rv_contractility':      TransitionConfig(tau_seconds=3.0),
    'pulm_vascular_resistance': TransitionConfig(tau_seconds=5.0),
    'af_substrate':          TransitionConfig(tau_seconds=10.0),
    'svt_substrate':         TransitionConfig(tau_seconds=10.0),
    'vt_substrate':          TransitionConfig(tau_seconds=10.0),

    # ------ Autonomic overrides — fast ramp ------
    'sympathetic_tone_override':    TransitionConfig(tau_seconds=1.0),
    'parasympathetic_tone_override': TransitionConfig(tau_seconds=1.0),
    'sa_rate_modifier_override':     TransitionConfig(tau_seconds=1.5),
    'contractility_modifier_override': TransitionConfig(tau_seconds=2.0),
}


class TransitionSmoother:
    """Exponentially smooth ``InteractionState`` transitions.

    Usage::

        smoother = TransitionSmoother()
        # Each beat:
        smoothed = smoother.update(intent, rr_sec)
    """

    def __init__(self) -> None:
        self._current: dict[str, float] = {}

    def reset(self) -> None:
        """Clear all tracked values (e.g., on pipeline reset)."""
        self._current.clear()

    def update(self, intent: InteractionState, dt: float) -> InteractionState:
        """Return a smoothed copy of *intent* for this beat.

        Args:
            intent: The current user intent (target values).
            dt: Time elapsed since last beat (seconds, typically rr_sec).

        Returns:
            A new InteractionState with numeric fields smoothed toward
            their target values.
        """
        smoothed = InteractionState()

        for f in fields(intent):
            name = f.name
            target = getattr(intent, name)
            config = TRANSITION_CONFIGS.get(name)

            # Non-smoothable types: pass through directly
            if not isinstance(target, (int, float)) or target is None:
                setattr(smoothed, name, _deep_copy(target))
                continue

            # Instant or unconfigured fields: snap to target
            if config is None or config.instant:
                setattr(smoothed, name, target)
                self._current[name] = float(target)
                continue

            # Exponential smoothing
            current = self._current.get(name)
            if current is None:
                # First update — initialize from the dataclass default,
                # NOT from target, so the value ramps from default→target
                default_val = getattr(InteractionState(), name, 0.0)
                if isinstance(default_val, (int, float)) and default_val is not None:
                    current = float(default_val)
                else:
                    current = float(target)

            if config.tau_seconds > 0 and dt > 0:
                alpha = 1.0 - math.exp(-dt / config.tau_seconds)
            else:
                alpha = 1.0

            new_val = current + alpha * (float(target) - current)
            self._current[name] = new_val

            # Preserve original type (int fields stay int)
            if isinstance(target, int):
                setattr(smoothed, name, round(new_val))
            else:
                setattr(smoothed, name, new_val)

        # Deep-copy complex fields that bypassed smoothing
        for f in fields(intent):
            name = f.name
            target = getattr(intent, name)
            if isinstance(target, (dict, list)):
                setattr(smoothed, name, _deep_copy(target))

        return smoothed

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def get_state(self) -> dict[str, float]:
        """Return current smoothed values for snapshot."""
        return dict(self._current)

    def set_state(self, state: dict[str, float]) -> None:
        """Restore smoothed values from snapshot."""
        self._current = dict(state)


def _deep_copy(val: Any) -> Any:
    """Shallow-deep copy for dicts and lists."""
    if isinstance(val, dict):
        return dict(val)
    if isinstance(val, list):
        return list(val)
    return val

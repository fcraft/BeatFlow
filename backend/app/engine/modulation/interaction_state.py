"""Interaction state — user intent layer for the V2 simulation pipeline.

InteractionState holds all user-set parameters (intents).  These are never
overwritten by ``compute_modifiers()``; instead, ``compute_modifiers()``
reads them and produces a derived ``Modifiers`` for the physics layers.

This cleanly separates **what the user asked for** from **the computed
per-beat modifiers**, eliminating the fragile "copy-back 20 fields" pattern.
"""
from __future__ import annotations

from dataclasses import dataclass, field, fields
from typing import Any


@dataclass
class InteractionState:
    """All user-set intents.  Never overwritten by compute_modifiers."""

    # ---- Exercise ----
    exercise_intensity: float = 0.0       # [0, 1]

    # ---- Emotion ----
    emotional_arousal: float = 0.0        # [0, 1]
    fatigue_level: float = 0.0            # [0, 1]

    # ---- Condition (rhythm / structural) ----
    rhythm_override: str = ''             # '' | 'af' | 'svt' | 'vt' | 'vf' | 'asystole'
    av_block_degree: int = 0              # 0, 1, 2, 3
    hr_override: float | None = None      # Direct HR override
    pvc_pattern: str = 'isolated'         # 'isolated' | 'bigeminy' | 'trigeminy' | 'couplets'
    damage_level: float = 0.0             # [0, 1]
    murmur_type: str = ''                 # '' | 'systolic' | 'diastolic'
    murmur_severity: float = 0.0          # [0, 1]

    # ---- Body state ----
    caffeine_level: float = 0.0           # [0, 1]
    alcohol_level: float = 0.0            # [0, 1]
    temperature: float = 36.6             # Celsius
    dehydration_level: float = 0.0        # [0, 1]
    sleep_debt: float = 0.0               # [0, 1]

    # ---- Electrolytes ----
    potassium_level: float = 4.0          # mEq/L [2.5, 7.0]
    calcium_level: float = 9.5            # mg/dL [6.0, 14.0]
    magnesium_level: float = 2.0          # mg/dL [1.0, 4.0]

    # ---- Respiratory ----
    fio2: float = 0.21                    # Fraction of inspired O2 [0.21, 1.0]

    # ---- Coronary ----
    coronary_stenosis: float = 0.0        # [0, 1] coronary artery stenosis

    # ---- Right ventricle ----
    rv_contractility: float = 1.0         # RV contractility modifier
    pulm_vascular_resistance: float = 0.15  # Pulmonary vascular resistance

    # ---- Arrhythmia substrates ----
    af_substrate: float = 0.0             # [0, 1]
    svt_substrate: float = 0.0            # [0, 1]
    vt_substrate: float = 0.0             # [0, 1]

    # ---- Intervention state ----
    defibrillation_count: int = 0

    # ---- Settings (direct hemodynamic overrides) ----
    preload_override: float = 1.0
    contractility_override: float = 1.0
    tpr_override: float = 1.0

    # ---- Valve pathology ----
    valve_areas: dict[str, float] = field(default_factory=dict)
    valve_stiffness: dict[str, float] = field(default_factory=dict)

    # ---- Audio / misc ----
    chest_wall_attenuation: float = 1.0
    electrode_noise: dict[str, float] = field(default_factory=dict)
    ectopic_foci: list = field(default_factory=list)

    # ---- Autonomic direct overrides (set by exercise/emotion commands) ----
    sympathetic_tone_override: float | None = None
    parasympathetic_tone_override: float | None = None
    sa_rate_modifier_override: float | None = None
    contractility_modifier_override: float | None = None

    # ------------------------------------------------------------------
    # Serialization helpers
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dict for snapshot."""
        d: dict[str, Any] = {}
        for f in fields(self):
            val = getattr(self, f.name)
            if isinstance(val, dict):
                val = dict(val)
            elif isinstance(val, list):
                val = list(val)
            d[f.name] = val
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> 'InteractionState':
        """Restore from a snapshot dict, ignoring unknown keys."""
        known_names = {f.name for f in fields(cls)}
        filtered = {k: v for k, v in d.items() if k in known_names}
        return cls(**filtered)

    @classmethod
    def from_modifiers(cls, m: Any) -> 'InteractionState':
        """Build InteractionState from a legacy Modifiers object.

        Used for backward-compatible snapshot migration: old snapshots
        that lack ``intent_state`` can reconstruct intent from the saved
        ``modifiers`` dict.
        """
        state = cls()
        # Map modifier fields → intent fields (identical names)
        for f in fields(state):
            if hasattr(m, f.name):
                val = getattr(m, f.name)
                if isinstance(val, dict):
                    val = dict(val)
                elif isinstance(val, list):
                    val = list(val)
                setattr(state, f.name, val)
        return state

    def get_active_interactions(self) -> dict[str, Any]:
        """Return which interactions are currently active.

        Useful for frontend display: shows which parameters have been
        set away from their defaults.
        """
        active: dict[str, Any] = {}
        if self.exercise_intensity > 0.05:
            active['exercise'] = round(self.exercise_intensity, 2)
        if self.emotional_arousal > 0.05:
            active['emotion'] = round(self.emotional_arousal, 2)
        if self.fatigue_level > 0.1:
            active['fatigue'] = round(self.fatigue_level, 2)
        if self.rhythm_override:
            active['rhythm'] = self.rhythm_override
        if self.av_block_degree > 0:
            active['av_block'] = self.av_block_degree
        if self.hr_override is not None:
            active['hr_override'] = round(self.hr_override, 1)
        if self.damage_level > 0.05:
            active['damage'] = round(self.damage_level, 2)
        if self.murmur_severity > 0.05:
            active['murmur'] = {'type': self.murmur_type, 'severity': round(self.murmur_severity, 2)}
        if self.caffeine_level > 0.05:
            active['caffeine'] = round(self.caffeine_level, 2)
        if self.alcohol_level > 0.05:
            active['alcohol'] = round(self.alcohol_level, 2)
        if abs(self.temperature - 36.6) > 0.3:
            active['temperature'] = round(self.temperature, 1)
        if self.dehydration_level > 0.05:
            active['dehydration'] = round(self.dehydration_level, 2)
        if self.sleep_debt > 0.1:
            active['sleep_debt'] = round(self.sleep_debt, 2)
        if abs(self.potassium_level - 4.0) > 0.3:
            active['potassium'] = round(self.potassium_level, 1)
        if abs(self.calcium_level - 9.5) > 0.3:
            active['calcium'] = round(self.calcium_level, 1)
        if abs(self.magnesium_level - 2.0) > 0.2:
            active['magnesium'] = round(self.magnesium_level, 1)
        if abs(self.fio2 - 0.21) > 0.02:
            active['fio2'] = round(self.fio2, 2)
        if self.coronary_stenosis > 0.05:
            active['coronary_stenosis'] = round(self.coronary_stenosis, 2)
        if abs(self.rv_contractility - 1.0) > 0.05:
            active['rv_contractility'] = round(self.rv_contractility, 2)
        if abs(self.pulm_vascular_resistance - 0.15) > 0.02:
            active['pulm_vascular_resistance'] = round(self.pulm_vascular_resistance, 2)
        if self.af_substrate > 0.05:
            active['af_substrate'] = round(self.af_substrate, 2)
        if self.svt_substrate > 0.05:
            active['svt_substrate'] = round(self.svt_substrate, 2)
        if self.vt_substrate > 0.05:
            active['vt_substrate'] = round(self.vt_substrate, 2)
        if self.defibrillation_count > 0:
            active['defibrillations'] = self.defibrillation_count
        return active

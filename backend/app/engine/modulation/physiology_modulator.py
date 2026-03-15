"""Physiology modulator: maps ANS, drugs, interaction state, damage → Modifiers.

Central integration point that computes per-beat Modifiers from:
1. Autonomic state (sympathetic/parasympathetic tones)
2. Drug concentrations (from PharmacokineticsEngine)
3. InteractionState (intent-based architecture)
4. Damage level
5. ExercisePhysiologyModel (optional, via state_ref)
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any

from app.engine.core.types import EctopicFocus, Modifiers, Stimuli


@dataclass(frozen=True)
class AutonomicState:
    """Autonomic nervous system state."""
    sympathetic_tone: float = 0.5
    parasympathetic_tone: float = 0.5


def _generate_ectopic_foci_from_pattern(
    pattern: str, damage_level: float, beat_index: int, couplet_pending: bool,
) -> tuple[list[EctopicFocus], bool]:
    """Generate ectopic foci based on PVC pattern.

    Returns:
        (foci_list, new_couplet_pending)
    """
    foci: list[EctopicFocus] = []

    def _make_focus(damage: float) -> EctopicFocus:
        coupling = random.uniform(300.0, 450.0)
        current = random.uniform(1.0, 2.0) * max(damage, 0.1)
        return EctopicFocus(
            node='purkinje',
            current=current,
            coupling_interval_ms=coupling,
            probability=1.0,
        )

    # If previous beat started a couplet, this beat is forced PVC
    if couplet_pending:
        foci.append(_make_focus(damage_level))
        return foci, False

    if pattern == 'isolated':
        # Random PVCs proportional to damage
        if damage_level > 0 and random.random() < damage_level * 0.15:
            foci.append(_make_focus(damage_level))

    elif pattern == 'bigeminy':
        # Every other beat is PVC (odd-indexed)
        if damage_level > 0.1 and beat_index % 2 == 1:
            foci.append(_make_focus(damage_level))

    elif pattern == 'trigeminy':
        # Every 3rd beat is PVC
        if beat_index % 3 == 2:
            foci.append(_make_focus(damage_level))

    elif pattern == 'couplets':
        # Trigger PVC and set couplet_pending for next beat
        if damage_level > 0 and beat_index % 4 == 1:
            foci.append(_make_focus(damage_level))
            return foci, True

    return foci, False


def compute_modifiers(
    autonomic: AutonomicState | None = None,
    pharma_levels: dict[str, float] | None = None,
    user_commands: dict[str, Any] | None = None,
    damage_level: float = 0.0,
    base_modifiers: Modifiers | None = None,
    *,
    interaction: 'InteractionState | None' = None,
    state_ref: 'PhysioState | None' = None,
    beat_index: int = 0,
) -> Modifiers:
    """Compute final Modifiers from all physiological factors.

    Args:
        autonomic: Current ANS state
        pharma_levels: Drug name → concentration mapping
        user_commands: Active user commands (exercise level, etc.)
            — LEGACY; prefer ``interaction`` when available
        damage_level: Myocardial damage [0, 1]
        base_modifiers: Optional starting modifiers to overlay on
        interaction: (NEW) Smoothed InteractionState from
            ``TransitionSmoother``.  When provided, body-state /
            emotion / electrolyte / hemodynamic-override fields are
            read from *interaction* instead of *base_modifiers*.
        state_ref: (NEW) Optional PhysioState reference. When provided
            and exercise is active, uses ExercisePhysiologyModel for
            HR computation instead of the legacy fixed formula.

    Returns:
        Fully computed Modifiers for the current beat
    """
    if autonomic is None:
        autonomic = AutonomicState()
    if pharma_levels is None:
        pharma_levels = {}
    if user_commands is None:
        user_commands = {}

    # Start from base or default
    m = Modifiers() if base_modifiers is None else _clone_modifiers(base_modifiers)

    # ------------------------------------------------------------------
    # When InteractionState is available, copy ALL intent fields onto
    # Modifiers *before* the physiology cascade.  This replaces the old
    # pattern where apply_command() wrote directly into Modifiers.
    # ------------------------------------------------------------------
    if interaction is not None:
        _apply_interaction(m, interaction)

    # ---- 1. Autonomic effects ----
    symp = autonomic.sympathetic_tone
    para = autonomic.parasympathetic_tone

    # Apply autonomic overrides from interaction if set
    if interaction is not None:
        if interaction.sympathetic_tone_override is not None:
            symp = interaction.sympathetic_tone_override
        if interaction.parasympathetic_tone_override is not None:
            para = interaction.parasympathetic_tone_override

    # Sympathetic → ↑ HR, ↑ contractility, ↑ TPR
    # Parasympathetic → ↓ HR (vagal)
    # Net SA rate: sympathetic increases, parasympathetic decreases
    ans_hr_factor = 1.0 + 0.6 * (symp - 0.5) - 0.4 * (para - 0.5)
    m.sa_rate_modifier *= max(0.5, min(2.5, ans_hr_factor))

    # Contractility: sympathetic positive inotrope
    m.contractility_modifier *= 1.0 + 0.4 * (symp - 0.5)

    # TPR: sympathetic → vasoconstriction
    m.tpr_modifier *= 1.0 + 0.3 * (symp - 0.5)

    # Store ANS tones in modifiers for downstream layers
    m.sympathetic_tone = symp
    m.parasympathetic_tone = para

    # ---- 2. Drug effects ----
    # Beta-blocker: ↓ HR, ↓ contractility, mild ↓ TPR
    bb = pharma_levels.get("beta_blocker", 0.0)
    if bb > 0.01:
        m.sa_rate_modifier *= max(0.5, 1.0 - 0.35 * bb)
        m.contractility_modifier *= max(0.6, 1.0 - 0.25 * bb)
        # Prolong AV conduction
        m.av_delay_modifier *= 1.0 + 0.3 * bb
        # SA node tau_open modifier (slows depolarization)
        m.cell_stimuli["sa"] = Stimuli(tau_open_modifier=1.0 + 0.5 * bb)

    # Amiodarone: ↓ HR, prolongs AP duration, anti-arrhythmic
    amio = pharma_levels.get("amiodarone", 0.0)
    if amio > 0.01:
        m.sa_rate_modifier *= max(0.6, 1.0 - 0.25 * amio)
        m.av_delay_modifier *= 1.0 + 0.2 * amio
        # Prolong repolarization via tau_close
        for node in ("sa", "av", "his", "purkinje"):
            existing = m.cell_stimuli.get(node, Stimuli())
            m.cell_stimuli[node] = Stimuli(
                external_current=existing.external_current,
                tau_in_modifier=existing.tau_in_modifier,
                tau_out_modifier=existing.tau_out_modifier,
                tau_open_modifier=existing.tau_open_modifier,
                tau_close_modifier=existing.tau_close_modifier * (1.0 + 0.4 * amio),
                v_gate_offset=existing.v_gate_offset,
            )

    # Digoxin: positive inotrope, ↓ HR, ↓ AV conduction
    dig = pharma_levels.get("digoxin", 0.0)
    if dig > 0.01:
        m.contractility_modifier *= 1.0 + 0.3 * dig
        m.sa_rate_modifier *= max(0.7, 1.0 - 0.15 * dig)
        m.av_delay_modifier *= 1.0 + 0.25 * dig

    # Atropine: blocks parasympathetic → ↑ HR
    atr = pharma_levels.get("atropine", 0.0)
    if atr > 0.01:
        # Effectively reduces parasympathetic influence
        para_block = min(1.0, atr * 0.8)
        m.sa_rate_modifier *= 1.0 + 0.3 * para_block
        m.parasympathetic_tone *= max(0.0, 1.0 - para_block)

    # ---- 2.5 Emotion effects ----
    arousal = m.emotional_arousal
    if arousal > 0:
        # Emotional arousal amplifies sympathetic tone
        m.sympathetic_tone = min(1.0, m.sympathetic_tone + 0.4 * arousal)
        m.sa_rate_modifier *= 1.0 + 0.3 * arousal
        m.tpr_modifier *= 1.0 + 0.15 * arousal

    fatigue = m.fatigue_level
    if fatigue > 0.1:
        # Fatigue: slight HR drop, reduced contractility
        m.sa_rate_modifier *= max(0.8, 1.0 - 0.15 * fatigue)
        m.contractility_modifier *= max(0.7, 1.0 - 0.2 * fatigue)

    # ---- 2.6 Body state effects ----
    caffeine = m.caffeine_level
    if caffeine > 0.05:
        m.sympathetic_tone = min(1.0, m.sympathetic_tone + 0.2 * caffeine)
        m.sa_rate_modifier *= 1.0 + 0.15 * caffeine

    alcohol = m.alcohol_level
    if alcohol > 0.05:
        m.parasympathetic_tone *= max(0.3, 1.0 - 0.3 * alcohol)
        m.tpr_modifier *= 1.0 - 0.1 * alcohol

    dehydration = m.dehydration_level
    if dehydration > 0.05:
        m.preload_modifier *= max(0.6, 1.0 - 0.3 * dehydration)
        m.sa_rate_modifier *= 1.0 + 0.2 * dehydration

    temp = m.temperature
    if temp > 37.5:
        delta = temp - 37.0
        m.sa_rate_modifier *= 1.0 + 0.08 * delta  # ~8 bpm per degree C

    sleep_debt = m.sleep_debt
    if sleep_debt > 0.1:
        m.sympathetic_tone = min(1.0, m.sympathetic_tone + 0.15 * sleep_debt)

    # ---- 3. Exercise effects (via physiological model or fallback) ----
    ex = m.exercise_intensity if interaction is not None else user_commands.get("exercise_intensity", 0.0)

    if ex > 0.01 and state_ref is not None and hasattr(state_ref, '_exercise_model'):
        model = state_ref._exercise_model
        hr_delta = model.compute_hr_delta(
            intensity=ex,
            elapsed_sec=getattr(state_ref, '_exercise_duration_sec', 0.0),
            fatigue=m.fatigue_level,
            dehydration=m.dehydration_level,
        )
        base_hr = 72.0
        m.sa_rate_modifier *= 1.0 + hr_delta / base_hr
        m.contractility_modifier *= 1.0 + 0.3 * ex
        m.preload_modifier *= 1.0 + 0.2 * ex
    elif ex > 0:
        m.sa_rate_modifier *= 1.0 + 0.8 * ex
        m.contractility_modifier *= 1.0 + 0.4 * ex
        m.preload_modifier *= 1.0 + 0.2 * ex

    # Apply sa_rate_modifier_override and contractility_modifier_override
    # from interaction (these are set by exercise/emotion commands)
    if interaction is not None:
        if interaction.sa_rate_modifier_override is not None:
            m.sa_rate_modifier = interaction.sa_rate_modifier_override
        if interaction.contractility_modifier_override is not None:
            m.contractility_modifier = interaction.contractility_modifier_override

    # ---- 4. Damage propagation ----
    effective_damage = damage_level
    if interaction is not None:
        effective_damage = max(effective_damage, interaction.damage_level)
    m.damage_level = max(m.damage_level, effective_damage)

    # Damage reduces contractility
    if effective_damage > 0:
        m.contractility_modifier *= max(0.3, 1.0 - 0.5 * effective_damage)

    # ---- 4.1 PVC pattern → ectopic foci generation ----
    if m.pvc_pattern != 'isolated' or m.damage_level > 0:
        new_foci, new_pending = _generate_ectopic_foci_from_pattern(
            pattern=m.pvc_pattern,
            damage_level=m.damage_level,
            beat_index=beat_index,
            couplet_pending=m._couplet_pending,
        )
        m.ectopic_foci = list(m.ectopic_foci) + new_foci
        m._couplet_pending = new_pending

    # ---- 4.5 Electrolyte effects ----
    k = m.potassium_level
    if k > 5.0:
        # Hyperkalemia: slow conduction, widen QRS
        severity = (k - 5.0) / 2.0  # 0-1 over 5-7 mEq/L
        m.av_delay_modifier *= 1.0 + 0.3 * severity
        # Prolong repolarization via tau_close on all nodes
        for node in ('sa', 'av', 'his', 'purkinje'):
            existing = m.cell_stimuli.get(node, Stimuli())
            m.cell_stimuli[node] = Stimuli(
                external_current=existing.external_current,
                tau_in_modifier=existing.tau_in_modifier * (1.0 + 0.4 * severity),
                tau_out_modifier=existing.tau_out_modifier,
                tau_open_modifier=existing.tau_open_modifier,
                tau_close_modifier=existing.tau_close_modifier * (1.0 + 0.5 * severity),
                v_gate_offset=existing.v_gate_offset,
            )
    elif k < 3.5:
        # Hypokalemia: prolong QT, U wave (via tau_close)
        severity = (3.5 - k) / 1.0  # 0-1 over 2.5-3.5
        for node in ('his', 'purkinje'):
            existing = m.cell_stimuli.get(node, Stimuli())
            m.cell_stimuli[node] = Stimuli(
                external_current=existing.external_current,
                tau_in_modifier=existing.tau_in_modifier,
                tau_out_modifier=existing.tau_out_modifier,
                tau_open_modifier=existing.tau_open_modifier,
                tau_close_modifier=existing.tau_close_modifier * (1.0 + 0.6 * severity),
                v_gate_offset=existing.v_gate_offset,
            )

    ca = m.calcium_level
    if ca > 10.5:
        # Hypercalcemia: shorten QT
        severity = (ca - 10.5) / 3.5
        m.calcium_modifier *= 1.0 + 0.3 * severity
    elif ca < 8.5:
        # Hypocalcemia: prolong QT
        severity = (8.5 - ca) / 2.5
        m.calcium_modifier *= max(0.5, 1.0 - 0.3 * severity)

    # ---- 5. User hemodynamic overrides (from SettingsTab sliders) ----
    if interaction is not None:
        # New path: read from InteractionState
        if interaction.preload_override != 1.0:
            m.preload_modifier = interaction.preload_override
        if interaction.contractility_override != 1.0:
            m.contractility_modifier = interaction.contractility_override
        if interaction.tpr_override != 1.0:
            m.tpr_modifier = interaction.tpr_override

    # ---- Final clamps ----
    m.sa_rate_modifier = max(0.3, min(3.0, m.sa_rate_modifier))
    m.contractility_modifier = max(0.2, min(2.5, m.contractility_modifier))
    m.tpr_modifier = max(0.3, min(3.0, m.tpr_modifier))
    m.preload_modifier = max(0.5, min(2.0, m.preload_modifier))
    m.av_delay_modifier = max(0.5, min(3.0, m.av_delay_modifier))

    return m


def _apply_interaction(m: Modifiers, interaction: 'InteractionState') -> None:
    """Copy all intent fields from InteractionState onto Modifiers.

    This sets the "starting point" for the physiology cascade — the
    body-state / condition / electrolyte fields that downstream sections
    (emotion effects, body state effects, electrolyte effects) will read
    from ``m``.
    """
    # Exercise / emotion
    m.exercise_intensity = interaction.exercise_intensity
    m.emotional_arousal = interaction.emotional_arousal
    m.fatigue_level = interaction.fatigue_level

    # Condition
    m.rhythm_override = interaction.rhythm_override
    m.av_block_degree = interaction.av_block_degree
    m.hr_override = interaction.hr_override
    m.pvc_pattern = interaction.pvc_pattern
    m.murmur_type = interaction.murmur_type
    m.murmur_severity = interaction.murmur_severity

    # Body state
    m.caffeine_level = interaction.caffeine_level
    m.alcohol_level = interaction.alcohol_level
    m.temperature = interaction.temperature
    m.dehydration_level = interaction.dehydration_level
    m.sleep_debt = interaction.sleep_debt

    # Electrolytes
    m.potassium_level = interaction.potassium_level
    m.calcium_level = interaction.calcium_level
    m.magnesium_level = getattr(interaction, 'magnesium_level', 2.0)

    # Respiratory
    m.fio2 = getattr(interaction, 'fio2', 0.21)

    # Right ventricle / pulmonary
    m.rv_contractility = getattr(interaction, 'rv_contractility', 1.0)
    m.pulm_vascular_resistance = getattr(interaction, 'pulm_vascular_resistance', 0.15)

    # Substrates
    m.af_substrate = interaction.af_substrate
    m.svt_substrate = interaction.svt_substrate
    m.vt_substrate = interaction.vt_substrate

    # Intervention
    m.defibrillation_count = interaction.defibrillation_count

    # Valve pathology
    if interaction.valve_areas:
        m.valve_areas = dict(interaction.valve_areas)
    if interaction.valve_stiffness:
        m.valve_stiffness = dict(interaction.valve_stiffness)

    # Audio/misc
    m.chest_wall_attenuation = interaction.chest_wall_attenuation
    if interaction.electrode_noise:
        m.electrode_noise = dict(interaction.electrode_noise)
    if interaction.ectopic_foci:
        m.ectopic_foci = list(interaction.ectopic_foci)


def _clone_modifiers(src: Modifiers) -> Modifiers:
    """Create a mutable copy of Modifiers."""
    return Modifiers(
        cell_stimuli=dict(src.cell_stimuli),
        sa_rate_modifier=src.sa_rate_modifier,
        av_delay_modifier=src.av_delay_modifier,
        ectopic_foci=list(src.ectopic_foci),
        contractility_modifier=src.contractility_modifier,
        calcium_modifier=src.calcium_modifier,
        tpr_modifier=src.tpr_modifier,
        preload_modifier=src.preload_modifier,
        valve_areas=dict(src.valve_areas),
        valve_stiffness=dict(src.valve_stiffness),
        electrode_noise=dict(src.electrode_noise),
        chest_wall_attenuation=src.chest_wall_attenuation,
        sympathetic_tone=src.sympathetic_tone,
        parasympathetic_tone=src.parasympathetic_tone,
        damage_level=src.damage_level,
        rhythm_override=src.rhythm_override,
        av_block_degree=src.av_block_degree,
        hr_override=src.hr_override,
        pvc_pattern=src.pvc_pattern,
        emotional_arousal=src.emotional_arousal,
        exercise_intensity=src.exercise_intensity,
        caffeine_level=src.caffeine_level,
        alcohol_level=src.alcohol_level,
        temperature=src.temperature,
        dehydration_level=src.dehydration_level,
        sleep_debt=src.sleep_debt,
        fatigue_level=src.fatigue_level,
        potassium_level=src.potassium_level,
        calcium_level=src.calcium_level,
        magnesium_level=src.magnesium_level,
        murmur_type=src.murmur_type,
        murmur_severity=src.murmur_severity,
        af_substrate=src.af_substrate,
        svt_substrate=src.svt_substrate,
        vt_substrate=src.vt_substrate,
        defibrillation_count=src.defibrillation_count,
        # Respiratory
        respiratory_phase=src.respiratory_phase,
        intrathoracic_pressure=src.intrathoracic_pressure,
        pao2=src.pao2,
        paco2=src.paco2,
        ph=src.ph,
        spo2_physical=src.spo2_physical,
        rr_physical=src.rr_physical,
        fio2=src.fio2,
        # Right ventricle / pulmonary
        rv_contractility=src.rv_contractility,
        pulm_vascular_resistance=src.pulm_vascular_resistance,
        # Coronary
        coronary_perfusion_pressure=src.coronary_perfusion_pressure,
        ischemia_level=src.ischemia_level,
        # HRV
        hrv_rr_offset_ms=src.hrv_rr_offset_ms,
        # QT dynamics
        qt_adapted_ms=src.qt_adapted_ms,
        # Internal
        _couplet_pending=src._couplet_pending,
    )

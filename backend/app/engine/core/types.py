"""
V3 engine I/O data types.

All types are frozen (immutable) dataclasses except Modifiers which is
mutable because it's recomputed each beat by PhysiologyModulator.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional

import numpy as np
from numpy.typing import NDArray

# --- Type aliases ---
CellPhase = Literal['resting', 'depolarizing', 'plateau', 'repolarizing']
BeatKind = Literal['sinus', 'pvc', 'svt', 'escape', 'vt', 'vf', 'paced', 'af', 'asystole']
ValveName = Literal['mitral', 'aortic', 'tricuspid', 'pulmonary']
ValveAction = Literal['open', 'close']
ConductionNode = Literal['sa', 'av', 'his', 'purkinje']


@dataclass(frozen=True)
class Stimuli:
    """External stimuli input (used by physiology_modulator for cell-level drug effects)."""
    external_current: float = 0.0
    tau_in_modifier: float = 1.0
    tau_out_modifier: float = 1.0
    tau_open_modifier: float = 1.0
    tau_close_modifier: float = 1.0
    v_gate_offset: float = 0.0


@dataclass(frozen=True)
class ActionPotential:
    """Lightweight action potential output (V3: no ODE traces).

    In V3 the conduction network is parametric, so vm_trace and
    calcium_trace are optional (None by default).  The apd_ms field
    is computed from Bazett/QT dynamics instead of measured from ODE.
    """
    vm: float = 0.0
    h_gate: float = 1.0
    calcium_transient: float = 0.0
    phase: CellPhase = 'resting'
    refractory: bool = False
    apd_ms: float = 300.0
    vm_trace: Optional[NDArray[np.float64]] = None
    calcium_trace: Optional[NDArray[np.float64]] = None


@dataclass(frozen=True)
class ConductionResult:
    """One beat's conduction network output."""
    beat_index: int
    rr_sec: float
    activation_times: dict[str, float]     # Node name → activation time (ms)
    node_aps: dict[str, ActionPotential]   # Node name → ActionPotential
    pr_interval_ms: float
    qrs_duration_ms: float
    qt_interval_ms: float
    p_wave_present: bool
    p_wave_retrograde: bool
    beat_kind: BeatKind
    conducted: bool


@dataclass(frozen=True)
class EcgFrame:
    """ECG synthesis output for one beat."""
    samples: dict[str, NDArray[np.float64]]  # lead_name → signal array
    sample_rate: int                          # 500
    beat_annotations: list[dict]


@dataclass(frozen=True)
class ValveEvent:
    """A valve opening or closing event (synthetic, from parametric timing)."""
    valve: ValveName
    action: ValveAction
    at_sample: int
    dp_dt: float         # dP/dt at closure (determines sound loudness)
    area_ratio: float    # Effective opening area ratio (1.0=normal, <1=stenosis)


@dataclass(frozen=True)
class HemodynamicState:
    """Algebraic hemodynamic state for one beat."""
    lv_pressure: NDArray[np.float64]
    lv_volume: NDArray[np.float64]
    aortic_pressure: NDArray[np.float64]
    systolic_bp: float
    diastolic_bp: float
    mean_arterial_pressure: float
    cardiac_output: float               # L/min
    ejection_fraction: float            # %
    stroke_volume: float                # mL
    valve_events: list[ValveEvent]
    heart_rate: float
    spo2: float
    respiratory_rate: float
    approximate: bool = True

    # --- Right ventricle / pulmonary (algebraic estimates) ---
    rv_pressure: NDArray[np.float64] = field(default_factory=lambda: np.zeros(1))
    rv_volume: NDArray[np.float64] = field(default_factory=lambda: np.zeros(1))
    pa_pressure: NDArray[np.float64] = field(default_factory=lambda: np.zeros(1))
    rv_ejection_fraction: float = 55.0
    rv_stroke_volume: float = 70.0
    pa_systolic: float = 25.0
    pa_diastolic: float = 10.0
    pa_mean: float = 15.0


@dataclass(frozen=True)
class PcgFrame:
    """PCG synthesis output for one beat."""
    samples: NDArray[np.float64]
    sample_rate: int                     # 4000
    s1_onset_sample: int
    s2_onset_sample: int
    murmur_present: bool
    channels: dict[str, NDArray[np.float64]] = field(default_factory=dict)
    s3_present: bool = False
    s4_present: bool = False


@dataclass(frozen=True)
class EctopicFocus:
    """Ectopic focus definition for PVC generation."""
    node: ConductionNode
    current: float
    coupling_interval_ms: float
    probability: float = 1.0


@dataclass
class Modifiers:
    """Mutable modifier set computed each beat by PhysiologyModulator."""
    cell_stimuli: dict[str, Stimuli] = field(default_factory=dict)
    sa_rate_modifier: float = 1.0
    av_delay_modifier: float = 1.0
    ectopic_foci: list[EctopicFocus] = field(default_factory=list)
    contractility_modifier: float = 1.0
    calcium_modifier: float = 1.0
    tpr_modifier: float = 1.0
    preload_modifier: float = 1.0
    valve_areas: dict[str, float] = field(default_factory=dict)
    valve_stiffness: dict[str, float] = field(default_factory=dict)
    electrode_noise: dict[str, float] = field(default_factory=dict)
    chest_wall_attenuation: float = 1.0
    sympathetic_tone: float = 0.5
    parasympathetic_tone: float = 0.5
    damage_level: float = 0.0

    # --- Rhythm / arrhythmia control ---
    rhythm_override: str = ''
    av_block_degree: int = 0
    hr_override: float | None = None
    pvc_pattern: str = 'isolated'

    # --- Emotion / body state ---
    emotional_arousal: float = 0.0
    exercise_intensity: float = 0.0
    caffeine_level: float = 0.0
    alcohol_level: float = 0.0
    temperature: float = 36.6
    dehydration_level: float = 0.0
    sleep_debt: float = 0.0
    fatigue_level: float = 0.0

    # --- Electrolytes ---
    potassium_level: float = 4.0
    calcium_level: float = 9.5
    magnesium_level: float = 2.0

    # --- Valve pathology ---
    murmur_type: str = ''
    murmur_severity: float = 0.0

    # --- Arrhythmia substrates ---
    af_substrate: float = 0.0
    svt_substrate: float = 0.0
    vt_substrate: float = 0.0

    # --- Intervention state ---
    defibrillation_count: int = 0

    # --- Respiratory system ---
    respiratory_phase: float = 0.0
    intrathoracic_pressure: float = -5.0
    pao2: float = 95.0
    paco2: float = 40.0
    ph: float = 7.40
    spo2_physical: float = 97.5
    rr_physical: float = 14.0
    fio2: float = 0.21

    # --- Right ventricle / pulmonary ---
    rv_contractility: float = 1.0
    pulm_vascular_resistance: float = 0.15

    # --- Coronary circulation ---
    coronary_perfusion_pressure: float = 70.0
    ischemia_level: float = 0.0

    # --- HRV ---
    hrv_rr_offset_ms: float = 0.0

    # --- QT dynamics ---
    qt_adapted_ms: float = 0.0

    # --- Internal state ---
    _couplet_pending: bool = False

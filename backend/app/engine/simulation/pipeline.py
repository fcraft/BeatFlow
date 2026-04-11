"""V3 Simulation Pipeline — parametric 3-layer engine.

Orchestrates:
  Layer 1: ParametricConductionNetwork.propagate()
  Layer 2a: EcgSynthesizerV2.synthesize()
  Layer 2b: ParametricPcgSynthesizer.synthesize()
  Layer 3: AlgebraicHemodynamics.compute()

Cross-cutting modules (all preserved from V2):
  - AutonomicReflexController (baroreceptor/chemo/thermo/RAAS feedback)
  - PharmacokineticsEngine (drug metabolism)
  - compute_modifiers (physiology modulator)
  - InteractionState + TransitionSmoother (intent-based architecture)
  - RespiratoryModel + GasExchange (closed-loop blood gases)
  - HrvGenerator (frequency-domain RR variability)
  - QtDynamics (rate-adaptive QT)
  - CoronaryModel (CPP-based ischemia)
  - check_beat_invariants (physics validator)

Public API: start, stop, apply_command, get_snapshot, get_init_payload, set_leads.
"""
from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from typing import Any, Awaitable, Callable, Dict, Optional

import random as _rng

import numpy as np

from app.engine.core.parametric_conduction import ParametricConductionNetwork
from app.engine.core.ecg_synthesizer import EcgSynthesizerV2
from app.engine.core.parametric_pcg import ParametricPcgSynthesizer
from app.engine.core.algebraic_hemo import AlgebraicHemodynamics
from app.engine.core.types import (
    ConductionResult,
    EcgFrame,
    HemodynamicState,
    Modifiers,
    PcgFrame,
    Stimuli,
)
from app.engine.modulation.interaction_state import InteractionState
from app.engine.modulation.transition_engine import TransitionSmoother

logger = logging.getLogger(__name__)

# ---------- Constants ----------
ECG_SR = 500
PCG_SR = 4000
CHUNK_INTERVAL_SEC = 0.1
ECG_CHUNK_SIZE = int(ECG_SR * CHUNK_INTERVAL_SEC)   # 50
PCG_CHUNK_SIZE = int(PCG_SR * CHUNK_INTERVAL_SEC)    # 400

ALL_LEAD_NAMES = [
    "I", "II", "III", "aVR", "aVL", "aVF",
    "V1", "V2", "V3", "V4", "V5", "V6",
]

SendCallback = Callable[[Dict[str, Any]], Awaitable[None]]


class SimulationPipeline:
    """V3 parametric simulation pipeline."""

    def __init__(self, snapshot: Optional[dict] = None) -> None:
        # Layer instances
        self._conduction: Optional[ParametricConductionNetwork] = None
        self._ecg_synth: Optional[EcgSynthesizerV2] = None
        self._pcg_synth: Optional[ParametricPcgSynthesizer] = None
        self._hemo: Optional[AlgebraicHemodynamics] = None

        # Cross-cutting modules
        self._autonomic: Any = None
        self._pharma: Any = None
        self._respiratory: Any = None
        self._hrv: Any = None
        self._qt: Any = None
        self._coronary: Any = None

        # Exercise physiology
        self._exercise_model: Any = None
        self._exercise_duration_sec: float = 0.0
        self._high_exercise_duration_sec: float = 0.0

        # State — intent-based architecture
        self._intent = InteractionState()
        self._transition = TransitionSmoother()
        self._modifiers = Modifiers()
        self._base_hr = 72.0
        self._selected_leads: list[str] = ["II"]

        # Output buffers
        self._ecg_buf: deque[float] = deque()
        self._pcg_buf: deque[float] = deque()
        self._ecg_lead_bufs: dict[str, deque[float]] = {}
        self._pcg_bufs: dict[str, deque[float]] = {
            pos: deque() for pos in ('aortic', 'pulmonic', 'tricuspid', 'mitral')
        }
        self._ecg_sample_counter: int = 0
        self._pcg_sample_counter: int = 0
        self._buf_lock = asyncio.Lock()

        # Shared state lock
        import threading
        self._state_lock = threading.Lock()

        # Latest vitals
        self._vitals: dict[str, Any] = self._default_vitals()
        self._recent_beat_annotations: list[dict] = []
        self._conduction_history: deque[dict] = deque(maxlen=300)
        self._latest_physiology_detail: dict | None = None

        # Async control
        self._running = False
        self._beat_task: Optional[asyncio.Task] = None
        self._stream_task: Optional[asyncio.Task] = None
        self._send_callback: Optional[SendCallback] = None
        self._stream_seq = 0
        self._start_time = 0.0

        # Binary protocol
        from app.engine.ws_binary_protocol import BinaryFrameEncoder
        self._binary_encoder = BinaryFrameEncoder()
        self._use_binary_protocol = False
        self._send_binary_callback: Optional[Callable[[bytes], Awaitable[None]]] = None

        if snapshot:
            self._restore_snapshot(snapshot)

    # ==================================================================
    # Public API
    # ==================================================================

    async def start(
        self,
        send_callback: SendCallback,
        send_binary_callback: Callable[[bytes], Awaitable[None]] | None = None,
        use_binary: bool = False,
    ) -> None:
        self._send_callback = send_callback
        self._running = True
        self._start_time = time.monotonic()
        self._stream_seq = 0
        self._use_binary_protocol = use_binary
        self._send_binary_callback = send_binary_callback

        if use_binary:
            with self._state_lock:
                self._binary_encoder.update_vitals_baseline(dict(self._vitals))

        self._ensure_layers()

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._pre_generate_beats)

        self._beat_task = asyncio.create_task(self._beat_loop())
        self._stream_task = asyncio.create_task(self._stream_loop())

    def _pre_generate_beats(self) -> None:
        for _ in range(5):
            self._run_one_beat()

    async def stop(self) -> None:
        self._running = False
        for task in (self._beat_task, self._stream_task):
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        self._beat_task = None
        self._stream_task = None

    def apply_command(self, command: str, params: Optional[Dict[str, Any]] = None) -> None:
        """Translate a user command to InteractionState changes."""
        cmd = command.lower().strip()
        p = params or {}
        intent = self._intent

        # === Exercise (6) ===
        if cmd == "rest":
            intent.exercise_intensity = 0.0
            intent.emotional_arousal = 0.0
            intent.hr_override = None
            intent.sympathetic_tone_override = None
            intent.sa_rate_modifier_override = None
            intent.contractility_modifier_override = None
        elif cmd == "walk":
            intent.exercise_intensity = 0.3
            intent.hr_override = None
            intent.sympathetic_tone_override = 0.6
            intent.sa_rate_modifier_override = None
            intent.contractility_modifier_override = None
        elif cmd == "jog":
            intent.exercise_intensity = 0.55
            intent.hr_override = None
            intent.sympathetic_tone_override = 0.7
            intent.sa_rate_modifier_override = None
            intent.contractility_modifier_override = None
        elif cmd == "run":
            intent.exercise_intensity = 0.8
            intent.hr_override = None
            intent.sympathetic_tone_override = 0.85
            intent.sa_rate_modifier_override = None
            intent.contractility_modifier_override = None
        elif cmd == "climb_stairs":
            intent.exercise_intensity = 0.65
            intent.hr_override = None
            intent.sympathetic_tone_override = 0.75
            intent.sa_rate_modifier_override = None
            intent.contractility_modifier_override = None
        elif cmd == "squat":
            intent.exercise_intensity = 0.5
            intent.emotional_arousal = min(1.0, intent.emotional_arousal + 0.3)
            intent.hr_override = None
            intent.sympathetic_tone_override = 0.65
            intent.sa_rate_modifier_override = None
            intent.contractility_modifier_override = None

        # === Emotion (5) ===
        elif cmd == "startle":
            intent.emotional_arousal = 0.9
        elif cmd == "anxiety":
            intent.emotional_arousal = 0.6
        elif cmd == "relaxation":
            intent.exercise_intensity = 0.0
            intent.emotional_arousal = 0.0
            intent.hr_override = None
        elif cmd == "stress":
            intent.emotional_arousal = 0.7
            intent.temperature = 36.8
        elif cmd == "fatigue":
            intent.emotional_arousal = 0.2
            intent.exercise_intensity = 0.1
            intent.fatigue_level = 0.6

        # === Cardiac condition (14) ===
        elif cmd == "condition_normal":
            intent.rhythm_override = ''
            intent.av_block_degree = 0
            intent.hr_override = None
            intent.damage_level = 0.0
            intent.murmur_type = ''
            intent.murmur_severity = 0.0
            intent.defibrillation_count = 0
            intent.pvc_pattern = 'isolated'
        elif cmd == "condition_af":
            severity = float(p.get("severity", 0.5))
            intent.rhythm_override = 'af'
            intent.damage_level = severity
            intent.af_substrate = max(intent.af_substrate, severity)
        elif cmd == "condition_pvc":
            severity = float(p.get("severity", 0.3))
            intent.damage_level = severity
            intent.pvc_pattern = str(p.get("pattern", "isolated"))
        elif cmd == "condition_tachycardia":
            target_hr = float(p.get("heart_rate", 150.0))
            intent.rhythm_override = ''
            intent.hr_override = max(100.0, target_hr)
        elif cmd == "condition_bradycardia":
            target_hr = float(p.get("heart_rate", 45.0))
            intent.rhythm_override = ''
            intent.hr_override = min(60.0, target_hr)
        elif cmd == "condition_valve_disease":
            murmur = str(p.get("murmur_type", "systolic"))
            severity = float(p.get("severity", 0.5))
            intent.murmur_type = murmur
            intent.murmur_severity = severity
            intent.damage_level = severity * 0.5
        elif cmd == "condition_heart_failure":
            severity = float(p.get("severity", 0.6))
            intent.damage_level = severity
            intent.murmur_type = 'systolic'
            intent.murmur_severity = severity * 0.4
        elif cmd == "condition_svt":
            target_hr = float(p.get("heart_rate", 180.0))
            intent.rhythm_override = 'svt'
            intent.hr_override = max(150.0, target_hr)
            intent.svt_substrate = max(intent.svt_substrate, 0.5)
        elif cmd == "condition_vt":
            severity = float(p.get("severity", 0.7))
            intent.rhythm_override = 'vt'
            intent.hr_override = 180.0
            intent.damage_level = 0.7
            intent.vt_substrate = max(intent.vt_substrate, severity)
        elif cmd == "condition_av_block_1":
            intent.av_block_degree = 1
        elif cmd == "condition_av_block_2":
            intent.av_block_degree = 2
        elif cmd == "condition_av_block_3":
            intent.av_block_degree = 3
        elif cmd == "condition_vf":
            intent.rhythm_override = 'vf'
            intent.hr_override = None
        elif cmd == "condition_asystole":
            intent.rhythm_override = 'asystole'
            intent.hr_override = None

        # Cancel HR override
        elif cmd == "cancel_hr_override":
            intent.hr_override = None

        # === Emergency intervention (2) ===
        elif cmd == "defibrillate":
            current_rhythm = self._modifiers.rhythm_override
            if current_rhythm not in ('vf', 'vt'):
                return
            intent.defibrillation_count += 1
            success_rate = 0.55
            if self._pharma is not None:
                pharma_levels = self._pharma.step(0.0)
                success_rate += pharma_levels.get('amiodarone', 0.0) * 0.15
            success_rate -= intent.damage_level * 0.20
            success_rate -= intent.defibrillation_count * 0.03
            success_rate = max(0.10, min(0.90, success_rate))
            roll = _rng.random()
            if roll < success_rate:
                intent.rhythm_override = ''
                intent.hr_override = 80.0
            elif roll < success_rate + 0.15:
                intent.rhythm_override = 'asystole'
                intent.hr_override = None

        elif cmd == "cardiovert":
            current_rhythm = self._modifiers.rhythm_override
            if current_rhythm not in ('af', 'svt', 'vt'):
                return
            rhythm = current_rhythm
            success_rate = {'svt': 0.92, 'af': 0.80}.get(rhythm, 0.75)
            if self._pharma is not None:
                pharma_levels = self._pharma.step(0.0)
                success_rate += pharma_levels.get('amiodarone', 0.0) * 0.08
            success_rate = min(0.98, success_rate)
            if _rng.random() < success_rate:
                intent.rhythm_override = ''
                intent.hr_override = None

        # === Body state (7) ===
        elif cmd == "caffeine":
            dose = max(0.1, min(1.0, float(p.get("dose", 0.5))))
            intent.caffeine_level = min(1.0, intent.caffeine_level + dose)
        elif cmd == "alcohol":
            dose = max(0.1, min(1.0, float(p.get("dose", 0.4))))
            intent.alcohol_level = min(1.0, intent.alcohol_level + dose)
        elif cmd == "fever":
            temp = max(37.5, min(41.0, float(p.get("temperature", 38.5))))
            intent.temperature = temp
            delta = temp - 37.0
            intent.dehydration_level = min(1.0, intent.dehydration_level + delta * 0.1)
        elif cmd == "sleep_deprivation":
            severity = max(0.1, min(1.0, float(p.get("severity", 0.6))))
            intent.sleep_debt = severity
            intent.emotional_arousal = min(1.0, intent.emotional_arousal + severity * 0.2)
        elif cmd == "dehydration":
            severity = max(0.1, min(1.0, float(p.get("severity", 0.5))))
            intent.dehydration_level = severity
        elif cmd == "hydrate":
            intent.dehydration_level = 0.0
        elif cmd == "sleep":
            intent.sleep_debt = 0.0
            intent.fatigue_level = 0.0
            intent.emotional_arousal = 0.0
            intent.exercise_intensity = 0.0

        # === Settings (7) ===
        elif cmd == "set_damage_level":
            intent.damage_level = max(0.0, min(1.0, float(p.get("level", 0.0))))
        elif cmd == "set_heart_rate":
            self._base_hr = max(30.0, min(250.0, float(p.get("value", 72.0))))
        elif cmd == "set_preload":
            intent.preload_override = max(0.5, min(2.0, float(p.get("level", 1.0))))
        elif cmd == "set_contractility":
            intent.contractility_override = max(0.2, min(2.5, float(p.get("level", 1.0))))
        elif cmd == "set_tpr":
            intent.tpr_override = max(0.3, min(3.0, float(p.get("level", 1.0))))
        elif cmd == "set_pvc_pattern":
            pattern = str(p.get("pattern", "isolated"))
            if pattern in {"isolated", "bigeminy", "trigeminy", "couplets"}:
                intent.pvc_pattern = pattern
        elif cmd == "reset":
            self._intent = InteractionState()
            self._transition.reset()
            self._modifiers = Modifiers()
            self._base_hr = 72.0

        # === Medication (4) ===
        elif cmd in ("beta_blocker", "amiodarone", "digoxin", "atropine"):
            dose = float(p.get("dose", 1.0))
            if self._pharma is not None:
                self._pharma.administer(cmd, dose=dose)

        # === Electrolyte (4) ===
        elif cmd == "hyperkalemia":
            intent.potassium_level = max(3.0, min(7.0, float(p.get("level", 6.0))))
        elif cmd == "hypokalemia":
            intent.potassium_level = max(2.5, min(3.5, float(p.get("level", 3.0))))
        elif cmd == "hypercalcemia":
            intent.calcium_level = max(8.5, min(14.0, float(p.get("level", 12.0))))
        elif cmd == "hypocalcemia":
            intent.calcium_level = max(6.0, min(8.5, float(p.get("level", 7.0))))

        # === Arrhythmia substrate (3) ===
        elif cmd == "set_af_substrate":
            intent.af_substrate = max(0.0, min(1.0, float(p.get("level", 0.5))))
        elif cmd == "set_svt_substrate":
            intent.svt_substrate = max(0.0, min(1.0, float(p.get("level", 0.5))))
        elif cmd == "set_vt_substrate":
            intent.vt_substrate = max(0.0, min(1.0, float(p.get("level", 0.5))))

        else:
            logger.debug("Unknown command '%s' — ignored", command)

    def get_snapshot(self) -> Dict[str, Any]:
        snap: Dict[str, Any] = {
            "intent_state": self._intent.to_dict(),
            "transition_state": self._transition.get_state(),
            "modifiers": {
                "sa_rate_modifier": self._modifiers.sa_rate_modifier,
                "av_delay_modifier": self._modifiers.av_delay_modifier,
                "contractility_modifier": self._modifiers.contractility_modifier,
                "sympathetic_tone": self._modifiers.sympathetic_tone,
                "parasympathetic_tone": self._modifiers.parasympathetic_tone,
                "damage_level": self._modifiers.damage_level,
                "tpr_modifier": self._modifiers.tpr_modifier,
                "preload_modifier": self._modifiers.preload_modifier,
                "chest_wall_attenuation": self._modifiers.chest_wall_attenuation,
                "rhythm_override": self._modifiers.rhythm_override,
                "av_block_degree": self._modifiers.av_block_degree,
                "hr_override": self._modifiers.hr_override,
                "pvc_pattern": self._modifiers.pvc_pattern,
                "emotional_arousal": self._modifiers.emotional_arousal,
                "exercise_intensity": self._modifiers.exercise_intensity,
                "caffeine_level": self._modifiers.caffeine_level,
                "alcohol_level": self._modifiers.alcohol_level,
                "temperature": self._modifiers.temperature,
                "dehydration_level": self._modifiers.dehydration_level,
                "sleep_debt": self._modifiers.sleep_debt,
                "fatigue_level": self._modifiers.fatigue_level,
                "potassium_level": self._modifiers.potassium_level,
                "calcium_level": self._modifiers.calcium_level,
                "murmur_type": self._modifiers.murmur_type,
                "murmur_severity": self._modifiers.murmur_severity,
                "af_substrate": self._modifiers.af_substrate,
                "svt_substrate": self._modifiers.svt_substrate,
                "vt_substrate": self._modifiers.vt_substrate,
                "defibrillation_count": self._modifiers.defibrillation_count,
            },
            "conduction_state": self._conduction.get_state() if self._conduction else {},
            "base_hr": self._base_hr,
            "selected_leads": list(self._selected_leads),
            "exercise_duration_sec": self._exercise_duration_sec,
            "high_exercise_duration_sec": self._high_exercise_duration_sec,
        }
        if self._autonomic is not None:
            snap["autonomic_state"] = self._autonomic.get_state()
        if self._pharma is not None:
            snap["pharma_state"] = self._pharma.get_state()
        if self._hemo is not None:
            snap["hemo_state"] = self._hemo.get_state()
        if self._respiratory is not None:
            snap["respiratory_state"] = self._respiratory.get_state()
        if self._hrv is not None:
            snap["hrv_state"] = self._hrv.get_state()
        if self._qt is not None:
            snap["qt_state"] = self._qt.get_state()
        if self._coronary is not None:
            snap["coronary_state"] = self._coronary.get_state()
        # Attach current vitals summary for profile list display
        with self._state_lock:
            v = self._vitals
            snap["heart_rate"] = v.get("heart_rate")
            snap["rhythm"] = v.get("rhythm")
            snap["systolic_bp"] = v.get("systolic_bp")
            snap["diastolic_bp"] = v.get("diastolic_bp")
            snap["spo2"] = v.get("spo2")
            snap["temperature"] = v.get("temperature")
        return snap

    def get_init_payload(self) -> Dict[str, Any]:
        from app.main import SERVER_STARTED_AT
        return {
            "type": "init",
            "vitals": dict(self._vitals),
            "ecg_sr": ECG_SR,
            "pcg_sr": PCG_SR,
            "chunk_interval_ms": int(CHUNK_INTERVAL_SEC * 1000),
            "ecg_chunk_size": ECG_CHUNK_SIZE,
            "pcg_chunk_size": PCG_CHUNK_SIZE,
            "stream_protocol": "sample-clock-v3",
            "available_leads": ALL_LEAD_NAMES,
            "selected_leads": list(self._selected_leads),
            "server_started_at": SERVER_STARTED_AT.isoformat(),
        }

    def set_leads(self, leads: list[str]) -> None:
        valid = [l for l in leads if l in ALL_LEAD_NAMES]
        if not valid:
            valid = ["II"]
        self._selected_leads = valid
        self._ecg_lead_bufs = {}

    # ==================================================================
    # Layer initialisation
    # ==================================================================

    def _ensure_layers(self) -> None:
        if self._conduction is None:
            self._conduction = ParametricConductionNetwork()
        if self._ecg_synth is None:
            self._ecg_synth = EcgSynthesizerV2(sample_rate=ECG_SR)
        if self._pcg_synth is None:
            self._pcg_synth = ParametricPcgSynthesizer()
        if self._hemo is None:
            self._hemo = AlgebraicHemodynamics()

        # Cross-cutting modules
        if self._autonomic is None:
            from app.engine.modulation.autonomic_reflex import AutonomicReflexController
            self._autonomic = AutonomicReflexController()
        if self._pharma is None:
            from app.engine.modulation.pharmacokinetics import PharmacokineticsEngine
            self._pharma = PharmacokineticsEngine()
        if self._respiratory is None:
            from app.engine.respiratory.respiratory_model import RespiratoryModel
            self._respiratory = RespiratoryModel()
        if self._hrv is None:
            from app.engine.core.hrv_generator import HrvGenerator
            self._hrv = HrvGenerator()
        if self._qt is None:
            from app.engine.core.qt_dynamics import QtDynamics
            self._qt = QtDynamics()
        if self._coronary is None:
            from app.engine.modulation.coronary_model import CoronaryModel
            self._coronary = CoronaryModel()
        if self._exercise_model is None:
            from app.engine.exercise_physiology import ExercisePhysiologyModel
            self._exercise_model = ExercisePhysiologyModel()

    # ==================================================================
    # Beat generation
    # ==================================================================

    def _run_one_beat(self) -> None:
        assert self._conduction is not None
        assert self._ecg_synth is not None
        assert self._pcg_synth is not None
        assert self._hemo is not None

        # HR calculation
        if self._modifiers.hr_override is not None:
            target_hr = self._modifiers.hr_override
        else:
            target_hr = self._base_hr * self._modifiers.sa_rate_modifier
        target_hr = max(20.0, min(300.0, target_hr))
        rr_sec = 60.0 / target_hr

        # --- Exercise state accumulation ---
        ex = self._modifiers.exercise_intensity
        if ex > 0.1:
            self._exercise_duration_sec += rr_sec
            if ex > 0.6:
                self._high_exercise_duration_sec += rr_sec
        else:
            self._exercise_duration_sec = max(0.0, self._exercise_duration_sec - rr_sec * 0.5)
            self._high_exercise_duration_sec = max(0.0, self._high_exercise_duration_sec - rr_sec * 0.3)

        if self._exercise_model is not None:
            fatigue_delta = self._exercise_model.compute_fatigue_delta(
                intensity=ex, dt=rr_sec, current_fatigue=self._intent.fatigue_level)
            self._intent.fatigue_level = max(0.0, min(1.0, self._intent.fatigue_level + fatigue_delta))
        if ex > 0.3:
            self._intent.temperature = min(39.5, self._intent.temperature + ex * 0.0003 * rr_sec)

        # --- Pre-conduction physiological updates ---
        if self._respiratory is not None:
            resp_state = self._respiratory.update(
                rr_sec=rr_sec,
                sympathetic_tone=self._modifiers.sympathetic_tone,
                parasympathetic_tone=self._modifiers.parasympathetic_tone,
                exercise_intensity=self._modifiers.exercise_intensity,
                fio2=self._modifiers.fio2,
            )
            self._modifiers.respiratory_phase = resp_state.respiratory_phase
            self._modifiers.intrathoracic_pressure = resp_state.intrathoracic_pressure
            self._modifiers.pao2 = resp_state.pao2
            self._modifiers.paco2 = resp_state.paco2
            self._modifiers.ph = resp_state.ph
            self._modifiers.spo2_physical = resp_state.spo2_physical
            self._modifiers.rr_physical = resp_state.respiratory_rate

        if self._hrv is not None:
            resp_freq = self._modifiers.rr_physical / 60.0 if self._modifiers.rr_physical > 0 else 0.23
            hrv_offset = self._hrv.next_offset(
                sympathetic_tone=self._modifiers.sympathetic_tone,
                parasympathetic_tone=self._modifiers.parasympathetic_tone,
                respiratory_freq_hz=resp_freq,
                respiratory_phase=self._modifiers.respiratory_phase,
            )
            self._modifiers.hrv_rr_offset_ms = hrv_offset

        if self._qt is not None:
            pharma_levels_for_qt: dict[str, float] = {}
            if self._pharma is not None:
                pharma_levels_for_qt = self._pharma.step(0.0)
            qt_ms = self._qt.update(
                rr_sec=rr_sec, dt=rr_sec,
                potassium=self._modifiers.potassium_level,
                calcium=self._modifiers.calcium_level,
                magnesium=self._modifiers.magnesium_level,
                drug_concentrations=pharma_levels_for_qt,
                ischemia_level=self._modifiers.ischemia_level,
                temperature=self._modifiers.temperature,
            )
            self._modifiers.qt_adapted_ms = qt_ms

        # --- Layer 1: Parametric Conduction ---
        conduction: ConductionResult = self._conduction.propagate(rr_sec, self._modifiers)

        # --- Layer 2a: ECG ---
        ecg_frame: EcgFrame = self._ecg_synth.synthesize(
            conduction, self._selected_leads, self._modifiers,
        )

        # --- Layer 2b: PCG ---
        pcg_frame: PcgFrame = self._pcg_synth.synthesize(conduction, self._modifiers)

        # --- Layer 3: Algebraic Hemodynamics ---
        hemo: HemodynamicState = self._hemo.compute(target_hr, rr_sec, self._modifiers)

        # --- Post-hemodynamic coronary update ---
        if self._coronary is not None:
            lv_edp = float(hemo.lv_pressure[0]) if len(hemo.lv_pressure) > 0 else 10.0
            coronary_stenosis = getattr(self._intent, 'coronary_stenosis', 0.0)
            cpp, ischemia = self._coronary.update(
                dbp=hemo.diastolic_bp, lv_edp=lv_edp,
                hr=hemo.heart_rate, sbp=hemo.systolic_bp,
                contractility=self._modifiers.contractility_modifier,
                dt=rr_sec, coronary_stenosis=coronary_stenosis,
            )
            self._modifiers.coronary_perfusion_pressure = cpp
            self._modifiers.ischemia_level = ischemia

        # --- Physiology detail for frontend ---
        from app.engine.core.lttb import lttb_downsample
        _P1_TARGET = 200
        try:
            physiology_detail = {
                "pv_loop": {
                    "lv_pressure": lttb_downsample(hemo.lv_pressure, _P1_TARGET).tolist(),
                    "lv_volume": lttb_downsample(hemo.lv_volume, _P1_TARGET).tolist(),
                },
                "action_potentials": {},
                "cardiac_cycle": {
                    "lv_pressure": lttb_downsample(hemo.lv_pressure, _P1_TARGET).tolist(),
                    "aortic_pressure": lttb_downsample(hemo.aortic_pressure, _P1_TARGET).tolist(),
                    "lv_volume": lttb_downsample(hemo.lv_volume, _P1_TARGET).tolist(),
                    "time_ms": list(range(_P1_TARGET)),
                },
                "valve_events": [
                    {
                        "valve": ve.valve, "action": ve.action,
                        "at_ms": round(ve.at_sample / 5000.0 * 1000.0, 1),
                        "dp_dt": round(ve.dp_dt, 1),
                        "area_ratio": round(ve.area_ratio, 3),
                    }
                    for ve in hemo.valve_events
                ],
            }
        except Exception:
            physiology_detail = None

        with self._state_lock:
            self._latest_physiology_detail = physiology_detail

        # --- Update modulation ---
        self._update_modulation(hemo, rr_sec)

        # --- Buffer ECG ---
        lead_key = "II" if "II" in ecg_frame.samples else next(iter(ecg_frame.samples), None)
        if lead_key and lead_key in ecg_frame.samples:
            for v in ecg_frame.samples[lead_key]:
                self._ecg_buf.append(float(v))
        for lead_name, lead_samples in ecg_frame.samples.items():
            if lead_name == lead_key:
                continue
            if lead_name not in self._ecg_lead_bufs:
                self._ecg_lead_bufs[lead_name] = deque()
            buf = self._ecg_lead_bufs[lead_name]
            for v in lead_samples:
                buf.append(float(v))

        # --- Buffer PCG ---
        for v in pcg_frame.samples:
            self._pcg_buf.append(float(v))
        for pos, ch_samples in pcg_frame.channels.items():
            buf = self._pcg_bufs.get(pos)
            if buf is not None:
                for v in ch_samples:
                    buf.append(float(v))

        # --- Update vitals ---
        new_vitals = {
            "heart_rate": round(hemo.heart_rate, 1),
            "systolic_bp": round(hemo.systolic_bp, 1),
            "diastolic_bp": round(hemo.diastolic_bp, 1),
            "spo2": round(hemo.spo2, 1),
            "temperature": round(self._modifiers.temperature, 1),
            "respiratory_rate": round(hemo.respiratory_rate, 1),
            "rhythm": conduction.beat_kind,
            "cardiac_output": round(hemo.cardiac_output, 2),
            "ejection_fraction": round(hemo.ejection_fraction, 1),
            "stroke_volume": round(hemo.stroke_volume, 1),
            "sympathetic_tone": round(self._modifiers.sympathetic_tone, 2),
            "parasympathetic_tone": round(self._modifiers.parasympathetic_tone, 2),
            "av_block_degree": self._modifiers.av_block_degree,
            "murmur_type": self._modifiers.murmur_type,
            "murmur_severity": round(self._modifiers.murmur_severity, 2),
            "potassium_level": round(self._modifiers.potassium_level, 1),
            "calcium_level": round(self._modifiers.calcium_level, 1),
            "exercise_intensity": round(self._intent.exercise_intensity, 2),
            "emotional_arousal": round(self._modifiers.emotional_arousal, 2),
            "caffeine_level": round(self._modifiers.caffeine_level, 2),
            "alcohol_level": round(self._modifiers.alcohol_level, 2),
            "dehydration_level": round(self._modifiers.dehydration_level, 2),
            "sleep_debt": round(self._modifiers.sleep_debt, 2),
            "damage_level": round(self._modifiers.damage_level, 2),
            "pvc_pattern": self._modifiers.pvc_pattern,
            "af_substrate": round(self._modifiers.af_substrate, 2),
            "svt_substrate": round(self._modifiers.svt_substrate, 2),
            "vt_substrate": round(self._modifiers.vt_substrate, 2),
            "defibrillation_count": self._modifiers.defibrillation_count,
            "fatigue_level": round(self._modifiers.fatigue_level, 2),
            "gallop_s3": pcg_frame.s3_present,
            "gallop_s4": pcg_frame.s4_present,
            "hr_override_active": self._modifiers.hr_override is not None,
            "hr_override_value": self._modifiers.hr_override,
            "arrhythmia_episode_type": self._conduction._episode_rhythm if self._conduction else '',
            "arrhythmia_episode_beats": self._conduction._episode_beats_remaining if self._conduction else 0,
            "pao2": round(self._modifiers.pao2, 1),
            "paco2": round(self._modifiers.paco2, 1),
            "ph": round(self._modifiers.ph, 3),
            "fio2": round(self._modifiers.fio2, 2),
            "magnesium_level": round(self._modifiers.magnesium_level, 1),
            "intrathoracic_pressure": round(self._modifiers.intrathoracic_pressure, 1),
            "coronary_perfusion_pressure": round(self._modifiers.coronary_perfusion_pressure, 1),
            "ischemia_level": round(self._modifiers.ischemia_level, 3),
            "qt_adapted_ms": round(self._modifiers.qt_adapted_ms, 1),
            "hrv_rr_offset_ms": round(self._modifiers.hrv_rr_offset_ms, 1),
            "rv_ejection_fraction": round(hemo.rv_ejection_fraction, 1),
            "pa_systolic": round(hemo.pa_systolic, 1),
            "pa_diastolic": round(hemo.pa_diastolic, 1),
            "pa_mean": round(hemo.pa_mean, 1),
            "rv_stroke_volume": round(hemo.rv_stroke_volume, 1),
            "coronary_stenosis": round(getattr(self._intent, 'coronary_stenosis', 0.0), 2),
            "raas_activation": round(self._autonomic.raas_activation, 3) if self._autonomic and hasattr(self._autonomic, 'raas_activation') else 0.0,
        }

        annotation = {
            "beat_index": conduction.beat_index,
            "rr_sec": conduction.rr_sec,
            "beat_kind": conduction.beat_kind,
            "pr_interval_ms": round(conduction.pr_interval_ms, 1),
            "qrs_duration_ms": round(conduction.qrs_duration_ms, 1),
            "qt_interval_ms": round(conduction.qt_interval_ms, 1),
            "p_wave_present": conduction.p_wave_present,
            "conducted": conduction.conducted,
            "instantaneous_hr": round(hemo.heart_rate, 1),
        }

        with self._state_lock:
            self._vitals = new_vitals
            self._recent_beat_annotations.append(annotation)
            self._conduction_history.append(annotation)

    def _update_modulation(self, hemo: HemodynamicState, rr_sec: float) -> None:
        from app.engine.modulation.autonomic_reflex import AutonomicReflexController
        from app.engine.modulation.pharmacokinetics import PharmacokineticsEngine
        from app.engine.modulation.physiology_modulator import (
            AutonomicState, compute_modifiers,
        )
        from app.engine.simulation.validator import check_beat_invariants

        # 1. Autonomic reflex
        if self._autonomic is not None:
            symp, para = self._autonomic.update(
                hemo.mean_arterial_pressure, rr_sec,
                cardiac_output=hemo.cardiac_output,
                spo2=hemo.spo2,
                paco2=self._modifiers.paco2,
                pao2=self._modifiers.pao2,
                ph=self._modifiers.ph,
                temperature=self._modifiers.temperature,
            )
        else:
            symp = self._modifiers.sympathetic_tone
            para = self._modifiers.parasympathetic_tone

        # 2. Pharmacokinetics
        pharma_levels: dict[str, float] = {}
        if self._pharma is not None:
            pharma_levels = self._pharma.step(rr_sec)

        # 3. Smooth user intent
        smoothed = self._transition.update(self._intent, rr_sec)

        # 4. Compute modifiers — build a state_ref-like object for exercise model
        state_ref = self._build_state_ref()

        self._modifiers = compute_modifiers(
            autonomic=AutonomicState(sympathetic_tone=symp, parasympathetic_tone=para),
            pharma_levels=pharma_levels,
            damage_level=smoothed.damage_level,
            base_modifiers=None,
            interaction=smoothed,
            state_ref=state_ref,
            beat_index=self._conduction._beat_index if self._conduction else 0,
        )

        # 5. Invariant validation
        violations = check_beat_invariants(hemo)
        for v in violations:
            if v.severity == "error":
                logger.warning("Invariant violation: %s", v.message)

    def _build_state_ref(self) -> Any:
        """Build a minimal state_ref for compute_modifiers exercise model."""
        class _StateRef:
            pass
        ref = _StateRef()
        ref._exercise_model = self._exercise_model
        ref._exercise_duration_sec = self._exercise_duration_sec
        ref._high_exercise_duration_sec = self._high_exercise_duration_sec
        return ref

    # ==================================================================
    # Async loops
    # ==================================================================

    async def _beat_loop(self) -> None:
        loop = asyncio.get_running_loop()
        try:
            while self._running:
                if self._modifiers.hr_override is not None:
                    eff_hr = self._modifiers.hr_override
                else:
                    eff_hr = self._base_hr * self._modifiers.sa_rate_modifier
                eff_hr = max(20.0, min(300.0, eff_hr))
                rr_sec = 60.0 / eff_hr

                buffered_ecg_chunks = len(self._ecg_buf) / ECG_CHUNK_SIZE

                if buffered_ecg_chunks < 3:
                    batch = 3 if eff_hr > 120 else 2
                    await loop.run_in_executor(None, self._run_batch_beats, batch)
                    sleep_time = 0.001
                elif buffered_ecg_chunks < 8:
                    batch = 2 if eff_hr > 120 else 1
                    await loop.run_in_executor(None, self._run_batch_beats, batch)
                    sleep_time = rr_sec * 0.3 if eff_hr > 120 else rr_sec * 0.5
                elif buffered_ecg_chunks > 20:
                    await loop.run_in_executor(None, self._run_one_beat)
                    sleep_time = rr_sec * 0.90
                else:
                    await loop.run_in_executor(None, self._run_one_beat)
                    sleep_time = rr_sec * 0.70

                await asyncio.sleep(max(0.001, sleep_time))
        except asyncio.CancelledError:
            pass

    def _run_batch_beats(self, count: int) -> None:
        for _ in range(count):
            self._run_one_beat()

    async def _stream_loop(self) -> None:
        loop_start = time.monotonic()
        try:
            while self._running:
                ecg_avail = min(len(self._ecg_buf), ECG_CHUNK_SIZE)
                pcg_avail = min(len(self._pcg_buf), PCG_CHUNK_SIZE)

                ecg_frac = ecg_avail / ECG_CHUNK_SIZE if ECG_CHUNK_SIZE > 0 else 0
                pcg_frac = pcg_avail / PCG_CHUNK_SIZE if PCG_CHUNK_SIZE > 0 else 0
                drain_frac = min(ecg_frac, pcg_frac) if ecg_frac > 0 and pcg_frac > 0 else max(ecg_frac, pcg_frac)

                ecg_n = max(0, int(ECG_CHUNK_SIZE * drain_frac))
                pcg_n = max(0, int(PCG_CHUNK_SIZE * drain_frac))

                ecg_chunk = [self._ecg_buf.popleft() for _ in range(ecg_n)]
                ecg_start = self._ecg_sample_counter
                self._ecg_sample_counter += ecg_n

                pcg_chunk = [self._pcg_buf.popleft() for _ in range(pcg_n)]
                pcg_start = self._pcg_sample_counter
                self._pcg_sample_counter += pcg_n

                pcg_channels: Dict[str, list] = {}
                for pos, buf in self._pcg_bufs.items():
                    ch_n = min(len(buf), PCG_CHUNK_SIZE)
                    ch_chunk = [buf.popleft() for _ in range(ch_n)]
                    pcg_channels[pos] = [round(v, 4) for v in ch_chunk]

                ecg_leads: Dict[str, list] = {}
                for lead_name, buf in self._ecg_lead_bufs.items():
                    ln = min(len(buf), ecg_n)
                    lead_chunk = [buf.popleft() for _ in range(ln)]
                    if ln < ecg_n:
                        lead_chunk.extend([0.0] * (ecg_n - ln))
                    if ecg_n > 0:
                        ecg_leads[lead_name] = lead_chunk

                with self._state_lock:
                    current_vitals = dict(self._vitals)
                    current_beat_annotations = self._recent_beat_annotations.copy()
                    self._recent_beat_annotations.clear()
                    physiology_detail = self._latest_physiology_detail
                    self._latest_physiology_detail = None

                current_seq = self._stream_seq
                self._stream_seq += 1
                server_elapsed = round(time.monotonic() - self._start_time, 3)

                if self._use_binary_protocol and self._send_binary_callback:
                    from app.engine.ws_binary_protocol import encode_signal_frame
                    vitals_delta = self._binary_encoder.compute_vitals_delta(current_vitals)
                    frame_bytes = encode_signal_frame(
                        seq=current_seq,
                        ecg_samples=ecg_chunk, pcg_samples=pcg_chunk,
                        ecg_start_sample=ecg_start, pcg_start_sample=pcg_start,
                        vitals_delta=vitals_delta,
                        beat_annotations=current_beat_annotations,
                        server_elapsed_sec=server_elapsed,
                        ecg_leads=ecg_leads if ecg_leads else None,
                    )
                    try:
                        await self._send_binary_callback(frame_bytes)
                    except Exception:
                        self._running = False
                        break
                elif self._send_callback:
                    message: Dict[str, Any] = {
                        "type": "signal",
                        "seq": current_seq,
                        "ecg": [round(v, 4) for v in ecg_chunk],
                        "pcg": [round(v, 4) for v in pcg_chunk],
                        "pcg_channels": pcg_channels,
                        "ecg_start_sample": ecg_start,
                        "pcg_start_sample": pcg_start,
                        "chunk_duration_ms": int(CHUNK_INTERVAL_SEC * 1000),
                        "timeline_sec": round(pcg_start / PCG_SR, 4),
                        "server_elapsed_sec": server_elapsed,
                        "vitals": current_vitals,
                        "beat_annotations": current_beat_annotations,
                    }
                    if ecg_leads:
                        message["ecg_leads"] = {
                            k: [round(v, 4) for v in samples]
                            for k, samples in ecg_leads.items()
                        }
                    if physiology_detail is not None:
                        message["physiology_detail"] = physiology_detail
                    try:
                        await self._send_callback(message)
                    except Exception:
                        self._running = False
                        break

                target_time = loop_start + (current_seq + 1) * CHUNK_INTERVAL_SEC
                sleep_dur = target_time - time.monotonic()
                if sleep_dur > 0:
                    await asyncio.sleep(sleep_dur)
        except asyncio.CancelledError:
            pass

    # ==================================================================
    # Helpers
    # ==================================================================

    @staticmethod
    def _default_vitals() -> dict[str, Any]:
        return {
            "heart_rate": 72.0, "systolic_bp": 120.0, "diastolic_bp": 80.0,
            "spo2": 98.0, "temperature": 36.6, "respiratory_rate": 16.0,
            "rhythm": "normal", "cardiac_output": 5.0, "ejection_fraction": 60.0,
            "stroke_volume": 70.0, "sympathetic_tone": 0.5, "parasympathetic_tone": 0.5,
            "av_block_degree": 0, "murmur_type": "", "murmur_severity": 0.0,
            "potassium_level": 4.0, "calcium_level": 9.5, "exercise_intensity": 0.0,
            "emotional_arousal": 0.0, "caffeine_level": 0.0, "alcohol_level": 0.0,
            "dehydration_level": 0.0, "sleep_debt": 0.0, "damage_level": 0.0,
            "pvc_pattern": "isolated", "af_substrate": 0.0, "svt_substrate": 0.0,
            "vt_substrate": 0.0, "defibrillation_count": 0, "fatigue_level": 0.0,
            "pao2": 95.0, "paco2": 40.0, "ph": 7.40, "fio2": 0.21,
            "magnesium_level": 2.0, "intrathoracic_pressure": -5.0,
            "coronary_perfusion_pressure": 70.0, "ischemia_level": 0.0,
            "qt_adapted_ms": 0.0, "hrv_rr_offset_ms": 0.0,
            "rv_ejection_fraction": 55.0, "pa_systolic": 25.0, "pa_diastolic": 10.0,
            "pa_mean": 15.0, "rv_stroke_volume": 70.0, "coronary_stenosis": 0.0,
            "raas_activation": 0.0,
        }

    def _restore_snapshot(self, snapshot: dict) -> None:
        if "intent_state" in snapshot:
            self._intent = InteractionState.from_dict(snapshot["intent_state"])
        if "transition_state" in snapshot:
            self._transition.set_state(snapshot["transition_state"])

        if "modifiers" in snapshot:
            m = snapshot["modifiers"]
            for key, default in [
                ("sa_rate_modifier", 1.0), ("av_delay_modifier", 1.0),
                ("contractility_modifier", 1.0), ("sympathetic_tone", 0.5),
                ("parasympathetic_tone", 0.5), ("damage_level", 0.0),
                ("tpr_modifier", 1.0), ("preload_modifier", 1.0),
                ("chest_wall_attenuation", 1.0), ("rhythm_override", ''),
                ("av_block_degree", 0), ("hr_override", None),
                ("pvc_pattern", 'isolated'), ("emotional_arousal", 0.0),
                ("exercise_intensity", 0.0), ("caffeine_level", 0.0),
                ("alcohol_level", 0.0), ("temperature", 36.6),
                ("dehydration_level", 0.0), ("sleep_debt", 0.0),
                ("fatigue_level", 0.0), ("potassium_level", 4.0),
                ("calcium_level", 9.5), ("murmur_type", ''),
                ("murmur_severity", 0.0), ("af_substrate", 0.0),
                ("svt_substrate", 0.0), ("vt_substrate", 0.0),
                ("defibrillation_count", 0),
            ]:
                setattr(self._modifiers, key, m.get(key, default))

            if "intent_state" not in snapshot:
                self._intent = InteractionState.from_modifiers(self._modifiers)

        if "base_hr" in snapshot:
            self._base_hr = snapshot["base_hr"]
        if "selected_leads" in snapshot:
            self._selected_leads = snapshot["selected_leads"]

        self._exercise_duration_sec = snapshot.get("exercise_duration_sec", 0.0)
        self._high_exercise_duration_sec = snapshot.get("high_exercise_duration_sec", 0.0)

        if "conduction_state" in snapshot and snapshot["conduction_state"]:
            self._ensure_layers()
            assert self._conduction is not None
            self._conduction.set_state(snapshot["conduction_state"])

        # Restore cross-cutting module states
        for key, attr in [
            ("autonomic_state", "_autonomic"),
            ("pharma_state", "_pharma"),
            ("respiratory_state", "_respiratory"),
            ("hrv_state", "_hrv"),
            ("qt_state", "_qt"),
            ("coronary_state", "_coronary"),
            ("hemo_state", "_hemo"),
        ]:
            if key in snapshot:
                self._ensure_layers()
                obj = getattr(self, attr)
                if obj is not None and hasattr(obj, 'set_state'):
                    obj.set_state(snapshot[key])

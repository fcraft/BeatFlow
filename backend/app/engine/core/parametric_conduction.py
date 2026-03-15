"""V3 parametric conduction network — timing-based, no ODE.

Replaces the V2 ConductionNetworkV2 (which ran Mitchell-Schaeffer ODE at
5000 Hz per beat).  V3 computes activation times, intervals, and beat kind
directly from parameters and modifiers using algebraic formulas.

Features preserved from V2:
- Substrate-triggered probabilistic arrhythmia episodes (AF/SVT/VT)
- AV block (I/II/III degree, Wenckebach)
- PVC ectopic foci injection
- HRV RR offset application
- VF/asystole/VT special beats
"""
from __future__ import annotations

import random
from typing import Any, Optional

import numpy as np

from app.engine.core.types import (
    ActionPotential,
    ConductionResult,
    EctopicFocus,
    Modifiers,
)

# Default inter-node propagation delays (ms)
_DEFAULT_DELAYS = {
    'sa_av': 80.0,
    'av_his': 30.0,
    'his_purkinje': 15.0,
}

_NODE_ORDER = ('sa', 'av', 'his', 'purkinje')


class ParametricConductionNetwork:
    """V3 parametric cardiac conduction network.

    Computes one beat's conduction timing without ODE integration.
    Output is a ConductionResult compatible with EcgSynthesizerV2.
    """

    def __init__(self) -> None:
        self._beat_index: int = 0
        self._delays = dict(_DEFAULT_DELAYS)

        # AV block state
        self._wenckebach_counter: int = 0
        self._wenckebach_cycle: int = 4

        # Substrate-triggered episode state
        self._episode_rhythm: str = ''
        self._episode_beats_remaining: int = 0
        self._episode_cooldown: int = 0

    def propagate(self, rr_sec: float, modifiers: Modifiers) -> ConductionResult:
        """Compute one beat's conduction parameters."""
        # --- Apply HRV RR offset ---
        hrv_offset_ms = getattr(modifiers, 'hrv_rr_offset_ms', 0.0)
        if hrv_offset_ms != 0.0:
            rr_sec = rr_sec + hrv_offset_ms / 1000.0
            rr_sec = max(0.3, min(2.5, rr_sec))

        # --- Rhythm override handling ---
        rhythm = getattr(modifiers, 'rhythm_override', '')
        if not rhythm:
            rhythm = self._evaluate_substrate_triggers(modifiers)
        avb = getattr(modifiers, 'av_block_degree', 0)

        # VF: chaotic
        if rhythm == 'vf':
            return self._generate_vf_beat(rr_sec, modifiers)

        # Asystole: flat line
        if rhythm == 'asystole':
            return self._generate_asystole_beat(rr_sec)

        # AF: irregular RR
        if rhythm == 'af':
            jitter = np.random.uniform(-0.25, 0.25)
            rr_sec = max(0.3, min(2.0, rr_sec * (1.0 + jitter)))

        # VT: ventricular ectopic
        if rhythm == 'vt':
            return self._generate_vt_beat(rr_sec, modifiers)

        is_svt = (rhythm == 'svt')

        # --- Compute activation times (ms) ---
        sa_time = 0.0
        av_time = sa_time + self._delays['sa_av'] * modifiers.av_delay_modifier
        his_time = av_time + self._delays['av_his']
        purkinje_time = his_time + self._delays['his_purkinje']

        activation_times = {
            'sa': sa_time,
            'av': av_time,
            'his': his_time,
            'purkinje': purkinje_time,
        }

        # --- PVC ectopic handling ---
        is_pvc = False
        for focus in modifiers.ectopic_foci:
            if focus.node == 'purkinje':
                purkinje_time = focus.coupling_interval_ms
                activation_times['purkinje'] = purkinje_time
                is_pvc = True

        # --- AV Block logic ---
        conducted = True
        p_wave_present = True

        if avb >= 1:
            if avb == 1:
                pass  # PR prolongation handled by av_delay_modifier
            elif avb == 2:
                self._wenckebach_counter += 1
                if self._wenckebach_counter >= self._wenckebach_cycle:
                    conducted = False
                    self._wenckebach_counter = 0
            elif avb == 3:
                conducted = False

        # AF: no organized P wave
        if rhythm == 'af':
            p_wave_present = False

        # --- Compute intervals ---
        total_ms = rr_sec * 1000.0

        if conducted and not is_pvc:
            pr_ms = purkinje_time - sa_time + 40.0  # +40ms electromechanical
        elif is_pvc:
            pr_ms = 0.0
        else:
            pr_ms = 160.0  # fallback for non-conducted

        # QRS duration
        if is_pvc or rhythm == 'vt':
            qrs_ms = np.random.uniform(120.0, 180.0)
        else:
            qrs_ms = np.random.uniform(80.0, 100.0)

        # QT interval: use qt_adapted_ms from QtDynamics if available
        qt_adapted = getattr(modifiers, 'qt_adapted_ms', 0.0)
        if qt_adapted > 200.0:
            qt_ms = qt_adapted
        else:
            # Bazett fallback: QTc ≈ 420ms, QT = QTc × sqrt(RR)
            import math
            qt_ms = 420.0 * math.sqrt(max(0.3, rr_sec))

        # APD estimate for node_aps (used by ECG synthesizer for T-wave positioning)
        apd_purkinje = qt_ms * 0.85  # Purkinje APD ≈ 85% of QT

        # Build lightweight ActionPotential objects (no ODE traces)
        node_aps = {}
        for name in _NODE_ORDER:
            if name == 'purkinje':
                apd = apd_purkinje
            elif name == 'sa':
                apd = apd_purkinje * 0.7
            else:
                apd = apd_purkinje * 0.8
            node_aps[name] = ActionPotential(
                vm=0.0 if not conducted else 0.8,
                h_gate=1.0,
                calcium_transient=0.0,
                phase='resting' if not conducted else 'repolarizing',
                refractory=False,
                apd_ms=apd,
            )

        # If not conducted, mark his/purkinje activation at beat end
        if not conducted:
            activation_times['his'] = total_ms
            activation_times['purkinje'] = total_ms

        self._beat_index += 1

        beat_kind: str
        if is_pvc:
            beat_kind = 'pvc'
        elif rhythm == 'af':
            beat_kind = 'af'
        elif is_svt:
            beat_kind = 'svt'
        else:
            beat_kind = 'sinus'

        return ConductionResult(
            beat_index=self._beat_index,
            rr_sec=rr_sec,
            activation_times=activation_times,
            node_aps=node_aps,
            pr_interval_ms=pr_ms,
            qrs_duration_ms=qrs_ms,
            qt_interval_ms=qt_ms,
            p_wave_present=p_wave_present and rhythm != 'af',
            p_wave_retrograde=False,
            beat_kind=beat_kind,
            conducted=conducted,
        )

    # ------------------------------------------------------------------
    # Special beats
    # ------------------------------------------------------------------

    def _generate_vf_beat(self, rr_sec: float, modifiers: Modifiers) -> ConductionResult:
        self._beat_index += 1
        total_ms = rr_sec * 1000.0
        node_aps = {
            name: ActionPotential(
                vm=0.3, phase='depolarizing', apd_ms=0.0,
            )
            for name in _NODE_ORDER
        }
        return ConductionResult(
            beat_index=self._beat_index, rr_sec=rr_sec,
            activation_times={name: 0.0 for name in _NODE_ORDER},
            node_aps=node_aps,
            pr_interval_ms=0.0, qrs_duration_ms=0.0, qt_interval_ms=0.0,
            p_wave_present=False, p_wave_retrograde=False,
            beat_kind='vf', conducted=False,
        )

    def _generate_asystole_beat(self, rr_sec: float) -> ConductionResult:
        self._beat_index += 1
        total_ms = rr_sec * 1000.0
        node_aps = {
            name: ActionPotential(phase='resting', apd_ms=0.0)
            for name in _NODE_ORDER
        }
        return ConductionResult(
            beat_index=self._beat_index, rr_sec=rr_sec,
            activation_times={name: total_ms for name in _NODE_ORDER},
            node_aps=node_aps,
            pr_interval_ms=0.0, qrs_duration_ms=0.0, qt_interval_ms=0.0,
            p_wave_present=False, p_wave_retrograde=False,
            beat_kind='asystole', conducted=False,
        )

    def _generate_vt_beat(self, rr_sec: float, modifiers: Modifiers) -> ConductionResult:
        self._beat_index += 1
        total_ms = rr_sec * 1000.0
        qt_adapted = getattr(modifiers, 'qt_adapted_ms', 0.0)
        qt_ms = qt_adapted if qt_adapted > 200.0 else 400.0
        qrs_ms = np.random.uniform(120.0, 200.0)
        node_aps = {
            name: ActionPotential(
                vm=0.8 if name == 'purkinje' else 0.0,
                phase='depolarizing' if name == 'purkinje' else 'resting',
                apd_ms=qt_ms * 0.85 if name == 'purkinje' else 0.0,
            )
            for name in _NODE_ORDER
        }
        return ConductionResult(
            beat_index=self._beat_index, rr_sec=rr_sec,
            activation_times={
                'sa': total_ms, 'av': total_ms, 'his': total_ms,
                'purkinje': 0.0,
            },
            node_aps=node_aps,
            pr_interval_ms=0.0, qrs_duration_ms=qrs_ms, qt_interval_ms=qt_ms,
            p_wave_present=False, p_wave_retrograde=False,
            beat_kind='vt', conducted=True,
        )

    # ------------------------------------------------------------------
    # Substrate-triggered arrhythmia episodes
    # ------------------------------------------------------------------

    def _evaluate_substrate_triggers(self, modifiers: Modifiers) -> str:
        if self._episode_beats_remaining > 0:
            self._episode_beats_remaining -= 1
            rhythm = self._episode_rhythm
            if self._episode_beats_remaining <= 0:
                self._episode_cooldown = random.randint(20, 60)
                self._episode_rhythm = ''
            return rhythm

        if self._episode_cooldown > 0:
            self._episode_cooldown -= 1
            return ''

        af_sub = getattr(modifiers, 'af_substrate', 0.0)
        svt_sub = getattr(modifiers, 'svt_substrate', 0.0)
        vt_sub = getattr(modifiers, 'vt_substrate', 0.0)

        p_af = af_sub ** 2 * 0.08
        p_svt = svt_sub ** 2 * 0.06
        p_vt = vt_sub ** 2 * 0.04

        r = random.random()
        if r < p_af:
            self._episode_rhythm = 'af'
            self._episode_beats_remaining = random.randint(10, 50)
            return 'af'
        r -= p_af
        if r < p_svt:
            self._episode_rhythm = 'svt'
            self._episode_beats_remaining = random.randint(8, 30)
            return 'svt'
        r -= p_svt
        if r < p_vt:
            self._episode_rhythm = 'vt'
            self._episode_beats_remaining = random.randint(5, 15)
            return 'vt'

        return ''

    # ------------------------------------------------------------------
    # State management
    # ------------------------------------------------------------------

    def get_state(self) -> dict[str, Any]:
        return {
            'beat_index': self._beat_index,
            'delays': dict(self._delays),
            'wenckebach_counter': self._wenckebach_counter,
            'wenckebach_cycle': self._wenckebach_cycle,
            'episode_rhythm': self._episode_rhythm,
            'episode_beats_remaining': self._episode_beats_remaining,
            'episode_cooldown': self._episode_cooldown,
        }

    def set_state(self, state: dict[str, Any]) -> None:
        self._beat_index = state.get('beat_index', 0)
        self._delays = dict(state.get('delays', _DEFAULT_DELAYS))
        self._wenckebach_counter = state.get('wenckebach_counter', 0)
        self._wenckebach_cycle = state.get('wenckebach_cycle', 4)
        self._episode_rhythm = state.get('episode_rhythm', '')
        self._episode_beats_remaining = state.get('episode_beats_remaining', 0)
        self._episode_cooldown = state.get('episode_cooldown', 0)

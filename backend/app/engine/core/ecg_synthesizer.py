"""ECG synthesizer: convert conduction network output to 12-lead surface ECG.

V2 architecture: VCG (Vectorcardiogram) intermediate representation.

Pipeline:
  1. Build 3 orthogonal VCG components (X=left-right, Y=foot-head, Z=front-back)
     using Gaussian basis functions at 5000 Hz internal rate
  2. Project VCG to 12 standard leads via Dower inverse transform matrix
  3. Guarantee Einthoven constraint: III = II - I (computed, not projected)
  4. Downsample from 5000 Hz to target sample_rate (default 500 Hz)
  5. Add configurable per-lead electrode noise
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
from scipy.signal import resample_poly

from app.engine.core.types import ConductionResult, EcgFrame, Modifiers

# Internal cell-model sample rate
_CELL_RATE = 5000

# Amplitude scaling so Lead II R-peak lands near 1.0-1.8 mV
_MV_SCALE = 1.8

# ---------------------------------------------------------------------------
# Dower inverse transform coefficients: VCG (X, Y, Z) → 12-lead ECG
# Rows: I, II, V1, V2, V3, V4, V5, V6
# III, aVR, aVL, aVF derived from I/II to guarantee Einthoven exactly.
# Reference: Dower et al., "Deriving the 12-lead ECG from VCG leads"
# Coefficients tuned for parametric simulation quality.
# ---------------------------------------------------------------------------
_DOWER_INV = np.array([
    # X        Y        Z         ← VCG component
    [ 0.632, -0.235,  0.059],    # Lead I
    [-0.235,  1.066, -0.132],    # Lead II
    [-0.515,  0.157,  0.917],    # V1
    [ 0.044,  0.164,  1.387],    # V2
    [ 0.882,  0.098,  1.277],    # V3
    [ 1.213,  0.127,  0.601],    # V4
    [ 1.125,  0.127, -0.086],    # V5
    [ 0.831,  0.076, -0.230],    # V6
], dtype=np.float64)

# Map from row index in _DOWER_INV to lead name
_DOWER_LEAD_NAMES = ['I', 'II', 'V1', 'V2', 'V3', 'V4', 'V5', 'V6']


@dataclass
class _VcgComponents:
    """Internal VCG 3-component intermediate representation (not public API)."""
    x: NDArray[np.float64]   # Left-right axis
    y: NDArray[np.float64]   # Foot-head axis (≈ Lead II direction)
    z: NDArray[np.float64]   # Front-back axis (key for V-lead transition)


class EcgSynthesizerV2:
    """Synthesize 12-lead ECG from conduction network output via VCG."""

    def __init__(self, sample_rate: int = 500) -> None:
        self.sample_rate = sample_rate
        # T-wave carryover buffer per VCG component for P-on-T fusion
        self._t_wave_carryover_x: NDArray[np.float64] | None = None
        self._t_wave_carryover_y: NDArray[np.float64] | None = None
        self._t_wave_carryover_z: NDArray[np.float64] | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def synthesize(
        self,
        conduction: ConductionResult,
        leads: list[str],
        modifiers: Modifiers,
    ) -> EcgFrame:
        """Produce an EcgFrame for the requested leads.

        Args:
            conduction: Output of ConductionNetworkV2.propagate().
            leads: Which of the 12 standard leads to include.
            modifiers: Current modifier set (electrode_noise used here).

        Returns:
            EcgFrame with downsampled lead arrays and beat annotations.
        """
        # 1. Build VCG components at cell-model rate (5000 Hz)
        vcg = self._build_vcg(conduction, modifiers)

        # 1b. Apply T-wave carryover from previous beat (P-on-T fusion)
        for attr, comp in [
            ('_t_wave_carryover_x', 'x'),
            ('_t_wave_carryover_y', 'y'),
            ('_t_wave_carryover_z', 'z'),
        ]:
            carry = getattr(self, attr)
            arr = getattr(vcg, comp)
            if carry is not None and len(carry) > 0:
                overlap = min(len(carry), len(arr))
                arr[:overlap] += carry[:overlap]
                setattr(self, attr, None)

        # 1c. Compute and save T-wave overflow for next beat
        self._compute_t_wave_overflow_vcg(conduction, modifiers)

        # 2. Project VCG to requested leads
        raw_leads = self._project_vcg_to_leads(vcg, leads)

        # 3. Downsample to target sample_rate
        target_len = int(conduction.rr_sec * self.sample_rate)
        samples: dict[str, NDArray[np.float64]] = {}
        for name, signal in raw_leads.items():
            ds = self._downsample(signal, target_len)
            # Add electrode noise
            noise_std = modifiers.electrode_noise.get(name, 0.0)
            if noise_std > 0:
                ds = ds + np.random.default_rng().normal(0, noise_std, len(ds))
            samples[name] = ds

        # 4. Beat annotations
        annotations = [
            {
                'beat_index': conduction.beat_index,
                'rr_sec': conduction.rr_sec,
                'beat_kind': conduction.beat_kind,
                'pr_interval_ms': conduction.pr_interval_ms,
                'qrs_duration_ms': conduction.qrs_duration_ms,
                'qt_interval_ms': conduction.qt_interval_ms,
                'p_wave_present': conduction.p_wave_present,
                'conducted': conduction.conducted,
            }
        ]

        return EcgFrame(
            samples=samples,
            sample_rate=self.sample_rate,
            beat_annotations=annotations,
        )

    # ------------------------------------------------------------------
    # VCG construction (dispatches by beat_kind)
    # ------------------------------------------------------------------

    def _build_vcg(
        self,
        conduction: ConductionResult,
        modifiers: Modifiers | None = None,
    ) -> _VcgComponents:
        """Build VCG 3-component representation for one beat."""
        sr = _CELL_RATE
        n = int(conduction.rr_sec * sr)
        t = np.arange(n, dtype=np.float64) / sr

        beat_kind = conduction.beat_kind

        if beat_kind == 'vt':
            return self._build_vt_vcg(t, n, conduction)
        elif beat_kind == 'pvc':
            return self._build_pvc_vcg(t, n, conduction)
        elif beat_kind == 'vf':
            return self._build_vf_vcg(t, n)
        elif beat_kind == 'asystole':
            z = np.zeros(n, dtype=np.float64)
            return _VcgComponents(x=z.copy(), y=z.copy(), z=z.copy())

        return self._build_sinus_vcg(t, n, conduction, modifiers)

    # ------------------------------------------------------------------
    # Sinus VCG (also SVT / AF)
    # ------------------------------------------------------------------

    @staticmethod
    def _build_sinus_vcg(
        t: NDArray[np.float64],
        n: int,
        conduction: ConductionResult,
        modifiers: Modifiers | None = None,
    ) -> _VcgComponents:
        """Build VCG for normal sinus / SVT / AF beats.

        Each component (X, Y, Z) has independent P-QRS-T morphology with
        physiologically motivated amplitudes and timing.
        """
        _g = EcgSynthesizerV2._gaussian
        x = np.zeros(n, dtype=np.float64)
        y = np.zeros(n, dtype=np.float64)
        z = np.zeros(n, dtype=np.float64)

        act_times = {k: v / 1000.0 for k, v in conduction.activation_times.items()}
        apds = {k: ap.apd_ms / 1000.0 for k, ap in conduction.node_aps.items()}

        # --- Extract modifiers ---
        qt_ms = 0.0
        ischemia_level = 0.0
        potassium = 4.0
        if modifiers is not None:
            qt_ms = getattr(modifiers, 'qt_adapted_ms', 0.0)
            ischemia_level = getattr(modifiers, 'ischemia_level', 0.0)
            potassium = getattr(modifiers, 'potassium_level', 4.0)

        # ==============================================================
        # P WAVE — atrial depolarisation
        # ==============================================================
        if conduction.p_wave_present:
            t_p = act_times['sa']
            # X: positive (atria depolarise left)
            x += _g(t, t_p, sigma=0.040, amplitude=0.08)
            x += _g(t, t_p + 0.050, sigma=0.030, amplitude=0.02)
            # Y: positive (atria depolarise inferiorly)
            y += _g(t, t_p, sigma=0.040, amplitude=0.12)
            y += _g(t, t_p + 0.060, sigma=0.030, amplitude=0.03)
            # Z: biphasic — positive then negative (classic V1 P-wave)
            z += _g(t, t_p, sigma=0.030, amplitude=0.06)
            z += _g(t, t_p + 0.060, sigma=0.025, amplitude=-0.04)

        # ==============================================================
        # QRS COMPLEX — ventricular depolarisation
        # ==============================================================
        t_qrs = act_times['his']

        # --- X component (left-right) ---
        # Septal depolarisation: brief rightward (negative X), then leftward
        x += _g(t, t_qrs - 0.008, sigma=0.004, amplitude=-0.08)   # septal q
        x += _g(t, t_qrs + 0.006, sigma=0.005, amplitude=0.90)    # main R
        x += _g(t, t_qrs + 0.022, sigma=0.005, amplitude=-0.10)   # small s

        # --- Y component (foot-head, ≈ Lead II direction) ---
        # Classic Lead-II-like QRS
        y += _g(t, t_qrs - 0.010, sigma=0.005, amplitude=-0.10)   # Q wave
        y += _g(t, t_qrs + 0.005, sigma=0.004, amplitude=1.20)    # R wave
        y += _g(t, t_qrs + 0.020, sigma=0.005, amplitude=-0.15)   # S wave

        # --- Z component (front-back) — KEY for V-lead transition ---
        # Septal depolarisation goes anterior (positive Z → V1 small r)
        # Free wall depolarisation goes posterior (negative Z → V1 deep S)
        z += _g(t, t_qrs - 0.005, sigma=0.004, amplitude=0.35)    # septal r (→ V1 r)
        z += _g(t, t_qrs + 0.008, sigma=0.006, amplitude=-0.85)   # free wall (→ V1 S)
        z += _g(t, t_qrs + 0.025, sigma=0.005, amplitude=0.08)    # terminal

        # ==============================================================
        # T WAVE — ventricular repolarisation
        # ==============================================================
        if qt_ms > 200.0:
            t_t_peak = t_qrs + (qt_ms / 1000.0) - 0.060
        else:
            t_t_start = act_times['purkinje'] + apds['purkinje']
            t_t_peak = t_t_start + 0.110

        rr_sec = conduction.rr_sec
        max_t_peak = rr_sec - 0.060
        t_t_peak = min(t_t_peak, max_t_peak)

        # Base T-wave amplitudes per component
        ty_amp = 0.25       # Y: upright T in inferior leads
        tx_amp = 0.15       # X: upright T in lateral leads
        tz_amp = -0.10      # Z: negative → V1-V3 T inversion/low amplitude

        t_tail_y = 0.10
        t_tail_x = 0.06
        t_tail_z = -0.04

        # --- Electrolyte modulation ---
        t_sigma = 0.045
        if potassium > 5.5:
            k_excess = potassium - 5.5
            # Hyperkalaemia: tall peaked T in all components
            ty_amp += 0.15 * min(k_excess, 2.0)
            tx_amp += 0.10 * min(k_excess, 2.0)
            tz_amp -= 0.08 * min(k_excess, 2.0)  # more negative Z → peaked V1-V3 T
            t_sigma = max(0.025, 0.045 - 0.008 * k_excess)
        elif potassium < 3.0:
            k_deficit = 3.0 - potassium
            ty_amp -= 0.20 * min(k_deficit, 1.0)
            tx_amp -= 0.12 * min(k_deficit, 1.0)
            tz_amp += 0.05 * min(k_deficit, 1.0)  # flatten Z T-wave

        # Apply T-wave
        x += _g(t, t_t_peak, sigma=t_sigma, amplitude=tx_amp)
        x += _g(t, t_t_peak + 0.080, sigma=0.040, amplitude=t_tail_x)

        y += _g(t, t_t_peak, sigma=t_sigma, amplitude=ty_amp)
        y += _g(t, t_t_peak + 0.080, sigma=0.040, amplitude=t_tail_y)

        z += _g(t, t_t_peak, sigma=t_sigma, amplitude=tz_amp)
        z += _g(t, t_t_peak + 0.080, sigma=0.040, amplitude=t_tail_z)

        # --- Hypokalaemia U wave (mainly in Y component) ---
        if potassium < 3.0:
            k_deficit = 3.0 - potassium
            u_amp = 0.08 * min(k_deficit, 1.0)
            u_time = t_t_peak + 0.180
            y += _g(t, u_time, sigma=0.050, amplitude=u_amp)
            x += _g(t, u_time, sigma=0.050, amplitude=u_amp * 0.4)

        # --- Ischemia ST-segment modification ---
        if ischemia_level > 0.05:
            st_start = t_qrs + 0.040
            st_end = t_t_peak - 0.040
            st_center = (st_start + st_end) / 2.0
            st_sigma = max(0.020, (st_end - st_start) / 3.0)
            st_depression = -0.30 * ischemia_level

            # ST depression primarily in Y and Z components
            # Y → affects inferior leads (II, III, aVF)
            y += _g(t, st_center, sigma=st_sigma, amplitude=st_depression)
            # Z → affects anterior/precordial leads (V1-V4)
            z += _g(t, st_center, sigma=st_sigma, amplitude=st_depression * 0.8)
            # X → affects lateral leads (I, aVL, V5-V6)
            x += _g(t, st_center, sigma=st_sigma, amplitude=st_depression * 0.5)

            # T-wave inversion in ischemia
            if ischemia_level > 0.3:
                inv = min(1.0, (ischemia_level - 0.3) / 0.5)
                y += _g(t, t_t_peak, sigma=t_sigma, amplitude=-2.0 * ty_amp * inv)
                z += _g(t, t_t_peak, sigma=t_sigma, amplitude=-2.0 * tz_amp * inv)
                x += _g(t, t_t_peak, sigma=t_sigma, amplitude=-2.0 * tx_amp * inv)

        # --- Normalize: scale Y so R-peak ≈ _MV_SCALE ---
        y, scale = EcgSynthesizerV2._normalize_vcg_primary(y)
        x *= scale
        z *= scale

        return _VcgComponents(x=x, y=y, z=z)

    # ------------------------------------------------------------------
    # VT VCG
    # ------------------------------------------------------------------

    @staticmethod
    def _build_vt_vcg(
        t: NDArray[np.float64],
        n: int,
        conduction: ConductionResult,
    ) -> _VcgComponents:
        """VT morphology: wide bizarre QRS in all 3 VCG components."""
        _g = EcgSynthesizerV2._gaussian
        x = np.zeros(n, dtype=np.float64)
        y = np.zeros(n, dtype=np.float64)
        z = np.zeros(n, dtype=np.float64)

        act_times = {k: v / 1000.0 for k, v in conduction.activation_times.items()}
        t_qrs = act_times['purkinje'] + 0.040

        # --- Y component (≈ Lead II) — wide positive QRS ---
        y += _g(t, t_qrs - 0.015, sigma=0.012, amplitude=-0.15)
        y += _g(t, t_qrs + 0.010, sigma=0.018, amplitude=1.00)
        y += _g(t, t_qrs + 0.045, sigma=0.015, amplitude=0.40)
        y += _g(t, t_qrs + 0.080, sigma=0.020, amplitude=-0.30)

        # --- X component — VT axis deviation (wide, bizarre) ---
        x += _g(t, t_qrs - 0.010, sigma=0.014, amplitude=-0.30)
        x += _g(t, t_qrs + 0.015, sigma=0.020, amplitude=0.60)
        x += _g(t, t_qrs + 0.055, sigma=0.018, amplitude=0.25)
        x += _g(t, t_qrs + 0.085, sigma=0.015, amplitude=-0.15)

        # --- Z component — dominant anterior forces in VT ---
        z += _g(t, t_qrs - 0.008, sigma=0.012, amplitude=0.40)
        z += _g(t, t_qrs + 0.012, sigma=0.022, amplitude=0.70)
        z += _g(t, t_qrs + 0.050, sigma=0.018, amplitude=-0.20)
        z += _g(t, t_qrs + 0.080, sigma=0.015, amplitude=-0.35)

        # --- Discordant T-waves (opposite QRS) ---
        t_t = t_qrs + 0.180
        y += _g(t, t_t, sigma=0.060, amplitude=-0.30)
        y += _g(t, t_t + 0.060, sigma=0.050, amplitude=-0.10)
        x += _g(t, t_t, sigma=0.055, amplitude=0.15)
        x += _g(t, t_t + 0.050, sigma=0.045, amplitude=0.05)
        z += _g(t, t_t, sigma=0.060, amplitude=-0.20)
        z += _g(t, t_t + 0.060, sigma=0.050, amplitude=0.10)

        y, scale = EcgSynthesizerV2._normalize_vcg_primary(y)
        x *= scale
        z *= scale

        return _VcgComponents(x=x, y=y, z=z)

    # ------------------------------------------------------------------
    # PVC VCG
    # ------------------------------------------------------------------

    @staticmethod
    def _build_pvc_vcg(
        t: NDArray[np.float64],
        n: int,
        conduction: ConductionResult,
    ) -> _VcgComponents:
        """PVC morphology: wide QRS, discordant T, optional P-wave."""
        _g = EcgSynthesizerV2._gaussian
        x = np.zeros(n, dtype=np.float64)
        y = np.zeros(n, dtype=np.float64)
        z = np.zeros(n, dtype=np.float64)

        act_times = {k: v / 1000.0 for k, v in conduction.activation_times.items()}

        # P-wave (if present)
        if conduction.p_wave_present:
            t_p = act_times['sa']
            x += _g(t, t_p, sigma=0.040, amplitude=0.08)
            y += _g(t, t_p, sigma=0.040, amplitude=0.12)
            z += _g(t, t_p, sigma=0.030, amplitude=0.06)
            z += _g(t, t_p + 0.060, sigma=0.025, amplitude=-0.04)

        t_qrs = act_times['purkinje'] + 0.020

        # --- Y: wide QRS ---
        y += _g(t, t_qrs - 0.010, sigma=0.010, amplitude=-0.12)
        y += _g(t, t_qrs + 0.010, sigma=0.015, amplitude=1.10)
        y += _g(t, t_qrs + 0.050, sigma=0.018, amplitude=-0.25)

        # --- X: PVC axis deviation ---
        x += _g(t, t_qrs - 0.008, sigma=0.012, amplitude=-0.20)
        x += _g(t, t_qrs + 0.012, sigma=0.016, amplitude=0.55)
        x += _g(t, t_qrs + 0.048, sigma=0.015, amplitude=-0.15)

        # --- Z: anterior-posterior wide QRS ---
        z += _g(t, t_qrs - 0.005, sigma=0.010, amplitude=0.35)
        z += _g(t, t_qrs + 0.010, sigma=0.018, amplitude=0.50)
        z += _g(t, t_qrs + 0.045, sigma=0.016, amplitude=-0.30)

        # Discordant T-wave
        t_t = t_qrs + 0.140
        y += _g(t, t_t, sigma=0.055, amplitude=-0.25)
        y += _g(t, t_t + 0.050, sigma=0.040, amplitude=-0.08)
        x += _g(t, t_t, sigma=0.050, amplitude=0.12)
        z += _g(t, t_t, sigma=0.055, amplitude=-0.15)
        z += _g(t, t_t + 0.050, sigma=0.040, amplitude=0.08)

        y, scale = EcgSynthesizerV2._normalize_vcg_primary(y)
        x *= scale
        z *= scale

        return _VcgComponents(x=x, y=y, z=z)

    # ------------------------------------------------------------------
    # VF VCG
    # ------------------------------------------------------------------

    @staticmethod
    def _build_vf_vcg(
        t: NDArray[np.float64],
        n: int,
    ) -> _VcgComponents:
        """VF: independent chaotic signals per component."""
        rng = np.random.default_rng()
        components = []
        for _ in range(3):
            vf = np.zeros(n, dtype=np.float64)
            for _ in range(8):
                freq = rng.uniform(2.0, 8.0)
                phase = rng.uniform(0, 2 * np.pi)
                amp = rng.uniform(0.1, 0.4)
                vf += amp * np.sin(2 * np.pi * freq * t + phase)
            vf += rng.normal(0, 0.05, n)
            envelope = 0.5 + 0.5 * np.sin(2 * np.pi * 0.5 * t + rng.uniform(0, np.pi))
            vf *= envelope
            peak = np.max(np.abs(vf))
            if peak > 1e-10:
                vf = vf / peak
            vf *= _MV_SCALE * 0.6
            components.append(vf)

        return _VcgComponents(x=components[0], y=components[1], z=components[2])

    # ------------------------------------------------------------------
    # VCG → 12-lead projection
    # ------------------------------------------------------------------

    @staticmethod
    def _project_vcg_to_leads(
        vcg: _VcgComponents,
        requested: list[str],
    ) -> dict[str, NDArray[np.float64]]:
        """Project VCG (X, Y, Z) to requested 12 standard leads.

        Lead III is computed as II - I to guarantee Einthoven exactly.
        Augmented leads derived from I/II/III (Goldberger definitions).
        """
        need = set(requested)
        result: dict[str, NDArray[np.float64]] = {}

        # Stack VCG as (3, N) matrix for vectorised projection
        vcg_mat = np.vstack([vcg.x, vcg.y, vcg.z])  # shape (3, N)

        # Project all Dower leads at once: (8, 3) @ (3, N) = (8, N)
        projected = _DOWER_INV @ vcg_mat  # (8, N)

        # Build lookup
        dower_leads: dict[str, NDArray[np.float64]] = {}
        for i, name in enumerate(_DOWER_LEAD_NAMES):
            dower_leads[name] = projected[i]

        lead_i = dower_leads['I']
        lead_ii = dower_leads['II']
        # Einthoven guarantee: III = II - I
        lead_iii = lead_ii - lead_i

        if 'I' in need:
            result['I'] = lead_i
        if 'II' in need:
            result['II'] = lead_ii.copy()
        if 'III' in need:
            result['III'] = lead_iii

        # Augmented leads (Goldberger definitions)
        if 'aVR' in need:
            result['aVR'] = -(lead_i + lead_ii) / 2.0
        if 'aVL' in need:
            result['aVL'] = (lead_i - lead_iii) / 2.0
        if 'aVF' in need:
            result['aVF'] = (lead_ii + lead_iii) / 2.0

        # Precordial leads from Dower projection
        for v_lead in ('V1', 'V2', 'V3', 'V4', 'V5', 'V6'):
            if v_lead in need:
                result[v_lead] = dower_leads[v_lead]

        return result

    # ------------------------------------------------------------------
    # T-wave overflow (P-on-T fusion) — VCG version
    # ------------------------------------------------------------------

    def _compute_t_wave_overflow_vcg(
        self,
        conduction: ConductionResult,
        modifiers: Modifiers | None = None,
    ) -> None:
        """Compute T-wave tail overflow for all 3 VCG components.

        At high HR, the T-wave extends beyond beat boundary.
        Store overflow per component for next beat's P-on-T fusion.
        """
        if conduction.beat_kind not in ('sinus', 'svt', 'af'):
            self._t_wave_carryover_x = None
            self._t_wave_carryover_y = None
            self._t_wave_carryover_z = None
            return

        sr = _CELL_RATE
        rr_sec = conduction.rr_sec
        act_times = {k: v / 1000.0 for k, v in conduction.activation_times.items()}
        t_qrs = act_times.get('his', 0.110)

        qt_ms = 0.0
        if modifiers is not None:
            qt_ms = getattr(modifiers, 'qt_adapted_ms', 0.0)

        if qt_ms > 200.0:
            t_t_peak = t_qrs + (qt_ms / 1000.0) - 0.060
        else:
            apds = {k: ap.apd_ms / 1000.0 for k, ap in conduction.node_aps.items()}
            t_t_start = act_times.get('purkinje', 0.0) + apds.get('purkinje', 0.3)
            t_t_peak = t_t_start + 0.110

        t_tail_center = t_t_peak + 0.080
        if t_tail_center <= rr_sec + 0.020:
            self._t_wave_carryover_x = None
            self._t_wave_carryover_y = None
            self._t_wave_carryover_z = None
            return

        overflow_dur = min(0.150, t_tail_center - rr_sec + 0.100)
        n_overflow = int(overflow_dur * sr)
        if n_overflow < 5:
            self._t_wave_carryover_x = None
            self._t_wave_carryover_y = None
            self._t_wave_carryover_z = None
            return

        t_overflow = np.arange(n_overflow, dtype=np.float64) / sr
        t_peak_rel = t_t_peak - rr_sec
        t_tail_rel = t_tail_center - rr_sec
        _g = self._gaussian

        # Y component (primary, like old Lead II overflow)
        oy = np.zeros(n_overflow, dtype=np.float64)
        oy += _g(t_overflow, t_peak_rel, sigma=0.045, amplitude=0.25)
        oy += _g(t_overflow, t_tail_rel, sigma=0.040, amplitude=0.10)
        oy *= _MV_SCALE * 0.4

        # X component (scaled)
        ox = np.zeros(n_overflow, dtype=np.float64)
        ox += _g(t_overflow, t_peak_rel, sigma=0.045, amplitude=0.15)
        ox += _g(t_overflow, t_tail_rel, sigma=0.040, amplitude=0.06)
        ox *= _MV_SCALE * 0.4

        # Z component (negative, T in Z is typically negative for sinus)
        oz = np.zeros(n_overflow, dtype=np.float64)
        oz += _g(t_overflow, t_peak_rel, sigma=0.045, amplitude=-0.10)
        oz += _g(t_overflow, t_tail_rel, sigma=0.040, amplitude=-0.04)
        oz *= _MV_SCALE * 0.4

        self._t_wave_carryover_x = ox
        self._t_wave_carryover_y = oy
        self._t_wave_carryover_z = oz

    # ------------------------------------------------------------------
    # Normalisation
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_vcg_primary(
        y_comp: NDArray[np.float64],
    ) -> tuple[NDArray[np.float64], float]:
        """Normalize Y component (primary) and return scale factor.

        Returns (normalized_y, scale) so X and Z can be scaled consistently.
        """
        baseline = np.percentile(y_comp, 5)
        y_comp = y_comp - baseline

        peak = np.max(np.abs(y_comp))
        if peak > 1e-10:
            scale = _MV_SCALE / peak
        else:
            scale = 1.0

        return y_comp * scale, scale

    # ------------------------------------------------------------------
    # Utility helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _gaussian(
        t: NDArray[np.float64],
        center: float,
        sigma: float,
        amplitude: float,
    ) -> NDArray[np.float64]:
        """Gaussian basis function for ECG morphology."""
        return amplitude * np.exp(-((t - center) ** 2) / (2 * sigma ** 2))

    def _downsample(
        self,
        signal: NDArray[np.float64],
        target_len: int,
    ) -> NDArray[np.float64]:
        """Downsample from _CELL_RATE to self.sample_rate."""
        if len(signal) <= 1 or target_len <= 1:
            return np.zeros(max(target_len, 1), dtype=np.float64)

        from math import gcd

        up = target_len
        down = len(signal)
        g = gcd(up, down)
        up //= g
        down //= g

        resampled = resample_poly(signal, up, down)
        if len(resampled) >= target_len:
            return resampled[:target_len].astype(np.float64)
        else:
            padded = np.zeros(target_len, dtype=np.float64)
            padded[: len(resampled)] = resampled
            return padded

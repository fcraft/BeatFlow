"""ECG synthesizer: convert conduction network output to 12-lead surface ECG.

Takes the 4-node action potential traces from ConductionNetworkV2 and projects
them onto body-surface leads using Dower-like transformation coefficients.

Pipeline:
  1. Build Lead II (primary) as weighted sum of node AP vm_traces
  2. Derive remaining leads ensuring Einthoven: II = I + III
  3. Downsample from 5000 Hz (cell model) to target sample_rate (default 500 Hz)
  4. Add configurable electrode noise from modifiers.electrode_noise
"""
from __future__ import annotations

import numpy as np
from numpy.typing import NDArray
from scipy.signal import resample_poly

from app.engine.core.types import ConductionResult, EcgFrame, Modifiers

# Internal cell-model sample rate
_CELL_RATE = 5000

# Node contribution weights for building Lead II
# SA node vm_trace → P wave, AV node overlaps with PR segment,
# His bundle → initial QRS, Purkinje → main QRS + T wave (repolarisation)
_NODE_WEIGHTS: dict[str, float] = {
    'sa': 0.12,        # P wave contribution
    'av': 0.03,        # minimal direct surface contribution
    'his': 0.25,       # early ventricular depolarisation
    'purkinje': 0.60,  # dominant ventricular complex
}

# Amplitude scaling so Lead II R-peak lands near 1.0 mV
_MV_SCALE = 1.8

# Lead I fraction of Lead II (used to guarantee Einthoven)
_LEAD_I_FRACTION = 0.6

# Precordial (V-lead) coefficients relative to Lead II
_V_LEAD_COEFFICIENTS: dict[str, float] = {
    'V1': -0.50,
    'V2':  0.20,
    'V3':  0.60,
    'V4':  0.90,
    'V5':  0.80,
    'V6':  0.50,
}


class EcgSynthesizerV2:
    """Synthesize 12-lead ECG from conduction network output."""

    def __init__(self, sample_rate: int = 500) -> None:
        self.sample_rate = sample_rate
        # T-wave carryover buffer: when T-wave extends beyond beat boundary
        # at high HR, the overflow is stored here and added to the next beat's
        # beginning, creating P-on-T fusion instead of T-wave disappearance.
        self._t_wave_carryover: NDArray[np.float64] | None = None

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
        # 1. Build Lead II at cell-model rate (5000 Hz)
        lead_ii_raw = self._build_lead_ii(conduction, modifiers)

        # 1b. Apply T-wave carryover from previous beat (P-on-T fusion)
        if self._t_wave_carryover is not None and len(self._t_wave_carryover) > 0:
            overlap = min(len(self._t_wave_carryover), len(lead_ii_raw))
            lead_ii_raw[:overlap] += self._t_wave_carryover[:overlap]
            self._t_wave_carryover = None

        # 1c. Compute and save T-wave overflow for next beat
        self._t_wave_carryover = self._compute_t_wave_overflow(
            conduction, modifiers,
        )

        # 2. Derive all requested leads at cell-model rate
        raw_leads = self._derive_leads(lead_ii_raw, leads)

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
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_lead_ii(
        conduction: ConductionResult,
        modifiers: Modifiers | None = None,
    ) -> NDArray[np.float64]:
        """Build Lead II using Gaussian-based morphology from V2 conduction model.

        Supports beat_kind-aware morphology:
        - 'sinus' / 'svt' / 'af': Normal P-QRS-T (SVT/AF may lack P-wave)
        - 'vt': Wide bizarre QRS from ventricular ectopic, no P-wave, inverted T
        - 'pvc': Wide QRS, may have preceding P-wave, inverted T
        - 'vf': Chaotic (handled separately, produces random oscillation)
        - 'asystole': Flat line (handled separately)
        """
        sr = _CELL_RATE  # 5000 Hz
        n = int(conduction.rr_sec * sr)  # Total samples in RR interval
        t = np.arange(n) / sr  # Time array in seconds

        beat_kind = conduction.beat_kind

        # Dispatch to specialised morphology builders
        if beat_kind == 'vt':
            return EcgSynthesizerV2._build_vt_morphology(t, n, conduction)
        elif beat_kind == 'pvc':
            return EcgSynthesizerV2._build_pvc_morphology(t, n, conduction)
        elif beat_kind == 'vf':
            return EcgSynthesizerV2._build_vf_morphology(t, n)
        elif beat_kind == 'asystole':
            return np.zeros(n, dtype=np.float64)

        # --- Normal sinus / SVT / AF morphology ---
        return EcgSynthesizerV2._build_sinus_morphology(t, n, conduction, modifiers)

    @staticmethod
    def _build_sinus_morphology(
        t: NDArray[np.float64],
        n: int,
        conduction: ConductionResult,
        modifiers: Modifiers | None = None,
    ) -> NDArray[np.float64]:
        """Normal sinus P-QRS-T morphology (also used for SVT/AF).

        Enhanced with:
        - QT-dynamic T-wave positioning (from qt_adapted_ms)
        - Ischemia ST-segment depression/elevation
        - Electrolyte-sensitive T-wave morphology
        """
        lead_ii = np.zeros(n, dtype=np.float64)

        # Extract conduction timing (in seconds)
        act_times = {k: v / 1000.0 for k, v in conduction.activation_times.items()}

        # Extract APD (in seconds)
        apds = {
            k: ap.apd_ms / 1000.0
            for k, ap in conduction.node_aps.items()
        }

        # --- P WAVE ---
        if conduction.p_wave_present:
            t_p = act_times['sa']
            p_main = EcgSynthesizerV2._gaussian(t, t_p, sigma=0.040, amplitude=0.12)
            p_tail = EcgSynthesizerV2._gaussian(t, t_p + 0.060, sigma=0.030, amplitude=0.03)
            lead_ii += p_main + p_tail

        # --- QRS COMPLEX ---
        t_qrs = act_times['his']

        # Q wave
        lead_ii += EcgSynthesizerV2._gaussian(t, t_qrs - 0.010, sigma=0.005, amplitude=-0.10)
        # R wave
        lead_ii += EcgSynthesizerV2._gaussian(t, t_qrs + 0.005, sigma=0.004, amplitude=1.20)
        # S wave
        lead_ii += EcgSynthesizerV2._gaussian(t, t_qrs + 0.020, sigma=0.005, amplitude=-0.15)

        # --- QT-dynamic T WAVE positioning ---
        # Use qt_adapted_ms from Modifiers if available; otherwise Purkinje APD
        qt_ms = 0.0
        ischemia_level = 0.0
        potassium = 4.0
        if modifiers is not None:
            qt_ms = getattr(modifiers, 'qt_adapted_ms', 0.0)
            ischemia_level = getattr(modifiers, 'ischemia_level', 0.0)
            potassium = getattr(modifiers, 'potassium_level', 4.0)

        if qt_ms > 200.0:
            # T-wave peak = QRS onset + QT interval - ~60ms (T peak before QT end)
            t_t_peak = t_qrs + (qt_ms / 1000.0) - 0.060
        else:
            # Fallback to Purkinje APD based positioning
            t_t_start = act_times['purkinje'] + apds['purkinje']
            t_t_peak = t_t_start + 0.110

        # Clamp T-wave peak so it stays within the beat boundary.
        # At high HR the QT pushes T-wave near/beyond rr_sec; without
        # clamping the Gaussian naturally decays to zero and T disappears.
        # The overflow portion is handled separately via _compute_t_wave_overflow.
        rr_sec = conduction.rr_sec
        max_t_peak = rr_sec - 0.060  # leave 60ms margin for tail
        t_t_peak = min(t_t_peak, max_t_peak)

        # T-wave amplitude modulation by ischemia and electrolytes
        t_amplitude = 0.25
        t_tail_amplitude = 0.10

        # Hyperkalaemia → tall peaked T waves
        if potassium > 5.5:
            k_excess = potassium - 5.5
            t_amplitude += 0.15 * min(k_excess, 2.0)
            # Also narrows the T wave
            t_sigma = max(0.025, 0.045 - 0.008 * k_excess)
        elif potassium < 3.0:
            # Hypokalaemia → flat/inverted T, prominent U wave
            k_deficit = 3.0 - potassium
            t_amplitude -= 0.20 * min(k_deficit, 1.0)
            t_sigma = 0.045
        else:
            t_sigma = 0.045

        lead_ii += EcgSynthesizerV2._gaussian(t, t_t_peak, sigma=t_sigma, amplitude=t_amplitude)
        lead_ii += EcgSynthesizerV2._gaussian(t, t_t_peak + 0.080, sigma=0.040, amplitude=t_tail_amplitude)

        # --- Hypokalaemia U wave ---
        if potassium < 3.0:
            k_deficit = 3.0 - potassium
            u_amplitude = 0.08 * min(k_deficit, 1.0)
            u_time = t_t_peak + 0.180
            lead_ii += EcgSynthesizerV2._gaussian(t, u_time, sigma=0.050, amplitude=u_amplitude)

        # --- Ischemia ST-segment modification ---
        if ischemia_level > 0.05:
            # ST depression: horizontal/downsloping ST below baseline
            st_start = t_qrs + 0.040   # J-point (end of QRS)
            st_end = t_t_peak - 0.040  # Before T-wave upstroke

            # ST depression magnitude: up to -0.3 mV at severe ischemia
            st_depression = -0.30 * ischemia_level

            # Broad Gaussian for ST segment depression
            st_center = (st_start + st_end) / 2.0
            st_sigma = max(0.020, (st_end - st_start) / 3.0)
            lead_ii += EcgSynthesizerV2._gaussian(
                t, st_center, sigma=st_sigma, amplitude=st_depression
            )

            # T-wave inversion in ischemia (partial to full)
            if ischemia_level > 0.3:
                inversion_factor = min(1.0, (ischemia_level - 0.3) / 0.5)
                # Reduce T amplitude, potentially invert
                t_ischemia_mod = -2.0 * t_amplitude * inversion_factor
                lead_ii += EcgSynthesizerV2._gaussian(
                    t, t_t_peak, sigma=t_sigma, amplitude=t_ischemia_mod
                )

        return EcgSynthesizerV2._normalize_lead(lead_ii)

    @staticmethod
    def _build_vt_morphology(
        t: NDArray[np.float64],
        n: int,
        conduction: ConductionResult,
    ) -> NDArray[np.float64]:
        """VT morphology: wide bizarre QRS, no P-wave, inverted T-wave.

        VT originates from a ventricular ectopic focus (purkinje node at t=0).
        The depolarization spreads slowly through the myocardium (not via the
        fast His-Purkinje system), producing a wide, slurred QRS complex.
        """
        lead_ii = np.zeros(n, dtype=np.float64)

        # VT QRS is anchored to purkinje activation (typically 0ms = beat start)
        act_times = {k: v / 1000.0 for k, v in conduction.activation_times.items()}
        apds = {
            k: ap.apd_ms / 1000.0
            for k, ap in conduction.node_aps.items()
        }

        # QRS center: use purkinje activation + small offset so QRS isn't
        # right at the edge of the buffer
        t_qrs = act_times['purkinje'] + 0.040  # 40ms into the beat

        # Wide bizarre QRS (~120-200ms): slow myocardial spread
        # Dominant R-wave (positive or negative depending on VT axis)
        # Using RBBB-like pattern: wide positive deflection with notch
        lead_ii += EcgSynthesizerV2._gaussian(t, t_qrs - 0.015, sigma=0.012, amplitude=-0.15)
        # Main wide R-wave
        lead_ii += EcgSynthesizerV2._gaussian(t, t_qrs + 0.010, sigma=0.018, amplitude=1.00)
        # Secondary R' notch (characteristic VT notching)
        lead_ii += EcgSynthesizerV2._gaussian(t, t_qrs + 0.045, sigma=0.015, amplitude=0.40)
        # Broad S-wave
        lead_ii += EcgSynthesizerV2._gaussian(t, t_qrs + 0.080, sigma=0.020, amplitude=-0.30)

        # --- Inverted T-wave (discordant with QRS direction) ---
        # VT T-wave is opposite polarity to QRS, broad and inverted
        t_t = t_qrs + 0.180  # T-wave starts after wide QRS
        lead_ii += EcgSynthesizerV2._gaussian(t, t_t, sigma=0.060, amplitude=-0.30)
        lead_ii += EcgSynthesizerV2._gaussian(t, t_t + 0.060, sigma=0.050, amplitude=-0.10)

        # No P-wave (ventricle drives rhythm, atria dissociated)

        return EcgSynthesizerV2._normalize_lead(lead_ii)

    @staticmethod
    def _build_pvc_morphology(
        t: NDArray[np.float64],
        n: int,
        conduction: ConductionResult,
    ) -> NDArray[np.float64]:
        """PVC morphology: wide QRS, discordant T-wave, may have preceding P-wave."""
        lead_ii = np.zeros(n, dtype=np.float64)

        act_times = {k: v / 1000.0 for k, v in conduction.activation_times.items()}
        apds = {
            k: ap.apd_ms / 1000.0
            for k, ap in conduction.node_aps.items()
        }

        # P-wave may be present (sinus rhythm continues, PVC interrupts)
        if conduction.p_wave_present:
            t_p = act_times['sa']
            lead_ii += EcgSynthesizerV2._gaussian(t, t_p, sigma=0.040, amplitude=0.12)

        # PVC QRS: anchored to purkinje (ectopic) activation
        t_qrs = act_times['purkinje'] + 0.020

        # Wide QRS (~120-160ms)
        lead_ii += EcgSynthesizerV2._gaussian(t, t_qrs - 0.010, sigma=0.010, amplitude=-0.12)
        # Tall wide R
        lead_ii += EcgSynthesizerV2._gaussian(t, t_qrs + 0.010, sigma=0.015, amplitude=1.10)
        # Broad S
        lead_ii += EcgSynthesizerV2._gaussian(t, t_qrs + 0.050, sigma=0.018, amplitude=-0.25)

        # Inverted T-wave (discordant)
        t_t = t_qrs + 0.140
        lead_ii += EcgSynthesizerV2._gaussian(t, t_t, sigma=0.055, amplitude=-0.25)
        lead_ii += EcgSynthesizerV2._gaussian(t, t_t + 0.050, sigma=0.040, amplitude=-0.08)

        return EcgSynthesizerV2._normalize_lead(lead_ii)

    @staticmethod
    def _build_vf_morphology(
        t: NDArray[np.float64],
        n: int,
    ) -> NDArray[np.float64]:
        """VF morphology: chaotic irregular oscillation, no identifiable waves."""
        rng = np.random.default_rng()
        # Chaotic oscillation: sum of random-frequency sinusoids
        vf = np.zeros(n, dtype=np.float64)
        for _ in range(8):
            freq = rng.uniform(2.0, 8.0)  # 2-8 Hz
            phase = rng.uniform(0, 2 * np.pi)
            amp = rng.uniform(0.1, 0.4)
            vf += amp * np.sin(2 * np.pi * freq * t + phase)
        # Add noise
        vf += rng.normal(0, 0.05, n)
        # Amplitude modulation (waxing/waning)
        envelope = 0.5 + 0.5 * np.sin(2 * np.pi * 0.5 * t)
        vf *= envelope
        # Scale to realistic amplitude
        peak = np.max(np.abs(vf))
        if peak > 1e-10:
            vf = vf / peak
        vf *= _MV_SCALE * 0.6  # VF is lower amplitude than normal QRS
        return vf

    @staticmethod
    def _normalize_lead(lead_ii: NDArray[np.float64]) -> NDArray[np.float64]:
        """Normalize lead signal: remove DC offset and scale to realistic amplitude."""
        # Subtract DC offset so signal oscillates around zero
        baseline = np.percentile(lead_ii, 5)
        lead_ii = lead_ii - baseline

        # Scale to realistic amplitude
        peak = np.max(np.abs(lead_ii))
        if peak > 1e-10:
            lead_ii = lead_ii / peak  # Normalize to [-1, 1]
        lead_ii *= _MV_SCALE  # Scale so R-peak ≈ 1.0-1.8 mV

        return lead_ii

    def _compute_t_wave_overflow(
        self,
        conduction: ConductionResult,
        modifiers: Modifiers | None = None,
    ) -> NDArray[np.float64] | None:
        """Compute T-wave tail that extends beyond the current beat boundary.

        At high HR, the T-wave peak is clamped within the beat, but the
        Gaussian tail would naturally extend into the next beat.  We
        compute this overflow and return it so synthesize() can add it
        to the beginning of the next beat (P-on-T fusion).
        """
        if conduction.beat_kind not in ('sinus', 'svt', 'af'):
            return None

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

        # Only generate overflow if T-wave tail extends beyond beat
        t_tail_center = t_t_peak + 0.080
        if t_tail_center <= rr_sec + 0.020:
            return None

        # Generate the overflow portion (up to 150ms into the next beat)
        overflow_dur = min(0.150, t_tail_center - rr_sec + 0.100)
        n_overflow = int(overflow_dur * sr)
        if n_overflow < 5:
            return None

        # Time array relative to beat boundary (t=0 is next beat start)
        t_overflow = np.arange(n_overflow, dtype=np.float64) / sr

        # The T-wave Gaussian extends: center is at (t_t_peak - rr_sec) relative to next beat start
        t_peak_rel = t_t_peak - rr_sec
        t_tail_rel = t_tail_center - rr_sec

        overflow = np.zeros(n_overflow, dtype=np.float64)
        overflow += self._gaussian(t_overflow, t_peak_rel, sigma=0.045, amplitude=0.25)
        overflow += self._gaussian(t_overflow, t_tail_rel, sigma=0.040, amplitude=0.10)

        # Scale to match the normalized signal level
        overflow *= _MV_SCALE * 0.4  # Attenuate slightly — P-on-T is partial
        return overflow

        return lead_ii

    @staticmethod
    def _gaussian(
        t: NDArray[np.float64],
        center: float,
        sigma: float,
        amplitude: float,
    ) -> NDArray[np.float64]:
        """Gaussian basis function for ECG morphology.

        Args:
            t: Time array (seconds)
            center: Center of Gaussian (seconds)
            sigma: Standard deviation (seconds)
            amplitude: Peak amplitude
        """
        return amplitude * np.exp(-((t - center) ** 2) / (2 * sigma ** 2))

    @staticmethod
    def _derive_leads(
        lead_ii: NDArray[np.float64],
        requested: list[str],
    ) -> dict[str, NDArray[np.float64]]:
        """Derive all requested leads from Lead II.

        Einthoven compliance: Lead I = alpha * Lead II,
        Lead III = Lead II - Lead I  => I + III = II exactly.
        Augmented leads from Einthoven definition.
        V-leads scaled from Lead II with morphology coefficients.
        """
        result: dict[str, NDArray[np.float64]] = {}
        need = set(requested)

        # Always compute Lead I and Lead III if any limb lead is needed
        lead_i = _LEAD_I_FRACTION * lead_ii
        lead_iii = lead_ii - lead_i  # guarantees II = I + III

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

        # Precordial leads
        for v_lead, coeff in _V_LEAD_COEFFICIENTS.items():
            if v_lead in need:
                result[v_lead] = coeff * lead_ii

        return result

    def _downsample(
        self,
        signal: NDArray[np.float64],
        target_len: int,
    ) -> NDArray[np.float64]:
        """Downsample from _CELL_RATE to self.sample_rate."""
        if len(signal) <= 1 or target_len <= 1:
            return np.zeros(max(target_len, 1), dtype=np.float64)

        # Use rational resampling: target_len / len(signal)
        # resample_poly(signal, up, down) where up/down = target_len/len(signal)
        from math import gcd

        up = target_len
        down = len(signal)
        g = gcd(up, down)
        up //= g
        down //= g

        resampled = resample_poly(signal, up, down)
        # Trim or pad to exact target_len
        if len(resampled) >= target_len:
            return resampled[:target_len].astype(np.float64)
        else:
            padded = np.zeros(target_len, dtype=np.float64)
            padded[: len(resampled)] = resampled
            return padded

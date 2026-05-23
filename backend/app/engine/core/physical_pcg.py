"""Physical-model PCG synthesizer: impulse-resonance with multi-band compression.

Replaces the pure damped-sinusoid modal decomposition in ParametricPcgSynthesizer
with a physically-motivated pipeline:

  1. Impulse Excitation — short impact pulse simulating valve closure pressure gradient
  2. Cascade Resonator Banks — S1/S2 each use parallel IIR resonators modelling
     ventricular/vascular/thoracic vibration modes
  3. Nonlinear Saturation — soft-clipping for tissue acoustic nonlinearity
  4. 4-Band WDRC — preserves S1/S2 dynamics while preventing murmur masking
  5. Chest Transfer Functions — per-position FIR filters for 4 auscultation sites
  6. Respiratory Modulation — S2 splitting, amplitude variation, S3/S4 modulation
"""
from __future__ import annotations

import logging

import numpy as np
from numpy.typing import NDArray

from app.engine.core.types import ConductionResult, Modifiers, PcgFrame

logger = logging.getLogger(__name__)

PCG_SR = 4000

# S1 resonator bank: 5 modes covering mitral + tricuspid closure
# (freq Hz, Q, relative gain)
S1_RESONATORS: list[tuple[float, float, float]] = [
    (45.0, 6.0, 0.30),    # M1 — mitral component
    (70.0, 8.0, 0.40),    # M1
    (100.0, 10.0, 0.30),  # M1  (Q reduced from 15: less ringing in systole)
    (35.0, 5.0, 0.15),    # T1 — tricuspid component
    (55.0, 7.0, 0.15),    # T1
]

# S2 resonator bank: 4 modes covering aortic + pulmonic closure
S2_RESONATORS: list[tuple[float, float, float]] = [
    (80.0, 7.0, 0.30),    # A2 — aortic component
    (120.0, 10.0, 0.35),  # A2 (Q reduced from 14)
    (160.0, 8.0, 0.20),   # A2 (Q reduced from 12)
    (90.0, 7.0, 0.15),    # P2 — pulmonic component
]

# S3 resonator bank: low-frequency gallop (rapid filling)
S3_RESONATORS: list[tuple[float, float, float]] = [
    (25.0, 4.0, 0.40),
    (40.0, 6.0, 0.30),
    (55.0, 5.0, 0.20),
]

# S4 resonator bank: atrial gallop
S4_RESONATORS: list[tuple[float, float, float]] = [
    (20.0, 3.0, 0.35),
    (35.0, 5.0, 0.30),
]

_BACKGROUND_NOISE_AMP = 0.0005
_RESPIRATORY_NOISE_AMP = 0.0004
_MUSCLE_NOISE_AMP = 0.00025

# Post-resonator makeup gain: the IIR biquad resonators have very small
# feedforward coefficients (b0 ~0.003 for a 70 Hz mode at Q=8 @ 4 kHz),
# producing peak amplitudes ~1/25th of the equivalent parametric modal burst.
# This gain compensates so both engines produce comparable loudness.
_RESONATOR_OUTPUT_GAIN = 12.0

_IMPULSE_DURATION_MS = 8.0
_IMPULSE_RISE_MS = 1.5


class PhysicalPcgSynthesizer:
    """Physical-model PCG synthesizer using impulse-resonance pipeline.

    Produces heart sounds by:
    1. Generating short impulse bursts at S1/S2 onset times
    2. Passing through resonator banks tuned to cardiac vibration modes
    3. Applying nonlinear saturation for tissue response
    4. Multi-band dynamic compression
    5. Position-specific chest transfer functions
    """

    SAMPLE_RATE: int = PCG_SR

    def __init__(self) -> None:
        self._prev_tail: NDArray[np.float64] | None = None
        self._rng = np.random.default_rng()
        self._frac_acc: float = 0.0

        # Lazy-initialized
        self._resonator_s1: object | None = None
        self._resonator_s2: object | None = None
        self._resonator_s3: object | None = None
        self._resonator_s4: object | None = None
        self._compressor: object | None = None
        self._chest_filter: object | None = None

    def _ensure_components(self) -> None:
        """Lazy-initialize resonator banks, compressor, and chest filters."""
        from app.engine.core.acoustic_resonator import ResonatorBank
        from app.engine.core.band_compressor import design_pcg_compressor
        from app.engine.core.chest_transfer import ChestTransferFilter

        sr = self.SAMPLE_RATE

        if self._resonator_s1 is None and S1_RESONATORS:
            freqs, Qs, gains = zip(*S1_RESONATORS)
            self._resonator_s1 = ResonatorBank(
                frequencies=list(freqs), Q_values=list(Qs), gains=list(gains),
                sample_rate=sr, clip_threshold=1.0,
            )

        if self._resonator_s2 is None and S2_RESONATORS:
            freqs, Qs, gains = zip(*S2_RESONATORS)
            self._resonator_s2 = ResonatorBank(
                frequencies=list(freqs), Q_values=list(Qs), gains=list(gains),
                sample_rate=sr, clip_threshold=1.0,
            )

        if self._resonator_s3 is None and S3_RESONATORS:
            freqs, Qs, gains = zip(*S3_RESONATORS)
            self._resonator_s3 = ResonatorBank(
                frequencies=list(freqs), Q_values=list(Qs), gains=list(gains),
                sample_rate=sr, clip_threshold=0.6,
            )

        if self._resonator_s4 is None and S4_RESONATORS:
            freqs, Qs, gains = zip(*S4_RESONATORS)
            self._resonator_s4 = ResonatorBank(
                frequencies=list(freqs), Q_values=list(Qs), gains=list(gains),
                sample_rate=sr, clip_threshold=0.5,
            )

        if self._compressor is None:
            self._compressor = design_pcg_compressor(sample_rate=sr)

        if self._chest_filter is None:
            self._chest_filter = ChestTransferFilter(sample_rate=sr)

    def _generate_excitation(
        self, n_samples: int, onset_sample: int, amplitude: float
    ) -> NDArray[np.float64]:
        """Generate short impulse excitation at onset_sample.

        Models the pressure gradient pulse from valve closure as a
        fast-rise, exponential-decay impulse (approximating dP/dt transient).
        """
        sr = self.SAMPLE_RATE
        impulse_dur = int(_IMPULSE_DURATION_MS / 1000.0 * sr)
        start = max(0, onset_sample)
        end = min(n_samples, start + impulse_dur)

        exc = np.zeros(n_samples, dtype=np.float64)
        if end <= start:
            return exc

        actual_dur = end - start
        rise_samples = int(_IMPULSE_RISE_MS / 1000.0 * sr)
        rise_samples = max(1, min(rise_samples, actual_dur))

        for i in range(actual_dur):
            if i < rise_samples:
                exc[start + i] = amplitude * (i / rise_samples)
            else:
                t_ms = i / sr * 1000.0
                exc[start + i] = amplitude * np.exp(-t_ms / 3.0)

        return exc

    def synthesize(
        self,
        conduction: ConductionResult,
        modifiers: Modifiers,
    ) -> PcgFrame:
        """Synthesize one beat of PCG using physical model."""
        self._ensure_components()

        sr = self.SAMPLE_RATE
        rr_sec = conduction.rr_sec
        exact = rr_sec * sr + self._frac_acc
        n_samples = round(exact)
        self._frac_acc = exact - n_samples
        hr = 60.0 / rr_sec if rr_sec > 0 else 60.0

        beat_kind = conduction.beat_kind

        # Asystole / VF: silent / chaotic
        if beat_kind == 'asystole':
            noise = self._rng.normal(0, _BACKGROUND_NOISE_AMP, n_samples)
            return PcgFrame(
                samples=noise.astype(np.float64), sample_rate=sr,
                s1_onset_sample=0, s2_onset_sample=0,
                murmur_present=False, channels={},
            )
        if beat_kind == 'vf':
            noise = self._rng.normal(0, 0.02, n_samples).astype(np.float64)
            return PcgFrame(
                samples=noise, sample_rate=sr,
                s1_onset_sample=0, s2_onset_sample=0,
                murmur_present=False, channels={},
            )

        # --- S1/S2 timing ---
        act_times = conduction.activation_times
        his_ms = act_times.get('his', 110.0)
        purkinje_ms = act_times.get('purkinje', 125.0)

        if beat_kind in ('vt', 'pvc'):
            qrs_onset_ms = purkinje_ms
        else:
            qrs_onset_ms = his_ms
        s1_onset_ms = qrs_onset_ms + 30.0  # electromechanical delay

        lvet_ms = max(200.0, -1.7 * hr + 413.0)  # Weissler formula
        s2_onset_ms = s1_onset_ms + lvet_ms

        s1_onset_sample = int(s1_onset_ms / 1000.0 * sr)
        s2_onset_sample = int(s2_onset_ms / 1000.0 * sr)

        s1_onset_sample = max(0, min(s1_onset_sample, n_samples - 1))
        s2_onset_sample = max(s1_onset_sample + int(0.1 * sr), min(s2_onset_sample, n_samples - 1))

        # --- Amplitude scaling ---
        contractility = modifiers.contractility_modifier
        damage = modifiers.damage_level
        attenuation = modifiers.chest_wall_attenuation

        s1_amp = 0.8 * contractility * (1.0 - 0.3 * damage) * attenuation
        s1_amp = max(0.1, min(1.2, s1_amp))
        # S2 base ~0.22× S1 base (real recordings: S1/S2 ≈ 4-5× at apex)
        s2_amp = 0.22 * (1.0 - 0.2 * damage) * attenuation
        # HR-dependent S2 attenuation: high HR → short diastole →
        # reduced ventricular filling → quieter semilunar valve closure.
        ref_diastole_ms = 689.0  # 1000ms RR - 311ms LVET at 60 BPM
        actual_diastole_ms = max(0.0, rr_sec * 1000.0 - lvet_ms)
        hr_s2_factor = min(1.0, (actual_diastole_ms / ref_diastole_ms) ** 0.3)
        s2_amp *= hr_s2_factor
        s2_amp = max(0.03, min(0.9, s2_amp))

        # --- Respiratory amplitude modulation ---
        resp_phase = modifiers.respiratory_phase
        resp_amp_factor = 1.0 - 0.08 * (0.5 + 0.5 * np.sin(resp_phase))
        s1_amp *= resp_amp_factor
        s2_amp *= resp_amp_factor

        # --- Excitation + Resonance pipeline ---
        pcm = self._rng.normal(0, _BACKGROUND_NOISE_AMP * 0.5, n_samples).astype(np.float64)

        # S1: excitation → resonator bank
        s1_exc = self._generate_excitation(n_samples, s1_onset_sample, s1_amp)
        pcm += self._resonator_s1.process(s1_exc) * _RESONATOR_OUTPUT_GAIN

        # S2 primary: excitation → resonator bank
        s2_exc = self._generate_excitation(n_samples, s2_onset_sample, s2_amp)
        pcm += self._resonator_s2.process(s2_exc) * _RESONATOR_OUTPUT_GAIN

        # P2 (pulmonic S2 component): delayed, softer
        split_ms = 20.0 + 30.0 * modifiers.parasympathetic_tone
        split_ms += 15.0 * max(0.0, np.sin(resp_phase))
        p2_onset = s2_onset_sample + int(split_ms / 1000.0 * sr)
        p2_exc = self._generate_excitation(n_samples, p2_onset, s2_amp * 0.55)
        pcm += self._resonator_s2.process(p2_exc) * _RESONATOR_OUTPUT_GAIN * 0.5

        # --- S3 gallop (damage > 0.3) ---
        s3_present = damage > 0.3 and beat_kind in ('sinus', 'svt', 'af')
        if s3_present:
            s3_onset_ms = s2_onset_ms + 120.0 + 40.0 * (1.0 - damage)
            s3_onset = int(s3_onset_ms / 1000.0 * sr)
            s3_amp = 0.15 * min(1.0, (damage - 0.3) / 0.4)
            s3_amp *= 1.0 + 0.15 * np.sin(resp_phase)
            s3_exc = self._generate_excitation(n_samples, s3_onset, s3_amp)
            pcm += self._resonator_s3.process(s3_exc) * _RESONATOR_OUTPUT_GAIN

        # --- S4 gallop (damage > 0.5) ---
        s4_present = damage > 0.5 and conduction.p_wave_present
        if s4_present:
            sa_ms = act_times.get('sa', 0.0)
            s4_onset_ms = sa_ms + 60.0
            s4_onset = int(s4_onset_ms / 1000.0 * sr)
            s4_amp = 0.12 * min(1.0, (damage - 0.5) / 0.3)
            s4_amp *= 1.0 + 0.15 * np.sin(resp_phase)
            s4_exc = self._generate_excitation(n_samples, s4_onset, s4_amp)
            pcm += self._resonator_s4.process(s4_exc) * _RESONATOR_OUTPUT_GAIN

        # --- Murmurs ---
        murmur_present = False
        murmur_type = modifiers.murmur_type
        murmur_severity = modifiers.murmur_severity
        if murmur_type and murmur_severity > 0.05:
            from app.engine.core.parametric_pcg import _add_murmur
            from app.engine.mechanical.murmur_config import MURMUR_PROFILES, MURMUR_TYPE_COMPAT
            profile_key = MURMUR_TYPE_COMPAT.get(murmur_type, murmur_type)
            if profile_key and profile_key in MURMUR_PROFILES:
                murmur_present = True
                profile = MURMUR_PROFILES[profile_key]
                _add_murmur(pcm, profile, s1_onset_sample, s2_onset_sample,
                            n_samples, murmur_severity, sr, self._rng)

        # --- Respiratory noise ---
        n_cycle = int(rr_sec * 0.25 * sr)  # quarter of respiratory cycle
        resp_phase_arr = np.zeros(n_samples, dtype=np.float64)
        if n_cycle > 0:
            resp_phase_arr[:] = resp_phase + np.arange(n_samples) / sr * 2 * np.pi * 0.25
        else:
            resp_phase_arr[:] = resp_phase
        resp_env = 1.0 + 0.3 * np.sin(resp_phase_arr)
        pcm += self._rng.normal(0, _RESPIRATORY_NOISE_AMP, n_samples) * resp_env
        pcm += self._rng.normal(0, _MUSCLE_NOISE_AMP, n_samples)

        # --- Stethoscope low-pass filter ---
        # Real stethoscopes have steep mechanical rolloff above ~400-500 Hz.
        # 6th-order Butterworth at 500 Hz approximates the acoustic transfer
        # function of a Littmann-type stethoscope (bell + tubing).
        try:
            from scipy.signal import butter, sosfilt
            sos = butter(6, 500.0, btype='low', fs=sr, output='sos')
            pcm = sosfilt(sos, pcm)
        except Exception:
            pass

        # --- 4-band WDRC ---
        pcm = self._compressor.process(pcm)

        # --- Beat crossfade (5ms cosine ramp) ---
        fade_samples = int(0.005 * sr)
        if fade_samples > 0 and n_samples > 2 * fade_samples:
            fade_in = 0.5 * (1.0 - np.cos(np.linspace(0, np.pi, fade_samples)))
            fade_out = 0.5 * (1.0 + np.cos(np.linspace(0, np.pi, fade_samples)))
            pcm[:fade_samples] *= fade_in
            pcm[-fade_samples:] *= fade_out

        if self._prev_tail is not None and len(self._prev_tail) > 0:
            overlap = min(len(self._prev_tail), fade_samples, n_samples)
            pcm[:overlap] += self._prev_tail[:overlap]
        self._prev_tail = pcm[-fade_samples:].copy() if fade_samples > 0 else None

        # --- Position channels via chest transfer functions ---
        channels: dict[str, NDArray[np.float64]] = {}
        for pos in self._chest_filter.list_positions():
            channels[pos] = self._chest_filter.apply(pcm, pos)

        return PcgFrame(
            samples=pcm.astype(np.float64),
            sample_rate=sr,
            s1_onset_sample=s1_onset_sample,
            s2_onset_sample=s2_onset_sample,
            murmur_present=murmur_present,
            channels=channels,
            s3_present=s3_present,
            s4_present=s4_present,
        )

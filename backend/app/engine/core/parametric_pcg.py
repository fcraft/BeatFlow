"""V3 parametric PCG synthesizer — S1/S2 timing directly from beat timeline.

Replaces the V2 AcousticGeneratorV2 (which required HemodynamicState with
valve events from a full ODE solve).  V3 computes S1/S2 onset directly from
the conduction result using Weissler's LVET formula, then synthesizes heart
sounds using modal decomposition (multi-damped-sinusoid) identical to V2's
acoustic quality.

Features:
- S1: M1 (mitral) + T1 (tricuspid) modal decomposition
- S2: A2 (aortic) + P2 (pulmonic) with parasympathetic splitting
- S3: Rapid filling gallop (damage > 0.3)
- S4: Atrial gallop (damage > 0.5)
- Murmurs: 7 types from murmur_config profiles
- AGC: Adaptive gain control
- Beat crossfade: 5ms cosine ramp at boundaries
- 4-position output (aortic, pulmonic, tricuspid, mitral)
"""
from __future__ import annotations

import logging

import numpy as np
from numpy.typing import NDArray

from app.engine.core.types import (
    ConductionResult,
    Modifiers,
    PcgFrame,
)
from app.engine.mechanical.murmur_config import MURMUR_PROFILES, MURMUR_TYPE_COMPAT

logger = logging.getLogger(__name__)

# Sample rate
PCG_SR = 4000

# ---------- Modal decomposition tables ----------
# S1: Mitral component (M1) — 3 modes
M1_MODES = [
    (50.0, 0.25, 30.0),
    (100.0, 0.50, 40.0),
    (150.0, 0.25, 55.0),
]
M1_DUR_MS = 80.0

# S1: Tricuspid component (T1) — 2 modes
T1_MODES = [
    (40.0, 0.40, 25.0),
    (80.0, 0.60, 40.0),
]
T1_DUR_MS = 60.0
T1_DELAY_MS = 10.0

# S2: Aortic component (A2) — 3 modes
A2_MODES = [
    (80.0, 0.20, 35.0),
    (120.0, 0.55, 45.0),
    (180.0, 0.25, 60.0),
]
A2_DUR_MS = 60.0

# S2: Pulmonic component (P2) — 2 modes
P2_MODES = [
    (60.0, 0.45, 30.0),
    (100.0, 0.55, 50.0),
]
P2_DUR_MS = 50.0

# S3 modes (low-frequency gallop)
S3_MODES = [(30.0, 0.60, 20.0), (50.0, 0.40, 30.0)]
S3_DUR_MS = 60.0

# S4 modes (atrial gallop)
S4_MODES = [(25.0, 0.55, 18.0), (45.0, 0.45, 25.0)]
S4_DUR_MS = 50.0

# AGC
_AGC_TARGET_RMS = 0.08
_AGC_TAU = 0.3

# Noise
_BACKGROUND_NOISE_AMP = 0.003
_RESPIRATORY_NOISE_AMP = 0.002
_MUSCLE_NOISE_AMP = 0.001


class ParametricPcgSynthesizer:
    """V3 parametric PCG synthesizer."""

    SAMPLE_RATE: int = PCG_SR

    def __init__(self) -> None:
        self._agc_gain: float = 1.0
        self._prev_tail: NDArray[np.float64] | None = None
        self._rng = np.random.default_rng()

    def synthesize(
        self,
        conduction: ConductionResult,
        modifiers: Modifiers,
    ) -> PcgFrame:
        """Synthesize one beat of PCG from conduction timing."""
        sr = self.SAMPLE_RATE
        rr_sec = conduction.rr_sec
        n_samples = int(rr_sec * sr)
        hr = 60.0 / rr_sec

        beat_kind = conduction.beat_kind
        pcm = np.zeros(n_samples, dtype=np.float64)

        if beat_kind == 'asystole':
            pcm += self._rng.normal(0, _BACKGROUND_NOISE_AMP, n_samples)
            return PcgFrame(
                samples=pcm, sample_rate=sr,
                s1_onset_sample=0, s2_onset_sample=0,
                murmur_present=False, channels={},
            )

        if beat_kind == 'vf':
            pcm = self._rng.normal(0, 0.02, n_samples).astype(np.float64)
            return PcgFrame(
                samples=pcm, sample_rate=sr,
                s1_onset_sample=0, s2_onset_sample=0,
                murmur_present=False, channels={},
            )

        # --- S1/S2 timing ---
        act_times = conduction.activation_times
        his_ms = act_times.get('his', 110.0)
        purkinje_ms = act_times.get('purkinje', 125.0)

        # S1 onset: QRS onset + electromechanical delay (20-40ms)
        if beat_kind in ('vt', 'pvc'):
            qrs_onset_ms = purkinje_ms
        else:
            qrs_onset_ms = his_ms
        s1_onset_ms = qrs_onset_ms + 30.0  # 30ms electromechanical delay

        # S2 onset: S1 + LVET(HR), Weissler: LVET = -1.7 × HR + 413 ms
        lvet_ms = max(200.0, -1.7 * hr + 413.0)
        s2_onset_ms = s1_onset_ms + lvet_ms

        s1_onset_sample = int(s1_onset_ms / 1000.0 * sr)
        s2_onset_sample = int(s2_onset_ms / 1000.0 * sr)

        # Clamp within beat
        s1_onset_sample = max(0, min(s1_onset_sample, n_samples - 1))
        s2_onset_sample = max(s1_onset_sample + int(0.1 * sr), min(s2_onset_sample, n_samples - 1))

        # --- Amplitude scaling ---
        contractility = modifiers.contractility_modifier
        damage = modifiers.damage_level
        attenuation = modifiers.chest_wall_attenuation

        s1_amp = 0.6 * contractility * (1.0 - 0.3 * damage) * attenuation
        s1_amp = max(0.1, min(1.0, s1_amp))
        s2_amp = 0.4 * (1.0 - 0.2 * damage) * attenuation
        s2_amp = max(0.05, min(0.8, s2_amp))

        # --- S1: M1 + T1 ---
        _add_modal_burst(pcm, s1_onset_sample, M1_MODES, M1_DUR_MS, s1_amp, sr)
        t1_onset = s1_onset_sample + int(T1_DELAY_MS / 1000.0 * sr)
        _add_modal_burst(pcm, t1_onset, T1_MODES, T1_DUR_MS, s1_amp * 0.5, sr)

        # --- S2: A2 + P2 ---
        _add_modal_burst(pcm, s2_onset_sample, A2_MODES, A2_DUR_MS, s2_amp, sr)
        # A2-P2 splitting (parasympathetic widens split)
        split_ms = 20.0 + 30.0 * modifiers.parasympathetic_tone
        p2_onset = s2_onset_sample + int(split_ms / 1000.0 * sr)
        _add_modal_burst(pcm, p2_onset, P2_MODES, P2_DUR_MS, s2_amp * 0.6, sr)

        # --- S3 gallop (damage > 0.3) ---
        s3_present = damage > 0.3 and beat_kind in ('sinus', 'svt', 'af')
        if s3_present:
            s3_onset_ms = s2_onset_ms + 120.0 + 40.0 * (1.0 - damage)
            s3_onset = int(s3_onset_ms / 1000.0 * sr)
            s3_amp = 0.15 * min(1.0, (damage - 0.3) / 0.4)
            _add_modal_burst(pcm, s3_onset, S3_MODES, S3_DUR_MS, s3_amp, sr)

        # --- S4 gallop (damage > 0.5) ---
        s4_present = damage > 0.5 and conduction.p_wave_present
        if s4_present:
            sa_ms = act_times.get('sa', 0.0)
            s4_onset_ms = sa_ms + 60.0
            s4_onset = int(s4_onset_ms / 1000.0 * sr)
            s4_amp = 0.12 * min(1.0, (damage - 0.5) / 0.3)
            _add_modal_burst(pcm, s4_onset, S4_MODES, S4_DUR_MS, s4_amp, sr)

        # --- Murmurs ---
        murmur_present = False
        murmur_type = modifiers.murmur_type
        murmur_severity = modifiers.murmur_severity
        if murmur_type and murmur_severity > 0.05:
            murmur_present = True
            profile_key = MURMUR_TYPE_COMPAT.get(murmur_type, murmur_type)
            if profile_key and profile_key in MURMUR_PROFILES:
                profile = MURMUR_PROFILES[profile_key]
                _add_murmur(pcm, profile, s1_onset_sample, s2_onset_sample,
                            n_samples, murmur_severity, sr, self._rng)

        # --- 4-layer noise ---
        pcm += self._rng.normal(0, _BACKGROUND_NOISE_AMP, n_samples)
        resp_phase = modifiers.respiratory_phase
        resp_env = 1.0 + 0.3 * np.sin(resp_phase + np.linspace(0, 2 * np.pi * rr_sec * 0.25, n_samples))
        pcm += self._rng.normal(0, _RESPIRATORY_NOISE_AMP, n_samples) * resp_env
        pcm += self._rng.normal(0, _MUSCLE_NOISE_AMP, n_samples)

        # --- Stethoscope low-pass filter (800 Hz cutoff) ---
        try:
            from scipy.signal import butter, sosfilt
            sos = butter(4, 800.0, btype='low', fs=sr, output='sos')
            pcm = sosfilt(sos, pcm)
        except Exception:
            pass  # graceful degradation

        # --- AGC ---
        rms = float(np.sqrt(np.mean(pcm ** 2))) + 1e-12
        target_gain = _AGC_TARGET_RMS / rms
        target_gain = max(0.3, min(3.0, target_gain))
        alpha = 1.0 - np.exp(-rr_sec / _AGC_TAU)
        self._agc_gain += alpha * (target_gain - self._agc_gain)
        pcm *= self._agc_gain

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

        # --- Multi-position channels ---
        channels = _compute_position_channels(pcm, murmur_type, murmur_severity)

        return PcgFrame(
            samples=pcm,
            sample_rate=sr,
            s1_onset_sample=s1_onset_sample,
            s2_onset_sample=s2_onset_sample,
            murmur_present=murmur_present,
            channels=channels,
            s3_present=s3_present,
            s4_present=s4_present,
        )


# ---------- Helpers ----------

def _add_modal_burst(
    buffer: NDArray[np.float64],
    onset: int,
    modes: list[tuple[float, float, float]],
    duration_ms: float,
    amplitude: float,
    sr: int,
) -> None:
    """Add a multi-mode damped sinusoid burst at onset."""
    n = int(duration_ms / 1000.0 * sr)
    end = min(onset + n, len(buffer))
    if end <= onset or onset < 0:
        return
    actual_n = end - onset
    tau = np.arange(actual_n, dtype=np.float64) / sr

    burst = np.zeros(actual_n, dtype=np.float64)
    for freq, rel_amp, damping in modes:
        burst += rel_amp * np.exp(-damping * tau) * np.sin(2.0 * np.pi * freq * tau)
    burst *= amplitude
    buffer[onset:end] += burst


def _add_murmur(
    buffer: NDArray[np.float64],
    profile,
    s1_sample: int,
    s2_sample: int,
    n_samples: int,
    severity: float,
    sr: int,
    rng: np.random.Generator,
) -> None:
    """Add murmur noise shaped by profile envelope."""
    from app.engine.mechanical.murmur_config import MurmurProfile

    if profile.timing == 'systolic':
        start = s1_sample + int(0.02 * sr)
        end = min(s2_sample, n_samples)
    elif profile.timing == 'diastolic':
        start = s2_sample + int(0.02 * sr)
        end = n_samples
    else:  # continuous
        start = s1_sample
        end = n_samples

    if end <= start:
        return

    n = end - start
    t = np.linspace(0, 1, n)

    # Envelope shape
    if profile.shape == 'diamond':
        env = np.where(t < 0.5, 2 * t, 2 * (1 - t))
    elif profile.shape == 'plateau':
        env = np.ones(n)
        ramp = max(1, int(0.1 * n))
        env[:ramp] = np.linspace(0, 1, ramp)
        env[-ramp:] = np.linspace(1, 0, ramp)
    elif profile.shape == 'decrescendo':
        env = np.linspace(1, 0, n)
    elif profile.shape == 'rumbling':
        env = 0.7 + 0.3 * np.sin(2 * np.pi * 3 * t)
    else:  # machinery
        env = np.ones(n)

    # Band-limited noise
    noise = rng.normal(0, 1, n)
    try:
        from scipy.signal import butter, sosfilt
        lo = max(20, profile.freq_lo)
        hi = min(sr / 2 - 1, profile.freq_hi)
        if lo < hi:
            sos = butter(3, [lo, hi], btype='bandpass', fs=sr, output='sos')
            noise = sosfilt(sos, noise)
    except Exception:
        pass

    murmur_signal = noise * env * severity * profile.amp_factor
    buffer[start:end] += murmur_signal


def _compute_position_channels(
    primary: NDArray[np.float64],
    murmur_type: str,
    murmur_severity: float,
) -> dict[str, NDArray[np.float64]]:
    """Compute 4-position PCG channels with position-specific weighting."""
    # Base weights (without murmur)
    weights = {
        'aortic': 0.8,
        'pulmonic': 0.7,
        'tricuspid': 0.6,
        'mitral': 1.0,
    }

    # Adjust weights for murmur if present
    profile_key = MURMUR_TYPE_COMPAT.get(murmur_type, murmur_type)
    if profile_key and profile_key in MURMUR_PROFILES and murmur_severity > 0.05:
        site_w = MURMUR_PROFILES[profile_key].site_weights
        for pos in weights:
            weights[pos] = max(weights[pos], site_w.get(pos, 0.0))

    return {pos: (primary * w).copy() for pos, w in weights.items()}

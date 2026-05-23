"""Physical-model PCG synthesizer: jittered multi-pulse damped-sinusoid synthesis.

Replaces the pure damped-sinusoid modal decomposition in ParametricPcgSynthesizer
with a physically-motivated pipeline:

  1. Chaotic Multi-Pulse Excitation — 4-6 jittered micro-pulses + noise burst
     simulating turbulent asynchronous valve leaflet closure
  2. Damped Sinusoid Synthesis — per-mode direct sin(ωt)·exp(-damping·t)
     with fast clinical damping rates (25-60 Hz) matching real heart sound
     temporal envelopes (NOT slow IIR resonator ringing)
  3. Envelope Shaping — fast-attack/hold/exponential-decay window to further
     tighten the percussive character
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

# ---------- Modal decomposition tables ----------
# (freq Hz, relative gain, damping Hz) — same format as parametric engine.
# Damping rates of 25-60 Hz produce fast percussive decays (time constant
# 17-40 ms), matching real heart sounds which are heavily damped tissue
# vibrations, NOT resonant ringing.

# S1: Mitral component (M1) — 3 modes
M1_MODES: list[tuple[float, float, float]] = [
    (50.0, 0.30, 30.0),
    (100.0, 0.45, 40.0),
    (150.0, 0.25, 55.0),
]
M1_DUR_MS = 80.0

# S1: Tricuspid component (T1) — 2 modes
T1_MODES: list[tuple[float, float, float]] = [
    (40.0, 0.40, 25.0),
    (80.0, 0.60, 40.0),
]
T1_DUR_MS = 60.0
T1_DELAY_MS = 10.0

# S2: Aortic component (A2) — 3 modes
A2_MODES: list[tuple[float, float, float]] = [
    (80.0, 0.20, 35.0),
    (120.0, 0.55, 45.0),
    (180.0, 0.25, 60.0),
]
A2_DUR_MS = 60.0

# S2: Pulmonic component (P2) — 2 modes
P2_MODES: list[tuple[float, float, float]] = [
    (60.0, 0.45, 30.0),
    (100.0, 0.55, 50.0),
]
P2_DUR_MS = 50.0

# S3 modes (low-frequency gallop)
S3_MODES: list[tuple[float, float, float]] = [
    (30.0, 0.60, 20.0),
    (50.0, 0.40, 30.0),
]
S3_DUR_MS = 60.0

# S4 modes (atrial gallop)
S4_MODES: list[tuple[float, float, float]] = [
    (25.0, 0.55, 18.0),
    (45.0, 0.45, 25.0),
]
S4_DUR_MS = 50.0

# Noise floor
_BACKGROUND_NOISE_AMP = 0.003
_RESPIRATORY_NOISE_AMP = 0.002
_MUSCLE_NOISE_AMP = 0.001

# Multi-pulse excitation parameters
_N_MICRO_PULSES = 5
_PULSE_SPREAD_MS = 10.0
_PULSE_JITTER_MS = 2.0
_NOISE_BURST_DURATION_MS = 15.0

# Envelope shaping: tight percussive window
_ENV_ATTACK_MS = 5.0
_ENV_HOLD_MS = 6.0
_ENV_DECAY_TAU_MS = 40.0

# Output gain (damped sinusoids have natural peak ~1.0, so less gain needed
# than the IIR resonator version)
_OUTPUT_GAIN = 2.5


def _add_modal_burst(
    buffer: NDArray[np.float64],
    onset: int,
    modes: list[tuple[float, float, float]],
    duration_ms: float,
    amplitude: float,
    sr: int,
    rng: np.random.Generator | None = None,
) -> None:
    """Add a multi-mode damped sinusoid burst at onset.

    Each mode contributes: rel_amp · exp(-damping·t) · sin(2π·freq·t + phase)
    with random initial phase per mode to prevent phase-aligned constructive
    interference that causes visual baseline asymmetry. Fast damping rates
    (25-60 Hz) produce natural percussive decay.
    """
    n = int(duration_ms / 1000.0 * sr)
    end = min(onset + n, len(buffer))
    if end <= onset or onset < 0:
        return
    actual_n = end - onset
    tau = np.arange(actual_n, dtype=np.float64) / sr

    burst = np.zeros(actual_n, dtype=np.float64)
    for freq, rel_amp, damping in modes:
        phase = rng.uniform(0, 2.0 * np.pi) if rng is not None else 0.0
        burst += rel_amp * np.exp(-damping * tau) * np.sin(2.0 * np.pi * freq * tau + phase)
    burst *= amplitude
    buffer[onset:end] += burst


class PhysicalPcgSynthesizer:
    """Physical-model PCG synthesizer using jittered multi-pulse damped-sinusoid
    synthesis with 4-band WDRC and chest transfer functions.

    Key differences from ParametricPcgSynthesizer:
    - Multi-pulse chaotic excitation (NOT clean single burst)
    - Turbulent noise burst at valve closure onset
    - 4-band WDRC (NOT single-band AGC)
    - Per-position chest transfer FIR filters
    - Envelope shaping for tighter percussive character
    """

    SAMPLE_RATE: int = PCG_SR

    def __init__(self) -> None:
        self._prev_tail: NDArray[np.float64] | None = None
        self._rng = np.random.default_rng()
        self._frac_acc: float = 0.0

        self._compressor: object | None = None
        self._chest_filter: object | None = None

    def _ensure_components(self) -> None:
        """Lazy-initialize compressor and chest filters."""
        from app.engine.core.band_compressor import design_pcg_compressor
        from app.engine.core.chest_transfer import ChestTransferFilter

        if self._compressor is None:
            self._compressor = design_pcg_compressor(sample_rate=self.SAMPLE_RATE)

        if self._chest_filter is None:
            self._chest_filter = ChestTransferFilter(sample_rate=self.SAMPLE_RATE)

    def _generate_heart_sound(
        self,
        n_samples: int,
        onset_sample: int,
        amplitude: float,
        modes: list[tuple[float, float, float]],
        duration_ms: float,
        noise_amp_ratio: float = 0.10,
    ) -> NDArray[np.float64]:
        """Generate one heart sound (S1/S2/S3/S4) via jittered multi-pulse
        damped-sinusoid synthesis + noise burst.

        The multi-pulse jitter simulates asynchronous leaflet closure —
        each of the 2-3 valve leaflets closes within ~10ms of the others,
        creating a complex interference pattern rather than a pure tone.
        """
        sr = self.SAMPLE_RATE
        sound = np.zeros(n_samples, dtype=np.float64)

        # --- Multi-pulse excitation ---
        pulse_times_ms = np.sort(
            self._rng.uniform(0.0, _PULSE_SPREAD_MS, _N_MICRO_PULSES)
        )

        for pulse_time_ms in pulse_times_ms:
            jitter_ms = self._rng.uniform(-_PULSE_JITTER_MS, _PULSE_JITTER_MS)
            onset = onset_sample + int((pulse_time_ms + jitter_ms) / 1000.0 * sr)
            pulse_amp = amplitude * self._rng.uniform(0.7, 1.0) / _N_MICRO_PULSES

            if 0 <= onset < n_samples:
                _add_modal_burst(sound, onset, modes, duration_ms, pulse_amp, sr, rng=self._rng)

        # --- Turbulent noise burst ---
        noise_samples = int(_NOISE_BURST_DURATION_MS / 1000.0 * sr)
        noise_onset = onset_sample - int(3.0 / 1000.0 * sr)
        noise_start = max(0, noise_onset)
        noise_end = min(n_samples, noise_start + noise_samples)
        noise_len = noise_end - noise_start

        if noise_len > 0:
            raw_noise = self._rng.normal(0, 1.0, noise_len)
            # Band-limit to heart sound range (~200 Hz lowpass via moving average)
            window = max(1, int(sr / 400))
            kernel = np.ones(window) / window
            raw_noise = np.convolve(raw_noise, kernel, mode='same')
            # Envelope: fast attack, exponential decay
            noise_env = np.exp(-np.arange(noise_len) / (noise_samples * 0.35))
            sound[noise_start:noise_end] += (
                raw_noise * noise_env * amplitude * noise_amp_ratio
            )

        # --- Envelope shaping ---
        # Tighter window than natural damped-sinusoid decay: cuts any
        # residual ringing tail for a cleaner percussive "thump".
        attack_samples = int(_ENV_ATTACK_MS / 1000.0 * sr)
        hold_samples = int(_ENV_HOLD_MS / 1000.0 * sr)
        decay_tau_samples = _ENV_DECAY_TAU_MS / 1000.0 * sr

        env_start = max(0, onset_sample - int(3.0 / 1000.0 * sr))
        for i in range(len(sound)):
            rel = i - env_start
            if rel < 0:
                continue
            elif rel < attack_samples:
                sound[i] *= rel / max(1, attack_samples)
            elif rel < attack_samples + hold_samples:
                pass
            else:
                decay_rel = rel - attack_samples - hold_samples
                sound[i] *= np.exp(-decay_rel / decay_tau_samples)

        return sound

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
        s1_onset_ms = qrs_onset_ms + 30.0

        lvet_ms = max(200.0, -1.7 * hr + 413.0)
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
        s2_amp = 0.5 * (1.0 - 0.2 * damage) * attenuation
        ref_diastole_ms = 689.0
        actual_diastole_ms = max(0.0, rr_sec * 1000.0 - lvet_ms)
        hr_s2_factor = min(1.0, (actual_diastole_ms / ref_diastole_ms) ** 0.3)
        s2_amp *= hr_s2_factor
        s2_amp = max(0.05, min(0.9, s2_amp))

        # --- Respiratory amplitude modulation ---
        resp_phase = modifiers.respiratory_phase
        resp_amp_factor = 1.0 - 0.08 * (0.5 + 0.5 * np.sin(resp_phase))
        s1_amp *= resp_amp_factor
        s2_amp *= resp_amp_factor

        # --- Synthesis pipeline ---
        pcm = self._rng.normal(0, _BACKGROUND_NOISE_AMP * 0.5, n_samples).astype(np.float64)

        # S1: M1 + T1 with inter-component delay
        pcm += self._generate_heart_sound(
            n_samples, s1_onset_sample, s1_amp,
            M1_MODES, M1_DUR_MS, noise_amp_ratio=0.08,
        ) * _OUTPUT_GAIN
        t1_onset = s1_onset_sample + int(T1_DELAY_MS / 1000.0 * sr)
        pcm += self._generate_heart_sound(
            n_samples, t1_onset, s1_amp * 0.5,
            T1_MODES, T1_DUR_MS, noise_amp_ratio=0.06,
        ) * _OUTPUT_GAIN

        # S2: A2 + delayed P2
        pcm += self._generate_heart_sound(
            n_samples, s2_onset_sample, s2_amp,
            A2_MODES, A2_DUR_MS, noise_amp_ratio=0.07,
        ) * _OUTPUT_GAIN

        split_ms = 20.0 + 30.0 * modifiers.parasympathetic_tone
        split_ms += 15.0 * max(0.0, np.sin(resp_phase))
        p2_onset = s2_onset_sample + int(split_ms / 1000.0 * sr)
        pcm += self._generate_heart_sound(
            n_samples, p2_onset, s2_amp * 0.55,
            P2_MODES, P2_DUR_MS, noise_amp_ratio=0.05,
        ) * _OUTPUT_GAIN

        # --- S3 gallop (damage > 0.3) ---
        s3_present = damage > 0.3 and beat_kind in ('sinus', 'svt', 'af')
        if s3_present:
            s3_onset_ms = s2_onset_ms + 120.0 + 40.0 * (1.0 - damage)
            s3_onset = int(s3_onset_ms / 1000.0 * sr)
            s3_amp = 0.15 * min(1.0, (damage - 0.3) / 0.4)
            s3_amp *= 1.0 + 0.15 * np.sin(resp_phase)
            pcm += self._generate_heart_sound(
                n_samples, s3_onset, s3_amp,
                S3_MODES, S3_DUR_MS, noise_amp_ratio=0.06,
            ) * _OUTPUT_GAIN

        # --- S4 gallop (damage > 0.5) ---
        s4_present = damage > 0.5 and conduction.p_wave_mode != "absent"
        if s4_present:
            sa_ms = act_times.get('sa', 0.0)
            s4_onset_ms = sa_ms + 60.0
            s4_onset = int(s4_onset_ms / 1000.0 * sr)
            s4_amp = 0.12 * min(1.0, (damage - 0.5) / 0.3)
            s4_amp *= 1.0 + 0.15 * np.sin(resp_phase)
            pcm += self._generate_heart_sound(
                n_samples, s4_onset, s4_amp,
                S4_MODES, S4_DUR_MS, noise_amp_ratio=0.05,
            ) * _OUTPUT_GAIN

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
        n_cycle = int(rr_sec * 0.25 * sr)
        resp_phase_arr = np.zeros(n_samples, dtype=np.float64)
        if n_cycle > 0:
            resp_phase_arr[:] = resp_phase + np.arange(n_samples) / sr * 2 * np.pi * 0.25
        else:
            resp_phase_arr[:] = resp_phase
        resp_env = 1.0 + 0.3 * np.sin(resp_phase_arr)
        pcm += self._rng.normal(0, _RESPIRATORY_NOISE_AMP, n_samples) * resp_env
        pcm += self._rng.normal(0, _MUSCLE_NOISE_AMP, n_samples)

        # --- Stethoscope low-pass filter ---
        try:
            from scipy.signal import butter, sosfilt
            sos = butter(6, 500.0, btype='low', fs=sr, output='sos')
            pcm = sosfilt(sos, pcm)
        except Exception:
            pass

        # --- 4-band WDRC ---
        pcm = self._compressor.process(pcm)

        # --- DC removal ---
        # Damped sinusoids exp(-αt)·sin(ωt) have a net DC offset because
        # successive half-cycles shrink under the exponential envelope.
        # Real stethoscopes are AC-coupled — remove DC so the waveform is
        # visually symmetric around the zero baseline.
        pcm -= np.mean(pcm)

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

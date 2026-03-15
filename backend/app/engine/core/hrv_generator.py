"""HRV frequency-domain generator: LF/HF inverse-FFT → per-beat RR offset.

Generates realistic heart rate variability by synthesizing time-domain RR
interval fluctuations from specified LF (0.04-0.15 Hz) and HF (0.15-0.40 Hz)
spectral power components using inverse FFT.

Key features:
- LF/HF spectral power control with physiological defaults
- Respiratory Sinus Arrhythmia (RSA): HF power is modulated by breathing phase
- Autonomic tone modulation: sympathetic → LF, parasympathetic → HF
- Circular buffer of RR offsets for smooth beat-to-beat variation
- State save/restore for simulation continuity

Reference: Task Force of the European Society of Cardiology, Circulation 1996.
"""
from __future__ import annotations

import math
from typing import Any

import numpy as np
from numpy.typing import NDArray


# Frequency bands (Hz)
_LF_LOW = 0.04
_LF_HIGH = 0.15
_HF_LOW = 0.15
_HF_HIGH = 0.40

# Default spectral power (ms²) — healthy resting adult
_DEFAULT_LF_POWER = 1000.0   # ms²
_DEFAULT_HF_POWER = 500.0    # ms²

# Buffer length: generate this many RR offsets at once (at ~1 Hz ≈ beats)
_BUFFER_LENGTH = 256


class HrvGenerator:
    """Frequency-domain HRV generator producing per-beat RR offsets.

    Usage::

        hrv = HrvGenerator()
        for each beat:
            offset_ms = hrv.next_offset(
                sympathetic_tone=...,
                parasympathetic_tone=...,
                respiratory_freq_hz=...,
                respiratory_phase=...,
            )
            actual_rr_ms = base_rr_ms + offset_ms
    """

    def __init__(
        self,
        lf_power: float = _DEFAULT_LF_POWER,
        hf_power: float = _DEFAULT_HF_POWER,
        sample_rate_hz: float = 1.0,
        seed: int | None = None,
    ) -> None:
        """
        Args:
            lf_power: Baseline LF spectral power (ms²).
            hf_power: Baseline HF spectral power (ms²).
            sample_rate_hz: Approximate sampling rate in beats/sec (~1 Hz).
            seed: Optional RNG seed for reproducibility.
        """
        self._lf_power_base = lf_power
        self._hf_power_base = hf_power
        self._fs = sample_rate_hz
        self._rng = np.random.default_rng(seed)

        # Circular buffer
        self._buffer: NDArray[np.float64] = np.zeros(0)
        self._buf_idx: int = 0

        # State for smooth transitions
        self._prev_lf_gain: float = 1.0
        self._prev_hf_gain: float = 1.0

    def next_offset(
        self,
        sympathetic_tone: float = 0.5,
        parasympathetic_tone: float = 0.5,
        respiratory_freq_hz: float = 0.23,
        respiratory_phase: float = 0.0,
    ) -> float:
        """Get next per-beat RR offset in milliseconds.

        Args:
            sympathetic_tone: [0, 1] — scales LF power.
            parasympathetic_tone: [0, 1] — scales HF power.
            respiratory_freq_hz: Current breathing frequency (Hz), centres HF peak.
            respiratory_phase: Current respiratory phase [0, 2π] for RSA modulation.

        Returns:
            RR offset in milliseconds (can be positive or negative).
        """
        # Regenerate buffer if exhausted
        if self._buf_idx >= len(self._buffer):
            self._regenerate_buffer(
                sympathetic_tone, parasympathetic_tone,
                respiratory_freq_hz,
            )

        offset = float(self._buffer[self._buf_idx])
        self._buf_idx += 1

        # Apply RSA modulation: inspiration shortens RR, expiration lengthens
        # RSA amplitude scales with parasympathetic tone
        rsa_amplitude = 15.0 * parasympathetic_tone  # ±15ms at full vagal tone
        rsa = rsa_amplitude * math.sin(respiratory_phase)
        offset += rsa

        return offset

    def _regenerate_buffer(
        self,
        sympathetic_tone: float,
        parasympathetic_tone: float,
        respiratory_freq_hz: float,
    ) -> None:
        """Generate a new buffer of RR offsets via inverse FFT.

        Constructs a power spectrum with LF and HF components, applies
        random phases, and inverse-FFTs to get time-domain RR fluctuations.
        """
        n = _BUFFER_LENGTH
        freqs = np.fft.rfftfreq(n, d=1.0 / self._fs)
        n_freq = len(freqs)

        # Compute gain factors with smoothing
        lf_gain = 0.5 + 1.5 * sympathetic_tone  # [0.5, 2.0]
        hf_gain = 0.5 + 1.5 * parasympathetic_tone  # [0.5, 2.0]

        # Smooth transition (exponential filter)
        alpha = 0.3
        lf_gain = self._prev_lf_gain + alpha * (lf_gain - self._prev_lf_gain)
        hf_gain = self._prev_hf_gain + alpha * (hf_gain - self._prev_hf_gain)
        self._prev_lf_gain = lf_gain
        self._prev_hf_gain = hf_gain

        # Effective power
        lf_power = self._lf_power_base * lf_gain
        hf_power = self._hf_power_base * hf_gain

        # Build power spectral density
        psd = np.zeros(n_freq, dtype=np.float64)

        for i, f in enumerate(freqs):
            if f <= 0:
                continue

            # LF component: Gaussian-shaped around 0.1 Hz
            if _LF_LOW <= f <= _LF_HIGH:
                lf_center = 0.10
                lf_sigma = 0.03
                lf_val = lf_power * math.exp(
                    -((f - lf_center) ** 2) / (2 * lf_sigma ** 2)
                )
                psd[i] += lf_val

            # HF component: Gaussian-shaped around respiratory frequency
            if _HF_LOW <= f <= _HF_HIGH:
                hf_center = max(_HF_LOW, min(_HF_HIGH, respiratory_freq_hz))
                hf_sigma = 0.04
                hf_val = hf_power * math.exp(
                    -((f - hf_center) ** 2) / (2 * hf_sigma ** 2)
                )
                psd[i] += hf_val

            # VLF floor (1/f noise, adds realism)
            if 0.003 < f < _LF_LOW:
                psd[i] += 200.0 / (f * 100.0)

        # Convert PSD to amplitude spectrum
        amplitude = np.sqrt(psd * 2.0 / n)

        # Random phases
        phases = self._rng.uniform(0, 2 * np.pi, n_freq)

        # Construct complex spectrum
        spectrum = amplitude * np.exp(1j * phases)
        spectrum[0] = 0.0  # No DC component

        # Inverse FFT to time domain
        signal = np.fft.irfft(spectrum, n=n)

        # Store in buffer
        self._buffer = signal.astype(np.float64)
        self._buf_idx = 0

    def get_lf_hf_ratio(
        self,
        sympathetic_tone: float = 0.5,
        parasympathetic_tone: float = 0.5,
    ) -> float:
        """Compute the LF/HF ratio for current autonomic state.

        Used for diagnostic display; not called during beat generation.
        """
        lf_gain = 0.5 + 1.5 * sympathetic_tone
        hf_gain = 0.5 + 1.5 * parasympathetic_tone
        lf = self._lf_power_base * lf_gain
        hf = self._hf_power_base * hf_gain
        if hf < 1e-6:
            return 999.0
        return lf / hf

    def get_state(self) -> dict[str, Any]:
        """Serialize state for save/restore."""
        return {
            "lf_power_base": self._lf_power_base,
            "hf_power_base": self._hf_power_base,
            "fs": self._fs,
            "buffer": self._buffer.tolist() if len(self._buffer) > 0 else [],
            "buf_idx": self._buf_idx,
            "prev_lf_gain": self._prev_lf_gain,
            "prev_hf_gain": self._prev_hf_gain,
            "rng_state": self._rng.bit_generator.state,
        }

    def set_state(self, state: dict[str, Any]) -> None:
        """Restore state from a previous get_state() call."""
        self._lf_power_base = state.get("lf_power_base", _DEFAULT_LF_POWER)
        self._hf_power_base = state.get("hf_power_base", _DEFAULT_HF_POWER)
        self._fs = state.get("fs", 1.0)
        buf = state.get("buffer", [])
        self._buffer = np.array(buf, dtype=np.float64) if buf else np.zeros(0)
        self._buf_idx = state.get("buf_idx", 0)
        self._prev_lf_gain = state.get("prev_lf_gain", 1.0)
        self._prev_hf_gain = state.get("prev_hf_gain", 1.0)
        if "rng_state" in state:
            self._rng.bit_generator.state = state["rng_state"]

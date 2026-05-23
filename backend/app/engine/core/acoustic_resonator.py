"""Cascade IIR resonator bank with nonlinear saturation for physical PCG synthesis.

Models the composite frequency response of ventricular walls, vascular walls,
and thoracic cavity as a bank of second-order IIR resonators with soft-clipping
nonlinearity that simulates tissue acoustic saturation.
"""
from __future__ import annotations

import numpy as np
from numpy.typing import NDArray


def soft_clip(x: NDArray[np.float64], threshold: float = 1.0) -> NDArray[np.float64]:
    """Soft-clipping nonlinearity: tanh-based saturation simulating tissue response.

    y = threshold * tanh(x / threshold)

    For |x| << threshold, y ≈ x (linear).
    For |x| >> threshold, y → ±threshold (saturation).
    """
    return threshold * np.tanh(np.asarray(x, dtype=np.float64) / threshold)


class CascadeResonator:
    """A single second-order IIR resonator modelling one vibration mode.

    Implements a discretized damped harmonic oscillator:
        y[n] = b0*x[n] - a1*y[n-1] - a2*y[n-2]

    Coefficients derived from analog prototype:
        H(s) = (omega_0/Q) * s / (s^2 + (omega_0/Q)*s + omega_0^2)
    using bilinear transform.

    Parameters:
        f0: Center frequency in Hz.
        Q: Quality factor (higher = sharper resonance, longer ring).
        sample_rate: Sample rate in Hz.
        gain: Output gain multiplier.
    """

    def __init__(self, f0: float, Q: float, sample_rate: int, gain: float = 1.0) -> None:
        if f0 <= 0 or Q <= 0:
            raise ValueError(f"f0={f0}, Q={Q} must be positive")
        w0 = 2.0 * np.pi * f0 / sample_rate
        alpha = np.sin(w0) / (2.0 * Q)

        # Bilinear transform coefficients for bandpass biquad
        b0 = alpha
        b1 = 0.0
        b2 = -alpha
        a0 = 1.0 + alpha
        a1 = -2.0 * np.cos(w0)
        a2 = 1.0 - alpha

        # Normalize by a0
        self._b0 = gain * b0 / a0
        self._b1 = gain * b1 / a0
        self._b2 = gain * b2 / a0
        self._a1 = -a1 / a0
        self._a2 = -a2 / a0

        self._z1: float = 0.0  # y[n-1]
        self._z2: float = 0.0  # y[n-2]
        self._x1: float = 0.0  # x[n-1]
        self._x2: float = 0.0  # x[n-2]

    def reset(self) -> None:
        """Clear resonator state."""
        self._z1 = 0.0
        self._z2 = 0.0
        self._x1 = 0.0
        self._x2 = 0.0

    def process(self, x: NDArray[np.float64]) -> NDArray[np.float64]:
        """Process input signal through the resonator."""
        x = np.asarray(x, dtype=np.float64)
        n = len(x)
        y = np.zeros(n, dtype=np.float64)

        for i in range(n):
            xi = x[i]
            yi = self._b0 * xi + self._b1 * self._x1 + self._b2 * self._x2 \
                 + self._a1 * self._z1 + self._a2 * self._z2
            y[i] = yi
            self._x2 = self._x1
            self._x1 = xi
            self._z2 = self._z1
            self._z1 = yi

        return y


class ResonatorBank:
    """A parallel bank of CascadeResonator instances with nonlinear saturation.

    Each resonator models a distinct vibration mode (e.g., S1: 4-6 modes at 30-180 Hz).
    Outputs are summed and passed through soft-clipping to simulate tissue nonlinearity.
    """

    def __init__(
        self,
        frequencies: list[float],
        Q_values: list[float],
        gains: list[float],
        sample_rate: int,
        clip_threshold: float = 1.0,
    ) -> None:
        if len(frequencies) != len(Q_values) or len(frequencies) != len(gains):
            raise ValueError("frequencies, Q_values, and gains must have same length")
        self._resonators = [
            CascadeResonator(f0=f, Q=q, sample_rate=sample_rate, gain=g)
            for f, q, g in zip(frequencies, Q_values, gains)
        ]
        self._clip_threshold = clip_threshold

    def reset(self) -> None:
        """Reset all resonators."""
        for r in self._resonators:
            r.reset()

    def process(self, x: NDArray[np.float64]) -> NDArray[np.float64]:
        """Pass input through all resonators in parallel and sum with soft-clip."""
        x = np.asarray(x, dtype=np.float64)
        n = len(x)
        out = np.zeros(n, dtype=np.float64)
        for resonator in self._resonators:
            resonator.reset()
            out += resonator.process(x)
        return soft_clip(out, threshold=self._clip_threshold)

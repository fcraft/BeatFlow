"""Chest transfer functions for 4 cardiac auscultation positions.

Models the frequency-dependent attenuation and resonance of the thoracic cavity
at each standard listening position. Uses FIR filters designed from idealized
chest-wall frequency response curves via the window method.

Positions:
  - Aortic: Right 2nd intercostal space — best for S2 (A2 component)
  - Pulmonic: Left 2nd intercostal space — best for S2 (P2 component), A2-P2 splitting
  - Tricuspid: Left 4th intercostal space — best for S1 (T1 component)
  - Mitral: Cardiac apex (5th ICS, midclavicular) — best for S1, S3, S4, mitral murmurs
"""
from __future__ import annotations

import numpy as np
from numpy.typing import NDArray


class ChestTransferFilter:
    """4-position auscultation filter bank using FIR filters.

    Each position has a distinct frequency response profile derived from
    idealized chest-wall transfer characteristics. Filters are designed via
    the window method (firwin2) to match target gain curves.
    """

    def __init__(self, sample_rate: int = 4000, filter_order: int = 65) -> None:
        self.sample_rate = sample_rate
        self.filter_order = filter_order
        self._build_filters()

    def list_positions(self) -> list[str]:
        """Return list of available auscultation positions."""
        return ['aortic', 'pulmonic', 'tricuspid', 'mitral']

    def _build_filters(self) -> None:
        """Build per-position FIR filters via window method.

        Each filter is designed from a target frequency response curve
        representing the acoustic transfer characteristics of the chest wall
        at that specific listening position. Gains are specified at normalized
        frequency points and interpolated by firwin2.
        """
        from scipy.signal import firwin2

        n = self.filter_order

        # Normalized frequency points (0 to Nyquist)
        freqs = np.array([0.0, 0.025, 0.05, 0.1, 0.15, 0.2, 0.3, 0.4, 0.5, 1.0])

        # --- Aortic: S2-dominant, less high-freq rolloff ---
        # Emphasizes 60-250 Hz (S2 range), mild high-freq attenuation
        # Best for hearing A2 component of S2
        aortic_gains = np.array([0.3, 0.6, 0.9, 1.0, 0.95, 0.9, 0.75, 0.5, 0.3, 0.1])
        self._aortic_fir = firwin2(n, freqs, aortic_gains)

        # --- Pulmonic: similar to aortic with more mid-high emphasis ---
        # Slightly better P2 visibility, wider A2-P2 splitting perceptible
        pulmonic_gains = np.array([0.25, 0.55, 0.85, 0.95, 1.0, 0.95, 0.8, 0.55, 0.35, 0.1])
        self._pulmonic_fir = firwin2(n, freqs, pulmonic_gains)

        # --- Tricuspid: mid-low emphasis for S1 T1 component ---
        # Emphasizes 40-150 Hz (T1 range), attenuates high frequencies more aggressively
        # Best for hearing tricuspid component of S1
        tricuspid_gains = np.array([0.35, 0.7, 1.0, 0.9, 0.7, 0.5, 0.35, 0.2, 0.12, 0.05])
        self._tricuspid_fir = firwin2(n, freqs, tricuspid_gains)

        # --- Mitral: strongest overall, broad low-mid emphasis ---
        # Best overall response for S1, also best for S3/S4 and mitral murmurs
        # Broadest passband with highest overall gain
        mitral_gains = np.array([0.4, 0.75, 1.0, 1.0, 0.9, 0.75, 0.55, 0.35, 0.2, 0.08])
        self._mitral_fir = firwin2(n, freqs, mitral_gains)

    def apply(self, signal: NDArray[np.float64], position: str) -> NDArray[np.float64]:
        """Apply chest transfer function for the given auscultation position.

        Args:
            signal: Input PCG signal (1D array).
            position: One of 'aortic', 'pulmonic', 'tricuspid', 'mitral'.

        Returns:
            Filtered signal with chest transfer characteristics applied.
        """
        from scipy.signal import lfilter

        x = np.asarray(signal, dtype=np.float64)

        fir_map = {
            'aortic': self._aortic_fir,
            'pulmonic': self._pulmonic_fir,
            'tricuspid': self._tricuspid_fir,
            'mitral': self._mitral_fir,
        }

        if position not in fir_map:
            raise ValueError(
                f"Unknown position: {position}. Available: {self.list_positions()}"
            )

        return lfilter(fir_map[position], [1.0], x)

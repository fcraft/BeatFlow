"""4-band Wide Dynamic Range Compressor (WDRC) for PCG.

Replaces the single-band AGC in ParametricPcgSynthesizer. Each band has
independent threshold, ratio, attack, and release parameters. This prevents
strong murmurs in high-frequency bands from suppressing S1/S2 energy in
low-frequency bands.

Bands:
  Band 1: 20-100 Hz   — S3/S4 low-frequency heart sounds
  Band 2: 100-250 Hz  — S1/S2 main body
  Band 3: 250-500 Hz  — High-frequency heart sounds + murmur
  Band 4: 500-800 Hz  — Respiratory sounds + friction rubs
"""
from __future__ import annotations

import numpy as np
from numpy.typing import NDArray


class BandCompressor:
    """4-band WDRC for PCG dynamic range control."""

    def __init__(
        self,
        sample_rate: int,
        crossover_freqs: list[float] | None = None,
        thresholds: list[float] | None = None,
        ratios: list[float] | None = None,
        attack_ms: float = 5.0,
        release_ms: float = 50.0,
        knee_db: float = 6.0,
        makeup_gains: list[float] | None = None,
    ) -> None:
        self.sample_rate = sample_rate

        self.crossover_freqs = crossover_freqs or [100.0, 250.0, 500.0]
        self.thresholds = thresholds or [0.08, 0.08, 0.06, 0.04]
        self.ratios = ratios or [2.0, 2.0, 3.0, 4.0]
        self.makeup_gains = makeup_gains or [1.0, 1.0, 1.2, 1.5]

        attack_samples = max(1, int(attack_ms / 1000.0 * sample_rate))
        release_samples = max(1, int(release_ms / 1000.0 * sample_rate))
        self._attack_coeff = 1.0 - np.exp(-1.0 / attack_samples)
        self._release_coeff = 1.0 - np.exp(-1.0 / release_samples)
        self._knee_db = knee_db

        self._build_crossover_filters()
        self._envelopes: list[float] = [0.0, 0.0, 0.0, 0.0]

    def _build_crossover_filters(self) -> None:
        """Build 2nd-order Butterworth crossover filters."""
        from scipy.signal import butter

        self._lp_filters: list = []
        self._hp_filters: list = []

        sr = self.sample_rate
        for fc in self.crossover_freqs:
            sos_lp = butter(2, fc, btype='low', fs=sr, output='sos')
            sos_hp = butter(2, fc, btype='high', fs=sr, output='sos')
            self._lp_filters.append(sos_lp)
            self._hp_filters.append(sos_hp)

    def split_bands(self, x: NDArray[np.float64]) -> list[NDArray[np.float64]]:
        """Split input signal into 4 frequency bands using cascaded crossover filters."""
        from scipy.signal import sosfilt

        x = np.asarray(x, dtype=np.float64)

        # Band 1: LP at fc0 (20-100 Hz)
        band1 = sosfilt(self._lp_filters[0], x)

        # Band 2: HP at fc0 → LP at fc1 (100-250 Hz)
        band2_tmp = sosfilt(self._hp_filters[0], x)
        band2 = sosfilt(self._lp_filters[1], band2_tmp)

        # Band 3: HP at fc1 → LP at fc2 (250-500 Hz)
        band3_tmp = sosfilt(self._hp_filters[1], x)
        band3 = sosfilt(self._lp_filters[2], band3_tmp)

        # Band 4: HP at fc2 (500-800 Hz)
        band4 = sosfilt(self._hp_filters[2], x)

        return [band1, band2, band3, band4]

    def _compute_gain_reduction(self, envelope: float, band_idx: int) -> float:
        """Compute gain reduction in dB for a given envelope level with soft knee."""
        if envelope < 1e-12:
            return 0.0

        level_db = 20.0 * np.log10(envelope + 1e-12)
        threshold_db = 20.0 * np.log10(self.thresholds[band_idx] + 1e-12)

        if level_db < threshold_db - self._knee_db / 2:
            return 0.0
        elif level_db > threshold_db + self._knee_db / 2:
            over = level_db - threshold_db
            return over * (1.0 - 1.0 / self.ratios[band_idx])
        else:
            over = level_db - (threshold_db - self._knee_db / 2)
            return over * over / (2.0 * self._knee_db) * (1.0 - 1.0 / self.ratios[band_idx])

    def process(self, x: NDArray[np.float64]) -> NDArray[np.float64]:
        """Apply 4-band WDRC to input signal."""
        bands = self.split_bands(x)
        output = np.zeros_like(x, dtype=np.float64)

        for i, band in enumerate(bands):
            processed = np.zeros_like(band, dtype=np.float64)

            for j in range(len(band)):
                abs_sample = abs(band[j])

                if abs_sample > self._envelopes[i]:
                    self._envelopes[i] += self._attack_coeff * (abs_sample - self._envelopes[i])
                else:
                    self._envelopes[i] += self._release_coeff * (abs_sample - self._envelopes[i])

                gr_db = self._compute_gain_reduction(self._envelopes[i], i)
                gain_linear = 10.0 ** (-gr_db / 20.0) * self.makeup_gains[i]
                processed[j] = band[j] * gain_linear

            output += processed

        return output


def design_pcg_compressor(sample_rate: int = 4000) -> BandCompressor:
    """Factory for PCG-optimized compressor with clinical defaults.

    Band thresholds and ratios tuned for heart sound preservation:
    - Lower bands (S1/S2) have milder compression to preserve dynamics
    - Higher bands (murmur/respiratory) have stronger compression
    - Makeup gains boost high bands slightly for clarity
    """
    return BandCompressor(
        sample_rate=sample_rate,
        crossover_freqs=[100.0, 250.0, 500.0],
        thresholds=[0.03, 0.04, 0.03, 0.02],
        ratios=[2.0, 2.0, 3.0, 4.0],
        attack_ms=5.0,
        release_ms=50.0,
        knee_db=6.0,
        makeup_gains=[1.0, 1.0, 1.2, 1.5],
    )

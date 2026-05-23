"""Individual variability parameters for ECG synthesis.

Generates random (but reproducible via seed) physiological variation parameters
that make each virtual human's ECG unique.  These are applied during VCG
construction and the VCG→ECG projection in EcgSynthesizerV2.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class MorphVarianceConfig:
    """Individual ECG variability parameters.

    All parameters are generated randomly at initialization (with optional seed
    for reproducibility).  They are stored in the virtual human profile so the
    same person always produces the same ECG.

    Attributes:
        cardiac_axis_deg: Electrical axis in frontal plane (degrees).
            Normal range -30° to +90°; μ=45°, σ=25°.
        chest_wall_thickness: Multiplier for lead amplitudes.
            1.0 = normal; <1.0 = thin (higher amplitudes); >1.0 = thick (lower).
        heart_rotation: Z-axis rotation of the heart.
            <0 = clockwise; 0 = normal; >0 = counterclockwise.
            Affects R-wave transition in precordial leads (V2→V4).
        age_years: Age of the virtual human (18-80).
        sex: 'M' or 'F'.
        age_r_wave_attenuation: R-wave amplitude reduction from aging (0.0-1.0).
        age_t_wave_attenuation: T-wave amplitude reduction from aging (0.0-1.0).
        age_axis_left_shift: Leftward axis shift from aging (degrees).
    """
    cardiac_axis_deg: float = 45.0
    chest_wall_thickness: float = 1.0
    heart_rotation: float = 0.0
    age_years: int = 35
    sex: str = 'M'

    # Derived age effects (computed automatically)
    age_r_wave_attenuation: float = 0.0
    age_t_wave_attenuation: float = 0.0
    age_axis_left_shift: float = 0.0

    def __post_init__(self) -> None:
        self._compute_age_effects()

    def _compute_age_effects(self) -> None:
        """Compute age-related ECG changes.

        R-wave amplitude: decreases ~1% per year after age 30
        T-wave amplitude: decreases ~0.5% per year after age 30
        QRS axis: shifts left ~0.3° per year after age 40
        """
        if self.age_years > 30:
            years_over = self.age_years - 30
            self.age_r_wave_attenuation = min(0.5, years_over * 0.01)
            self.age_t_wave_attenuation = min(0.35, years_over * 0.005)
        if self.age_years > 40:
            self.age_axis_left_shift = (self.age_years - 40) * 0.3

    def get_axis_rotation_matrix(self) -> np.ndarray:
        """Return 3×3 rotation matrix for cardiac axis in frontal plane (XY).

        Only the frontal plane components (X, Y) are rotated; Z is unaffected.
        Rotation = cardiac_axis_deg - 45° (deviation from nominal 45°).
        """
        delta = np.radians(self.cardiac_axis_deg - 45.0)
        cos_d = np.cos(delta)
        sin_d = np.sin(delta)
        return np.array([
            [cos_d, -sin_d, 0.0],
            [sin_d,  cos_d, 0.0],
            [0.0,    0.0,   1.0],
        ], dtype=np.float64)

    def get_z_rotation_matrix(self) -> np.ndarray:
        """Return 3×3 rotation matrix for heart rotation about Z axis.

        Affects precordial lead R-wave progression.
        heart_rotation < 0 → clockwise → delayed transition
        heart_rotation > 0 → counterclockwise → early transition
        """
        angle = np.radians(self.heart_rotation * 15.0)  # ±15° max
        cos_a = np.cos(angle)
        sin_a = np.sin(angle)
        return np.array([
            [cos_a, -sin_a, 0.0],
            [sin_a,  cos_a, 0.0],
            [0.0,    0.0,   1.0],
        ], dtype=np.float64)

    def get_amplitude_scale(self) -> float:
        """Overall amplitude scaling factor.

        Combines chest wall thickness and sex:
          - Thinner chest → higher amplitudes
          - Male → slightly higher amplitudes
        """
        # Chest wall: thicker → more attenuation → lower scale
        chest_factor = 1.0 / self.chest_wall_thickness

        # Sex: males have ~10% higher QRS amplitudes
        sex_factor = 1.05 if self.sex == 'M' else 0.95

        return chest_factor * sex_factor

    def get_r_wave_scale(self) -> float:
        """R-wave amplitude scaling including age attenuation."""
        return max(0.5, 1.0 - self.age_r_wave_attenuation)

    def get_t_wave_scale(self) -> float:
        """T-wave amplitude scaling including age attenuation."""
        return max(0.65, 1.0 - self.age_t_wave_attenuation)

    def get_effective_axis(self) -> float:
        """Get effective cardiac axis including age-related left shift."""
        return self.cardiac_axis_deg - self.age_axis_left_shift


def generate_random_variance(seed: int | None = None) -> MorphVarianceConfig:
    """Generate a random individual variability profile.

    Uses a normal distribution for continuous parameters within physiological
    ranges.  The seed allows reproducible random generation (useful for tests).

    Args:
        seed: Optional random seed for reproducibility.

    Returns:
        A MorphVarianceConfig with randomly sampled parameters.
    """
    rng = np.random.default_rng(seed)

    # Cardiac axis: normal distribution μ=45°, σ=25°, clipped to [-30, +90]
    axis = rng.normal(45.0, 25.0)
    axis = max(-30.0, min(90.0, axis))

    # Chest wall thickness: log-normal-ish, median ~1.0, range [0.7, 1.5]
    chest = rng.normal(1.0, 0.2)
    chest = max(0.7, min(1.5, chest))

    # Heart rotation: normal distribution, clipped to [-1, +1]
    rotation = rng.normal(0.0, 0.35)
    rotation = max(-1.0, min(1.0, rotation))

    # Age: roughly uniform-ish between 18-80, skewed toward middle
    age = int(rng.normal(45, 18))
    age = max(18, min(80, age))

    # Sex: roughly 50/50
    sex = 'M' if rng.random() < 0.5 else 'F'

    return MorphVarianceConfig(
        cardiac_axis_deg=round(axis, 1),
        chest_wall_thickness=round(chest, 2),
        heart_rotation=round(rotation, 2),
        age_years=age,
        sex=sex,
    )

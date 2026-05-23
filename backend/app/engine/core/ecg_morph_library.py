"""Pathological ECG morphology library for VCG-based synthesis.

Each morphology config describes modifications to the standard VCG Gaussian
basis functions used in EcgSynthesizerV2._build_sinus_vcg().  The config is
applied as a post-processing overlay: the normal VCG is built first, then
the morphology's modifications are added/substituted.

Supported morphologies (8):
  lbbb           — Left Bundle Branch Block
  rbbb           — Right Bundle Branch Block
  wpw            — Wolff-Parkinson-White (delta wave)
  brugada_type1  — Brugada Type 1 (coved ST elevation V1-V3)
  brugada_type2  — Brugada Type 2 (saddleback ST elevation V1-V3)
  wellens        — Wellens syndrome (biphasic/deep inverted T V2-V3)
  hyperkalemia   — Tall peaked T, low P, wide QRS
  hypokalemia    — Flat T, prominent U, ST depression
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PWaveOverride:
    """P-wave Gaussian modifications per VCG component."""
    x_amplitudes: list[float] | None = None   # Override amplitude for each X gaussian
    y_amplitudes: list[float] | None = None
    z_amplitudes: list[float] | None = None
    x_sigmas: list[float] | None = None
    y_sigmas: list[float] | None = None
    z_sigmas: list[float] | None = None
    vcg_scale: float = 1.0                    # Additional scale factor after modification


@dataclass
class QRSOverride:
    """QRS Gaussian modifications per VCG component.

    Each list corresponds to the sequence of Gaussians used in _build_sinus_vcg:
      X: [septal_q, main_R, small_s]
      Y: [Q_wave, R_wave, S_wave]
      Z: [septal_r, free_wall_S, terminal]

    Additional Gaussians can be appended via extra_* lists for features like
    delta waves (WPW) or R' (RBBB).
    """
    x_amplitudes: list[float] | None = None
    y_amplitudes: list[float] | None = None
    z_amplitudes: list[float] | None = None
    x_sigmas: list[float] | None = None
    y_sigmas: list[float] | None = None
    z_sigmas: list[float] | None = None
    x_timing_offsets: list[float] | None = None  # Time offset per gaussian (seconds)
    y_timing_offsets: list[float] | None = None
    z_timing_offsets: list[float] | None = None

    # Extra Gaussians appended after the standard ones
    x_extra_amps: list[float] = field(default_factory=list)
    x_extra_sigmas: list[float] = field(default_factory=list)
    x_extra_timing: list[float] = field(default_factory=list)
    y_extra_amps: list[float] = field(default_factory=list)
    y_extra_sigmas: list[float] = field(default_factory=list)
    y_extra_timing: list[float] = field(default_factory=list)
    z_extra_amps: list[float] = field(default_factory=list)
    z_extra_sigmas: list[float] = field(default_factory=list)
    z_extra_timing: list[float] = field(default_factory=list)

    vcg_scale: float = 1.0


@dataclass
class TWaveOverride:
    """T-wave Gaussian modifications per VCG component."""
    x_amplitude: float | None = None
    y_amplitude: float | None = None
    z_amplitude: float | None = None
    x_tail_amp: float | None = None
    y_tail_amp: float | None = None
    z_tail_amp: float | None = None
    t_sigma: float | None = None
    # Secondary T-wave (for biphasic T in Wellens)
    x_amp2: float | None = None
    y_amp2: float | None = None
    z_amp2: float | None = None
    t_offset2: float | None = None
    vcg_scale: float = 1.0


@dataclass
class STOverride:
    """ST segment modifications."""
    x_depression: float = 0.0    # Negative = depression, positive = elevation (mV)
    y_depression: float = 0.0
    z_depression: float = 0.0
    st_sigma: float | None = None


@dataclass
class PathologicalMorphConfig:
    """Complete pathological morphology configuration."""
    name: str
    description: str
    p_wave: PWaveOverride | None = None
    qrs: QRSOverride | None = None
    st_segment: STOverride | None = None
    t_wave: TWaveOverride | None = None
    applicable_leads: list[str] | None = None  # Which leads are most affected


# =========================================================================
# Morphology definitions
# =========================================================================

MORPH_LIBRARY: dict[str, PathologicalMorphConfig] = {
    # ------------------------------------------------------------------
    "lbbb": PathologicalMorphConfig(
        name="lbbb",
        description="Left Bundle Branch Block — wide QRS ≥120ms, absent septal q in I/aVL/V5-V6, deep S in V1-V3",
        qrs=QRSOverride(
            # X: septal q abolished, main R widened and notched
            x_amplitudes=[0.0, 0.70, -0.05],
            x_sigmas=[0.004, 0.015, 0.008],
            x_timing_offsets=[0.0, 0.010, 0.040],
            x_extra_amps=[0.20],
            x_extra_sigmas=[0.012],
            x_extra_timing=[0.025],
            # Y: Q wave reduced, R wide, deep S
            y_amplitudes=[-0.03, 1.10, -0.35],
            y_sigmas=[0.005, 0.014, 0.012],
            y_timing_offsets=[0.0, 0.008, 0.030],
            # Z: septal r tiny, deep wide S, absent terminal r
            z_amplitudes=[0.05, -0.90, 0.02],
            z_sigmas=[0.004, 0.018, 0.005],
            vcg_scale=1.0,
        ),
        t_wave=TWaveOverride(
            # Discordant T: inverted in leads with dominant R
            x_amplitude=-0.20, y_amplitude=-0.30, z_amplitude=0.12,
            vcg_scale=1.0,
        ),
        applicable_leads=["I", "aVL", "V1", "V2", "V3", "V5", "V6"],
    ),

    # ------------------------------------------------------------------
    "rbbb": PathologicalMorphConfig(
        name="rbbb",
        description="Right Bundle Branch Block — wide QRS with terminal R' in V1 (rSR' pattern), wide S in I/aVL/V6",
        qrs=QRSOverride(
            # X: normal initial, wider terminal S
            x_amplitudes=[-0.08, 0.85, -0.20],
            x_sigmas=[0.004, 0.006, 0.010],
            x_timing_offsets=[0.0, 0.0, 0.008],
            # Y: wide terminal S
            y_amplitudes=[-0.10, 1.10, -0.25],
            y_sigmas=[0.005, 0.005, 0.010],
            y_timing_offsets=[0.0, 0.0, 0.008],
            # Z: R' added (positive terminal deflection → tall R' in V1)
            z_amplitudes=[0.35, -0.65, 0.05],
            z_sigmas=[0.004, 0.008, 0.004],
            z_timing_offsets=[0.0, 0.0, 0.0],
            z_extra_amps=[0.55],
            z_extra_sigmas=[0.008],
            z_extra_timing=[0.025],
            vcg_scale=1.0,
        ),
        t_wave=TWaveOverride(
            z_amplitude=0.08,  # T-wave inversion in V1-V3 via Z component
            vcg_scale=1.0,
        ),
        applicable_leads=["V1", "V2", "V3", "I", "aVL", "V6"],
    ),

    # ------------------------------------------------------------------
    "wpw": PathologicalMorphConfig(
        name="wpw",
        description="Wolff-Parkinson-White — delta wave (slurred QRS upstroke), short PR, wide QRS",
        p_wave=PWaveOverride(
            # Short PR = P wave closer to QRS (reduced P-QRS gap simulated
            # by shifting P wave later — handled in synthesizer integration)
            vcg_scale=1.0,
        ),
        qrs=QRSOverride(
            # Delta wave: early slow depolarisation via accessory pathway
            # Added as an early wide Gaussian before the normal QRS
            x_extra_amps=[0.25],
            x_extra_sigmas=[0.012],
            x_extra_timing=[-0.012],  # BEFORE standard QRS onset
            y_extra_amps=[0.30],
            y_extra_sigmas=[0.012],
            y_extra_timing=[-0.012],
            z_extra_amps=[0.15],
            z_extra_sigmas=[0.012],
            z_extra_timing=[-0.012],
            # Slightly wider main QRS
            x_sigmas=[0.005, 0.007, 0.006],
            y_sigmas=[0.006, 0.006, 0.006],
            vcg_scale=1.0,
        ),
        t_wave=TWaveOverride(
            # Discordant T-wave
            y_amplitude=-0.15, vcg_scale=1.0,
        ),
        applicable_leads=["I", "II", "aVL", "V1", "V2", "V5", "V6"],
    ),

    # ------------------------------------------------------------------
    "brugada_type1": PathologicalMorphConfig(
        name="brugada_type1",
        description="Brugada Type 1 — coved ST elevation ≥2mm in V1-V3, T-wave inversion",
        qrs=QRSOverride(
            # Z: enhanced terminal forces
            z_amplitudes=[0.30, -0.75, 0.15],
        ),
        st_segment=STOverride(
            # ST elevation via Z component (affects anterior precordial leads)
            z_depression=0.60,   # Positive = elevation in V1-V3
            st_sigma=0.030,
        ),
        t_wave=TWaveOverride(
            z_amplitude=0.15,    # Inverted T in V1-V3 (Z positive → V1 positive → inverted T)
            y_amplitude=0.20,
            vcg_scale=1.0,
        ),
        applicable_leads=["V1", "V2", "V3"],
    ),

    # ------------------------------------------------------------------
    "brugada_type2": PathologicalMorphConfig(
        name="brugada_type2",
        description="Brugada Type 2 — saddleback ST elevation ≥1mm in V1-V3",
        qrs=QRSOverride(
            z_amplitudes=[0.30, -0.75, 0.15],
        ),
        st_segment=STOverride(
            z_depression=0.30,    # Less elevation than Type 1
            st_sigma=0.035,
        ),
        t_wave=TWaveOverride(
            z_amplitude=0.08,     # Biphasic or upright T
            y_amplitude=0.22,
            vcg_scale=1.0,
        ),
        applicable_leads=["V1", "V2", "V3"],
    ),

    # ------------------------------------------------------------------
    "wellens": PathologicalMorphConfig(
        name="wellens",
        description="Wellens syndrome — biphasic or deeply inverted T waves in V2-V3, indicative of proximal LAD stenosis",
        t_wave=TWaveOverride(
            # Deeply inverted T in anterior leads (via Z and Y)
            z_amplitude=0.18,      # Positive Z → inverted T in V1-V3
            y_amplitude=-0.08,      # Reduced Y T amplitude
            z_tail_amp=0.06,
            # Biphasic component
            z_amp2=-0.12,
            t_offset2=0.100,
            t_sigma=0.050,
            vcg_scale=1.0,
        ),
        st_segment=STOverride(
            z_depression=-0.10,    # Mild ST depression or flat
            y_depression=-0.05,
        ),
        applicable_leads=["V2", "V3"],
    ),

    # ------------------------------------------------------------------
    "hyperkalemia": PathologicalMorphConfig(
        name="hyperkalemia",
        description="Hyperkalemia — tall peaked T waves (tented), low/flat P waves, wide QRS, shortened QT",
        p_wave=PWaveOverride(
            x_amplitudes=[0.03, 0.01],
            y_amplitudes=[0.04, 0.01],
            z_amplitudes=[0.02, -0.01],
            vcg_scale=0.4,           # Low amplitude P
        ),
        qrs=QRSOverride(
            # Wide QRS
            x_sigmas=[0.006, 0.010, 0.008],
            y_sigmas=[0.007, 0.008, 0.008],
            z_sigmas=[0.006, 0.012, 0.007],
            vcg_scale=1.0,
        ),
        t_wave=TWaveOverride(
            # Tall, narrow, peaked T (tented)
            y_amplitude=0.55,
            x_amplitude=0.35,
            z_amplitude=-0.25,
            t_sigma=0.025,           # Narrower T
            vcg_scale=1.0,
        ),
        applicable_leads=["II", "III", "aVF", "V2", "V3", "V4", "V5", "V6"],
    ),

    # ------------------------------------------------------------------
    "hypokalemia": PathologicalMorphConfig(
        name="hypokalemia",
        description="Hypokalemia — flat/broad T waves, prominent U waves, ST depression, prolonged QT",
        t_wave=TWaveOverride(
            y_amplitude=0.08,        # Flat T
            x_amplitude=0.05,
            z_amplitude=-0.03,
            t_sigma=0.065,           # Broader T
            y_tail_amp=0.02,
            vcg_scale=1.0,
        ),
        st_segment=STOverride(
            y_depression=-0.08,      # ST depression
            z_depression=-0.05,
            st_sigma=0.040,
        ),
        applicable_leads=["II", "III", "aVF", "V4", "V5", "V6"],
    ),
}


def get_morph_config(name: str) -> PathologicalMorphConfig | None:
    """Retrieve a morphology config by name. Returns None if not found."""
    return MORPH_LIBRARY.get(name)


def list_morphologies() -> list[str]:
    """Return list of available morphology names."""
    return sorted(MORPH_LIBRARY.keys())

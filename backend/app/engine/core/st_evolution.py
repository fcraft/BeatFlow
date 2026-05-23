"""ST segment evolution model for myocardial infarction progression.

Tracks ST/T/Q changes through four phases of STEMI:
  Hyperacute → Acute → Subacute → Old

Evolution speed is modulated by coronary_stenosis (0.0-1.0), where higher
values accelerate progression through the phases.
"""
from __future__ import annotations

from dataclasses import dataclass
import time


@dataclass
class STEvolutionState:
    """Current ST/T/Q state at a given point in the MI timeline."""
    phase: str                    # 'hyperacute' | 'acute' | 'subacute' | 'old'
    elapsed_minutes: float        # Minutes since MI onset
    st_elevation_mv: float        # ST elevation in mV (positive = elevation)
    t_wave_amplitude_factor: float  # Multiplier on T-wave amplitude (>1 = taller)
    t_wave_inversion: float       # 0.0 = upright, 1.0 = fully inverted
    q_wave_depth_factor: float    # 0.0 = no Q, 1.0 = pathological Q
    r_wave_reduction: float       # 0.0 = normal R, 1.0 = R wave lost
    description: str              # Human-readable phase description


class STEvolutionModel:
    """Time-dependent ST segment evolution for myocardial infarction.

    Models the complete STEMI timeline from hyperacute through old/chronic phases.
    The model is driven by elapsed time and modulated by coronary stenosis severity.

    Usage:
        model = STEvolutionModel(coronary_stenosis=0.7)
        model.start()  # Begin MI timeline

        # Each beat:
        state = model.update(dt_seconds=0.8)
        # Apply state.st_elevation_mv, state.t_wave_inversion, etc. to VCG

        # If coronary flow is restored:
        model.resolve()  # ST returns to baseline immediately
    """

    # Phase transition thresholds (minutes, scaled by stenosis)
    _DEFAULT_TRANSITIONS: dict[str, tuple[float, float]] = {
        # phase: (start_min, end_min) at stenosis=0.5
        'hyperacute': (0.0, 30.0),
        'acute': (30.0, 360.0),       # 6 hours
        'subacute': (360.0, 4320.0),  # 72 hours
        'old': (4320.0, float('inf')),
    }

    def __init__(self, coronary_stenosis: float = 0.5) -> None:
        self.coronary_stenosis = max(0.0, min(1.0, coronary_stenosis))
        self._elapsed_minutes: float = 0.0
        self._active: bool = False
        self._start_time: float | None = None
        self._resolved: bool = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def elapsed_minutes(self) -> float:
        return self._elapsed_minutes

    @property
    def active(self) -> bool:
        return self._active and not self._resolved

    def start(self) -> None:
        """Begin the MI timeline."""
        self._active = True
        self._resolved = False
        self._elapsed_minutes = 0.0
        self._start_time = time.time()

    def resolve(self) -> None:
        """Resolve ST elevation (reperfusion). ST returns to baseline."""
        self._resolved = True

    def restart(self) -> None:
        """Re-start MI after resolution (re-occlusion)."""
        self.start()

    @property
    def stenosis(self) -> float:
        return self.coronary_stenosis

    @stenosis.setter
    def stenosis(self, value: float) -> None:
        self.coronary_stenosis = max(0.0, min(1.0, value))

    def update(self, dt_seconds: float) -> STEvolutionState:
        """Advance the model by dt_seconds and return current state."""
        if not self._active:
            return self._inactive_state()

        if self._resolved:
            return self._resolved_state()

        self._elapsed_minutes += dt_seconds / 60.0
        return self._compute_state()

    def get_current_state(self) -> STEvolutionState:
        """Return current state without advancing time."""
        if not self._active:
            return self._inactive_state()
        if self._resolved:
            return self._resolved_state()
        return self._compute_state()

    # ------------------------------------------------------------------
    # Internal state computation
    # ------------------------------------------------------------------

    def _get_effective_minutes(self) -> float:
        """Scale elapsed time by stenosis factor.

        At stenosis=0.5, time passes at 1× rate.
        At stenosis=0.9, time passes at 3× rate (severe stenosis → fast progression).
        At stenosis=0.2, time passes at 0.3× rate (mild stenosis → slow progression).
        """
        # Rate multiplier: maps stenosis [0,1] to rate [0.1, 5.0]
        # stenosis=0.5 → rate=1.0 (normal)
        # stenosis=0.0 → rate=0.1 (very slow)
        # stenosis=1.0 → rate=5.0 (very fast)
        rate = 0.1 + 4.9 * self.coronary_stenosis
        return self._elapsed_minutes * rate

    def _compute_state(self) -> STEvolutionState:
        """Compute ST/T/Q state from effective elapsed time."""
        eff_min = self._get_effective_minutes()

        if eff_min < 30.0:
            return self._hyperacute_state(eff_min)
        elif eff_min < 360.0:
            return self._acute_state(eff_min)
        elif eff_min < 4320.0:
            return self._subacute_state(eff_min)
        else:
            return self._old_state(eff_min)

    def _hyperacute_state(self, eff_min: float) -> STEvolutionState:
        """0-30 min: Tall T-waves, minimal ST change."""
        progress = eff_min / 30.0  # 0→1 across phase

        return STEvolutionState(
            phase='hyperacute',
            elapsed_minutes=self._elapsed_minutes,
            st_elevation_mv=0.02 + 0.08 * progress,   # Subtle ST rise
            t_wave_amplitude_factor=1.0 + 0.8 * progress,  # T-waves grow tall
            t_wave_inversion=0.0,                       # Still upright
            q_wave_depth_factor=0.0,                    # No Q waves yet
            r_wave_reduction=0.0,
            description=f'Hyperacute STEMI ({self._elapsed_minutes:.0f} min)',
        )

    def _acute_state(self, eff_min: float) -> STEvolutionState:
        """30 min - 6 h: ST elevation, T-wave inverting."""
        phase_min = eff_min - 30.0
        phase_dur = 360.0 - 30.0  # 330 min
        progress = min(1.0, phase_min / phase_dur)

        # ST elevation peaks mid-acute phase then begins to decline
        st_magnitude = 0.15 + 0.25 * (1.0 - abs(2.0 * (progress - 0.5)))

        return STEvolutionState(
            phase='acute',
            elapsed_minutes=self._elapsed_minutes,
            st_elevation_mv=st_magnitude,
            t_wave_amplitude_factor=1.0 - 0.3 * progress,
            t_wave_inversion=0.1 + 0.6 * progress,     # Progressively inverting
            q_wave_depth_factor=0.0 + 0.2 * progress,   # Q waves begin
            r_wave_reduction=0.0 + 0.1 * progress,
            description=f'Acute STEMI ({self._elapsed_minutes / 60:.1f} h)',
        )

    def _subacute_state(self, eff_min: float) -> STEvolutionState:
        """6-72 h: ST returning to baseline, deep T inversion, Q waves."""
        phase_min = eff_min - 360.0
        phase_dur = 4320.0 - 360.0
        progress = min(1.0, phase_min / phase_dur)

        return STEvolutionState(
            phase='subacute',
            elapsed_minutes=self._elapsed_minutes,
            st_elevation_mv=0.15 * (1.0 - progress),    # ST falls
            t_wave_amplitude_factor=0.8 + 0.3 * progress,
            t_wave_inversion=0.7 + 0.3 * progress,       # Deep inversion
            q_wave_depth_factor=0.2 + 0.8 * progress,    # Pathological Q
            r_wave_reduction=0.1 + 0.4 * progress,       # R wave loss
            description=f'Subacute STEMI ({self._elapsed_minutes / 60:.0f} h)',
        )

    def _old_state(self, eff_min: float) -> STEvolutionState:
        """>72 h: ST at baseline, possible permanent T inversion, Q waves."""
        hours_since = (eff_min - 4320.0) / 60.0
        chronicity = min(1.0, hours_since / (30 * 24))  # 0→1 over 30 days post-MI

        return STEvolutionState(
            phase='old',
            elapsed_minutes=self._elapsed_minutes,
            st_elevation_mv=0.0,                         # ST back to baseline
            t_wave_amplitude_factor=0.7 + 0.2 * chronicity,
            t_wave_inversion=max(0.2, 1.0 - 0.5 * chronicity),  # May normalize
            q_wave_depth_factor=1.0,                     # Permanent Q
            r_wave_reduction=0.3 + 0.3 * chronicity,      # Some R may return
            description=f'Old MI ({self._elapsed_minutes / 60:.0f} h)',
        )

    def _inactive_state(self) -> STEvolutionState:
        return STEvolutionState(
            phase='none',
            elapsed_minutes=0.0,
            st_elevation_mv=0.0,
            t_wave_amplitude_factor=1.0,
            t_wave_inversion=0.0,
            q_wave_depth_factor=0.0,
            r_wave_reduction=0.0,
            description='No active MI',
        )

    def _resolved_state(self) -> STEvolutionState:
        """Post-reperfusion: ST normalized but Q/T may persist."""
        eff_min = self._get_effective_minutes()
        if eff_min < 360.0:
            qi = 0.0 + 0.2 * (eff_min / 360.0)
            ti = 0.1 + 0.3 * (eff_min / 360.0)
        else:
            qi = 0.2 + 0.3 * min(1.0, (eff_min - 360.0) / 3960.0)
            ti = 0.4 + 0.3 * min(1.0, (eff_min - 360.0) / 3960.0)

        return STEvolutionState(
            phase='resolved',
            elapsed_minutes=self._elapsed_minutes,
            st_elevation_mv=0.0,        # ST normalized by reperfusion
            t_wave_amplitude_factor=1.0,
            t_wave_inversion=ti,        # Some T changes may persist
            q_wave_depth_factor=qi,     # Q may have already formed
            r_wave_reduction=0.05,
            description='Reperfused (ST resolved)',
        )

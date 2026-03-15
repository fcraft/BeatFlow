"""Respiratory mechanics model for the V2 physics pipeline.

Implements:
- Sinusoidal intrathoracic pressure cycle (frequency driven by chemoreceptors)
- Tidal volume / minute ventilation computation
- Respiratory phase output for RSA (respiratory sinus arrhythmia)
- Chemoreceptor drive: PaCO2/PaO2 → respiratory rate and tidal volume
- Integration with GasExchangeModel for closed-loop blood gas feedback

Design: per-beat update for real-time performance (<0.5ms per beat).

Reference physiology:
- Normal RR: 12-20 breaths/min
- Normal Vt: 500 mL (6-8 mL/kg for 70kg)
- Normal MV: 6-8 L/min
- Intrathoracic pressure: -4 to -8 cmH2O (normal breathing)
  Converted to mmHg: -3 to -6 mmHg
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from app.engine.respiratory.gas_exchange import BloodGasState, GasExchangeModel


@dataclass
class RespiratoryState:
    """Complete respiratory system output for one beat."""
    respiratory_phase: float = 0.0          # [0, 2*pi]
    intrathoracic_pressure: float = -5.0    # mmHg (normal -3 to -6)
    tidal_volume_ml: float = 500.0          # mL
    minute_ventilation: float = 7.0         # L/min
    respiratory_rate: float = 14.0          # breaths/min
    pao2: float = 95.0                      # mmHg
    paco2: float = 40.0                     # mmHg
    sao2: float = 97.5                      # %
    ph: float = 7.40
    fio2: float = 0.21
    spo2_physical: float = 97.5             # SpO2 from O2-Hb curve


class RespiratoryModel:
    """Respiratory mechanics with chemoreceptor feedback.

    The model maintains a breathing cycle phase that advances each beat
    based on the current respiratory rate. The respiratory rate is
    modulated by:
    1. Chemoreceptor drive (PaCO2, PaO2, pH)
    2. Autonomic tone (sympathetic ↑ RR, parasympathetic ↓ RR)
    3. Exercise metabolic demand
    4. Mechanical ventilation override

    Intrathoracic pressure follows a sinusoidal pattern, affecting
    venous return (preload) and cardiac output.
    """

    # ---- Baseline respiratory parameters ----
    BASE_RR: float = 14.0                 # breaths/min
    BASE_VT: float = 500.0                # mL
    BASE_ITP_MEAN: float = -5.0           # mmHg (mean intrathoracic pressure)
    BASE_ITP_AMPLITUDE: float = 0.8       # mmHg — reduced from 2.0 to attenuate
                                          # audible respiratory modulation of PCG
                                          # (ITP → dp/dt → S1/S2 amplitude chain)

    # ---- Chemoreceptor drive parameters ----
    # PaCO2 drive: central chemoreceptor (most potent stimulus)
    CHEMO_CO2_GAIN: float = 0.5           # RR increase per mmHg above 40
    CHEMO_CO2_THRESHOLD: float = 35.0     # mmHg (below this, minimal drive)
    CHEMO_CO2_SETPOINT: float = 40.0      # Normal PaCO2

    # PaO2 drive: peripheral chemoreceptor (carotid body)
    CHEMO_O2_GAIN: float = 0.3            # RR increase factor per mmHg below 60
    CHEMO_O2_THRESHOLD: float = 60.0      # mmHg (hypoxic drive kicks in)

    # pH drive: both central and peripheral
    CHEMO_PH_GAIN: float = 20.0           # RR change per pH unit deviation

    # ---- Tidal volume modulation ----
    VT_CO2_GAIN: float = 15.0             # mL increase per mmHg PaCO2 above 40
    VT_EXERCISE_GAIN: float = 800.0       # mL increase at max exercise
    VT_MAX: float = 3000.0                # mL (max ~forced vital capacity)
    VT_MIN: float = 150.0                 # mL (dead space)

    # ---- ITP modulation ----
    ITP_EXERCISE_AMP: float = 2.0         # mmHg — reduced from 4.0 (exercise ITP swing)
    ITP_DEEP_BREATH_AMP: float = 6.0      # mmHg (e.g. COPD, labored breathing)

    # ---- Rate limits ----
    RR_MIN: float = 4.0                   # breaths/min
    RR_MAX: float = 45.0                  # breaths/min
    RR_TAU: float = 6.0                   # beats for 63% adaptation

    # ---- Dynamics ----
    VT_TAU: float = 4.0                   # beats for tidal volume adaptation

    def __init__(self) -> None:
        # Breathing cycle phase [0, 2*pi]
        self._phase: float = 0.0

        # Current smoothed respiratory rate
        self._rr: float = self.BASE_RR

        # Current smoothed tidal volume
        self._vt: float = self.BASE_VT

        # Gas exchange sub-model
        self._gas_exchange = GasExchangeModel()

        # Cumulative time tracker (seconds)
        self._total_time_sec: float = 0.0

    @property
    def gas_exchange(self) -> GasExchangeModel:
        """Access to the gas exchange sub-model."""
        return self._gas_exchange

    @property
    def current_rr(self) -> float:
        return self._rr

    @property
    def current_phase(self) -> float:
        return self._phase

    def get_state(self) -> dict[str, Any]:
        """Serialize state for snapshot persistence."""
        return {
            "phase": self._phase,
            "rr": self._rr,
            "vt": self._vt,
            "total_time_sec": self._total_time_sec,
            "gas_exchange": self._gas_exchange.get_state_dict(),
        }

    def set_state(self, state: dict[str, Any]) -> None:
        """Restore from snapshot."""
        self._phase = state.get("phase", 0.0)
        self._rr = state.get("rr", self.BASE_RR)
        self._vt = state.get("vt", self.BASE_VT)
        self._total_time_sec = state.get("total_time_sec", 0.0)
        if "gas_exchange" in state:
            self._gas_exchange.set_state_dict(state["gas_exchange"])

    # ------------------------------------------------------------------
    # Core update (called once per beat by pipeline)
    # ------------------------------------------------------------------

    def update(
        self,
        rr_sec: float,
        sympathetic_tone: float = 0.5,
        parasympathetic_tone: float = 0.5,
        exercise_intensity: float = 0.0,
        fio2: float = 0.21,
        mechanical_ventilation: bool = False,
        cardiac_output: float = 5.0,
        metabolic_rate: float = 1.0,
    ) -> RespiratoryState:
        """Update respiratory state for one beat.

        Args:
            rr_sec: Current RR interval (seconds) — for phase advancement
            sympathetic_tone: [0, 1]
            parasympathetic_tone: [0, 1]
            exercise_intensity: [0, 1]
            fio2: Fraction of inspired O2 (0.21 = room air)
            mechanical_ventilation: If True, RR/Vt set to fixed values
            cardiac_output: Current cardiac output (L/min)
            metabolic_rate: Metabolic rate multiplier (exercise → higher)

        Returns:
            RespiratoryState with all respiratory parameters
        """
        # Get current blood gas state for chemoreceptor feedback
        bg = self._gas_exchange.state

        # ---- Compute target respiratory rate ----
        if mechanical_ventilation:
            rr_target = 14.0  # Fixed ventilator rate
            vt_target = 500.0
        else:
            rr_target = self._compute_rr_target(
                bg, sympathetic_tone, parasympathetic_tone, exercise_intensity,
            )
            vt_target = self._compute_vt_target(bg, exercise_intensity)

        # ---- Smooth RR and Vt (first-order lag) ----
        alpha_rr = 1.0 / self.RR_TAU
        alpha_vt = 1.0 / self.VT_TAU

        self._rr += alpha_rr * (rr_target - self._rr)
        self._rr = max(self.RR_MIN, min(self.RR_MAX, self._rr))

        self._vt += alpha_vt * (vt_target - self._vt)
        self._vt = max(self.VT_MIN, min(self.VT_MAX, self._vt))

        # ---- Advance breathing phase ----
        # Phase advance per beat = 2*pi * (RR/60) * rr_sec
        breath_freq_hz = self._rr / 60.0
        phase_advance = 2.0 * math.pi * breath_freq_hz * rr_sec
        self._phase = (self._phase + phase_advance) % (2.0 * math.pi)

        # ---- Compute intrathoracic pressure ----
        itp = self._compute_itp(exercise_intensity)

        # ---- Compute minute ventilation ----
        mv = self._rr * self._vt / 1000.0  # L/min

        # ---- Metabolic rate from exercise ----
        effective_metabolic_rate = metabolic_rate
        if exercise_intensity > 0.01:
            # VO2 increases ~linearly with exercise intensity
            # Max VO2 ~= 3-5x resting
            effective_metabolic_rate = max(metabolic_rate, 1.0 + 4.0 * exercise_intensity)

        # ---- Update gas exchange ----
        bg = self._gas_exchange.update(
            minute_ventilation=mv,
            fio2=fio2,
            cardiac_output=cardiac_output,
            metabolic_rate=effective_metabolic_rate,
            mechanical_ventilation=mechanical_ventilation,
        )

        # ---- SpO2 from physical model ----
        spo2 = GasExchangeModel.sao2_to_spo2(bg.sao2)

        # Track time
        self._total_time_sec += rr_sec

        return RespiratoryState(
            respiratory_phase=self._phase,
            intrathoracic_pressure=itp,
            tidal_volume_ml=self._vt,
            minute_ventilation=mv,
            respiratory_rate=self._rr,
            pao2=bg.pao2,
            paco2=bg.paco2,
            sao2=bg.sao2,
            ph=bg.ph,
            fio2=fio2,
            spo2_physical=spo2,
        )

    # ------------------------------------------------------------------
    # Internal computations
    # ------------------------------------------------------------------

    def _compute_rr_target(
        self,
        bg: BloodGasState,
        sympathetic_tone: float,
        parasympathetic_tone: float,
        exercise_intensity: float,
    ) -> float:
        """Compute target RR from chemoreceptor drive + ANS + exercise.

        Chemoreceptor drive hierarchy:
        1. PaCO2 (central chemoreceptor) — most potent
        2. PaO2 (peripheral chemoreceptor) — kicks in when PaO2 < 60
        3. pH (both central and peripheral)
        """
        rr = self.BASE_RR

        # ---- CO2 drive (central chemoreceptor) ----
        # Linear increase above setpoint, mild decrease below threshold
        co2_delta = bg.paco2 - self.CHEMO_CO2_SETPOINT
        if co2_delta > 0:
            rr += self.CHEMO_CO2_GAIN * co2_delta
        elif bg.paco2 < self.CHEMO_CO2_THRESHOLD:
            # Hypocapnia → reduced drive (can cause apnea)
            rr *= max(0.5, bg.paco2 / self.CHEMO_CO2_SETPOINT)

        # ---- O2 drive (peripheral chemoreceptor) ----
        # Only significant when PaO2 < 60 mmHg (hypoxic drive)
        if bg.pao2 < self.CHEMO_O2_THRESHOLD:
            o2_deficit = self.CHEMO_O2_THRESHOLD - bg.pao2
            rr += self.CHEMO_O2_GAIN * o2_deficit

        # ---- pH drive ----
        # Acidosis → increase RR (compensatory hyperventilation)
        # Alkalosis → decrease RR
        ph_delta = 7.40 - bg.ph  # Positive when acidotic
        rr += self.CHEMO_PH_GAIN * ph_delta

        # ---- ANS modulation ----
        # Sympathetic increases RR, parasympathetic decreases
        ans_factor = 1.0 + 0.3 * (sympathetic_tone - 0.5) - 0.2 * (parasympathetic_tone - 0.5)
        rr *= max(0.5, min(2.0, ans_factor))

        # ---- Exercise drive ----
        # Exercise dramatically increases RR (up to ~40 breaths/min)
        if exercise_intensity > 0.01:
            rr += 20.0 * exercise_intensity

        return max(self.RR_MIN, min(self.RR_MAX, rr))

    def _compute_vt_target(
        self,
        bg: BloodGasState,
        exercise_intensity: float,
    ) -> float:
        """Compute target tidal volume from chemoreceptor drive + exercise.

        During exercise, Vt increases first (up to ~60% of VC),
        then RR increases to meet demand.
        """
        vt = self.BASE_VT

        # CO2 drive on Vt
        co2_delta = bg.paco2 - self.CHEMO_CO2_SETPOINT
        if co2_delta > 0:
            vt += self.VT_CO2_GAIN * co2_delta

        # Exercise increases Vt (first response, before RR increase)
        if exercise_intensity > 0.01:
            vt += self.VT_EXERCISE_GAIN * exercise_intensity

        return max(self.VT_MIN, min(self.VT_MAX, vt))

    def _compute_itp(self, exercise_intensity: float) -> float:
        """Compute intrathoracic pressure from breathing phase.

        ITP follows a sinusoidal pattern:
        - More negative during inspiration (phase 0 to pi)
        - Less negative during expiration (phase pi to 2*pi)

        Exercise increases ITP amplitude (more forceful breathing).
        """
        # Amplitude modulation with exercise
        amplitude = self.BASE_ITP_AMPLITUDE + self.ITP_EXERCISE_AMP * exercise_intensity

        # Sinusoidal ITP: most negative at peak inspiration (phase = pi/2)
        itp = self.BASE_ITP_MEAN - amplitude * math.sin(self._phase)

        return itp

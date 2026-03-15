"""V3 algebraic hemodynamics — no ODE.

Replaces the V2 HemodynamicEngineV2 (biventricular P-V loop ODE).
Computes all hemodynamic parameters algebraically from HR, modifiers,
and generates synthetic LV/RV pressure-volume curves for frontend
visualization (PV loop, cardiac cycle).

Reference:
- Weissler AM et al. Systolic Time Intervals in Heart Failure. Circulation 1968.
- Guyton AC. Textbook of Medical Physiology, Ch. 9 (Cardiac Output).
"""
from __future__ import annotations

import logging
from typing import Any

import numpy as np
from numpy.typing import NDArray

from app.engine.core.types import (
    HemodynamicState,
    Modifiers,
    ValveEvent,
)

logger = logging.getLogger(__name__)

# Visualization curve resolution
_CURVE_POINTS = 200


class AlgebraicHemodynamics:
    """V3 algebraic hemodynamic engine.

    Computes SBP/DBP/MAP/CO/EF/SV and generates synthetic pressure-volume
    curves without solving differential equations.
    """

    # Baseline healthy adult parameters
    BASE_SBP: float = 120.0
    BASE_DBP: float = 80.0
    BASE_SV: float = 70.0     # mL
    BASE_EF: float = 60.0     # %
    BASE_EDV: float = 120.0   # mL
    SPO2_BASE: float = 98.0
    RR_BASE: float = 16.0

    def __init__(self) -> None:
        self._prev_sbp: float = self.BASE_SBP
        self._prev_dbp: float = self.BASE_DBP

    def compute(
        self,
        hr: float,
        rr_sec: float,
        modifiers: Modifiers,
    ) -> HemodynamicState:
        """Compute hemodynamic state algebraically."""
        contractility = modifiers.contractility_modifier
        preload = modifiers.preload_modifier
        tpr = modifiers.tpr_modifier
        damage = modifiers.damage_level

        # --- Stroke volume ---
        sv = self.BASE_SV * contractility * preload * (1.0 - 0.4 * damage)
        sv = max(10.0, min(150.0, sv))

        # --- Cardiac output ---
        co = hr * sv / 1000.0  # L/min
        co = max(0.5, min(15.0, co))

        # --- Blood pressure ---
        # SBP depends on SV and TPR; DBP depends on TPR and HR
        sbp = 90.0 + 30.0 * (sv / self.BASE_SV) * tpr
        sbp = max(60.0, min(250.0, sbp))

        dbp = 60.0 + 20.0 * tpr * (1.0 - 0.002 * max(0, hr - 60))
        dbp = max(30.0, min(sbp - 5.0, min(150.0, dbp)))

        # Smooth with previous values for stability
        sbp = 0.7 * sbp + 0.3 * self._prev_sbp
        dbp = 0.7 * dbp + 0.3 * self._prev_dbp
        self._prev_sbp = sbp
        self._prev_dbp = dbp

        map_ = dbp + (sbp - dbp) / 3.0

        # --- Ejection fraction ---
        ef = self.BASE_EF * contractility * (1.0 - 0.3 * damage)
        ef = float(np.clip(ef, 15.0, 80.0))

        # --- EDV/ESV for PV loop ---
        edv = sv / (ef / 100.0) if ef > 5.0 else self.BASE_EDV
        edv = max(60.0, min(250.0, edv))
        esv = edv - sv

        # --- SpO2: use physical model if available ---
        spo2_physical = getattr(modifiers, 'spo2_physical', 0.0)
        if spo2_physical > 50.0:
            spo2 = float(np.clip(spo2_physical, 70.0, 100.0))
        else:
            spo2 = float(np.clip(
                self.SPO2_BASE - 2.0 * (1.0 - co / 5.0) - 5.0 * damage,
                70.0, 100.0,
            ))

        # --- Respiratory rate ---
        rr_physical = getattr(modifiers, 'rr_physical', 0.0)
        if rr_physical > 2.0:
            rr_resp = float(np.clip(rr_physical, 4.0, 60.0))
        else:
            rr_resp = float(self.RR_BASE * (
                1.0 + 0.5 * modifiers.sympathetic_tone
                - 0.3 * modifiers.parasympathetic_tone
            ))

        # --- Right ventricle (simplified estimates) ---
        rv_ef = float(np.clip(55.0 * contractility * (1.0 - 0.2 * damage), 20.0, 75.0))
        rv_sv = sv * 0.95  # slightly less than LV
        pa_sys = 25.0 * (1.0 + 0.5 * (tpr - 1.0))
        pa_dia = 10.0 * (1.0 + 0.3 * (tpr - 1.0))
        pa_mean = pa_dia + (pa_sys - pa_dia) / 3.0

        # --- Synthetic curves for visualization ---
        n = _CURVE_POINTS
        lv_pressure = _synthetic_lv_pressure(n, rr_sec, sbp, dbp)
        lv_volume = _synthetic_lv_volume(n, rr_sec, edv, esv)
        aortic_pressure = _synthetic_aortic_pressure(n, rr_sec, sbp, dbp)
        rv_pressure = _synthetic_rv_pressure(n, pa_sys)
        rv_volume = _synthetic_lv_volume(n, rr_sec, edv * 1.08, esv * 1.05)
        pa_pressure_curve = _synthetic_aortic_pressure(n, rr_sec, pa_sys, pa_dia)

        # --- Synthetic valve events (for pipeline physiology_detail) ---
        sr_hemo = 5000  # assumed hemo sample rate for valve event timing
        n_hemo = int(rr_sec * sr_hemo)
        mitral_close = int(0.10 * n_hemo)
        aortic_close = int(0.40 * n_hemo)
        dp_dt = float((sbp - dbp) / (0.1 * rr_sec + 1e-9))
        valve_events = [
            ValveEvent(valve='mitral', action='close', at_sample=mitral_close,
                       dp_dt=dp_dt, area_ratio=modifiers.valve_areas.get('mitral', 1.0)),
            ValveEvent(valve='aortic', action='close', at_sample=aortic_close,
                       dp_dt=dp_dt, area_ratio=modifiers.valve_areas.get('aortic', 1.0)),
            ValveEvent(valve='tricuspid', action='close', at_sample=mitral_close,
                       dp_dt=dp_dt * 0.3, area_ratio=1.0),
            ValveEvent(valve='pulmonary', action='close', at_sample=aortic_close,
                       dp_dt=dp_dt * 0.3, area_ratio=1.0),
        ]

        return HemodynamicState(
            lv_pressure=lv_pressure,
            lv_volume=lv_volume,
            aortic_pressure=aortic_pressure,
            systolic_bp=float(sbp),
            diastolic_bp=float(dbp),
            mean_arterial_pressure=float(map_),
            cardiac_output=float(co),
            ejection_fraction=ef,
            stroke_volume=float(sv),
            valve_events=valve_events,
            heart_rate=float(hr),
            spo2=spo2,
            respiratory_rate=rr_resp,
            approximate=True,
            rv_pressure=rv_pressure,
            rv_volume=rv_volume,
            pa_pressure=pa_pressure_curve,
            rv_ejection_fraction=rv_ef,
            rv_stroke_volume=float(rv_sv),
            pa_systolic=float(pa_sys),
            pa_diastolic=float(pa_dia),
            pa_mean=float(pa_mean),
        )

    def get_state(self) -> dict[str, Any]:
        return {"prev_sbp": self._prev_sbp, "prev_dbp": self._prev_dbp}

    def set_state(self, state: dict[str, Any]) -> None:
        self._prev_sbp = state.get("prev_sbp", self.BASE_SBP)
        self._prev_dbp = state.get("prev_dbp", self.BASE_DBP)


# ---------- Synthetic curve generators ----------

def _synthetic_lv_pressure(n: int, dt: float, sbp: float, dbp: float) -> NDArray[np.float64]:
    t = np.linspace(0, 1, n)
    p = np.full(n, dbp, dtype=np.float64)
    sys_end = 0.40
    mask = t <= sys_end
    t_sys = t[mask] / sys_end
    p[mask] = dbp + (sbp - dbp) * np.sin(np.pi * t_sys)
    dia_mask = ~mask
    t_dia = (t[dia_mask] - sys_end) / (1.0 - sys_end + 1e-9)
    p[dia_mask] = dbp * (1.0 + 0.1 * np.exp(-3.0 * t_dia))
    return p


def _synthetic_lv_volume(n: int, dt: float, edv: float, esv: float) -> NDArray[np.float64]:
    t = np.linspace(0, 1, n)
    v = np.full(n, edv, dtype=np.float64)
    sys_end = 0.40
    fill_start = 0.42
    sys_mask = t <= sys_end
    t_sys = t[sys_mask] / (sys_end + 1e-9)
    v[sys_mask] = edv - (edv - esv) * np.sin(0.5 * np.pi * t_sys)
    fill_mask = t >= fill_start
    t_fill = (t[fill_mask] - fill_start) / (1.0 - fill_start + 1e-9)
    v[fill_mask] = esv + (edv - esv) * (1.0 - np.exp(-3.0 * t_fill))
    return v


def _synthetic_aortic_pressure(n: int, dt: float, sbp: float, dbp: float) -> NDArray[np.float64]:
    t = np.linspace(0, 1, n)
    p = np.full(n, dbp, dtype=np.float64)
    sys_end = 0.40
    sys_mask = t <= sys_end
    t_sys = t[sys_mask] / sys_end
    p[sys_mask] = dbp + (sbp - dbp) * 0.95 * np.sin(np.pi * t_sys)
    dia_mask = ~sys_mask
    t_dia = (t[dia_mask] - sys_end) / (1.0 - sys_end + 1e-9)
    p[dia_mask] = dbp + (sbp * 0.95 - dbp) * np.exp(-2.5 * t_dia)
    return p


def _synthetic_rv_pressure(n: int, pa_sys: float) -> NDArray[np.float64]:
    t = np.linspace(0, 1, n)
    p = np.zeros(n, dtype=np.float64)
    sys_end = 0.35
    mask = t <= sys_end
    t_sys = t[mask] / sys_end
    p[mask] = pa_sys * np.sin(np.pi * t_sys)
    return p

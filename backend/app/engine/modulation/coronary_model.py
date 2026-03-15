"""Coronary circulation model: CPP calculation + ischemia cascade.

Models coronary perfusion and myocardial oxygen supply/demand balance:

1. **Coronary Perfusion Pressure (CPP)**:
   CPP = DBP - LVEDP
   Normal ≈ 60-80 mmHg; <50 mmHg triggers ischemia

2. **Myocardial O₂ Supply/Demand**:
   - Supply ∝ CPP × coronary_reserve
   - Demand ∝ HR × contractility × wall_stress (rate-pressure product proxy)
   
3. **Ischemia cascade**:
   - Supply/demand mismatch → progressive ischemia [0, 1]
   - Ischemia evolves with time constant (not instantaneous)
   - Severe ischemia (>0.7) → contractility depression feedback

Reference:
- Hoffman JIE. Determinants and prediction of transmural myocardial perfusion.
  Circulation 1978;58:381-391.
"""
from __future__ import annotations

import math
from typing import Any


# Normal coronary parameters
_CPP_NORMAL = 70.0          # mmHg
_CPP_ISCHEMIA_THRESHOLD = 50.0  # Below this, ischemia begins
_CPP_CRITICAL = 25.0        # Severe ischemia
_CORONARY_RESERVE = 3.0     # Normal coronary flow reserve (can triple flow)

# Ischemia time constant
_TAU_ISCHEMIA_ONSET = 10.0   # seconds — ischemia develops gradually
_TAU_ISCHEMIA_RECOVERY = 30.0  # seconds — recovery is slower than onset

# Rate-pressure product normalization
_RPP_NORMAL = 9000.0         # HR(75) × SBP(120) = 9000


class CoronaryModel:
    """Coronary circulation model with CPP-based ischemia cascade.

    Usage::

        coronary = CoronaryModel()
        for each beat:
            cpp, ischemia = coronary.update(
                dbp=80.0,
                lv_edp=12.0,
                hr=75.0,
                sbp=120.0,
                contractility=1.0,
                dt=0.8,
            )
    """

    def __init__(self) -> None:
        self._ischemia: float = 0.0
        self._cpp: float = _CPP_NORMAL
        self._coronary_reserve: float = _CORONARY_RESERVE

    def update(
        self,
        dbp: float,
        lv_edp: float,
        hr: float,
        sbp: float,
        contractility: float = 1.0,
        dt: float = 0.8,
        *,
        coronary_stenosis: float = 0.0,
    ) -> tuple[float, float]:
        """Update coronary perfusion for one beat.

        Args:
            dbp: Diastolic blood pressure (mmHg).
            lv_edp: LV end-diastolic pressure (mmHg), ~8-12 normally.
            hr: Heart rate (bpm).
            sbp: Systolic blood pressure (mmHg).
            contractility: Contractility modifier (1.0 = normal).
            dt: Beat duration (seconds).
            coronary_stenosis: [0, 1] degree of coronary artery stenosis.

        Returns:
            (cpp, ischemia_level) — CPP in mmHg, ischemia in [0, 1].
        """
        # --- Step 1: Coronary Perfusion Pressure ---
        self._cpp = dbp - lv_edp
        self._cpp = max(0.0, self._cpp)

        # --- Step 2: Effective coronary reserve (reduced by stenosis) ---
        effective_reserve = self._coronary_reserve * (1.0 - coronary_stenosis)
        effective_reserve = max(0.5, effective_reserve)

        # --- Step 3: O₂ supply (proportional to CPP × reserve) ---
        # Normalized to 1.0 at normal conditions
        supply = (self._cpp / _CPP_NORMAL) * (effective_reserve / _CORONARY_RESERVE)
        supply = max(0.0, min(2.0, supply))

        # --- Step 4: O₂ demand (rate-pressure product proxy) ---
        # RPP = HR × SBP; normalize to 1.0 at rest
        rpp = hr * sbp
        demand = (rpp / _RPP_NORMAL) * contractility
        demand = max(0.1, demand)

        # --- Step 5: Supply/demand ratio → ischemia target ---
        if demand < 1e-6:
            ratio = 2.0  # Infinite supply
        else:
            ratio = supply / demand

        # Ischemia target: sigmoid mapping
        # ratio > 1.0 → no ischemia; ratio < 0.5 → severe ischemia
        if ratio >= 1.0:
            ischemia_target = 0.0
        elif ratio <= 0.2:
            ischemia_target = 1.0
        else:
            # Smooth sigmoid transition between 0.2 and 1.0
            # Map ratio [0.2, 1.0] → ischemia [1.0, 0.0]
            normalized = (ratio - 0.2) / 0.8  # [0, 1]
            ischemia_target = 1.0 - normalized

        # Also consider direct CPP threshold
        if self._cpp < _CPP_ISCHEMIA_THRESHOLD:
            cpp_ischemia = (_CPP_ISCHEMIA_THRESHOLD - self._cpp) / (_CPP_ISCHEMIA_THRESHOLD - _CPP_CRITICAL)
            cpp_ischemia = max(0.0, min(1.0, cpp_ischemia))
            ischemia_target = max(ischemia_target, cpp_ischemia)

        # --- Step 6: First-order lag for ischemia evolution ---
        if ischemia_target > self._ischemia:
            tau = _TAU_ISCHEMIA_ONSET
        else:
            tau = _TAU_ISCHEMIA_RECOVERY

        alpha = 1.0 - math.exp(-dt / tau)
        self._ischemia += alpha * (ischemia_target - self._ischemia)
        self._ischemia = max(0.0, min(1.0, self._ischemia))

        return (self._cpp, self._ischemia)

    @property
    def cpp(self) -> float:
        """Current coronary perfusion pressure (mmHg)."""
        return self._cpp

    @property
    def ischemia_level(self) -> float:
        """Current ischemia level [0, 1]."""
        return self._ischemia

    def get_state(self) -> dict[str, Any]:
        return {
            "ischemia": self._ischemia,
            "cpp": self._cpp,
            "coronary_reserve": self._coronary_reserve,
        }

    def set_state(self, state: dict[str, Any]) -> None:
        self._ischemia = state.get("ischemia", 0.0)
        self._cpp = state.get("cpp", _CPP_NORMAL)
        self._coronary_reserve = state.get("coronary_reserve", _CORONARY_RESERVE)

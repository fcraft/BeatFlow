"""Level 0 physics invariant validator.

Checks 8 invariant conditions on each beat's hemodynamic + conduction output.
Returns a list of violations (empty = all good).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np

from app.engine.core.types import ConductionResult, HemodynamicState


@dataclass(frozen=True)
class InvariantViolation:
    """A single physics invariant violation."""
    code: str            # Short identifier (e.g. "HR_RANGE")
    message: str         # Human-readable description
    severity: Literal["warning", "error"]
    actual_value: float


# Valid ranges for invariant checks
HR_MIN, HR_MAX = 20.0, 300.0
EF_MIN, EF_MAX = 5.0, 95.0
SPO2_MIN, SPO2_MAX = 50.0, 100.0


def check_beat_invariants(
    hemo: HemodynamicState,
    conduction: ConductionResult | None = None,
) -> list[InvariantViolation]:
    """Check physics invariants for one beat.

    Args:
        hemo: Hemodynamic state from Layer 5
        conduction: Optional conduction result from Layer 2

    Returns:
        List of violations (empty if all invariants hold)
    """
    violations: list[InvariantViolation] = []

    # 1. HR in range [20, 300]
    if not (HR_MIN <= hemo.heart_rate <= HR_MAX):
        violations.append(InvariantViolation(
            code="HR_RANGE",
            message=f"Heart rate {hemo.heart_rate:.1f} bpm outside [{HR_MIN}, {HR_MAX}]",
            severity="error",
            actual_value=hemo.heart_rate,
        ))

    # 2. SBP > DBP
    if hemo.systolic_bp <= hemo.diastolic_bp:
        violations.append(InvariantViolation(
            code="SBP_GT_DBP",
            message=f"SBP ({hemo.systolic_bp:.1f}) <= DBP ({hemo.diastolic_bp:.1f})",
            severity="error",
            actual_value=hemo.systolic_bp - hemo.diastolic_bp,
        ))

    # 3. EF in range [5%, 95%]
    if not (EF_MIN <= hemo.ejection_fraction <= EF_MAX):
        violations.append(InvariantViolation(
            code="EF_RANGE",
            message=f"EF {hemo.ejection_fraction:.1f}% outside [{EF_MIN}, {EF_MAX}]",
            severity="error",
            actual_value=hemo.ejection_fraction,
        ))

    # 4. SV > 0
    if hemo.stroke_volume <= 0:
        violations.append(InvariantViolation(
            code="SV_POSITIVE",
            message=f"Stroke volume {hemo.stroke_volume:.1f} mL <= 0",
            severity="error",
            actual_value=hemo.stroke_volume,
        ))

    # 5. CO > 0
    if hemo.cardiac_output <= 0:
        violations.append(InvariantViolation(
            code="CO_POSITIVE",
            message=f"Cardiac output {hemo.cardiac_output:.2f} L/min <= 0",
            severity="error",
            actual_value=hemo.cardiac_output,
        ))

    # 6. SpO2 in range [50%, 100%]
    if not (SPO2_MIN <= hemo.spo2 <= SPO2_MAX):
        violations.append(InvariantViolation(
            code="SPO2_RANGE",
            message=f"SpO2 {hemo.spo2:.1f}% outside [{SPO2_MIN}, {SPO2_MAX}]",
            severity="warning",
            actual_value=hemo.spo2,
        ))

    # 7. RR > 0
    if hemo.respiratory_rate <= 0:
        violations.append(InvariantViolation(
            code="RR_POSITIVE",
            message=f"Respiratory rate {hemo.respiratory_rate:.1f} <= 0",
            severity="error",
            actual_value=hemo.respiratory_rate,
        ))

    # 8. P-V loop area > 0 (if curves available)
    if len(hemo.lv_pressure) > 1 and len(hemo.lv_volume) > 1:
        _trapz = getattr(np, 'trapezoid', None) or np.trapz
        pv_area = abs(float(_trapz(hemo.lv_pressure, hemo.lv_volume)))
        if pv_area <= 0:
            violations.append(InvariantViolation(
                code="PV_AREA_POSITIVE",
                message=f"P-V loop area {pv_area:.2f} <= 0",
                severity="warning",
                actual_value=pv_area,
            ))

    # 9. RV EF in range [5%, 95%] (if biventricular)
    rv_ef = getattr(hemo, 'rv_ejection_fraction', 55.0)
    if not (EF_MIN <= rv_ef <= EF_MAX):
        violations.append(InvariantViolation(
            code="RV_EF_RANGE",
            message=f"RV EF {rv_ef:.1f}% outside [{EF_MIN}, {EF_MAX}]",
            severity="warning",
            actual_value=rv_ef,
        ))

    # 10. PA systolic in range [5, 80] mmHg
    pa_sys = getattr(hemo, 'pa_systolic', 25.0)
    if not (5.0 <= pa_sys <= 80.0):
        violations.append(InvariantViolation(
            code="PA_SYS_RANGE",
            message=f"PA systolic {pa_sys:.1f} mmHg outside [5, 80]",
            severity="warning",
            actual_value=pa_sys,
        ))

    # 11. PA systolic >= PA diastolic
    pa_dia = getattr(hemo, 'pa_diastolic', 10.0)
    if pa_sys < pa_dia:
        violations.append(InvariantViolation(
            code="PA_SYS_GE_DIA",
            message=f"PA systolic ({pa_sys:.1f}) < PA diastolic ({pa_dia:.1f})",
            severity="warning",
            actual_value=pa_sys - pa_dia,
        ))

    return violations

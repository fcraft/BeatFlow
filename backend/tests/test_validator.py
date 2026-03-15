"""Tests for invariant validator (Task 7)."""
from __future__ import annotations

import numpy as np
import pytest

from app.engine.core.types import HemodynamicState, ValveEvent
from app.engine.simulation.validator import check_beat_invariants, InvariantViolation


def _make_normal_hemo() -> HemodynamicState:
    """Create a normal hemodynamic state that passes all invariants."""
    n = 4000
    # Realistic P-V loop with area > 0
    t = np.linspace(0, 1, n)
    lv_p = 10 + 110 * np.sin(np.pi * t) * (t < 0.4)
    lv_v = 120 - 50 * np.sin(0.5 * np.pi * t) * (t < 0.4)
    lv_v[t >= 0.4] = 70 + 50 * (1 - np.exp(-3 * (t[t >= 0.4] - 0.4)))

    return HemodynamicState(
        lv_pressure=lv_p,
        lv_volume=lv_v,
        aortic_pressure=np.full(n, 90.0),
        systolic_bp=120.0,
        diastolic_bp=80.0,
        mean_arterial_pressure=93.0,
        cardiac_output=5.0,
        ejection_fraction=60.0,
        stroke_volume=70.0,
        valve_events=[],
        heart_rate=72.0,
        spo2=98.0,
        respiratory_rate=16.0,
    )


class TestInvariantValidator:
    """Test physics invariant checks."""

    def test_normal_state_no_violations(self) -> None:
        hemo = _make_normal_hemo()
        violations = check_beat_invariants(hemo)
        assert violations == []

    def test_hr_too_low(self) -> None:
        hemo = _make_normal_hemo()
        hemo = HemodynamicState(
            **{**_hemo_dict(hemo), "heart_rate": 10.0}
        )
        violations = check_beat_invariants(hemo)
        codes = [v.code for v in violations]
        assert "HR_RANGE" in codes

    def test_hr_too_high(self) -> None:
        hemo = HemodynamicState(
            **{**_hemo_dict(_make_normal_hemo()), "heart_rate": 350.0}
        )
        violations = check_beat_invariants(hemo)
        assert any(v.code == "HR_RANGE" for v in violations)

    def test_sbp_not_greater_than_dbp(self) -> None:
        hemo = HemodynamicState(
            **{**_hemo_dict(_make_normal_hemo()),
               "systolic_bp": 70.0, "diastolic_bp": 80.0}
        )
        violations = check_beat_invariants(hemo)
        assert any(v.code == "SBP_GT_DBP" for v in violations)

    def test_ef_out_of_range(self) -> None:
        hemo = HemodynamicState(
            **{**_hemo_dict(_make_normal_hemo()), "ejection_fraction": 99.0}
        )
        violations = check_beat_invariants(hemo)
        assert any(v.code == "EF_RANGE" for v in violations)

    def test_sv_zero(self) -> None:
        hemo = HemodynamicState(
            **{**_hemo_dict(_make_normal_hemo()), "stroke_volume": 0.0}
        )
        violations = check_beat_invariants(hemo)
        assert any(v.code == "SV_POSITIVE" for v in violations)

    def test_co_negative(self) -> None:
        hemo = HemodynamicState(
            **{**_hemo_dict(_make_normal_hemo()), "cardiac_output": -1.0}
        )
        violations = check_beat_invariants(hemo)
        assert any(v.code == "CO_POSITIVE" for v in violations)

    def test_spo2_out_of_range(self) -> None:
        hemo = HemodynamicState(
            **{**_hemo_dict(_make_normal_hemo()), "spo2": 45.0}
        )
        violations = check_beat_invariants(hemo)
        assert any(v.code == "SPO2_RANGE" for v in violations)

    def test_rr_zero(self) -> None:
        hemo = HemodynamicState(
            **{**_hemo_dict(_make_normal_hemo()), "respiratory_rate": 0.0}
        )
        violations = check_beat_invariants(hemo)
        assert any(v.code == "RR_POSITIVE" for v in violations)

    def test_pv_area_flat_curves(self) -> None:
        """Flat LV curves → PV area = 0 → violation."""
        n = 100
        hemo = HemodynamicState(
            lv_pressure=np.full(n, 80.0),
            lv_volume=np.full(n, 120.0),
            aortic_pressure=np.full(n, 80.0),
            systolic_bp=120.0,
            diastolic_bp=80.0,
            mean_arterial_pressure=93.0,
            cardiac_output=5.0,
            ejection_fraction=60.0,
            stroke_volume=70.0,
            valve_events=[],
            heart_rate=72.0,
            spo2=98.0,
            respiratory_rate=16.0,
        )
        violations = check_beat_invariants(hemo)
        assert any(v.code == "PV_AREA_POSITIVE" for v in violations)

    def test_multiple_violations(self) -> None:
        """Multiple issues → multiple violations."""
        hemo = HemodynamicState(
            lv_pressure=np.full(10, 0.0),
            lv_volume=np.full(10, 0.0),
            aortic_pressure=np.full(10, 0.0),
            systolic_bp=50.0,
            diastolic_bp=60.0,  # SBP < DBP
            mean_arterial_pressure=55.0,
            cardiac_output=-1.0,
            ejection_fraction=2.0,  # Too low
            stroke_volume=-5.0,
            valve_events=[],
            heart_rate=5.0,  # Too low
            spo2=30.0,  # Too low
            respiratory_rate=0.0,  # Zero
        )
        violations = check_beat_invariants(hemo)
        codes = {v.code for v in violations}
        assert "HR_RANGE" in codes
        assert "SBP_GT_DBP" in codes
        assert "EF_RANGE" in codes
        assert "SV_POSITIVE" in codes
        assert "CO_POSITIVE" in codes
        assert "SPO2_RANGE" in codes
        assert "RR_POSITIVE" in codes

    def test_violation_has_severity(self) -> None:
        hemo = HemodynamicState(
            **{**_hemo_dict(_make_normal_hemo()), "heart_rate": 5.0}
        )
        violations = check_beat_invariants(hemo)
        assert len(violations) > 0
        assert violations[0].severity in ("warning", "error")


def _hemo_dict(hemo: HemodynamicState) -> dict:
    """Convert HemodynamicState to dict for easy field replacement."""
    return {
        "lv_pressure": hemo.lv_pressure,
        "lv_volume": hemo.lv_volume,
        "aortic_pressure": hemo.aortic_pressure,
        "systolic_bp": hemo.systolic_bp,
        "diastolic_bp": hemo.diastolic_bp,
        "mean_arterial_pressure": hemo.mean_arterial_pressure,
        "cardiac_output": hemo.cardiac_output,
        "ejection_fraction": hemo.ejection_fraction,
        "stroke_volume": hemo.stroke_volume,
        "valve_events": hemo.valve_events,
        "heart_rate": hemo.heart_rate,
        "spo2": hemo.spo2,
        "respiratory_rate": hemo.respiratory_rate,
    }

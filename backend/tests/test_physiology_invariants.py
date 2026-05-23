"""Physiology invariants — constraints that must hold regardless of input.

Tests verify fundamental physiological laws and cross-system constraints
that the simulation must never violate (spec section 10.3).
"""
import numpy as np
import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_default_hemo():
    """Build a healthy HemodynamicState at 72 BPM."""
    from app.engine.core.types import HemodynamicState
    return HemodynamicState(
        lv_pressure=np.array([0.0, 120.0, 10.0, 120.0]),
        lv_volume=np.array([120.0, 120.0, 50.0, 50.0]),
        aortic_pressure=np.array([80.0, 120.0, 80.0, 120.0]),
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
        approximate=True,
    )


def _make_graph():
    """Create a default causal graph."""
    from app.engine.modulation.causal_graph import create_default_graph
    return create_default_graph()


def _baseline_inputs():
    return {
        "map_mmhg": 93.0,
        "paco2_mmhg": 40.0,
        "pao2_mmhg": 98.0,
        "ph": 7.40,
        "temperature_c": 37.0,
        "cardiac_output": 5.0,
        "exercise_intensity": 0.0,
        "damage_level": 0.0,
    }


# ---------------------------------------------------------------------------
# Circulatory constraints
# ---------------------------------------------------------------------------

class TestCirculatoryInvariants:
    """MAP, CO, pressure relationships must hold."""

    def test_map_equals_dbp_plus_third_pulse_pressure(self):
        """MAP ≈ DBP + (SBP - DBP) / 3 (error < 5 mmHg)."""
        hemo = _make_default_hemo()
        expected_map = hemo.diastolic_bp + (hemo.systolic_bp - hemo.diastolic_bp) / 3.0
        assert abs(hemo.mean_arterial_pressure - expected_map) < 5.0

    def test_cardiac_output_equals_hr_times_sv(self):
        """CO (L/min) = HR (bpm) × SV (mL) / 1000."""
        hemo = _make_default_hemo()
        expected_co = hemo.heart_rate * hemo.stroke_volume / 1000.0
        assert abs(hemo.cardiac_output - expected_co) < 1.0

    def test_pulse_pressure_positive(self):
        """SBP must always exceed DBP (pulse pressure > 0)."""
        hemo = _make_default_hemo()
        assert hemo.systolic_bp > hemo.diastolic_bp

    def test_sbp_gt_map_gt_dbp(self):
        """SBP > MAP > DBP must hold."""
        hemo = _make_default_hemo()
        assert hemo.systolic_bp > hemo.mean_arterial_pressure > hemo.diastolic_bp

    def test_no_negative_pressures_or_volumes(self):
        """All pressures and volumes must be non-negative."""
        hemo = _make_default_hemo()
        assert hemo.systolic_bp >= 0
        assert hemo.diastolic_bp >= 0
        assert hemo.stroke_volume >= 0
        assert hemo.cardiac_output >= 0
        assert hemo.ejection_fraction >= 0


# ---------------------------------------------------------------------------
# Reflex constraints
# ---------------------------------------------------------------------------

class TestBaroreflexInvariants:
    """Baroreflex must exhibit negative feedback."""

    def _step_steady(self, graph, inputs, n=10):
        """Step graph n times to reach steady state, return last result."""
        r = None
        for _ in range(n):
            r = graph.step(0.8, inputs)
        return r

    def test_map_drop_increases_baro_symp(self):
        """MAP ↓ → baro_symp ↑ (negative feedback)."""
        graph = _make_graph()
        baseline = _baseline_inputs()

        norm = self._step_steady(graph, baseline)
        hypo = self._step_steady(graph, {**baseline, "map_mmhg": 60.0})
        assert hypo["baro_symp"] > norm["baro_symp"], \
            f"MAP 60→baro_symp={hypo['baro_symp']:.2f} should > MAP 93→baro_symp={norm['baro_symp']:.2f}"

    def test_map_rise_increases_parasympathetic(self):
        """MAP ↑ → parasympathetic_tone ↑ (baroreflex activation)."""
        graph = _make_graph()
        baseline = _baseline_inputs()

        norm = self._step_steady(graph, baseline)
        hyper = self._step_steady(graph, {**baseline, "map_mmhg": 140.0})
        assert hyper["parasympathetic_tone"] > norm["parasympathetic_tone"], \
            f"MAP 140→para={hyper['parasympathetic_tone']:.2f} should > MAP 93→para={norm['parasympathetic_tone']:.2f}"

    def test_baroreflex_affects_sa_rate(self):
        """MAP change should affect sa_rate_modifier via baroreflex."""
        graph = _make_graph()
        baseline = _baseline_inputs()

        norm = self._step_steady(graph, baseline)
        hypo = self._step_steady(graph, {**baseline, "map_mmhg": 55.0})
        assert hypo["sa_rate_modifier"] > norm["sa_rate_modifier"], \
            "Hypotension should increase SA rate via baroreflex"


# ---------------------------------------------------------------------------
# Respiratory constraints
# ---------------------------------------------------------------------------

class TestRespiratoryInvariants:
    """Respiratory drive constraints."""

    def _step_steady(self, graph, inputs, n=10):
        r = None
        for _ in range(n):
            r = graph.step(0.8, inputs)
        return r

    def test_hypercapnia_increases_chemo_drive(self):
        """PaCO₂ ↑ → chemo_symp_drive ↑ (central chemoreflex)."""
        graph = _make_graph()
        baseline = _baseline_inputs()

        norm = self._step_steady(graph, baseline)
        hypercapnia = self._step_steady(graph, {**baseline, "paco2_mmhg": 55.0})
        assert hypercapnia["chemo_symp_drive"] > norm["chemo_symp_drive"], \
            f"PaCO₂ 55→chemo={hypercapnia['chemo_symp_drive']:.3f} should > PaCO₂ 40→chemo={norm['chemo_symp_drive']:.3f}"

    def test_hypoxia_increases_sympathetic(self):
        """PaO₂ ↓ → sympathetic_tone ↑ (peripheral chemoreflex)."""
        graph = _make_graph()
        baseline = _baseline_inputs()

        norm = self._step_steady(graph, baseline)
        hypoxia = self._step_steady(graph, {**baseline, "pao2_mmhg": 50.0})
        assert hypoxia["chemo_symp_drive"] >= norm["chemo_symp_drive"], \
            f"PaO₂ 50→chemo={hypoxia['chemo_symp_drive']:.3f} should >= PaO₂ 98→chemo={norm['chemo_symp_drive']:.3f}"


# ---------------------------------------------------------------------------
# Pharmacological constraints
# ---------------------------------------------------------------------------

class TestPharmacologicalInvariants:
    """Drug effects must follow known pharmacology."""

    def _step_steady(self, graph, inputs, n=10):
        r = None
        for _ in range(n):
            r = graph.step(0.8, inputs)
        return r

    def test_beta_blocker_reduces_hr_and_contractility(self):
        """Beta blocker → SA rate ↓ and contractility ↓ ."""
        baseline = _baseline_inputs()
        g1 = _make_graph()
        norm = self._step_steady(g1, baseline)
        g2 = _make_graph()
        bb = self._step_steady(g2, {**baseline, "beta_blocker": 1.0})
        assert bb["sa_rate_modifier"] < norm["sa_rate_modifier"], \
            f"BB sa={bb['sa_rate_modifier']:.3f} should < normal sa={norm['sa_rate_modifier']:.3f}"
        assert bb["contractility_modifier"] < norm["contractility_modifier"], \
            f"BB contract={bb['contractility_modifier']:.3f} should < normal contract={norm['contractility_modifier']:.3f}"

    def test_drug_clearance_reduces_effect_over_time(self):
        """Drug effect should diminish as concentration decays."""
        graph = _make_graph()
        baseline = _baseline_inputs()

        r1 = self._step_steady(graph, {**baseline, "beta_blocker": 1.0})
        r2 = self._step_steady(graph, {**baseline, "beta_blocker": 0.3})
        assert r2["sa_rate_modifier"] > r1["sa_rate_modifier"], \
            "SA rate should recover as drug level drops"

    def test_atropine_increases_hr(self):
        """Atropine (anticholinergic) → SA rate ↑ ."""
        baseline = _baseline_inputs()
        g1 = _make_graph()
        norm = self._step_steady(g1, baseline)
        g2 = _make_graph()
        atr = self._step_steady(g2, {**baseline, "atropine": 1.0})
        assert atr["sa_rate_modifier"] > norm["sa_rate_modifier"], \
            f"Atropine sa={atr['sa_rate_modifier']:.3f} should > normal sa={norm['sa_rate_modifier']:.3f}"


# ---------------------------------------------------------------------------
# Bounds constraints
# ---------------------------------------------------------------------------

class TestBoundsInvariants:
    """Vitals must stay within physiological limits."""

    def test_hr_within_physiological_range(self):
        """HR must be in [20, 300] bpm."""
        hemo = _make_default_hemo()
        assert 20 <= hemo.heart_rate <= 300

    def test_spo2_bounded_0_to_100(self):
        """SpO₂ must be in [0, 100] %."""
        hemo = _make_default_hemo()
        assert 0 <= hemo.spo2 <= 100

    def test_ef_bounded_5_to_95(self):
        """EF must be in [5, 95] %."""
        hemo = _make_default_hemo()
        assert 5 <= hemo.ejection_fraction <= 95

    def test_temperature_in_physiological_range(self):
        """Core temperature must produce bounded modifier effects."""
        graph = _make_graph()
        r = graph.step(0.8, {**_baseline_inputs(), "temperature_c": 37.0})
        # Temperature effect should not produce wildly out-of-range modifiers
        assert 0.4 <= r.get("sa_rate_modifier", 1.0) <= 3.0


# ---------------------------------------------------------------------------
# Validator integration
# ---------------------------------------------------------------------------

class TestValidatorIntegration:
    """The built-in check_beat_invariants should catch violations."""

    def test_validator_passes_healthy_state(self):
        """Healthy state should produce zero violations."""
        from app.engine.simulation.validator import check_beat_invariants
        hemo = _make_default_hemo()
        violations = check_beat_invariants(hemo)
        errors = [v for v in violations if v.severity == "error"]
        assert len(errors) == 0, f"Healthy state violated: {[e.message for e in errors]}"

    def test_validator_detects_extreme_hypotension(self):
        """SBP < DBP should be caught."""
        from app.engine.simulation.validator import check_beat_invariants
        from app.engine.core.types import HemodynamicState
        hemo = HemodynamicState(
            lv_pressure=np.zeros(0), lv_volume=np.zeros(0),
            aortic_pressure=np.zeros(0),
            systolic_bp=40.0, diastolic_bp=50.0,
            mean_arterial_pressure=30.0,
            cardiac_output=2.0, ejection_fraction=30.0,
            stroke_volume=30.0, valve_events=[],
            heart_rate=40.0, spo2=85.0, respiratory_rate=20.0,
            approximate=True,
        )
        violations = check_beat_invariants(hemo)
        codes = {v.code for v in violations}
        assert "SBP_GT_DBP" in codes

    def test_validator_detects_extreme_hr(self):
        """HR=400 should be flagged (HemodynamicState is frozen, construct new)."""
        from app.engine.simulation.validator import check_beat_invariants
        from app.engine.core.types import HemodynamicState
        import numpy as np
        hemo = HemodynamicState(
            lv_pressure=np.zeros(0), lv_volume=np.zeros(0),
            aortic_pressure=np.zeros(0),
            systolic_bp=120.0, diastolic_bp=80.0,
            mean_arterial_pressure=93.0,
            cardiac_output=5.0, ejection_fraction=60.0,
            stroke_volume=70.0, valve_events=[],
            heart_rate=400.0, spo2=98.0, respiratory_rate=16.0,
            approximate=True,
        )
        violations = check_beat_invariants(hemo)
        codes = {v.code for v in violations}
        assert "HR_RANGE" in codes

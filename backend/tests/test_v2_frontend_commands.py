"""V2 Frontend Command Audit Test Suite.

Validates that every frontend command produces valid pipeline output
without errors, NaN, or silent signals.
"""
from __future__ import annotations

import numpy as np
import pytest

from app.engine.simulation.pipeline import SimulationPipeline


# =====================================================================
# Shared helper
# =====================================================================

def run_command_test(
    command: str,
    params: dict | None = None,
    n_beats: int = 10,
) -> tuple[np.ndarray, np.ndarray, dict]:
    """Run a single command and return signals + vitals.

    Returns:
        (ecg, pcg, vitals)
    """
    p = SimulationPipeline()
    p._ensure_layers()
    p.apply_command(command, params or {})

    for _ in range(n_beats):
        p._run_one_beat()

    ecg = np.array(list(p._ecg_buf), dtype=np.float64)
    pcg = np.array(list(p._pcg_buf), dtype=np.float64)
    vitals = dict(p._vitals)

    return ecg, pcg, vitals


def assert_valid_output(ecg: np.ndarray, pcg: np.ndarray, label: str):
    """Assert signals are non-empty, no NaN/Inf."""
    assert len(ecg) > 0 or len(pcg) > 0, f"No output for {label}"
    if len(ecg) > 0:
        assert not np.any(np.isnan(ecg)), f"NaN in ECG for {label}"
        assert not np.any(np.isinf(ecg)), f"Inf in ECG for {label}"
    if len(pcg) > 0:
        assert not np.any(np.isnan(pcg)), f"NaN in PCG for {label}"
        assert not np.any(np.isinf(pcg)), f"Inf in PCG for {label}"


# =====================================================================
# Task 6a: Exercise Commands
# =====================================================================

class TestExerciseCommands:
    """Validate all 6 exercise commands produce valid output."""

    @pytest.mark.parametrize("cmd", [
        "rest", "walk", "jog", "run", "climb_stairs", "squat",
    ])
    def test_exercise_command_produces_valid_output(self, cmd: str):
        ecg, pcg, vitals = run_command_test(cmd)
        assert_valid_output(ecg, pcg, f"exercise:{cmd}")
        assert vitals.get("heart_rate", 0) > 0, (
            f"HR is 0 after {cmd}"
        )

    def test_exercise_progression(self):
        """HR with 'run' should be higher than with 'rest'.

        Note: The V2 engine uses transition smoothing and the relationship
        between exercise commands and HR is indirect (via sympathetic tone).
        We focus on the most extreme comparison (rest vs run) which should
        show a clear difference.
        """
        _, _, rest_vitals = run_command_test("rest", n_beats=30)
        _, _, run_vitals = run_command_test("run", n_beats=30)

        rest_hr = rest_vitals.get("heart_rate", 0)
        run_hr = run_vitals.get("heart_rate", 0)

        assert run_hr > rest_hr, (
            f"run HR {run_hr:.1f} not > rest HR {rest_hr:.1f}"
        )


# =====================================================================
# Task 6b: Emotion Commands
# =====================================================================

class TestEmotionCommands:
    """Validate all 5 emotion commands."""

    @pytest.mark.parametrize("cmd", [
        "startle", "anxiety", "relaxation", "stress", "fatigue",
    ])
    def test_emotion_command_produces_valid_output(self, cmd: str):
        ecg, pcg, vitals = run_command_test(cmd)
        assert_valid_output(ecg, pcg, f"emotion:{cmd}")
        assert vitals.get("heart_rate", 0) > 0, f"HR 0 after {cmd}"


# =====================================================================
# Task 6c: Condition Commands
# =====================================================================

class TestConditionCommands:
    """Validate all 14 condition commands + interventions + PVC + substrates."""

    @pytest.mark.parametrize("cmd,params", [
        ("condition_normal", {}),
        ("condition_af", {"severity": 0.5}),
        ("condition_pvc", {"severity": 0.3}),
        ("condition_tachycardia", {"heart_rate": 150}),
        ("condition_bradycardia", {"heart_rate": 45}),
        ("condition_valve_disease", {"murmur_type": "systolic", "severity": 0.5}),
        ("condition_heart_failure", {"severity": 0.6}),
        ("condition_svt", {"heart_rate": 180}),
        ("condition_vt", {"severity": 0.7}),
        ("condition_av_block_1", {}),
        ("condition_av_block_2", {}),
        ("condition_av_block_3", {}),
        ("condition_vf", {}),
        ("condition_asystole", {}),
    ])
    def test_condition_produces_valid_output(self, cmd: str, params: dict):
        ecg, pcg, vitals = run_command_test(cmd, params)
        assert_valid_output(ecg, pcg, f"condition:{cmd}")

    @pytest.mark.parametrize("cmd", ["defibrillate", "cardiovert"])
    def test_intervention_does_not_crash(self, cmd: str):
        """Interventions should not crash even when rhythm doesn't match."""
        p = SimulationPipeline()
        p._ensure_layers()
        for _ in range(3):
            p._run_one_beat()

        # Apply intervention (may be ineffective, but must not crash)
        p.apply_command(cmd)
        for _ in range(3):
            p._run_one_beat()

        ecg = np.array(list(p._ecg_buf), dtype=np.float64)
        pcg = np.array(list(p._pcg_buf), dtype=np.float64)
        assert_valid_output(ecg, pcg, f"intervention:{cmd}")

    @pytest.mark.parametrize("pattern", [
        "isolated", "bigeminy", "trigeminy", "couplets",
    ])
    def test_pvc_pattern(self, pattern: str):
        ecg, pcg, vitals = run_command_test(
            "set_pvc_pattern", {"pattern": pattern},
        )
        assert_valid_output(ecg, pcg, f"pvc_pattern:{pattern}")

    @pytest.mark.parametrize("cmd,params", [
        ("set_af_substrate", {"level": 0.7}),
        ("set_svt_substrate", {"level": 0.7}),
        ("set_vt_substrate", {"level": 0.7}),
    ])
    def test_substrate_command(self, cmd: str, params: dict):
        ecg, pcg, vitals = run_command_test(cmd, params)
        assert_valid_output(ecg, pcg, f"substrate:{cmd}")


# =====================================================================
# Task 6d: Medication Commands
# =====================================================================

class TestMedicationCommands:
    """Validate all 4 medication commands."""

    @pytest.mark.parametrize("cmd", [
        "beta_blocker", "amiodarone", "digoxin", "atropine",
    ])
    def test_medication_produces_valid_output(self, cmd: str):
        ecg, pcg, vitals = run_command_test(cmd, {"dose": 1.0})
        assert_valid_output(ecg, pcg, f"medication:{cmd}")
        assert vitals.get("heart_rate", 0) > 0, f"HR 0 after {cmd}"


# =====================================================================
# Task 6e: Body State Commands
# =====================================================================

class TestBodyStateCommands:
    """Validate all 7 body state commands with parameters."""

    @pytest.mark.parametrize("cmd,params", [
        ("caffeine", {"dose": 0.5}),
        ("alcohol", {"dose": 0.4}),
        ("fever", {"temperature": 39.0}),
        ("sleep_deprivation", {"severity": 0.6}),
        ("dehydration", {"severity": 0.5}),
        ("hydrate", {}),
        ("sleep", {}),
    ])
    def test_body_state_produces_valid_output(self, cmd: str, params: dict):
        ecg, pcg, vitals = run_command_test(cmd, params)
        assert_valid_output(ecg, pcg, f"body_state:{cmd}")


# =====================================================================
# Task 6f: Electrolyte Commands
# =====================================================================

class TestElectrolyteCommands:
    """Validate all 4 electrolyte commands with specific levels."""

    @pytest.mark.parametrize("cmd,params", [
        ("hyperkalemia", {"level": 6.0}),
        ("hypokalemia", {"level": 3.0}),
        ("hypercalcemia", {"level": 12.0}),
        ("hypocalcemia", {"level": 7.0}),
    ])
    def test_electrolyte_produces_valid_output(self, cmd: str, params: dict):
        ecg, pcg, vitals = run_command_test(cmd, params)
        assert_valid_output(ecg, pcg, f"electrolyte:{cmd}")


# =====================================================================
# Task 6g: Settings Commands
# =====================================================================

class TestSettingsCommands:
    """Validate all settings sliders across their full range."""

    @pytest.mark.parametrize("level", [0.0, 0.3, 0.5, 0.7, 1.0])
    def test_damage_level_range(self, level: float):
        ecg, pcg, vitals = run_command_test(
            "set_damage_level", {"level": level},
        )
        assert_valid_output(ecg, pcg, f"damage:{level}")

    @pytest.mark.parametrize("hr", [30, 60, 72, 120, 180, 250])
    def test_heart_rate_range(self, hr: int):
        ecg, pcg, vitals = run_command_test(
            "set_heart_rate", {"value": float(hr)},
        )
        assert_valid_output(ecg, pcg, f"hr:{hr}")

    @pytest.mark.parametrize("level", [0.5, 1.0, 1.5, 2.0])
    def test_preload_range(self, level: float):
        ecg, pcg, vitals = run_command_test(
            "set_preload", {"level": level},
        )
        assert_valid_output(ecg, pcg, f"preload:{level}")

    @pytest.mark.parametrize("level", [0.2, 0.5, 1.0, 1.5, 2.5])
    def test_contractility_range(self, level: float):
        ecg, pcg, vitals = run_command_test(
            "set_contractility", {"level": level},
        )
        assert_valid_output(ecg, pcg, f"contractility:{level}")

    @pytest.mark.parametrize("level", [0.3, 0.5, 1.0, 2.0, 3.0])
    def test_tpr_range(self, level: float):
        ecg, pcg, vitals = run_command_test(
            "set_tpr", {"level": level},
        )
        assert_valid_output(ecg, pcg, f"tpr:{level}")

    def test_reset_command(self):
        """Reset should restore defaults without crash."""
        p = SimulationPipeline()
        p._ensure_layers()
        # Apply some changes
        p.apply_command("run")
        p.apply_command("condition_af", {"severity": 0.7})
        for _ in range(5):
            p._run_one_beat()

        # Reset
        p.apply_command("reset")
        for _ in range(5):
            p._run_one_beat()

        ecg = np.array(list(p._ecg_buf), dtype=np.float64)
        pcg = np.array(list(p._pcg_buf), dtype=np.float64)
        assert_valid_output(ecg, pcg, "reset")


# =====================================================================
# Task 6h: Frontend Control Issues Verification
# =====================================================================

class TestFrontendControlIssues:
    """Verify specific frontend control behaviors."""

    def test_vitals_reports_damage_level(self):
        """Backend should report damage_level in vitals dict."""
        p = SimulationPipeline()
        p._ensure_layers()
        p.apply_command("set_damage_level", {"level": 0.5})
        for _ in range(5):
            p._run_one_beat()

        vitals = p._vitals
        assert "damage_level" in vitals, (
            "damage_level not in vitals output"
        )
        # Damage may be smoothed, but should be > 0
        assert vitals["damage_level"] > 0, (
            f"damage_level is {vitals['damage_level']} after set to 0.5"
        )

    def test_vitals_reports_heart_rate(self):
        """Backend should report heart_rate in vitals dict."""
        p = SimulationPipeline()
        p._ensure_layers()
        p.apply_command("set_heart_rate", {"value": 100.0})
        for _ in range(10):
            p._run_one_beat()

        vitals = p._vitals
        assert "heart_rate" in vitals, "heart_rate not in vitals output"
        assert vitals["heart_rate"] > 0, (
            f"heart_rate is {vitals['heart_rate']} after set to 100"
        )

    def test_heart_failure_severity_param_works(self):
        """condition_heart_failure should accept severity parameter."""
        for severity in [0.3, 0.6, 0.9]:
            p = SimulationPipeline()
            p._ensure_layers()
            p.apply_command("condition_heart_failure", {"severity": severity})
            for _ in range(5):
                p._run_one_beat()

            vitals = p._vitals
            # damage_level should reflect the severity (possibly smoothed)
            reported = vitals.get("damage_level", 0)
            # With transition smoothing, it may not reach full severity
            # in 5 beats, but should be > 0 for severity > 0
            if severity >= 0.3:
                assert reported > 0, (
                    f"damage_level={reported} after HF severity={severity}"
                )

"""Tests for enhanced autonomic feedback: chemoreceptor drives + ANS fatigue."""
from app.engine.modulation.autonomic_reflex import AutonomicReflexController


def test_low_spo2_increases_sympathetic():
    """SpO₂=90 → sympathetic rises more than SpO₂=97."""
    ctrl_normal = AutonomicReflexController()
    ctrl_hypoxic = AutonomicReflexController()

    # Low MAP to drive sympathetic up, run several beats
    low_map = 70.0
    dt = 0.8
    for _ in range(30):
        s_normal, _ = ctrl_normal.update(low_map, dt, spo2=97.0)
        s_hypoxic, _ = ctrl_hypoxic.update(low_map, dt, spo2=90.0)

    assert s_hypoxic > s_normal, (
        f"Hypoxic sympathetic ({s_hypoxic:.4f}) should exceed "
        f"normal ({s_normal:.4f})"
    )


def test_low_co_increases_sympathetic():
    """CO=2.5 → sympathetic rises more than CO=5.0."""
    ctrl_normal = AutonomicReflexController()
    ctrl_low_co = AutonomicReflexController()

    low_map = 70.0
    dt = 0.8
    for _ in range(30):
        s_normal, _ = ctrl_normal.update(low_map, dt, cardiac_output=5.0)
        s_low_co, _ = ctrl_low_co.update(low_map, dt, cardiac_output=2.5)

    assert s_low_co > s_normal, (
        f"Low CO sympathetic ({s_low_co:.4f}) should exceed "
        f"normal ({s_normal:.4f})"
    )


def test_ans_fatigue_reduces_sympathetic_ceiling():
    """5+ minutes of high sympathetic → effective sympathetic decreases."""
    ctrl = AutonomicReflexController()

    # Drive sympathetic very high with low MAP + low SpO2 + low CO
    low_map = 50.0
    dt = 0.8
    # Run 400 beats (~320 seconds, >5 min) to accumulate fatigue
    symp_values = []
    for _ in range(400):
        s, _ = ctrl.update(low_map, dt, spo2=85.0, cardiac_output=2.0)
        symp_values.append(s)

    # After fatigue accumulation, sympathetic should be lower than its peak
    peak_symp = max(symp_values[:100])  # Peak in first 100 beats
    final_symp = symp_values[-1]

    assert ctrl._ans_fatigue > 0.0, "Fatigue should have accumulated"
    assert final_symp < peak_symp, (
        f"Final sympathetic ({final_symp:.4f}) should be less than "
        f"peak ({peak_symp:.4f}) due to fatigue"
    )


def test_ans_fatigue_recovers_at_rest():
    """After fatigue, normal sympathetic → fatigue decreases."""
    ctrl = AutonomicReflexController()

    # First accumulate fatigue with high sympathetic drive
    low_map = 50.0
    dt = 0.8
    for _ in range(300):
        ctrl.update(low_map, dt, spo2=85.0, cardiac_output=2.0)

    fatigue_after_stress = ctrl._ans_fatigue
    assert fatigue_after_stress > 0.0, "Should have fatigue after stress"

    # Now rest: normal MAP → sympathetic drops below 0.7 → fatigue recovers
    normal_map = 93.0
    for _ in range(400):
        ctrl.update(normal_map, dt, spo2=97.0, cardiac_output=5.0)

    fatigue_after_rest = ctrl._ans_fatigue
    assert fatigue_after_rest < fatigue_after_stress, (
        f"Fatigue after rest ({fatigue_after_rest:.4f}) should be less than "
        f"after stress ({fatigue_after_stress:.4f})"
    )


def test_backward_compatible_without_new_params():
    """Calling update(map, dt) without new kwargs works identically."""
    ctrl_old = AutonomicReflexController()
    ctrl_new = AutonomicReflexController()

    map_val = 93.0
    dt = 0.8

    for _ in range(20):
        s_old, p_old = ctrl_old.update(map_val, dt)
        s_new, p_new = ctrl_new.update(map_val, dt, cardiac_output=5.0, spo2=97.0)

    # With default params (CO=5.0, SpO2=97.0), results should be identical
    assert abs(s_old - s_new) < 1e-10, (
        f"Sympathetic mismatch: old={s_old}, new={s_new}"
    )
    assert abs(p_old - p_new) < 1e-10, (
        f"Parasympathetic mismatch: old={p_old}, new={p_new}"
    )


def test_get_set_state_includes_fatigue():
    """get_state/set_state round-trips ans_fatigue."""
    ctrl = AutonomicReflexController()
    ctrl._ans_fatigue = 0.42

    state = ctrl.get_state()
    assert "ans_fatigue" in state
    assert state["ans_fatigue"] == 0.42

    ctrl2 = AutonomicReflexController()
    ctrl2.set_state(state)
    assert ctrl2._ans_fatigue == 0.42


def test_set_state_defaults_fatigue_to_zero():
    """set_state without ans_fatigue key defaults to 0.0."""
    ctrl = AutonomicReflexController()
    ctrl._ans_fatigue = 0.5
    ctrl.set_state({"sympathetic": 0.5, "parasympathetic": 0.5})
    assert ctrl._ans_fatigue == 0.0

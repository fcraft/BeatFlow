"""Tests for 4-node cardiac conduction network."""
import numpy as np
import pytest
from app.engine.core.parametric_conduction import ParametricConductionNetwork as ConductionNetworkV2
from app.engine.core.types import Modifiers, EctopicFocus


@pytest.fixture
def network():
    return ConductionNetworkV2()


class TestNormalSinusRhythm:
    def test_produces_conduction_result(self, network):
        result = network.propagate(0.833, Modifiers())
        assert result.beat_kind == 'sinus'
        assert result.conducted is True

    def test_pr_interval_normal_range(self, network):
        result = network.propagate(0.833, Modifiers())
        assert 120 <= result.pr_interval_ms <= 200, f"PR={result.pr_interval_ms}ms"

    def test_qrs_duration_normal(self, network):
        result = network.propagate(0.833, Modifiers())
        assert 60 <= result.qrs_duration_ms <= 120, f"QRS={result.qrs_duration_ms}ms"

    def test_qt_interval_normal(self, network):
        result = network.propagate(0.833, Modifiers())
        assert 300 <= result.qt_interval_ms <= 500, f"QT={result.qt_interval_ms}ms"

    def test_p_wave_present(self, network):
        result = network.propagate(0.833, Modifiers())
        assert result.p_wave_present is True
        assert result.p_wave_retrograde is False

    def test_activation_times_sequential(self, network):
        result = network.propagate(0.833, Modifiers())
        t = result.activation_times
        assert t['sa'] < t['av'] < t['his'] < t['purkinje']


class TestStability:
    def test_1000_beats_no_drift(self, network):
        hrs = []
        for _ in range(1000):
            result = network.propagate(0.833, Modifiers())
            hrs.append(60.0 / result.rr_sec)
        cv = np.std(hrs) / np.mean(hrs)
        assert cv < 0.02, f"HR CV should be < 2%, got {cv:.4f}"
        drift = abs(np.mean(hrs[:50]) - np.mean(hrs[-50:]))
        assert drift < 0.5, f"HR drift should be < 0.5 bpm, got {drift:.2f}"


class TestPVC:
    def test_ectopic_produces_pvc(self, network):
        mod = Modifiers(ectopic_foci=[
            EctopicFocus(node='purkinje', current=1.0, coupling_interval_ms=400)
        ])
        result = network.propagate(0.833, mod)
        assert result.qrs_duration_ms > 100 or result.beat_kind == 'pvc'


class TestAVBlock:
    def test_first_degree_increased_pr(self, network):
        mod = Modifiers(av_delay_modifier=2.0)
        result = network.propagate(0.833, mod)
        assert result.pr_interval_ms > 200, f"PR={result.pr_interval_ms}ms should be >200"


class TestStateManagement:
    def test_state_roundtrip(self, network):
        for _ in range(10):
            network.propagate(0.833, Modifiers())
        state = network.get_state()
        new_net = ConductionNetworkV2()
        new_net.set_state(state)
        r1 = network.propagate(0.833, Modifiers())
        r2 = new_net.propagate(0.833, Modifiers())
        assert abs(r1.pr_interval_ms - r2.pr_interval_ms) < 5.0

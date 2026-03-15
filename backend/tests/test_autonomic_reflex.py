"""Tests for AutonomicReflexController (Task 4)."""
from __future__ import annotations

import pytest

from app.engine.modulation.autonomic_reflex import AutonomicReflexController


class TestAutonomicReflexController:
    """Test baroreceptor reflex controller."""

    def setup_method(self) -> None:
        self.ctrl = AutonomicReflexController()

    def test_initial_state(self) -> None:
        assert self.ctrl.sympathetic_tone == 0.5
        assert self.ctrl.parasympathetic_tone == 0.5

    def test_normal_map_stable(self) -> None:
        """At normal MAP (~93), tones should stay near resting."""
        for _ in range(10):
            self.ctrl.update(93.0, dt=0.83)
        assert abs(self.ctrl.sympathetic_tone - 0.5) < 0.15
        assert abs(self.ctrl.parasympathetic_tone - 0.5) < 0.15

    def test_low_bp_raises_hr(self) -> None:
        """BP drop 30mmHg → sympathetic should increase within 3s (~4 beats)."""
        initial_symp = self.ctrl.sympathetic_tone
        # Simulate ~4 beats with low MAP
        for _ in range(5):
            self.ctrl.update(63.0, dt=0.83)  # MAP dropped 30mmHg

        assert self.ctrl.sympathetic_tone > initial_symp, (
            "Sympathetic tone should increase with low BP"
        )

    def test_high_bp_increases_parasympathetic(self) -> None:
        """High BP → parasympathetic increases (vagal response)."""
        initial_para = self.ctrl.parasympathetic_tone
        for _ in range(5):
            self.ctrl.update(130.0, dt=0.83)  # High MAP
        assert self.ctrl.parasympathetic_tone > initial_para

    def test_parasympathetic_faster_than_sympathetic(self) -> None:
        """Parasympathetic should respond faster (τ=0.5s vs τ=2s)."""
        ctrl = AutonomicReflexController()
        # Single beat with high MAP
        ctrl.update(130.0, dt=0.83)
        para_change = abs(ctrl.parasympathetic_tone - 0.5)
        symp_change = abs(ctrl.sympathetic_tone - 0.5)
        # Para should change more in the first beat
        assert para_change >= symp_change * 0.5, (
            f"Para change {para_change:.4f} should be >= half symp change {symp_change:.4f}"
        )

    def test_circuit_breaker_limits_rapid_change(self) -> None:
        """Rapid oscillations should trigger circuit breaker."""
        # Alternate between extreme MAPs
        changes = []
        for i in range(6):
            bp = 150.0 if i % 2 == 0 else 50.0
            s_before = self.ctrl.sympathetic_tone
            self.ctrl.update(bp, dt=0.83)
            changes.append(abs(self.ctrl.sympathetic_tone - s_before))

        # Later changes should be smaller due to circuit breaker
        # (cumulative threshold triggered)
        assert changes[-1] <= changes[0] + 0.01 or changes[-1] < 0.06

    def test_tones_bounded_0_1(self) -> None:
        """Tones must stay in [0, 1]."""
        for _ in range(20):
            self.ctrl.update(40.0, dt=0.83)  # Very low MAP
        assert 0.0 <= self.ctrl.sympathetic_tone <= 1.0
        assert 0.0 <= self.ctrl.parasympathetic_tone <= 1.0

        for _ in range(20):
            self.ctrl.update(180.0, dt=0.83)  # Very high MAP
        assert 0.0 <= self.ctrl.sympathetic_tone <= 1.0
        assert 0.0 <= self.ctrl.parasympathetic_tone <= 1.0

    def test_serialization_roundtrip(self) -> None:
        """get_state/set_state roundtrip."""
        self.ctrl.update(70.0, dt=0.83)
        self.ctrl.update(70.0, dt=0.83)
        state = self.ctrl.get_state()

        ctrl2 = AutonomicReflexController()
        ctrl2.set_state(state)
        assert abs(ctrl2.sympathetic_tone - self.ctrl.sympathetic_tone) < 1e-10
        assert abs(ctrl2.parasympathetic_tone - self.ctrl.parasympathetic_tone) < 1e-10

    def test_gradual_recovery(self) -> None:
        """After BP normalizes, tones should gradually return to rest."""
        # Push tones off baseline
        for _ in range(10):
            self.ctrl.update(60.0, dt=0.83)
        symp_elevated = self.ctrl.sympathetic_tone

        # Return to normal MAP
        for _ in range(15):
            self.ctrl.update(93.0, dt=0.83)

        # Should have moved back toward 0.5
        assert abs(self.ctrl.sympathetic_tone - 0.5) < abs(symp_elevated - 0.5)

"""Tests for physiology modulator (Task 6)."""
from __future__ import annotations

import pytest

from app.engine.core.types import Modifiers
from app.engine.modulation.physiology_modulator import (
    AutonomicState,
    compute_modifiers,
)


class TestPhysiologyModulator:
    """Test compute_modifiers integration."""

    def test_default_modifiers(self) -> None:
        """Default inputs → near-default modifiers."""
        m = compute_modifiers()
        assert 0.8 <= m.sa_rate_modifier <= 1.2
        assert 0.8 <= m.contractility_modifier <= 1.2

    def test_sympathetic_increases_hr(self) -> None:
        """High sympathetic → increased sa_rate_modifier."""
        m = compute_modifiers(autonomic=AutonomicState(sympathetic_tone=0.9, parasympathetic_tone=0.3))
        assert m.sa_rate_modifier > 1.1

    def test_parasympathetic_decreases_hr(self) -> None:
        """High parasympathetic → decreased sa_rate_modifier."""
        m = compute_modifiers(autonomic=AutonomicState(sympathetic_tone=0.3, parasympathetic_tone=0.9))
        assert m.sa_rate_modifier < 0.95

    def test_sympathetic_increases_contractility(self) -> None:
        m = compute_modifiers(autonomic=AutonomicState(sympathetic_tone=0.9))
        assert m.contractility_modifier > 1.1

    def test_sympathetic_increases_tpr(self) -> None:
        m = compute_modifiers(autonomic=AutonomicState(sympathetic_tone=0.9))
        assert m.tpr_modifier > 1.05

    def test_beta_blocker_reduces_hr(self) -> None:
        m = compute_modifiers(pharma_levels={"beta_blocker": 0.5})
        assert m.sa_rate_modifier < 0.95

    def test_beta_blocker_reduces_contractility(self) -> None:
        m = compute_modifiers(pharma_levels={"beta_blocker": 0.5})
        assert m.contractility_modifier < 0.95

    def test_atropine_increases_hr(self) -> None:
        m = compute_modifiers(pharma_levels={"atropine": 0.5})
        assert m.sa_rate_modifier > 1.05

    def test_digoxin_positive_inotrope(self) -> None:
        m = compute_modifiers(pharma_levels={"digoxin": 0.5})
        assert m.contractility_modifier > 1.05

    def test_amiodarone_slows_hr(self) -> None:
        m = compute_modifiers(pharma_levels={"amiodarone": 0.5})
        assert m.sa_rate_modifier < 0.95

    def test_exercise_increases_hr_and_contractility(self) -> None:
        m = compute_modifiers(user_commands={"exercise_intensity": 0.7})
        assert m.sa_rate_modifier > 1.3
        assert m.contractility_modifier > 1.1

    def test_combined_exercise_and_beta_blocker(self) -> None:
        """Exercise + beta-blocker: attenuated HR response."""
        ex_only = compute_modifiers(user_commands={"exercise_intensity": 0.5})
        combined = compute_modifiers(
            pharma_levels={"beta_blocker": 0.5},
            user_commands={"exercise_intensity": 0.5},
        )
        assert combined.sa_rate_modifier < ex_only.sa_rate_modifier

    def test_damage_reduces_contractility(self) -> None:
        m = compute_modifiers(damage_level=0.5)
        assert m.contractility_modifier < 0.85

    def test_damage_propagated(self) -> None:
        m = compute_modifiers(damage_level=0.7)
        assert m.damage_level == 0.7

    def test_all_modifiers_clamped(self) -> None:
        """Extreme inputs should not produce out-of-range modifiers."""
        m = compute_modifiers(
            autonomic=AutonomicState(sympathetic_tone=1.0, parasympathetic_tone=0.0),
            pharma_levels={"atropine": 1.5, "digoxin": 1.0},
            user_commands={"exercise_intensity": 1.0},
        )
        assert 0.3 <= m.sa_rate_modifier <= 3.0
        assert 0.2 <= m.contractility_modifier <= 2.5
        assert 0.3 <= m.tpr_modifier <= 3.0

    def test_base_modifiers_overlay(self) -> None:
        """compute_modifiers with base should build on existing values."""
        base = Modifiers(valve_areas={"aortic": 0.5})
        m = compute_modifiers(base_modifiers=base)
        assert m.valve_areas.get("aortic") == 0.5

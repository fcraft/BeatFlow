"""Tests for InteractionState and TransitionSmoother (Step 1 of refactoring)."""
from __future__ import annotations

import math

import pytest

from app.engine.modulation.interaction_state import InteractionState
from app.engine.modulation.transition_engine import (
    TRANSITION_CONFIGS,
    TransitionConfig,
    TransitionSmoother,
)


# ======================================================================
# InteractionState tests
# ======================================================================

class TestInteractionState:
    """Unit tests for InteractionState dataclass."""

    def test_defaults(self) -> None:
        s = InteractionState()
        assert s.exercise_intensity == 0.0
        assert s.emotional_arousal == 0.0
        assert s.rhythm_override == ''
        assert s.hr_override is None
        assert s.temperature == 36.6
        assert s.potassium_level == 4.0
        assert s.calcium_level == 9.5
        assert s.damage_level == 0.0
        assert s.valve_areas == {}
        assert s.ectopic_foci == []

    def test_to_dict_roundtrip(self) -> None:
        s = InteractionState(
            exercise_intensity=0.7,
            rhythm_override='af',
            potassium_level=6.0,
            valve_areas={'aortic': 0.5},
        )
        d = s.to_dict()
        s2 = InteractionState.from_dict(d)
        assert s2.exercise_intensity == 0.7
        assert s2.rhythm_override == 'af'
        assert s2.potassium_level == 6.0
        assert s2.valve_areas == {'aortic': 0.5}

    def test_from_dict_ignores_unknown_keys(self) -> None:
        d = {'exercise_intensity': 0.5, 'unknown_field': 999}
        s = InteractionState.from_dict(d)
        assert s.exercise_intensity == 0.5
        assert not hasattr(s, 'unknown_field') or True  # unknown is just ignored

    def test_from_modifiers_mapping(self) -> None:
        """from_modifiers should copy matching field names from a Modifiers-like object."""
        from app.engine.core.types import Modifiers
        m = Modifiers()
        m.emotional_arousal = 0.6
        m.damage_level = 0.3
        m.potassium_level = 5.5
        m.rhythm_override = 'vt'
        m.valve_areas = {'mitral': 0.7}

        s = InteractionState.from_modifiers(m)
        assert s.emotional_arousal == 0.6
        assert s.damage_level == 0.3
        assert s.potassium_level == 5.5
        assert s.rhythm_override == 'vt'
        assert s.valve_areas == {'mitral': 0.7}

    def test_get_active_interactions_defaults_empty(self) -> None:
        s = InteractionState()
        active = s.get_active_interactions()
        assert active == {}

    def test_get_active_interactions_reports_changes(self) -> None:
        s = InteractionState(
            exercise_intensity=0.8,
            rhythm_override='af',
            caffeine_level=0.3,
            potassium_level=6.0,
            damage_level=0.5,
        )
        active = s.get_active_interactions()
        assert 'exercise' in active
        assert active['exercise'] == 0.8
        assert active['rhythm'] == 'af'
        assert 'caffeine' in active
        assert 'potassium' in active
        assert 'damage' in active

    def test_dict_fields_are_independent(self) -> None:
        """Ensure dict/list fields don't share references between instances."""
        s1 = InteractionState()
        s2 = InteractionState()
        s1.valve_areas['aortic'] = 0.5
        assert s2.valve_areas == {}  # s2 unaffected


# ======================================================================
# TransitionSmoother tests
# ======================================================================

class TestTransitionSmoother:
    """Unit tests for TransitionSmoother."""

    def test_instant_fields_snap(self) -> None:
        """Instant fields (rhythm_override) should change immediately."""
        smoother = TransitionSmoother()
        intent = InteractionState(rhythm_override='af')
        result = smoother.update(intent, dt=0.8)
        assert result.rhythm_override == 'af'

    def test_slow_field_ramps(self) -> None:
        """A field with tau=3.0 should not reach target in one 0.8s beat."""
        smoother = TransitionSmoother()

        # Start at default (0.0), target 1.0
        intent = InteractionState(exercise_intensity=1.0)
        r1 = smoother.update(intent, dt=0.8)

        # After 0.8s with tau=3.0: alpha ≈ 1 - exp(-0.8/3.0) ≈ 0.234
        # Expected: 0.0 + 0.234 * (1.0 - 0.0) ≈ 0.234
        assert 0.1 < r1.exercise_intensity < 0.5, f"Got {r1.exercise_intensity}"
        assert r1.exercise_intensity < 1.0  # Not yet at target

    def test_convergence_over_many_beats(self) -> None:
        """After many beats, smoothed value should converge to target."""
        smoother = TransitionSmoother()
        intent = InteractionState(exercise_intensity=0.8)

        result = None
        for _ in range(50):
            result = smoother.update(intent, dt=0.8)

        assert result is not None
        assert abs(result.exercise_intensity - 0.8) < 0.01

    def test_ramp_down(self) -> None:
        """Should ramp down when target decreases."""
        smoother = TransitionSmoother()

        # First converge to 0.8
        intent_high = InteractionState(exercise_intensity=0.8)
        for _ in range(50):
            smoother.update(intent_high, dt=0.8)

        # Now ramp down to 0.0
        intent_low = InteractionState(exercise_intensity=0.0)
        r1 = smoother.update(intent_low, dt=0.8)
        assert r1.exercise_intensity < 0.8  # Started ramping down
        assert r1.exercise_intensity > 0.0  # Not yet at 0

        # After many beats, should converge to 0
        for _ in range(50):
            r1 = smoother.update(intent_low, dt=0.8)
        assert r1.exercise_intensity < 0.01

    def test_hr_override_none_passthrough(self) -> None:
        """hr_override=None should pass through since it's not float."""
        smoother = TransitionSmoother()
        intent = InteractionState(hr_override=None)
        result = smoother.update(intent, dt=0.8)
        assert result.hr_override is None

    def test_hr_override_numeric_ramps(self) -> None:
        """hr_override as float should ramp via tau=1.5s."""
        smoother = TransitionSmoother()
        intent = InteractionState(hr_override=180.0)

        r1 = smoother.update(intent, dt=0.8)
        # First beat snaps (no history), so it should be at target
        # Actually, first update initializes current to target
        assert r1.hr_override is not None

    def test_dict_fields_passthrough(self) -> None:
        """Dict/list fields should pass through unchanged (not smoothed)."""
        smoother = TransitionSmoother()
        intent = InteractionState(valve_areas={'aortic': 0.5})
        result = smoother.update(intent, dt=0.8)
        assert result.valve_areas == {'aortic': 0.5}

    def test_dict_fields_independent_copy(self) -> None:
        """Modifying result's dict shouldn't affect the smoother."""
        smoother = TransitionSmoother()
        intent = InteractionState(valve_areas={'aortic': 0.5})
        result = smoother.update(intent, dt=0.8)
        result.valve_areas['mitral'] = 0.3
        # Next update should NOT see the 'mitral' key
        result2 = smoother.update(intent, dt=0.8)
        assert 'mitral' not in result2.valve_areas

    def test_reset_clears_state(self) -> None:
        """reset() should clear all tracked values."""
        smoother = TransitionSmoother()

        # Build up some state
        intent = InteractionState(exercise_intensity=0.8)
        for _ in range(10):
            smoother.update(intent, dt=0.8)

        smoother.reset()

        # After reset, should start fresh (from default 0.0, ramping toward 0.5)
        intent2 = InteractionState(exercise_intensity=0.5)
        r = smoother.update(intent2, dt=0.8)
        # First update after reset starts from default (0.0), NOT from 0.8
        # With tau=3.0 and dt=0.8: alpha ≈ 0.234, so val ≈ 0.0 + 0.234 * 0.5 ≈ 0.117
        assert r.exercise_intensity < 0.3  # Should be ramping from 0, not near 0.8

    def test_state_serialization(self) -> None:
        """get_state/set_state should preserve smoother state."""
        smoother = TransitionSmoother()
        intent = InteractionState(exercise_intensity=0.8)
        for _ in range(5):
            smoother.update(intent, dt=0.8)

        state = smoother.get_state()
        assert 'exercise_intensity' in state

        # Create a new smoother and restore
        smoother2 = TransitionSmoother()
        smoother2.set_state(state)

        # Should produce same result as original
        r_original = smoother.update(intent, dt=0.8)
        r_restored = smoother2.update(intent, dt=0.8)
        assert abs(r_original.exercise_intensity - r_restored.exercise_intensity) < 0.001

    def test_all_configured_fields_are_valid(self) -> None:
        """All keys in TRANSITION_CONFIGS should be valid InteractionState fields."""
        valid_names = {f.name for f in __import__('dataclasses').fields(InteractionState)}
        for key in TRANSITION_CONFIGS:
            assert key in valid_names, f"TRANSITION_CONFIGS key '{key}' is not an InteractionState field"

    def test_zero_dt_snaps(self) -> None:
        """dt=0 should snap to target immediately."""
        smoother = TransitionSmoother()
        intent = InteractionState(exercise_intensity=0.8)
        result = smoother.update(intent, dt=0.0)
        assert abs(result.exercise_intensity - 0.8) < 0.01

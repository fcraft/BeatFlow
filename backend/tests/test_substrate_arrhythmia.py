"""Tests for substrate-triggered probabilistic arrhythmia episodes."""
import random

import pytest

from app.engine.core.parametric_conduction import ParametricConductionNetwork as ConductionNetworkV2
from app.engine.core.types import Modifiers


def _run_beats(net: ConductionNetworkV2, modifiers: Modifiers, n: int) -> list[str]:
    """Run n beats and return list of beat_kind strings."""
    kinds = []
    for _ in range(n):
        result = net.propagate(0.8, modifiers)
        kinds.append(result.beat_kind)
    return kinds


class TestSubstrateArrhythmia:
    """Test substrate-driven arrhythmia trigger logic."""

    def test_zero_substrate_never_triggers(self):
        """All substrates=0 → 200 beats should all be sinus."""
        random.seed(42)
        net = ConductionNetworkV2()
        mods = Modifiers(af_substrate=0.0, svt_substrate=0.0, vt_substrate=0.0)
        kinds = _run_beats(net, mods, 200)
        assert all(k == 'sinus' for k in kinds), f"Got non-sinus beats: {set(kinds)}"

    def test_high_af_substrate_triggers_af(self):
        """af_substrate=0.9 over 100 beats should produce at least one AF episode."""
        random.seed(123)
        net = ConductionNetworkV2()
        mods = Modifiers(af_substrate=0.9, svt_substrate=0.0, vt_substrate=0.0)
        kinds = _run_beats(net, mods, 100)
        assert 'af' in kinds, f"Expected AF in 100 beats with substrate=0.9, got: {set(kinds)}"

    def test_rhythm_override_takes_precedence(self):
        """Explicit rhythm_override='vt' should override substrate triggers."""
        random.seed(42)
        net = ConductionNetworkV2()
        mods = Modifiers(
            rhythm_override='vt',
            af_substrate=1.0,
            svt_substrate=1.0,
            vt_substrate=1.0,
        )
        kinds = _run_beats(net, mods, 20)
        # All beats should be VT from override, not AF or SVT from substrate
        assert all(k == 'vt' for k in kinds), f"Expected all vt, got: {kinds}"

    def test_episode_cooldown_prevents_rapid_retrigger(self):
        """After an episode ends, cooldown period should prevent immediate re-trigger."""
        random.seed(42)
        net = ConductionNetworkV2()
        # Force an episode by directly setting state
        net._episode_rhythm = 'af'
        net._episode_beats_remaining = 1  # Will end after 1 beat
        net._episode_cooldown = 0

        mods = Modifiers(af_substrate=1.0, svt_substrate=0.0, vt_substrate=0.0)

        # First beat: last beat of episode
        result = net.propagate(0.8, mods)
        assert result.beat_kind == 'af'

        # Episode just ended → cooldown should be active
        assert net._episode_cooldown > 0, "Cooldown should be set after episode ends"

        # During cooldown, beats should be sinus regardless of high substrate
        cooldown_beats = net._episode_cooldown
        sinus_count = 0
        for _ in range(cooldown_beats):
            result = net.propagate(0.8, mods)
            if result.beat_kind == 'sinus':
                sinus_count += 1
        # All cooldown beats should be sinus
        assert sinus_count == cooldown_beats, (
            f"Expected {cooldown_beats} sinus beats during cooldown, got {sinus_count}"
        )

    def test_episode_state_serialization(self):
        """get_state/set_state should round-trip preserve episode state."""
        net = ConductionNetworkV2()
        net._episode_rhythm = 'svt'
        net._episode_beats_remaining = 15
        net._episode_cooldown = 30
        net._wenckebach_counter = 2
        net._wenckebach_cycle = 5

        state = net.get_state()

        # Verify state dict contains episode fields
        assert state['episode_rhythm'] == 'svt'
        assert state['episode_beats_remaining'] == 15
        assert state['episode_cooldown'] == 30
        assert state['wenckebach_counter'] == 2
        assert state['wenckebach_cycle'] == 5

        # Restore into a fresh network
        net2 = ConductionNetworkV2()
        net2.set_state(state)

        assert net2._episode_rhythm == 'svt'
        assert net2._episode_beats_remaining == 15
        assert net2._episode_cooldown == 30
        assert net2._wenckebach_counter == 2
        assert net2._wenckebach_cycle == 5

    def test_probability_scales_quadratically(self):
        """substrate=0.1 vs 0.9 trigger rate difference should be significant.

        P(AF) = substrate² × 0.08
        At 0.1: 0.01 × 0.08 = 0.0008/beat
        At 0.9: 0.81 × 0.08 = 0.0648/beat
        Ratio ~81x, so over many beats, 0.9 should trigger far more often.
        """
        random.seed(999)

        # Low substrate: 500 beats
        net_low = ConductionNetworkV2()
        mods_low = Modifiers(af_substrate=0.1)
        kinds_low = _run_beats(net_low, mods_low, 500)
        af_count_low = kinds_low.count('af')

        # High substrate: 500 beats
        random.seed(999)
        net_high = ConductionNetworkV2()
        mods_high = Modifiers(af_substrate=0.9)
        kinds_high = _run_beats(net_high, mods_high, 500)
        af_count_high = kinds_high.count('af')

        # High substrate should produce significantly more AF beats
        assert af_count_high > af_count_low, (
            f"High substrate ({af_count_high} AF beats) should exceed "
            f"low substrate ({af_count_low} AF beats)"
        )

    def test_episode_duration_within_bounds(self):
        """When an episode triggers, its duration should be within expected range."""
        random.seed(42)
        net = ConductionNetworkV2()
        # Manually trigger an AF episode
        net._episode_rhythm = 'af'
        net._episode_beats_remaining = 25  # Within AF range [10, 50]

        mods = Modifiers()  # no substrate needed, episode already active
        af_beats = 0
        for _ in range(100):
            result = net.propagate(0.8, mods)
            if result.beat_kind == 'af':
                af_beats += 1

        # Should get exactly 25 AF beats (the remaining episode)
        assert af_beats == 25, f"Expected 25 AF beats, got {af_beats}"

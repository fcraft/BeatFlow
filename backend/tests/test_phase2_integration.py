"""Integration tests for Phase 2 interaction refactoring.

Tests the full pipeline flow: apply_command → intent → transition →
compute_modifiers → physics layers → ECG/PCG output.

Verifies:
1. Intent-based commands propagate through the beat generation pipeline
2. TransitionSmoother produces gradual parameter changes
3. PCG improvements: multi-modal synthesis, AGC, crossfade, PR-S1 coupling
4. Valve debounce at high HR works correctly
5. Snapshot/restore with new intent architecture
"""
from __future__ import annotations

import numpy as np
import pytest

from app.engine.core.types import Modifiers
from app.engine.core.parametric_pcg import (
    ParametricPcgSynthesizer,
    _add_modal_burst,
    M1_MODES,
)
from app.engine.modulation.interaction_state import InteractionState
from app.engine.modulation.physiology_modulator import (
    AutonomicState,
    compute_modifiers,
)
from app.engine.modulation.transition_engine import TransitionSmoother
from app.engine.simulation.pipeline import SimulationPipeline


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_pipeline() -> SimulationPipeline:
    """Create pipeline with layers initialized."""
    p = SimulationPipeline()
    p._ensure_layers()
    return p


def run_beats(pipeline: SimulationPipeline, n: int = 3) -> None:
    """Run n beats on the pipeline to push intent through modulation."""
    for _ in range(n):
        pipeline._run_one_beat()


# ===========================================================================
# 1. Intent → Modifiers propagation
# ===========================================================================

class TestIntentPropagation:
    """Verify that commands written to intent propagate to modifiers."""

    def test_exercise_propagates_to_hr(self):
        """Running should increase HR through intent → modifiers pipeline."""
        p = make_pipeline()
        run_beats(p, 2)  # Baseline
        baseline_hr = p._vitals.get("heart_rate", 72)

        p.apply_command("run", {})
        run_beats(p, 5)  # Let transition smooth
        exercise_hr = p._vitals.get("heart_rate", 72)

        # Exercise should increase HR (even partially due to smoothing)
        assert exercise_hr > baseline_hr, (
            f"Expected HR to increase from {baseline_hr} with exercise, got {exercise_hr}"
        )

    def test_af_rhythm_propagates(self):
        """AF condition should change beat rhythm."""
        p = make_pipeline()
        p.apply_command("condition_af", {})
        run_beats(p, 3)

        # The modifiers should reflect AF
        assert p._modifiers.rhythm_override == 'af'

    def test_electrolyte_changes_propagate(self):
        """Hyperkalemia should affect AV delay."""
        p = make_pipeline()
        run_beats(p, 2)

        p.apply_command("hyperkalemia", {"level": 6.5})
        run_beats(p, 5)  # Let transition smooth

        # Potassium should be approaching target (smoothed)
        assert p._modifiers.potassium_level > 4.5, (
            f"Expected elevated K+, got {p._modifiers.potassium_level}"
        )

    def test_reset_clears_everything(self):
        """Reset should return intent and modifiers to defaults."""
        p = make_pipeline()
        p.apply_command("run", {})
        p.apply_command("condition_af", {})
        p.apply_command("hyperkalemia", {})

        p.apply_command("reset", {})
        # Intent should be default
        assert p._intent.exercise_intensity == 0.0
        assert p._intent.rhythm_override == ''
        assert p._intent.potassium_level == 4.0
        # Modifiers should be reset
        assert p._modifiers.exercise_intensity == 0.0


# ===========================================================================
# 2. Transition smoothing integration
# ===========================================================================

class TestTransitionIntegration:
    """Verify that intent changes ramp gradually, not snap."""

    def test_exercise_ramps_gradually(self):
        """Exercise intensity should not jump to full immediately."""
        p = make_pipeline()
        run_beats(p, 2)  # Baseline beats to initialize modulation

        p.apply_command("run", {})  # intent.exercise_intensity = 0.8
        # Run exactly one beat to see partial ramp
        p._run_one_beat()

        # After one beat, exercise_intensity on modifiers should be
        # partially ramped (not 0 and not fully 0.8)
        ei = p._modifiers.exercise_intensity
        # The exact value depends on RR interval and tau=3s
        # At ~72bpm (RR=0.83s), alpha = 1 - exp(-0.83/3) ≈ 0.24
        # So exercise_intensity ≈ 0.24 * 0.8 ≈ 0.19
        assert 0.05 < ei < 0.8, (
            f"Expected partial ramp, got exercise_intensity={ei}"
        )

    def test_rhythm_override_snaps_instantly(self):
        """Rhythm override should apply immediately (instant transition)."""
        p = make_pipeline()
        p.apply_command("condition_vf", {})
        run_beats(p, 1)

        # Rhythm should snap immediately
        assert p._modifiers.rhythm_override == 'vf'


# ===========================================================================
# 3. compute_modifiers with InteractionState
# ===========================================================================

class TestComputeModifiersWithInteraction:
    """Verify compute_modifiers uses InteractionState correctly."""

    def test_interaction_exercise_affects_hr(self):
        intent = InteractionState(exercise_intensity=0.7)
        m = compute_modifiers(
            autonomic=AutonomicState(),
            interaction=intent,
        )
        assert m.sa_rate_modifier > 1.3

    def test_interaction_electrolytes_affect_av_delay(self):
        intent = InteractionState(potassium_level=6.5)
        m = compute_modifiers(
            autonomic=AutonomicState(),
            interaction=intent,
        )
        assert m.av_delay_modifier > 1.0

    def test_interaction_preload_override(self):
        intent = InteractionState(preload_override=0.7)
        m = compute_modifiers(
            autonomic=AutonomicState(),
            interaction=intent,
        )
        assert m.preload_modifier == pytest.approx(0.7, abs=0.05)

    def test_interaction_damage_propagates(self):
        intent = InteractionState(damage_level=0.6)
        m = compute_modifiers(
            autonomic=AutonomicState(),
            interaction=intent,
        )
        assert m.damage_level >= 0.6
        assert m.contractility_modifier < 1.0  # Damage reduces contractility

    def test_legacy_user_commands_still_work(self):
        """Old-style user_commands should still function without interaction."""
        m = compute_modifiers(
            user_commands={"exercise_intensity": 0.5},
        )
        assert m.sa_rate_modifier > 1.2


# ===========================================================================
# 4. (removed: valve debounce tests — V3 uses parametric timing)
# ===========================================================================


# ===========================================================================
# 5. PCG quality: multi-modal synthesis
# ===========================================================================

class TestPCGMultiModal:
    """Verify multi-modal synthesis produces richer spectra."""

    def test_modal_burst_produces_output(self):
        buf = np.zeros(4000, dtype=np.float64)
        _add_modal_burst(buf, 100, M1_MODES, 80.0, 0.5, 4000)
        assert np.max(np.abs(buf)) > 0.01

    def test_modal_burst_has_multiple_frequencies(self):
        """FFT of modal burst should show energy at multiple frequencies."""
        buf = np.zeros(4000, dtype=np.float64)
        _add_modal_burst(buf, 0, M1_MODES, 80.0, 1.0, 4000)
        fft = np.abs(np.fft.rfft(buf))
        freqs = np.fft.rfftfreq(len(buf), 1.0 / 4000)

        # Check for energy near each mode frequency (±10Hz)
        for mode_freq, _, _ in M1_MODES:
            mask = (freqs > mode_freq - 15) & (freqs < mode_freq + 15)
            energy = np.sum(fft[mask])
            assert energy > 0.1, f"Expected energy near {mode_freq}Hz"


# ===========================================================================
# 6. PCG AGC via V3 pipeline integration
# ===========================================================================

class TestPCGAGCCrossfade:
    """Verify V3 PCG synthesizer AGC works through pipeline integration."""

    def test_agc_produces_nonzero_pcg(self):
        """Pipeline should produce non-silent PCG with AGC."""
        p = make_pipeline()
        run_beats(p, 5)
        # Check PCG buffer has data
        assert len(p._pcg_buf) > 0, "PCG buffer should not be empty after 5 beats"


# ===========================================================================
# 7. Snapshot roundtrip with new architecture
# ===========================================================================

class TestSnapshotPhase2:
    """Verify snapshot saves and restores intent + transition state."""

    def test_intent_persists_across_snapshot(self):
        p1 = make_pipeline()
        p1.apply_command("run", {})
        p1.apply_command("condition_af", {})
        p1.apply_command("hyperkalemia", {"level": 6.5})
        run_beats(p1, 3)

        snap = p1.get_snapshot()
        assert "intent_state" in snap
        assert "transition_state" in snap

        p2 = SimulationPipeline(snapshot=snap)
        # Intent should be preserved
        assert p2._intent.exercise_intensity == pytest.approx(
            p1._intent.exercise_intensity, abs=0.01
        )
        assert p2._intent.rhythm_override == 'af'
        assert p2._intent.potassium_level == pytest.approx(6.5, abs=0.1)

    def test_transition_state_persists(self):
        p1 = make_pipeline()
        p1.apply_command("run", {})
        run_beats(p1, 3)  # Let smoother accumulate state

        snap = p1.get_snapshot()
        p2 = SimulationPipeline(snapshot=snap)

        # Transition state should be restored
        t1_state = p1._transition.get_state()
        t2_state = p2._transition.get_state()
        for key in t1_state:
            assert key in t2_state
            assert t2_state[key] == pytest.approx(t1_state[key], abs=0.01)


# ===========================================================================
# 8. (removed: PR-S1 coupling tests — V3 uses parametric PCG timing)
# ===========================================================================


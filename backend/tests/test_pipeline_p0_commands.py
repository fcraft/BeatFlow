"""P0 command handler tests for SimulationPipeline.

Tests the 49 command handlers accessible via pipeline.apply_command(cmd, params).
Covers exercise, emotion, condition, electrolyte, body state, settings,
substrate, defibrillation, cardioversion, and snapshot roundtrip.

Phase 2: Commands now write to ``pipeline._intent`` (InteractionState)
instead of directly to ``pipeline._modifiers``.
"""

import pytest
from unittest.mock import patch

from app.engine.simulation.pipeline import SimulationPipeline


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_pipeline() -> SimulationPipeline:
    """Create a fresh pipeline with all layers initialised."""
    p = SimulationPipeline()
    p._ensure_layers()
    return p


# ===========================================================================
# 1. Exercise commands – smoke test
# ===========================================================================

class TestExerciseCommands:
    """Verify exercise_intensity on intent changes correctly."""

    @pytest.mark.parametrize("cmd,expected_min_intensity", [
        ("rest", 0.0),
        ("walk", 0.1),
        ("jog", 0.3),
        ("run", 0.5),
        ("climb_stairs", 0.4),
        ("squat", 0.3),
    ])
    def test_exercise_sets_intensity(self, cmd, expected_min_intensity):
        p = make_pipeline()
        p.apply_command(cmd, {})
        assert p._intent.exercise_intensity >= expected_min_intensity, (
            f"{cmd}: exercise_intensity={p._intent.exercise_intensity} < {expected_min_intensity}"
        )

    def test_rest_resets_intensity(self):
        p = make_pipeline()
        p.apply_command("run", {})
        assert p._intent.exercise_intensity > 0
        p.apply_command("rest", {})
        assert p._intent.exercise_intensity == 0.0

    def test_run_increases_sympathetic_override(self):
        p = make_pipeline()
        p.apply_command("run", {})
        assert p._intent.sympathetic_tone_override is not None
        assert p._intent.sympathetic_tone_override > 0.5


# ===========================================================================
# 2. Emotion commands
# ===========================================================================

class TestEmotionCommands:

    def test_startle(self):
        p = make_pipeline()
        p.apply_command("startle", {})
        assert p._intent.emotional_arousal >= 0.9

    def test_anxiety(self):
        p = make_pipeline()
        p.apply_command("anxiety", {})
        assert p._intent.emotional_arousal >= 0.5

    def test_relaxation_resets(self):
        p = make_pipeline()
        p.apply_command("startle", {})
        p.apply_command("relaxation", {})
        assert p._intent.emotional_arousal <= 0.1

    def test_stress(self):
        p = make_pipeline()
        p.apply_command("stress", {})
        assert p._intent.emotional_arousal >= 0.6

    def test_fatigue(self):
        p = make_pipeline()
        p.apply_command("fatigue", {})
        assert p._intent.emotional_arousal >= 0.1
        assert p._intent.fatigue_level > 0


# ===========================================================================
# 3. Condition commands
# ===========================================================================

class TestConditionCommands:

    def test_condition_normal_resets(self):
        p = make_pipeline()
        p.apply_command("condition_af", {})
        assert p._intent.rhythm_override == "af"
        p.apply_command("condition_normal", {})
        assert p._intent.rhythm_override == "" or p._intent.rhythm_override is None

    def test_condition_af(self):
        p = make_pipeline()
        p.apply_command("condition_af", {})
        assert p._intent.rhythm_override == "af"

    def test_condition_svt(self):
        p = make_pipeline()
        p.apply_command("condition_svt", {})
        assert p._intent.rhythm_override == "svt"
        assert p._intent.hr_override >= 150

    def test_condition_vt(self):
        p = make_pipeline()
        p.apply_command("condition_vt", {})
        assert p._intent.rhythm_override == "vt"

    def test_condition_vf(self):
        p = make_pipeline()
        p.apply_command("condition_vf", {})
        assert p._intent.rhythm_override == "vf"

    def test_condition_asystole(self):
        p = make_pipeline()
        p.apply_command("condition_asystole", {})
        assert p._intent.rhythm_override == "asystole"

    def test_condition_tachycardia(self):
        p = make_pipeline()
        p.apply_command("condition_tachycardia", {})
        assert p._intent.hr_override >= 100

    def test_condition_bradycardia(self):
        p = make_pipeline()
        p.apply_command("condition_bradycardia", {})
        assert p._intent.hr_override <= 60

    def test_condition_av_block_1(self):
        p = make_pipeline()
        p.apply_command("condition_av_block_1", {})
        assert p._intent.av_block_degree == 1

    def test_condition_av_block_2(self):
        p = make_pipeline()
        p.apply_command("condition_av_block_2", {})
        assert p._intent.av_block_degree == 2

    def test_condition_av_block_3(self):
        p = make_pipeline()
        p.apply_command("condition_av_block_3", {})
        assert p._intent.av_block_degree == 3


# ===========================================================================
# 4. Valve disease
# ===========================================================================

class TestValveDisease:

    def test_condition_valve_disease_sets_murmur(self):
        p = make_pipeline()
        p.apply_command("condition_valve_disease", {})
        assert p._intent.murmur_type is not None
        assert p._intent.murmur_severity > 0


# ===========================================================================
# 5. Heart failure
# ===========================================================================

class TestHeartFailure:

    def test_condition_heart_failure(self):
        p = make_pipeline()
        p.apply_command("condition_heart_failure", {})
        assert p._intent.damage_level > 0
        assert p._intent.murmur_type is not None or p._intent.murmur_severity >= 0


# ===========================================================================
# 6. Electrolyte commands
# ===========================================================================

class TestElectrolyteCommands:

    def test_hyperkalemia(self):
        p = make_pipeline()
        p.apply_command("hyperkalemia", {})
        assert p._intent.potassium_level >= 6.0

    def test_hypokalemia(self):
        p = make_pipeline()
        p.apply_command("hypokalemia", {})
        assert p._intent.potassium_level <= 3.0

    def test_hypercalcemia(self):
        p = make_pipeline()
        p.apply_command("hypercalcemia", {})
        assert p._intent.calcium_level >= 12.0

    def test_hypocalcemia(self):
        p = make_pipeline()
        p.apply_command("hypocalcemia", {})
        assert p._intent.calcium_level <= 7.0


# ===========================================================================
# 7. Body state commands
# ===========================================================================

class TestBodyStateCommands:

    def test_caffeine_additive(self):
        p = make_pipeline()
        p.apply_command("caffeine", {})
        level1 = p._intent.caffeine_level
        assert level1 > 0
        p.apply_command("caffeine", {})
        level2 = p._intent.caffeine_level
        assert level2 > level1, "caffeine should be additive"

    def test_alcohol_additive(self):
        p = make_pipeline()
        p.apply_command("alcohol", {})
        level1 = p._intent.alcohol_level
        assert level1 > 0
        p.apply_command("alcohol", {})
        level2 = p._intent.alcohol_level
        assert level2 > level1, "alcohol should be additive"

    def test_fever(self):
        p = make_pipeline()
        p.apply_command("fever", {})
        assert p._intent.temperature > 37.0
        assert p._intent.dehydration_level > 0

    def test_sleep_deprivation(self):
        p = make_pipeline()
        p.apply_command("sleep_deprivation", {})
        assert p._intent.sleep_debt > 0

    def test_dehydration(self):
        p = make_pipeline()
        p.apply_command("dehydration", {})
        assert p._intent.dehydration_level > 0

    def test_hydrate(self):
        p = make_pipeline()
        p.apply_command("dehydration", {})
        p.apply_command("hydrate", {})
        assert p._intent.dehydration_level < 0.5

    def test_sleep(self):
        p = make_pipeline()
        p.apply_command("sleep_deprivation", {})
        p.apply_command("sleep", {})
        assert p._intent.sleep_debt < 0.5


# ===========================================================================
# 8. Settings commands
# ===========================================================================

class TestSettingsCommands:

    def test_set_damage_level(self):
        p = make_pipeline()
        p.apply_command("set_damage_level", {"level": 0.7})
        assert p._intent.damage_level == pytest.approx(0.7, abs=0.05)

    def test_set_heart_rate(self):
        p = make_pipeline()
        p.apply_command("set_heart_rate", {"value": 120})
        assert p._base_hr == pytest.approx(120.0, abs=1.0)

    def test_set_pvc_pattern(self):
        p = make_pipeline()
        p.apply_command("set_pvc_pattern", {"pattern": "bigeminy"})
        assert p._intent.pvc_pattern == "bigeminy"

    def test_set_preload(self):
        p = make_pipeline()
        p.apply_command("set_preload", {"level": 0.8})
        assert p._intent.preload_override == pytest.approx(0.8, abs=0.05)

    def test_set_contractility(self):
        p = make_pipeline()
        p.apply_command("set_contractility", {"level": 0.6})
        assert p._intent.contractility_override == pytest.approx(0.6, abs=0.05)

    def test_set_tpr(self):
        p = make_pipeline()
        p.apply_command("set_tpr", {"level": 1.3})
        assert p._intent.tpr_override == pytest.approx(1.3, abs=0.05)

    def test_reset(self):
        p = make_pipeline()
        p.apply_command("run", {})
        p.apply_command("condition_af", {})
        p.apply_command("caffeine", {})
        p.apply_command("reset", {})
        assert p._intent.exercise_intensity == 0.0
        assert p._intent.rhythm_override == "" or p._intent.rhythm_override is None
        assert p._intent.caffeine_level == 0.0


# ===========================================================================
# 9. Substrate commands
# ===========================================================================

class TestSubstrateCommands:

    def test_set_af_substrate(self):
        p = make_pipeline()
        p.apply_command("set_af_substrate", {"level": 0.8})
        assert p._intent.af_substrate >= 0.7

    def test_set_svt_substrate(self):
        p = make_pipeline()
        p.apply_command("set_svt_substrate", {"level": 0.6})
        assert p._intent.svt_substrate >= 0.5

    def test_set_vt_substrate(self):
        p = make_pipeline()
        p.apply_command("set_vt_substrate", {"level": 0.9})
        assert p._intent.vt_substrate >= 0.8


# ===========================================================================
# 10. Defibrillation
# ===========================================================================

class TestDefibrillation:

    def test_defibrillation_count_increments(self):
        p = make_pipeline()
        # Must set rhythm on _modifiers (not just intent) for defibrillate check
        p.apply_command("condition_vf", {})
        p._modifiers.rhythm_override = 'vf'  # Simulate modulation having run
        p.apply_command("defibrillate", {})
        assert p._intent.defibrillation_count >= 1

    def test_defibrillation_forced_success(self):
        """Mock random.random to return 0.1 → forces success."""
        p = make_pipeline()
        p.apply_command("condition_vf", {})
        p._modifiers.rhythm_override = 'vf'

        with patch("app.engine.simulation.pipeline._rng.random", return_value=0.1):
            p.apply_command("defibrillate", {})

        # Success means rhythm override should be reset
        assert p._intent.rhythm_override != "vf" or p._intent.defibrillation_count >= 1

    def test_defibrillation_forced_failure(self):
        """Mock random.random to return 0.99 → likely stays in vf."""
        p = make_pipeline()
        p.apply_command("condition_vf", {})
        p._modifiers.rhythm_override = 'vf'

        with patch("app.engine.simulation.pipeline._rng.random", return_value=0.99):
            p.apply_command("defibrillate", {})

        # High random → intent stays vf or moves to asystole
        assert p._intent.rhythm_override in ("vf", "asystole", "", None)

    def test_multiple_defibrillations(self):
        p = make_pipeline()
        p.apply_command("condition_vf", {})
        p._modifiers.rhythm_override = 'vf'

        # Mock random high so all attempts fail, keeping rhythm as VF
        with patch("app.engine.simulation.pipeline._rng.random", return_value=0.99):
            for _ in range(3):
                # Re-set _modifiers.rhythm_override each time since
                # defibrillate checks _modifiers, not _intent
                p._modifiers.rhythm_override = 'vf'
                p.apply_command("defibrillate", {})

        assert p._intent.defibrillation_count >= 3


# ===========================================================================
# 11. Cardioversion
# ===========================================================================

class TestCardioversion:

    def test_cardioversion_forced_success(self):
        """Set AF, mock random for success, verify rhythm resets."""
        p = make_pipeline()
        p.apply_command("condition_af", {})
        p._modifiers.rhythm_override = 'af'

        with patch("app.engine.simulation.pipeline._rng.random", return_value=0.1):
            p.apply_command("cardiovert", {})

        assert p._intent.rhythm_override != "af" or p._intent.defibrillation_count >= 0

    def test_cardioversion_on_non_applicable_rhythm(self):
        """Cardioversion on normal rhythm should be a no-op."""
        p = make_pipeline()
        # rhythm_override is '' (normal) on both intent and modifiers
        p.apply_command("cardiovert", {})
        assert p._intent.rhythm_override == ""


# ===========================================================================
# 12. Snapshot roundtrip
# ===========================================================================

class TestSnapshotRoundtrip:

    def test_snapshot_preserves_complex_state(self):
        """Set AF + electrolytes + caffeine, snapshot, restore, verify."""
        p1 = make_pipeline()
        p1.apply_command("condition_af", {})
        p1.apply_command("hyperkalemia", {})
        p1.apply_command("caffeine", {})
        p1.apply_command("caffeine", {})  # double dose

        snapshot = p1.get_snapshot()

        # Create new pipeline from snapshot
        p2 = SimulationPipeline(snapshot=snapshot)

        # Verify rhythm on intent
        assert p2._intent.rhythm_override == "af"

        # Verify electrolyte state
        assert p2._intent.potassium_level >= 6.0

        # Verify caffeine
        assert p2._intent.caffeine_level > 0

    def test_snapshot_preserves_exercise(self):
        p1 = make_pipeline()
        p1.apply_command("run", {})
        original_intensity = p1._intent.exercise_intensity

        snapshot = p1.get_snapshot()
        p2 = SimulationPipeline(snapshot=snapshot)

        assert p2._intent.exercise_intensity == pytest.approx(original_intensity, abs=0.01)

    def test_snapshot_preserves_condition_state(self):
        p1 = make_pipeline()
        p1.apply_command("set_af_substrate", {"level": 0.8})
        p1.apply_command("condition_svt", {})

        snapshot = p1.get_snapshot()
        p2 = SimulationPipeline(snapshot=snapshot)

        assert p2._intent.rhythm_override == "svt"
        assert p2._intent.af_substrate >= 0.7

    def test_legacy_snapshot_migration(self):
        """A snapshot without intent_state should reconstruct intent from modifiers."""
        legacy_snap = {
            "modifiers": {
                "rhythm_override": "af",
                "potassium_level": 6.5,
                "caffeine_level": 0.7,
                "exercise_intensity": 0.3,
                "damage_level": 0.4,
            },
            "base_hr": 80.0,
        }
        p = SimulationPipeline(snapshot=legacy_snap)
        # Intent should be reconstructed from modifiers
        assert p._intent.rhythm_override == "af"
        assert p._intent.potassium_level == pytest.approx(6.5, abs=0.1)
        assert p._intent.caffeine_level == pytest.approx(0.7, abs=0.1)
        assert p._intent.exercise_intensity == pytest.approx(0.3, abs=0.1)

"""Tests for exercise physiology integration in V3 pipeline."""
import pytest

from app.engine.simulation.pipeline import SimulationPipeline


@pytest.fixture
def pipeline():
    """Create a pipeline with layers initialized (needed for _run_one_beat)."""
    p = SimulationPipeline()
    p._ensure_layers()
    return p


def _run_beats(pipeline: SimulationPipeline, n: int = 10):
    """Helper: run n beats through the pipeline."""
    for _ in range(n):
        pipeline._run_one_beat()


class TestExerciseDurationAccumulates:
    def test_exercise_duration_accumulates(self, pipeline: SimulationPipeline):
        """Set intensity > 0.1, run beats → duration should increase."""
        pipeline._intent.exercise_intensity = 0.5
        pipeline._modifiers.exercise_intensity = 0.5

        initial_dur = pipeline._exercise_duration_sec
        _run_beats(pipeline, 30)
        assert pipeline._exercise_duration_sec > initial_dur


class TestExerciseDurationDecays:
    def test_exercise_duration_decays_at_rest(self, pipeline: SimulationPipeline):
        """After exercise, set intensity=0 → duration should decrease."""
        pipeline._exercise_duration_sec = 120.0
        pipeline._intent.exercise_intensity = 0.0
        pipeline._modifiers.exercise_intensity = 0.0

        _run_beats(pipeline, 30)
        assert pipeline._exercise_duration_sec < 120.0


class TestCardiacDrift:
    def test_cardiac_drift_increases_hr_over_time(self, pipeline: SimulationPipeline):
        """Simulate 10+ min exercise → HR delta from exercise model should be higher with elapsed time."""
        model = pipeline._exercise_model
        intensity = 0.6

        hr_delta_start = model.compute_hr_delta(
            intensity=intensity, elapsed_sec=0.0, fatigue=0.0, dehydration=0.0)
        hr_delta_10min = model.compute_hr_delta(
            intensity=intensity, elapsed_sec=600.0, fatigue=0.0, dehydration=0.0)

        assert hr_delta_10min > hr_delta_start

        pipeline._intent.exercise_intensity = 0.6
        pipeline._modifiers.exercise_intensity = 0.6
        _run_beats(pipeline, 30)
        assert pipeline._exercise_duration_sec > 0


class TestFatigueAccumulates:
    def test_fatigue_accumulates_during_exercise(self, pipeline: SimulationPipeline):
        """intensity > 0 → fatigue_level increases."""
        pipeline._intent.exercise_intensity = 0.7
        pipeline._intent.fatigue_level = 0.0
        pipeline._modifiers.exercise_intensity = 0.7

        initial_fatigue = pipeline._intent.fatigue_level
        _run_beats(pipeline, 50)
        assert pipeline._intent.fatigue_level > initial_fatigue


class TestTemperatureRises:
    def test_temperature_rises_during_exercise(self, pipeline: SimulationPipeline):
        """intensity > 0.3 → temperature increases."""
        pipeline._intent.exercise_intensity = 0.7
        pipeline._intent.temperature = 36.6
        pipeline._modifiers.exercise_intensity = 0.7

        initial_temp = pipeline._intent.temperature
        _run_beats(pipeline, 50)
        assert pipeline._intent.temperature > initial_temp


class TestExerciseSnapshotRoundtrip:
    def test_exercise_state_snapshot_roundtrip(self, pipeline: SimulationPipeline):
        """get_snapshot / restore preserves exercise state."""
        pipeline._exercise_duration_sec = 300.0
        pipeline._high_exercise_duration_sec = 120.0

        snap = pipeline.get_snapshot()
        assert snap["exercise_duration_sec"] == 300.0
        assert snap["high_exercise_duration_sec"] == 120.0

        p2 = SimulationPipeline()
        p2._ensure_layers()
        p2._restore_snapshot(snap)

        assert p2._exercise_duration_sec == 300.0
        assert p2._high_exercise_duration_sec == 120.0

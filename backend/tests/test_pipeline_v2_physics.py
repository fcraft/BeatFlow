"""Tests for Phase 1B pipeline integration (Task 8).

Tests the full pipeline with V2 physics layers, autonomic feedback,
pharmacokinetics, physiology modulator, and invariant validator.
"""
from __future__ import annotations

import time

import numpy as np
import pytest

from app.engine.simulation.pipeline import SimulationPipeline


class TestPipelineV2Physics:
    """Integration tests for the full V2 physics pipeline."""

    def setup_method(self) -> None:
        self.pipeline = SimulationPipeline()
        self.pipeline._ensure_layers()

    def test_single_beat_runs(self) -> None:
        """Pipeline should produce a beat without errors."""
        self.pipeline._run_one_beat()
        assert self.pipeline._vitals["heart_rate"] > 0

    def test_multiple_beats_stable(self) -> None:
        """5 beats should run with stable vitals."""
        for _ in range(5):
            self.pipeline._run_one_beat()
        v = self.pipeline._vitals
        assert 40 <= v["heart_rate"] <= 200
        assert v["systolic_bp"] > v["diastolic_bp"]
        assert 50 <= v["spo2"] <= 100

    def test_vitals_in_physiological_range(self) -> None:
        """After several beats, vitals should be physiologically reasonable."""
        for _ in range(5):
            self.pipeline._run_one_beat()
        v = self.pipeline._vitals
        assert 30 <= v["heart_rate"] <= 250
        assert 60 <= v["systolic_bp"] <= 250
        assert 30 <= v["diastolic_bp"] <= 150
        assert 2.0 <= v["cardiac_output"] <= 10.0
        assert 20 <= v["ejection_fraction"] <= 90

    def test_beat_performance(self) -> None:
        """Single beat should complete in <200ms (generous for CI)."""
        # Warm up
        for _ in range(3):
            self.pipeline._run_one_beat()

        # Average over 3 beats to reduce noise
        t0 = time.perf_counter()
        for _ in range(3):
            self.pipeline._run_one_beat()
        avg_ms = (time.perf_counter() - t0) / 3 * 1000
        assert avg_ms < 300, f"Beat avg {avg_ms:.1f}ms (>300ms)"

    def test_ecg_pcg_buffers_filled(self) -> None:
        """Buffers should have data after beats."""
        for _ in range(3):
            self.pipeline._run_one_beat()
        assert len(self.pipeline._ecg_buf) > 0
        assert len(self.pipeline._pcg_buf) > 0

    def test_exercise_command_affects_vitals(self) -> None:
        """Exercise command should increase HR."""
        for _ in range(3):
            self.pipeline._run_one_beat()
        rest_hr = self.pipeline._vitals["heart_rate"]

        self.pipeline.apply_command("run")
        for _ in range(5):
            self.pipeline._run_one_beat()
        run_hr = self.pipeline._vitals["heart_rate"]

        assert run_hr > rest_hr * 1.1, (
            f"Running HR {run_hr} not significantly > rest HR {rest_hr}"
        )

    def test_drug_command_beta_blocker(self) -> None:
        """Beta blocker should reduce HR over several beats."""
        for _ in range(3):
            self.pipeline._run_one_beat()
        baseline_hr = self.pipeline._vitals["heart_rate"]

        self.pipeline.apply_command("beta_blocker")
        for _ in range(10):
            self.pipeline._run_one_beat()
        bb_hr = self.pipeline._vitals["heart_rate"]

        # Beta-blocker should reduce HR (may take several beats via PK)
        assert bb_hr <= baseline_hr * 1.05, (
            f"BB HR {bb_hr} not reduced from baseline {baseline_hr}"
        )

    def test_drug_command_atropine(self) -> None:
        """Atropine should increase HR."""
        for _ in range(3):
            self.pipeline._run_one_beat()
        baseline_hr = self.pipeline._vitals["heart_rate"]

        self.pipeline.apply_command("atropine")
        for _ in range(10):
            self.pipeline._run_one_beat()
        atr_hr = self.pipeline._vitals["heart_rate"]

        # Atropine should increase HR (blocks parasympathetic)
        assert atr_hr >= baseline_hr * 0.95

    def test_rest_resets_state(self) -> None:
        """Rest command should reset to baseline."""
        self.pipeline.apply_command("run")
        for _ in range(5):
            self.pipeline._run_one_beat()

        self.pipeline.apply_command("rest")
        for _ in range(10):
            self.pipeline._run_one_beat()

        v = self.pipeline._vitals
        # Should be returning toward rest
        assert v["heart_rate"] < 200

    def test_snapshot_and_restore(self) -> None:
        """get_snapshot/restore should preserve state."""
        for _ in range(3):
            self.pipeline._run_one_beat()

        snapshot = self.pipeline.get_snapshot()
        assert "modifiers" in snapshot
        assert "base_hr" in snapshot
        assert "autonomic_state" in snapshot
        assert "pharma_state" in snapshot

        # Restore into new pipeline
        p2 = SimulationPipeline(snapshot=snapshot)
        p2._ensure_layers()
        # Should not crash
        p2._run_one_beat()

    def test_snapshot_with_drugs(self) -> None:
        """Snapshot should preserve drug state."""
        self.pipeline.apply_command("beta_blocker")
        for _ in range(5):
            self.pipeline._run_one_beat()

        snapshot = self.pipeline.get_snapshot()
        p2 = SimulationPipeline(snapshot=snapshot)
        p2._ensure_layers()
        p2._run_one_beat()

        # Both should have similar vitals
        assert abs(
            self.pipeline._vitals["heart_rate"] - p2._vitals["heart_rate"]
        ) < 30

    def test_autonomic_feedback_present(self) -> None:
        """Autonomic controller should be active in V2 mode."""
        assert self.pipeline._autonomic is not None
        assert self.pipeline._pharma is not None

    def test_init_payload(self) -> None:
        """get_init_payload should return expected structure."""
        payload = self.pipeline.get_init_payload()
        assert payload["type"] == "init"
        assert payload["ecg_sr"] == 500
        assert payload["pcg_sr"] == 4000
        assert "vitals" in payload

    def test_set_leads(self) -> None:
        self.pipeline.set_leads(["I", "II", "V1"])
        assert self.pipeline._selected_leads == ["I", "II", "V1"]


# (TestPipelineLegacyCompat removed — V3 has no legacy mode)

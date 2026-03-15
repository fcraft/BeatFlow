"""Tests for the v2 simulation pipeline."""
import asyncio
import time

import pytest

from app.engine.simulation.pipeline import SimulationPipeline


@pytest.fixture
def pipeline():
    return SimulationPipeline()


class TestPipelineLifecycle:
    def test_init_payload_has_v3_protocol(self, pipeline):
        payload = pipeline.get_init_payload()
        assert payload["stream_protocol"] == "sample-clock-v3"
        assert payload["type"] == "init"
        assert "vitals" in payload
        assert "ecg_sr" in payload
        assert "pcg_sr" in payload
        assert "available_leads" in payload
        assert "selected_leads" in payload

    async def test_start_and_stop(self, pipeline):
        messages: list[dict] = []

        async def send(msg):
            messages.append(msg)

        await pipeline.start(send)
        await asyncio.sleep(0.5)
        await pipeline.stop()
        assert len(messages) > 0

    async def test_signal_frames_have_required_fields(self, pipeline):
        messages: list[dict] = []

        async def send(msg):
            messages.append(msg)

        await pipeline.start(send)
        await asyncio.sleep(0.8)
        await pipeline.stop()
        signals = [m for m in messages if m.get("type") == "signal"]
        assert len(signals) > 0
        sig = signals[0]
        assert "ecg" in sig
        assert "pcg" in sig
        assert "vitals" in sig
        assert "ecg_start_sample" in sig
        assert "pcg_start_sample" in sig
        assert "seq" in sig

    async def test_ecg_pcg_are_lists_of_floats(self, pipeline):
        messages: list[dict] = []

        async def send(msg):
            messages.append(msg)

        await pipeline.start(send)
        await asyncio.sleep(0.5)
        await pipeline.stop()
        signals = [m for m in messages if m.get("type") == "signal"]
        assert len(signals) > 0
        sig = signals[0]
        assert isinstance(sig["ecg"], list)
        assert isinstance(sig["pcg"], list)
        assert len(sig["ecg"]) > 0
        assert len(sig["pcg"]) > 0

    def test_performance_one_beat(self, pipeline):
        """One beat pipeline run should be fast."""
        pipeline._ensure_layers()
        start = time.perf_counter()
        pipeline._run_one_beat()
        elapsed_ms = (time.perf_counter() - start) * 1000
        assert elapsed_ms < 200, f"One beat took {elapsed_ms:.1f}ms"


class TestPipelineCommands:
    def test_apply_command_no_crash(self, pipeline):
        pipeline.apply_command("rest")
        pipeline.apply_command("walk")
        pipeline.apply_command("jog")
        pipeline.apply_command("run")
        pipeline.apply_command("beta_blocker")
        pipeline.apply_command("unknown_command_should_not_crash")

    def test_set_leads(self, pipeline):
        pipeline.set_leads(["I", "II", "V1"])
        payload = pipeline.get_init_payload()
        assert set(payload["selected_leads"]) == {"I", "II", "V1"}

    def test_set_leads_default_fallback(self, pipeline):
        """Invalid leads should fall back to ['II']."""
        pipeline.set_leads(["INVALID"])
        payload = pipeline.get_init_payload()
        assert "II" in payload["selected_leads"]


class TestPipelineSnapshot:
    def test_get_snapshot_returns_dict(self, pipeline):
        pipeline._ensure_layers()
        pipeline._run_one_beat()
        snap = pipeline.get_snapshot()
        assert isinstance(snap, dict)
        assert "modifiers" in snap
        assert "conduction_state" in snap

    def test_restore_from_snapshot(self, pipeline):
        pipeline._ensure_layers()
        pipeline._run_one_beat()
        snap = pipeline.get_snapshot()
        # Create a new pipeline from snapshot
        p2 = SimulationPipeline(snapshot=snap)
        p2._ensure_layers()
        snap2 = p2.get_snapshot()
        assert snap2["modifiers"]["sa_rate_modifier"] == snap["modifiers"]["sa_rate_modifier"]

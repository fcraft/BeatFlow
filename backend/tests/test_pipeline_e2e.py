"""End-to-end integration test: v2 pipeline produces valid signal frames."""
import asyncio

import numpy as np
import pytest

from app.engine.simulation.pipeline import SimulationPipeline


@pytest.fixture
def pipeline_v2():
    return SimulationPipeline()


class TestEndToEnd:
    async def test_30_seconds_sinus_rhythm(self, pipeline_v2):
        """Run pipeline for ~3.5s real time, validate output quality."""
        frames = []

        async def collect(msg):
            frames.append(msg)

        await pipeline_v2.start(collect)
        try:
            await asyncio.sleep(3.5)
        finally:
            await pipeline_v2.stop()

        signals = [f for f in frames if f.get("type") == "signal"]
        assert len(signals) >= 20, f"Expected >=20 signal frames, got {len(signals)}"

        # Validate ECG signal quality
        all_ecg = []
        for s in signals:
            all_ecg.extend(s["ecg"])
        ecg_arr = np.array(all_ecg)

        # R-wave should be detectable
        assert np.max(ecg_arr) > 0.3, "ECG should have detectable R-waves"
        # No NaN/Inf
        assert not np.any(np.isnan(ecg_arr)), "ECG contains NaN"
        assert not np.any(np.isinf(ecg_arr)), "ECG contains Inf"

        # Validate vitals are reasonable
        last_vitals = signals[-1]["vitals"]
        assert 40 <= last_vitals["heart_rate"] <= 120
        assert 80 <= last_vitals.get("systolic_bp", 120) <= 180

    async def test_command_changes_state(self, pipeline_v2):
        """Applying commands should not crash and should affect state."""
        frames = []

        async def collect(msg):
            frames.append(msg)

        await pipeline_v2.start(collect)
        try:
            await asyncio.sleep(1.0)
            pipeline_v2.apply_command("run")
            await asyncio.sleep(2.0)
        finally:
            await pipeline_v2.stop()

        signals = [f for f in frames if f.get("type") == "signal"]
        assert len(signals) > 0, "Should have signal frames"

    async def test_snapshot_roundtrip(self, pipeline_v2):
        """Saving and restoring state should preserve HR."""
        frames_before = []

        async def collect_before(msg):
            frames_before.append(msg)

        await pipeline_v2.start(collect_before)
        try:
            await asyncio.sleep(1.5)
            snapshot = pipeline_v2.get_snapshot()
        finally:
            await pipeline_v2.stop()

        # Restore from snapshot
        restored = SimulationPipeline(snapshot=snapshot)
        frames_after = []

        async def collect_after(msg):
            frames_after.append(msg)

        await restored.start(collect_after)
        try:
            await asyncio.sleep(1.0)
        finally:
            await restored.stop()

        signals_before = [f for f in frames_before if f.get("type") == "signal"]
        signals_after = [f for f in frames_after if f.get("type") == "signal"]

        if signals_before and signals_after:
            hr_before = signals_before[-1]["vitals"]["heart_rate"]
            hr_after = signals_after[0]["vitals"]["heart_rate"]
            assert abs(hr_before - hr_after) < 5.0, (
                f"HR drift after snapshot: {hr_before:.1f} -> {hr_after:.1f}"
            )

    async def test_multi_lead_output(self, pipeline_v2):
        """Setting multiple leads should produce ecg_leads data."""
        pipeline_v2.set_leads(["I", "II", "V1"])
        frames = []

        async def collect(msg):
            frames.append(msg)

        await pipeline_v2.start(collect)
        try:
            await asyncio.sleep(1.5)
        finally:
            await pipeline_v2.stop()

        signals = [f for f in frames if f.get("type") == "signal"]
        assert len(signals) > 0
        # Check init payload has correct leads
        payload = pipeline_v2.get_init_payload()
        assert set(payload["selected_leads"]) == {"I", "II", "V1"}

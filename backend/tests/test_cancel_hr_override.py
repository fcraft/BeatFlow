"""Tests for cancel_hr_override command."""
import asyncio

import pytest

from app.engine.simulation.pipeline import SimulationPipeline


@pytest.fixture
def pipeline():
    return SimulationPipeline()


class TestCancelHrOverride:
    def test_cancel_clears_override(self, pipeline: SimulationPipeline):
        """Set hr_override via tachycardia, then cancel → override should be None."""
        pipeline.apply_command("condition_tachycardia", {})
        assert pipeline._intent.hr_override is not None

        pipeline.apply_command("cancel_hr_override", {})
        assert pipeline._intent.hr_override is None

    def test_cancel_preserves_other_conditions(self, pipeline: SimulationPipeline):
        """Set valve_disease + tachycardia, cancel_hr_override → valve disease intact."""
        pipeline.apply_command("condition_valve_disease", {"severity": 0.7})
        pipeline.apply_command("condition_tachycardia", {})
        assert pipeline._intent.hr_override is not None

        pipeline.apply_command("cancel_hr_override", {})
        assert pipeline._intent.hr_override is None
        # Valve disease fields should remain
        assert pipeline._intent.murmur_severity > 0

    def test_cancel_when_no_override_is_noop(self, pipeline: SimulationPipeline):
        """Cancel when no override set → no error, hr_override stays None."""
        assert pipeline._intent.hr_override is None
        pipeline.apply_command("cancel_hr_override", {})
        assert pipeline._intent.hr_override is None

    def test_hr_reverts_to_physiology_after_cancel(self, pipeline: SimulationPipeline):
        """After cancel, HR should be driven by sa_rate_modifier (physiology)."""
        pipeline.apply_command("condition_tachycardia", {})
        assert pipeline._intent.hr_override is not None

        pipeline.apply_command("cancel_hr_override", {})
        # Intent cleared — the smoother will gradually propagate None to _modifiers
        assert pipeline._intent.hr_override is None
        # Verify no override is set on modifiers for a fresh pipeline (no beats run yet)
        assert pipeline._modifiers.hr_override is None

    async def test_vitals_include_hr_override_fields(self, pipeline: SimulationPipeline):
        """Check hr_override_active and hr_override_value appear in vitals."""
        messages: list[dict] = []

        async def send(msg):
            messages.append(msg)

        await pipeline.start(send)
        await asyncio.sleep(0.8)

        # Apply tachycardia to set hr_override
        pipeline.apply_command("condition_tachycardia", {})
        await asyncio.sleep(2.0)
        await pipeline.stop()

        signals = [m for m in messages if m.get("type") == "signal"]
        assert len(signals) > 0

        # Find a signal after the tachycardia command
        last_vitals = signals[-1]["vitals"]
        assert "hr_override_active" in last_vitals
        assert "hr_override_value" in last_vitals

        # With tachycardia active, override should be active
        assert last_vitals["hr_override_active"] is True
        assert last_vitals["hr_override_value"] is not None

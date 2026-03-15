"""Shared fixtures for virtual human engine tests."""

import pytest
from app.engine.simulation.pipeline import SimulationPipeline


@pytest.fixture
def pipeline_v2() -> SimulationPipeline:
    """Fresh v3 SimulationPipeline instance (not started)."""
    return SimulationPipeline()

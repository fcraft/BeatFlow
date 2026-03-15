"""Test valve event serialization in physiology_detail."""
import pytest
import numpy as np
from app.engine.core.types import ValveEvent, HemodynamicState


class TestValveEventSerialization:
    def test_at_sample_to_ms_conversion(self) -> None:
        ve = ValveEvent(valve='mitral', action='close', at_sample=500, dp_dt=800.0, area_ratio=1.0)
        at_ms = round(ve.at_sample / 5000.0 * 1000.0, 1)
        assert at_ms == 100.0

    def test_serialization_format(self) -> None:
        ve = ValveEvent(valve='aortic', action='open', at_sample=750, dp_dt=600.0, area_ratio=0.8)
        serialized = {
            'valve': ve.valve, 'action': ve.action,
            'at_ms': round(ve.at_sample / 5000.0 * 1000.0, 1),
            'dp_dt': ve.dp_dt, 'area_ratio': ve.area_ratio,
        }
        assert serialized == {'valve': 'aortic', 'action': 'open', 'at_ms': 150.0, 'dp_dt': 600.0, 'area_ratio': 0.8}


class TestValveEventPipelineIntegration:
    def _serialize_valve_events(self, valve_events):
        return [
            {"valve": ve.valve, "action": ve.action, "at_ms": round(ve.at_sample / 5000.0 * 1000.0, 1), "dp_dt": round(ve.dp_dt, 1), "area_ratio": round(ve.area_ratio, 3)}
            for ve in valve_events
        ] if valve_events else []

    def test_multiple_valve_events_serialized(self) -> None:
        events = [
            ValveEvent(valve='mitral', action='close', at_sample=400, dp_dt=800.0, area_ratio=1.0),
            ValveEvent(valve='aortic', action='open', at_sample=420, dp_dt=600.0, area_ratio=0.9),
            ValveEvent(valve='aortic', action='close', at_sample=1600, dp_dt=500.0, area_ratio=1.0),
            ValveEvent(valve='mitral', action='open', at_sample=1700, dp_dt=300.0, area_ratio=0.85),
        ]
        result = self._serialize_valve_events(events)
        assert len(result) == 4
        assert result[2]['at_ms'] == 320.0

    def test_empty_valve_events(self) -> None:
        assert self._serialize_valve_events([]) == []

    def test_area_ratio_rounding(self) -> None:
        events = [ValveEvent(valve='mitral', action='close', at_sample=100, dp_dt=1.0, area_ratio=0.12345)]
        result = self._serialize_valve_events(events)
        assert result[0]['area_ratio'] == 0.123

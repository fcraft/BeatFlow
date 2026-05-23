"""Causal event tracking — backend.

Records physiological state changes as CausalEvent instances, enabling
the frontend to display "why did this value change?" causality chains.

Each CausalEvent captures: what changed, by how much, what triggered it,
and a human-readable mechanism description.

Usage (in pipeline._run_one_beat):
    tracker.record("exercise_model", "jog", "heart_rate", "vitals.heart_rate",
                   old_value=72.0, new_value=95.0, mechanism="Exercise → ↑sympathetic → ↑HR")
    ...
    message["causal_events"] = tracker.recent(20)
"""
from __future__ import annotations

import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from typing import Any


@dataclass
class CausalEvent:
    """A single physiological state change with its causal explanation.

    Attributes:
        id: Unique event identifier.
        timestamp_ms: When the event occurred (monotonic, relative to stream start).
        source: System component that caused the change (e.g., "baroreflex").
        source_detail: Specific trigger detail (e.g., "MAP_drop_15mmHg").
        target: Human-readable variable name (e.g., "heart_rate").
        target_path: Machine-readable path (e.g., "vitals.heart_rate").
        old_value: Previous value (None if initial).
        new_value: New value after the change.
        delta: Magnitude of change.
        mechanism: Human-readable physiological explanation.
        confidence: 0-1 certainty of this causal attribution.
        parent_event_id: Upstream event that triggered this one (for chains).
    """

    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    timestamp_ms: float = 0.0
    source: str = ""
    source_detail: str = ""
    target: str = ""
    target_path: str = ""
    old_value: float | str | None = None
    new_value: float | str = ""
    delta: float | None = None
    mechanism: str = ""
    confidence: float = 1.0
    parent_event_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "timestamp_ms": round(self.timestamp_ms, 0),
            "source": self.source,
            "source_detail": self.source_detail,
            "target": self.target,
            "target_path": self.target_path,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "delta": self.delta,
            "mechanism": self.mechanism,
            "confidence": round(self.confidence, 2),
            "parent_event_id": self.parent_event_id,
        }


class CausalTracker:
    """Records causal events and provides recent-event queries.

    Maintains a bounded circular buffer of CausalEvent instances.
    Thread-safe for single-producer (beat loop) access.
    Uses drain() for WebSocket push to avoid re-sending already-pushed events.
    """

    def __init__(self, max_events: int = 200) -> None:
        self._max_events = max_events
        self._buffer: deque[CausalEvent] = deque(maxlen=max_events)
        self._stream_start_ms = time.monotonic() * 1000.0
        self._next_seq: int = 0
        self._drain_seq: int = 0

    def record(
        self,
        source: str,
        source_detail: str,
        target: str,
        target_path: str,
        *,
        old_value: float | str | None = None,
        new_value: float | str = "",
        mechanism: str = "",
        confidence: float = 1.0,
        parent_event_id: str | None = None,
    ) -> CausalEvent:
        """Record a new causal event and return it."""
        now = time.monotonic() * 1000.0 - self._stream_start_ms

        delta: float | None = None
        if isinstance(old_value, (int, float)) and isinstance(new_value, (int, float)):
            delta = float(new_value) - float(old_value)

        event = CausalEvent(
            timestamp_ms=now,
            source=source,
            source_detail=source_detail,
            target=target,
            target_path=target_path,
            old_value=old_value,
            new_value=new_value,
            delta=delta,
            mechanism=mechanism,
            confidence=confidence,
            parent_event_id=parent_event_id,
        )
        event._seq = self._next_seq  # type: ignore[attr-defined]
        self._next_seq += 1
        self._buffer.append(event)
        return event

    def record_chain(
        self,
        source: str,
        source_detail: str,
        changes: list[tuple[str, str, float, float, str]],
        confidence: float = 1.0,
    ) -> list[CausalEvent]:
        """Record a chain of related changes sharing a root cause.

        Args:
            source: Root cause component.
            source_detail: Root cause detail.
            changes: List of (target, target_path, old_value, new_value, mechanism).
            confidence: Confidence for all events in the chain.

        Returns:
            List of created CausalEvent instances.
        """
        parent_id: str | None = None
        events: list[CausalEvent] = []
        for target, target_path, old_val, new_val, mechanism in changes:
            event = self.record(
                source=source,
                source_detail=source_detail,
                target=target,
                target_path=target_path,
                old_value=old_val,
                new_value=new_val,
                mechanism=mechanism,
                confidence=confidence,
                parent_event_id=parent_id,
            )
            parent_id = event.id
            events.append(event)
        return events

    def drain(self) -> list[dict[str, Any]]:
        """Return events recorded since the last drain() call.

        Uses monotonically increasing sequence numbers (not buffer cursors)
        so the bounded deque dropping old items from the left does not
        cause missed or duplicated events.
        """
        events = [e for e in self._buffer if e._seq >= self._drain_seq]  # type: ignore[attr-defined]
        if events:
            self._drain_seq = events[-1]._seq + 1  # type: ignore[attr-defined]
        return [e.to_dict() for e in events]

    def recent(self, n: int = 20) -> list[dict[str, Any]]:
        """Return the most recent n events as dicts (for snapshot/init)."""
        items = list(self._buffer)[-n:]
        return [e.to_dict() for e in items]

    def clear(self) -> None:
        """Clear all recorded events."""
        self._buffer.clear()
        self._drain_seq = 0

    def __len__(self) -> int:
        return sum(1 for e in self._buffer if e._seq >= self._drain_seq)  # type: ignore[attr-defined]

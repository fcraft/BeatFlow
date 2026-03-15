"""V3 protocol interfaces for the 3-layer parametric pipeline.

Each layer is defined as a @runtime_checkable Protocol so implementations
can be swapped or tested independently.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.engine.core.types import (
    ConductionResult,
    EcgFrame,
    HemodynamicState,
    Modifiers,
    PcgFrame,
)


@runtime_checkable
class ConductionNetwork(Protocol):
    """Layer 1: Cardiac conduction network (parametric)."""
    def propagate(self, rr_sec: float, modifiers: Modifiers) -> ConductionResult: ...
    def get_state(self) -> dict: ...
    def set_state(self, state: dict) -> None: ...


@runtime_checkable
class EcgSynthesizer(Protocol):
    """Layer 2a: Body surface ECG synthesis."""
    def synthesize(self, conduction: ConductionResult,
                   leads: list[str], modifiers: Modifiers) -> EcgFrame: ...


@runtime_checkable
class PcgSynthesizer(Protocol):
    """Layer 2b: Heart sound (PCG) synthesis."""
    def synthesize(self, conduction: ConductionResult,
                   modifiers: Modifiers) -> PcgFrame: ...


@runtime_checkable
class HemodynamicEngine(Protocol):
    """Layer 3: Algebraic hemodynamic computation."""
    def compute(self, hr: float, rr_sec: float,
                modifiers: Modifiers) -> HemodynamicState: ...

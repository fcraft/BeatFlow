"""Physiology causal graph engine — Phase 3A core.

Replaces the monolithic compute_modifiers() with a directed acyclic graph
of CausalNode instances. Each node declares its inputs/outputs and a pure
transfer function. The graph topologically sorts nodes and applies first-order
lag smoothing to all outputs for physiologically realistic temporal dynamics.

Usage:
    graph = create_default_graph()
    result = graph.step(dt_sec=0.8, external_inputs={
        "map_mmhg": 93.0, "paco2_mmhg": 40.0, ...
    })
    # result is a flat dict mapping output variable names to values
"""
from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable

import numpy as np


@dataclass
class CausalNode:
    """A single node in the physiology causal graph.

    Each node reads from named input variables, applies a pure transfer_fn,
    and writes to named output variables.  The CausalGraph applies first-order
    lag smoothing with time_constant_ms to every output.

    Attributes:
        name: Unique node identifier.
        inputs: Variable names this node reads from the global state dict.
        outputs: Variable names this node writes to the global state dict.
        transfer_fn: Pure function mapping input dict → output dict.
        delay_ms: Transport/processing delay before output takes effect.
        time_constant_ms: First-order lag time constant (tau).
    """

    name: str
    inputs: list[str]
    outputs: list[str]
    transfer_fn: Callable[[dict[str, float]], dict[str, float]]
    delay_ms: float = 0.0
    time_constant_ms: float = 500.0


class CausalGraph:
    """A directed acyclic graph of CausalNode instances.

    On each step(), the graph:
    1. Merges external_inputs into the persistent state dict
    2. Topologically traverses nodes
    3. For each node: calls transfer_fn, applies first-order lag
    4. Returns a dict of all output variables

    The state dict persists between step() calls, enabling smooth
    temporal dynamics via the per-node first-order lag.
    """

    def __init__(
        self, nodes: list[CausalNode],
        external_inputs: set[str] | None = None,
    ) -> None:
        self.nodes = list(nodes)
        self.state: dict[str, float] = {}
        self._external_inputs = external_inputs or set()

        # Validate
        self._validate_no_cycles()
        self._validate_inputs_resolvable()
        self._order = self._topological_sort()

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def _validate_no_cycles(self) -> None:
        """Raise ValueError if the graph contains a directed cycle."""
        producers: dict[str, str] = {}
        for node in self.nodes:
            for out in node.outputs:
                if out in producers:
                    raise ValueError(
                        f"Output variable '{out}' is produced by both "
                        f"'{producers[out]}' and '{node.name}'"
                    )
                producers[out] = node.name

        successors: dict[str, set[str]] = {n.name: set() for n in self.nodes}
        for node in self.nodes:
            for inp in node.inputs:
                if inp in producers:
                    producer_name = producers[inp]
                    if producer_name != node.name:
                        successors[producer_name].add(node.name)

        WHITE, GREY, BLACK = 0, 1, 2
        colour: dict[str, int] = {n.name: WHITE for n in self.nodes}

        def visit(v: str) -> None:
            colour[v] = GREY
            for w in successors.get(v, set()):
                if colour[w] == GREY:
                    raise ValueError(
                        f"Cycle detected in causal graph: '{v}' → '{w}'"
                    )
                if colour[w] == WHITE:
                    visit(w)
            colour[v] = BLACK

        for node in self.nodes:
            if colour[node.name] == WHITE:
                visit(node.name)

    def _validate_inputs_resolvable(self) -> None:
        """Raise ValueError if any node's input cannot be resolved."""
        produced: set[str] = set()
        for node in self.nodes:
            for out in node.outputs:
                produced.add(out)

        unresolvable: list[tuple[str, str]] = []
        for node in self.nodes:
            for inp in node.inputs:
                if inp in produced or inp in self.state or inp in self._external_inputs:
                    continue
                unresolvable.append((node.name, inp))

        if unresolvable:
            details = ", ".join(f"'{n}.{i}'" for n, i in unresolvable)
            raise ValueError(
                f"Unresolvable input(s): {details}. "
                f"Provide them via external_inputs at step() time "
                f"or list them in the graph's known external_inputs set."
            )

    def _topological_sort(self) -> list[str]:
        """Return node names in topological order (Kahn's algorithm)."""
        # Build in-degree and adjacency maps
        producers: dict[str, str] = {}
        for node in self.nodes:
            for out in node.outputs:
                producers[out] = node.name

        in_degree: dict[str, int] = {n.name: 0 for n in self.nodes}
        adj: dict[str, list[str]] = {n.name: [] for n in self.nodes}

        for node in self.nodes:
            for inp in node.inputs:
                producer = producers.get(inp)
                if producer is not None and producer != node.name:
                    adj.setdefault(producer, []).append(node.name)
                    in_degree[node.name] = in_degree.get(node.name, 0) + 1

        # Kahn's algorithm
        queue: deque[str] = deque(
            n.name for n in self.nodes if in_degree.get(n.name, 0) == 0
        )
        order: list[str] = []

        while queue:
            v = queue.popleft()
            order.append(v)
            for w in adj.get(v, []):
                in_degree[w] -= 1
                if in_degree[w] == 0:
                    queue.append(w)

        if len(order) != len(self.nodes):
            # Shouldn't happen after cycle detection, but defensive
            remaining = set(n.name for n in self.nodes) - set(order)
            raise ValueError(
                f"Unresolved dependencies (possible cycle): {remaining}"
            )

        return order

    # ------------------------------------------------------------------
    # Step
    # ------------------------------------------------------------------

    def step(
        self, dt_sec: float, external_inputs: dict[str, float]
    ) -> dict[str, float]:
        """Advance the graph by dt_sec seconds.

        Args:
            dt_sec: Time step in seconds (typically beat interval ~0.8s).
            external_inputs: Fresh values injected from outside the graph
                (e.g., MAP from hemodynamics, PaCO2 from respiratory model).

        Returns:
            Dict mapping all output variable names to their current values.
        """
        # Merge external inputs into state
        self.state.update(external_inputs)

        # Name → node lookup
        node_map: dict[str, CausalNode] = {n.name: n for n in self.nodes}

        for node_name in self._order:
            node = node_map[node_name]

            # Gather inputs from state
            inputs = {key: self.state.get(key, 0.0) for key in node.inputs}

            # Compute target outputs (pure function)
            try:
                targets = node.transfer_fn(inputs)
            except Exception:
                # If transfer_fn fails, skip this node silently —
                # physiological models should be robust to edge cases
                continue

            # Apply first-order lag and write to state
            dt_ms = dt_sec * 1000.0
            for key, target in targets.items():
                prev = self.state.get(key, 0.0)
                if node.time_constant_ms > 0:
                    alpha = 1.0 - math.exp(-dt_ms / node.time_constant_ms)
                    self.state[key] = prev + alpha * (target - prev)
                else:
                    self.state[key] = target

        # Return all current outputs (values written by any node)
        output_keys: set[str] = set()
        for node in self.nodes:
            output_keys.update(node.outputs)
        return {k: self.state.get(k, 0.0) for k in output_keys}


# ======================================================================
# Factory: default physiology causal graph
# ======================================================================

def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def create_default_graph() -> CausalGraph:
    """Build the default 4-layer physiology causal graph (~18 nodes).

    Layers:
      1. Reflex arcs — baroreflex, chemoreflex, thermoregulation, RAAS
      2. ANS integration — merge reflex outputs into symp/para tones
      3. Primary modulators — exercise, damage, drug, emotion, electrolyte
      4. Integrated outputs — HR, contractility, SVR, BP, CO
    """
    nodes: list[CausalNode] = []

    # ------------------------------------------------------------------
    # Layer 1: Reflex arcs
    # ------------------------------------------------------------------

    def baroreflex_fn(d: dict) -> dict:
        """MAP deviation → sympathetic/parasympathetic reflex response."""
        map_mmhg = d["map_mmhg"]
        # Logistic response centered at MAP=93mmHg
        map_dev = (map_mmhg - 93.0) / 20.0
        # Lower MAP → higher symp, lower para
        symp_drive = _clamp(0.5 - 0.4 * map_dev, 0.1, 0.9)
        para_drive = _clamp(0.5 + 0.5 * map_dev, 0.1, 0.9)
        return {"baro_symp": symp_drive, "baro_para": para_drive}

    nodes.append(CausalNode(
        name="baroreflex",
        inputs=["map_mmhg"],
        outputs=["baro_symp", "baro_para"],
        transfer_fn=baroreflex_fn,
        time_constant_ms=500.0,  # Fast: 1-2 beats
    ))

    def chemoreflex_fn(d: dict) -> dict:
        """PaCO2/PaO2/pH → chemoreceptor-driven sympathetic activation."""
        paco2 = d["paco2_mmhg"]
        pao2 = d["pao2_mmhg"]
        ph = d["ph"]

        # Hypercapnia → symp activation
        co2_drive = _clamp((paco2 - 40.0) / 20.0, -1.0, 2.0)
        # Hypoxia → symp activation (below 60mmHg)
        o2_drive = _clamp((60.0 - pao2) / 30.0, 0.0, 2.0) if pao2 < 60.0 else 0.0
        # Acidosis → symp activation
        ph_drive = _clamp((7.40 - ph) / 0.2, 0.0, 1.0) if ph < 7.40 else 0.0

        total = _clamp(0.0 + 0.6 * co2_drive + 0.3 * o2_drive + 0.1 * ph_drive,
                       -0.5, 2.0)
        return {"chemo_symp_drive": max(0.0, total)}

    nodes.append(CausalNode(
        name="chemoreflex",
        inputs=["paco2_mmhg", "pao2_mmhg", "ph"],
        outputs=["chemo_symp_drive"],
        transfer_fn=chemoreflex_fn,
        time_constant_ms=5000.0,  # Slower: 5-10s
    ))

    def raas_fn(d: dict) -> dict:
        """Low MAP or low CO → RAAS activation (very slow)."""
        map_mmhg = d["map_mmhg"]
        co = d["cardiac_output"]
        map_drive = _clamp((70.0 - map_mmhg) / 30.0, 0.0, 1.5) if map_mmhg < 70.0 else 0.0
        co_drive = _clamp((3.5 - co) / 2.0, 0.0, 1.0) if co < 3.5 else 0.0
        return {"raas_activation": _clamp(map_drive + co_drive, 0.0, 1.0)}

    nodes.append(CausalNode(
        name="raas",
        inputs=["map_mmhg", "cardiac_output"],
        outputs=["raas_activation"],
        transfer_fn=raas_fn,
        time_constant_ms=60_000.0,  # Very slow: 15-30 min
    ))

    def thermoregulation_fn(d: dict) -> dict:
        """Temperature deviation → sympathetic adjustment."""
        temp = d["temperature_c"]
        delta = temp - 37.0
        return {"thermo_symp": _clamp(0.5 + 0.1 * delta, 0.1, 0.9)}

    nodes.append(CausalNode(
        name="thermoregulation",
        inputs=["temperature_c"],
        outputs=["thermo_symp"],
        transfer_fn=thermoregulation_fn,
        time_constant_ms=300_000.0,  # Minutes
    ))

    # ------------------------------------------------------------------
    # Layer 2: ANS integration
    # ------------------------------------------------------------------

    def ans_balance_fn(d: dict) -> dict:
        """Merge all autonomic drives into final sympathetic/parasympathetic."""
        # Start from baseline
        symp = 0.5
        symp += d.get("baro_symp", 0.5) - 0.5
        symp += d.get("chemo_symp_drive", 0.0) * 0.3
        symp += d.get("raas_activation", 0.0) * 0.1
        symp += d.get("thermo_symp", 0.5) - 0.5
        symp += d.get("emotional_symp_drive", 0.0) * 0.4
        symp = _clamp(symp, 0.1, 1.0)

        para = 0.5
        para += d.get("baro_para", 0.5) - 0.5
        para -= d.get("emotional_para_suppress", 0.0) * 0.3
        para = _clamp(para, 0.1, 1.0)

        # User intent overrides (e.g., jog/hike command)
        symp_override = d.get("symp_override", 0.0)
        para_override = d.get("para_override", 0.0)
        if symp_override > 0.01:
            symp = symp_override
        if para_override > 0.01:
            para = para_override

        return {"sympathetic_tone": symp, "parasympathetic_tone": para}

    nodes.append(CausalNode(
        name="ans_balance",
        inputs=["baro_symp", "baro_para", "chemo_symp_drive",
                 "raas_activation", "thermo_symp",
                 "emotional_symp_drive", "emotional_para_suppress"],
        outputs=["sympathetic_tone", "parasympathetic_tone"],
        transfer_fn=ans_balance_fn,
        time_constant_ms=200.0,  # Fast integration
    ))

    # ------------------------------------------------------------------
    # Layer 3: Primary modulators
    # ------------------------------------------------------------------

    def exercise_effects_fn(d: dict) -> dict:
        """Exercise intensity → HR/SV/TPR deltas."""
        ex = d["exercise_intensity"]
        return {
            "ex_hr_drive": 0.8 * ex,
            "ex_contractility_drive": 0.4 * ex,
            "ex_tpr_drive": -0.2 * ex,  # Exercise → vasodilation in muscle
        }

    nodes.append(CausalNode(
        name="exercise_effects",
        inputs=["exercise_intensity"],
        outputs=["ex_hr_drive", "ex_contractility_drive", "ex_tpr_drive"],
        transfer_fn=exercise_effects_fn,
        time_constant_ms=1000.0,  # ~1s to steady state
    ))

    def damage_effects_fn(d: dict) -> dict:
        """Myocardial damage → reduced contractility."""
        damage = d["damage_level"]
        return {"damage_contractility_factor": max(0.3, 1.0 - 0.5 * damage)}

    nodes.append(CausalNode(
        name="damage_effects",
        inputs=["damage_level"],
        outputs=["damage_contractility_factor"],
        transfer_fn=damage_effects_fn,
        time_constant_ms=100.0,
    ))

    def drug_effects_fn(d: dict) -> dict:
        """Drug concentrations → HR/SV/TPR modifiers.

        Reads drug levels from state (injected as external inputs from
        PharmacokineticsEngine). Returns additive deltas on top of baseline.
        """
        bb = d.get("beta_blocker", 0.0)
        amio = d.get("amiodarone", 0.0)
        dig = d.get("digoxin", 0.0)
        atr = d.get("atropine", 0.0)

        hr_factor = 1.0
        contractility_factor = 1.0
        av_delay_factor = 1.0

        if bb > 0.01:
            hr_factor *= max(0.5, 1.0 - 0.35 * bb)
            contractility_factor *= max(0.6, 1.0 - 0.25 * bb)
            av_delay_factor *= 1.0 + 0.3 * bb
        if amio > 0.01:
            hr_factor *= max(0.6, 1.0 - 0.25 * amio)
            av_delay_factor *= 1.0 + 0.2 * amio
        if dig > 0.01:
            contractility_factor *= 1.0 + 0.3 * dig
            hr_factor *= max(0.7, 1.0 - 0.15 * dig)
            av_delay_factor *= 1.0 + 0.25 * dig
        if atr > 0.01:
            hr_factor *= 1.0 + 0.3 * min(1.0, atr * 0.8)

        return {
            "drug_hr_factor": hr_factor,
            "drug_contractility_factor": contractility_factor,
            "drug_av_delay_factor": av_delay_factor,
        }

    nodes.append(CausalNode(
        name="drug_effects",
        inputs=["beta_blocker", "amiodarone", "digoxin", "atropine"],
        outputs=["drug_hr_factor", "drug_contractility_factor",
                  "drug_av_delay_factor"],
        transfer_fn=drug_effects_fn,
        time_constant_ms=2000.0,  # Drug effects build gradually
    ))

    def electrolyte_effects_fn(d: dict) -> dict:
        """Potassium/calcium levels → HR/contractility modifiers."""
        k = d.get("potassium_level", 4.0)
        ca = d.get("calcium_level", 9.0)

        hr_factor = 1.0
        if k > 5.0:
            hr_factor *= max(0.7, 1.0 - 0.1 * (k - 5.0))
        elif k < 3.5:
            hr_factor *= 1.0 + 0.05 * (3.5 - k)

        contractility_factor = 1.0
        if ca > 10.0:
            contractility_factor *= 1.0 + 0.05 * (ca - 10.0)
        elif ca < 8.0:
            contractility_factor *= max(0.8, 1.0 - 0.1 * (8.0 - ca))

        return {"electrolyte_hr_factor": hr_factor,
                "electrolyte_contractility_factor": contractility_factor}

    nodes.append(CausalNode(
        name="electrolyte_effects",
        inputs=["potassium_level", "calcium_level"],
        outputs=["electrolyte_hr_factor", "electrolyte_contractility_factor"],
        transfer_fn=electrolyte_effects_fn,
        time_constant_ms=5000.0,  # Electrolyte shifts take seconds to effect
    ))

    def emotion_effects_fn(d: dict) -> dict:
        """Emotional arousal → sympathetic/parasympathetic modulation."""
        arousal = d.get("emotional_arousal", 0.0)
        return {
            "emotional_symp_drive": arousal,
            "emotional_para_suppress": arousal * 0.5,
        }

    nodes.append(CausalNode(
        name="emotion_effects",
        inputs=["emotional_arousal"],
        outputs=["emotional_symp_drive", "emotional_para_suppress"],
        transfer_fn=emotion_effects_fn,
        time_constant_ms=500.0,
    ))

    # ------------------------------------------------------------------
    # Layer 4: Integrated outputs
    # ------------------------------------------------------------------

    def heart_rate_fn(d: dict) -> dict:
        """Compute sa_rate_modifier from all upstream drives."""
        symp = d["sympathetic_tone"]
        para = d["parasympathetic_tone"]

        # Base ANS effect
        hr = 1.0 + 0.6 * (symp - 0.5) - 0.4 * (para - 0.5)
        # Exercise drive
        hr += d.get("ex_hr_drive", 0.0)
        # Drug modulation
        hr *= d.get("drug_hr_factor", 1.0)
        # Electrolyte modulation
        hr *= d.get("electrolyte_hr_factor", 1.0)

        return {"sa_rate_modifier": _clamp(hr, 0.5, 2.5)}

    nodes.append(CausalNode(
        name="heart_rate",
        inputs=["sympathetic_tone", "parasympathetic_tone",
                 "ex_hr_drive", "drug_hr_factor", "electrolyte_hr_factor"],
        outputs=["sa_rate_modifier"],
        transfer_fn=heart_rate_fn,
        time_constant_ms=200.0,
    ))

    def contractility_fn(d: dict) -> dict:
        """Compute contractility_modifier from upstream drives."""
        symp = d["sympathetic_tone"]
        base = 1.0 + 0.4 * (symp - 0.5)
        base += d.get("ex_contractility_drive", 0.0)
        base *= d.get("damage_contractility_factor", 1.0)
        base *= d.get("drug_contractility_factor", 1.0)
        base *= d.get("electrolyte_contractility_factor", 1.0)
        return {"contractility_modifier": _clamp(base, 0.3, 2.0)}

    nodes.append(CausalNode(
        name="contractility",
        inputs=["sympathetic_tone", "ex_contractility_drive",
                 "damage_contractility_factor", "drug_contractility_factor",
                 "electrolyte_contractility_factor"],
        outputs=["contractility_modifier"],
        transfer_fn=contractility_fn,
        time_constant_ms=200.0,
    ))

    def svr_fn(d: dict) -> dict:
        """Compute tpr_modifier from sympathetic tone and exercise."""
        symp = d["sympathetic_tone"]
        base = 1.0 + 0.3 * (symp - 0.5)
        base += d.get("ex_tpr_drive", 0.0)
        raas = d.get("raas_activation", 0.0)
        base += raas * 0.15  # RAAS → vasoconstriction
        return {"tpr_modifier": _clamp(base, 0.5, 2.0)}

    nodes.append(CausalNode(
        name="svr",
        inputs=["sympathetic_tone", "ex_tpr_drive", "raas_activation"],
        outputs=["tpr_modifier"],
        transfer_fn=svr_fn,
        time_constant_ms=1000.0,
    ))

    def av_delay_fn(d: dict) -> dict:
        """Compute av_delay_modifier from drug effects."""
        return {"av_delay_modifier": d.get("drug_av_delay_factor", 1.0)}

    nodes.append(CausalNode(
        name="av_delay",
        inputs=["drug_av_delay_factor"],
        outputs=["av_delay_modifier"],
        transfer_fn=av_delay_fn,
        time_constant_ms=500.0,
    ))

    def preload_fn(d: dict) -> dict:
        """Compute preload_modifier from exercise and sympathetic tone.

        Exercise → venoconstriction → ↑ preload.
        Sympathetic activation → splanchnic vasoconstriction → ↑ venous return.
        """
        symp = d["sympathetic_tone"]
        ex = d.get("exercise_intensity", 0.0)
        base = 1.0 + 0.15 * (symp - 0.5) + 0.2 * ex
        return {"preload_modifier": _clamp(base, 0.5, 2.0)}

    nodes.append(CausalNode(
        name="preload",
        inputs=["sympathetic_tone", "exercise_intensity"],
        outputs=["preload_modifier"],
        transfer_fn=preload_fn,
        time_constant_ms=1000.0,
    ))

    return CausalGraph(nodes, external_inputs={
        "map_mmhg", "paco2_mmhg", "pao2_mmhg", "ph",
        "temperature_c", "cardiac_output",
        "exercise_intensity", "damage_level",
        "beta_blocker", "amiodarone", "digoxin", "atropine",
        "potassium_level", "calcium_level",
        "emotional_arousal",
        "symp_override", "para_override",
        "rv_contractility",
    })

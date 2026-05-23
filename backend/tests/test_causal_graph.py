"""Unit tests for PhysiologyCausalGraph — Phase 3A core."""
from __future__ import annotations

import math

import pytest


# ---------------------------------------------------------------------------
# CausalNode tests
# ---------------------------------------------------------------------------

class TestCausalNode:
    def test_node_basic_transfer(self):
        """A node applies its transfer_fn to produce outputs from inputs."""
        from app.engine.modulation.causal_graph import CausalNode

        node = CausalNode(
            name="test",
            inputs=["a", "b"],
            outputs=["c"],
            transfer_fn=lambda d: {"c": d["a"] + d["b"]},
        )
        result = node.transfer_fn({"a": 1.0, "b": 2.0})
        assert result == {"c": 3.0}

    def test_node_delay_and_time_constant_defaults(self):
        """Default delay is 0ms, default time constant is 500ms."""
        from app.engine.modulation.causal_graph import CausalNode

        node = CausalNode(
            name="test", inputs=["x"], outputs=["y"],
            transfer_fn=lambda d: {"y": d["x"] * 2},
        )
        assert node.delay_ms == 0.0
        assert node.time_constant_ms == 500.0

    def test_node_custom_time_constants(self):
        """Nodes can have per-node delay and time constant."""
        from app.engine.modulation.causal_graph import CausalNode

        node = CausalNode(
            name="slow", inputs=["x"], outputs=["y"],
            transfer_fn=lambda d: {"y": d["x"]},
            delay_ms=1000.0, time_constant_ms=5000.0,
        )
        assert node.delay_ms == 1000.0
        assert node.time_constant_ms == 5000.0


# ---------------------------------------------------------------------------
# CausalGraph tests
# ---------------------------------------------------------------------------

class TestCausalGraphTopology:
    def test_linear_chain_executes_in_order(self):
        """A→B→C should execute A first, then B, then C."""
        from app.engine.modulation.causal_graph import CausalGraph, CausalNode

        execution_order: list[str] = []

        def make_node(name: str, inp: str, out: str) -> CausalNode:
            def fn(d: dict) -> dict:
                execution_order.append(name)
                return {out: d[inp]}
            return CausalNode(name=name, inputs=[inp], outputs=[out], transfer_fn=fn)

        a = make_node("a", "x", "a_out")
        b = make_node("b", "a_out", "b_out")
        c = make_node("c", "b_out", "y")

        graph = CausalGraph([a, b, c], external_inputs={"x"})
        result = graph.step(0.5, {"x": 1.0})

        assert execution_order == ["a", "b", "c"]
        assert "y" in result

    def test_diamond_dependency_respects_deps(self):
        """Diamond graph (in→A, in→B, A→C, B→C→out) must run A,B before C."""
        from app.engine.modulation.causal_graph import CausalGraph, CausalNode

        order: list[str] = []

        a = CausalNode("a", ["x"], ["a_out"], lambda d: (order.append("a"), {"a_out": d["x"] * 2})[1])
        b = CausalNode("b", ["x"], ["b_out"], lambda d: (order.append("b"), {"b_out": d["x"] * 3})[1])
        c = CausalNode("c", ["a_out", "b_out"], ["y"],
                       lambda d: (order.append("c"), {"y": d["a_out"] + d["b_out"]})[1])

        graph = CausalGraph([a, b, c], external_inputs={"x"})
        graph.step(0.5, {"x": 1.0})

        assert order.index("a") < order.index("c")
        assert order.index("b") < order.index("c")

    def test_cycle_detection_raises_error(self):
        """A graph with A→B→A should raise ValueError on construction."""
        from app.engine.modulation.causal_graph import CausalGraph, CausalNode

        a = CausalNode("a", ["b_out"], ["a_out"], lambda d: {"a_out": d["b_out"]})
        b = CausalNode("b", ["a_out"], ["b_out"], lambda d: {"b_out": d["a_out"]})

        with pytest.raises(ValueError, match="[Cc]ycle"):
            CausalGraph([a, b])

    def test_missing_input_raises_error(self):
        """A node referencing an input no node produces should raise ValueError."""
        from app.engine.modulation.causal_graph import CausalGraph, CausalNode

        a = CausalNode("a", ["nonexistent"], ["a_out"], lambda d: {"a_out": 1.0})
        b = CausalNode("b", ["a_out"], ["y"], lambda d: {"y": d["a_out"]})

        with pytest.raises(ValueError, match="nonexistent|input|missing"):
            CausalGraph([a, b])


class TestCausalGraphFirstOrderLag:
    def test_lag_smooths_step_change(self):
        """A step input should produce exponential approach to target."""
        from app.engine.modulation.causal_graph import CausalGraph, CausalNode

        node = CausalNode(
            name="lag", inputs=["x"], outputs=["y"],
            transfer_fn=lambda d: {"y": d["x"]},
            time_constant_ms=1000.0,  # 1 second tau
        )
        graph = CausalGraph([node], external_inputs={"x"})

        # Initial external input = 0, state starts at 0
        r1 = graph.step(0.1, {"x": 0.0})
        assert r1["y"] == pytest.approx(0.0, abs=0.01)

        # Step to 10, step 0.1s → expected: 10*(1-e^(-0.1/1.0)) ≈ 10*0.095 ≈ 0.95
        r2 = graph.step(0.1, {"x": 10.0})
        expected = 10.0 * (1.0 - math.exp(-0.1 / 1.0))
        assert r2["y"] == pytest.approx(expected, rel=0.05)

        # Another step → continued approach
        r3 = graph.step(0.1, {"x": 10.0})
        # After 2 steps of 0.1s each: target=10, tau=1, t=0.2
        expected2 = 10.0 * (1.0 - math.exp(-0.2 / 1.0))
        assert r3["y"] == pytest.approx(expected2, rel=0.05)

    def test_lag_converges_to_target(self):
        """After many small steps, output should converge to target."""
        from app.engine.modulation.causal_graph import CausalGraph, CausalNode

        node = CausalNode(
            name="conv", inputs=["x"], outputs=["y"],
            transfer_fn=lambda d: {"y": d["x"]},
            time_constant_ms=200.0,
        )
        graph = CausalGraph([node], external_inputs={"x"})

        for _ in range(50):
            result = graph.step(0.05, {"x": 5.0})

        assert result["y"] == pytest.approx(5.0, rel=0.01)


class TestCausalGraphExternalInputs:
    def test_external_inputs_feed_initial_nodes(self):
        """External inputs provide values for nodes with no upstream producer."""
        from app.engine.modulation.causal_graph import CausalGraph, CausalNode

        a = CausalNode("a", ["x"], ["a_out"], lambda d: {"a_out": d["x"] * 2})
        b = CausalNode("b", ["a_out", "y"], ["b_out"],
                       lambda d: {"b_out": d["a_out"] + d["y"]})

        graph = CausalGraph([a, b], external_inputs={"x", "y"})
        # Run twice so first-order lag converges (cold start → steady state)
        graph.step(1.0, {"x": 3.0, "y": 4.0})
        result = graph.step(1.0, {"x": 3.0, "y": 4.0})

        # With dt=1s >> tau, lag is negligible
        assert result["b_out"] == pytest.approx(10.0, rel=0.05)

    def test_rapid_lag_when_dt_matches_tau(self):
        """When dt ≈ tau, output should reach ~63% of target in one step."""
        from app.engine.modulation.causal_graph import CausalGraph, CausalNode

        node = CausalNode(
            name="r", inputs=["x"], outputs=["y"],
            transfer_fn=lambda d: {"y": d["x"]},
            time_constant_ms=500.0,
        )
        graph = CausalGraph([node], external_inputs={"x"})

        result = graph.step(0.5, {"x": 10.0})
        expected = 10.0 * (1.0 - math.exp(-1.0))  # 63.2%
        assert result["y"] == pytest.approx(expected, rel=0.05)


class TestCausalGraphStatePersistence:
    def test_state_persists_between_steps(self):
        """CausalGraph.state preserves values across multiple step() calls."""
        from app.engine.modulation.causal_graph import CausalGraph, CausalNode

        node = CausalNode(
            name="s", inputs=["x"], outputs=["y"],
            transfer_fn=lambda d: {"y": d["x"]},
            time_constant_ms=1000.0,
        )
        graph = CausalGraph([node], external_inputs={"x"})

        r1 = graph.step(0.1, {"x": 10.0})
        r2 = graph.step(0.1, {"x": 10.0})

        # State should be progressing toward 10
        assert r2["y"] > r1["y"]

    def test_state_resets_with_new_graph(self):
        """A fresh CausalGraph starts with empty state."""
        from app.engine.modulation.causal_graph import CausalGraph, CausalNode

        node = CausalNode("r", ["x"], ["y"], lambda d: {"y": d["x"]})
        g1 = CausalGraph([node], external_inputs={"x"})
        g1.step(0.5, {"x": 100.0})

        g2 = CausalGraph([node], external_inputs={"x"})
        r = g2.step(0.5, {"x": 0.0})
        assert r["y"] == pytest.approx(0.0, abs=0.01)


# ---------------------------------------------------------------------------
# Factory function tests
# ---------------------------------------------------------------------------

class TestCreateDefaultGraph:
    def test_creates_graph_with_expected_outputs(self):
        """Default graph should produce expected Modifiers outputs."""
        from app.engine.modulation.causal_graph import create_default_graph

        graph = create_default_graph()
        assert graph is not None
        assert len(graph.nodes) > 5

        # Run one step with typical inputs
        result = graph.step(0.8, {
            "map_mmhg": 93.0,
            "paco2_mmhg": 40.0,
            "pao2_mmhg": 98.0,
            "ph": 7.40,
            "temperature_c": 37.0,
            "cardiac_output": 5.0,
            "exercise_intensity": 0.0,
            "damage_level": 0.0,
        })

        # Check key outputs exist
        for key in ("sa_rate_modifier", "contractility_modifier",
                     "tpr_modifier", "sympathetic_tone", "parasympathetic_tone"):
            assert key in result, f"Missing output: {key}"

    def test_exercise_increases_heart_rate(self):
        """Higher exercise intensity → higher sa_rate_modifier."""
        from app.engine.modulation.causal_graph import create_default_graph

        g1 = create_default_graph()
        g2 = create_default_graph()

        base = {"map_mmhg": 93.0, "paco2_mmhg": 40.0, "pao2_mmhg": 98.0,
                "ph": 7.40, "temperature_c": 37.0, "cardiac_output": 5.0,
                "damage_level": 0.0}

        # Run several steps to reach steady state
        for _ in range(10):
            g1.step(0.8, {**base, "exercise_intensity": 0.0})
            g2.step(0.8, {**base, "exercise_intensity": 0.7})

        r_rest = g1.step(0.8, {**base, "exercise_intensity": 0.0})
        r_ex = g2.step(0.8, {**base, "exercise_intensity": 0.7})

        assert r_ex["sa_rate_modifier"] > r_rest["sa_rate_modifier"]

    def test_damage_reduces_contractility(self):
        """Higher damage → lower contractility_modifier."""
        from app.engine.modulation.causal_graph import create_default_graph

        base = {"map_mmhg": 93.0, "paco2_mmhg": 40.0, "pao2_mmhg": 98.0,
                "ph": 7.40, "temperature_c": 37.0, "cardiac_output": 5.0,
                "exercise_intensity": 0.0}

        g_normal = create_default_graph()
        g_damaged = create_default_graph()

        for _ in range(10):
            g_normal.step(0.8, {**base, "damage_level": 0.0})
            g_damaged.step(0.8, {**base, "damage_level": 0.5})

        r_norm = g_normal.step(0.8, {**base, "damage_level": 0.0})
        r_dmg = g_damaged.step(0.8, {**base, "damage_level": 0.5})

        assert r_dmg["contractility_modifier"] < r_norm["contractility_modifier"]


# ---------------------------------------------------------------------------
# Performance tests
# ---------------------------------------------------------------------------

class TestCausalGraphPerformance:
    def test_step_under_5ms(self):
        """CausalGraph.step() must complete in under 5ms for real-time use."""
        import time
        from app.engine.modulation.causal_graph import create_default_graph

        graph = create_default_graph()
        inputs = {
            "map_mmhg": 93.0, "paco2_mmhg": 40.0, "pao2_mmhg": 98.0,
            "ph": 7.40, "temperature_c": 37.0, "cardiac_output": 5.0,
            "exercise_intensity": 0.3, "damage_level": 0.1,
        }

        # Warm-up
        for _ in range(5):
            graph.step(0.8, inputs)

        times = []
        for _ in range(100):
            t0 = time.perf_counter()
            graph.step(0.8, inputs)
            times.append(time.perf_counter() - t0)

        avg_ms = sum(times) / len(times) * 1000
        assert avg_ms < 5.0, f"CausalGraph.step() avg {avg_ms:.2f}ms exceeds 5ms limit"

    def test_memory_stable_over_many_steps(self):
        """Repeated steps should not leak memory."""
        import tracemalloc
        from app.engine.modulation.causal_graph import create_default_graph

        graph = create_default_graph()
        inputs = {
            "map_mmhg": 93.0, "paco2_mmhg": 40.0, "pao2_mmhg": 98.0,
            "ph": 7.40, "temperature_c": 37.0, "cardiac_output": 5.0,
            "exercise_intensity": 0.0, "damage_level": 0.0,
        }

        tracemalloc.start()
        snap1 = tracemalloc.take_snapshot()

        for _ in range(1000):
            graph.step(0.8, inputs)

        snap2 = tracemalloc.take_snapshot()
        tracemalloc.stop()

        stats = snap2.compare_to(snap1, 'lineno')
        total_diff = sum(s.size_diff for s in stats)
        assert total_diff < 1_000_000, f"Memory grew by {total_diff / 1024:.0f} KB"

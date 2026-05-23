"""Performance benchmarks for simulation pipeline.

Ensures real-time streaming requirements are met.
"""
import time
import tracemalloc

import pytest


def _make_default_conduction(rr_sec=0.8):
    from app.engine.core.types import ConductionResult, ActionPotential
    return ConductionResult(
        beat_index=0, rr_sec=rr_sec,
        activation_times={'sa': 0.0, 'av': 80.0, 'his': 120.0, 'purkinje': 140.0},
        node_aps={
            'sa': ActionPotential(apd_ms=200), 'av': ActionPotential(apd_ms=200),
            'his': ActionPotential(apd_ms=300), 'purkinje': ActionPotential(apd_ms=300),
        },
        pr_interval_ms=120.0, qrs_duration_ms=80.0, qt_interval_ms=380.0,
        p_wave_present=True, p_wave_retrograde=False,
        beat_kind='sinus', conducted=True,
    )


class TestPerformanceBenchmarks:
    def test_physical_pcg_synthesis_under_50ms(self):
        """Physical PCG synthesize() should complete in <50ms average."""
        from app.engine.core.physical_pcg import PhysicalPcgSynthesizer
        from app.engine.core.types import Modifiers

        synth = PhysicalPcgSynthesizer()
        conduction = _make_default_conduction()
        modifiers = Modifiers()

        for _ in range(5):
            synth.synthesize(conduction, modifiers)

        times = []
        for _ in range(50):
            t0 = time.perf_counter()
            synth.synthesize(conduction, modifiers)
            times.append(time.perf_counter() - t0)

        avg_ms = sum(times) / len(times) * 1000
        assert avg_ms < 50.0, f"PCG synthesis avg {avg_ms:.1f}ms exceeds 50ms limit"

    def test_parametric_pcg_synthesis_under_10ms(self):
        """Parametric PCG (fallback) should be faster than 10ms."""
        from app.engine.core.parametric_pcg import ParametricPcgSynthesizer
        from app.engine.core.types import Modifiers

        synth = ParametricPcgSynthesizer()
        conduction = _make_default_conduction()
        modifiers = Modifiers()

        for _ in range(5):
            synth.synthesize(conduction, modifiers)

        times = []
        for _ in range(50):
            t0 = time.perf_counter()
            synth.synthesize(conduction, modifiers)
            times.append(time.perf_counter() - t0)

        avg_ms = sum(times) / len(times) * 1000
        assert avg_ms < 10.0, f"Parametric PCG avg {avg_ms:.1f}ms exceeds 10ms"

    def test_no_memory_leak_over_1000_beats(self):
        """Repeated synthesis should not leak memory significantly."""
        from app.engine.core.physical_pcg import PhysicalPcgSynthesizer
        from app.engine.core.types import Modifiers
        import numpy as np

        synth = PhysicalPcgSynthesizer()
        conduction = _make_default_conduction()
        modifiers = Modifiers()

        tracemalloc.start()
        start_snapshot = tracemalloc.take_snapshot()

        for _ in range(1000):
            synth.synthesize(conduction, modifiers)

        end_snapshot = tracemalloc.take_snapshot()
        tracemalloc.stop()

        stats = end_snapshot.compare_to(start_snapshot, 'lineno')
        total_diff = sum(s.size_diff for s in stats)
        assert total_diff < 5_000_000, f"Memory grew by {total_diff / 1024:.0f} KB"

    def test_resonator_processing_efficient(self):
        """ResonatorBank.process() should be fast for typical beat lengths."""
        from app.engine.core.acoustic_resonator import ResonatorBank
        import numpy as np

        bank = ResonatorBank(
            frequencies=[45, 70, 100, 35, 55],
            Q_values=[8, 12, 15, 6, 10],
            gains=[0.3, 0.4, 0.3, 0.15, 0.15],
            sample_rate=4000,
        )

        impulse = np.zeros(3200)
        impulse[10] = 1.0

        t0 = time.perf_counter()
        for _ in range(100):
            bank.reset()
            bank.process(impulse)
        elapsed = time.perf_counter() - t0

        avg_ms = elapsed / 100 * 1000
        assert avg_ms < 10.0, f"Resonator bank avg {avg_ms:.1f}ms per call"

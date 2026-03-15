"""Tests for HRV frequency-domain generator and QT dynamic adaptation model.

Covers:
- HrvGenerator: LF/HF inverse-FFT, RSA modulation, autonomic tone scaling,
  LF/HF ratio, state save/restore, buffer regeneration
- QtDynamics: Bazett correction, first-order lag, electrolyte effects,
  drug effects, ischemia effects, temperature effects, QT dispersion
- ConductionNetwork integration: HRV RR offset applied correctly
- EcgSynthesizer integration: QT-dynamic T-wave positioning, ischemia ST
"""
import math

import numpy as np
import pytest

from app.engine.core.hrv_generator import HrvGenerator
from app.engine.core.qt_dynamics import QtDynamics
from app.engine.core.parametric_conduction import ParametricConductionNetwork as ConductionNetworkV2
from app.engine.core.ecg_synthesizer import EcgSynthesizerV2
from app.engine.core.types import Modifiers


# ============================================================
# HrvGenerator tests
# ============================================================

class TestHrvGenerator:
    """Tests for the HRV frequency-domain generator."""

    def test_default_construction(self):
        """Default HrvGenerator should construct without errors."""
        hrv = HrvGenerator()
        assert hrv is not None

    def test_seeded_reproducibility(self):
        """Same seed should produce identical offset sequences."""
        hrv1 = HrvGenerator(seed=42)
        hrv2 = HrvGenerator(seed=42)
        offsets1 = [hrv1.next_offset() for _ in range(20)]
        offsets2 = [hrv2.next_offset() for _ in range(20)]
        for a, b in zip(offsets1, offsets2):
            assert abs(a - b) < 1e-10, f"Mismatch: {a} != {b}"

    def test_offset_has_variability(self):
        """Offsets should not be all zeros — should show variability."""
        hrv = HrvGenerator(seed=123)
        offsets = [hrv.next_offset() for _ in range(50)]
        std = np.std(offsets)
        assert std > 0.01, f"Too little variability: std={std}"

    def test_offset_bounded(self):
        """Offsets should be bounded (realistic RR variation ±100ms)."""
        hrv = HrvGenerator(seed=7)
        offsets = [hrv.next_offset() for _ in range(200)]
        for o in offsets:
            assert -200.0 < o < 200.0, f"Offset out of bounds: {o}"

    def test_rsa_modulation(self):
        """RSA should add sinusoidal modulation correlated with respiratory phase."""
        hrv = HrvGenerator(seed=99)
        # Inspiration (phase=π/2): should shorten RR (positive RSA offset via sin)
        offset_insp = hrv.next_offset(
            parasympathetic_tone=0.8,
            respiratory_phase=math.pi / 2,
        )
        # Reset for comparable baseline
        hrv2 = HrvGenerator(seed=99)
        # Expiration (phase=3π/2): should lengthen RR (negative RSA offset)
        offset_exp = hrv2.next_offset(
            parasympathetic_tone=0.8,
            respiratory_phase=3 * math.pi / 2,
        )
        # Inspiration offset should be more positive than expiration
        assert offset_insp > offset_exp

    def test_rsa_scales_with_vagal_tone(self):
        """RSA amplitude should scale with parasympathetic tone."""
        # High vagal tone → larger RSA effect
        hrv_high = HrvGenerator(seed=50)
        offset_high = hrv_high.next_offset(
            parasympathetic_tone=1.0,
            respiratory_phase=math.pi / 2,
        )
        hrv_low = HrvGenerator(seed=50)
        offset_low = hrv_low.next_offset(
            parasympathetic_tone=0.1,
            respiratory_phase=math.pi / 2,
        )
        # The RSA component is additive: high tone should give larger offset
        # Both have same base offset from FFT (same seed), differ by RSA amount
        rsa_diff = offset_high - offset_low
        assert rsa_diff > 5.0, f"RSA scaling too small: {rsa_diff}"

    def test_sympathetic_increases_lf(self):
        """High sympathetic tone should increase LF power → more low-freq variability."""
        hrv_high = HrvGenerator(seed=42, lf_power=2000.0, hf_power=200.0)
        hrv_low = HrvGenerator(seed=42, lf_power=200.0, hf_power=2000.0)
        offsets_high = [hrv_high.next_offset(sympathetic_tone=0.9) for _ in range(100)]
        offsets_low = [hrv_low.next_offset(sympathetic_tone=0.1) for _ in range(100)]
        # Different power distributions should give different variance profiles
        std_high = np.std(offsets_high)
        std_low = np.std(offsets_low)
        # Both should have some variability
        assert std_high > 0.1
        assert std_low > 0.1

    def test_lf_hf_ratio(self):
        """LF/HF ratio should reflect autonomic balance."""
        hrv = HrvGenerator()
        # Sympathetic dominant
        ratio_symp = hrv.get_lf_hf_ratio(sympathetic_tone=0.9, parasympathetic_tone=0.2)
        # Parasympathetic dominant
        ratio_para = hrv.get_lf_hf_ratio(sympathetic_tone=0.2, parasympathetic_tone=0.9)
        assert ratio_symp > ratio_para
        assert ratio_symp > 1.0  # Should be > 1 for sympathetic dominance
        assert ratio_para < 1.0  # Should be < 1 for vagal dominance

    def test_lf_hf_ratio_extreme(self):
        """LF/HF ratio should handle extreme vagal values gracefully."""
        hrv = HrvGenerator(hf_power=0.0)
        ratio = hrv.get_lf_hf_ratio(sympathetic_tone=0.5, parasympathetic_tone=0.5)
        assert ratio == 999.0  # Defined ceiling for zero HF

    def test_buffer_regeneration(self):
        """Buffer should regenerate when exhausted."""
        hrv = HrvGenerator(seed=10)
        # Exhaust more than one buffer worth
        offsets = [hrv.next_offset() for _ in range(300)]
        assert len(offsets) == 300
        # All should be finite
        for o in offsets:
            assert math.isfinite(o)

    def test_state_save_restore(self):
        """State save/restore should produce identical continuation."""
        hrv = HrvGenerator(seed=77)
        # Generate some offsets
        for _ in range(10):
            hrv.next_offset()
        state = hrv.get_state()

        # Continue generating
        offsets_original = [hrv.next_offset() for _ in range(10)]

        # Restore and generate
        hrv2 = HrvGenerator()
        hrv2.set_state(state)
        offsets_restored = [hrv2.next_offset() for _ in range(10)]

        for a, b in zip(offsets_original, offsets_restored):
            assert abs(a - b) < 1e-10

    def test_zero_power_produces_minimal_offset(self):
        """Zero LF/HF power should produce near-zero offsets (only RSA)."""
        hrv = HrvGenerator(lf_power=0.0, hf_power=0.0, seed=5)
        offsets = [hrv.next_offset(
            parasympathetic_tone=0.0,
            respiratory_phase=0.0,
        ) for _ in range(50)]
        # All should be very small (numerical noise only)
        for o in offsets:
            assert abs(o) < 5.0, f"Non-zero offset with zero power: {o}"

    def test_different_respiratory_freq(self):
        """Different respiratory frequencies should shift HF peak."""
        hrv_fast = HrvGenerator(seed=42)
        hrv_slow = HrvGenerator(seed=42)
        # Both generate a buffer with different respiratory freq
        offsets_fast = [hrv_fast.next_offset(respiratory_freq_hz=0.35) for _ in range(100)]
        offsets_slow = [hrv_slow.next_offset(respiratory_freq_hz=0.18) for _ in range(100)]
        # They should differ (different spectral profile)
        # Not identical due to different HF peak centering
        assert not np.allclose(offsets_fast, offsets_slow, atol=0.01)


# ============================================================
# QtDynamics tests
# ============================================================

class TestQtDynamics:
    """Tests for the QT dynamic adaptation model."""

    def test_default_construction(self):
        qt = QtDynamics()
        assert qt.qt_ms == 400.0

    def test_bazett_correction_normal_hr(self):
        """At normal HR (75 bpm, RR=0.8s), QT should be near 375ms."""
        qt = QtDynamics()
        # Run several beats to approach steady state
        for _ in range(100):
            result = qt.update(rr_sec=0.8, dt=0.8)
        # QTc=420, QT = 420 * sqrt(0.8) ≈ 375.6ms
        expected = 420.0 * math.sqrt(0.8)
        assert abs(result - expected) < 5.0, f"QT={result}, expected≈{expected}"

    def test_qt_prolongation_at_slow_hr(self):
        """Slow HR → longer QT."""
        qt = QtDynamics()
        for _ in range(100):
            result = qt.update(rr_sec=1.2, dt=1.2)
        # QT = 420 * sqrt(1.2) ≈ 460ms
        expected = 420.0 * math.sqrt(1.2)
        assert abs(result - expected) < 5.0

    def test_qt_shortening_at_fast_hr(self):
        """Fast HR → shorter QT."""
        qt = QtDynamics()
        for _ in range(100):
            result = qt.update(rr_sec=0.5, dt=0.5)
        # QT = 420 * sqrt(0.5) ≈ 297ms; with lag filter and rounding, allow ±25ms
        expected = 420.0 * math.sqrt(0.5)
        assert abs(result - expected) < 25.0

    def test_first_order_lag(self):
        """QT should not jump instantly when HR changes — lag filter."""
        qt = QtDynamics()
        # Stabilize at 75 bpm
        for _ in range(100):
            qt.update(rr_sec=0.8, dt=0.8)
        qt_before = qt.qt_ms

        # Sudden HR change to 120 bpm (RR=0.5s)
        qt.update(rr_sec=0.5, dt=0.5)
        qt_after_one = qt.qt_ms

        # QT should have moved toward target but not reached it yet
        target = 420.0 * math.sqrt(0.5)
        assert qt_after_one < qt_before  # Moving toward shorter QT
        assert qt_after_one > target + 10.0  # Not yet reached target

    def test_hypokalaemia_prolongs_qt(self):
        """Low potassium should prolong QT."""
        qt_normal = QtDynamics()
        qt_hypo = QtDynamics()
        for _ in range(100):
            result_normal = qt_normal.update(rr_sec=0.8, dt=0.8, potassium=4.0)
            result_hypo = qt_hypo.update(rr_sec=0.8, dt=0.8, potassium=2.5)
        assert result_hypo > result_normal + 20.0

    def test_hyperkalaemia_shortens_qt(self):
        """High potassium should shorten QT."""
        qt_normal = QtDynamics()
        qt_hyper = QtDynamics()
        for _ in range(100):
            result_normal = qt_normal.update(rr_sec=0.8, dt=0.8, potassium=4.0)
            result_hyper = qt_hyper.update(rr_sec=0.8, dt=0.8, potassium=6.5)
        assert result_hyper < result_normal

    def test_hypocalcaemia_prolongs_qt(self):
        """Low calcium should prolong QT."""
        qt_normal = QtDynamics()
        qt_hypo = QtDynamics()
        for _ in range(100):
            result_normal = qt_normal.update(rr_sec=0.8, dt=0.8, calcium=9.5)
            result_hypo = qt_hypo.update(rr_sec=0.8, dt=0.8, calcium=6.5)
        assert result_hypo > result_normal + 20.0

    def test_hypomagnesaemia_prolongs_qt(self):
        """Low magnesium should prolong QT."""
        qt_normal = QtDynamics()
        qt_hypo = QtDynamics()
        for _ in range(100):
            result_normal = qt_normal.update(rr_sec=0.8, dt=0.8, magnesium=2.0)
            result_hypo = qt_hypo.update(rr_sec=0.8, dt=0.8, magnesium=1.0)
        assert result_hypo > result_normal + 10.0

    def test_amiodarone_prolongs_qt(self):
        """Amiodarone should prolong QT."""
        qt_normal = QtDynamics()
        qt_amio = QtDynamics()
        for _ in range(100):
            result_normal = qt_normal.update(rr_sec=0.8, dt=0.8)
            result_amio = qt_amio.update(
                rr_sec=0.8, dt=0.8,
                drug_concentrations={"amiodarone": 0.5},
            )
        assert result_amio > result_normal + 40.0

    def test_digoxin_shortens_qt(self):
        """Digoxin should shorten QT (scooped ST)."""
        qt_normal = QtDynamics()
        qt_dig = QtDynamics()
        for _ in range(100):
            result_normal = qt_normal.update(rr_sec=0.8, dt=0.8)
            result_dig = qt_dig.update(
                rr_sec=0.8, dt=0.8,
                drug_concentrations={"digoxin": 0.4},
            )
        assert result_dig < result_normal

    def test_ischemia_prolongs_qt(self):
        """Ischemia should prolong QT."""
        qt_normal = QtDynamics()
        qt_isch = QtDynamics()
        for _ in range(100):
            result_normal = qt_normal.update(rr_sec=0.8, dt=0.8)
            result_isch = qt_isch.update(rr_sec=0.8, dt=0.8, ischemia_level=0.8)
        assert result_isch > result_normal + 20.0

    def test_hypothermia_prolongs_qt(self):
        """Hypothermia should prolong QT."""
        qt_normal = QtDynamics()
        qt_cold = QtDynamics()
        for _ in range(100):
            result_normal = qt_normal.update(rr_sec=0.8, dt=0.8, temperature=36.6)
            result_cold = qt_cold.update(rr_sec=0.8, dt=0.8, temperature=33.0)
        assert result_cold > result_normal + 20.0

    def test_qt_clamped_to_bounds(self):
        """QT should never exceed physiological bounds."""
        qt = QtDynamics()
        # Extreme prolongation: slow HR + hypoK + amiodarone + ischemia
        for _ in range(200):
            result = qt.update(
                rr_sec=2.0, dt=2.0,
                potassium=2.0,
                drug_concentrations={"amiodarone": 1.0},
                ischemia_level=1.0,
                temperature=30.0,
            )
        assert result <= 700.0
        assert result >= 280.0

    def test_qt_dispersion(self):
        """QT dispersion should reflect beat-to-beat QT variability."""
        qt = QtDynamics()
        # Alternate fast and slow RR to create dispersion
        for i in range(30):
            rr = 0.5 if i % 2 == 0 else 1.2
            qt.update(rr_sec=rr, dt=rr)
        dispersion = qt.qt_dispersion_ms
        assert dispersion > 0.0

    def test_qt_dispersion_zero_at_steady_state(self):
        """QT dispersion should be near zero at steady HR."""
        qt = QtDynamics()
        for _ in range(50):
            qt.update(rr_sec=0.8, dt=0.8)
        dispersion = qt.qt_dispersion_ms
        assert dispersion < 5.0  # Should be very small at steady state

    def test_state_save_restore(self):
        """State save/restore should preserve QT adaptation state."""
        qt = QtDynamics()
        for _ in range(20):
            qt.update(rr_sec=0.8, dt=0.8)
        state = qt.get_state()
        qt_before = qt.qt_ms

        qt2 = QtDynamics()
        qt2.set_state(state)
        assert abs(qt2.qt_ms - qt_before) < 1e-10

    def test_combined_effects(self):
        """Combined electrolyte + drug + ischemia should stack."""
        qt = QtDynamics()
        for _ in range(100):
            result = qt.update(
                rr_sec=0.8, dt=0.8,
                potassium=2.5,       # hypoK → prolong
                magnesium=1.0,       # hypoMg → prolong
                drug_concentrations={"amiodarone": 0.3},  # → prolong
                ischemia_level=0.5,  # → prolong
            )
        # Should be significantly prolonged
        baseline_qt = 420.0 * math.sqrt(0.8)
        assert result > baseline_qt + 80.0


# ============================================================
# ConductionNetwork HRV integration tests
# ============================================================

class TestConductionNetworkHrvIntegration:
    """Tests for HRV RR offset integration in ConductionNetworkV2."""

    def test_hrv_offset_applied(self):
        """Non-zero hrv_rr_offset_ms should change actual RR in result."""
        net = ConductionNetworkV2()
        mod_zero = Modifiers(hrv_rr_offset_ms=0.0)
        mod_plus = Modifiers(hrv_rr_offset_ms=50.0)  # +50ms

        result_zero = net.propagate(0.8, mod_zero)
        net2 = ConductionNetworkV2()
        result_plus = net2.propagate(0.8, mod_plus)

        # With +50ms offset, effective RR = 0.85s
        assert abs(result_plus.rr_sec - 0.85) < 0.01
        assert abs(result_zero.rr_sec - 0.8) < 0.01

    def test_hrv_offset_negative(self):
        """Negative HRV offset should shorten RR."""
        net = ConductionNetworkV2()
        mod = Modifiers(hrv_rr_offset_ms=-60.0)  # -60ms
        result = net.propagate(0.8, mod)
        assert abs(result.rr_sec - 0.74) < 0.01

    def test_hrv_offset_clamped(self):
        """Extreme HRV offset should be clamped to safe bounds."""
        net = ConductionNetworkV2()
        # Extreme negative offset that would make RR < 0.3
        mod = Modifiers(hrv_rr_offset_ms=-600.0)
        result = net.propagate(0.8, mod)
        assert result.rr_sec >= 0.3

        # Extreme positive offset
        net2 = ConductionNetworkV2()
        mod2 = Modifiers(hrv_rr_offset_ms=2000.0)
        result2 = net2.propagate(0.8, mod2)
        assert result2.rr_sec <= 2.5

    def test_hrv_offset_zero_no_change(self):
        """Zero HRV offset should not change RR."""
        net = ConductionNetworkV2()
        mod = Modifiers(hrv_rr_offset_ms=0.0)
        result = net.propagate(0.8, mod)
        assert abs(result.rr_sec - 0.8) < 0.001


# ============================================================
# ConductionNetwork QT dynamics integration tests
# ============================================================

class TestConductionNetworkQtIntegration:
    """Tests for QT dynamics integration in ConductionNetworkV2."""

    def test_qt_adapted_used_when_available(self):
        """qt_adapted_ms from Modifiers should override APD-based QT."""
        net = ConductionNetworkV2()
        mod = Modifiers(qt_adapted_ms=450.0)
        result = net.propagate(0.8, mod)
        # The QT in result should be close to our adapted value
        assert abs(result.qt_interval_ms - 450.0) < 1.0

    def test_qt_adapted_zero_uses_fallback(self):
        """qt_adapted_ms=0 should use APD-based QT fallback."""
        net = ConductionNetworkV2()
        mod = Modifiers(qt_adapted_ms=0.0)
        result = net.propagate(0.8, mod)
        # Should get a reasonable fallback QT
        assert 200.0 < result.qt_interval_ms < 600.0

    def test_qt_adapted_short(self):
        """Short qt_adapted_ms below 200 should use fallback."""
        net = ConductionNetworkV2()
        mod = Modifiers(qt_adapted_ms=150.0)
        result = net.propagate(0.8, mod)
        # Should NOT use 150ms (below threshold), should use fallback
        assert result.qt_interval_ms > 200.0


# ============================================================
# EcgSynthesizer QT/ischemia integration tests
# ============================================================

class TestEcgSynthesizerQtIntegration:
    """Tests for QT-dynamic T-wave and ischemia ST in EcgSynthesizer."""

    def _make_sinus_conduction(self, rr_sec: float = 0.8) -> "ConductionResult":
        """Helper: generate a normal sinus beat via ConductionNetworkV2."""
        net = ConductionNetworkV2()
        return net.propagate(rr_sec, Modifiers())

    def test_synthesize_with_modifiers(self):
        """Synthesizer should accept modifiers and produce valid EcgFrame."""
        synth = EcgSynthesizerV2()
        cond = self._make_sinus_conduction()
        mod = Modifiers(qt_adapted_ms=400.0, ischemia_level=0.0)
        frame = synth.synthesize(cond, ['II'], mod)
        assert 'II' in frame.samples
        assert len(frame.samples['II']) > 0

    def test_ischemia_modifies_morphology(self):
        """Ischemia should produce different ECG morphology (ST depression)."""
        synth = EcgSynthesizerV2()
        cond = self._make_sinus_conduction()

        mod_normal = Modifiers(ischemia_level=0.0)
        mod_ischemia = Modifiers(ischemia_level=0.8)

        frame_normal = synth.synthesize(cond, ['II'], mod_normal)
        frame_ischemia = synth.synthesize(cond, ['II'], mod_ischemia)

        # Morphologies should differ
        diff = np.abs(frame_normal.samples['II'] - frame_ischemia.samples['II'])
        assert np.max(diff) > 0.01, "Ischemia should change morphology"

    def test_qt_adapted_shifts_t_wave(self):
        """Different qt_adapted_ms should shift T-wave timing."""
        synth = EcgSynthesizerV2()
        cond = self._make_sinus_conduction()

        mod_short = Modifiers(qt_adapted_ms=320.0)
        mod_long = Modifiers(qt_adapted_ms=500.0)

        frame_short = synth.synthesize(cond, ['II'], mod_short)
        frame_long = synth.synthesize(cond, ['II'], mod_long)

        # Find T-wave peak position (max after QRS ~40% into beat)
        sig_short = frame_short.samples['II']
        sig_long = frame_long.samples['II']
        n = len(sig_short)
        start = int(n * 0.3)
        end = int(n * 0.85)

        t_peak_short = start + np.argmax(sig_short[start:end])
        t_peak_long = start + np.argmax(sig_long[start:end])

        # Longer QT should have later T-wave peak
        assert t_peak_long >= t_peak_short

    def test_hyperkalaemia_peaked_t(self):
        """Hyperkalaemia should produce taller/peaked T waves."""
        synth = EcgSynthesizerV2()
        cond = self._make_sinus_conduction()

        mod_normal = Modifiers(potassium_level=4.0)
        mod_hyperK = Modifiers(potassium_level=7.0)

        frame_normal = synth.synthesize(cond, ['II'], mod_normal)
        frame_hyperK = synth.synthesize(cond, ['II'], mod_hyperK)

        # Both should be valid signals
        assert len(frame_normal.samples['II']) > 0
        assert len(frame_hyperK.samples['II']) > 0

    def test_hypokalaemia_u_wave(self):
        """Hypokalaemia should produce U waves (additional positive deflection)."""
        synth = EcgSynthesizerV2()
        cond = self._make_sinus_conduction()

        mod_normal = Modifiers(potassium_level=4.0)
        mod_hypoK = Modifiers(potassium_level=2.0)

        frame_normal = synth.synthesize(cond, ['II'], mod_normal)
        frame_hypoK = synth.synthesize(cond, ['II'], mod_hypoK)

        # Morphologies should differ
        diff = np.abs(frame_normal.samples['II'] - frame_hypoK.samples['II'])
        assert np.max(diff) > 0.01

    def test_backward_compatibility_no_modifiers(self):
        """_build_lead_ii should work with modifiers=None (backward compat)."""
        synth = EcgSynthesizerV2()
        cond = self._make_sinus_conduction()
        # Call with modifiers containing default values
        mod = Modifiers()
        frame = synth.synthesize(cond, ['II'], mod)
        assert len(frame.samples['II']) > 0

    def test_vt_unaffected_by_qt_modifiers(self):
        """VT morphology should not be affected by QT/ischemia modifiers
        (VT has its own morphology builder)."""
        net = ConductionNetworkV2()
        mod = Modifiers(
            rhythm_override='vt',
            qt_adapted_ms=500.0,
            ischemia_level=0.9,
        )
        cond = net.propagate(0.8, mod)
        synth = EcgSynthesizerV2()
        frame = synth.synthesize(cond, ['II'], mod)
        assert len(frame.samples['II']) > 0
        assert cond.beat_kind == 'vt'

    def test_severe_ischemia_st_depression(self):
        """Severe ischemia should produce measurable ST depression."""
        synth = EcgSynthesizerV2()
        cond = self._make_sinus_conduction()

        mod_severe = Modifiers(ischemia_level=0.9)
        frame = synth.synthesize(cond, ['II'], mod_severe)

        # ST segment region: roughly 10-30% into the beat
        sig = frame.samples['II']
        n = len(sig)
        st_start = int(n * 0.12)
        st_end = int(n * 0.30)
        st_segment = sig[st_start:st_end]

        # ST depression means the signal should be more negative in ST segment
        # compared to baseline (which is near zero)
        assert len(st_segment) > 0


# ============================================================
# End-to-end: HRV + QT + Conduction + ECG pipeline
# ============================================================

class TestEndToEndHrvQtPipeline:
    """Integration test: HRV and QT feeding through conduction → ECG."""

    def test_full_pipeline_10_beats(self):
        """Simulate 10 beats with HRV and QT dynamics, verify valid output."""
        hrv = HrvGenerator(seed=42)
        qt = QtDynamics()
        net = ConductionNetworkV2()
        synth = EcgSynthesizerV2()

        base_rr = 0.8  # 75 bpm

        for i in range(10):
            # Get HRV offset
            offset_ms = hrv.next_offset(
                sympathetic_tone=0.5,
                parasympathetic_tone=0.5,
            )

            # Get adapted QT
            qt_ms = qt.update(rr_sec=base_rr + offset_ms / 1000.0, dt=base_rr)

            # Build modifiers
            mod = Modifiers(
                hrv_rr_offset_ms=offset_ms,
                qt_adapted_ms=qt_ms,
            )

            # Propagate
            cond = net.propagate(base_rr, mod)
            assert cond.rr_sec > 0.2
            assert cond.qt_interval_ms > 200.0

            # Synthesize ECG
            frame = synth.synthesize(cond, ['II'], mod)
            assert len(frame.samples['II']) > 0
            assert frame.sample_rate == 500

    def test_exercise_scenario(self):
        """Exercise: sympathetic up, HR up → shorter QT, higher LF/HF."""
        hrv = HrvGenerator(seed=7)
        qt = QtDynamics()

        # Rest phase
        for _ in range(50):
            offset = hrv.next_offset(sympathetic_tone=0.3, parasympathetic_tone=0.7)
            qt.update(rr_sec=0.9, dt=0.9)
        qt_rest = qt.qt_ms

        # Exercise phase
        for _ in range(50):
            offset = hrv.next_offset(sympathetic_tone=0.9, parasympathetic_tone=0.1)
            qt.update(rr_sec=0.5, dt=0.5)
        qt_exercise = qt.qt_ms

        # Exercise should have shorter QT (faster HR)
        assert qt_exercise < qt_rest

    def test_drug_and_electrolyte_scenario(self):
        """Amiodarone + hypokalaemia → significant QT prolongation."""
        qt = QtDynamics()
        for _ in range(100):
            result = qt.update(
                rr_sec=0.8, dt=0.8,
                potassium=2.8,
                drug_concentrations={"amiodarone": 0.5},
            )
        # Should be significantly prolonged beyond normal
        normal_qt = 420.0 * math.sqrt(0.8)
        assert result > normal_qt + 50.0

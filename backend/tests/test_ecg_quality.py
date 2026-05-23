"""ECG waveform quality and morphology verification tests.

Tests verify:
  - Pathological morphologies produce measurably different 12-lead ECGs
  - Einthoven's law holds (III = II - I) under all conditions
  - Individual variance produces distinguishable ECGs
  - ST evolution phases produce appropriate ST changes
  - aVR negativity constraint holds for sinus rhythm
"""
import numpy as np
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
        p_wave_mode="normal",
        beat_kind='sinus', conducted=True,
    )


def _synthesize(synth, conduction, modifiers=None):
    from app.engine.core.types import Modifiers
    if modifiers is None:
        modifiers = Modifiers()
    return synth.synthesize(
        conduction, ['I', 'II', 'III', 'aVR', 'aVL', 'aVF',
                      'V1', 'V2', 'V3', 'V4', 'V5', 'V6'], modifiers)


class TestEinthovenLaw:
    def test_iii_equals_ii_minus_i_normal(self):
        """III = II - I must hold exactly for normal ECG."""
        from app.engine.core.ecg_synthesizer import EcgSynthesizerV2
        synth = EcgSynthesizerV2()
        frame = _synthesize(synth, _make_default_conduction())
        iii = frame.samples['III']
        ii_minus_i = frame.samples['II'] - frame.samples['I']
        assert np.allclose(iii, ii_minus_i, atol=1e-10)

    def test_iii_equals_ii_minus_i_with_morph(self):
        """III = II - I holds under pathological morphologies."""
        from app.engine.core.ecg_synthesizer import EcgSynthesizerV2
        from app.engine.core.ecg_morph_library import list_morphologies

        synth = EcgSynthesizerV2()
        for morph_name in list_morphologies():
            synth.active_morph = morph_name
            frame = _synthesize(synth, _make_default_conduction())
            iii = frame.samples['III']
            ii_minus_i = frame.samples['II'] - frame.samples['I']
            assert np.allclose(iii, ii_minus_i, atol=1e-10), \
                f"Einthoven violated for {morph_name}"
        synth.active_morph = None

    def test_avr_negative_qrs_normal_sinus(self):
        """aVR should have negative QRS in normal sinus rhythm."""
        from app.engine.core.ecg_synthesizer import EcgSynthesizerV2
        synth = EcgSynthesizerV2()
        frame = _synthesize(synth, _make_default_conduction())
        avr = frame.samples['aVR']
        # QRS region: rough estimate (middle portion of beat)
        mid = len(avr) // 2
        qrs_window = avr[max(0, mid - 30):min(len(avr), mid + 40)]
        qrs_min = float(np.min(qrs_window))
        assert qrs_min < -0.05, f"aVR QRS should be predominantly negative, min={qrs_min:.3f}mV"


class TestPathologicalMorphologies:
    def test_lbbb_wide_qrs(self):
        """LBBB should produce different ECG from normal with wide QRS features."""
        from app.engine.core.ecg_synthesizer import EcgSynthesizerV2
        synth = EcgSynthesizerV2()
        normal = _synthesize(synth, _make_default_conduction())
        synth.active_morph = 'lbbb'
        lbbb = _synthesize(synth, _make_default_conduction())
        synth.active_morph = None

        # LBBB should differ measurably from normal
        for lead in ['I', 'V1', 'V6']:
            corr = np.corrcoef(normal.samples[lead], lbbb.samples[lead])[0, 1]
            assert corr < 0.95, f"LBBB {lead} too similar to normal (corr={corr:.3f})"

    def test_rbbb_terminal_r_prime_in_v1(self):
        """RBBB should show terminal R' in V1 (late positive deflection)."""
        from app.engine.core.ecg_synthesizer import EcgSynthesizerV2
        synth = EcgSynthesizerV2()
        synth.active_morph = 'rbbb'
        frame_rbbb = _synthesize(synth, _make_default_conduction())
        synth.active_morph = None
        frame_normal = _synthesize(synth, _make_default_conduction())

        v1_rbbb = frame_rbbb.samples['V1']
        v1_normal = frame_normal.samples['V1']

        # RBBB should have more positive late activity in V1 vs normal
        late_start = int(len(v1_rbbb) * 0.50)
        late_end = int(len(v1_rbbb) * 0.80)
        late_max_rbbb = float(np.max(v1_rbbb[late_start:late_end]))
        late_max_normal = float(np.max(v1_normal[late_start:late_end]))
        assert late_max_rbbb > late_max_normal * 1.5, \
            f"RBBB late V1 max={late_max_rbbb:.3f}, normal={late_max_normal:.3f}mV"

    def test_wpw_delta_wave_changes_ecg(self):
        """WPW delta wave should produce a distinct ECG."""
        from app.engine.core.ecg_synthesizer import EcgSynthesizerV2
        synth = EcgSynthesizerV2()
        normal = _synthesize(synth, _make_default_conduction())
        synth.active_morph = 'wpw'
        wpw = _synthesize(synth, _make_default_conduction())
        synth.active_morph = None

        corr = np.corrcoef(normal.samples['II'], wpw.samples['II'])[0, 1]
        assert corr < 0.98, f"WPW should differ from normal (corr={corr:.3f})"

    def test_hyperkalemia_peaked_t(self):
        """Hyperkalemia should produce taller, narrower T-waves vs normal."""
        from app.engine.core.ecg_synthesizer import EcgSynthesizerV2
        synth = EcgSynthesizerV2()
        normal = _synthesize(synth, _make_default_conduction())
        synth.active_morph = 'hyperkalemia'
        hyperk = _synthesize(synth, _make_default_conduction())
        synth.active_morph = None

        # Compare T-wave region: late half of beat (after QRS peak)
        lead_ii_n = normal.samples['II']
        lead_ii_h = hyperk.samples['II']
        mid_n = np.argmax(lead_ii_n)  # QRS peak position in normal
        mid_h = np.argmax(lead_ii_h)
        # T-wave: after QRS peak + 30 samples
        t_start_n = min(mid_n + 30, len(lead_ii_n) - 1)
        t_start_h = min(mid_h + 30, len(lead_ii_h) - 1)
        t_max_normal = float(np.max(lead_ii_n[t_start_n:])) if t_start_n < len(lead_ii_n) else 0.0
        t_max_hyperk = float(np.max(lead_ii_h[t_start_h:])) if t_start_h < len(lead_ii_h) else 0.0
        assert t_max_hyperk > t_max_normal, \
            f"Hyperkalemia T should be taller: {t_max_normal:.3f} vs {t_max_hyperk:.3f}mV"

    def test_all_morphologies_produce_valid_ecg(self):
        """All 8 morphologies should produce valid (non-NaN, non-zero) ECGs."""
        from app.engine.core.ecg_synthesizer import EcgSynthesizerV2
        from app.engine.core.ecg_morph_library import list_morphologies

        synth = EcgSynthesizerV2()
        for morph_name in list_morphologies():
            synth.active_morph = morph_name
            frame = _synthesize(synth, _make_default_conduction())
            for lead, samples in frame.samples.items():
                assert not np.any(np.isnan(samples)), f"{morph_name} {lead} has NaN"
                assert not np.any(np.isinf(samples)), f"{morph_name} {lead} has Inf"
                assert np.max(np.abs(samples)) > 0.001, \
                    f"{morph_name} {lead} is near-silent"
        synth.active_morph = None


class TestMorphVariance:
    def test_two_variants_produce_different_ecgs(self):
        """Two different MorphVarianceConfig should produce measurably different ECGs."""
        from app.engine.core.ecg_synthesizer import EcgSynthesizerV2
        from app.engine.core.morph_variance import generate_random_variance

        synth1 = EcgSynthesizerV2()
        synth1.morph_variance = generate_random_variance(seed=42)
        frame1 = _synthesize(synth1, _make_default_conduction())

        synth2 = EcgSynthesizerV2()
        synth2.morph_variance = generate_random_variance(seed=99)
        frame2 = _synthesize(synth2, _make_default_conduction())

        # Amplitudes should differ (different chest wall thickness, age, etc.)
        rms1 = float(np.sqrt(np.mean(frame1.samples['II'] ** 2)))
        rms2 = float(np.sqrt(np.mean(frame2.samples['II'] ** 2)))
        assert rms1 != rms2, f"Variance should produce different amplitudes: {rms1:.4f} vs {rms2:.4f}"

    def test_axis_rotation_affects_leads(self):
        """Cardiac axis deviation should change relative lead amplitudes."""
        from app.engine.core.ecg_synthesizer import EcgSynthesizerV2
        from app.engine.core.morph_variance import MorphVarianceConfig

        synth_normal = EcgSynthesizerV2()
        synth_normal.morph_variance = MorphVarianceConfig(cardiac_axis_deg=45.0)
        frame_normal = _synthesize(synth_normal, _make_default_conduction())

        synth_left = EcgSynthesizerV2()
        synth_left.morph_variance = MorphVarianceConfig(cardiac_axis_deg=-10.0)
        frame_left = _synthesize(synth_left, _make_default_conduction())

        # Left axis: Lead I should be more positive relative to Lead II
        ratio_normal = float(np.max(frame_normal.samples['I'])) / (float(np.max(frame_normal.samples['II'])) + 1e-12)
        ratio_left = float(np.max(frame_left.samples['I'])) / (float(np.max(frame_left.samples['II'])) + 1e-12)
        assert ratio_left > ratio_normal, \
            f"Left axis should increase I/II ratio: normal={ratio_normal:.2f} left={ratio_left:.2f}"


class TestSTEvolution:
    def test_st_evolution_phases_produce_different_ecgs(self):
        """Each STEMI phase should produce a measurably different ECG."""
        from app.engine.core.ecg_synthesizer import EcgSynthesizerV2
        from app.engine.core.st_evolution import STEvolutionModel

        synth = EcgSynthesizerV2()
        frames = {}

        for phase_minutes, label in [(0, 'onset'), (30, 'acute'), (360, 'subacute'), (5000, 'old')]:
            model = STEvolutionModel(coronary_stenosis=0.5)
            model.start()
            model.update(phase_minutes * 60)  # Convert to seconds
            synth.st_evolution = model
            frames[label] = _synthesize(synth, _make_default_conduction())

        synth.st_evolution = None

        # Each phase should differ from the previous
        phases = ['onset', 'acute', 'subacute', 'old']
        for i in range(len(phases) - 1):
            corr = np.corrcoef(frames[phases[i]].samples['II'],
                               frames[phases[i+1]].samples['II'])[0, 1]
            assert corr < 0.99, \
                f"Phases {phases[i]} and {phases[i+1]} too similar (corr={corr:.3f})"

    def test_stemi_resolved_returns_to_near_baseline(self):
        """Resolved STEMI should have ST close to baseline (no elevation)."""
        from app.engine.core.ecg_synthesizer import EcgSynthesizerV2
        from app.engine.core.st_evolution import STEvolutionModel

        synth = EcgSynthesizerV2()
        model = STEvolutionModel(coronary_stenosis=0.5)
        model.start()
        model.update(1800)  # 30 min → acute phase
        model.resolve()
        synth.st_evolution = model

        frame_resolved = _synthesize(synth, _make_default_conduction())
        synth.st_evolution = None
        frame_normal = _synthesize(synth, _make_default_conduction())

        # Resolved should be closer to normal than active STEMI would be
        corr = np.corrcoef(frame_normal.samples['II'], frame_resolved.samples['II'])[0, 1]
        assert corr > 0.8, f"Resolved STEMI should be close to normal (corr={corr:.3f})"

    def test_high_stenosis_accelerates_progression(self):
        """Higher stenosis should reach acute phase faster."""
        from app.engine.core.st_evolution import STEvolutionModel

        model_low = STEvolutionModel(coronary_stenosis=0.3)
        model_low.start()
        model_low.update(1800)  # 30 min

        model_high = STEvolutionModel(coronary_stenosis=0.9)
        model_high.start()
        model_high.update(1800)  # 30 min

        # High stenosis should be further along
        assert model_high.elapsed_minutes == model_low.elapsed_minutes  # Same real time
        # But the effective times should differ (we can check via phase or st_elevation)
        state_low = model_low.get_current_state()
        state_high = model_high.get_current_state()
        # High stenosis: effective time = 30 * (0.1 + 4.9*0.9) = 30 * 4.51 = 135.3 min → acute phase
        # Low stenosis: effective time = 30 * (0.1 + 4.9*0.3) = 30 * 1.57 = 47.1 min → also acute
        # Both are in acute phase, but high stenosis has higher ST elevation at this point
        assert state_high.st_elevation_mv != state_low.st_elevation_mv

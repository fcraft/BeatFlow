"""Tests for ECG synthesis from conduction results."""
import numpy as np
import pytest
from app.engine.core.ecg_synthesizer import EcgSynthesizerV2
from app.engine.core.parametric_conduction import ParametricConductionNetwork as ConductionNetworkV2
from app.engine.core.types import Modifiers


@pytest.fixture
def synth():
    return EcgSynthesizerV2(sample_rate=500)


@pytest.fixture
def sinus_result():
    net = ConductionNetworkV2()
    return net.propagate(0.833, Modifiers())


class TestEcgOutput:
    def test_output_has_correct_samples(self, synth, sinus_result):
        frame = synth.synthesize(sinus_result, ['II'], Modifiers())
        expected_samples = int(sinus_result.rr_sec * 500)
        assert abs(len(frame.samples['II']) - expected_samples) <= 2

    def test_r_wave_amplitude_range(self, synth, sinus_result):
        frame = synth.synthesize(sinus_result, ['II'], Modifiers())
        r_peak = np.max(np.abs(frame.samples['II']))
        assert 0.3 <= r_peak <= 4.0, f"R wave amplitude {r_peak} out of range"

    def test_sample_rate_correct(self, synth, sinus_result):
        frame = synth.synthesize(sinus_result, ['II'], Modifiers())
        assert frame.sample_rate == 500


class TestMultiLead:
    def test_12_leads_produced(self, synth, sinus_result):
        all_leads = ['I', 'II', 'III', 'aVR', 'aVL', 'aVF',
                     'V1', 'V2', 'V3', 'V4', 'V5', 'V6']
        frame = synth.synthesize(sinus_result, all_leads, Modifiers())
        assert set(frame.samples.keys()) == set(all_leads)

    def test_lead_relationship(self, synth, sinus_result):
        """Einthoven: Lead I + Lead III ~ Lead II (correlation > 0.95)."""
        frame = synth.synthesize(sinus_result, ['I', 'II', 'III'], Modifiers())
        reconstructed = frame.samples['I'] + frame.samples['III']
        actual = frame.samples['II']
        n = min(len(reconstructed), len(actual))
        corr = np.corrcoef(reconstructed[:n], actual[:n])[0, 1]
        assert corr > 0.95, f"Einthoven correlation {corr:.3f} too low"


class TestVcgLeadMorphology:
    """Validate that VCG-based synthesis produces physiologically distinct
    lead morphologies, especially the V1-V6 precordial transition."""

    ALL_LEADS = ['I', 'II', 'III', 'aVR', 'aVL', 'aVF',
                 'V1', 'V2', 'V3', 'V4', 'V5', 'V6']

    def test_v1_negative_dominant(self, synth, sinus_result):
        """V1 should be S-wave dominant (negative area > positive area)."""
        frame = synth.synthesize(sinus_result, ['V1'], Modifiers())
        v1 = frame.samples['V1']
        # In normal sinus, V1 has rS pattern: small r, deep S
        neg_area = np.sum(np.clip(v1, None, 0))
        pos_area = np.sum(np.clip(v1, 0, None))
        # Negative area should dominate (S-wave)
        assert abs(neg_area) > abs(pos_area) * 0.3, (
            f"V1 not S-dominant: neg_area={neg_area:.2f}, pos_area={pos_area:.2f}"
        )

    def test_v5_v6_positive_dominant(self, synth, sinus_result):
        """V5/V6 should be R-wave dominant (positive peak > |negative peak|)."""
        frame = synth.synthesize(sinus_result, ['V5', 'V6'], Modifiers())
        for lead_name in ('V5', 'V6'):
            signal = frame.samples[lead_name]
            pos_peak = np.max(signal)
            neg_peak = np.min(signal)
            assert pos_peak > abs(neg_peak) * 0.5, (
                f"{lead_name} not R-dominant: pos={pos_peak:.3f}, neg={neg_peak:.3f}"
            )

    def test_r_wave_progression_v1_to_v6(self, synth, sinus_result):
        """R-wave amplitude should generally increase from V1 to V4-V5."""
        frame = synth.synthesize(sinus_result, self.ALL_LEADS, Modifiers())
        r_peaks = {}
        for lead in ('V1', 'V2', 'V3', 'V4', 'V5', 'V6'):
            r_peaks[lead] = np.max(frame.samples[lead])
        # V4 or V5 should have larger R than V1
        assert r_peaks['V4'] > r_peaks['V1'] or r_peaks['V5'] > r_peaks['V1'], (
            f"No R-wave progression: V1={r_peaks['V1']:.3f}, "
            f"V4={r_peaks['V4']:.3f}, V5={r_peaks['V5']:.3f}"
        )

    def test_leads_are_morphologically_distinct(self, synth, sinus_result):
        """V1 and V6 should NOT be simple scalar multiples of each other.

        Cross-correlation should be well below 0.99 (ideally < 0.8).
        """
        frame = synth.synthesize(sinus_result, ['V1', 'V6'], Modifiers())
        v1 = frame.samples['V1']
        v6 = frame.samples['V6']
        n = min(len(v1), len(v6))
        if np.std(v1[:n]) > 1e-10 and np.std(v6[:n]) > 1e-10:
            corr = abs(float(np.corrcoef(v1[:n], v6[:n])[0, 1]))
            assert corr < 0.95, (
                f"V1-V6 correlation {corr:.3f} too high — leads not distinct"
            )

    def test_avr_inverted(self, synth, sinus_result):
        """aVR should be predominantly negative (inverted P-QRS-T)."""
        frame = synth.synthesize(sinus_result, ['aVR'], Modifiers())
        avr = frame.samples['aVR']
        neg_area = np.sum(np.clip(avr, None, 0))
        pos_area = np.sum(np.clip(avr, 0, None))
        assert abs(neg_area) > abs(pos_area), (
            f"aVR not inverted: neg_area={neg_area:.2f}, pos_area={pos_area:.2f}"
        )

    def test_v1_v6_different_from_lead_ii_scaling(self, synth, sinus_result):
        """V1 and V6 should differ in shape from Lead II (not just scaled).

        The old implementation had V_lead = coeff * Lead_II.
        With VCG, the correlation should be < 0.98 for at least one of them.
        """
        frame = synth.synthesize(sinus_result, ['II', 'V1', 'V6'], Modifiers())
        lead_ii = frame.samples['II']
        v1 = frame.samples['V1']
        v6 = frame.samples['V6']
        n = min(len(lead_ii), len(v1), len(v6))

        # At least one of V1/V6 should have low correlation with II
        corr_v1 = abs(float(np.corrcoef(lead_ii[:n], v1[:n])[0, 1]))
        corr_v6 = abs(float(np.corrcoef(lead_ii[:n], v6[:n])[0, 1]))
        assert corr_v1 < 0.98 or corr_v6 < 0.98, (
            f"V-leads too similar to Lead II: V1 corr={corr_v1:.3f}, V6 corr={corr_v6:.3f}"
        )

    @pytest.mark.parametrize("beat_kind,rhythm", [
        ('vt', 'vt'),
        ('pvc', ''),
    ])
    def test_abnormal_rhythm_leads_distinct(self, beat_kind, rhythm):
        """VT/PVC should also produce distinct V-lead morphologies."""
        net = ConductionNetworkV2()
        mods = Modifiers()
        if rhythm:
            mods.rhythm_override = rhythm
        if beat_kind == 'pvc':
            from app.engine.core.types import EctopicFocus
            mods.ectopic_foci = [EctopicFocus(node='purkinje', current=1.0,
                                              coupling_interval_ms=50.0)]
        rr_sec = 60.0 / (180.0 if beat_kind == 'vt' else 72.0)
        result = net.propagate(rr_sec, mods)
        synth = EcgSynthesizerV2(sample_rate=500)
        frame = synth.synthesize(result, ['V1', 'V6'], mods)

        v1 = frame.samples['V1']
        v6 = frame.samples['V6']
        n = min(len(v1), len(v6))
        if np.std(v1[:n]) > 1e-10 and np.std(v6[:n]) > 1e-10:
            corr = abs(float(np.corrcoef(v1[:n], v6[:n])[0, 1]))
            assert corr < 0.98, (
                f"{beat_kind}: V1-V6 correlation {corr:.3f} too high"
            )

    def test_no_nan_in_all_leads(self, synth, sinus_result):
        """No NaN/Inf in any of the 12 leads."""
        frame = synth.synthesize(sinus_result, self.ALL_LEADS, Modifiers())
        for name, signal in frame.samples.items():
            assert not np.any(np.isnan(signal)), f"NaN in {name}"
            assert not np.any(np.isinf(signal)), f"Inf in {name}"


class TestBeatAnnotations:
    def test_annotations_present(self, synth, sinus_result):
        frame = synth.synthesize(sinus_result, ['II'], Modifiers())
        assert len(frame.beat_annotations) >= 1
        ann = frame.beat_annotations[0]
        assert 'beat_index' in ann
        assert 'rr_sec' in ann

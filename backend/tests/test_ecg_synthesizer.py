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


class TestBeatAnnotations:
    def test_annotations_present(self, synth, sinus_result):
        frame = synth.synthesize(sinus_result, ['II'], Modifiers())
        assert len(frame.beat_annotations) >= 1
        ann = frame.beat_annotations[0]
        assert 'beat_index' in ann
        assert 'rr_sec' in ann

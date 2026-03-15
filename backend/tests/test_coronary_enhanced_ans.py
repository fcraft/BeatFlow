"""Tests for coronary model and enhanced autonomic reflex controller.

Covers:
- CoronaryModel: CPP calculation, ischemia cascade, supply/demand, stenosis, lag
- AutonomicReflexController: baroreceptor, chemoreceptor (PaCO₂/PaO₂/pH),
  thermoregulation, RAAS, backward compatibility, state save/restore
- InteractionState: new fields (magnesium, fio2, coronary_stenosis, etc.)
- TransitionEngine: new field smoothing configs
"""
import math

import pytest

from app.engine.modulation.coronary_model import CoronaryModel
from app.engine.modulation.autonomic_reflex import AutonomicReflexController
from app.engine.modulation.interaction_state import InteractionState
from app.engine.modulation.transition_engine import TransitionSmoother, TRANSITION_CONFIGS
from app.engine.core.types import Modifiers


# ============================================================
# CoronaryModel tests
# ============================================================

class TestCoronaryModel:
    """Tests for the coronary circulation model."""

    def test_default_construction(self):
        cm = CoronaryModel()
        assert cm.cpp == 70.0
        assert cm.ischemia_level == 0.0

    def test_normal_cpp(self):
        """Normal DBP/LVEDP should give CPP ~60-80."""
        cm = CoronaryModel()
        cpp, ischemia = cm.update(dbp=80.0, lv_edp=10.0, hr=75.0, sbp=120.0)
        assert 60.0 <= cpp <= 80.0
        assert ischemia < 0.1

    def test_low_dbp_reduces_cpp(self):
        """Low DBP should reduce CPP."""
        cm = CoronaryModel()
        cpp, _ = cm.update(dbp=40.0, lv_edp=10.0, hr=75.0, sbp=90.0)
        assert cpp < 40.0

    def test_high_lvedp_reduces_cpp(self):
        """High LVEDP (heart failure) should reduce CPP."""
        cm = CoronaryModel()
        cpp, _ = cm.update(dbp=80.0, lv_edp=30.0, hr=75.0, sbp=120.0)
        assert cpp == pytest.approx(50.0)

    def test_ischemia_onset(self):
        """Low CPP should trigger ischemia over time."""
        cm = CoronaryModel()
        # Multiple beats with low DBP
        for _ in range(30):
            _, ischemia = cm.update(dbp=35.0, lv_edp=15.0, hr=100.0, sbp=90.0, dt=0.6)
        assert ischemia > 0.2

    def test_ischemia_recovery(self):
        """Restoring normal CPP should reduce ischemia (slowly)."""
        cm = CoronaryModel()
        # Induce ischemia
        for _ in range(50):
            cm.update(dbp=30.0, lv_edp=15.0, hr=100.0, sbp=80.0, dt=0.6)
        ischemia_peak = cm.ischemia_level
        assert ischemia_peak > 0.3

        # Recovery
        for _ in range(80):
            cm.update(dbp=80.0, lv_edp=10.0, hr=75.0, sbp=120.0, dt=0.8)
        assert cm.ischemia_level < ischemia_peak

    def test_stenosis_worsens_ischemia(self):
        """Coronary stenosis should worsen supply/demand mismatch."""
        cm_normal = CoronaryModel()
        cm_stenosis = CoronaryModel()
        for _ in range(30):
            _, isch_normal = cm_normal.update(
                dbp=70.0, lv_edp=10.0, hr=100.0, sbp=140.0, dt=0.6)
            _, isch_stenosis = cm_stenosis.update(
                dbp=70.0, lv_edp=10.0, hr=100.0, sbp=140.0, dt=0.6,
                coronary_stenosis=0.7)
        assert isch_stenosis > isch_normal

    def test_high_demand_causes_ischemia(self):
        """High HR + high BP (high RPP) with limited supply → ischemia."""
        cm = CoronaryModel()
        for _ in range(30):
            _, ischemia = cm.update(
                dbp=60.0, lv_edp=12.0, hr=160.0, sbp=180.0, dt=0.4,
                coronary_stenosis=0.5)
        assert ischemia > 0.1

    def test_ischemia_clamped(self):
        """Ischemia should be clamped to [0, 1]."""
        cm = CoronaryModel()
        for _ in range(100):
            _, ischemia = cm.update(dbp=20.0, lv_edp=20.0, hr=180.0, sbp=80.0, dt=0.3)
        assert 0.0 <= ischemia <= 1.0

    def test_state_save_restore(self):
        cm = CoronaryModel()
        for _ in range(10):
            cm.update(dbp=40.0, lv_edp=12.0, hr=90.0, sbp=100.0, dt=0.7)
        state = cm.get_state()
        cm2 = CoronaryModel()
        cm2.set_state(state)
        assert abs(cm2.ischemia_level - cm.ischemia_level) < 1e-10
        assert abs(cm2.cpp - cm.cpp) < 1e-10


# ============================================================
# Enhanced AutonomicReflexController tests
# ============================================================

class TestEnhancedAutonomicReflex:
    """Tests for the enhanced ANS controller."""

    def test_default_tones(self):
        """Default tones should be 0.5/0.5."""
        arc = AutonomicReflexController()
        assert arc.sympathetic_tone == 0.5
        assert arc.parasympathetic_tone == 0.5

    def test_baroreceptor_high_map(self):
        """High MAP → ↑ parasympathetic, ↓ sympathetic."""
        arc = AutonomicReflexController()
        for _ in range(20):
            symp, para = arc.update(map_mmhg=130.0, dt=0.8)
        assert para > 0.5
        assert symp < 0.5

    def test_baroreceptor_low_map(self):
        """Low MAP → ↑ sympathetic, ↓ parasympathetic."""
        arc = AutonomicReflexController()
        for _ in range(20):
            symp, para = arc.update(map_mmhg=60.0, dt=0.8)
        assert symp > 0.5

    # ---- Chemoreceptor PaCO₂ ----

    def test_hypercapnia_increases_sympathetic(self):
        """High PaCO₂ → ↑ sympathetic."""
        arc_normal = AutonomicReflexController()
        arc_hyper = AutonomicReflexController()
        for _ in range(20):
            s_normal, _ = arc_normal.update(93.0, 0.8, paco2=40.0)
            s_hyper, _ = arc_hyper.update(93.0, 0.8, paco2=60.0)
        assert s_hyper > s_normal

    # ---- Chemoreceptor PaO₂ ----

    def test_hypoxia_increases_sympathetic(self):
        """Low PaO₂ → ↑ sympathetic."""
        arc_normal = AutonomicReflexController()
        arc_hypox = AutonomicReflexController()
        for _ in range(20):
            s_normal, _ = arc_normal.update(93.0, 0.8, pao2=95.0)
            s_hypox, _ = arc_hypox.update(93.0, 0.8, pao2=50.0)
        assert s_hypox > s_normal

    def test_severe_hypoxia_bradycardia(self):
        """Severe hypoxia (PaO₂ < 60) → parasympathetic activation."""
        arc = AutonomicReflexController()
        for _ in range(20):
            _, para = arc.update(93.0, 0.8, pao2=40.0)
        assert para > 0.5

    # ---- Chemoreceptor pH ----

    def test_acidosis_increases_sympathetic(self):
        """Low pH → ↑ sympathetic."""
        arc_normal = AutonomicReflexController()
        arc_acid = AutonomicReflexController()
        for _ in range(20):
            s_normal, _ = arc_normal.update(93.0, 0.8, ph=7.40)
            s_acid, _ = arc_acid.update(93.0, 0.8, ph=7.10)
        assert s_acid > s_normal

    # ---- Thermoregulation ----

    def test_hyperthermia_increases_sympathetic(self):
        """High temperature → ↑ sympathetic."""
        arc_normal = AutonomicReflexController()
        arc_hot = AutonomicReflexController()
        for _ in range(20):
            s_normal, _ = arc_normal.update(93.0, 0.8, temperature=36.6)
            s_hot, _ = arc_hot.update(93.0, 0.8, temperature=40.0)
        assert s_hot > s_normal

    def test_hypothermia_bradycardia(self):
        """Severe hypothermia → parasympathetic activation."""
        arc = AutonomicReflexController()
        for _ in range(30):
            _, para = arc.update(93.0, 0.8, temperature=30.0)
        assert para > 0.5

    # ---- RAAS ----

    def test_raas_activates_on_low_map(self):
        """Low MAP should activate RAAS."""
        arc = AutonomicReflexController()
        for _ in range(50):
            arc.update(60.0, 0.8, cardiac_output=3.0)
        assert arc.raas_activation > 0.1

    def test_raas_inactive_at_normal(self):
        """Normal MAP/CO should not activate RAAS."""
        arc = AutonomicReflexController()
        for _ in range(10):
            arc.update(93.0, 0.8, cardiac_output=5.0)
        assert arc.raas_activation < 0.05

    def test_raas_slow_decay(self):
        """RAAS should decay slowly when conditions normalize."""
        arc = AutonomicReflexController()
        # Activate
        for _ in range(60):
            arc.update(55.0, 0.8, cardiac_output=2.5)
        raas_peak = arc.raas_activation

        # Normalize
        for _ in range(20):
            arc.update(93.0, 0.8, cardiac_output=5.0)
        assert arc.raas_activation < raas_peak
        assert arc.raas_activation > 0.0  # Slow decay

    # ---- Backward compatibility ----

    def test_spo2_backward_compat(self):
        """Legacy spo2 parameter should still work."""
        arc = AutonomicReflexController()
        for _ in range(10):
            symp, _ = arc.update(93.0, 0.8, spo2=80.0)
        assert symp > 0.5

    # ---- Circuit breaker ----

    def test_circuit_breaker_limits_rapid_change(self):
        """Rapid MAP changes should be limited by circuit breaker."""
        arc = AutonomicReflexController()
        # Sudden extreme change
        arc.update(93.0, 0.8)  # Baseline
        s1, p1 = arc.sympathetic_tone, arc.parasympathetic_tone
        arc.update(40.0, 0.8)  # Extreme drop
        s2, p2 = arc.sympathetic_tone, arc.parasympathetic_tone
        # Change should be limited
        assert abs(s2 - s1) <= 0.15
        assert abs(p2 - p1) <= 0.15

    # ---- State save/restore ----

    def test_state_save_restore(self):
        arc = AutonomicReflexController()
        for _ in range(10):
            arc.update(60.0, 0.8, paco2=55.0, cardiac_output=3.0)
        state = arc.get_state()

        arc2 = AutonomicReflexController()
        arc2.set_state(state)
        assert abs(arc2.sympathetic_tone - arc.sympathetic_tone) < 1e-10
        assert abs(arc2.raas_activation - arc.raas_activation) < 1e-10

    def test_state_backward_compat(self):
        """Old state format (without RAAS) should load."""
        arc = AutonomicReflexController()
        old_state = {"sympathetic": 0.6, "parasympathetic": 0.4, "recent_changes": [], "ans_fatigue": 0.1}
        arc.set_state(old_state)
        assert arc.sympathetic_tone == 0.6
        assert arc.raas_activation == 0.0  # Default


# ============================================================
# InteractionState new fields tests
# ============================================================

class TestInteractionStateNewFields:
    """Tests for new fields in InteractionState."""

    def test_magnesium_default(self):
        s = InteractionState()
        assert s.magnesium_level == 2.0

    def test_fio2_default(self):
        s = InteractionState()
        assert s.fio2 == 0.21

    def test_coronary_stenosis_default(self):
        s = InteractionState()
        assert s.coronary_stenosis == 0.0

    def test_rv_contractility_default(self):
        s = InteractionState()
        assert s.rv_contractility == 1.0

    def test_pulm_vascular_resistance_default(self):
        s = InteractionState()
        assert s.pulm_vascular_resistance == 0.15

    def test_serialization_round_trip(self):
        s = InteractionState(magnesium_level=1.5, fio2=0.4, coronary_stenosis=0.5)
        d = s.to_dict()
        s2 = InteractionState.from_dict(d)
        assert s2.magnesium_level == 1.5
        assert s2.fio2 == 0.4
        assert s2.coronary_stenosis == 0.5

    def test_active_interactions_new_fields(self):
        s = InteractionState(
            magnesium_level=1.2,
            fio2=0.6,
            coronary_stenosis=0.7,
            rv_contractility=0.5,
        )
        active = s.get_active_interactions()
        assert 'magnesium' in active
        assert 'fio2' in active
        assert 'coronary_stenosis' in active
        assert 'rv_contractility' in active

    def test_active_interactions_defaults_empty(self):
        s = InteractionState()
        active = s.get_active_interactions()
        assert 'magnesium' not in active
        assert 'fio2' not in active
        assert 'coronary_stenosis' not in active


# ============================================================
# TransitionEngine new fields tests
# ============================================================

class TestTransitionEngineNewFields:
    """Tests for new fields in transition configs."""

    def test_new_configs_exist(self):
        assert 'magnesium_level' in TRANSITION_CONFIGS
        assert 'fio2' in TRANSITION_CONFIGS
        assert 'coronary_stenosis' in TRANSITION_CONFIGS
        assert 'rv_contractility' in TRANSITION_CONFIGS
        assert 'pulm_vascular_resistance' in TRANSITION_CONFIGS

    def test_coronary_stenosis_slow(self):
        """Coronary stenosis should have slow transition."""
        assert TRANSITION_CONFIGS['coronary_stenosis'].tau_seconds >= 8.0

    def test_fio2_medium(self):
        """FiO2 should have medium transition (ventilator change)."""
        assert 1.0 <= TRANSITION_CONFIGS['fio2'].tau_seconds <= 5.0

    def test_smoother_handles_new_fields(self):
        """TransitionSmoother should smooth new fields."""
        smoother = TransitionSmoother()
        intent = InteractionState(coronary_stenosis=0.8, fio2=0.6, magnesium_level=1.0)
        smoothed = smoother.update(intent, dt=0.8)
        # After one beat, should be moving toward target
        assert smoothed.coronary_stenosis > 0.0
        assert smoothed.fio2 > 0.21
        assert smoothed.magnesium_level < 2.0

    def test_smoother_convergence(self):
        """After many beats, smoothed values should converge to target."""
        smoother = TransitionSmoother()
        intent = InteractionState(coronary_stenosis=0.5)
        for _ in range(100):
            smoothed = smoother.update(intent, dt=0.8)
        assert abs(smoothed.coronary_stenosis - 0.5) < 0.05


# ============================================================
# Integration: coronary + ANS pipeline
# ============================================================

class TestCoronaryANSIntegration:
    """Integration tests for coronary model feeding into ANS."""

    def test_ischemia_increases_sympathetic(self):
        """Ischemia should increase sympathetic via low CO / low MAP."""
        cm = CoronaryModel()
        arc = AutonomicReflexController()

        # Normal baseline
        for _ in range(10):
            arc.update(93.0, 0.8)
        symp_baseline = arc.sympathetic_tone

        # Simulate ischemia conditions (low DBP, high demand)
        for _ in range(30):
            cpp, ischemia = cm.update(dbp=35.0, lv_edp=15.0, hr=120.0, sbp=90.0, dt=0.5)
            # Low MAP, low CO during ischemia
            arc.update(60.0, 0.5, cardiac_output=3.0)

        assert arc.sympathetic_tone > symp_baseline

    def test_full_cascade(self):
        """Full cascade: stenosis → ischemia → ANS response."""
        cm = CoronaryModel()
        arc = AutonomicReflexController()

        for _ in range(50):
            cpp, ischemia = cm.update(
                dbp=65.0, lv_edp=12.0, hr=100.0, sbp=130.0, dt=0.6,
                coronary_stenosis=0.8,
            )
            symp, para = arc.update(
                85.0, 0.6,
                cardiac_output=4.0,
                pao2=85.0,
                paco2=42.0,
            )

        # Some ischemia should have developed
        assert ischemia > 0.05
        # Sympathetic should be elevated from low CO
        assert symp >= 0.45

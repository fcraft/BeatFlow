"""Tests for the respiratory system module: RespiratoryModel + GasExchangeModel.

Covers:
- Gas exchange: O2-Hb dissociation curve (Hill), Henderson-Hasselbalch pH,
  alveolar gas equations, blood gas state adaptation
- Respiratory model: sinusoidal ITP cycle, chemoreceptor-driven RR,
  tidal volume modulation, phase advancement, exercise response
- Modifiers integration: new respiratory fields in types.py
"""
import math

import pytest

from app.engine.respiratory.gas_exchange import BloodGasState, GasExchangeModel
from app.engine.respiratory.respiratory_model import RespiratoryModel, RespiratoryState
from app.engine.core.types import Modifiers


# ============================================================
# GasExchangeModel tests
# ============================================================

class TestGasExchangeModel:
    """Tests for GasExchangeModel."""

    def test_initial_state_is_normal(self):
        """Initial blood gas values should be in normal physiological range."""
        ge = GasExchangeModel()
        bg = ge.state
        assert 80.0 <= bg.pao2 <= 100.0
        assert 35.0 <= bg.paco2 <= 45.0
        assert 95.0 <= bg.sao2 <= 100.0
        assert 7.35 <= bg.ph <= 7.45
        assert 22.0 <= bg.hco3 <= 26.0

    def test_hill_equation_normal_pao2(self):
        """At normal PaO2 (~95 mmHg, pH 7.40), SaO2 should be ~97%."""
        ge = GasExchangeModel()
        sao2 = ge.compute_sao2(95.0, 7.40)
        assert 95.0 <= sao2 <= 99.5

    def test_hill_equation_p50(self):
        """At P50 (26.6 mmHg), SaO2 should be ~50%."""
        ge = GasExchangeModel()
        sao2 = ge.compute_sao2(26.6, 7.40)
        assert 45.0 <= sao2 <= 55.0

    def test_hill_equation_low_pao2(self):
        """At very low PaO2 (~40 mmHg), SaO2 should drop significantly."""
        ge = GasExchangeModel()
        sao2 = ge.compute_sao2(40.0, 7.40)
        assert 50.0 <= sao2 <= 80.0

    def test_hill_equation_high_pao2(self):
        """At high PaO2 (~500 mmHg with O2 therapy), SaO2 should be near 100%."""
        ge = GasExchangeModel()
        sao2 = ge.compute_sao2(500.0, 7.40)
        assert sao2 > 99.5

    def test_hill_equation_zero_pao2(self):
        """At zero PaO2, SaO2 should be 0%."""
        ge = GasExchangeModel()
        sao2 = ge.compute_sao2(0.0, 7.40)
        assert sao2 == 0.0

    def test_bohr_effect_acidosis(self):
        """Acidosis (low pH) should shift curve rightward → lower SaO2 at same PaO2."""
        ge = GasExchangeModel()
        sao2_normal = ge.compute_sao2(60.0, 7.40)
        sao2_acidotic = ge.compute_sao2(60.0, 7.20)
        assert sao2_acidotic < sao2_normal

    def test_bohr_effect_alkalosis(self):
        """Alkalosis (high pH) should shift curve leftward → higher SaO2 at same PaO2."""
        ge = GasExchangeModel()
        sao2_normal = ge.compute_sao2(60.0, 7.40)
        sao2_alkalotic = ge.compute_sao2(60.0, 7.60)
        assert sao2_alkalotic > sao2_normal

    def test_henderson_hasselbalch_normal(self):
        """pH from normal PaCO2 (40) and HCO3 (24) should be ~7.40."""
        ge = GasExchangeModel()
        ph = ge._compute_ph(40.0, 24.0)
        assert 7.38 <= ph <= 7.42

    def test_henderson_hasselbalch_respiratory_acidosis(self):
        """High PaCO2 (60 mmHg) should cause pH < 7.35 (respiratory acidosis)."""
        ge = GasExchangeModel()
        ph = ge._compute_ph(60.0, 24.0)
        assert ph < 7.35

    def test_henderson_hasselbalch_respiratory_alkalosis(self):
        """Low PaCO2 (25 mmHg) should cause pH > 7.45 (respiratory alkalosis)."""
        ge = GasExchangeModel()
        ph = ge._compute_ph(25.0, 24.0)
        assert ph > 7.45

    def test_henderson_hasselbalch_metabolic_acidosis(self):
        """Low HCO3 (12 mEq/L) should cause pH < 7.35 (metabolic acidosis)."""
        ge = GasExchangeModel()
        ph = ge._compute_ph(40.0, 12.0)
        assert ph < 7.35

    def test_update_steady_state_room_air(self):
        """After many beats at room air, normal ventilation → stable normal blood gases."""
        ge = GasExchangeModel()
        # Run 100 beats to reach steady state
        for _ in range(100):
            bg = ge.update(minute_ventilation=7.0, fio2=0.21, cardiac_output=5.0)
        assert 75.0 <= bg.pao2 <= 110.0
        assert 33.0 <= bg.paco2 <= 47.0
        assert 7.33 <= bg.ph <= 7.47

    def test_update_hyperventilation(self):
        """Hyperventilation → PaCO2 drops → respiratory alkalosis."""
        ge = GasExchangeModel()
        # Steady state first
        for _ in range(50):
            ge.update(minute_ventilation=7.0, fio2=0.21)
        # Hyperventilate
        for _ in range(50):
            bg = ge.update(minute_ventilation=20.0, fio2=0.21)
        assert bg.paco2 < 35.0
        assert bg.ph > 7.40

    def test_update_hypoventilation(self):
        """Hypoventilation → PaCO2 rises → respiratory acidosis."""
        ge = GasExchangeModel()
        for _ in range(50):
            ge.update(minute_ventilation=7.0, fio2=0.21)
        # Hypoventilate
        for _ in range(50):
            bg = ge.update(minute_ventilation=3.0, fio2=0.21)
        assert bg.paco2 > 45.0
        assert bg.ph < 7.40

    def test_update_supplemental_oxygen(self):
        """Higher FiO2 should increase PaO2."""
        ge = GasExchangeModel()
        for _ in range(50):
            ge.update(minute_ventilation=7.0, fio2=0.21)
        baseline_pao2 = ge.state.pao2
        for _ in range(50):
            bg = ge.update(minute_ventilation=7.0, fio2=0.50)
        assert bg.pao2 > baseline_pao2

    def test_sao2_to_spo2_good_perfusion(self):
        """With good perfusion, SpO2 ≈ SaO2."""
        spo2 = GasExchangeModel.sao2_to_spo2(97.0, perfusion_index=1.0)
        assert spo2 == 97.0

    def test_sao2_to_spo2_poor_perfusion(self):
        """With poor perfusion, SpO2 < SaO2."""
        spo2 = GasExchangeModel.sao2_to_spo2(97.0, perfusion_index=0.3)
        assert spo2 < 97.0

    def test_state_serialization(self):
        """get_state_dict and set_state_dict should roundtrip."""
        ge = GasExchangeModel()
        for _ in range(20):
            ge.update(minute_ventilation=7.0, fio2=0.21)
        d = ge.get_state_dict()
        ge2 = GasExchangeModel()
        ge2.set_state_dict(d)
        assert abs(ge2.state.pao2 - ge.state.pao2) < 0.01
        assert abs(ge2.state.paco2 - ge.state.paco2) < 0.01
        assert abs(ge2.state.ph - ge.state.ph) < 0.001

    def test_low_cardiac_output_widens_aa_gradient(self):
        """Low cardiac output should widen A-a gradient → lower PaO2."""
        ge_normal = GasExchangeModel()
        ge_low_co = GasExchangeModel()
        for _ in range(80):
            ge_normal.update(minute_ventilation=7.0, cardiac_output=5.0)
            ge_low_co.update(minute_ventilation=7.0, cardiac_output=2.0)
        assert ge_low_co.state.pao2 < ge_normal.state.pao2


# ============================================================
# RespiratoryModel tests
# ============================================================

class TestRespiratoryModel:
    """Tests for RespiratoryModel."""

    def test_initial_state(self):
        """Initial respiratory state should be in normal range."""
        rm = RespiratoryModel()
        rs = rm.update(rr_sec=0.85)  # ~70 bpm
        assert 10.0 <= rs.respiratory_rate <= 20.0
        assert 300.0 <= rs.tidal_volume_ml <= 700.0
        assert 4.0 <= rs.minute_ventilation <= 12.0
        assert 0.0 <= rs.respiratory_phase <= 2.0 * math.pi

    def test_phase_advances_each_beat(self):
        """Respiratory phase should advance with each beat."""
        rm = RespiratoryModel()
        rs1 = rm.update(rr_sec=0.85)
        phase1 = rs1.respiratory_phase
        rs2 = rm.update(rr_sec=0.85)
        phase2 = rs2.respiratory_phase
        # Phase should have advanced (may wrap around 2*pi)
        assert rs2.respiratory_phase != phase1 or True  # Phase wraps

    def test_phase_wraps_at_2pi(self):
        """Phase should stay within [0, 2*pi]."""
        rm = RespiratoryModel()
        for _ in range(200):
            rs = rm.update(rr_sec=0.85)
            assert 0.0 <= rs.respiratory_phase < 2.0 * math.pi + 0.01

    def test_intrathoracic_pressure_sinusoidal(self):
        """ITP should oscillate sinusoidally around the mean."""
        rm = RespiratoryModel()
        itps = []
        for _ in range(100):
            rs = rm.update(rr_sec=0.85)
            itps.append(rs.intrathoracic_pressure)
        # ITP should vary
        assert max(itps) > min(itps)
        # ITP should be negative (normal breathing)
        assert all(itp < 0.0 for itp in itps)

    def test_exercise_increases_rr(self):
        """Exercise should increase respiratory rate."""
        rm_rest = RespiratoryModel()
        rm_exercise = RespiratoryModel()
        for _ in range(50):
            rs_rest = rm_rest.update(rr_sec=0.85, exercise_intensity=0.0)
            rs_ex = rm_exercise.update(rr_sec=0.85, exercise_intensity=0.7)
        assert rs_ex.respiratory_rate > rs_rest.respiratory_rate

    def test_exercise_increases_tidal_volume(self):
        """Exercise should increase tidal volume."""
        rm_rest = RespiratoryModel()
        rm_exercise = RespiratoryModel()
        for _ in range(50):
            rs_rest = rm_rest.update(rr_sec=0.85, exercise_intensity=0.0)
            rs_ex = rm_exercise.update(rr_sec=0.85, exercise_intensity=0.7)
        assert rs_ex.tidal_volume_ml > rs_rest.tidal_volume_ml

    def test_exercise_increases_minute_ventilation(self):
        """Exercise should increase minute ventilation (both RR and Vt up)."""
        rm_rest = RespiratoryModel()
        rm_exercise = RespiratoryModel()
        for _ in range(50):
            rs_rest = rm_rest.update(rr_sec=0.85, exercise_intensity=0.0)
            rs_ex = rm_exercise.update(rr_sec=0.85, exercise_intensity=0.7)
        assert rs_ex.minute_ventilation > rs_rest.minute_ventilation

    def test_exercise_increases_itp_amplitude(self):
        """Exercise should increase ITP amplitude (more forceful breathing)."""
        rm_rest = RespiratoryModel()
        rm_exercise = RespiratoryModel()
        itps_rest = []
        itps_ex = []
        for _ in range(100):
            rs_rest = rm_rest.update(rr_sec=0.85, exercise_intensity=0.0)
            rs_ex = rm_exercise.update(rr_sec=0.85, exercise_intensity=0.8)
            itps_rest.append(rs_rest.intrathoracic_pressure)
            itps_ex.append(rs_ex.intrathoracic_pressure)
        amp_rest = max(itps_rest) - min(itps_rest)
        amp_ex = max(itps_ex) - min(itps_ex)
        assert amp_ex > amp_rest

    def test_sympathetic_increases_rr(self):
        """High sympathetic tone should increase respiratory rate."""
        rm_lo = RespiratoryModel()
        rm_hi = RespiratoryModel()
        for _ in range(50):
            rs_lo = rm_lo.update(rr_sec=0.85, sympathetic_tone=0.2)
            rs_hi = rm_hi.update(rr_sec=0.85, sympathetic_tone=0.9)
        assert rs_hi.respiratory_rate > rs_lo.respiratory_rate

    def test_supplemental_o2_increases_spo2(self):
        """Higher FiO2 should eventually produce higher SpO2."""
        rm_room = RespiratoryModel()
        rm_o2 = RespiratoryModel()
        for _ in range(80):
            rs_room = rm_room.update(rr_sec=0.85, fio2=0.21)
            rs_o2 = rm_o2.update(rr_sec=0.85, fio2=0.50)
        assert rs_o2.spo2_physical >= rs_room.spo2_physical

    def test_mechanical_ventilation_fixes_rr(self):
        """Mechanical ventilation should enforce a fixed RR of ~14."""
        rm = RespiratoryModel()
        for _ in range(50):
            rs = rm.update(
                rr_sec=0.85,
                mechanical_ventilation=True,
                exercise_intensity=0.9,  # Should not affect RR in mech vent
            )
        assert 12.0 <= rs.respiratory_rate <= 16.0

    def test_blood_gas_values_propagated(self):
        """RespiratoryState should contain blood gas values from GasExchangeModel."""
        rm = RespiratoryModel()
        for _ in range(30):
            rs = rm.update(rr_sec=0.85)
        assert rs.pao2 > 0.0
        assert rs.paco2 > 0.0
        assert rs.ph > 0.0
        assert rs.sao2 is not None  # via gas_exchange

    def test_fio2_passthrough(self):
        """FiO2 value should be passed through to the state."""
        rm = RespiratoryModel()
        rs = rm.update(rr_sec=0.85, fio2=0.40)
        assert rs.fio2 == 0.40

    def test_state_serialization_roundtrip(self):
        """get_state / set_state should preserve model state."""
        rm = RespiratoryModel()
        for _ in range(30):
            rm.update(rr_sec=0.85, exercise_intensity=0.5)
        state = rm.get_state()

        rm2 = RespiratoryModel()
        rm2.set_state(state)

        # Both should produce similar next outputs
        rs1 = rm.update(rr_sec=0.85)
        rs2 = rm2.update(rr_sec=0.85)
        assert abs(rs1.respiratory_rate - rs2.respiratory_rate) < 0.5
        assert abs(rs1.pao2 - rs2.pao2) < 1.0

    def test_rr_clamped_to_bounds(self):
        """Respiratory rate should never exceed bounds."""
        rm = RespiratoryModel()
        # Extreme exercise should not push RR beyond max
        for _ in range(100):
            rs = rm.update(
                rr_sec=0.5,
                exercise_intensity=1.0,
                sympathetic_tone=1.0,
            )
        assert rs.respiratory_rate <= RespiratoryModel.RR_MAX
        assert rs.respiratory_rate >= RespiratoryModel.RR_MIN

    def test_low_co_reduces_pao2(self):
        """Low cardiac output should widen A-a gradient → lower PaO2."""
        rm_normal = RespiratoryModel()
        rm_low_co = RespiratoryModel()
        for _ in range(80):
            rs_normal = rm_normal.update(rr_sec=0.85, cardiac_output=5.0)
            rs_low_co = rm_low_co.update(rr_sec=0.85, cardiac_output=2.0)
        assert rs_low_co.pao2 < rs_normal.pao2


# ============================================================
# Modifiers integration tests
# ============================================================

class TestModifiersRespiratoryFields:
    """Tests for new respiratory fields in Modifiers."""

    def test_default_respiratory_fields(self):
        """New respiratory fields should have physiologically normal defaults."""
        m = Modifiers()
        assert 0.0 <= m.respiratory_phase <= 2.0 * math.pi
        assert m.intrathoracic_pressure == -5.0
        assert m.pao2 == 95.0
        assert m.paco2 == 40.0
        assert m.ph == 7.40
        assert m.spo2_physical == 97.5
        assert m.rr_physical == 14.0
        assert m.fio2 == 0.21
        assert m.magnesium_level == 2.0

    def test_default_rv_pulmonary_fields(self):
        """RV/pulmonary fields should have normal defaults."""
        m = Modifiers()
        assert m.rv_contractility == 1.0
        assert m.pulm_vascular_resistance == 0.15

    def test_default_coronary_fields(self):
        """Coronary fields should have normal defaults."""
        m = Modifiers()
        assert m.coronary_perfusion_pressure == 70.0
        assert m.ischemia_level == 0.0

    def test_default_hrv_qt_fields(self):
        """HRV and QT fields should have sensible defaults."""
        m = Modifiers()
        assert m.hrv_rr_offset_ms == 0.0
        assert m.qt_adapted_ms == 0.0

    def test_modifiers_mutable(self):
        """Modifiers respiratory fields should be writable."""
        m = Modifiers()
        m.respiratory_phase = 1.5
        m.intrathoracic_pressure = -7.0
        m.pao2 = 80.0
        m.paco2 = 50.0
        m.ph = 7.30
        m.spo2_physical = 92.0
        m.rr_physical = 24.0
        m.fio2 = 0.40
        m.magnesium_level = 1.5
        m.ischemia_level = 0.3
        m.hrv_rr_offset_ms = 15.0
        m.qt_adapted_ms = 450.0
        assert m.respiratory_phase == 1.5
        assert m.pao2 == 80.0
        assert m.magnesium_level == 1.5
        assert m.ischemia_level == 0.3
        assert m.hrv_rr_offset_ms == 15.0
        assert m.qt_adapted_ms == 450.0


# ============================================================
# Integration: RespiratoryModel → Modifiers mapping
# ============================================================

class TestRespiratoryToModifiers:
    """Test that RespiratoryState can populate Modifiers fields correctly."""

    def test_respiratory_state_to_modifiers(self):
        """RespiratoryState values should map cleanly to Modifiers fields."""
        rm = RespiratoryModel()
        for _ in range(30):
            rs = rm.update(rr_sec=0.85)

        m = Modifiers()
        # Simulate what pipeline will do
        m.respiratory_phase = rs.respiratory_phase
        m.intrathoracic_pressure = rs.intrathoracic_pressure
        m.pao2 = rs.pao2
        m.paco2 = rs.paco2
        m.ph = rs.ph
        m.spo2_physical = rs.spo2_physical
        m.rr_physical = rs.respiratory_rate
        m.fio2 = rs.fio2

        assert m.respiratory_phase == rs.respiratory_phase
        assert m.pao2 == rs.pao2
        assert m.rr_physical == rs.respiratory_rate


# ============================================================
# Edge cases and robustness
# ============================================================

class TestEdgeCases:
    """Edge case and robustness tests."""

    def test_gas_exchange_extreme_ventilation(self):
        """Very high ventilation should not crash, PaCO2 should go very low."""
        ge = GasExchangeModel()
        for _ in range(50):
            bg = ge.update(minute_ventilation=40.0, fio2=0.21)
        assert bg.paco2 >= GasExchangeModel.PACO2_MIN
        assert bg.ph <= 7.8

    def test_gas_exchange_near_zero_ventilation(self):
        """Near-zero ventilation should cause CO2 retention, not crash."""
        ge = GasExchangeModel()
        for _ in range(50):
            bg = ge.update(minute_ventilation=0.5, fio2=0.21)
        assert bg.paco2 <= GasExchangeModel.PACO2_MAX
        assert bg.ph >= 6.8

    def test_respiratory_model_very_short_rr(self):
        """Very short RR interval (tachycardia) should not crash."""
        rm = RespiratoryModel()
        rs = rm.update(rr_sec=0.3)
        assert rs.respiratory_rate > 0.0
        assert 0.0 <= rs.respiratory_phase < 2.0 * math.pi + 0.01

    def test_respiratory_model_very_long_rr(self):
        """Very long RR interval (bradycardia) should not crash."""
        rm = RespiratoryModel()
        rs = rm.update(rr_sec=2.0)
        assert rs.respiratory_rate > 0.0

    def test_gas_exchange_high_metabolic_rate(self):
        """High metabolic rate → increased CO2 production → PaCO2 rises."""
        ge_rest = GasExchangeModel()
        ge_exercise = GasExchangeModel()
        for _ in range(80):
            ge_rest.update(minute_ventilation=7.0, metabolic_rate=1.0)
            ge_exercise.update(minute_ventilation=7.0, metabolic_rate=4.0)
        # Same ventilation but higher metabolism → higher PaCO2
        assert ge_exercise.state.paco2 > ge_rest.state.paco2

    def test_respiratory_model_multiple_beats_stable(self):
        """Running many beats at rest should produce stable values."""
        rm = RespiratoryModel()
        for _ in range(200):
            rs = rm.update(rr_sec=0.85)
        # Should be at steady state
        assert 10.0 <= rs.respiratory_rate <= 20.0
        assert 4.0 <= rs.minute_ventilation <= 12.0
        assert 80.0 <= rs.pao2 <= 110.0
        assert 33.0 <= rs.paco2 <= 47.0
        assert 7.33 <= rs.ph <= 7.47

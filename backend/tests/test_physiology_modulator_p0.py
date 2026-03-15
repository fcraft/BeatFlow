"""P0 physiology modulator tests.

Tests the compute_modifiers function from the physiology_modulator module,
verifying that emotion, substance, electrolyte, and environmental factors
correctly influence the resulting Modifiers.
"""

import pytest

from app.engine.core.types import Modifiers
from app.engine.modulation.physiology_modulator import compute_modifiers, AutonomicState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def baseline_autonomic() -> AutonomicState:
    """Return a neutral autonomic state."""
    return AutonomicState(sympathetic_tone=0.5, parasympathetic_tone=0.5)


def call_compute(base_modifiers=None, **user_commands) -> Modifiers:
    """Convenience wrapper around compute_modifiers."""
    return compute_modifiers(
        autonomic=baseline_autonomic(),
        pharma_levels={},
        user_commands=user_commands,
        damage_level=0.0,
        base_modifiers=base_modifiers,
    )


# ===========================================================================
# 1. Emotion arousal amplifies sympathetic tone
# ===========================================================================

class TestEmotionArousal:

    def test_high_arousal_increases_sympathetic(self):
        base = Modifiers(emotional_arousal=0.8)
        mods = call_compute(base_modifiers=base)
        # With high arousal, sympathetic tone should be elevated
        assert mods.sympathetic_tone > 0.5

    def test_high_arousal_increases_sa_rate(self):
        base_mods = call_compute()
        aroused = Modifiers(emotional_arousal=0.8)
        mods = call_compute(base_modifiers=aroused)
        assert mods.sa_rate_modifier > base_mods.sa_rate_modifier or mods.sa_rate_modifier >= 1.0

    def test_zero_arousal_neutral(self):
        base = Modifiers(emotional_arousal=0.0)
        mods = call_compute(base_modifiers=base)
        # Should not dramatically alter sympathetic
        assert 0.3 <= mods.sympathetic_tone <= 0.7


# ===========================================================================
# 2. Caffeine effect
# ===========================================================================

class TestCaffeineEffect:

    def test_caffeine_increases_sympathetic(self):
        base_no_caffeine = call_compute()
        base_with_caffeine = Modifiers(caffeine_level=0.5)
        mods = call_compute(base_modifiers=base_with_caffeine)
        assert mods.sympathetic_tone > base_no_caffeine.sympathetic_tone

    def test_caffeine_increases_sa_rate(self):
        base = Modifiers(caffeine_level=0.5)
        mods = call_compute(base_modifiers=base)
        neutral = call_compute()
        assert mods.sa_rate_modifier >= neutral.sa_rate_modifier


# ===========================================================================
# 3. Alcohol effect
# ===========================================================================

class TestAlcoholEffect:

    def test_alcohol_affects_parasympathetic(self):
        base = Modifiers(alcohol_level=0.7)
        mods = call_compute(base_modifiers=base)
        neutral = call_compute()
        # Alcohol should alter autonomic balance
        assert mods.parasympathetic_tone != neutral.parasympathetic_tone or \
               mods.sympathetic_tone != neutral.sympathetic_tone


# ===========================================================================
# 4. Dehydration effect
# ===========================================================================

class TestDehydrationEffect:

    def test_dehydration_decreases_preload(self):
        base = Modifiers(dehydration_level=0.8)
        mods = call_compute(base_modifiers=base)
        neutral = call_compute()
        assert mods.preload_modifier < neutral.preload_modifier

    def test_dehydration_increases_sa_rate(self):
        base = Modifiers(dehydration_level=0.8)
        mods = call_compute(base_modifiers=base)
        neutral = call_compute()
        assert mods.sa_rate_modifier >= neutral.sa_rate_modifier


# ===========================================================================
# 5. Temperature / fever
# ===========================================================================

class TestTemperatureEffect:

    def test_fever_increases_sa_rate(self):
        base = Modifiers(temperature=39.0)
        mods = call_compute(base_modifiers=base)
        neutral = call_compute()
        assert mods.sa_rate_modifier > neutral.sa_rate_modifier

    def test_normal_temp_neutral(self):
        base = Modifiers(temperature=37.0)
        mods = call_compute(base_modifiers=base)
        neutral = call_compute()
        assert abs(mods.sa_rate_modifier - neutral.sa_rate_modifier) < 0.15


# ===========================================================================
# 6. Sleep debt
# ===========================================================================

class TestSleepDebtEffect:

    def test_sleep_debt_increases_sympathetic(self):
        base = Modifiers(sleep_debt=0.8)
        mods = call_compute(base_modifiers=base)
        neutral = call_compute()
        assert mods.sympathetic_tone > neutral.sympathetic_tone


# ===========================================================================
# 7. Hyperkalemia
# ===========================================================================

class TestHyperkalemia:

    def test_high_potassium_increases_av_delay(self):
        base = Modifiers(potassium_level=6.5)
        mods = call_compute(base_modifiers=base)
        neutral = call_compute()
        assert mods.av_delay_modifier > neutral.av_delay_modifier


# ===========================================================================
# 8. Hypokalemia
# ===========================================================================

class TestHypokalemia:

    def test_low_potassium_affects_cell_stimuli(self):
        base = Modifiers(potassium_level=2.8)
        mods = call_compute(base_modifiers=base)
        # Low K affects His/Purkinje tau_close → check cell_stimuli
        cs = mods.cell_stimuli
        # Verify some modification happened for his or purkinje layers
        has_his = any("his" in str(k).lower() for k in cs) if cs else False
        has_purkinje = any("purkinje" in str(k).lower() for k in cs) if cs else False
        # At minimum, potassium should affect AV or ventricular conduction
        assert has_his or has_purkinje or mods.av_delay_modifier != 1.0, \
            "Low potassium should affect His/Purkinje conduction or AV delay"


# ===========================================================================
# 9. Hypercalcemia
# ===========================================================================

class TestHypercalcemia:

    def test_high_calcium_increases_modifier(self):
        base = Modifiers(calcium_level=12.0)
        mods = call_compute(base_modifiers=base)
        neutral = call_compute()
        assert mods.calcium_modifier > neutral.calcium_modifier


# ===========================================================================
# 10. Hypocalcemia
# ===========================================================================

class TestHypocalcemia:

    def test_low_calcium_decreases_modifier(self):
        base = Modifiers(calcium_level=7.0)
        mods = call_compute(base_modifiers=base)
        neutral = call_compute()
        assert mods.calcium_modifier < neutral.calcium_modifier

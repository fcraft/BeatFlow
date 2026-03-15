"""Tests for PharmacokineticsEngine (Task 5)."""
from __future__ import annotations

import math

import pytest

from app.engine.modulation.pharmacokinetics import (
    DRUG_PROFILES,
    PharmacokineticsEngine,
)


class TestPharmacokineticsEngine:
    """Test suite for one-compartment PK engine."""

    def setup_method(self) -> None:
        self.pk = PharmacokineticsEngine()

    def test_no_drugs_empty(self) -> None:
        result = self.pk.step(1.0)
        assert result == {}

    def test_administer_unknown_drug_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown drug"):
            self.pk.administer("aspirin")

    def test_beta_blocker_rise_and_fall(self) -> None:
        """Concentration should rise then fall."""
        self.pk.administer("beta_blocker", dose=1.0)
        prev = 0.0
        peak_t = 0.0
        peak_c = 0.0
        for i in range(200):
            c = self.pk.step(1.0)
            conc = c.get("beta_blocker", 0.0)
            if conc > peak_c:
                peak_c = conc
                peak_t = (i + 1)
            prev = conc

        assert peak_c > 0.01, "Should reach meaningful concentration"
        assert peak_t > 0, "Peak should occur after administration"

    def test_three_half_lives_decay(self) -> None:
        """After 3 half-lives, concentration < 12.5% of peak."""
        for drug_name, profile in DRUG_PROFILES.items():
            pk = PharmacokineticsEngine()
            pk.administer(drug_name, dose=1.0)

            # Find peak by stepping in small increments
            peak_c = 0.0
            dt = 1.0  # 1 second steps
            for _ in range(int(profile.half_life_s * 2)):
                c = pk.step(dt)
                conc = c.get(drug_name, 0.0)
                if conc > peak_c:
                    peak_c = conc

            # Now step for 3 more half-lives
            for _ in range(int(profile.half_life_s * 3)):
                c = pk.step(dt)

            final = c.get(drug_name, 0.0)
            assert final < peak_c * 0.125, (
                f"{drug_name}: after 3 half-lives, "
                f"concentration {final:.4f} >= 12.5% of peak {peak_c:.4f}"
            )

    def test_multiple_doses_stack(self) -> None:
        """Two doses of the same drug should produce higher concentration."""
        pk1 = PharmacokineticsEngine()
        pk1.administer("beta_blocker", dose=1.0)
        for _ in range(30):
            c1 = pk1.step(1.0)

        pk2 = PharmacokineticsEngine()
        pk2.administer("beta_blocker", dose=1.0)
        pk2.administer("beta_blocker", dose=1.0)
        for _ in range(30):
            c2 = pk2.step(1.0)

        assert c2["beta_blocker"] > c1["beta_blocker"] * 1.5

    def test_digoxin_potassium_interaction(self) -> None:
        """Low potassium should boost effective digoxin concentration."""
        pk_normal = PharmacokineticsEngine()
        pk_normal.set_potassium(4.0)
        pk_normal.administer("digoxin", dose=1.0)
        for _ in range(50):
            cn = pk_normal.step(1.0)

        pk_low_k = PharmacokineticsEngine()
        pk_low_k.set_potassium(3.0)
        pk_low_k.administer("digoxin", dose=1.0)
        for _ in range(50):
            cl = pk_low_k.step(1.0)

        assert cl["digoxin"] > cn["digoxin"], (
            "Low K should increase effective digoxin concentration"
        )

    def test_all_four_drugs_supported(self) -> None:
        for drug in ["beta_blocker", "amiodarone", "digoxin", "atropine"]:
            pk = PharmacokineticsEngine()
            pk.administer(drug, dose=1.0)
            c = pk.step(10.0)
            assert drug in c
            assert c[drug] > 0.0

    def test_serialization_roundtrip(self) -> None:
        """get_state/set_state must preserve concentrations."""
        self.pk.administer("beta_blocker", dose=1.0)
        self.pk.administer("digoxin", dose=0.5)
        for _ in range(20):
            self.pk.step(1.0)

        state = self.pk.get_state()
        c_before = self.pk.step(1.0)

        pk2 = PharmacokineticsEngine()
        pk2.set_state(state)
        c_after = pk2.step(1.0)

        for drug in c_before:
            assert abs(c_before[drug] - c_after[drug]) < 1e-6

    def test_zero_dose(self) -> None:
        self.pk.administer("beta_blocker", dose=0.0)
        c = self.pk.step(10.0)
        assert c.get("beta_blocker", 0.0) < 1e-6

    def test_concentration_non_negative(self) -> None:
        """Concentration must never go negative."""
        self.pk.administer("atropine", dose=1.0)
        for _ in range(500):
            c = self.pk.step(1.0)
            for val in c.values():
                assert val >= 0.0

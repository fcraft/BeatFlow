"""One-compartment pharmacokinetics engine.

Models absorption and elimination of cardiac drugs using the Bateman equation:
  C(t) = dose × (k_a/(k_a - k_e)) × (exp(-k_e×t) - exp(-k_a×t))

Supports: beta_blocker, amiodarone, digoxin, atropine.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class DrugProfile:
    """Pharmacokinetic parameters for a single drug."""
    name: str
    k_a: float          # Absorption rate constant (1/s)
    k_e: float          # Elimination rate constant (1/s)
    half_life_s: float   # Elimination half-life (seconds)
    therapeutic_min: float  # Minimum therapeutic concentration
    therapeutic_max: float  # Maximum therapeutic concentration
    toxic_threshold: float  # Toxicity threshold


# Drug profiles (time constants in seconds for beat-level simulation)
DRUG_PROFILES: dict[str, DrugProfile] = {
    "beta_blocker": DrugProfile(
        name="beta_blocker",
        k_a=0.02,        # ~50s absorption
        k_e=0.005,       # ~140s elimination half-life
        half_life_s=140.0,
        therapeutic_min=0.1,
        therapeutic_max=0.8,
        toxic_threshold=1.2,
    ),
    "amiodarone": DrugProfile(
        name="amiodarone",
        k_a=0.01,        # Slow absorption
        k_e=0.002,       # Very slow elimination (~350s half-life)
        half_life_s=350.0,
        therapeutic_min=0.1,
        therapeutic_max=0.7,
        toxic_threshold=1.0,
    ),
    "digoxin": DrugProfile(
        name="digoxin",
        k_a=0.015,       # Moderate absorption
        k_e=0.004,       # ~175s half-life
        half_life_s=175.0,
        therapeutic_min=0.08,
        therapeutic_max=0.5,
        toxic_threshold=0.7,
    ),
    "atropine": DrugProfile(
        name="atropine",
        k_a=0.03,        # Fast absorption
        k_e=0.008,       # ~87s half-life
        half_life_s=87.0,
        therapeutic_min=0.1,
        therapeutic_max=0.9,
        toxic_threshold=1.3,
    ),
}


@dataclass
class _ActiveDose:
    """Tracks a single administered dose."""
    drug: str
    dose: float
    elapsed: float = 0.0  # seconds since administration


class PharmacokineticsEngine:
    """One-compartment PK engine for cardiac drug simulation.

    Usage:
        pk = PharmacokineticsEngine()
        pk.administer("beta_blocker", dose=1.0)
        concentrations = pk.step(dt=0.83)  # one beat at 72 bpm
    """

    def __init__(self) -> None:
        self._active_doses: list[_ActiveDose] = []
        self._potassium: float = 4.0   # mEq/L — normal range 3.5-5.0

    def administer(self, drug_name: str, dose: float = 1.0) -> None:
        """Administer a drug dose. Dose is in normalised units."""
        if drug_name not in DRUG_PROFILES:
            raise ValueError(
                f"Unknown drug '{drug_name}'. "
                f"Available: {list(DRUG_PROFILES.keys())}"
            )
        self._active_doses.append(_ActiveDose(drug=drug_name, dose=dose))

    def set_potassium(self, k_level: float) -> None:
        """Set serum potassium level (mEq/L) for digoxin interaction."""
        self._potassium = max(2.5, min(7.0, k_level))

    def step(self, dt: float) -> dict[str, float]:
        """Advance time by *dt* seconds and return current concentrations.

        Returns dict mapping drug_name → normalised concentration [0, ~1.5].
        """
        concentrations: dict[str, float] = {}

        # Advance all active doses
        for ad in self._active_doses:
            ad.elapsed += dt

        # Remove doses that are essentially eliminated (< 0.1% of peak)
        self._active_doses = [
            ad for ad in self._active_doses
            if self._concentration(ad) > 1e-4
        ]

        # Sum concentrations per drug (multiple doses can stack)
        for ad in self._active_doses:
            c = self._concentration(ad)
            concentrations[ad.drug] = concentrations.get(ad.drug, 0.0) + c

        # Digoxin-potassium interaction: low K increases effective toxicity
        # by lowering the toxic_threshold. We model this by boosting
        # effective concentration when K is low.
        if "digoxin" in concentrations and self._potassium < 3.5:
            k_deficit = 3.5 - self._potassium
            # Each 0.5 mEq/L deficit increases effective concentration by ~30%
            boost = 1.0 + 0.6 * k_deficit
            concentrations["digoxin"] *= boost

        return concentrations

    def get_state(self) -> dict[str, Any]:
        """Serialize for snapshot."""
        return {
            "active_doses": [
                {"drug": ad.drug, "dose": ad.dose, "elapsed": ad.elapsed}
                for ad in self._active_doses
            ],
            "potassium": self._potassium,
        }

    def set_state(self, state: dict[str, Any]) -> None:
        """Restore from snapshot."""
        self._active_doses = [
            _ActiveDose(drug=d["drug"], dose=d["dose"], elapsed=d["elapsed"])
            for d in state.get("active_doses", [])
        ]
        self._potassium = state.get("potassium", 4.0)

    # ---- private ----

    @staticmethod
    def _concentration(ad: _ActiveDose) -> float:
        """Bateman equation: C(t) = dose × (k_a/(k_a-k_e)) × (e^(-k_e×t) - e^(-k_a×t))."""
        profile = DRUG_PROFILES[ad.drug]
        k_a = profile.k_a
        k_e = profile.k_e
        t = ad.elapsed

        if t <= 0:
            return 0.0

        # Guard against k_a == k_e (degenerate case)
        if abs(k_a - k_e) < 1e-12:
            return ad.dose * k_a * t * math.exp(-k_a * t)

        ratio = k_a / (k_a - k_e)
        c = ad.dose * ratio * (math.exp(-k_e * t) - math.exp(-k_a * t))
        return max(0.0, c)

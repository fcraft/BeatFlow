"""Gas exchange compartment model for the respiratory system.

Implements:
- Alveolar gas equations (simplified ideal alveolar gas equation)
- O2-Hb dissociation curve via Hill equation (n=2.7, P50=26.6 mmHg)
- Henderson-Hasselbalch equation for arterial pH
- Arterial blood gas state tracking (PaO2, PaCO2, SaO2, pH)

Reference physiology:
- Normal PaO2: 80-100 mmHg
- Normal PaCO2: 35-45 mmHg
- Normal SaO2: 95-100%
- Normal pH: 7.35-7.45
- Normal HCO3-: 22-26 mEq/L
"""
from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass
class BloodGasState:
    """Arterial blood gas state."""
    pao2: float = 95.0          # mmHg (normal 80-100)
    paco2: float = 40.0         # mmHg (normal 35-45)
    sao2: float = 97.5          # % (normal 95-100)
    ph: float = 7.40            # (normal 7.35-7.45)
    hco3: float = 24.0          # mEq/L (normal 22-26)
    pao2_alveolar: float = 104.0  # Alveolar O2 partial pressure


class GasExchangeModel:
    """Compartment-based gas exchange model.

    Uses simplified alveolar gas equations and O2-Hb dissociation curve
    to compute arterial blood gas values from respiratory parameters.

    Design: per-beat update (not per-sample) for performance.
    Typical overhead: <0.1ms per beat.
    """

    # ---- Hill equation parameters for O2-Hb dissociation ----
    HILL_N: float = 2.7         # Hill coefficient
    HILL_P50: float = 26.6      # P50 in mmHg (PO2 at 50% saturation)

    # ---- Alveolar gas equation constants ----
    P_ATM: float = 760.0        # Atmospheric pressure (mmHg)
    P_H2O: float = 47.0         # Water vapor pressure at 37°C (mmHg)
    RQ: float = 0.8             # Respiratory quotient (CO2 produced / O2 consumed)

    # ---- Metabolic constants ----
    VO2_REST: float = 250.0     # Resting O2 consumption (mL/min)
    VCO2_REST: float = 200.0    # Resting CO2 production (mL/min)

    # ---- Henderson-Hasselbalch constants ----
    HH_PKA: float = 6.1         # pKa for CO2/HCO3 system
    HH_S: float = 0.03          # Solubility coefficient (mEq/L/mmHg)

    # ---- Dynamics time constants (per-beat adaptation) ----
    TAU_PAO2: float = 8.0       # Beats to reach 63% of target PaO2
    TAU_PACO2: float = 12.0     # Beats to reach 63% of target PaCO2
    TAU_HCO3: float = 60.0      # Beats for renal HCO3 compensation (slow)

    # ---- Physiological bounds ----
    PAO2_MIN: float = 20.0
    PAO2_MAX: float = 600.0     # With supplemental O2
    PACO2_MIN: float = 10.0
    PACO2_MAX: float = 100.0
    HCO3_MIN: float = 8.0
    HCO3_MAX: float = 45.0

    def __init__(self) -> None:
        self._state = BloodGasState()

    @property
    def state(self) -> BloodGasState:
        return self._state

    def get_state_dict(self) -> dict:
        """Serialize for snapshot persistence."""
        return {
            "pao2": self._state.pao2,
            "paco2": self._state.paco2,
            "sao2": self._state.sao2,
            "ph": self._state.ph,
            "hco3": self._state.hco3,
        }

    def set_state_dict(self, d: dict) -> None:
        """Restore from snapshot."""
        self._state.pao2 = d.get("pao2", 95.0)
        self._state.paco2 = d.get("paco2", 40.0)
        self._state.sao2 = d.get("sao2", 97.5)
        self._state.ph = d.get("ph", 7.40)
        self._state.hco3 = d.get("hco3", 24.0)

    # ------------------------------------------------------------------
    # Core update (called once per beat)
    # ------------------------------------------------------------------

    def update(
        self,
        minute_ventilation: float,
        fio2: float = 0.21,
        cardiac_output: float = 5.0,
        metabolic_rate: float = 1.0,
        mechanical_ventilation: bool = False,
    ) -> BloodGasState:
        """Update blood gas state for this beat.

        Args:
            minute_ventilation: Current minute ventilation (L/min)
            fio2: Fraction of inspired O2 (0.21 = room air)
            cardiac_output: Cardiac output (L/min)
            metabolic_rate: Metabolic rate multiplier (1.0 = rest)
            mechanical_ventilation: If True, ventilation is guaranteed

        Returns:
            Updated BloodGasState
        """
        # Scale metabolic demands
        vo2 = self.VO2_REST * metabolic_rate
        vco2 = self.VCO2_REST * metabolic_rate

        # Effective alveolar ventilation (subtract dead space ~30%)
        dead_space_fraction = 0.30
        va = max(minute_ventilation * (1.0 - dead_space_fraction), 0.5)

        # ---- Alveolar gas equation ----
        # PaCO2 target: PaCO2 = VCO2 / VA * K (K = 863 for BTPS→STPD)
        paco2_target = (vco2 / max(va, 0.5)) * 0.863
        paco2_target = max(self.PACO2_MIN, min(self.PACO2_MAX, paco2_target))

        # Alveolar O2: PAO2 = FiO2 × (Patm - PH2O) - PaCO2 / RQ
        pio2 = fio2 * (self.P_ATM - self.P_H2O)
        pao2_alveolar = pio2 - paco2_target / self.RQ
        pao2_alveolar = max(self.PAO2_MIN, min(self.PAO2_MAX, pao2_alveolar))

        # A-a gradient (normally ~5-15 mmHg, increases with pathology)
        # Simplified: gradient increases with reduced CO
        aa_gradient = 5.0 + 10.0 * max(0.0, 1.0 - cardiac_output / 5.0)
        pao2_target = pao2_alveolar - aa_gradient
        pao2_target = max(self.PAO2_MIN, min(self.PAO2_MAX, pao2_target))

        # ---- First-order lag adaptation ----
        alpha_o2 = 1.0 / self.TAU_PAO2
        alpha_co2 = 1.0 / self.TAU_PACO2
        alpha_hco3 = 1.0 / self.TAU_HCO3

        new_pao2 = self._state.pao2 + alpha_o2 * (pao2_target - self._state.pao2)
        new_paco2 = self._state.paco2 + alpha_co2 * (paco2_target - self._state.paco2)

        # Clamp
        new_pao2 = max(self.PAO2_MIN, min(self.PAO2_MAX, new_pao2))
        new_paco2 = max(self.PACO2_MIN, min(self.PACO2_MAX, new_paco2))

        # ---- Renal HCO3 compensation (slow) ----
        # Target HCO3 adjusts to normalize pH around 7.40
        # Normal relationship: HCO3 = 24 × 10^(pH-7.40) — simplified
        hco3_target = 24.0 * (new_paco2 / 40.0)  # Metabolic compensation
        hco3_target = max(self.HCO3_MIN, min(self.HCO3_MAX, hco3_target))
        new_hco3 = self._state.hco3 + alpha_hco3 * (hco3_target - self._state.hco3)
        new_hco3 = max(self.HCO3_MIN, min(self.HCO3_MAX, new_hco3))

        # ---- Henderson-Hasselbalch equation ----
        new_ph = self._compute_ph(new_paco2, new_hco3)

        # ---- O2-Hb dissociation curve ----
        new_sao2 = self.compute_sao2(new_pao2, new_ph)

        # Update state
        self._state = BloodGasState(
            pao2=new_pao2,
            paco2=new_paco2,
            sao2=new_sao2,
            ph=new_ph,
            hco3=new_hco3,
            pao2_alveolar=pao2_alveolar,
        )
        return self._state

    # ------------------------------------------------------------------
    # O2-Hb dissociation curve (Hill equation)
    # ------------------------------------------------------------------

    def compute_sao2(self, pao2: float, ph: float = 7.40) -> float:
        """Compute SaO2 (%) from PaO2 using Hill equation with Bohr shift.

        The Bohr effect: acidosis shifts curve rightward (lower affinity),
        alkalosis shifts leftward (higher affinity).

        Args:
            pao2: Arterial O2 partial pressure (mmHg)
            ph: Arterial pH

        Returns:
            SaO2 in percent [0, 100]
        """
        if pao2 <= 0:
            return 0.0

        # Bohr effect: shift P50 by ~2.5 mmHg per 0.1 pH unit
        bohr_shift = -25.0 * (ph - 7.40)  # mmHg shift in P50
        p50_effective = max(10.0, self.HILL_P50 + bohr_shift)

        # Hill equation: SaO2 = PaO2^n / (PaO2^n + P50^n)
        po2_n = pao2 ** self.HILL_N
        p50_n = p50_effective ** self.HILL_N
        sao2 = 100.0 * po2_n / (po2_n + p50_n)

        return max(0.0, min(100.0, sao2))

    # ------------------------------------------------------------------
    # Henderson-Hasselbalch equation
    # ------------------------------------------------------------------

    def _compute_ph(self, paco2: float, hco3: float) -> float:
        """Compute arterial pH from Henderson-Hasselbalch equation.

        pH = pKa + log10([HCO3-] / (S × PaCO2))

        Args:
            paco2: Arterial CO2 partial pressure (mmHg)
            hco3: Bicarbonate concentration (mEq/L)

        Returns:
            Arterial pH
        """
        denominator = self.HH_S * max(paco2, 1.0)
        ratio = max(hco3, 0.1) / denominator
        ph = self.HH_PKA + math.log10(max(ratio, 0.01))
        return max(6.8, min(7.8, ph))

    # ------------------------------------------------------------------
    # Static helpers (useful for external callers / tests)
    # ------------------------------------------------------------------

    @staticmethod
    def sao2_to_spo2(sao2: float, perfusion_index: float = 1.0) -> float:
        """Convert SaO2 to SpO2 (pulse oximetry estimate).

        SpO2 approximates SaO2 but can differ with poor perfusion,
        motion artifacts, or abnormal hemoglobins.

        Args:
            sao2: Arterial O2 saturation (%)
            perfusion_index: Perfusion quality [0, 1], 1.0 = good

        Returns:
            SpO2 (%)
        """
        # Small bias at normal range, larger deviation with poor perfusion
        noise = (1.0 - perfusion_index) * 2.0  # Up to 2% error
        spo2 = sao2 - noise
        return max(0.0, min(100.0, spo2))

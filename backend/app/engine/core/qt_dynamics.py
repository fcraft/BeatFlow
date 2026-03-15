"""QT interval dynamic adaptation model.

Implements rate-adaptive QT correction with electrolyte and drug effects:

1. **Bazett-corrected QTc**: QTc = QT / sqrt(RR) as baseline reference
2. **First-order lag filter**: QT adapts gradually to HR changes (τ ≈ 30s)
3. **Electrolyte effects**:
   - Hypokalaemia (K⁺↓) → QT prolongation
   - Hyperkalaemia (K⁺↑) → QT shortening
   - Hypocalcaemia (Ca²⁺↓) → QT prolongation
   - Hypomagnesaemia (Mg²⁺↓) → QT prolongation
4. **Drug effects**:
   - Amiodarone → QT prolongation (Class III antiarrhythmic)
   - Beta-blockers → mild QT shortening via HR effect
5. **Ischemia effect**: Myocardial ischaemia → QT prolongation + dispersion

Reference:
- Bazett HC. Heart 1920;7:353-370.
- Rautaharju et al. Circulation 2009;119:e241-e250.
"""
from __future__ import annotations

import math
from typing import Any


# Normal QTc range (ms)
_QTC_NORMAL = 420.0     # ms (male upper normal ~440, female ~460)
_QT_MIN = 280.0          # Minimum physiological QT (ms)
_QT_MAX = 700.0          # Maximum physiological QT (ms)

# Adaptation time constant
_TAU_ADAPTATION = 30.0   # seconds — QT memory effect


class QtDynamics:
    """Rate-adaptive QT interval model with electrolyte/drug/ischemia effects.

    Usage::

        qt = QtDynamics()
        for each beat:
            qt_ms = qt.update(
                rr_sec=0.83,
                dt=0.83,
                potassium=4.0,
                calcium=9.5,
                magnesium=2.0,
                drug_concentrations={'amiodarone': 0.3},
                ischemia_level=0.0,
            )
    """

    def __init__(self, initial_qt_ms: float = 400.0) -> None:
        self._qt_adapted: float = initial_qt_ms
        self._qt_history: list[float] = []  # Last N QT values for dispersion calc

    def update(
        self,
        rr_sec: float,
        dt: float,
        *,
        potassium: float = 4.0,
        calcium: float = 9.5,
        magnesium: float = 2.0,
        drug_concentrations: dict[str, float] | None = None,
        ischemia_level: float = 0.0,
        temperature: float = 36.6,
    ) -> float:
        """Compute adapted QT interval for this beat.

        Args:
            rr_sec: Current RR interval (seconds).
            dt: Time step (seconds), typically = rr_sec.
            potassium: Serum K⁺ (mEq/L), normal 3.5-5.0.
            calcium: Serum Ca²⁺ (mg/dL), normal 8.5-10.5.
            magnesium: Serum Mg²⁺ (mg/dL), normal 1.7-2.2.
            drug_concentrations: Drug name → normalised concentration.
            ischemia_level: [0, 1] myocardial ischaemia severity.
            temperature: Core body temperature (°C).

        Returns:
            Adapted QT interval in milliseconds.
        """
        if drug_concentrations is None:
            drug_concentrations = {}

        # --- Step 1: Bazett target QTc ---
        # QT = QTc × sqrt(RR)  →  target QT for current RR
        rr_sec_clamped = max(0.3, min(2.0, rr_sec))
        qt_bazett = _QTC_NORMAL * math.sqrt(rr_sec_clamped)

        # --- Step 2: Electrolyte modifiers (additive, in ms) ---
        delta_electrolyte = 0.0

        # Potassium: hypo → prolongation, hyper → shortening
        if potassium < 3.5:
            # Each 0.5 mEq/L below 3.5 → +25ms QT prolongation
            delta_electrolyte += 50.0 * (3.5 - potassium)
        elif potassium > 5.0:
            # Each 0.5 mEq/L above 5.0 → -15ms QT shortening
            delta_electrolyte -= 30.0 * (potassium - 5.0)

        # Calcium: hypocalcaemia → prolongation (mainly ST segment)
        if calcium < 8.5:
            # Each 1 mg/dL below 8.5 → +30ms
            delta_electrolyte += 30.0 * (8.5 - calcium)

        # Magnesium: hypomagnesaemia → prolongation
        if magnesium < 1.7:
            # Each 0.5 mg/dL below 1.7 → +20ms
            delta_electrolyte += 40.0 * (1.7 - magnesium)

        # --- Step 3: Drug effects (additive, in ms) ---
        delta_drug = 0.0

        # Amiodarone: Class III — blocks IKr → QT prolongation
        amio = drug_concentrations.get("amiodarone", 0.0)
        if amio > 0.0:
            # Up to +80ms at therapeutic concentration (0.5)
            delta_drug += 160.0 * amio

        # Beta-blocker: minimal direct QT effect, slight shortening via HR
        bb = drug_concentrations.get("beta_blocker", 0.0)
        if bb > 0.0:
            delta_drug -= 10.0 * bb

        # Digoxin: shortens QT (scooped ST, shortened QT)
        dig = drug_concentrations.get("digoxin", 0.0)
        if dig > 0.0:
            delta_drug -= 40.0 * dig

        # --- Step 4: Ischemia effect ---
        delta_ischemia = 0.0
        if ischemia_level > 0.0:
            # Ischemia prolongs QT, up to +60ms at severe ischemia
            delta_ischemia = 60.0 * ischemia_level

        # --- Step 5: Temperature effect ---
        delta_temp = 0.0
        if temperature < 35.0:
            # Hypothermia prolongs QT: +15ms per °C below 35
            delta_temp = 15.0 * (35.0 - temperature)
        elif temperature > 38.5:
            # Hyperthermia shortens QT slightly: -5ms per °C above 38.5
            delta_temp = -5.0 * (temperature - 38.5)

        # --- Step 6: Compute target QT ---
        qt_target = qt_bazett + delta_electrolyte + delta_drug + delta_ischemia + delta_temp

        # Clamp to physiological bounds
        qt_target = max(_QT_MIN, min(_QT_MAX, qt_target))

        # --- Step 7: First-order lag adaptation ---
        # QT has a "memory" effect — it doesn't change instantaneously with HR
        alpha = 1.0 - math.exp(-dt / _TAU_ADAPTATION)
        self._qt_adapted += alpha * (qt_target - self._qt_adapted)
        self._qt_adapted = max(_QT_MIN, min(_QT_MAX, self._qt_adapted))

        # Track history for dispersion calculation
        self._qt_history.append(self._qt_adapted)
        if len(self._qt_history) > 30:
            self._qt_history.pop(0)

        return self._qt_adapted

    @property
    def qt_ms(self) -> float:
        """Current adapted QT in ms."""
        return self._qt_adapted

    @property
    def qtc_bazett(self) -> float:
        """Current QTc (Bazett-corrected) — informational only."""
        # Approximate from last known RR
        if len(self._qt_history) < 1:
            return _QTC_NORMAL
        return self._qt_adapted  # Already rate-corrected in adaptation

    @property
    def qt_dispersion_ms(self) -> float:
        """QT dispersion (max - min) over recent beats.

        Elevated QT dispersion is a risk marker for arrhythmia.
        """
        if len(self._qt_history) < 5:
            return 0.0
        recent = self._qt_history[-10:]
        return max(recent) - min(recent)

    def get_state(self) -> dict[str, Any]:
        """Serialize for save/restore."""
        return {
            "qt_adapted": self._qt_adapted,
            "qt_history": list(self._qt_history),
        }

    def set_state(self, state: dict[str, Any]) -> None:
        """Restore from a previous get_state() call."""
        self._qt_adapted = state.get("qt_adapted", 400.0)
        self._qt_history = list(state.get("qt_history", []))

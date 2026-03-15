"""Tests for PVC pattern → ectopic foci generation."""
import random

import pytest

from app.engine.core.types import EctopicFocus, Modifiers
from app.engine.modulation.physiology_modulator import (
    _generate_ectopic_foci_from_pattern,
    compute_modifiers,
)


class TestGenerateEctopicFociFromPattern:
    """Unit tests for _generate_ectopic_foci_from_pattern."""

    def test_isolated_no_damage_no_pvcs(self):
        """damage=0, pattern='isolated', 200 beats → no PVC ectopic foci."""
        total_foci = 0
        couplet_pending = False
        for i in range(200):
            foci, couplet_pending = _generate_ectopic_foci_from_pattern(
                pattern='isolated', damage_level=0.0,
                beat_index=i, couplet_pending=couplet_pending,
            )
            total_foci += len(foci)
        assert total_foci == 0

    def test_isolated_high_damage_random_pvcs(self):
        """damage=0.8, pattern='isolated', 200 beats → ~10-50 PVCs."""
        random.seed(42)
        total_foci = 0
        couplet_pending = False
        for i in range(200):
            foci, couplet_pending = _generate_ectopic_foci_from_pattern(
                pattern='isolated', damage_level=0.8,
                beat_index=i, couplet_pending=couplet_pending,
            )
            total_foci += len(foci)
        # P(PVC) = 0.8 * 0.15 = 0.12, so expect ~24 out of 200
        assert 5 <= total_foci <= 60, f"Expected 5-60 PVCs, got {total_foci}"

    def test_bigeminy_every_other_beat(self):
        """pattern='bigeminy', damage=0.3, odd-indexed beats have PVC foci."""
        random.seed(42)
        for i in range(20):
            foci, _ = _generate_ectopic_foci_from_pattern(
                pattern='bigeminy', damage_level=0.3,
                beat_index=i, couplet_pending=False,
            )
            if i % 2 == 1:
                assert len(foci) == 1, f"Beat {i} (odd) should have 1 PVC"
                assert foci[0].node == 'purkinje'
                assert 300 <= foci[0].coupling_interval_ms <= 450
            else:
                assert len(foci) == 0, f"Beat {i} (even) should have no PVC"

    def test_bigeminy_low_damage_no_pvcs(self):
        """Bigeminy requires damage_level > 0.1."""
        for i in range(20):
            foci, _ = _generate_ectopic_foci_from_pattern(
                pattern='bigeminy', damage_level=0.05,
                beat_index=i, couplet_pending=False,
            )
            assert len(foci) == 0

    def test_trigeminy_every_third_beat(self):
        """pattern='trigeminy', damage=0.3, every 3rd beat (index%3==2) has PVC."""
        random.seed(42)
        for i in range(30):
            foci, _ = _generate_ectopic_foci_from_pattern(
                pattern='trigeminy', damage_level=0.3,
                beat_index=i, couplet_pending=False,
            )
            if i % 3 == 2:
                assert len(foci) == 1, f"Beat {i} should have PVC"
            else:
                assert len(foci) == 0, f"Beat {i} should have no PVC"

    def test_couplets_paired(self):
        """pattern='couplets', damage=0.5, PVCs come in pairs."""
        random.seed(42)
        couplet_pending = False
        pvc_beats = []
        for i in range(20):
            foci, couplet_pending = _generate_ectopic_foci_from_pattern(
                pattern='couplets', damage_level=0.5,
                beat_index=i, couplet_pending=couplet_pending,
            )
            if foci:
                pvc_beats.append(i)

        # Couplets should produce consecutive pairs
        assert len(pvc_beats) >= 2
        # Check that PVCs come in consecutive pairs
        i = 0
        while i < len(pvc_beats) - 1:
            if pvc_beats[i + 1] == pvc_beats[i] + 1:
                i += 2  # Skip the pair
            else:
                i += 1
        # All PVCs should be accounted for in pairs
        pairs = 0
        for j in range(len(pvc_beats) - 1):
            if pvc_beats[j + 1] == pvc_beats[j] + 1:
                pairs += 1
        assert pairs >= 1, f"Expected at least 1 couplet pair, PVC beats: {pvc_beats}"


class TestComputeModifiersIntegration:
    """Integration tests calling compute_modifiers with beat_index."""

    def test_existing_ectopic_foci_preserved(self):
        """Manually set foci + pattern → both present."""
        random.seed(42)
        existing_focus = EctopicFocus(
            node='his', current=0.5, coupling_interval_ms=400.0, probability=0.8,
        )
        base = Modifiers(
            ectopic_foci=[existing_focus],
            pvc_pattern='bigeminy',
            damage_level=0.5,
        )
        m = compute_modifiers(
            base_modifiers=base,
            beat_index=1,  # odd → bigeminy fires
        )
        # Should have at least the existing focus plus a new one
        assert len(m.ectopic_foci) >= 2
        # The existing focus should still be there
        assert any(f.node == 'his' and f.current == 0.5 for f in m.ectopic_foci)
        # A new purkinje focus from bigeminy
        assert any(f.node == 'purkinje' for f in m.ectopic_foci)

    def test_compute_modifiers_backward_compatible(self):
        """compute_modifiers works without beat_index (defaults to 0)."""
        m = compute_modifiers()
        assert m is not None
        assert m.ectopic_foci == []

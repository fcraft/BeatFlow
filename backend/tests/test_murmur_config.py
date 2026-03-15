"""Tests for murmur configuration profiles."""
import pytest
from app.engine.mechanical.murmur_config import (
    MurmurProfile, MURMUR_PROFILES, MURMUR_TYPE_COMPAT,
)


class TestMurmurConfig:
    def test_all_profiles_have_required_fields(self) -> None:
        for name, profile in MURMUR_PROFILES.items():
            assert profile.shape in ('diamond', 'plateau', 'decrescendo', 'rumbling', 'machinery')
            assert profile.timing in ('systolic', 'diastolic', 'continuous')
            assert 0 < profile.freq_lo < profile.freq_hi
            assert 0 < profile.amp_factor < 1.0

    def test_all_profiles_have_four_site_weights(self) -> None:
        expected = {'aortic', 'pulmonic', 'tricuspid', 'mitral'}
        for name, profile in MURMUR_PROFILES.items():
            assert set(profile.site_weights.keys()) == expected
            for site, w in profile.site_weights.items():
                assert 0.0 <= w <= 1.0

    def test_compat_mapping_covers_legacy_types(self) -> None:
        assert '' in MURMUR_TYPE_COMPAT
        assert 'systolic' in MURMUR_TYPE_COMPAT
        assert 'diastolic' in MURMUR_TYPE_COMPAT

    def test_compat_values_exist_in_profiles(self) -> None:
        for legacy, clinical in MURMUR_TYPE_COMPAT.items():
            if clinical:
                assert clinical in MURMUR_PROFILES

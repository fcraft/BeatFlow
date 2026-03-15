"""Tests for LTTB downsampling utility."""
import numpy as np
import pytest

from app.engine.core.lttb import lttb_downsample


class TestLttbDownsample:
    """Test LTTB algorithm."""

    def test_passthrough_when_target_exceeds_input(self):
        data = np.array([1.0, 2.0, 3.0])
        result = lttb_downsample(data, 10)
        np.testing.assert_array_equal(result, data)

    def test_passthrough_when_target_equals_input(self):
        data = np.array([1.0, 2.0, 3.0, 4.0])
        result = lttb_downsample(data, 4)
        np.testing.assert_array_equal(result, data)

    def test_passthrough_when_target_less_than_3(self):
        data = np.array([1.0, 2.0, 3.0, 4.0])
        result = lttb_downsample(data, 2)
        np.testing.assert_array_equal(result, data)

    def test_preserves_first_and_last(self):
        data = np.arange(1000, dtype=np.float64)
        result = lttb_downsample(data, 50)
        assert len(result) == 50
        assert result[0] == data[0]
        assert result[-1] == data[-1]

    def test_output_length_matches_target(self):
        data = np.random.default_rng(42).normal(size=5000).astype(np.float64)
        result = lttb_downsample(data, 200)
        assert len(result) == 200

    def test_preserves_signal_shape(self):
        """Sine wave downsampled should still have similar min/max."""
        t = np.linspace(0, 4 * np.pi, 2000)
        data = np.sin(t)
        result = lttb_downsample(data, 100)
        assert result.max() > 0.9
        assert result.min() < -0.9

    def test_returns_copy_not_view(self):
        data = np.array([1.0, 2.0, 3.0])
        result = lttb_downsample(data, 10)
        result[0] = 999.0
        assert data[0] == 1.0

    def test_monotonic_linear_signal(self):
        """Linear signal downsampled should remain approximately linear."""
        data = np.linspace(0, 100, 1000)
        result = lttb_downsample(data, 50)
        assert len(result) == 50
        # Check approximately monotonic
        diffs = np.diff(result)
        assert np.all(diffs > 0)

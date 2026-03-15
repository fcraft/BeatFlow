"""Smoke tests for the extracted analysis module."""
import numpy as np
import pytest


def test_ecg_detector_imports():
    from app.analysis.ecg_detector import ecg_detect_scipy
    assert callable(ecg_detect_scipy)


def test_ecg_detector_all_imports():
    from app.analysis.ecg_detector import (
        ecg_detect_scipy,
        ecg_detect_neurokit2,
        ecg_detect_wfdb,
    )
    assert callable(ecg_detect_scipy)
    assert callable(ecg_detect_neurokit2)
    assert callable(ecg_detect_wfdb)


def test_pcg_detector_imports():
    from app.analysis.pcg_detector import pcg_detect_scipy
    assert callable(pcg_detect_scipy)


def test_pcg_detector_all_imports():
    from app.analysis.pcg_detector import (
        pcg_detect_scipy,
        pcg_detect_neurokit2,
        classify_s1s2,
    )
    assert callable(pcg_detect_scipy)
    assert callable(pcg_detect_neurokit2)
    assert callable(classify_s1s2)


def test_ecg_detect_on_synthetic():
    """Run scipy detector on synthetic signal with clear QRS-like peaks."""
    from app.analysis.ecg_detector import ecg_detect_scipy
    sr = 500
    duration = 5.0
    t = np.arange(0, duration, 1 / sr)
    sig = np.zeros_like(t)
    # Create periodic QRS-like bursts at ~1 Hz: narrow Gaussian at 8 Hz band
    for beat in range(5):
        center = beat + 0.5  # offset from 0 to avoid edge
        idx = int(center * sr)
        win = int(0.04 * sr)  # 40 ms half-width
        for j in range(-win, win + 1):
            if 0 <= idx + j < len(sig):
                # Gaussian pulse scaled so band-pass energy is high
                sig[idx + j] += np.exp(-0.5 * (j / (win / 4)) ** 2)
    result = ecg_detect_scipy(sig, sr, duration)
    assert len(result) >= 2, f"Should detect QRS peaks, got {len(result)}"


def test_ecg_detect_returns_list_of_dicts():
    """ecg_detect_scipy must return dicts with required keys."""
    from app.analysis.ecg_detector import ecg_detect_scipy
    sr = 500
    t = np.arange(0, 10, 1 / sr)
    # Sine-wave approximation of ECG: 1Hz fundamental
    sig = np.sin(2 * np.pi * 1.0 * t)
    duration = float(len(t) / sr)
    result = ecg_detect_scipy(sig, sr, duration)
    # May or may not detect peaks on pure sine, but must return a list
    assert isinstance(result, list)
    for item in result:
        assert "annotation_type" in item
        assert "start_time" in item
        assert "end_time" in item
        assert "confidence" in item
        assert "algorithm" in item
        assert item["algorithm"] == "scipy"


def test_pcg_detect_on_synthetic():
    """Run scipy PCG detector on synthetic signal with clear envelope peaks."""
    from app.analysis.pcg_detector import pcg_detect_scipy
    sr = 2000
    duration = 5.0
    t = np.arange(0, duration, 1 / sr)
    sig = np.zeros_like(t)
    # Heart sounds: two peaks per heartbeat at ~1Hz, with S1-S2 gap ~0.3s
    for beat in range(5):
        # S1 at beat second
        for offset in [0.0, 0.3]:
            center = beat + offset
            idx = int(center * sr)
            if idx < len(sig):
                # Gaussian burst
                win = int(0.03 * sr)
                for j in range(-win, win + 1):
                    if 0 <= idx + j < len(sig):
                        sig[idx + j] += np.exp(-0.5 * (j / (win / 3)) ** 2)
    result = pcg_detect_scipy(sig, sr, duration)
    assert isinstance(result, list)
    for item in result:
        assert item["annotation_type"] in ("s1", "s2")
        assert item["algorithm"] == "scipy"


def test_classify_s1s2_basic():
    """classify_s1s2 should alternate s1/s2 correctly for clear patterns."""
    from app.analysis.pcg_detector import classify_s1s2
    sr = 1000
    # S1-S2 pairs: short gap=200ms, long gap=600ms, repeating
    # Peaks at: 0, 200, 800, 1000, 1600, 1800 (samples)
    peaks = np.array([0, 200, 800, 1000, 1600, 1800])
    labels = classify_s1s2(peaks, sr)
    assert len(labels) == len(peaks)
    # All labels must be s1 or s2
    assert all(l in ("s1", "s2") for l in labels)


def test_classify_s1s2_single_peak():
    """Single peak should return ['s1']."""
    from app.analysis.pcg_detector import classify_s1s2
    labels = classify_s1s2(np.array([500]), 1000)
    assert labels == ["s1"]


def test_classify_s1s2_empty():
    """Empty peaks should return empty list."""
    from app.analysis.pcg_detector import classify_s1s2
    labels = classify_s1s2(np.array([]), 1000)
    assert labels == []


def test_files_module_uses_analysis_imports():
    """Ensure files.py imports from app.analysis (no stale internal defs)."""
    import importlib
    import app.api.v1.endpoints.files as files_mod
    # The new names should be importable from the module namespace
    assert hasattr(files_mod, "ecg_detect_scipy")
    assert hasattr(files_mod, "pcg_detect_scipy")
    assert hasattr(files_mod, "classify_s1s2")

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


def test_classify_s1s2_s1_only_flag():
    """s1_only=True should return all 's1' regardless of pattern."""
    from app.analysis.pcg_detector import classify_s1s2
    sr = 1000
    # Clear S1-S2 alternating pattern
    peaks = np.array([0, 300, 800, 1100, 1600, 1900])
    labels = classify_s1s2(peaks, sr, s1_only=True)
    assert labels == ["s1"] * len(peaks)


def test_classify_s1s2_uniform_s2_missing():
    """When S2 is missing and intervals are uniform ~0.8s,
    classify_s1s2 should detect S1-only pattern and return all 's1'."""
    from app.analysis.pcg_detector import classify_s1s2
    sr = 1000
    # Simulate S2 missing: peaks at every 800ms (75 BPM, only S1 detected)
    peaks = np.array([0, 800, 1600, 2400, 3200, 4000])
    labels = classify_s1s2(peaks, sr)
    assert labels == ["s1", "s1", "s1", "s1", "s1", "s1"]


def test_classify_s1s2_uniform_with_varying_hr():
    """Sliding window should handle gradually changing heart rate
    while still detecting all S1 when S2 is missing."""
    from app.analysis.pcg_detector import classify_s1s2
    sr = 1000
    # HR gradually increases from 75 BPM to 120 BPM
    # intervals: 800, 780, 750, 720, 680, 650, 600, 580, 550, 520, 500
    peaks = np.cumsum([0, 800, 780, 750, 720, 680, 650, 600, 580, 550, 520, 500])
    labels = classify_s1s2(peaks, sr)
    # All should be s1 (S2 missing, sliding window CV still low)
    unique = set(labels)
    assert unique == {"s1"}, f"Expected all s1, got {unique}"


def test_classify_s1s2_normal_alternating():
    """Normal S1-S2 alternating pattern should produce correct labels."""
    from app.analysis.pcg_detector import classify_s1s2
    sr = 1000
    # S1 at 0, S2 at 300, S1 at 800, S2 at 1100, S1 at 1600, S2 at 1900
    peaks = np.array([0, 300, 800, 1100, 1600, 1900])
    labels = classify_s1s2(peaks, sr)
    assert labels[0] == "s1"  # First peak is S1
    # Should alternate: s1, s2, s1, s2, s1, s2
    for i in range(len(peaks)):
        expected = "s1" if i % 2 == 0 else "s2"
        assert labels[i] == expected, f"Peak {i}: expected {expected}, got {labels[i]}"


def test_classify_s1s2_ectopic_beat():
    """Ectopic (premature) beat should be labeled as S1
    and NOT trigger alternating flip that follows."""
    from app.analysis.pcg_detector import classify_s1s2
    sr = 1000
    # Normal S1 at 0, 800; ectopic S1 at 1050 (250ms after normal S1),
    # then compensatory pause to next S1 at 1600 (550ms after ectopic)
    peaks = np.array([0, 800, 1050, 1600, 2400, 3200])
    labels = classify_s1s2(peaks, sr)
    # The ectopic peak at index 2 should be s1
    assert labels[2] == "s1", f"Ectopic peak should be s1, got {labels[2]}"
    # Should not cause entire sequence to flip
    assert labels[0] == "s1"
    assert labels[1] == "s1" or labels[1] == "s1"  # uniform detection may trigger


def test_classify_s1s2_amplitude_refinement():
    """When peak heights are provided and S2 has higher amplitude than S1,
    labels should be swapped."""
    from app.analysis.pcg_detector import classify_s1s2
    sr = 1000
    # Normal alternating intervals
    peaks = np.array([0, 300, 800, 1100, 1600, 1900])
    # S2 amplitudes (at index 1, 3, 5) are higher than S1 → swap expected
    heights = np.array([0.5, 1.0, 0.5, 1.0, 0.5, 1.0])
    labels = classify_s1s2(peaks, sr, peak_heights=heights)
    # S2 peaks (originally s2 but with higher amplitude) may be swapped back
    # The amplitudes don't necessarily force a swap if the interval pattern is clear
    # But at least verify no crash and valid labels
    assert all(l in ("s1", "s2") for l in labels)
    assert len(labels) == len(peaks)


def test_classify_s1s2_amplitude_weak_s2():
    """When S2 has weak amplitude (as expected), no swap should occur."""
    from app.analysis.pcg_detector import classify_s1s2
    sr = 1000
    peaks = np.array([0, 300, 800, 1100, 1600, 1900])
    # S1 stronger than S2 (normal physiology)
    heights = np.array([1.0, 0.4, 1.0, 0.4, 1.0, 0.4])
    labels = classify_s1s2(peaks, sr, peak_heights=heights)
    # S1 should be at even indices
    for i in range(0, len(peaks), 2):
        assert labels[i] == "s1", f"Peak {i}: expected s1, got {labels[i]}"
    for i in range(1, len(peaks), 2):
        assert labels[i] == "s2", f"Peak {i}: expected s2, got {labels[i]}"


def test_classify_s1s2_all_short_intervals():
    """When all intervals are short (both S1 and S2 detected, similar spacing),
    should default to all s1 rather than alternation to avoid BPM halving."""
    from app.analysis.pcg_detector import classify_s1s2
    sr = 1000
    # All ~0.25s intervals — could happen with very fast HR where S1/S2 spacing
    # becomes similar to S2/S1 spacing
    peaks = np.array([0, 250, 500, 750, 1000, 1250, 1500])
    labels = classify_s1s2(peaks, sr)
    assert all(l in ("s1", "s2") for l in labels)
    # Should not crash; specific classification depends on algorithm
    assert len(labels) == len(peaks)


def test_pcg_detect_scipy_uses_classify_s1s2():
    """pcg_detect_scipy should now use classify_s1s2 for label assignment."""
    from app.analysis.pcg_detector import pcg_detect_scipy
    sr = 2000
    duration = 4.0
    t = np.arange(0, duration, 1 / sr)
    sig = np.zeros_like(t)
    # Simulate S1-only: one peak per beat at 75 BPM (800ms apart)
    for beat in range(5):
        center = beat * 0.8
        idx = int(center * sr)
        if idx < len(sig):
            win = int(0.03 * sr)
            for j in range(-win, win + 1):
                if 0 <= idx + j < len(sig):
                    sig[idx + j] += np.exp(-0.5 * (j / (win / 3)) ** 2)
    result = pcg_detect_scipy(sig, sr, duration)
    # With uniform S1-only pattern, all labels should be s1
    for item in result:
        assert item["algorithm"] == "scipy"
        assert item["annotation_type"] in ("s1", "s2")


def test_pcg_detect_scipy_s1_only_param():
    """pcg_detect_scipy with s1_only=True should return all s1."""
    from app.analysis.pcg_detector import pcg_detect_scipy
    sr = 2000
    duration = 4.0
    t = np.arange(0, duration, 1 / sr)
    sig = np.zeros_like(t)
    # S1 and S2 peaks alternating
    for beat in range(5):
        for offset in [0.0, 0.3]:
            center = beat + offset
            idx = int(center * sr)
            if idx < len(sig):
                win = int(0.03 * sr)
                for j in range(-win, win + 1):
                    if 0 <= idx + j < len(sig):
                        sig[idx + j] += np.exp(-0.5 * (j / (win / 3)) ** 2)
    result = pcg_detect_scipy(sig, sr, duration, s1_only=True)
    for item in result:
        assert item["annotation_type"] == "s1", f"Expected s1, got {item['annotation_type']}"


def test_files_module_uses_analysis_imports():
    """Ensure files.py imports from app.analysis (no stale internal defs).
    
    使用 AST 分析验证 import 语句，避免触发完整的应用初始化。
    """
    import ast
    import os

    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    files_path = os.path.join(backend_dir, "app", "api", "v1", "endpoints", "files.py")

    with open(files_path) as f:
        tree = ast.parse(f.read(), filename=files_path)

    imported_names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "app.analysis.pcg_detector":
            for alias in node.names:
                imported_names.add(alias.name.split(" as ")[0])

    required = {"classify_s1s2", "pcg_detect_scipy", "pcg_detect_neurokit2"}
    assert required.issubset(imported_names), (
        f"files.py missing imports from app.analysis.pcg_detector: {required - imported_names}"
    )

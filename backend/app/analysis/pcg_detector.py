"""PCG detection algorithms — pure signal-processing functions, no HTTP/FastAPI dependencies."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as np


def classify_s1s2(peaks: "np.ndarray", sr: int) -> list:
    """
    根据相邻峰间距对 S1/S2 分类。
    原理：S1→S2 (收缩期) 间距 < S2→S1 (舒张期) 间距。
    """
    import numpy as np
    if len(peaks) < 2:
        return ["s1"] * len(peaks)

    intervals = np.diff(peaks.astype(float)) / sr  # seconds between peaks
    n = len(peaks)
    labels = ["s1"] * n

    # 找周期性模式：将间距聚类为短/长两类
    median_interval = float(np.median(intervals))
    short_intervals = intervals < median_interval * 0.85

    # 如果能分出短/长，按模式分配
    if np.any(short_intervals) and not np.all(short_intervals):
        # 从第一个短间距前的峰开始标记 S1
        # 短间距 = S1→S2，长间距 = S2→S1
        # 找第一个短间距
        first_short = int(np.argmax(short_intervals))
        # 第一个短间距的起始峰是 S1
        # 遍历所有峰，基于间距模式打标
        cur = "s1"
        labels[first_short] = "s1"
        for i in range(first_short, n - 1):
            labels[i] = cur
            if short_intervals[i]:  # 短间距后是 S2
                cur = "s2" if cur == "s1" else "s1"
            else:  # 长间距后是 S1
                cur = "s1"
        # 填充 first_short 之前的峰（反向推）
        cur = labels[first_short]
        for i in range(first_short - 1, -1, -1):
            cur = "s2" if cur == "s1" else "s1"
            labels[i] = cur
    else:
        # 无法区分，交替分配
        for i in range(n):
            labels[i] = "s1" if i % 2 == 0 else "s2"

    return labels


def pcg_detect_scipy(sig: "np.ndarray", work_sr: int, duration: float) -> list:
    """SciPy Hilbert-envelope S1/S2 检测"""
    import numpy as np
    from scipy import signal as sp_signal

    nyq = work_sr / 2.0
    b, a = sp_signal.butter(4, [20.0 / nyq, 400.0 / nyq], btype="band")
    filtered = sp_signal.filtfilt(b, a, sig)

    analytic = sp_signal.hilbert(filtered)
    envelope = np.abs(analytic)

    b_lp, a_lp = sp_signal.butter(4, 10.0 / nyq, btype="low")
    smooth = sp_signal.filtfilt(b_lp, a_lp, envelope)

    thr = float(np.mean(smooth) + 1.5 * np.std(smooth))
    min_dist = max(1, int(work_sr * 0.15))
    peaks, props = sp_signal.find_peaks(smooth, height=thr, distance=min_dist, prominence=thr * 0.3)

    peak_heights = props["peak_heights"]
    max_h = float(np.max(peak_heights)) if len(peak_heights) > 0 else 1.0

    half_w = 0.04
    result = []
    for idx, pk in enumerate(peaks):
        t = float(pk) / work_sr
        conf = round(float(peak_heights[idx]) / (max_h + 1e-9), 4)
        ann_type = "s1" if idx % 2 == 0 else "s2"
        result.append({
            "annotation_type": ann_type,
            "start_time": round(max(0.0, t - half_w), 4),
            "end_time":   round(min(duration, t + half_w), 4),
            "confidence": min(1.0, conf),
            "label": ann_type.upper(),
            "source": "auto",
            "algorithm": "scipy",
        })
    return result


def pcg_detect_neurokit2(sig: "np.ndarray", work_sr: int, duration: float) -> list:
    """
    NeuroKit2 心音检测: 使用带通滤波 + 小波分解的能量包络，
    结合自适应峰值分类进行 S1/S2 区分
    """
    import numpy as np
    from scipy import signal as sp_signal

    try:
        import neurokit2 as nk  # type: ignore

        # 1. 清理信号（带通 + 归一化）
        cleaned = nk.signal_filter(
            sig, sampling_rate=work_sr,
            lowcut=20, highcut=400, method="butterworth", order=4
        )

        # 2. 计算信号功率包络（滑动 RMS，窗口 50ms）
        win_samples = max(1, int(0.05 * work_sr))
        sq = cleaned ** 2
        kernel = np.ones(win_samples) / win_samples
        power = np.sqrt(np.convolve(sq, kernel, mode="same"))

        # 3. 再次低通平滑
        smooth = nk.signal_filter(power, sampling_rate=work_sr, highcut=15, method="butterworth", order=2)

        # 4. 峰值检测
        min_dist = max(1, int(work_sr * 0.12))
        thr = float(np.mean(smooth) + 1.2 * np.std(smooth))
        from scipy.signal import find_peaks
        peaks, props = find_peaks(smooth, height=thr, distance=min_dist, prominence=thr * 0.25)

        if len(peaks) == 0:
            return pcg_detect_scipy(sig, work_sr, duration)

        peak_heights = props["peak_heights"]
        max_h = float(np.max(peak_heights)) or 1.0

        # 5. S1/S2 分类：利用相邻峰间距
        # S1-S2 间距短（收缩期 ~0.3s），S2-S1 间距长（舒张期 ~0.5s）
        result = []
        half_w = 0.04
        labels = classify_s1s2(peaks, work_sr)

        for idx, pk in enumerate(peaks):
            t = float(pk) / work_sr
            conf = round(float(peak_heights[idx]) / (max_h + 1e-9), 4)
            ann_type = labels[idx]
            result.append({
                "annotation_type": ann_type,
                "start_time": round(max(0.0, t - half_w), 4),
                "end_time":   round(min(duration, t + half_w), 4),
                "confidence": min(1.0, conf),
                "label": ann_type.upper(),
                "source": "auto",
                "algorithm": "neurokit2",
            })
        return result

    except Exception:
        # Fallback to scipy
        return pcg_detect_scipy(sig, work_sr, duration)

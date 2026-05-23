"""PCG detection algorithms — pure signal-processing functions, no HTTP/FastAPI dependencies."""
from __future__ import annotations

# Enable PEP 604 union syntax (X | Y) on Python 3.9 for neurokit2 compat
try:
    import eval_type_backport  # noqa: F401
except ImportError:
    pass

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    import numpy as np


def classify_s1s2(peaks: "np.ndarray", sr: int, s1_only: bool = False,
                  peak_heights: "np.ndarray | None" = None) -> list:
    """
    根据相邻峰间距对 S1/S2 分类。

    原理：S1→S2 (收缩期) 间距 < S2→S1 (舒张期) 间距。

    改进：
    - s1_only=True 时全部标记为 S1
    - 滑动窗口均匀间距检测：自动识别 S2 缺失场景，
      支持同一文件内的心率变化（窗口局部判断）
    - 早搏检测：极短间距（<0.30s）且前导间距 > 短间距 1.5 倍
      时，将该峰值标记为早搏 S1，不触发后续标签翻转
    - 振幅辅助：若 S1/S2 对的振幅与预期相反（S2 比 S1 强 20%+），
      交换标签
    """
    import numpy as np

    n = len(peaks)
    if s1_only:
        return ["s1"] * n
    if n < 2:
        return ["s1"] * n

    intervals = np.diff(peaks.astype(float)) / sr  # seconds between peaks

    # ── 滑动窗口均匀间距检测 ─────────────────────────────────────────
    # 若 ≥80% 的局部窗口内 CV < 0.25 且均值在心跳周期范围
    # (0.4–2.0s → 30–150 BPM)，判定 S2 缺失，全部标记为 S1。
    # 滑动窗口保证局部心率变化场景下也能正确识别。
    window_size = min(5, max(3, len(intervals)))
    stride = max(1, window_size // 3)
    uniform_count = 0
    total_windows = 0

    for start in range(0, len(intervals) - window_size + 1, stride):
        win = intervals[start:start + window_size]
        local_mean = float(np.mean(win))
        if local_mean <= 0:
            continue
        local_cv = float(np.std(win) / local_mean)
        if local_cv < 0.25 and 0.4 <= local_mean <= 2.0:
            uniform_count += 1
        total_windows += 1

    if total_windows > 0 and uniform_count >= total_windows * 0.8:
        return ["s1"] * n

    # ── 早搏检测 ─────────────────────────────────────────────────────
    # 早搏特征：极短间距（<0.30s）且前一间距 > 该短间距的 1.5 倍。
    # ectopic_peak[i] 表示第 i 个峰是早搏触发。
    ectopic_peak = [False] * n
    for i in range(2, n):
        if intervals[i - 1] < 0.30 and intervals[i - 2] > intervals[i - 1] * 1.5:
            ectopic_peak[i] = True

    # ── 间距模式分类 ─────────────────────────────────────────────────
    # 使用排序后最大间隙分割法将间距分为短/长两类，
    # 比简单 median * 0.85 更鲁棒（避免短间距成为中位数导致误判）。
    sorted_intervals = np.sort(intervals)
    best_gap = 0.0
    best_mid = 0.0
    for j in range(len(sorted_intervals) - 1):
        gap = float(sorted_intervals[j + 1] - sorted_intervals[j])
        if gap > best_gap:
            best_gap = gap
            best_mid = float(sorted_intervals[j] + sorted_intervals[j + 1]) / 2.0

    if best_gap > 0 and best_gap > sorted_intervals[-1] * 0.05:
        short_threshold = best_mid
    else:
        # 无明显间隙 → 所有间距相近
        short_threshold = float(np.median(intervals)) * 0.85

    short_intervals = intervals < short_threshold

    labels = ["s1"] * n

    if np.any(short_intervals) and not np.all(short_intervals):
        first_short = int(np.argmax(short_intervals))
        cur = "s1"

        if first_short < n - 1:
            for i in range(first_short, n - 1):
                labels[i] = cur
                if ectopic_peak[i + 1]:
                    # 下一个峰是早搏，保持 S1 标签
                    cur = cur
                elif short_intervals[i]:
                    cur = "s2" if cur == "s1" else "s1"
                else:
                    cur = "s1"
            labels[n - 1] = cur

        # 反向填充 first_short 之前的峰
        # 保守策略：无法确定前的序列模式，
        # 以 first_short 标签为准（避免交替导致的 BPM 减半）
        for i in range(first_short - 1, -1, -1):
            labels[i] = labels[first_short]
    else:
        # 无法通过间距辨识，默认全部归为 S1（避免误标导致的 BPM 减半）
        return ["s1"] * n

    # ── 振幅精修 ─────────────────────────────────────────────────────
    # S1 通常振幅 > S2。若相邻 S1/S2 对的振幅与预期相反，
    # 说明间距分类可能出错，交换标签。
    if peak_heights is not None and len(peak_heights) == n:
        heights = np.array(peak_heights, dtype=float)
        for i in range(n - 1):
            if labels[i] == "s1" and labels[i + 1] == "s2":
                if heights[i + 1] > heights[i] * 1.2:
                    labels[i], labels[i + 1] = labels[i + 1], labels[i]

    return labels


# ─────────────────────────────────────────────────────────────────────────────
# 自适应预处理 — 信号质量分析 + 动态滤波 + 局部阈值
# ─────────────────────────────────────────────────────────────────────────────

def _analyze_signal_quality(sig: "np.ndarray", sr: int) -> dict:
    """
    分析信号质量，返回 SNR 估计、主频带、噪声基底。

    方法：对信号做周期图（Welch），将功率谱分为心音频带 (20–200 Hz)
    和噪声频带 (>400 Hz)，以频带功率比作为 SNR 估计。
    """
    import numpy as np
    from scipy import signal as sp_signal

    nperseg = min(len(sig), sr * 2)
    freqs, psd = sp_signal.welch(sig, sr, nperseg=nperseg, scaling="density")

    # 心音频带 20–200 Hz
    hs_mask = (freqs >= 20) & (freqs <= 200)
    hs_power = float(np.trapezoid(psd[hs_mask], freqs[hs_mask])) if hs_mask.any() else 0.0

    # 噪声频带 > 400 Hz（高频噪声）
    noise_mask = freqs > 400
    noise_power = float(np.trapezoid(psd[noise_mask], freqs[noise_mask])) if noise_mask.any() else 1e-9

    snr = hs_power / (noise_power + 1e-9)

    # 主频：心音频带内 PSD 最大值对应的频率
    if hs_mask.any():
        dominant_freq = float(freqs[hs_mask][np.argmax(psd[hs_mask])])
    else:
        dominant_freq = 100.0

    # 噪声基底：信号包络的偏度（正偏度高 = 有清晰的峰）
    analytic = sp_signal.hilbert(sig)
    envelope = np.abs(analytic)
    # 峭度 (kurtosis) — 高峰度表示有尖锐的峰
    env_std = float(np.std(envelope)) or 1e-9
    kurtosis = float(np.mean((envelope - np.mean(envelope))**4) / (env_std**4))

    return {
        "snr": round(snr, 2),
        "dominant_freq": round(dominant_freq, 1),
        "kurtosis": round(kurtosis, 2),
    }


def _adaptive_filter(sig: "np.ndarray", sr: int, quality: dict) -> "np.ndarray":
    """
    根据信号质量自适应选择带通滤波参数。

    - 高 SNR / 高峰度 → 心音清晰，用较宽通带 (20–400 Hz) 保留细节
    - 低 SNR / 低峰度 → 信号微弱或噪声大，用较窄通带 (30–250 Hz) 抑制噪声
    - 若主频偏低 (< 80 Hz)，进一步收窄高通截止
    """
    import numpy as np
    from scipy import signal as sp_signal

    snr = quality["snr"]
    kurt = quality["kurtosis"]
    dom_freq = quality["dominant_freq"]

    # 根据 SNR 和峭度决定滤波器带宽
    if snr > 10 and kurt > 5:
        lowcut, highcut = 20.0, 400.0  # 高质量：宽通带
    elif snr > 3:
        lowcut, highcut = 25.0, 300.0  # 中等质量
    else:
        lowcut, highcut = 30.0, 250.0  # 低质量：窄通带，强降噪

    # 若主频偏低，收窄通带以聚焦心音能量
    if dom_freq < 80:
        highcut = min(highcut, 250.0)

    nyq = sr / 2.0
    b, a = sp_signal.butter(4, [lowcut / nyq, highcut / nyq], btype="band")
    return sp_signal.filtfilt(b, a, sig)


def _adaptive_threshold(envelope: "np.ndarray", sr: int,
                         min_dist: int) -> "np.ndarray":
    """
    基于局部统计的自适应阈值，替代全局 mean + k*std。

    将信号分为窗口（~1 秒），每个窗口独立计算 mean + k*std，
    线性插值得到逐样本阈值。这样在信号幅度变化时（如运动/静息切换），
    不会因全局阈值过低而误检，或过高而漏检。
    """
    import numpy as np

    win_samples = int(sr * 1.0)  # 1 秒窗口
    if win_samples >= len(envelope):
        # 信号过短，退化为全局阈值
        thr = float(np.mean(envelope) + 1.5 * np.std(envelope))
        return np.full_like(envelope, thr)

    n_windows = max(1, len(envelope) // win_samples)
    thresholds = np.zeros(len(envelope))

    for i in range(n_windows):
        lo = i * win_samples
        hi = min(len(envelope), (i + 1) * win_samples)
        chunk = envelope[lo:hi]
        if len(chunk) < min_dist:
            continue
        local_thr = float(np.mean(chunk) + 1.5 * np.std(chunk))
        thresholds[lo:hi] = local_thr

    # 处理尾部不足一个窗口的部分
    tail_start = n_windows * win_samples
    if tail_start < len(envelope):
        chunk = envelope[tail_start:]
        if len(chunk) >= min_dist:
            thresholds[tail_start:] = float(np.mean(chunk) + 1.5 * np.std(chunk))
        else:
            thresholds[tail_start:] = thresholds[tail_start - 1] if tail_start > 0 else thresholds[0]

    # 中值滤波平滑阈值曲线，避免窗口边界跳变
    smooth_win = max(3, min_dist // 2)
    if smooth_win % 2 == 0:
        smooth_win += 1
    from scipy.ndimage import median_filter
    thresholds = median_filter(thresholds, size=smooth_win)

    return thresholds


# ─────────────────────────────────────────────────────────────────────────────
# 检测函数
# ─────────────────────────────────────────────────────────────────────────────


def pcg_detect_scipy(sig: "np.ndarray", work_sr: int, duration: float,
                     s1_only: bool = False, min_bpm: "Optional[int]" = None,
                     max_bpm: "Optional[int]" = None) -> list:
    """SciPy Hilbert-envelope S1/S2 检测（scipy.signal 实现 + 自适应预处理）。

    Parameters
    ----------
    s1_only : bool
        仅检测 S1，忽略 S2 分类（适用于 S2 信号极弱场景）
    min_bpm, max_bpm : int | None
        预期 BPM 范围约束。
    """
    import numpy as np
    from scipy import signal as sp_signal

    # ── 自适应预处理：信号质量分析 + 动态滤波（scipy 实现）─────────
    quality = _analyze_signal_quality(sig, work_sr)
    filtered = _adaptive_filter(sig, work_sr, quality)

    # ── 多尺度包络 ──────────────────────────────────────────────────
    analytic = sp_signal.hilbert(filtered)
    envelope = np.abs(analytic)
    win_short = max(1, int(0.02 * work_sr))
    win_long = max(1, int(0.08 * work_sr))
    sq = filtered ** 2
    kernel_s = np.ones(win_short) / win_short
    kernel_l = np.ones(win_long) / win_long
    rms_short = np.sqrt(np.convolve(sq, kernel_s, mode="same"))
    rms_long = np.sqrt(np.convolve(sq, kernel_l, mode="same"))
    envelope_combined = np.maximum.reduce([envelope, rms_short, rms_long])

    nyq = work_sr / 2.0
    b_lp, a_lp = sp_signal.butter(4, 10.0 / nyq, btype="low")
    smooth = sp_signal.filtfilt(b_lp, a_lp, envelope_combined)

    # ── 自适应局部阈值 ──────────────────────────────────────────────
    min_dist = max(1, int(work_sr * 0.15))
    thresholds = _adaptive_threshold(smooth, work_sr, min_dist)

    # S1-only：降低阈值更激进抓峰（无需区分 S1/S2，可容忍更多候选）
    if s1_only:
        thresholds = thresholds * 0.55

    # BPM 约束
    if min_bpm is not None and max_bpm is not None:
        bpm_dist = int(work_sr * 60.0 / max_bpm * 0.85)
        min_dist = max(min_dist, bpm_dist)
        expected_max = int(duration * max_bpm / 60.0 * 1.3) + 3
        best_peaks, best_props = None, None
        local_thr = thresholds.copy()
        for attempt in range(3):
            peaks, props = sp_signal.find_peaks(
                smooth, height=local_thr, distance=min_dist, prominence=local_thr * 0.3
            )
            if len(peaks) <= expected_max or attempt == 2:
                best_peaks, best_props = peaks, props
                break
            local_thr = local_thr * 1.25
        peaks, props = best_peaks, best_props
    else:
        peaks, props = sp_signal.find_peaks(
            smooth, height=thresholds, distance=min_dist, prominence=thresholds * 0.3
        )

    peak_heights = props["peak_heights"]
    max_h = float(np.max(peak_heights)) if len(peak_heights) > 0 else 1.0

    # 使用 classify_s1s2 统一分类（替代简单奇偶交替）
    labels = classify_s1s2(peaks, work_sr, s1_only=s1_only, peak_heights=peak_heights)

    half_w = 0.04
    result = []
    for idx, pk in enumerate(peaks):
        t = float(pk) / work_sr
        conf = round(float(peak_heights[idx]) / (max_h + 1e-9), 4)
        result.append({
            "annotation_type": labels[idx],
            "start_time": round(max(0.0, t - half_w), 4),
            "end_time":   round(min(duration, t + half_w), 4),
            "confidence": min(1.0, conf),
            "label": labels[idx].upper(),
            "source": "auto",
            "algorithm": "scipy",
        })
    return result


def pcg_detect_neurokit2(sig: "np.ndarray", work_sr: int, duration: float,
                         s1_only: bool = False, min_bpm: "Optional[int]" = None,
                         max_bpm: "Optional[int]" = None) -> list:
    """
    NeuroKit2 心音检测: 使用带通滤波 + 小波分解的能量包络，
    结合自适应峰值分类进行 S1/S2 区分

    Parameters
    ----------
    s1_only : bool
        仅检测 S1，忽略 S2 分类（适用于 S2 信号极弱场景）
    min_bpm, max_bpm : int | None
        预期 BPM 范围约束。
    """
    import numpy as np
    from scipy import signal as sp_signal

    try:
        import neurokit2 as nk  # type: ignore

        # ── 自适应预处理：信号质量分析 + 动态滤波 ──────────────────
        quality = _analyze_signal_quality(sig, work_sr)
        # 根据质量调整 neurokit2 滤波参数
        snr = quality["snr"]
        if snr > 10:
            lowcut, highcut = 20.0, 400.0
        elif snr > 3:
            lowcut, highcut = 25.0, 350.0
        else:
            lowcut, highcut = 30.0, 250.0

        # 1. 清理信号（自适应带通 + 归一化）
        cleaned = nk.signal_filter(
            sig, sampling_rate=work_sr,
            lowcut=lowcut, highcut=highcut, method="butterworth", order=4
        )

        # 2. 多尺度功率包络
        for ws, label in [(0.03, "short"), (0.07, "long")]:
            w = max(1, int(ws * work_sr))
            sq = cleaned ** 2
            kernel = np.ones(w) / w
            if label == "short":
                power_short = np.sqrt(np.convolve(sq, kernel, mode="same"))
            else:
                power_long = np.sqrt(np.convolve(sq, kernel, mode="same"))
        power = np.maximum(power_short, power_long)

        # 3. 再次低通平滑
        smooth = nk.signal_filter(power, sampling_rate=work_sr, highcut=15, method="butterworth", order=2)

        # 4. 峰值检测 — 自适应阈值
        min_dist = max(1, int(work_sr * 0.12))
        thresholds = _adaptive_threshold(smooth, work_sr, min_dist)

        # S1-only：降低阈值更激进抓峰（无需区分 S1/S2，可容忍更多候选）
        if s1_only:
            thresholds = thresholds * 0.55

        # BPM 约束
        if min_bpm is not None and max_bpm is not None:
            from scipy.signal import find_peaks as _fp
            bpm_dist = int(work_sr * 60.0 / max_bpm * 0.85)
            min_dist = max(min_dist, bpm_dist)
            expected_max = int(duration * max_bpm / 60.0 * 1.3) + 3

            # 迭代调整阈值
            best_peaks_found = None
            best_props_found = None
            local_thr = thresholds.copy()
            for attempt in range(3):
                peaks, props = _fp(
                    smooth, height=local_thr, distance=min_dist, prominence=local_thr * 0.25
                )
                if len(peaks) <= expected_max or attempt == 2:
                    best_peaks_found, best_props_found = peaks, props
                    break
                local_thr = local_thr * 1.25
            peaks, props = best_peaks_found, best_props_found
        else:
            from scipy.signal import find_peaks
            peaks, props = find_peaks(
                smooth, height=thresholds, distance=min_dist, prominence=thresholds * 0.25
            )

        if len(peaks) == 0:
            return pcg_detect_scipy(sig, work_sr, duration, s1_only)

        peak_heights = props["peak_heights"]
        max_h = float(np.max(peak_heights)) or 1.0

        # 5. S1/S2 分类：利用相邻峰间距 + 振幅辅助
        # S1-S2 间距短（收缩期 ~0.3s），S2-S1 间距长（舒张期 ~0.5s）
        result = []
        half_w = 0.04
        labels = classify_s1s2(peaks, work_sr, s1_only=s1_only, peak_heights=peak_heights)

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
        return pcg_detect_scipy(sig, work_sr, duration, s1_only)

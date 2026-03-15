"""ECG detection algorithms — pure signal-processing functions, no HTTP/FastAPI dependencies."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as np


def ecg_detect_scipy(sig: "np.ndarray", work_sr: int, duration: float) -> list:
    """SciPy Pan-Tompkins 简版 QRS + P/T 检测"""
    import numpy as np
    from scipy import signal as sp_signal

    nyq = work_sr / 2.0

    b, a = sp_signal.butter(4, [5.0 / nyq, 15.0 / nyq], btype="band")
    filtered = sp_signal.filtfilt(b, a, sig)
    diff = np.diff(filtered, prepend=filtered[0])
    squared = diff ** 2
    mw = max(1, int(work_sr * 0.15))
    integrated = np.convolve(squared, np.ones(mw) / mw, mode="same")

    thr = float(np.mean(integrated) + 1.2 * np.std(integrated))
    min_dist = max(1, int(work_sr * 0.25))
    qrs_peaks, props = sp_signal.find_peaks(integrated, height=thr, distance=min_dist, prominence=thr * 0.2)
    peak_heights = props["peak_heights"]
    max_h = float(np.max(peak_heights)) if len(peak_heights) > 0 else 1.0

    result = []
    half_qrs = 0.05
    for i, pk in enumerate(qrs_peaks):
        t = float(pk) / work_sr
        conf = round(float(peak_heights[i]) / (max_h + 1e-9), 4)
        result.append({
            "annotation_type": "qrs",
            "start_time": round(max(0.0, t - half_qrs), 4),
            "end_time":   round(min(duration, t + half_qrs), 4),
            "confidence": min(1.0, conf),
            "label": "QRS",
            "source": "auto",
            "algorithm": "scipy",
        })

    # P 波
    b_p, a_p = sp_signal.butter(4, [1.0 / nyq, 6.0 / nyq], btype="band")
    p_signal = sp_signal.filtfilt(b_p, a_p, sig)
    for pk in qrs_peaks:
        t = float(pk) / work_sr
        p_center = t - 0.16
        if p_center < 0.05:
            continue
        p_lo = max(0, int((p_center - 0.08) * work_sr))
        p_hi = min(len(p_signal), int((p_center + 0.08) * work_sr))
        seg = p_signal[p_lo:p_hi]
        if len(seg) < 3:
            continue
        local_peaks, _ = sp_signal.find_peaks(np.abs(seg), distance=len(seg) // 2)
        best = local_peaks[int(np.argmax(np.abs(seg[local_peaks])))] if len(local_peaks) > 0 else int(np.argmax(np.abs(seg)))
        p_t = (p_lo + best) / work_sr
        result.append({
            "annotation_type": "p_wave",
            "start_time": round(max(0.0, p_t - 0.04), 4),
            "end_time":   round(min(duration, p_t + 0.04), 4),
            "confidence": 0.65,
            "label": "P",
            "source": "auto",
            "algorithm": "scipy",
        })

    # T 波
    b_t, a_t = sp_signal.butter(4, 6.0 / nyq, btype="low")
    t_signal = sp_signal.filtfilt(b_t, a_t, sig)
    for i, pk in enumerate(qrs_peaks):
        t_qrs = float(pk) / work_sr
        rr = (float(qrs_peaks[i + 1]) - float(pk)) / work_sr if i + 1 < len(qrs_peaks) else 0.8
        t_center = t_qrs + min(0.40, rr * 0.38)
        if t_center > duration - 0.05:
            continue
        t_lo = max(0, int((t_center - 0.08) * work_sr))
        t_hi = min(len(t_signal), int((t_center + 0.10) * work_sr))
        seg = t_signal[t_lo:t_hi]
        if len(seg) < 3:
            continue
        best = int(np.argmax(np.abs(seg)))
        tv = (t_lo + best) / work_sr
        result.append({
            "annotation_type": "t_wave",
            "start_time": round(max(0.0, tv - 0.06), 4),
            "end_time":   round(min(duration, tv + 0.06), 4),
            "confidence": 0.65,
            "label": "T",
            "source": "auto",
            "algorithm": "scipy",
        })

    return result


def ecg_detect_neurokit2(sig: "np.ndarray", work_sr: int, duration: float) -> list:
    """NeuroKit2 ECG 全波形检测（P/Q/R/S/T）"""
    import numpy as np
    try:
        import neurokit2 as nk  # type: ignore

        # 1. R 峰检测
        signals, info = nk.ecg_process(sig, sampling_rate=work_sr)
        r_peaks = info["ECG_R_Peaks"]

        # 2. 波形细分（DWT 方法）
        _, delineate_info = nk.ecg_delineate(sig, rpeaks=r_peaks, sampling_rate=work_sr, method="dwt")

        result = []

        # R 峰
        for pk in r_peaks:
            t = float(pk) / work_sr
            result.append({
                "annotation_type": "qrs",
                "start_time": round(max(0.0, t - 0.05), 4),
                "end_time":   round(min(duration, t + 0.05), 4),
                "confidence": 0.92,
                "label": "QRS",
                "source": "auto",
                "algorithm": "neurokit2",
            })

        # P 波
        p_peaks = [int(x) for x in delineate_info.get("ECG_P_Peaks", []) if x == x]  # filter NaN
        for pk in p_peaks:
            t = float(pk) / work_sr
            result.append({
                "annotation_type": "p_wave",
                "start_time": round(max(0.0, t - 0.04), 4),
                "end_time":   round(min(duration, t + 0.04), 4),
                "confidence": 0.85,
                "label": "P",
                "source": "auto",
                "algorithm": "neurokit2",
            })

        # T 波
        t_peaks = [int(x) for x in delineate_info.get("ECG_T_Peaks", []) if x == x]
        for pk in t_peaks:
            t = float(pk) / work_sr
            result.append({
                "annotation_type": "t_wave",
                "start_time": round(max(0.0, t - 0.06), 4),
                "end_time":   round(min(duration, t + 0.06), 4),
                "confidence": 0.82,
                "label": "T",
                "source": "auto",
                "algorithm": "neurokit2",
            })

        # Q 峰
        q_peaks = [int(x) for x in delineate_info.get("ECG_Q_Peaks", []) if x == x]
        for pk in q_peaks:
            t = float(pk) / work_sr
            result.append({
                "annotation_type": "q_wave",
                "start_time": round(max(0.0, t - 0.02), 4),
                "end_time":   round(min(duration, t + 0.02), 4),
                "confidence": 0.80,
                "label": "Q",
                "source": "auto",
                "algorithm": "neurokit2",
            })

        # S 峰
        s_peaks = [int(x) for x in delineate_info.get("ECG_S_Peaks", []) if x == x]
        for pk in s_peaks:
            t = float(pk) / work_sr
            result.append({
                "annotation_type": "s_wave",
                "start_time": round(max(0.0, t - 0.02), 4),
                "end_time":   round(min(duration, t + 0.02), 4),
                "confidence": 0.80,
                "label": "S",
                "source": "auto",
                "algorithm": "neurokit2",
            })

        return result

    except Exception:
        return ecg_detect_scipy(sig, work_sr, duration)


def ecg_detect_wfdb(sig: "np.ndarray", work_sr: int, duration: float) -> list:
    """wfdb XQRS + scipy P/T 检测"""
    import numpy as np
    try:
        import wfdb.processing as wfdbp  # type: ignore

        r_peaks = wfdbp.xqrs_detect(sig=sig.astype(float), fs=work_sr, verbose=False)
        result = []
        for pk in r_peaks:
            t = float(pk) / work_sr
            result.append({
                "annotation_type": "qrs",
                "start_time": round(max(0.0, t - 0.05), 4),
                "end_time":   round(min(duration, t + 0.05), 4),
                "confidence": 0.90,
                "label": "QRS",
                "source": "auto",
                "algorithm": "wfdb",
            })

        # Reuse scipy for P/T waves based on XQRS R peaks
        from scipy import signal as sp_signal
        nyq = work_sr / 2.0

        b_p, a_p = sp_signal.butter(4, [1.0 / nyq, 6.0 / nyq], btype="band")
        p_signal = sp_signal.filtfilt(b_p, a_p, sig)
        for pk in r_peaks:
            t = float(pk) / work_sr
            p_center = t - 0.16
            if p_center < 0.05:
                continue
            p_lo = max(0, int((p_center - 0.08) * work_sr))
            p_hi = min(len(p_signal), int((p_center + 0.08) * work_sr))
            seg = p_signal[p_lo:p_hi]
            if len(seg) < 3:
                continue
            local_peaks, _ = sp_signal.find_peaks(np.abs(seg), distance=max(1, len(seg) // 2))
            best = local_peaks[int(np.argmax(np.abs(seg[local_peaks])))] if len(local_peaks) > 0 else int(np.argmax(np.abs(seg)))
            p_t = (p_lo + best) / work_sr
            result.append({
                "annotation_type": "p_wave",
                "start_time": round(max(0.0, p_t - 0.04), 4),
                "end_time":   round(min(duration, p_t + 0.04), 4),
                "confidence": 0.70,
                "label": "P",
                "source": "auto",
                "algorithm": "wfdb",
            })

        b_t, a_t = sp_signal.butter(4, 6.0 / nyq, btype="low")
        t_signal = sp_signal.filtfilt(b_t, a_t, sig)
        for i, pk in enumerate(r_peaks):
            t_qrs = float(pk) / work_sr
            rr = (float(r_peaks[i + 1]) - float(pk)) / work_sr if i + 1 < len(r_peaks) else 0.8
            t_center = t_qrs + min(0.40, rr * 0.38)
            if t_center > duration - 0.05:
                continue
            t_lo = max(0, int((t_center - 0.08) * work_sr))
            t_hi = min(len(t_signal), int((t_center + 0.10) * work_sr))
            seg = t_signal[t_lo:t_hi]
            if len(seg) < 3:
                continue
            best = int(np.argmax(np.abs(seg)))
            tv = (t_lo + best) / work_sr
            result.append({
                "annotation_type": "t_wave",
                "start_time": round(max(0.0, tv - 0.06), 4),
                "end_time":   round(min(duration, tv + 0.06), 4),
                "confidence": 0.70,
                "label": "T",
                "source": "auto",
                "algorithm": "wfdb",
            })

        return result
    except Exception:
        return ecg_detect_scipy(sig, work_sr, duration)

"""
模拟信号生成模块
POST /simulate/generate — 生成 ECG + PCG WAV 文件，写入数据库并自动检测标记
"""
from __future__ import annotations

import io
import math
import os
import uuid
import wave
from typing import List, Optional

import numpy as np
from scipy.signal import butter, sosfilt, resample_poly
from scipy.io import wavfile
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select

import app.models  # noqa: F401
from app.core.config import settings
from app.core.deps import CurrentActiveUser, DatabaseSession
from app.models.project import Annotation, MediaFile, Project

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────
ECG_SR = 500      # Hz
PCG_SR_DEFAULT = 4000   # Hz  (低质量，兼容模式)
PCG_SR = 4000           # 运行时由 req.pcg_sample_rate 覆盖

# 听诊器频响建模：20-800Hz 主通带，胸壁低频共鸣 20-120Hz
_STETHO_LO  = 20.0    # Hz  低截止
_STETHO_HI  = 800.0   # Hz  高截止（贝尔型听诊器约到 1kHz，普通膜型约 800Hz）
_STETHO_RES = 80.0    # Hz  胸壁/听诊器共鸣峰

# ─────────────────────────────────────────────────────────────────────────────
# Request / Response schemas
# ─────────────────────────────────────────────────────────────────────────────

class SimulateRequest(BaseModel):
    # ── project ──────────────────────────────────────────────────────────────
    project_id: str = Field(..., description="文件写入的项目 ID")

    # ── ECG ──────────────────────────────────────────────────────────────────
    ecg_rhythm: str = Field(
        default="normal",
        description=(
            "心律类型: normal | tachycardia | bradycardia | sinus_arrhythmia"
            " | af | pvc | svt | vt | ron_t"
        ),
    )
    heart_rate: float = Field(default=72.0, ge=30, le=300, description="平均心率 (bpm)")
    heart_rate_std: float = Field(default=2.0, ge=0, le=50, description="心率标准差，控制节律变异性")
    pvc_ratio: float = Field(default=0.15, ge=0, le=0.5, description="PVC 比例 (0~0.5)")
    noise_level: float = Field(default=0.01, ge=0, le=0.5, description="ECG 噪声幅度")
    duration: float = Field(default=10.0, ge=3, le=300, description="信号时长（秒）")
    # ── R-on-T 专用参数 ──────────────────────────────────────────────────
    ron_t_vt_probability: float = Field(
        default=0.6, ge=0, le=1.0,
        description="R-on-T 触发 VT/VF 的概率 (0=从不, 1=必然)",
    )
    ron_t_vf_ratio: float = Field(
        default=0.4, ge=0, le=1.0,
        description="触发的恶性心律中 VF 的比例 (0=全VT, 1=全VF)",
    )

    # ── PCG ──────────────────────────────────────────────────────────────────
    generate_pcg: bool = Field(default=True, description="是否同时生成 PCG 心音")
    pcg_abnormalities: List[str] = Field(
        default=[],
        description=(
            "PCG 异常: [] | murmur_systolic | murmur_diastolic"
            " | split_s2 | s3_gallop | s4_gallop"
        ),
    )
    pcg_sample_rate: int = Field(
        default=4000,
        description="PCG 采样率 Hz: 4000 | 8000 | 16000 | 44100 | 48000",
    )
    stethoscope_mode: bool = Field(
        default=True,
        description=(
            "听诊器模式：启用后对 PCG 进行频响塑形（20-800Hz 通带 + 低频共鸣），"
            "使音频听起来像从听诊器中听到"
        ),
    )
    pcg_noise_level: float = Field(default=0.003, ge=0, le=0.1, description="PCG 背景噪声幅度（建议 ≤0.01）")
    s1_amplitude: float = Field(default=1.0, ge=0.1, le=3.0, description="S1 音幅度系数")
    s2_amplitude: float = Field(default=0.7, ge=0.1, le=3.0, description="S2 音幅度系数")
    exercise_intensity: float = Field(
        default=0.0, ge=0.0, le=1.0,
        description=(
            "运动强度 (0=静息, 1=剧烈运动)。"
            "增加低频运动伪影(5-18Hz)、皮肤摩擦噪声(100-500Hz)、心音幅度呼吸调制强度。"
        ),
    )

    # ── 公共 ──────────────────────────────────────────────────────────────────
    random_seed: Optional[int] = Field(default=None, description="随机种子，None 为随机")
    auto_detect: bool = Field(default=True, description="生成后自动运行标记检测")


class SimulateResult(BaseModel):
    ecg_file_id: str
    ecg_filename: str
    pcg_file_id: Optional[str] = None
    pcg_filename: Optional[str] = None
    duration: float
    heart_rate: float
    rhythm: str
    r_peak_count: int
    ecg_annotation_count: int
    pcg_annotation_count: int
    association_id: Optional[str] = None  # 自动创建的关联 ID


# ─────────────────────────────────────────────────────────────────────────────
# ECG synthesis  (v2 — 高精度改造)
#
# 精度改进:
#   1. 正常/中等心率 (≤180bpm): 直接使用 neurokit2 ecgsyn 引擎（基于 MIT ECGSYN 模型）
#   2. 高心率/异常心律: 使用改进的模板叠加:
#      - 心率自适应 QT 间期 (Bazett 公式)
#      - 逐拍形态微变异 (amplitude jitter + timing jitter)
#      - P 波 / T 波随心率自适应缩放
#   3. 通用增强:
#      - 呼吸性基线漂移 (0.15-0.3Hz 正弦)
#      - 可选 50Hz 工频干扰
#      - AF 纤颤波 (f-wave)
#      - 改进的 PVC 宽 QRS 形态
# ─────────────────────────────────────────────────────────────────────────────

# neurokit2 ecgsyn 能正确生成的最高心率
_ECGSYN_HR_MAX = 180


def _build_beat_template(sr: int = ECG_SR, heart_rate: float = 72.0) -> tuple[np.ndarray, int]:
    """
    构建单拍 PQRST 模板。
    根据心率调整 QT 间期 (Bazett) 和 P-R 间期。
    流程: neurokit2 截取 → baseline detrend → HR adapt → wave amplitude normalization → edge fade
    """
    try:
        import neurokit2 as nk
        ecg_ref = nk.ecg_simulate(duration=15, sampling_rate=sr, heart_rate=60, noise=0, method="ecgsyn")
        _, info = nk.ecg_process(ecg_ref, sampling_rate=sr)
        peaks = info["ECG_R_Peaks"]
        if len(peaks) < 3:
            raise ValueError("peaks too few")
        rp = peaks[len(peaks) // 2]
        pre = int(0.25 * sr)
        post = int(0.55 * sr)
        template = ecg_ref[rp - pre : rp + post].astype(np.float32)
        template = _detrend_template_baseline(template, r_offset=pre)
        # 根据目标心率调整 QT 间期 (Bazett: QTc = QT / sqrt(RR))
        template, pre = _adapt_template_to_hr(template, pre, sr, heart_rate)
        template = _normalize_wave_amplitudes(template, pre, sr)
        template = _fade_template_edges(template, sr=sr)
        return template, pre
    except Exception:
        template, pre = _synthetic_template(sr)
        adapted, pre = _adapt_template_to_hr(template, pre, sr, heart_rate)
        adapted = _normalize_wave_amplitudes(adapted, pre, sr)
        adapted = _fade_template_edges(adapted, sr=sr)
        return adapted, pre


def _detrend_template_baseline(template: np.ndarray, r_offset: int = -1) -> np.ndarray:
    """
    对模板做 iso-electric baseline 归零。

    策略：用 TP 段（P 波 onset 之前 + T 波尾之后的等电位区域）
    的中位数作为统一 baseline 减去，保留 PQRST 各波的相对幅度比例。

    旧的线性 detrend 会不均匀地扭曲 P/T/R 波幅度比（R 峰附近减更多，
    尾端减更少），导致 T 波相对偏高、P 波相对偏低。
    """
    n = len(template)
    if n < 20:
        return template

    # TP 段 = P 波 onset 之前 + T 波 return-to-baseline 之后
    # 这两段在正常 ECG 中应处于等电位线（≈0mV）
    # P 波 onset 约在 R 峰前 200ms，T 波结束约在 R 峰后 400ms
    if r_offset < 0:
        r_offset = n // 3  # 粗略估计

    # 首段 TP: 模板开头 15% 或 R 峰前 200ms+ 区域
    tp_head_end = max(3, min(r_offset - int(0.20 * 500), int(n * 0.08)))
    # 尾段 TP: 模板结尾 10%
    tp_tail_start = max(r_offset + int(0.42 * 500), int(n * 0.90))

    # 收集 TP 段样本
    tp_samples = []
    if tp_head_end > 0:
        tp_samples.extend(template[:tp_head_end].tolist())
    if tp_tail_start < n:
        tp_samples.extend(template[tp_tail_start:].tolist())

    if len(tp_samples) < 3:
        # 无法可靠估计，用首尾各5个均值的中点
        baseline = (float(np.mean(template[:5])) + float(np.mean(template[-5:]))) / 2
    else:
        baseline = float(np.median(tp_samples))

    return template - baseline


def _normalize_wave_amplitudes(
    template: np.ndarray,
    r_offset: int,
    sr: int,
    *,
    target_t_r_ratio: float = 0.25,
    max_p_r_ratio: float = 0.15,
) -> np.ndarray:
    """
    校正模板中 T 波和 P 波的幅度到临床正常范围。

    neurokit2 ECGSYN 生成的 T 波偏高（T/R ≈ 0.37-0.42），临床正常范围
    T/R 应在 0.15-0.30。P 波也可能偏高（P/R > 0.15）。

    方法：
    - 定位 T 波段（R 峰后 100-400ms），如果 T/R 超过目标值，
      对 T 波段施加衰减因子，同时在 ST-T 交界处平滑过渡
    - 定位 P 波段（R 峰前 60-200ms），如果 P/R 超过目标值，
      对 P 波段施加衰减因子
    """
    n = len(template)
    result = template.copy()

    # R 峰值
    r_peak = template[r_offset]
    if r_peak <= 0.01:
        return result  # 模板异常，不处理

    # ── T 波校正 ──────────────────────────────────────────────
    # T 波大约在 R 峰后 100-400ms
    t_start = min(n, r_offset + int(0.08 * sr))
    t_end = min(n, r_offset + int(0.42 * sr))
    if t_end > t_start + 5:
        t_region = result[t_start:t_end]
        t_peak = float(np.max(t_region))
        t_ratio = t_peak / r_peak

        if t_ratio > target_t_r_ratio:
            # 需要衰减 T 波
            # 衰减因子使 T 波 peak 降到 target_t_r_ratio * R peak
            attenuation = target_t_r_ratio / t_ratio

            # 构造平滑过渡窗：从 1.0 过渡到 attenuation
            # ST 段 (R 峰后 60-100ms) 保持不变，T 波段逐渐衰减
            st_end = min(n, r_offset + int(0.10 * sr))
            transition = max(1, st_end - t_start)
            t_len = t_end - t_start

            # 建造衰减 mask: [1.0 → attenuation] 在前 transition 段，
            # 然后保持 attenuation 到末尾，最后回到 1.0
            mask = np.ones(t_len, dtype=np.float32)
            # 过渡段：从 1.0 cosine 过渡到 attenuation
            if transition > 0 and transition < t_len:
                fade = 0.5 * (1.0 + np.cos(np.linspace(0, np.pi, transition)))
                mask[:transition] = attenuation + (1.0 - attenuation) * fade.astype(np.float32)
                mask[transition:] = attenuation
            else:
                mask[:] = attenuation

            # 尾端回升：最后 15% 从 attenuation 回到 1.0（避免突变）
            tail_len = max(2, int(t_len * 0.15))
            tail_fade = 0.5 * (1.0 - np.cos(np.linspace(0, np.pi, tail_len)))
            mask[-tail_len:] = attenuation + (1.0 - attenuation) * tail_fade.astype(np.float32)

            result[t_start:t_end] *= mask

    # ── P 波校正 ──────────────────────────────────────────────
    # P 波大约在 R 峰前 60-200ms
    p_start = max(0, r_offset - int(0.22 * sr))
    p_end = max(0, r_offset - int(0.04 * sr))
    if p_end > p_start + 3:
        p_region = result[p_start:p_end]
        p_peak = float(np.max(np.abs(p_region)))
        p_ratio = p_peak / r_peak

        if p_ratio > max_p_r_ratio:
            attenuation = max_p_r_ratio / p_ratio
            p_len = p_end - p_start

            # 对 P 波区域施加衰减，两端平滑过渡
            mask = np.ones(p_len, dtype=np.float32)
            edge = max(2, int(p_len * 0.15))
            # 前端过渡
            mask[:edge] = 1.0 - (1.0 - attenuation) * (
                0.5 * (1.0 - np.cos(np.linspace(0, np.pi, edge)))
            ).astype(np.float32)
            # 中段
            mask[edge:-edge] = attenuation
            # 后端过渡
            mask[-edge:] = attenuation + (1.0 - attenuation) * (
                0.5 * (1.0 - np.cos(np.linspace(0, np.pi, edge)))
            ).astype(np.float32)

            result[p_start:p_end] *= mask

    return result


def _fade_template_edges(template: np.ndarray, fade_ms: float = 15.0, sr: int = ECG_SR) -> np.ndarray:
    """
    对模板首尾施加 cosine fade-in/fade-out，确保两端平滑归零。

    这解决两个问题：
    1. neurokit2 截取的模板首尾可能包含上一拍 T 波尾/下一拍 P 波起始的残余
    2. 逐拍拼接时，模板边缘非零会造成前一拍末端和下一拍开头的突变
    """
    fade_samples = max(2, int(fade_ms * sr / 1000.0))
    n = len(template)
    if n < fade_samples * 2 + 10:
        return template  # 模板太短，不处理

    result = template.copy()

    # fade-in: 前 fade_samples 用 cosine 从 0 上升到 1
    fade_in = 0.5 * (1.0 - np.cos(np.linspace(0, np.pi, fade_samples)))
    result[:fade_samples] *= fade_in.astype(np.float32)

    # fade-out: 后 fade_samples 用 cosine 从 1 下降到 0
    fade_out = 0.5 * (1.0 + np.cos(np.linspace(0, np.pi, fade_samples)))
    result[-fade_samples:] *= fade_out.astype(np.float32)

    return result


def _adapt_template_to_hr(
    template: np.ndarray, r_offset: int, sr: int, hr: float,
) -> tuple[np.ndarray, int]:
    """
    根据心率调整模板的 QT 间期和 P-R 间期。
    返回 (adapted_template, new_r_offset)。
    """
    rr = 60.0 / max(hr, 30)  # RR 间期(秒)

    # Bazett 公式: QTc ≈ 0.40s (正常), QT = QTc * sqrt(RR)
    qt_factor = np.sqrt(rr) / np.sqrt(1.0)  # 参考 60bpm (RR=1s)
    qt_factor = np.clip(qt_factor, 0.6, 1.3)

    # ST-T 段在 R 峰之后 — 对后半段做时间缩放
    n_pre = r_offset
    n_post = len(template) - r_offset
    post_part = template[r_offset:]
    new_post_len = max(int(n_post * qt_factor), 10)
    post_scaled = np.interp(
        np.linspace(0, n_post - 1, new_post_len),
        np.arange(n_post),
        post_part,
    ).astype(np.float32)

    # P-R 间期：快心率时 P-R 缩短
    pr_factor = np.clip(0.7 + 0.3 * rr, 0.6, 1.1)
    pre_part = template[:r_offset]
    new_pre_len = max(int(n_pre * pr_factor), 10)
    pre_scaled = np.interp(
        np.linspace(0, n_pre - 1, new_pre_len),
        np.arange(n_pre),
        pre_part,
    ).astype(np.float32)

    return np.concatenate([pre_scaled, post_scaled]), new_pre_len


def _synthetic_template(sr: int = ECG_SR) -> tuple[np.ndarray, int]:
    """纯数学合成 PQRST 模板（fallback）— 改进版。"""
    pre = int(0.25 * sr)
    post = int(0.55 * sr)
    n = pre + post
    t = np.linspace(-pre / sr, post / sr, n)

    def gauss(t, mu, sig, amp):
        return amp * np.exp(-((t - mu) ** 2) / (2 * sig**2))

    template = (
        gauss(t, -0.12, 0.038, 0.10)   # P wave (atrial depol, σ=38ms → ~90ms FWHM, smooth dome)
        + gauss(t, -0.09, 0.028, 0.05)  # P wave tail (gradual offset)
        + gauss(t, -0.015, 0.005, -0.12) # Q deflection
        + gauss(t, 0.0,  0.004, 1.2)    # R peak (sharp)
        + gauss(t, 0.012, 0.005, -0.20)  # S deflection
        + gauss(t, 0.03, 0.008, -0.03)   # J-point
        + gauss(t, 0.16, 0.035, 0.22)    # T wave (ventricular repolarization)
        + gauss(t, 0.19, 0.030, 0.08)    # T wave tail
    )
    return template.astype(np.float32), pre


def _parametric_template(
    sr: int,
    *,
    pr_interval_ms: float = 160.0,
    qrs_duration_ms: float = 90.0,
    p_wave_present: bool = True,
    p_wave_retrograde: bool = False,
    heart_rate: float = 72.0,
) -> tuple[np.ndarray, int]:
    """
    参数化 PQRST 模板生成器 — 受传导事件驱动。

    模板长度根据心率自适应：高心率时模板更紧凑，确保 T 波/P 波
    在 RR 间期内合理分布，不会产生过长的空白尾部。

    参数:
        sr: 采样率 (Hz)
        pr_interval_ms: PR 间期 (ms)，控制 P 波到 QRS 的距离
        qrs_duration_ms: QRS 时限 (ms)，控制 QRS 宽度
        p_wave_present: 是否生成 P 波（AF 时为 False）
        p_wave_retrograde: 逆行 P 波（SVT 特征，P 波倒置且在 QRS 之后）
        heart_rate: 心率 (bpm)，用于 Bazett QT 计算和模板长度

    返回:
        (template, r_offset) — 模板数组和 R 峰在模板中的位置索引
    """
    rr_sec = 60.0 / max(heart_rate, 30.0)

    # ── 模板长度根据 RR 间期自适应 ──────────────────────────────
    # R 峰前时长：取 RR 的 25% 与 0.25s 中较小者（高 HR 时缩短）
    pre_sec = min(0.25, rr_sec * 0.25)
    # R 峰后时长：取 RR 的 75% 与 0.55s 中较小者
    post_sec = min(0.55, rr_sec * 0.75)
    # 确保最低时长
    pre_sec = max(0.06, pre_sec)
    post_sec = max(0.12, post_sec)

    r_off = int(round(pre_sec * sr))
    post_samples = int(round(post_sec * sr))
    n = r_off + post_samples
    t = np.linspace(-pre_sec, post_sec, n)

    def gauss(center: float, width: float, amp: float) -> np.ndarray:
        return amp * np.exp(-((t - center) ** 2) / (2 * width**2))

    template = np.zeros(n, dtype=np.float64)

    # ── P 波 ────────────────────────────────────────────────────
    if p_wave_present:
        if p_wave_retrograde:
            p_center = 0.05
            template += gauss(p_center, 0.018, -0.12)
            template += gauss(p_center + 0.015, 0.012, -0.06)
        else:
            pr_sec = pr_interval_ms / 1000.0
            p_center = -(pr_sec - 0.040)
            p_center = max(-pre_sec + 0.02, min(-0.04, p_center))
            # 高心率时 P 波稍窄
            p_width = min(0.038, rr_sec * 0.06)
            p_width = max(0.015, p_width)
            template += gauss(p_center, p_width, 0.10)
            template += gauss(p_center + 0.03 * min(1.0, rr_sec), 0.028 * min(1.0, rr_sec / 0.6), 0.05)

    # ── QRS 复合波 ──────────────────────────────────────────────
    qrs_scale = qrs_duration_ms / 90.0
    template += gauss(-0.015 * qrs_scale, 0.005 * qrs_scale, -0.12)  # Q
    template += gauss(0.0, 0.004 * qrs_scale, 1.2)                    # R
    template += gauss(0.012 * qrs_scale, 0.005 * qrs_scale, -0.20)    # S
    template += gauss(0.03 * qrs_scale, 0.008 * qrs_scale, -0.03)     # J-point

    # ── T 波 ────────────────────────────────────────────────────
    # Bazett 公式：QT = 400ms * sqrt(RR_sec)
    qt_ms = 400.0 * math.sqrt(rr_sec)
    qt_sec = qt_ms / 1000.0
    # T 波中心 ≈ QT * 0.55
    t_center = qt_sec * 0.55
    t_center = max(0.08, min(post_sec - 0.04, t_center))
    # 高心率时 T 波更窄更紧凑
    t_width = min(0.035, rr_sec * 0.055)
    t_width = max(0.015, t_width)
    t_tail_width = min(0.030, rr_sec * 0.045)
    t_tail_width = max(0.012, t_tail_width)
    template += gauss(t_center, t_width, 0.22)
    template += gauss(t_center + t_tail_width, t_tail_width, 0.08)

    # ── 后处理 ──────────────────────────────────────────────────
    template = template.astype(np.float32)
    template = _normalize_wave_amplitudes(template, r_off, sr)
    template = _fade_template_edges(template, sr=sr)

    return template, r_off


def _af_r_peaks(duration: float, mean_hr: float, sr: int, rng: np.random.Generator) -> np.ndarray:
    """房颤：RR 间期服从指数分布（高变异性）。"""
    n_est = int(duration * mean_hr / 60 * 4)
    rr_sec = rng.exponential(scale=60.0 / mean_hr, size=n_est)
    rr_sec = np.clip(rr_sec, 60.0 / 300, 60.0 / 25)  # 25~300 bpm
    r_locs = np.cumsum(np.round(rr_sec * sr).astype(int))
    r_locs = r_locs[r_locs < int(duration * sr) - 1]
    return r_locs.astype(int)


def _regular_r_peaks(
    duration: float, hr: float, hr_std: float, sr: int, rng: np.random.Generator
) -> np.ndarray:
    """规则节律 R-peak 位置（窦性/SVT/VT 等）。"""
    n_est = int(duration * hr / 60 * 3)
    base_rr = 60.0 / hr
    rr_sec = rng.normal(base_rr, base_rr * hr_std / hr, n_est)
    rr_sec = np.clip(rr_sec, 60.0 / 300, 60.0 / 25)
    r_locs = np.cumsum(np.round(rr_sec * sr).astype(int))
    r_locs = r_locs[r_locs < int(duration * sr) - 1]
    return r_locs.astype(int)


def _synthesize_ecg(
    r_peaks: np.ndarray,
    duration: float,
    sr: int,
    noise: float,
    heart_rate: float = 72.0,
    pvc_indices: Optional[set] = None,
    vt_mode: bool = False,
    af_mode: bool = False,
    rng: Optional[np.random.Generator] = None,
) -> np.ndarray:
    """
    按 R-peak 序列合成高精度 ECG。

    改进:
    - 心率自适应模板 (QT/PR 间期随 RR 变化)
    - 逐拍形态微变异 (±5% 幅度 + ±2ms 时间抖动)
    - 呼吸性基线漂移 (0.15-0.3Hz)
    - AF 纤颤波 (f-wave)
    - 改进的 PVC/VT 形态
    """
    rng = rng or np.random.default_rng()
    template, r_off = _build_beat_template(sr, heart_rate)
    pvc_set = set(pvc_indices or [])
    total = int(duration * sr)

    # 初始化: 基线噪声
    sig = rng.normal(0, max(noise, 1e-6), total).astype(np.float32)

    # ── 呼吸性基线漂移 (0.15-0.3Hz 正弦) ──────────────────────────
    resp_freq = rng.uniform(0.15, 0.30)
    resp_phase = rng.uniform(0, 2 * np.pi)
    t_axis = np.arange(total, dtype=np.float32) / sr
    baseline_drift = 0.05 * np.sin(2 * np.pi * resp_freq * t_axis + resp_phase)
    # 加入超低频漂移 (模拟电极运动)
    drift_freq2 = rng.uniform(0.02, 0.08)
    baseline_drift += 0.03 * np.sin(2 * np.pi * drift_freq2 * t_axis + rng.uniform(0, 2 * np.pi))
    sig += baseline_drift.astype(np.float32)

    # ── AF 纤颤波 (f-wave) ─────────────────────────────────────────
    if af_mode:
        # 叠加 3-8Hz 不规则小波模拟心房纤颤
        for _ in range(4):
            f_freq = rng.uniform(3.0, 8.0)
            f_amp = rng.uniform(0.02, 0.06)
            f_phase = rng.uniform(0, 2 * np.pi)
            sig += (f_amp * np.sin(2 * np.pi * f_freq * t_axis + f_phase)).astype(np.float32)

    # ── VT/SVT 模板: 宽 QRS + 形态改变 ────────────────────────────
    if vt_mode:
        vt_template = np.interp(
            np.linspace(0, len(template) - 1, int(len(template) * 1.4)),
            np.arange(len(template)),
            template,
        ).astype(np.float32)
        # 抑制 P 波、增大 QRS、反转 T 波
        p_end = int(len(vt_template) * 0.25)
        vt_template[:p_end] *= 0.05  # 几乎无 P 波
        t_start = int(len(vt_template) * 0.55)
        vt_template[t_start:] *= -0.8  # T 波反转
        vt_template *= 1.3  # 整体增大
    else:
        vt_template = None

    # ── PVC 模板: 宽 QRS + 深倒 T + 无 P 波 ──────────────────────
    pvc_template_base = np.interp(
        np.linspace(0, len(template) - 1, int(len(template) * 1.5)),
        np.arange(len(template)),
        template,
    ).astype(np.float32)
    # 抑制 P 波
    pvc_p_end = int(len(pvc_template_base) * 0.2)
    pvc_template_base[:pvc_p_end] *= 0.05
    # QRS 增宽 + 反向
    pvc_r_off = int(r_off * 1.5)
    qrs_zone = slice(max(0, pvc_r_off - int(0.06 * sr)), min(len(pvc_template_base), pvc_r_off + int(0.06 * sr)))
    pvc_template_base[qrs_zone] *= -1.4
    # T 波反转
    pvc_t_start = int(len(pvc_template_base) * 0.5)
    pvc_template_base[pvc_t_start:] *= -1.2

    # ── 逐拍叠加 ──────────────────────────────────────────────────
    for i, rp in enumerate(r_peaks):
        # 选择模板
        if vt_mode and vt_template is not None:
            t = vt_template
            off = int(r_off * 1.4)
        elif i in pvc_set:
            t = pvc_template_base
            off = pvc_r_off
        else:
            t = template
            off = r_off

        # ── 逐拍形态变异 ──────────────────────────────────────────
        # 幅度抖动 ±5%
        amp_jitter = 1.0 + rng.normal(0, 0.05)
        beat = t * amp_jitter

        # 呼吸调制: 吸气时幅度略增 (呼吸性窦性心律不齐的视觉效果)
        resp_mod = 1.0 + 0.04 * np.sin(2 * np.pi * resp_freq * (int(rp) / sr) + resp_phase)
        beat = beat * resp_mod

        # 时间抖动 ±2 samples (±4ms at 500Hz)
        time_jitter = rng.integers(-2, 3)
        rp_adj = int(rp) + time_jitter

        start = rp_adj - off
        end = start + len(beat)

        # 边界截取（而非跳过）：处理首尾拍可能超出信号范围的情况
        tpl_s = 0
        if start < 0:
            tpl_s = -start
            start = 0
        tpl_e = len(beat)
        if end > total:
            tpl_e -= (end - total)
            end = total
        if start < end and tpl_s < tpl_e:
            sig[start:end] += beat[tpl_s:tpl_e]

    return sig


# ─────────────────────────────────────────────────────────────────────────────
# VF (Ventricular Fibrillation) synthesis
# ─────────────────────────────────────────────────────────────────────────────

def _synthesize_vf(duration_sec: float, sr: int, rng: np.random.Generator) -> np.ndarray:
    """
    合成室颤 (VF) 波形 — 完全无序、无可辨识 QRS 的混沌波形。
    由多个随机频率（3-10Hz）正弦叠加 + 幅度包络衰减模拟。
    """
    total = int(duration_sec * sr)
    t = np.arange(total, dtype=np.float32) / sr
    sig = np.zeros(total, dtype=np.float32)

    # 叠加 6-10 个随机频率分量模拟混沌电活动
    n_components = rng.integers(6, 11)
    for _ in range(n_components):
        freq = rng.uniform(3.0, 10.0)       # VF 主频 3-10Hz
        amp = rng.uniform(0.15, 0.5)
        phase = rng.uniform(0, 2 * np.pi)
        # 频率随时间微漂移
        freq_drift = rng.uniform(-0.5, 0.5)
        inst_freq = freq + freq_drift * t / max(duration_sec, 1)
        sig += (amp * np.sin(2 * np.pi * inst_freq * t + phase)).astype(np.float32)

    # 幅度包络：VF 通常从粗颤逐渐变为细颤（幅度衰减）
    envelope = np.exp(-0.3 * t / max(duration_sec, 1))
    envelope *= (1.0 + 0.3 * np.sin(2 * np.pi * rng.uniform(0.2, 0.8) * t)).astype(np.float32)
    sig *= envelope.astype(np.float32)

    sig += rng.normal(0, 0.03, total).astype(np.float32)
    return sig


def _synthesize_vt_burst(duration_sec: float, sr: int, hr: float,
                         rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray]:
    """
    合成一段室速 (VT) 爆发。
    返回 (signal, r_peaks_within_burst)。
    """
    total = int(duration_sec * sr)
    vt_hr = max(hr, rng.uniform(160, 220))
    r_peaks = _regular_r_peaks(duration_sec, vt_hr, vt_hr * 0.02, sr, rng)

    template, r_off = _build_beat_template(sr, vt_hr)
    vt_template = np.interp(
        np.linspace(0, len(template) - 1, int(len(template) * 1.4)),
        np.arange(len(template)), template,
    ).astype(np.float32)
    p_end = int(len(vt_template) * 0.25)
    vt_template[:p_end] *= 0.05
    t_start = int(len(vt_template) * 0.55)
    vt_template[t_start:] *= -0.8
    vt_template *= 1.3
    vt_r_off = int(r_off * 1.4)

    sig = rng.normal(0, 0.005, total).astype(np.float32)
    for rp in r_peaks:
        beat = vt_template * (1.0 + rng.normal(0, 0.03))
        start = int(rp) - vt_r_off
        end = start + len(beat)
        if start >= 0 and end <= total:
            sig[start:end] += beat
    return sig, r_peaks


# ─────────────────────────────────────────────────────────────────────────────
# R-on-T phenomenon → VT / VF
# ─────────────────────────────────────────────────────────────────────────────

def _simulate_ron_t(req: SimulateRequest, rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray, list[dict]]:
    """
    模拟 R-on-T 现象：

    T 波后半段（QT 的 70-100%）是心室"易损期"(vulnerable period)。
    PVC 恰好落在此窗口 = R-on-T，可触发 VT 或 VF。

    信号结构:
      [正常窦律] → [R-on-T PVC] → [概率触发 VT 或 VF] → [可能恢复窦律]

    返回 (signal, all_r_peaks, event_annotations)
    """
    import neurokit2 as nk

    sr = ECG_SR
    hr = req.heart_rate
    dur = req.duration
    noise = req.noise_level
    total = int(dur * sr)
    sig = np.zeros(total, dtype=np.float32)
    all_r_peaks: list[int] = []
    events: list[dict] = []

    # ── 阶段 1: 正常窦律 (40-60% 时长) ─────────────────────────
    normal_dur = max(dur * rng.uniform(0.40, 0.60), 2.0)
    try:
        normal_sig = np.asarray(nk.ecg_simulate(
            duration=normal_dur + 1, sampling_rate=sr, heart_rate=hr,
            heart_rate_std=req.heart_rate_std, noise=noise, method="ecgsyn",
            random_state=rng.integers(0, 2**31),
        ), dtype=np.float32)
        _, info = nk.ecg_process(normal_sig, sampling_rate=sr)
        normal_peaks = np.array(info["ECG_R_Peaks"], dtype=int)
    except Exception:
        normal_peaks = _regular_r_peaks(normal_dur, hr, req.heart_rate_std, sr, rng)
        normal_sig = _synthesize_ecg(normal_peaks, normal_dur + 1, sr, noise, heart_rate=hr, rng=rng)

    n_normal = min(int(normal_dur * sr), len(normal_sig), total)
    sig[:n_normal] = normal_sig[:n_normal]
    normal_peaks = normal_peaks[normal_peaks < n_normal]
    all_r_peaks.extend(normal_peaks.tolist())

    if len(normal_peaks) < 2:
        return sig, np.array(all_r_peaks, dtype=int), events

    # ── 阶段 2: R-on-T PVC ────────────────────────────────────
    last_rp = normal_peaks[-1]
    rr = 60.0 / hr
    qt = 0.40 * np.sqrt(rr)
    vuln_start = last_rp + int(qt * 0.70 * sr)
    vuln_end = last_rp + int(qt * 1.00 * sr)
    ron_t_sample = rng.integers(vuln_start, max(vuln_start + 1, vuln_end))

    if ron_t_sample >= total:
        return sig, np.array(all_r_peaks, dtype=int), events

    # PVC 模板
    template, r_off = _build_beat_template(sr, hr)
    pvc_len = int(len(template) * 1.5)
    pvc_t = np.interp(np.linspace(0, len(template) - 1, pvc_len),
                       np.arange(len(template)), template).astype(np.float32)
    pvc_r_off = int(r_off * 1.5)
    pvc_t[:int(pvc_len * 0.2)] *= 0.05
    qrs_w = int(0.06 * sr)
    pvc_t[max(0, pvc_r_off - qrs_w):min(pvc_len, pvc_r_off + qrs_w)] *= -1.5
    pvc_t[int(pvc_len * 0.5):] *= -1.3
    pvc_t *= 1.2

    ps = ron_t_sample - pvc_r_off
    pe = ps + len(pvc_t)
    if ps >= 0 and pe <= total:
        sig[ps:pe] += pvc_t
    all_r_peaks.append(int(ron_t_sample))

    ron_t_time = ron_t_sample / sr
    events.append({
        "annotation_type": "ron_t",
        "start_time": round(ron_t_time - 0.05, 4),
        "end_time": round(ron_t_time + 0.10, 4),
        "confidence": 0.95, "label": "R-on-T PVC", "source": "simulated",
        "annotation_metadata": {"algorithm": "simulate", "event": "ron_t",
                                "vulnerable_period_ms": round((vuln_end - vuln_start) / sr * 1000, 1)},
    })

    # ── 阶段 3: 概率触发 VT / VF ──────────────────────────────
    trans = pe
    remaining = (total - trans) / sr if trans < total else 0

    if rng.random() < req.ron_t_vt_probability and remaining > 0.5:
        is_vf = rng.random() < req.ron_t_vf_ratio

        if is_vf:
            # 短暂 VT 过渡 → VF
            vt_pre = min(rng.uniform(0.5, 2.0), remaining * 0.3)
            if vt_pre > 0.3 and trans < total:
                vt_seg, vt_pks = _synthesize_vt_burst(vt_pre, sr, hr, rng)
                n = min(len(vt_seg), total - trans)
                fade = min(int(0.05 * sr), n)
                if fade > 1:
                    ramp = np.linspace(0, 1, fade, dtype=np.float32)
                    sig[trans:trans + fade] *= (1 - ramp)
                    vt_seg[:fade] *= ramp
                sig[trans:trans + n] += vt_seg[:n]
                all_r_peaks.extend((vt_pks[vt_pks < n] + trans).tolist())
                events.append({
                    "annotation_type": "vt", "start_time": round(trans / sr, 4),
                    "end_time": round((trans + n) / sr, 4), "confidence": 0.90,
                    "label": "VT → VF 过渡", "source": "simulated",
                    "annotation_metadata": {"algorithm": "simulate", "event": "vt_transition", "triggered_by": "ron_t"},
                })
                trans += int(vt_pre * sr)

            vf_dur = (total - trans) / sr if trans < total else 0
            if vf_dur > 0.2:
                vf_seg = _synthesize_vf(vf_dur + 0.5, sr, rng)
                n = min(len(vf_seg), total - trans)
                fade = min(int(0.05 * sr), n)
                if fade > 1:
                    ramp = np.linspace(0, 1, fade, dtype=np.float32)
                    sig[trans:trans + fade] *= (1 - ramp)
                    vf_seg[:fade] *= ramp
                sig[trans:trans + n] += vf_seg[:n]
                events.append({
                    "annotation_type": "vf", "start_time": round(trans / sr, 4),
                    "end_time": round(min(dur, (trans + n) / sr), 4), "confidence": 0.92,
                    "label": "VF 室颤", "source": "simulated",
                    "annotation_metadata": {"algorithm": "simulate", "event": "vf", "triggered_by": "ron_t"},
                })
        else:
            # 持续 VT（可能恢复）
            vt_dur = min(rng.uniform(2.0, 6.0), remaining)
            vt_seg, vt_pks = _synthesize_vt_burst(vt_dur + 0.5, sr, hr, rng)
            n = min(len(vt_seg), total - trans)
            fade = min(int(0.05 * sr), n)
            if fade > 1:
                ramp = np.linspace(0, 1, fade, dtype=np.float32)
                sig[trans:trans + fade] *= (1 - ramp)
                vt_seg[:fade] *= ramp
            sig[trans:trans + n] = vt_seg[:n]
            all_r_peaks.extend((vt_pks[vt_pks < n] + trans).tolist())
            events.append({
                "annotation_type": "vt", "start_time": round(trans / sr, 4),
                "end_time": round((trans + n) / sr, 4), "confidence": 0.92,
                "label": "VT 室速", "source": "simulated",
                "annotation_metadata": {"algorithm": "simulate", "event": "vt", "triggered_by": "ron_t"},
            })

            # 50% 概率恢复窦律
            rec_start = trans + n
            if rec_start < total and rng.random() < 0.5:
                rec_dur = (total - rec_start) / sr
                if rec_dur > 1.0:
                    try:
                        rec_sig = np.asarray(nk.ecg_simulate(
                            duration=rec_dur + 0.5, sampling_rate=sr, heart_rate=hr,
                            noise=noise, method="ecgsyn", random_state=rng.integers(0, 2**31),
                        ), dtype=np.float32)
                        _, ri = nk.ecg_process(rec_sig, sampling_rate=sr)
                        rec_pks = np.array(ri["ECG_R_Peaks"], dtype=int)
                    except Exception:
                        rec_pks = _regular_r_peaks(rec_dur, hr, req.heart_rate_std, sr, rng)
                        rec_sig = _synthesize_ecg(rec_pks, rec_dur + 0.5, sr, noise, heart_rate=hr, rng=rng)
                    rn = min(len(rec_sig), total - rec_start)
                    fade = min(int(0.08 * sr), rn)
                    if fade > 1:
                        ramp = np.linspace(0, 1, fade, dtype=np.float32)
                        sig[rec_start:rec_start + fade] *= (1 - ramp)
                        rec_sig[:fade] *= ramp
                    sig[rec_start:rec_start + rn] = rec_sig[:rn]
                    all_r_peaks.extend((rec_pks[rec_pks < rn] + rec_start).tolist())
                    events.append({
                        "annotation_type": "other", "start_time": round(rec_start / sr, 4),
                        "end_time": round((rec_start + rn) / sr, 4), "confidence": 0.85,
                        "label": "窦律恢复", "source": "simulated",
                        "annotation_metadata": {"algorithm": "simulate", "event": "sinus_recovery"},
                    })
    else:
        # 未触发 — 代偿间歇后恢复
        resume = pe + int(rr * sr * 0.5)
        if resume < total:
            rdur = (total - resume) / sr
            if rdur > 1.0:
                rpks = _regular_r_peaks(rdur, hr, req.heart_rate_std, sr, rng)
                rsig = _synthesize_ecg(rpks, rdur + 0.5, sr, noise, heart_rate=hr, rng=rng)
                n = min(len(rsig), total - resume)
                sig[resume:resume + n] += rsig[:n]
                all_r_peaks.extend((rpks[rpks < n] + resume).tolist())

    peak = np.max(np.abs(sig))
    if peak > 0:
        sig = sig / peak * 0.85
    return sig.astype(np.float32), np.array(sorted(set(all_r_peaks)), dtype=int), events


def simulate_ecg(req: SimulateRequest) -> tuple[np.ndarray, np.ndarray]:
    """
    返回 (ecg_signal float32, r_peaks int[]).

    策略:
    - normal/tachycardia/bradycardia/sinus_arrhythmia 且 HR ≤ 180bpm:
      使用 neurokit2 ecgsyn 直接生成（最逼真的 ECGSYN 模型）
    - 其他情况 (AF/PVC/SVT/VT 或 HR > 180bpm):
      使用增强版模板叠加
    """
    rng = np.random.default_rng(req.random_seed)
    rhythm = req.ecg_rhythm
    hr = req.heart_rate
    hr_std = req.heart_rate_std
    dur = req.duration
    noise = req.noise_level

    # ── 判断是否可以使用 neurokit2 ecgsyn 直接生成 ─────────────────
    simple_rhythms = {"normal", "tachycardia", "bradycardia", "sinus_arrhythmia"}
    can_use_ecgsyn = rhythm in simple_rhythms and hr <= _ECGSYN_HR_MAX

    if rhythm == "ron_t":
        # R-on-T 特殊路径：返回 (sig, peaks, events) 中 events 需在调用处处理
        return _simulate_ron_t(req, rng)  # type: ignore[return-value]

    if can_use_ecgsyn:
        return _simulate_ecg_ecgsyn(rhythm, hr, hr_std, dur, noise, rng)

    # ── 复杂心律 / 高心率：使用增强模板叠加 ────────────────────────
    if rhythm == "af":
        r_peaks = _af_r_peaks(dur, hr, ECG_SR, rng)
        sig = _synthesize_ecg(r_peaks, dur, ECG_SR, noise, heart_rate=hr, af_mode=True, rng=rng)

    elif rhythm == "pvc":
        base_peaks = _regular_r_peaks(dur, hr, hr_std, ECG_SR, rng)
        n = len(base_peaks)
        pvc_n = max(1, int(n * req.pvc_ratio))
        pvc_idx = set(rng.choice(n, size=pvc_n, replace=False).tolist())
        comp_peaks = list(base_peaks)
        for idx in sorted(pvc_idx):
            if idx < len(comp_peaks) - 1:
                rr = comp_peaks[idx + 1] - comp_peaks[idx]
                comp_peaks[idx] = comp_peaks[idx] - int(rr * 0.40)
                if idx + 1 < len(comp_peaks) - 1:
                    comp_peaks[idx + 1] = comp_peaks[idx] + int(rr * 1.50)
        r_peaks = np.array(sorted(comp_peaks))
        r_peaks = r_peaks[(r_peaks >= 0) & (r_peaks < int(dur * ECG_SR))]
        sig = _synthesize_ecg(r_peaks, dur, ECG_SR, noise, heart_rate=hr, pvc_indices=pvc_idx, rng=rng)

    elif rhythm in ("svt", "vt"):
        vt = rhythm == "vt"
        if rhythm == "svt":
            hr = max(hr, 130.0)
        else:
            hr = max(hr, 100.0)
        r_peaks = _regular_r_peaks(dur, hr, hr_std * 0.3, ECG_SR, rng)
        sig = _synthesize_ecg(r_peaks, dur, ECG_SR, noise, heart_rate=hr, vt_mode=vt, rng=rng)

    else:
        # 高心率 normal/tachy/brady 无法用 ecgsyn 的情况
        if rhythm == "tachycardia":
            hr = max(hr, 100.0)
        elif rhythm == "bradycardia":
            hr = min(hr, 60.0)
        elif rhythm == "sinus_arrhythmia":
            hr_std = max(hr_std, 12.0)
        r_peaks = _regular_r_peaks(dur, hr, hr_std, ECG_SR, rng)
        sig = _synthesize_ecg(r_peaks, dur, ECG_SR, noise, heart_rate=hr, rng=rng)

    return sig.astype(np.float32), r_peaks


def _simulate_ecg_ecgsyn(
    rhythm: str, hr: float, hr_std: float, dur: float, noise: float,
    rng: np.random.Generator,
) -> tuple[np.ndarray, np.ndarray]:
    """
    使用 neurokit2 ecgsyn 引擎直接生成完整 ECG 信号。
    ecgsyn 基于 MIT 的 ECGSYN 模型，形态最逼真。

    后处理: 对 T 波幅度做衰减校正（ECGSYN T/R 比约 0.37，需降至 ~0.25）。
    """
    import neurokit2 as nk

    # 调整心率范围
    if rhythm == "tachycardia":
        hr = max(hr, 100.0)
    elif rhythm == "bradycardia":
        hr = min(hr, 60.0)
    elif rhythm == "sinus_arrhythmia":
        hr_std = max(hr_std, 12.0)

    try:
        sig = nk.ecg_simulate(
            duration=dur,
            sampling_rate=ECG_SR,
            heart_rate=hr,
            heart_rate_std=hr_std,
            noise=noise,
            method="ecgsyn",
            random_state=rng.integers(0, 2**31),
        )
        sig = np.asarray(sig, dtype=np.float32)

        # 提取 R-peaks
        _, info = nk.ecg_process(sig, sampling_rate=ECG_SR)
        r_peaks = np.array(info["ECG_R_Peaks"], dtype=int)

        # ── T 波和 P 波幅度校正 ─────────────────────────────────
        # ECGSYN 的 T/R 比约 0.37，P/R 比约 0.21，均偏高
        # 临床正常范围: T/R ≈ 0.15-0.30, P/R ≈ 0.08-0.15
        sig = _attenuate_t_waves(sig, r_peaks, ECG_SR, target_ratio=0.25)
        sig = _attenuate_p_waves(sig, r_peaks, ECG_SR, target_ratio=0.12)

        # 添加呼吸性基线漂移 (ecgsyn 自身没有)
        total = len(sig)
        t_axis = np.arange(total, dtype=np.float32) / ECG_SR
        resp_freq = rng.uniform(0.15, 0.30)
        sig += (0.04 * np.sin(2 * np.pi * resp_freq * t_axis + rng.uniform(0, 2 * np.pi))).astype(np.float32)

        return sig, r_peaks

    except Exception:
        # Fallback 到模板方法
        r_peaks = _regular_r_peaks(dur, hr, hr_std, ECG_SR, rng)
        sig = _synthesize_ecg(r_peaks, dur, ECG_SR, noise, heart_rate=hr, rng=rng)
        return sig.astype(np.float32), r_peaks


def _attenuate_t_waves(
    sig: np.ndarray,
    r_peaks: np.ndarray,
    sr: int,
    target_ratio: float = 0.25,
) -> np.ndarray:
    """
    对完整 ECG 信号中每拍的 T 波做幅度衰减。

    用于校正 neurokit2 ECGSYN 生成的 T 波偏高问题。
    策略: 对每拍 R 峰后 100-400ms 区域检查 T/R 比，如果超标则衰减。
    衰减使用平滑窗函数，避免引入不连续性。
    """
    result = sig.copy()
    n = len(sig)

    for i, rp in enumerate(r_peaks):
        rp = int(rp)
        r_val = float(sig[rp])
        if r_val <= 0.01:
            continue

        # T 波段: R 峰后 100-400ms
        t_start = rp + int(0.10 * sr)
        t_end = min(n, rp + int(0.40 * sr))

        # 不要与下一拍的 QRS 重叠
        if i < len(r_peaks) - 1:
            next_qrs = int(r_peaks[i + 1]) - int(0.06 * sr)
            t_end = min(t_end, next_qrs)

        if t_end <= t_start + 5:
            continue

        t_region = sig[t_start:t_end]
        t_peak = float(np.max(t_region))
        if t_peak <= 0:
            continue

        t_ratio = t_peak / r_val
        if t_ratio <= target_ratio:
            continue

        # 衰减因子
        attenuation = target_ratio / t_ratio
        t_len = t_end - t_start

        # 平滑衰减窗: 从 1.0 过渡到 attenuation，再从 attenuation 回到 1.0
        transition = max(2, int(0.02 * sr))  # 20ms 过渡
        mask = np.ones(t_len, dtype=np.float32)

        # 前端过渡
        if transition < t_len:
            fade_in = 0.5 * (1.0 + np.cos(np.linspace(0, np.pi, transition)))
            mask[:transition] = (attenuation + (1.0 - attenuation) * fade_in).astype(np.float32)
            mask[transition:] = attenuation

        # 尾端过渡
        tail = max(2, int(t_len * 0.2))
        if tail < t_len:
            fade_out = 0.5 * (1.0 - np.cos(np.linspace(0, np.pi, tail)))
            mask[-tail:] = (attenuation + (1.0 - attenuation) * fade_out).astype(np.float32)

        result[t_start:t_end] *= mask

    return result


def _attenuate_p_waves(
    sig: np.ndarray,
    r_peaks: np.ndarray,
    sr: int,
    target_ratio: float = 0.12,
) -> np.ndarray:
    """
    对完整 ECG 信号中每拍的 P 波做幅度衰减。

    neurokit2 ECGSYN 的 P/R 比约 0.20-0.28，临床正常 P/R ≈ 0.08-0.15。
    策略: 对 R 峰前 50-220ms 区域检查正向偏折，如果 P/R 超标则衰减。
    """
    result = sig.copy()
    n = len(sig)

    for i, rp in enumerate(r_peaks):
        rp = int(rp)
        r_val = float(sig[rp])
        if r_val <= 0.01:
            continue

        # P 波段: R 峰前 50-220ms
        p_start = rp - int(0.22 * sr)
        p_end = rp - int(0.04 * sr)

        # 不要与上一拍的 T 波重叠
        if i > 0:
            prev_t_end = int(r_peaks[i - 1]) + int(0.42 * sr)
            p_start = max(p_start, prev_t_end)

        p_start = max(0, p_start)
        if p_end <= p_start + 3:
            continue

        p_region = sig[p_start:p_end]
        p_peak = float(np.max(p_region))
        if p_peak <= 0:
            continue

        p_ratio = p_peak / r_val
        if p_ratio <= target_ratio:
            continue

        # 衰减因子
        attenuation = target_ratio / p_ratio
        p_len = p_end - p_start

        # 平滑窗
        transition = max(2, int(0.015 * sr))  # 15ms 过渡
        mask = np.ones(p_len, dtype=np.float32)

        # 前端过渡
        if transition < p_len:
            fade_in = 0.5 * (1.0 + np.cos(np.linspace(0, np.pi, transition)))
            mask[:transition] = (attenuation + (1.0 - attenuation) * fade_in).astype(np.float32)
            if 2 * transition < p_len:
                mask[transition:-transition] = attenuation
        # 后端过渡 (PR 段回到正常)
        if transition < p_len:
            fade_out = 0.5 * (1.0 - np.cos(np.linspace(0, np.pi, transition)))
            mask[-transition:] = (attenuation + (1.0 - attenuation) * fade_out).astype(np.float32)

        result[p_start:p_end] *= mask

    return result


# ─────────────────────────────────────────────────────────────────────────────
# PCG synthesis
# ─────────────────────────────────────────────────────────────────────────────

def _bandpass(sig: np.ndarray, lo: float, hi: float, sr: int) -> np.ndarray:
    nyq = sr / 2
    lo_n = max(lo / nyq, 1e-4)
    hi_n = min(hi / nyq, 0.9999)
    sos = butter(4, [lo_n, hi_n], btype="bandpass", output="sos")
    return sosfilt(sos, sig).astype(np.float32)


def _stethoscope_filter(sig: np.ndarray, sr: int) -> np.ndarray:
    """
    模拟听诊器频响：
    1. 20-800Hz 四阶带通（Butterworth），模拟膜式体件通带
    2. 轻微低频共鸣增强（~80Hz），模拟胸壁/听诊器腔体共鸣
    3. 微弱高频滚降使音色更"温暖"
    """
    # Step 1: 主通带 20-800Hz
    filtered = _bandpass(sig, _STETHO_LO, _STETHO_HI, sr)

    # Step 2: 共鸣增强 — 在 60-120Hz 段叠加少量 boosted 成分
    res_band = _bandpass(sig, 50.0, 120.0, sr)
    filtered = filtered + 0.18 * res_band  # 约 +2dB 共鸣

    # Step 3: 轻微高频滚降 (额外 4 阶低通 700Hz)
    nyq = sr / 2
    if 700.0 / nyq < 0.9999:
        sos_lp = butter(4, 700.0 / nyq, btype="low", output="sos")
        filtered = sosfilt(sos_lp, filtered).astype(np.float32)

    return filtered.astype(np.float32)


def _make_heart_sound(
    duration: float,
    sr: int,
    lo: float = 20.0,
    hi: float = 150.0,
    amplitude: float = 1.0,
    rng: Optional[np.random.Generator] = None,
    freq_jitter: float = 0.0,      # 频率随机偏移比例 0~0.2
    width_jitter: float = 0.0,     # 时长随机缩放 0~0.2
) -> np.ndarray:
    """
    多模态心音合成 v3：多个随机相位阻尼振荡模态 + 带限噪声填充 + 急起缓落包络。

    真实心音是心瓣膜突然关闭 → 心肌/胸壁**多模态**阻尼振荡，不同振动模态
    有各自的频率、衰减率和随机初始相位。这比 2 个正弦叠加更接近真实冲击响应，
    消除了"规律震荡"的合成听感。

    关键改进（相对 v2）：
    1. 4-6 个频率模态（随机分布在 lo~hi 范围），每个有独立随机相位 → 消除规律振荡
    2. 各模态的衰减系数不同（高频衰减快、低频衰减慢）→ 自然的频谱演变
    3. 叠加少量带限噪声 → 填充谐波间的频谱空隙，增加"质感"
    4. 非对称包络：极快 onset（3-8ms）+ 缓慢指数衰减尾 → 模拟真实冲击
    """
    rng = rng or np.random.default_rng()

    # 应用宽度抖动
    if width_jitter > 0:
        duration = duration * (1.0 + rng.uniform(-width_jitter, width_jitter))
    duration = max(0.02, duration)

    n = int(duration * sr)
    if n < 2:
        return np.zeros(1, dtype=np.float32)
    t = np.linspace(0, duration, n, dtype=np.float32)

    # 应用频率抖动到频率范围
    center_freq = (lo + hi) / 2.0
    if freq_jitter > 0:
        jit = float(rng.uniform(-freq_jitter, freq_jitter))
        lo = lo * (1.0 + jit)
        hi = hi * (1.0 + jit)
        center_freq = (lo + hi) / 2.0

    # ── 多模态阻尼振荡 ───────────────────────────────────────
    # 真实心音包含 4-8 个振动模态，各自频率、相位、衰减速率不同
    n_modes = int(rng.integers(4, 7))  # 4-6 个模态
    damped = np.zeros(n, dtype=np.float64)

    # 在 lo~hi 范围内生成随机分布的模态频率
    mode_freqs = np.sort(rng.uniform(lo, hi, n_modes))

    for i, freq in enumerate(mode_freqs):
        # 每个模态有独立的随机初始相位（0~2π），打破规律震荡
        phase = float(rng.uniform(0, 2 * np.pi))

        # 频率越高衰减越快（高频模态快速消失，低频模态拖尾更长）
        # 基础衰减：duration 末尾衰减到 5%
        base_alpha = -np.log(0.05) / max(duration, 0.01)
        # 高频加速因子：频率在 hi 端的模态衰减速率是低频端的 1.5~2.5 倍
        freq_ratio = (freq - lo) / max(hi - lo, 1.0)
        alpha = base_alpha * (1.0 + freq_ratio * float(rng.uniform(0.5, 1.5)))

        # 模态幅度：中心频率附近最强，边缘衰减（近似共振分布）
        freq_dist = abs(freq - center_freq) / max(hi - lo, 1.0)
        mode_amp = float(rng.uniform(0.5, 1.0)) * np.exp(-1.5 * freq_dist)

        damped += mode_amp * np.exp(-alpha * t) * np.sin(2 * np.pi * freq * t + phase)

    # ── 带限噪声层 ───────────────────────────────────────────
    # 填充模态频率之间的频谱空隙，增加"肉感"和"质感"
    # 真实心音不是纯粹的正弦叠加，还有组织振动产生的随机宽频成分
    noise_white = rng.normal(0, 1, n).astype(np.float32)
    lo_bp = max(lo * 0.8, 10.0)
    hi_bp = min(hi * 1.2, sr / 2 * 0.9)
    if lo_bp < hi_bp:
        noise_band = _bandpass(noise_white, lo_bp, hi_bp, sr)
    else:
        noise_band = noise_white
    noise_pk = np.max(np.abs(noise_band))
    if noise_pk > 0:
        noise_band = noise_band / noise_pk
    # 噪声层幅度约为模态叠加的 10-20%
    noise_level = float(rng.uniform(0.10, 0.20))
    combined = damped.astype(np.float32) + noise_band * noise_level * float(np.max(np.abs(damped)))

    # ── 非对称包络：急起缓落 ──────────────────────────────────
    # 真实瓣膜关闭是 onset 极快（< 5ms 冲击）+ offset 缓慢拖尾
    # 使用分段包络：快速指数上升 + 缓慢指数衰减
    onset_time = float(rng.uniform(0.003, 0.008))  # 3-8ms 的快速上升
    peak_pos = onset_time / max(duration, 0.01)     # 峰值出现在很早的位置
    peak_idx = max(1, int(peak_pos * n))

    env = np.zeros(n, dtype=np.float32)
    # 上升段：快速指数上升
    if peak_idx > 0:
        rise = np.linspace(0, 1, peak_idx, dtype=np.float32)
        # 用 x^2 曲线加速上升的"冲击感"
        env[:peak_idx] = rise ** 2
    # 下降段：双指数衰减（快成分 + 慢成分混合），避免机械的单指数
    if peak_idx < n:
        fall_t = np.linspace(0, duration - onset_time, n - peak_idx, dtype=np.float32)
        # 快衰减成分（高频振动迅速消散）
        tau_fast = duration * float(rng.uniform(0.15, 0.25))
        # 慢衰减成分（低频振动的长拖尾）
        tau_slow = duration * float(rng.uniform(0.40, 0.60))
        # 混合比例
        fast_ratio = float(rng.uniform(0.5, 0.7))
        env[peak_idx:] = (
            fast_ratio * np.exp(-fall_t / max(tau_fast, 0.001))
            + (1.0 - fast_ratio) * np.exp(-fall_t / max(tau_slow, 0.001))
        ).astype(np.float32)

    sig = (combined * env * amplitude).astype(np.float32)

    # 带通保证频率范围正确
    lo_clip = max(lo * 0.7, 10.0)
    hi_clip = min(hi * 1.3, sr / 2 * 0.9)
    if lo_clip < hi_clip:
        sig = _bandpass(sig, lo_clip, hi_clip, sr)

    return sig.astype(np.float32)


def _make_murmur(
    duration: float,
    sr: int,
    lo: float = 80.0,
    hi: float = 600.0,
    amplitude: float = 0.04,
    shape: str = "diamond",
    rng: Optional[np.random.Generator] = None,
) -> np.ndarray:
    """杂音：高频带限噪声 × 包络（菱形 or 递减）。"""
    rng = rng or np.random.default_rng()
    n = max(2, int(duration * sr))
    noise = rng.normal(0, 1, n).astype(np.float32)
    filt = _bandpass(noise, lo, hi, sr)
    if shape == "diamond":
        half = n // 2
        env = np.concatenate([np.linspace(0.1, 1.0, half), np.linspace(1.0, 0.1, n - half)])
    else:  # decrescendo
        env = np.linspace(1.0, 0.1, n)
    return (filt * env * amplitude).astype(np.float32)


def _add_at(sig: np.ndarray, sound: np.ndarray, pos: int) -> None:
    """将 sound 叠加到 sig[pos:pos+len(sound)]（边界安全）。"""
    end = pos + len(sound)
    if pos < 0:
        sound = sound[-pos:]
        pos = 0
        end = pos + len(sound)
    if end > len(sig):
        sound = sound[: len(sig) - pos]
        end = len(sig)
    if len(sound) > 0 and pos < len(sig):
        sig[pos:end] += sound


def simulate_pcg(
    r_peaks_ecg: np.ndarray,
    duration: float,
    req: SimulateRequest,
    rng: Optional[np.random.Generator] = None,
) -> np.ndarray:
    """
    根据 ECG R-peak 序列合成 PCG（v2 — 基于真实运动 PCG 优化）。

    r_peaks_ecg: ECG 采样点位置（ECG_SR=500Hz 坐标系）
    采样率由 req.pcg_sample_rate 决定。

    v2 改进:
    1. S1/S2 改为阻尼振荡合成（更接近真实瓣膜冲击响应）
    2. 逐拍幅度/宽度抖动（±15% 幅度，±15% 时长）
    3. 呼吸性幅度调制（S1/S2 随呼吸周期 ±12% 变化）
    4. 生理性持续背景音（20-150Hz 连续底噪，提升真实感）
    5. 运动伪影层（可选）：低频运动噪声 + 摩擦噪声
    6. 软限幅后处理降低峰值因子（从 12 降至 ~6）
    """
    rng = rng or np.random.default_rng(req.random_seed)
    sr = int(req.pcg_sample_rate) if req.pcg_sample_rate else PCG_SR_DEFAULT
    total = int(duration * sr)
    sig = np.zeros(total, dtype=np.float32)
    t_axis = np.arange(total, dtype=np.float32) / sr

    abnorm = set(req.pcg_abnormalities)
    n_beats = len(r_peaks_ecg)
    exercise = float(getattr(req, 'exercise_intensity', 0.0))

    # 心音基础幅度
    _s1_amp = 0.15 * req.s1_amplitude
    _s2_amp = 0.10 * req.s2_amplitude

    # ── 呼吸参数（用于逐拍幅度调制）────────────────────────────
    resp_freq = rng.uniform(0.15, 0.30)
    resp_phase = rng.uniform(0, 2 * np.pi)

    # ── 逐拍合成 ──────────────────────────────────────────────
    for i, rp_ecg in enumerate(r_peaks_ecg):
        rp_pcg = int(rp_ecg / ECG_SR * sr)

        if i < n_beats - 1:
            rr_sec = (r_peaks_ecg[i + 1] - rp_ecg) / ECG_SR
        else:
            rr_sec = 60.0 / req.heart_rate

        # 呼吸调制系数（该拍位置的呼吸相位）
        beat_t = rp_pcg / sr
        resp_mod = 1.0 + 0.12 * np.sin(2 * np.pi * resp_freq * beat_t + resp_phase)

        # 逐拍幅度抖动 ±15%
        amp_jitter = 1.0 + rng.normal(0, 0.08)

        # 综合幅度系数
        s1_amp_i = _s1_amp * resp_mod * amp_jitter
        s2_amp_i = _s2_amp * resp_mod * (amp_jitter * 0.9 + 0.1)

        # ── S1 (~R peak + 20ms) ──────────────────────────────
        s1_start = rp_pcg + int(0.020 * sr)
        s1_dur = min(0.14, rr_sec * 0.18)
        # S1: 二尖瓣/三尖瓣关闭，主频 30-90Hz，频率逐拍微变
        s1 = _make_heart_sound(
            s1_dur, sr, lo=25.0, hi=90.0, amplitude=s1_amp_i, rng=rng,
            freq_jitter=0.12, width_jitter=0.15,
        )

        if req.ecg_rhythm == "s4_gallop" or "s4_gallop" in abnorm:
            s4 = _make_heart_sound(0.07, sr, 15, 60, _s1_amp * 0.18, rng)
            _add_at(sig, s4, s1_start - int(0.08 * sr))

        _add_at(sig, s1, s1_start)

        systole_sec = min(rr_sec * 0.38, 0.35)

        # ── 收缩期杂音 ──────────────────────────────────────
        if "murmur_systolic" in abnorm:
            m_dur = max(0.05, systole_sec - 0.06)
            murmur = _make_murmur(m_dur, sr, 80, 500, _s1_amp * 0.25, "diamond", rng)
            _add_at(sig, murmur, s1_start + len(s1))

        # ── S2 ────────────────────────────────────────────
        s2_start = rp_pcg + int(0.020 * sr) + int(systole_sec * sr)
        s2_dur = min(0.10, rr_sec * 0.12)
        # S2: 主动脉/肺动脉瓣关闭，主频 50-130Hz，比 S1 音调略高
        s2 = _make_heart_sound(
            s2_dur, sr, lo=40.0, hi=130.0, amplitude=s2_amp_i, rng=rng,
            freq_jitter=0.10, width_jitter=0.12,
        )

        if "split_s2" in abnorm:
            _add_at(sig, s2, s2_start)
            s2b = _make_heart_sound(s2_dur, sr, 40, 130, s2_amp_i * 0.75, rng)
            _add_at(sig, s2b, s2_start + int(0.04 * sr))
        else:
            _add_at(sig, s2, s2_start)

        # ── 舒张期杂音 ──────────────────────────────────────
        if "murmur_diastolic" in abnorm:
            diastole_sec = rr_sec - systole_sec - 0.02
            if diastole_sec > 0.05:
                dm = _make_murmur(
                    min(diastole_sec * 0.6, 0.20), sr, 60, 350, _s2_amp * 0.18, "decrescendo", rng
                )
                _add_at(sig, dm, s2_start + len(s2) + int(0.02 * sr))

        # ── S3 奔马律 ────────────────────────────────────
        if "s3_gallop" in abnorm:
            s3 = _make_heart_sound(0.07, sr, 15, 60, _s1_amp * 0.18, rng)
            _add_at(sig, s3, s2_start + int(0.14 * sr))

    # ── 听诊器频响塑形 ─────────────────────────────────────────
    if req.stethoscope_mode:
        sig = _stethoscope_filter(sig, sr)

    # ── 生理性持续背景音（改进 #4）─────────────────────────────
    # 真实心音有持续的 20-150Hz 组织/血流背景声，使 Crest Factor 从 12 降到 ~6
    bg_white = rng.normal(0, 1, total).astype(np.float32)
    tissue_bg = _bandpass(bg_white, 20.0, min(150.0, sr / 2 * 0.9), sr)
    tissue_bg_pk = np.max(np.abs(tissue_bg))
    if tissue_bg_pk > 0:
        tissue_bg = tissue_bg / tissue_bg_pk
    # 持续背景幅度约为 S1 峰值的 8%（真实值约 5-12%）
    sig += tissue_bg * _s1_amp * 0.08

    # ── 额外背景噪声（用户可调参数）───────────────────────────
    if req.pcg_noise_level > 0:
        bg_white2 = rng.normal(0, 1, total).astype(np.float32)
        bg_noise = _bandpass(bg_white2, 20.0, min(400.0, sr / 2 * 0.8), sr)
        bg_peak = np.max(np.abs(bg_noise))
        if bg_peak > 0:
            bg_noise = bg_noise / bg_peak
        sig += bg_noise * req.pcg_noise_level * 0.3

    # ── 运动伪影层（改进 #5，exercise_intensity > 0 时启用）────
    if exercise > 0:
        # 低频运动伪影（身体晃动 5-18Hz）
        # 真实运动 PCG 的 5-20Hz 能量比静息增加 1.6×
        motion_white = rng.normal(0, 1, total).astype(np.float32)
        motion_lo = _bandpass(motion_white, 5.0, min(18.0, sr / 2 * 0.9), sr)
        motion_lo_pk = np.max(np.abs(motion_lo))
        if motion_lo_pk > 0:
            motion_lo = motion_lo / motion_lo_pk
        sig += motion_lo * exercise * _s1_amp * 0.15

        # 皮肤/衣物摩擦噪声（150-500Hz）
        # 真实运动 PCG 的 150-500Hz 能量增加 4×
        friction_white = rng.normal(0, 1, total).astype(np.float32)
        friction_hi = _bandpass(friction_white, 150.0, min(500.0, sr / 2 * 0.9), sr)
        friction_pk = np.max(np.abs(friction_hi))
        if friction_pk > 0:
            friction_hi = friction_hi / friction_pk
        sig += friction_hi * exercise * _s1_amp * 0.06

        # 调制包络（运动时的间歇性接触噪声）
        mod_freq = rng.uniform(1.5, 3.5)  # 步频 1.5-3.5Hz
        mod_env = (1.0 + exercise * 0.5 * np.sin(2 * np.pi * mod_freq * t_axis)).astype(np.float32)
        sig *= mod_env

    # ── 软限幅后处理（改进 #6）——————降低峰值因子 ──────────────
    # tanh 软限幅使极端峰值被压制，让波形更圆润、Crest Factor 从 ~12 降至 ~6
    # 参数 1.5 控制限幅强度：越大越软
    peak_before = np.max(np.abs(sig))
    if peak_before > 0:
        sig_norm = sig / peak_before
        sig = np.tanh(sig_norm * 1.5) / np.tanh(np.array(1.5, dtype=np.float32))
        sig = (sig * peak_before).astype(np.float32)

    # ── 归一化至 0.9 峰值 ─────────────────────────────────────
    peak = np.max(np.abs(sig))
    if peak > 0:
        sig = sig / peak * 0.9
    return sig


# ─────────────────────────────────────────────────────────────────────────────
# ECG annotations from r_peaks
# ─────────────────────────────────────────────────────────────────────────────

def _ecg_annotations_from_peaks(
    r_peaks: np.ndarray, duration: float, sr: int = ECG_SR
) -> list[dict]:
    """从 R-peak 序列生成 ECG 标记（QRS + P + T）。"""
    items = []
    n = len(r_peaks)
    for i, rp in enumerate(r_peaks):
        rr_next = (r_peaks[i + 1] - rp) / sr if i < n - 1 else 0.8
        rr_prev = (rp - r_peaks[i - 1]) / sr if i > 0 else 0.8

        t_r = rp / sr
        # QRS complex
        items.append(
            dict(
                annotation_type="qrs",
                start_time=round(t_r - 0.04, 4),
                end_time=round(t_r + 0.05, 4),
                confidence=0.92,
                label="QRS",
                source="simulated",
                annotation_metadata={"algorithm": "simulate"},
            )
        )
        # P wave (~160ms before R)
        if rr_prev > 0.25:
            p_center = t_r - 0.16
            if p_center > 0:
                items.append(
                    dict(
                        annotation_type="p_wave",
                        start_time=round(p_center - 0.04, 4),
                        end_time=round(p_center + 0.04, 4),
                        confidence=0.85,
                        label="P",
                        source="simulated",
                        annotation_metadata={"algorithm": "simulate"},
                    )
                )
        # T wave (~200ms after R, wider in slow HR)
        t_offset = min(0.22 + (rr_next - 0.8) * 0.1, 0.35)
        t_center = t_r + t_offset
        if t_center + 0.06 < duration:
            items.append(
                dict(
                    annotation_type="t_wave",
                    start_time=round(t_center - 0.06, 4),
                    end_time=round(t_center + 0.06, 4),
                    confidence=0.82,
                    label="T",
                    source="simulated",
                    annotation_metadata={"algorithm": "simulate"},
                )
            )
    return items


def _pcg_annotations_from_peaks(
    r_peaks: np.ndarray,
    duration: float,
    ecg_sr: int = ECG_SR,
    heart_rate: float = 72.0,
    abnorm: Optional[set] = None,
) -> list[dict]:
    """从 R-peak 序列生成 PCG 标记（S1/S2 及杂音）。"""
    items = []
    n = len(r_peaks)
    abnorm = abnorm or set()
    for i, rp in enumerate(r_peaks):
        rr_sec = (r_peaks[i + 1] - rp) / ecg_sr if i < n - 1 else 60.0 / heart_rate
        systole_sec = min(rr_sec * 0.38, 0.35)
        s1_t = rp / ecg_sr + 0.020
        s2_t = s1_t + systole_sec
        s1_dur = min(0.14, rr_sec * 0.18)
        s2_dur = min(0.10, rr_sec * 0.12)

        if s1_t + s1_dur < duration:
            items.append(
                dict(
                    annotation_type="s1",
                    start_time=round(s1_t, 4),
                    end_time=round(s1_t + s1_dur, 4),
                    confidence=0.93,
                    label="S1",
                    source="simulated",
                    annotation_metadata={"algorithm": "simulate"},
                )
            )
        if s2_t + s2_dur < duration:
            items.append(
                dict(
                    annotation_type="s2",
                    start_time=round(s2_t, 4),
                    end_time=round(s2_t + s2_dur, 4),
                    confidence=0.91,
                    label="S2",
                    source="simulated",
                    annotation_metadata={"algorithm": "simulate"},
                )
            )
        # 杂音标记
        if "murmur_systolic" in abnorm:
            m_start = s1_t + s1_dur
            m_end = s2_t - 0.01
            if m_end > m_start + 0.02:
                items.append(
                    dict(
                        annotation_type="murmur",
                        start_time=round(m_start, 4),
                        end_time=round(m_end, 4),
                        confidence=0.88,
                        label="Systolic Murmur",
                        source="simulated",
                        annotation_metadata={"algorithm": "simulate"},
                    )
                )
        if "murmur_diastolic" in abnorm:
            m_start = s2_t + s2_dur
            m_end = m_start + rr_sec * 0.25
            if m_end < duration:
                items.append(
                    dict(
                        annotation_type="murmur",
                        start_time=round(m_start, 4),
                        end_time=round(m_end, 4),
                        confidence=0.85,
                        label="Diastolic Murmur",
                        source="simulated",
                        annotation_metadata={"algorithm": "simulate"},
                    )
                )
    return items


# ─────────────────────────────────────────────────────────────────────────────
# File save helper
# ─────────────────────────────────────────────────────────────────────────────

def _save_wav(signal: np.ndarray, sr: int, upload_dir: str, filename: str) -> tuple[str, int]:
    """将 float32 signal 写成 PCM int16 WAV，返回 (file_path, file_size_bytes)。"""
    os.makedirs(upload_dir, exist_ok=True)
    path = os.path.join(upload_dir, filename)
    pcm = np.clip(signal, -1.0, 1.0)
    pcm_i16 = (pcm * 32767).astype(np.int16)
    wavfile.write(path, sr, pcm_i16)
    return path, os.path.getsize(path)


# ─────────────────────────────────────────────────────────────────────────────
# Router
# ─────────────────────────────────────────────────────────────────────────────

router = APIRouter()

# Built-in templates ──────────────────────────────────────────────────────────
TEMPLATES = [
    {
        "id": "normal_adult",
        "name": "正常成人窦性心律",
        "category": "normal",
        "description": "标准成人静息心率，P-QRS-T 完整，S1/S2 正常",
        "params": dict(ecg_rhythm="normal", heart_rate=72, heart_rate_std=2, noise_level=0.01,
                       duration=10, generate_pcg=True, pcg_abnormalities=[],
                       s1_amplitude=1.0, s2_amplitude=0.7, pcg_noise_level=0.005),
    },
    {
        "id": "sinus_tachycardia",
        "name": "窦性心动过速",
        "category": "arrhythmia",
        "description": "心率 > 100 bpm，节律规整，常见于运动/焦虑/发热",
        "params": dict(ecg_rhythm="tachycardia", heart_rate=130, heart_rate_std=3, noise_level=0.01,
                       duration=10, generate_pcg=True, pcg_abnormalities=[],
                       s1_amplitude=1.1, s2_amplitude=0.8, pcg_noise_level=0.004),
    },
    {
        "id": "sinus_bradycardia",
        "name": "窦性心动过缓",
        "category": "arrhythmia",
        "description": "心率 < 60 bpm，节律规整，常见于运动员/迷走神经张力高",
        "params": dict(ecg_rhythm="bradycardia", heart_rate=45, heart_rate_std=2, noise_level=0.01,
                       duration=15, generate_pcg=True, pcg_abnormalities=[],
                       s1_amplitude=0.9, s2_amplitude=0.65, pcg_noise_level=0.005),
    },
    {
        "id": "sinus_arrhythmia",
        "name": "窦性心律不齐",
        "category": "arrhythmia",
        "description": "RR 间期随呼吸周期性变化，青少年常见生理现象",
        "params": dict(ecg_rhythm="sinus_arrhythmia", heart_rate=72, heart_rate_std=15,
                       noise_level=0.015, duration=15, generate_pcg=True, pcg_abnormalities=[],
                       s1_amplitude=1.0, s2_amplitude=0.7, pcg_noise_level=0.005),
    },
    {
        "id": "af",
        "name": "心房颤动 (AF)",
        "category": "arrhythmia",
        "description": "RR 间期完全不规则，无明显 P 波，临床最常见心律失常",
        "params": dict(ecg_rhythm="af", heart_rate=90, heart_rate_std=5, noise_level=0.03,
                       duration=15, generate_pcg=True, pcg_abnormalities=[],
                       s1_amplitude=0.9, s2_amplitude=0.65, pcg_noise_level=0.006),
    },
    {
        "id": "pvc",
        "name": "室性早搏 (PVC)",
        "category": "arrhythmia",
        "description": "宽大畸形 QRS 提前出现 + 代偿间歇，S1 音减弱",
        "params": dict(ecg_rhythm="pvc", heart_rate=72, heart_rate_std=3, pvc_ratio=0.20,
                       noise_level=0.01, duration=15, generate_pcg=True, pcg_abnormalities=[],
                       s1_amplitude=0.75, s2_amplitude=0.6, pcg_noise_level=0.005),
    },
    {
        "id": "svt",
        "name": "室上性心动过速 (SVT)",
        "category": "arrhythmia",
        "description": "突发规整快速心率 160~220 bpm，P 波隐藏于 QRS 内",
        "params": dict(ecg_rhythm="svt", heart_rate=190, heart_rate_std=1, noise_level=0.01,
                       duration=10, generate_pcg=True, pcg_abnormalities=[],
                       s1_amplitude=1.0, s2_amplitude=0.75, pcg_noise_level=0.004),
    },
    {
        "id": "vt",
        "name": "室性心动过速 (VT)",
        "category": "arrhythmia",
        "description": "宽 QRS 快速节律，心率 150~250 bpm，危急心律失常",
        "params": dict(ecg_rhythm="vt", heart_rate=175, heart_rate_std=2, noise_level=0.02,
                       duration=10, generate_pcg=True, pcg_abnormalities=[],
                       s1_amplitude=0.85, s2_amplitude=0.7, pcg_noise_level=0.006),
    },
    {
        "id": "ron_t_vt",
        "name": "R-on-T → 室速 (VT)",
        "category": "arrhythmia",
        "description": "PVC 落在 T 波易损期触发室速发作，可能自行恢复窦律",
        "params": dict(ecg_rhythm="ron_t", heart_rate=72, heart_rate_std=2, noise_level=0.01,
                       duration=15, generate_pcg=False, pcg_abnormalities=[],
                       ron_t_vt_probability=0.9, ron_t_vf_ratio=0.0),
    },
    {
        "id": "ron_t_vf",
        "name": "R-on-T → 室颤 (VF)",
        "category": "arrhythmia",
        "description": "PVC 落在 T 波易损期触发致命室颤，从粗颤逐渐演变为细颤",
        "params": dict(ecg_rhythm="ron_t", heart_rate=72, heart_rate_std=2, noise_level=0.01,
                       duration=15, generate_pcg=False, pcg_abnormalities=[],
                       ron_t_vt_probability=0.95, ron_t_vf_ratio=0.8),
    },
    {
        "id": "ron_t_random",
        "name": "R-on-T（随机结局）",
        "category": "arrhythmia",
        "description": "PVC 落在 T 波易损期，60% 概率触发恶性心律（VT 或 VF），结局随机",
        "params": dict(ecg_rhythm="ron_t", heart_rate=72, heart_rate_std=2, noise_level=0.01,
                       duration=15, generate_pcg=False, pcg_abnormalities=[],
                       ron_t_vt_probability=0.6, ron_t_vf_ratio=0.4),
    },
    {
        "id": "systolic_murmur",
        "name": "收缩期杂音（二尖瓣关闭不全）",
        "category": "valvular",
        "description": "S1 后全收缩期杂音，高调吹风样，向腋下传导",
        "params": dict(ecg_rhythm="normal", heart_rate=75, heart_rate_std=2, noise_level=0.01,
                       duration=12, generate_pcg=True,
                       pcg_abnormalities=["murmur_systolic"],
                       s1_amplitude=1.0, s2_amplitude=0.7, pcg_noise_level=0.005),
    },
    {
        "id": "s3_gallop",
        "name": "S3 奔马律（心力衰竭）",
        "category": "valvular",
        "description": "S2 后额外低频 S3 音，三音节奔马律，提示心室顺应性降低",
        "params": dict(ecg_rhythm="tachycardia", heart_rate=105, heart_rate_std=3, noise_level=0.01,
                       duration=12, generate_pcg=True,
                       pcg_abnormalities=["s3_gallop"],
                       s1_amplitude=0.9, s2_amplitude=0.65, pcg_noise_level=0.005),
    },
    {
        "id": "exercise_stairs",
        "name": "运动后心音（上楼梯）",
        "category": "normal",
        "description": "130bpm 快速窦律，含运动伪影（低频晃动 + 衣物摩擦），模拟上楼梯后听诊场景",
        "params": dict(ecg_rhythm="tachycardia", heart_rate=130, heart_rate_std=4, noise_level=0.015,
                       duration=15, generate_pcg=True, pcg_abnormalities=[],
                       s1_amplitude=1.1, s2_amplitude=0.8, pcg_noise_level=0.006,
                       stethoscope_mode=True, pcg_sample_rate=8000,
                       exercise_intensity=0.4),
    },
    {
        "id": "exercise_squats",
        "name": "运动后心音（深蹲）",
        "category": "normal",
        "description": "160bpm 快速窦律，强运动伪影，S1/S2 幅度增大，模拟剧烈运动后听诊场景",
        "params": dict(ecg_rhythm="tachycardia", heart_rate=160, heart_rate_std=6, noise_level=0.02,
                       duration=15, generate_pcg=True, pcg_abnormalities=[],
                       s1_amplitude=1.3, s2_amplitude=1.0, pcg_noise_level=0.008,
                       stethoscope_mode=True, pcg_sample_rate=8000,
                       exercise_intensity=0.7),
    },
]


@router.get("/templates", summary="获取内置模拟模板列表")
async def list_templates(current_user: CurrentActiveUser):
    return {"templates": TEMPLATES}


@router.post("/generate", summary="生成模拟 ECG/PCG 信号", response_model=SimulateResult)
async def generate_simulation(
    req: SimulateRequest,
    db: DatabaseSession,
    current_user: CurrentActiveUser,
):
    """
    合成 ECG（必选）和 PCG（可选），写入指定项目，
    自动生成标记（source='simulated'）。
    """
    # 验证项目
    proj_res = await db.execute(
        select(Project).where(Project.id == req.project_id)
    )
    project = proj_res.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    upload_dir = os.path.join(settings.UPLOAD_DIR, req.project_id)
    rng = np.random.default_rng(req.random_seed)

    # ── 生成 ECG ─────────────────────────────────────────────────
    ron_t_events: list[dict] = []
    try:
        result = simulate_ecg(req)
        if len(result) == 3:
            # R-on-T 模式返回 (sig, peaks, events)
            ecg_sig, r_peaks, ron_t_events = result
        else:
            ecg_sig, r_peaks = result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"ECG 合成失败: {e}")

    # 归一化
    peak = np.max(np.abs(ecg_sig))
    if peak > 0:
        ecg_sig = ecg_sig / peak * 0.85

    # 保存 ECG WAV
    uid_ecg = uuid.uuid4()
    ecg_fname = f"sim_ecg_{uid_ecg.hex[:8]}.wav"
    ecg_path, ecg_size = _save_wav(ecg_sig, ECG_SR, upload_dir, ecg_fname)

    display_name = f"模拟ECG_{req.ecg_rhythm}_{req.heart_rate:.0f}bpm_{req.duration:.0f}s.wav"

    ecg_file = MediaFile(
        id=uid_ecg,
        project_id=uuid.UUID(req.project_id),
        filename=ecg_fname,
        original_filename=display_name,
        file_type="ecg",
        file_size=ecg_size,
        file_path=f"{req.project_id}/{ecg_fname}",
        storage_backend="local",
        duration=req.duration,
        sample_rate=float(ECG_SR),
        channels=1,
    )
    db.add(ecg_file)
    await db.flush()

    # ECG 标记
    ecg_ann_count = 0
    if req.auto_detect and len(r_peaks) > 0:
        ecg_anns = _ecg_annotations_from_peaks(r_peaks, req.duration)
        for d in ecg_anns:
            db.add(Annotation(
                file_id=uid_ecg,
                user_id=current_user.id,
                **d,
            ))
        ecg_ann_count = len(ecg_anns)

    # R-on-T 事件标记 (ron_t / vt / vf / sinus_recovery)
    if ron_t_events:
        for ev in ron_t_events:
            db.add(Annotation(
                file_id=uid_ecg,
                user_id=current_user.id,
                **ev,
            ))
        ecg_ann_count += len(ron_t_events)

    # ── 生成 PCG ─────────────────────────────────────────────────
    pcg_file_id = None
    pcg_fname_out = None
    pcg_ann_count = 0

    if req.generate_pcg and len(r_peaks) > 0:
        try:
            # R-on-T 场景：仅过滤 VF 时间段内的 R-peaks
            # VF 段无协调性心室收缩 → 无离散心音，只有混沌噪声
            # VT 段仍有协调性（虽异常快速）心室收缩 → 保留 S1/S2
            pcg_r_peaks = r_peaks.copy()
            if req.ecg_rhythm == "ron_t" and ron_t_events:
                # 仅收集 VF 的时间段（VT 保留心音）
                vf_segments: list[tuple[float, float]] = []
                for ev in ron_t_events:
                    if ev["annotation_type"] == "vf":
                        vf_segments.append((ev["start_time"], ev["end_time"]))

                if vf_segments:
                    # 过滤落在 VF 段内的 R-peaks（VT 段 R-peaks 保留）
                    def in_vf(rp_sec: float) -> bool:
                        return any(s <= rp_sec <= e for s, e in vf_segments)

                    pcg_r_peaks = np.array(
                        [rp for rp in r_peaks if not in_vf(rp / ECG_SR)],
                        dtype=int,
                    )

            pcg_sig = simulate_pcg(pcg_r_peaks, req.duration, req, rng)

            # R-on-T VF 段：在 PCG 信号的 VF 时间区间叠加混沌噪声（覆盖任何残留心音）
            if req.ecg_rhythm == "ron_t" and ron_t_events:
                pcg_actual_sr_tmp = int(req.pcg_sample_rate) if req.pcg_sample_rate else PCG_SR_DEFAULT
                for ev in ron_t_events:
                    if ev["annotation_type"] == "vf":
                        t0_s = int(ev["start_time"] * pcg_actual_sr_tmp)
                        t1_s = min(len(pcg_sig), int(ev["end_time"] * pcg_actual_sr_tmp))
                        if t1_s > t0_s:
                            vf_dur_s = (t1_s - t0_s) / pcg_actual_sr_tmp
                            # 混沌低幅噪声（5-50Hz，幅度约为正常心音的 15%）
                            vf_noise = rng.normal(0, 0.05, t1_s - t0_s).astype(np.float32)
                            from scipy.signal import butter as _butter, sosfilt as _sosfilt
                            nyq_tmp = pcg_actual_sr_tmp / 2
                            sos_vf = _butter(4, [5.0 / nyq_tmp, min(50.0 / nyq_tmp, 0.99)], btype="band", output="sos")
                            vf_noise = _sosfilt(sos_vf, vf_noise).astype(np.float32)
                            # 幅度随时间衰减（粗颤→细颤）
                            t_seg = np.arange(t1_s - t0_s, dtype=np.float32) / pcg_actual_sr_tmp
                            decay = np.exp(-0.5 * t_seg / max(vf_dur_s, 0.1)).astype(np.float32)
                            pcg_sig[t0_s:t1_s] = pcg_sig[t0_s:t1_s] * 0.05 + vf_noise * decay * 0.15

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"PCG 合成失败: {e}")

        pcg_actual_sr = int(req.pcg_sample_rate) if req.pcg_sample_rate else PCG_SR_DEFAULT
        uid_pcg = uuid.uuid4()
        pcg_fname = f"sim_pcg_{uid_pcg.hex[:8]}.wav"
        pcg_path, pcg_size = _save_wav(pcg_sig, pcg_actual_sr, upload_dir, pcg_fname)

        abnorm_str = ("+" + "+".join(req.pcg_abnormalities)) if req.pcg_abnormalities else ""
        stetho_str = "_stetho" if req.stethoscope_mode else ""
        pcg_display = f"模拟PCG_{req.ecg_rhythm}{abnorm_str}_{req.heart_rate:.0f}bpm_{pcg_actual_sr}Hz{stetho_str}.wav"

        pcg_file = MediaFile(
            id=uid_pcg,
            project_id=uuid.UUID(req.project_id),
            filename=pcg_fname,
            original_filename=pcg_display,
            file_type="pcg",
            file_size=pcg_size,
            file_path=f"{req.project_id}/{pcg_fname}",
            storage_backend="local",
            duration=req.duration,
            sample_rate=float(pcg_actual_sr),
            channels=1,
        )
        db.add(pcg_file)
        await db.flush()
        pcg_file_id = str(uid_pcg)
        pcg_fname_out = pcg_display

        if req.auto_detect:
            abnorm_set = set(req.pcg_abnormalities)
            pcg_anns = _pcg_annotations_from_peaks(
                r_peaks, req.duration,
                heart_rate=req.heart_rate,
                abnorm=abnorm_set,
            )
            for d in pcg_anns:
                db.add(Annotation(
                    file_id=uid_pcg,
                    user_id=current_user.id,
                    **d,
                ))
            pcg_ann_count = len(pcg_anns)

    await db.commit()

    # ── 自动创建 ECG+PCG 关联 ──────────────────────────────────────────────
    assoc_id: Optional[str] = None
    if pcg_file_id:
        try:
            from app.models.project import FileAssociation
            assoc = FileAssociation(
                id=uuid.uuid4(),
                project_id=uuid.UUID(req.project_id),
                created_by=current_user.id,
                name=f"模拟生成关联 — {req.ecg_rhythm} {req.heart_rate:.0f}bpm",
                ecg_file_id=uid_ecg,
                pcg_file_id=uuid.UUID(pcg_file_id),
                video_file_id=None,
                pcg_offset=0.0,
                video_offset=0.0,
                notes="由模拟生成自动关联（ECG+PCG 同步生成，偏移为 0）",
            )
            db.add(assoc)
            await db.commit()
            assoc_id = str(assoc.id)
        except Exception as e:
            # 关联失败不影响主流程，但记录错误信息
            import logging
            logging.getLogger(__name__).warning("模拟生成：自动创建关联失败: %s", e)
            await db.rollback()

    return SimulateResult(
        ecg_file_id=str(uid_ecg),
        ecg_filename=display_name,
        pcg_file_id=pcg_file_id,
        pcg_filename=pcg_fname_out,
        duration=req.duration,
        heart_rate=req.heart_rate,
        rhythm=req.ecg_rhythm,
        r_peak_count=int(len(r_peaks)),
        ecg_annotation_count=ecg_ann_count,
        pcg_annotation_count=pcg_ann_count,
        association_id=assoc_id,
    )

"""诊断2: 分析 _detrend_template_baseline 对 T 波的影响"""
import numpy as np
from app.api.v1.endpoints import simulate as sim

# neurokit2 原始模板 (60bpm 参考)
import neurokit2 as nk
ecg_ref = nk.ecg_simulate(duration=15, sampling_rate=500, heart_rate=60, noise=0, method="ecgsyn")
_, info = nk.ecg_process(ecg_ref, sampling_rate=500)
peaks = info["ECG_R_Peaks"]
rp = peaks[len(peaks) // 2]
pre = int(0.25 * 500)
post = int(0.55 * 500)
raw = ecg_ref[rp - pre : rp + post].astype(np.float32)

print("=== Linear detrend 的问题 ===")
print(f"raw 首5个均值: {np.mean(raw[:5]):.4f}")
print(f"raw 尾5个均值: {np.mean(raw[-5:]):.4f}")
print(f"线性 ramp: 从 {np.mean(raw[:5]):.4f} 到 {np.mean(raw[-5:]):.4f}")
print()

# detrend 的 ramp
head_bl = float(np.mean(raw[:5]))
tail_bl = float(np.mean(raw[-5:]))
ramp = np.linspace(head_bl, tail_bl, len(raw), dtype=np.float32)

# ramp 在 R 峰处的值
print(f"ramp[r_off={pre}] = {ramp[pre]:.4f}")
print(f"raw R peak: {raw[pre]:.4f}")
print(f"detrended R peak: {raw[pre] - ramp[pre]:.4f}")
print()

# ramp 在 T 波区域的值
t_idx = pre + 140  # ~280ms after R, T wave peak region
print(f"ramp at T wave region (idx {t_idx}): {ramp[t_idx]:.4f}")
print(f"raw T wave: {raw[t_idx]:.4f}")
print(f"detrended T wave: {raw[t_idx] - ramp[t_idx]:.4f}")
print()

# ramp 在 P 波区域的值
p_idx = pre - 60  # ~120ms before R, P wave peak region
print(f"ramp at P wave region (idx {p_idx}): {ramp[p_idx]:.4f}")
print(f"raw P wave: {raw[p_idx]:.4f}")
print(f"detrended P wave: {raw[p_idx] - ramp[p_idx]:.4f}")
print()

print("=== 问题分析 ===")
print("线性 detrend 的 ramp 从首端(正值)线性下降到尾端(负值/接近零)")
print("在 T 波区域, ramp 接近零或较小 → T 波几乎不受影响")
print("在 P 波区域, ramp 是较大正值 → P 波被显著压低")
print("这造成 P 波被过度削弱, 但 T 波保持不变")
print()

# 实际上, 如果尾端本身不为零（T波残余），那 detrend 是对的
# 但真正问题可能在别处。让我看看 neurokit2 原始 T/R 比
# neurokit2 ECGSYN 的 T 波本身就偏高（约 0.37 * R）
# 标准 ECG: T 波约 R 峰的 1/8 到 1/3
# 所以 T/R=0.37 确实在正常高端，但不算异常

# 但 P 波的问题:
# detrend 后 P/R = 0.132, 正常范围
# 但 _build_beat_template 最终输出 P/R = 0.179 @ 72bpm
# 差异来自 _adapt_template_to_hr!

print("=== _adapt_template_to_hr 对 P 波的影响 ===")
detrended = sim._detrend_template_baseline(raw.copy())
# 72bpm adapt
adapted, new_pre = sim._adapt_template_to_hr(detrended, pre, 500, 72.0)
print(f"pre(60bpm)={pre}, new_pre(72bpm)={new_pre}")
print(f"PR factor = 0.7 + 0.3 * {60/72:.3f} = {0.7 + 0.3 * 60/72:.3f}")
print(f"Pre 段: {pre} → {new_pre} samples (压缩比 {new_pre/pre:.3f})")
print("当 pre 段被压缩时, P 波的幅度应保持不变(interp只改时间不改幅度)")
print("但压缩后 P 波'尖'了 → 看起来更突出")
print()

# 关键: 看看 P 波在模板中的绝对位置和边缘关系
print("=== 72bpm 模板中 P 波的详细分析 ===")
final_tpl, final_r_off = sim._build_beat_template(500, 72.0)
print(f"final template: len={len(final_tpl)}, r_off={final_r_off}")

# P 波峰值位置
p_region = final_tpl[:final_r_off]
p_peak_idx = np.argmax(p_region[10:]) + 10  # 跳过首端 fade
p_peak_val = p_region[p_peak_idx]
print(f"P wave peak: idx={p_peak_idx}, val={p_peak_val:.4f}")
print(f"P wave onset distance from start: {p_peak_idx} samples = {p_peak_idx/500*1000:.0f}ms")
print(f"P wave distance before R peak: {final_r_off - p_peak_idx} samples = {(final_r_off - p_peak_idx)/500*1000:.0f}ms")
print()

# 总结
print("=== 总结 ===")
print(f"P/R = {p_peak_val/final_tpl[final_r_off]:.3f} (期望 0.08-0.15)")
print(f"T/R = {np.max(final_tpl[final_r_off+60:]):.3f}/{final_tpl[final_r_off]:.3f} = {np.max(final_tpl[final_r_off+60:])/final_tpl[final_r_off]:.3f} (期望 0.15-0.30)")
print()
print("问题:")
print("1. T/R 比 0.39 偏高（正常上限约 0.30）")
print("2. P/R 比 0.18 偏高（正常上限约 0.15）")
print("3. 但用户说'P 比 T 高得多' → 这可能是因为 detrend 后 P/T=0.46")
print("   这意味着 P 波接近 T 波的一半, 在视觉上确实 P 波显得过高")

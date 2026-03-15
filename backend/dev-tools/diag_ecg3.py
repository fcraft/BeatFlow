"""诊断3: 精确定位 P 波位置，检查线性 detrend 的实际效果"""
import numpy as np
from app.api.v1.endpoints import simulate as sim

# _build_beat_template 全流程输出
tpl, r_off = sim._build_beat_template(500, 72.0)
print(f"Template len={len(tpl)}, r_off={r_off}")

# 打印模板的前半段(R 峰之前)逐段值
print("\n=== R 峰前区域 (每 10 samples 的 max) ===")
for i in range(0, r_off, 10):
    seg = tpl[i:min(i+10, r_off)]
    print(f"  [{i:3d}:{min(i+10,r_off):3d}] max={np.max(seg):+.4f}  min={np.min(seg):+.4f}  "
          f"({(r_off-i)/500*1000:.0f}ms before R)")

print(f"\n=== R 峰区域 ===")
for i in range(max(0, r_off-5), min(len(tpl), r_off+10)):
    print(f"  tpl[{i}] = {tpl[i]:+.4f} {'<-- R peak (r_off)' if i == r_off else ''}")

print(f"\n=== R 峰后区域 (每 10 samples 的 max/min) ===")
for i in range(r_off, len(tpl), 20):
    seg = tpl[i:min(i+20, len(tpl))]
    print(f"  [{i:3d}:{min(i+20,len(tpl)):3d}] max={np.max(seg):+.4f}  min={np.min(seg):+.4f}  "
          f"({(i-r_off)/500*1000:.0f}ms after R)")

# 现在检查 neurokit2 原始模板中真正的 P 波
print("\n=== neurokit2 RAW template (60bpm, 无处理) ===")
import neurokit2 as nk
ecg_ref = nk.ecg_simulate(duration=15, sampling_rate=500, heart_rate=60, noise=0, method="ecgsyn")
_, info = nk.ecg_process(ecg_ref, sampling_rate=500)
peaks = info["ECG_R_Peaks"]
rp = peaks[len(peaks) // 2]
pre = 125
post = 275
raw = ecg_ref[rp - pre : rp + post].astype(np.float32)

# P 波在 neurokit2 ECGSYN 中约在 R 峰前 120-160ms
# 即 index 125 - 80 = 45 到 125 - 60 = 65
print("P wave region (raw, 60-200ms before R):")
for i in range(0, 100, 10):
    seg = raw[i:min(i+10, 100)]
    print(f"  [{i:3d}:{min(i+10,100):3d}] max={np.max(seg):+.4f}  min={np.min(seg):+.4f}")

# 检查 detrend 后
detrended = sim._detrend_template_baseline(raw.copy())
print("\nP wave region (after detrend):")
for i in range(0, 100, 10):
    seg = detrended[i:min(i+10, 100)]
    print(f"  [{i:3d}:{min(i+10,100):3d}] max={np.max(seg):+.4f}  min={np.min(seg):+.4f}")

# 找到 detrend 前后真正的 P 波 peak
print(f"\nraw P region [25:85] peak: {np.max(raw[25:85]):.4f} at {25+np.argmax(raw[25:85])}")
print(f"detrended P region [25:85] peak: {np.max(detrended[25:85]):.4f} at {25+np.argmax(detrended[25:85])}")
print(f"raw T region [185:265] peak: {np.max(raw[185:265]):.4f}")
print(f"detrended T region [185:265] peak: {np.max(detrended[185:265]):.4f}")
print(f"raw R: {raw[125]:.4f}")
print(f"detrended R: {detrended[125]:.4f}")

print("\n=== 线性 detrend 的 ramp 值 ===")
h = float(np.mean(raw[:5]))
t_val = float(np.mean(raw[-5:]))
ramp = np.linspace(h, t_val, len(raw))
print(f"head_baseline={h:.4f}, tail_baseline={t_val:.4f}")
print(f"ramp at P wave (~idx 55): {ramp[55]:.4f}")
print(f"ramp at R peak (idx 125): {ramp[125]:.4f}")
print(f"ramp at T wave (~idx 225): {ramp[225]:.4f}")
print(f"ramp at tail (idx 395): {ramp[395]:.4f}")

# 关键问题: detrend ramp 在 P 波区域减了多少?
p_raw = raw[55]
p_detrended = detrended[55]
print(f"\nP 波 (idx 55): raw={p_raw:.4f}, ramp={ramp[55]:.4f}, detrended={p_detrended:.4f}")
print(f"P 波被 detrend 减去了 {ramp[55]:.4f}")
print(f"如果 P 波 raw 值本身只有 ~0.10-0.18, 被减去 ~0.12 后会变成接近 0 甚至负值!")

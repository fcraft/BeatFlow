"""验证修复: 检查 P/T/R 波幅度比例"""
import numpy as np
from app.api.v1.endpoints import simulate as sim

print("=" * 60)
print("模板路径 (_build_beat_template)")
print("=" * 60)
for hr in [60.0, 72.0, 90.0, 120.0]:
    tpl, r_off = sim._build_beat_template(500, hr)
    r_max = np.max(tpl)
    
    # P 波: R 峰前 40-200ms
    p_s = max(0, r_off - int(0.20 * 500))
    p_e = max(0, r_off - int(0.04 * 500))
    p_max = np.max(tpl[p_s:p_e]) if p_e > p_s else 0
    
    # T 波: R 峰后 100-400ms
    t_s = min(len(tpl), r_off + int(0.10 * 500))
    t_e = min(len(tpl), r_off + int(0.40 * 500))
    t_max = np.max(tpl[t_s:t_e]) if t_e > t_s else 0
    
    ok_p = "✓" if 0.05 <= p_max / r_max <= 0.18 else "✗"
    ok_t = "✓" if 0.10 <= t_max / r_max <= 0.32 else "✗"
    ok_pt = "✓" if t_max > p_max else "✗"
    
    print(f"  HR={hr:3.0f}bpm: R={r_max:.3f}  P={p_max:.3f}  T={t_max:.3f}  "
          f"P/R={p_max/r_max:.3f}{ok_p}  T/R={t_max/r_max:.3f}{ok_t}  T>P:{ok_pt}")

print()
print("=" * 60)
print("ecgsyn 直接路径 (_simulate_ecg_ecgsyn)")
print("=" * 60)
rng = np.random.default_rng(42)
ecg, rpeaks = sim._simulate_ecg_ecgsyn("normal", 72.0, 2.0, 10.0, 0.01, rng)
# 分析几个拍
for idx in [2, 4, 6]:
    if idx >= len(rpeaks):
        break
    rp = rpeaks[idx]
    r_val = ecg[rp]
    
    p_s = max(0, rp - 90)
    p_e = max(0, rp - 20)
    t_s = min(len(ecg), rp + 50)
    t_e = min(len(ecg), rp + 200)
    
    p_max = np.max(ecg[p_s:p_e]) if p_e > p_s else 0
    t_max = np.max(ecg[t_s:t_e]) if t_e > t_s else 0
    
    print(f"  Beat {idx}: R={r_val:.3f}  P={p_max:.3f}  T={t_max:.3f}  "
          f"P/R={p_max/r_val:.3f}  T/R={t_max/r_val:.3f}  P/T={p_max/t_max:.3f}")

print()
print("=" * 60)
print("模板叠加路径 (_synthesize_ecg)")
print("=" * 60)
rng2 = np.random.default_rng(42)
rpeaks2 = sim._regular_r_peaks(10.0, 72.0, 2.0, 500, rng2)
rng3 = np.random.default_rng(42)
ecg2 = sim._synthesize_ecg(rpeaks2, 10.0, 500, 0.01, heart_rate=72.0, rng=rng3)
for idx in [2, 4, 6]:
    if idx >= len(rpeaks2):
        break
    rp = rpeaks2[idx]
    r_val = ecg2[rp]
    
    p_s = max(0, rp - 90)
    p_e = max(0, rp - 20)
    t_s = min(len(ecg2), rp + 50)
    t_e = min(len(ecg2), rp + 200)
    
    p_max = np.max(ecg2[p_s:p_e]) if p_e > p_s else 0
    t_max = np.max(ecg2[t_s:t_e]) if t_e > t_s else 0
    
    print(f"  Beat {idx}: R={r_val:.3f}  P={p_max:.3f}  T={t_max:.3f}  "
          f"P/R={p_max/r_val:.3f}  T/R={t_max/r_val:.3f}  P/T={p_max/t_max:.3f}")

print()
print("=" * 60)
print("Fallback synthetic template")
print("=" * 60)
tpl, r_off = sim._synthetic_template(500)
adapted, new_off = sim._adapt_template_to_hr(tpl, r_off, 500, 72.0)
adapted = sim._normalize_wave_amplitudes(adapted, new_off, 500)
adapted = sim._fade_template_edges(adapted, sr=500)
r_max = np.max(adapted)
p_s = max(0, new_off - 100)
p_e = max(0, new_off - 20)
p_max = np.max(adapted[p_s:p_e]) if p_e > p_s else 0
t_s = min(len(adapted), new_off + 50)
t_e = min(len(adapted), new_off + 200)
t_max = np.max(adapted[t_s:t_e]) if t_e > t_s else 0
print(f"  R={r_max:.3f}  P={p_max:.3f}  T={t_max:.3f}  "
      f"P/R={p_max/r_max:.3f}  T/R={t_max/r_max:.3f}  P/T={p_max/t_max:.3f}")

print()
print("Target ranges: P/R=0.08-0.15  T/R=0.15-0.30  P < T")

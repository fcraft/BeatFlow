"""诊断4: 确认最终输出 P/T 比例问题 - 模拟实际 _synthesize_ecg 输出"""
import numpy as np
from app.api.v1.endpoints import simulate as sim

# 模拟 72bpm 正常心律 10 秒
rng = np.random.default_rng(42)
r_peaks = sim._regular_r_peaks(10.0, 72.0, 2.0, 500, rng)
rng2 = np.random.default_rng(42)
ecg = sim._synthesize_ecg(r_peaks, 10.0, 500, 0.01, heart_rate=72.0, rng=rng2)

# 对齐到第3个 R 峰，分析 P/T/R
rp = r_peaks[3]
pre = 200  # 分析窗口: R 峰前 400ms
post = 300  # R 峰后 600ms
if rp - pre >= 0 and rp + post < len(ecg):
    seg = ecg[rp-pre:rp+post]
    
    print(f"R peak at sample {rp}")
    print(f"R peak amplitude: {ecg[rp]:.4f}")
    
    # P 波: R 峰前 80-180ms (idx 100-140 in segment)
    p_region = seg[pre-90:pre-30]
    p_max = np.max(p_region)
    p_idx = pre-90+np.argmax(p_region)
    
    # T 波: R 峰后 120-350ms
    t_region = seg[pre+60:pre+175]
    t_max = np.max(t_region)
    t_idx = pre+60+np.argmax(t_region)
    
    r_val = seg[pre]
    
    print(f"\n在合成 ECG 信号中:")
    print(f"  R = {r_val:.4f}")
    print(f"  P = {p_max:.4f} ({(pre-p_idx)/500*1000:.0f}ms before R)")
    print(f"  T = {t_max:.4f} ({(t_idx-pre)/500*1000:.0f}ms after R)")
    print(f"  P/R = {p_max/r_val:.3f}")
    print(f"  T/R = {t_max/r_val:.3f}")
    print(f"  P/T = {p_max/t_max:.3f}")
    
    # 也看看归一化后
    peak = np.max(np.abs(ecg))
    ecg_norm = ecg / peak * 0.85
    seg_norm = ecg_norm[rp-pre:rp+post]
    print(f"\n归一化后:")
    print(f"  R = {seg_norm[pre]:.4f}")
    print(f"  P = {np.max(seg_norm[pre-90:pre-30]):.4f}")
    print(f"  T = {np.max(seg_norm[pre+60:pre+175]):.4f}")

# 与 _simulate_ecg_ecgsyn 比较 (这是 simple rhythms 用的路径)
print("\n=== _simulate_ecg_ecgsyn 路径 (neurokit2 直接生成) ===")
rng3 = np.random.default_rng(42)
try:
    ecg2, r2 = sim._simulate_ecg_ecgsyn("normal", 72.0, 2.0, 10.0, 0.01, rng3)
    rp2 = r2[3]
    if rp2 - pre >= 0 and rp2 + post < len(ecg2):
        seg2 = ecg2[rp2-pre:rp2+post]
        r_val2 = seg2[pre]
        p_max2 = np.max(seg2[pre-90:pre-30])
        t_max2 = np.max(seg2[pre+60:pre+175])
        print(f"  R = {r_val2:.4f}")
        print(f"  P = {p_max2:.4f}")
        print(f"  T = {t_max2:.4f}")
        print(f"  P/R = {p_max2/r_val2:.3f}")
        print(f"  T/R = {t_max2/r_val2:.3f}")
        print(f"  P/T = {p_max2/t_max2:.3f}")
except Exception as e:
    print(f"  Error: {e}")

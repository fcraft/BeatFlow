"""ECG 模板诊断: 分析 P/T/R 波幅度比例"""
import numpy as np
from app.api.v1.endpoints import simulate as sim

for hr in [60.0, 72.0, 90.0, 120.0]:
    tpl, r_off = sim._build_beat_template(500, hr)
    
    r_val = tpl[r_off]
    r_max_idx = np.argmax(tpl)
    r_max = tpl[r_max_idx]
    
    # P 波区域: R 峰前 60-200ms
    p_start = max(0, r_off - int(0.20 * 500))
    p_end = max(0, r_off - int(0.06 * 500))
    if p_end > p_start:
        p_region = tpl[p_start:p_end]
        p_max = np.max(p_region)
        p_max_idx = p_start + np.argmax(p_region)
    else:
        p_max, p_max_idx = 0, 0
    
    # T 波区域: R 峰后 120-350ms
    t_start = min(len(tpl), r_off + int(0.12 * 500))
    t_end = min(len(tpl), r_off + int(0.35 * 500))
    if t_end > t_start:
        t_region = tpl[t_start:t_end]
        t_max = np.max(t_region)
        t_max_idx = t_start + np.argmax(t_region)
    else:
        t_max, t_max_idx = 0, 0
    
    # S 波
    s_start = r_off + 1
    s_end = min(len(tpl), r_off + int(0.04 * 500))
    s_min = np.min(tpl[s_start:s_end]) if s_end > s_start else 0
    
    print(f'=== HR={hr:.0f}bpm ===')
    print(f'  Template: len={len(tpl)}, r_off={r_off}')
    print(f'  R peak: tpl[{r_off}]={r_val:.4f}, max={r_max:.4f} at idx={r_max_idx}')
    print(f'  P wave: max={p_max:.4f} at idx={p_max_idx}')
    print(f'  T wave: max={t_max:.4f} at idx={t_max_idx}')
    print(f'  S wave: min={s_min:.4f}')
    if r_max > 0 and t_max > 0:
        print(f'  Ratios: P/R={p_max/r_max:.3f}, T/R={t_max/r_max:.3f}, P/T={p_max/t_max:.3f}')
    print(f'  Expected: P/R~0.10-0.15, T/R~0.15-0.30, P/T~0.4-0.6')
    print()

# 也看看 detrend 之前的原始 neurokit2 模板
print('=== RAW neurokit2 (before detrend) ===')
try:
    import neurokit2 as nk
    ecg_ref = nk.ecg_simulate(duration=15, sampling_rate=500, heart_rate=60, noise=0, method="ecgsyn")
    _, info = nk.ecg_process(ecg_ref, sampling_rate=500)
    peaks = info["ECG_R_Peaks"]
    rp = peaks[len(peaks) // 2]
    pre = int(0.25 * 500)
    post = int(0.55 * 500)
    raw_tpl = ecg_ref[rp - pre : rp + post].astype(np.float32)
    r_off_raw = pre
    r_max_raw = raw_tpl[r_off_raw]
    
    p_s = max(0, r_off_raw - 100)
    p_e = max(0, r_off_raw - 30)
    p_max_raw = np.max(raw_tpl[p_s:p_e])
    
    t_s = min(len(raw_tpl), r_off_raw + 60)
    t_e = min(len(raw_tpl), r_off_raw + 175)
    t_max_raw = np.max(raw_tpl[t_s:t_e])
    
    print(f'  R={r_max_raw:.4f}, P={p_max_raw:.4f}, T={t_max_raw:.4f}')
    print(f'  P/R={p_max_raw/r_max_raw:.3f}, T/R={t_max_raw/r_max_raw:.3f}, P/T={p_max_raw/t_max_raw:.3f}')
    
    # After detrend only
    detrended = sim._detrend_template_baseline(raw_tpl.copy())
    r_det = detrended[r_off_raw]
    p_det = np.max(detrended[p_s:p_e])
    t_det = np.max(detrended[t_s:t_e])
    print(f'\n  After detrend only:')
    print(f'  R={r_det:.4f}, P={p_det:.4f}, T={t_det:.4f}')
    print(f'  P/R={p_det/r_det:.3f}, T/R={t_det/r_det:.3f}, P/T={p_det/t_det:.3f}')
    
    # After detrend + adapt (72bpm)
    adapted, new_r_off = sim._adapt_template_to_hr(detrended, r_off_raw, 500, 72.0)
    r_adapt = adapted[new_r_off] if new_r_off < len(adapted) else np.max(adapted)
    p_s2 = max(0, new_r_off - 100)
    p_e2 = max(0, new_r_off - 30)
    p_adapt = np.max(adapted[p_s2:p_e2]) if p_e2 > p_s2 else 0
    t_s2 = min(len(adapted), new_r_off + 60)
    t_e2 = min(len(adapted), new_r_off + 175)
    t_adapt = np.max(adapted[t_s2:t_e2]) if t_e2 > t_s2 else 0
    print(f'\n  After detrend + adapt (72bpm):')
    print(f'  R={r_adapt:.4f}, P={p_adapt:.4f}, T={t_adapt:.4f}')
    if r_adapt > 0 and t_adapt > 0:
        print(f'  P/R={p_adapt/r_adapt:.3f}, T/R={t_adapt/r_adapt:.3f}, P/T={p_adapt/t_adapt:.3f}')
    
    # After detrend + adapt + fade
    faded = sim._fade_template_edges(adapted.copy(), sr=500)
    r_faded = faded[new_r_off] if new_r_off < len(faded) else np.max(faded)
    p_faded = np.max(faded[p_s2:p_e2]) if p_e2 > p_s2 else 0
    t_faded = np.max(faded[t_s2:t_e2]) if t_e2 > t_s2 else 0
    print(f'\n  After detrend + adapt + fade (=_build_beat_template):')
    print(f'  R={r_faded:.4f}, P={p_faded:.4f}, T={t_faded:.4f}')
    if r_faded > 0 and t_faded > 0:
        print(f'  P/R={p_faded/r_faded:.3f}, T/R={t_faded/r_faded:.3f}, P/T={p_faded/t_faded:.3f}')
        
except Exception as e:
    print(f'  neurokit2 error: {e}')

# Synthetic (fallback)
print('\n=== SYNTHETIC TEMPLATE (fallback) ===')
tpl, r_off = sim._synthetic_template(500)
r_max = tpl[r_off]
p_s = max(0, r_off - 100)
p_e = max(0, r_off - 30)
p_max = np.max(tpl[p_s:p_e]) if p_e > p_s else 0
t_s = min(len(tpl), r_off + 60)
t_e = min(len(tpl), r_off + 175)
t_max = np.max(tpl[t_s:t_e]) if t_e > t_s else 0
print(f'  R={r_max:.4f}, P={p_max:.4f}, T={t_max:.4f}')
if r_max > 0 and t_max > 0:
    print(f'  P/R={p_max/r_max:.3f}, T/R={t_max/r_max:.3f}, P/T={p_max/t_max:.3f}')

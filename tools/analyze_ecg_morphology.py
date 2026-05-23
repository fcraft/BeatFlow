#!/usr/bin/env python3
"""Analyze ECG morphology from full pipeline — detect shape issues.

Usage:
  PYTHONPATH=backend .venv/bin/python tools/analyze_ecg_morphology.py
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'backend'))

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from app.engine.core.parametric_conduction import ParametricConductionNetwork
from app.engine.core.ecg_synthesizer import EcgSynthesizerV2
from app.engine.core.types import Modifiers
from app.engine.core.morph_variance import MorphVarianceConfig, generate_random_variance
from app.engine.core.ecg_morph_library import MORPH_LIBRARY
from scipy.signal import find_peaks

SR = 500
LEAD_ORDER = ['I', 'II', 'III', 'aVR', 'aVL', 'aVF',
              'V1', 'V2', 'V3', 'V4', 'V5', 'V6']

OUTPUT_DIR = Path(__file__).resolve().parent.parent / 'exports' / 'ecg_analysis'
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def generate_ecg(synth, conduction_net, modifiers, n_beats=3, base_hr=72.0,
                 active_morph=None, morph_variance=None, st_evolution=None):
    """Generate n_beats of 12-lead ECG."""
    synth.active_morph = active_morph
    synth.morph_variance = morph_variance
    synth.st_evolution = st_evolution

    all_samples = {lead: [] for lead in LEAD_ORDER}
    for i in range(n_beats):
        rr_sec = 60.0 / base_hr
        conduction = conduction_net.propagate(rr_sec, modifiers)
        frame = synth.synthesize(conduction, LEAD_ORDER, modifiers)
        for lead in LEAD_ORDER:
            all_samples[lead].append(frame.samples.get(lead, np.zeros(0)))
    return {lead: np.concatenate(all_samples[lead]) for lead in LEAD_ORDER}


def detect_fiducial(signal, sr=SR):
    """Detect R-peaks, QRS onset/offset, T-wave peak via simple peak detection."""
    # R peaks: find maxima > 60% of max
    r_peaks, props = find_peaks(signal, height=np.max(signal) * 0.5, distance=int(0.2 * sr))
    if len(r_peaks) == 0:
        return None

    # Use middle beat for measurements
    mid = len(r_peaks) // 2
    r = r_peaks[mid]

    # QRS onset: search backward from R for first zero-crossing or derivative sign change
    qrs_start = r - int(0.05 * sr)  # default -50ms
    for j in range(r - 1, max(0, r - int(0.12 * sr)), -1):
        if signal[j] * signal[j - 1] <= 0 or abs(signal[j] - signal[j - 1]) < 1e-6:
            qrs_start = j
            break

    # QRS end: search forward from R
    qrs_end = r + int(0.05 * sr)  # default +50ms
    for j in range(r + 1, min(len(signal), r + int(0.12 * sr))):
        if abs(signal[j]) < abs(signal[r]) * 0.05:
            qrs_end = j
            break

    # T-wave peak: max between QRS end and next R wave (or end)
    t_end = min(r_peaks[mid + 1] - int(0.15 * sr), len(signal)) if mid + 1 < len(r_peaks) else len(signal)
    t_window = signal[qrs_end:t_end]
    if len(t_window) > 20:
        t_peak = qrs_end + np.argmax(t_window)
    else:
        t_peak = qrs_end + int(0.2 * sr)

    # P-wave: search before QRS
    p_search_end = qrs_start
    p_search_start = max(0, r - int(0.3 * sr))
    p_window = signal[p_search_start:p_search_end]
    if len(p_window) > 10:
        p_peak = p_search_start + np.argmax(p_window)
    else:
        p_peak = qrs_start - int(0.1 * sr)

    return {
        'r_peak': r,
        'r_amplitude': float(signal[r]),
        'qrs_onset': qrs_start,
        'qrs_end': qrs_end,
        'qrs_duration_ms': (qrs_end - qrs_start) / sr * 1000,
        't_peak': t_peak,
        't_amplitude': float(signal[t_peak]) if t_peak < len(signal) else 0.0,
        'p_peak': p_peak,
        'p_amplitude': float(signal[p_peak]) if p_peak < len(signal) else 0.0,
        'st_level_mv': float(np.mean(signal[qrs_end + 5: qrs_end + int(0.04 * sr)])) if qrs_end + int(0.04 * sr) < len(signal) else 0.0,
    }


def analyze_morphology(label, ecg_dict):
    """Analyze morphology of all 12 leads, print report."""
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"{'='*60}")

    fiducials = {}
    for lead in LEAD_ORDER:
        fid = detect_fiducial(ecg_dict[lead])
        if fid:
            fiducials[lead] = fid

    if not fiducials:
        print("  ERROR: No R-peaks detected!")
        return fiducials

    # Einthoven check
    lead_i = ecg_dict['I']
    lead_ii = ecg_dict['II']
    lead_iii = ecg_dict['III']
    min_len = min(len(lead_i), len(lead_ii), len(lead_iii))
    diff = np.max(np.abs(lead_iii[:min_len] - (lead_ii[:min_len] - lead_i[:min_len])))
    print(f"  Einthoven max error: {diff:.4f} mV {'OK' if diff < 0.05 else 'FAIL'}")

    # aVR check (should be mostly negative)
    avr_negative_ratio = np.sum(ecg_dict['aVR'] < -0.05) / max(1, len(ecg_dict['aVR']))
    area_under_negative = -np.sum(ecg_dict['aVR'][ecg_dict['aVR'] < 0])
    area_under_positive = np.sum(ecg_dict['aVR'][ecg_dict['aVR'] > 0])
    print(f"  aVR negative sample ratio: {avr_negative_ratio:.1%}")
    print(f"  aVR neg/pos area ratio: {area_under_negative / max(area_under_positive, 1e-9):.1f}x {'OK' if area_under_negative > area_under_positive else 'WARN'}")

    # Per-lead analysis
    print(f"\n  {'Lead':<6} {'R-amp(mV)':>10} {'QRS(ms)':>8} {'T-amp(mV)':>10} {'P-amp(mV)':>10} {'ST(mV)':>8}")
    print(f"  {'-'*55}")
    for lead in LEAD_ORDER:
        f = fiducials.get(lead)
        if f:
            print(f"  {lead:<6} {f['r_amplitude']:>+10.3f} {f['qrs_duration_ms']:>8.1f} "
                  f"{f['t_amplitude']:>+10.3f} {f['p_amplitude']:>+10.3f} {f['st_level_mv']:>+8.3f}")
        else:
            print(f"  {lead:<6} {'N/A':>10} {'N/A':>8} {'N/A':>10} {'N/A':>10} {'N/A':>8}")

    # Precordial R-wave progression check
    v_leads = ['V1', 'V2', 'V3', 'V4', 'V5', 'V6']
    r_amps = [fiducials.get(v, {}).get('r_amplitude', 0) for v in v_leads]
    print(f"\n  Precordial R progression: {' → '.join(f'{a:.2f}' for a in r_amps)}")

    # Check for monotonic progression
    increasing = all(r_amps[i] <= r_amps[i + 1] for i in range(len(r_amps) - 1))
    print(f"  R monotonic? {'YES' if increasing else 'NO (abnormal transition)'}")

    # QRS axis (simplified: I vs aVF)
    r_i = fiducials.get('I', {}).get('r_amplitude', 0)
    r_avf = fiducials.get('aVF', {}).get('r_amplitude', 0)
    axis = np.degrees(np.arctan2(r_avf, r_i)) if abs(r_i) > 1e-6 else 90
    print(f"  QRS axis (I/aVF): {axis:.0f}° {'OK (0-90°)' if -30 <= axis <= 90 else 'ABNORMAL'}")

    return fiducials


def plot_12_lead_with_fiducials(ecg_dict, fiducials, output_path, title):
    """Plot 12-lead ECG with fiducial markers."""
    fig, axes = plt.subplots(6, 2, figsize=(18, 20))
    fig.suptitle(title, fontsize=13, fontweight='bold')

    for idx, lead in enumerate(LEAD_ORDER):
        row, col = idx // 2, idx % 2
        ax = axes[row, col]
        signal = ecg_dict[lead]
        t = np.arange(len(signal)) / SR
        ax.plot(t, signal, linewidth=0.5, color='black')

        f = fiducials.get(lead)
        if f:
            ax.axvline(t[f['r_peak']], color='red', alpha=0.4, linewidth=1, linestyle='--')
            ax.axvline(t[f['qrs_onset']], color='green', alpha=0.4, linewidth=0.8, linestyle=':')
            ax.axvline(t[f['qrs_end']], color='green', alpha=0.4, linewidth=0.8, linestyle=':')
            ax.axvline(t[f['t_peak']], color='blue', alpha=0.4, linewidth=0.8, linestyle=':')
            ax.axvline(t[f['p_peak']], color='orange', alpha=0.4, linewidth=0.8, linestyle=':')
            ax.plot(t[f['r_peak']], f['r_amplitude'], 'ro', markersize=3)
            ax.plot(t[f['t_peak']], f['t_amplitude'], 'b.', markersize=3)

        ax.set_ylabel(lead, fontsize=9, rotation=0, labelpad=20)
        ax.set_ylim(-2.5, 2.5)
        ax.grid(True, alpha=0.2)
        if len(t) > 0:
            ax.set_xlim(0, t[-1])

    axes[-1, 0].set_xlabel('Time (s)')
    axes[-1, 1].set_xlabel('Time (s)')
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  Plot saved: {output_path}")


def main():
    print("Initializing pipeline components...")
    conduction_net = ParametricConductionNetwork()
    synth = EcgSynthesizerV2(sample_rate=SR)
    modifiers = Modifiers()
    base_hr = 72.0

    # ---- 1. Baseline normal sinus ----
    print("\n>>> Generating baseline ECG...")
    ecg_baseline = generate_ecg(synth, conduction_net, modifiers, n_beats=4, base_hr=base_hr)
    fid_baseline = analyze_morphology("1. Baseline Normal Sinus Rhythm (72 BPM)", ecg_baseline)
    plot_12_lead_with_fiducials(ecg_baseline, fid_baseline,
                                OUTPUT_DIR / '01_baseline_normal.png',
                                '01 — Baseline Normal Sinus Rhythm (72 BPM)')

    # ---- 2. With individual variance ----
    print("\n>>> Generating ECG with individual variance...")
    variance = generate_random_variance(seed=42)
    ecg_var = generate_ecg(synth, conduction_net, modifiers, n_beats=4, base_hr=base_hr,
                           morph_variance=variance)
    fid_var = analyze_morphology(f"2. With Variance (seed=42, axis={variance.cardiac_axis_deg:.0f}°)", ecg_var)
    plot_12_lead_with_fiducials(ecg_var, fid_var,
                                OUTPUT_DIR / '02_variance.png',
                                f'02 — Variance: axis={variance.cardiac_axis_deg:.0f}°, '
                                f'chest={variance.chest_wall_thickness:.2f}')

    # ---- 3-6. Each pathological morphology ----
    morph_list = [
        ('lbbb', '03_lbbb.png', '03 — LBBB'),
        ('rbbb', '04_rbbb.png', '04 — RBBB'),
        ('wpw', '05_wpw.png', '05 — WPW (Delta Wave)'),
        ('brugada_type1', '06_brugada1.png', '06 — Brugada Type 1'),
        ('brugada_type2', '07_brugada2.png', '07 — Brugada Type 2'),
        ('wellens', '08_wellens.png', '08 — Wellens Syndrome'),
        ('hyperkalemia', '09_hyperkalemia.png', '09 — Hyperkalemia'),
        ('hypokalemia', '10_hypokalemia.png', '10 — Hypokalemia'),
    ]

    for morph_key, filename, title in morph_list:
        print(f"\n>>> Generating {morph_key}...")
        ecg_morph = generate_ecg(synth, conduction_net, modifiers, n_beats=4, base_hr=base_hr,
                                 active_morph=morph_key)
        fid_morph = analyze_morphology(f"{title}", ecg_morph)
        plot_12_lead_with_fiducials(ecg_morph, fid_morph,
                                    OUTPUT_DIR / filename, title)

    # ---- Summary ----
    print(f"\n{'='*60}")
    print(f"  Done. All plots saved to: {OUTPUT_DIR}")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()

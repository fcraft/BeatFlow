#!/usr/bin/env python3
"""Export ECG waveform plots for morphology review.

Usage:
  python tools/export_ecg_plot.py --output exports/ecg/
  python tools/export_ecg_plot.py --beats 5 --output exports/ecg/
"""
import argparse
import os
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'backend'))


def build_mini_pipeline():
    from app.engine.core.parametric_conduction import ParametricConductionNetwork
    from app.engine.core.ecg_synthesizer import EcgSynthesizerV2
    from app.engine.core.types import Modifiers

    pipeline = type('MiniPipeline', (), {})()
    pipeline._conduction = ParametricConductionNetwork()
    pipeline._ecg_synth = EcgSynthesizerV2(sample_rate=500)
    pipeline._selected_leads = ['I', 'II', 'III', 'aVR', 'aVL', 'aVF',
                                 'V1', 'V2', 'V3', 'V4', 'V5', 'V6']
    pipeline._modifiers = Modifiers()
    pipeline._base_hr = 72.0
    return pipeline


def generate_ecg_beats(pipeline, n_beats=1):
    frames = []
    for i in range(n_beats):
        rr_sec = 60.0 / pipeline._base_hr
        conduction = pipeline._conduction.propagate(rr_sec, pipeline._modifiers)
        ecg_frame = pipeline._ecg_synth.synthesize(
            conduction, pipeline._selected_leads, pipeline._modifiers)
        frames.append(ecg_frame)
    return frames


def plot_12_lead(frames, output_path, title='12-Lead ECG'):
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
    except ImportError:
        print("Error: matplotlib not installed. Run: pip install matplotlib")
        sys.exit(1)

    lead_order = ['I', 'II', 'III', 'aVR', 'aVL', 'aVF',
                  'V1', 'V2', 'V3', 'V4', 'V5', 'V6']
    sr = 500

    all_samples = {}
    for name in lead_order:
        chunks = []
        for f in frames:
            if name in f.samples:
                chunks.append(f.samples[name])
        all_samples[name] = np.concatenate(chunks) if chunks else np.zeros(0)

    fig, axes = plt.subplots(6, 2, figsize=(16, 18))
    fig.suptitle(title, fontsize=14, fontweight='bold')

    for idx, lead in enumerate(lead_order):
        row, col = idx // 2, idx % 2
        ax = axes[row, col]
        signal = all_samples.get(lead, np.zeros(1))
        t = np.arange(len(signal)) / sr
        ax.plot(t, signal, linewidth=0.6, color='black')
        ax.set_ylabel(lead, fontsize=9)
        ax.set_ylim(-2.5, 2.5)
        ax.grid(True, alpha=0.3)
        if len(t) > 0:
            ax.set_xlim(0, t[-1])

    axes[-1, 0].set_xlabel('Time (s)')
    axes[-1, 1].set_xlabel('Time (s)')
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  Exported: {output_path}")


def main():
    parser = argparse.ArgumentParser(description='Export ECG waveform plots')
    parser.add_argument('--output', '-o', default='exports/ecg')
    parser.add_argument('--beats', type=int, default=3)
    parser.add_argument('--title', default='12-Lead ECG')
    args = parser.parse_args()

    os.makedirs(args.output, exist_ok=True)
    pipeline = build_mini_pipeline()

    print(f"Generating {args.beats} beat(s) of ECG...")
    frames = generate_ecg_beats(pipeline, args.beats)

    path = os.path.join(args.output, 'ecg_12_lead.png')
    plot_12_lead(frames, path, title=args.title)
    print(f"Done. Output: {args.output}/")


if __name__ == '__main__':
    main()

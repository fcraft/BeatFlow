#!/usr/bin/env python3
"""Export PCG audio to WAV files for blind A/B listening tests.

Usage:
  python tools/export_pcg_wav.py --mode physical --scenario rest --duration 10
  python tools/export_pcg_wav.py --ab --scenario rest --duration 10
  python tools/export_pcg_wav.py --mode physical --scenario rest --positions
  python tools/export_pcg_wav.py --murmur-kit --duration 8
"""
import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'backend'))


def build_pipeline(mode='physical'):
    """Build a minimal pipeline for WAV export."""
    from app.engine.core.parametric_conduction import ParametricConductionNetwork
    from app.engine.core.ecg_synthesizer import EcgSynthesizerV2
    from app.engine.core.parametric_pcg import ParametricPcgSynthesizer
    from app.engine.core.physical_pcg import PhysicalPcgSynthesizer
    from app.engine.core.algebraic_hemo import AlgebraicHemodynamics
    from app.engine.core.types import Modifiers

    pipeline = type('MiniPipeline', (), {})()
    pipeline._conduction = ParametricConductionNetwork()
    pipeline._ecg_synth = EcgSynthesizerV2(sample_rate=500)
    pipeline._selected_leads = ['I', 'II', 'III', 'aVR', 'aVL', 'aVF',
                                 'V1', 'V2', 'V3', 'V4', 'V5', 'V6']
    pipeline._hemo = AlgebraicHemodynamics()
    pipeline._modifiers = Modifiers()
    pipeline._base_hr = 72.0

    if mode == 'physical':
        pipeline._pcg_synth = PhysicalPcgSynthesizer()
    else:
        pipeline._pcg_synth = ParametricPcgSynthesizer()

    return pipeline


def run_beats(pipeline, n_beats):
    """Run N beats and collect PCG frames."""
    frames = []
    for i in range(n_beats):
        rr_sec = 60.0 / pipeline._base_hr
        conduction = pipeline._conduction.propagate(rr_sec, pipeline._modifiers)
        pcg_frame = pipeline._pcg_synth.synthesize(conduction, pipeline._modifiers)
        frames.append(pcg_frame)
    return frames


def export_wav(frames, output_path, position=None):
    """Export accumulated PCG samples to WAV file."""
    try:
        import soundfile as sf
    except ImportError:
        print("Error: soundfile not installed. Run: pip install soundfile")
        sys.exit(1)

    sr = 4000
    all_samples = []
    for f in frames:
        if position and position in f.channels:
            all_samples.append(f.channels[position])
        else:
            all_samples.append(f.samples)

    audio = np.concatenate(all_samples)
    peak = np.max(np.abs(audio))
    if peak > 1e-12:
        audio = audio / peak * 0.95

    sf.write(output_path, audio, sr)
    duration = len(audio) / sr
    print(f"  Exported: {output_path} ({duration:.1f}s, {sr} Hz)")


MURMUR_TYPES = [
    'aortic_stenosis', 'mitral_regurgitation', 'aortic_regurgitation',
    'mitral_stenosis', 'ventricular_septal_defect', 'patent_ductus_arteriosus',
]


def export_murmur_kit(output_dir, duration_sec, mode='physical'):
    """Export murmur examples for pathology identification test."""
    pipeline = build_pipeline(mode)
    n_beats = int(duration_sec / (60.0 / pipeline._base_hr))

    os.makedirs(output_dir, exist_ok=True)
    print(f"\nMurmur Kit ({mode} engine):")

    for mtype in MURMUR_TYPES:
        pipeline._modifiers.murmur_type = mtype
        pipeline._modifiers.murmur_severity = 0.7
        frames = run_beats(pipeline, n_beats)
        path = os.path.join(output_dir, f"murmur_{mtype}.wav")
        export_wav(frames, path)

    pipeline._modifiers.murmur_type = ''
    pipeline._modifiers.murmur_severity = 0.0
    frames = run_beats(pipeline, n_beats)
    path = os.path.join(output_dir, "normal.wav")
    export_wav(frames, path)

    key = {m: m for m in MURMUR_TYPES}
    key['normal'] = 'normal'
    with open(os.path.join(output_dir, 'key.json'), 'w') as f:
        json.dump(key, f, indent=2)
    print(f"  Key file: {output_dir}/key.json")


def main():
    parser = argparse.ArgumentParser(description='Export PCG WAV for auditory evaluation')
    parser.add_argument('--mode', default='physical', choices=['parametric', 'physical'])
    parser.add_argument('--scenario', default='rest')
    parser.add_argument('--duration', type=float, default=10.0)
    parser.add_argument('--ab', action='store_true')
    parser.add_argument('--positions', action='store_true')
    parser.add_argument('--murmur-kit', action='store_true')
    parser.add_argument('--output', '-o', default='exports/pcg')
    args = parser.parse_args()

    os.makedirs(args.output, exist_ok=True)

    if args.murmur_kit:
        if args.ab:
            export_murmur_kit(os.path.join(args.output, 'murmur_kit_parametric'),
                              args.duration, mode='parametric')
            export_murmur_kit(os.path.join(args.output, 'murmur_kit_physical'),
                              args.duration, mode='physical')
        else:
            export_murmur_kit(os.path.join(args.output, 'murmur_kit'),
                              args.duration, mode=args.mode)
        return

    if args.ab:
        print(f"A/B Comparison: {args.scenario} ({args.duration}s)")
        for mode_label, engine_mode in [('A_parametric', 'parametric'), ('B_physical', 'physical')]:
            pipeline = build_pipeline(engine_mode)
            n_beats = int(args.duration / (60.0 / pipeline._base_hr))
            frames = run_beats(pipeline, n_beats)
            path = os.path.join(args.output, f"{mode_label}_{args.scenario}.wav")
            export_wav(frames, path)
        mapping = {'A_parametric': 'parametric', 'B_physical': 'physical'}
        with open(os.path.join(args.output, 'ab_key.json'), 'w') as f:
            json.dump(mapping, f, indent=2)
        print(f"  Scoring key: {args.output}/ab_key.json")
        return

    pipeline = build_pipeline(args.mode)
    n_beats = int(args.duration / (60.0 / pipeline._base_hr))
    frames = run_beats(pipeline, n_beats)

    if args.positions:
        print(f"Exporting 4 positions ({args.mode}/{args.scenario}):")
        for pos in ['aortic', 'pulmonic', 'tricuspid', 'mitral']:
            path = os.path.join(args.output, f"{args.mode}_{args.scenario}_{pos}.wav")
            export_wav(frames, pos)
    else:
        path = os.path.join(args.output, f"{args.mode}_{args.scenario}.wav")
        export_wav(frames, path)


if __name__ == '__main__':
    main()

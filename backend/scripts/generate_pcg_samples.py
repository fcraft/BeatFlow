#!/usr/bin/env python3
"""Generate multiple versions of PCG heart sound WAV files for audition.

Each version produces 4 auscultation-position WAVs (aortic, pulmonic, tricuspid, mitral)
at 44100 Hz, 10 seconds (~12 beats at 72 bpm).

Versions differ in modal decomposition, timing, and envelope shaping to let the
user pick the most realistic one by ear.

Physiological basis (Durand & Pibarot, Leatham, Shaver):
- S1: mitral (M1) + tricuspid (T1) valve closure, 20-50ms after QRS
  - M1: lower freq 25-45Hz dominant, higher components up to 150Hz
  - T1: 20-30ms after M1, slightly softer
  - Total S1 duration: 100-160ms (including both components)
- S2: aortic (A2) + pulmonic (P2) valve closure
  - A2: higher-pitched than S1, dominant 50-80Hz + harmonics to 200Hz
  - P2: 20-40ms after A2 (wider on inspiration), softer
  - Total S2 duration: 80-120ms
- Systolic period (S1-S2): ~300ms at 72bpm (Weissler: LVET = -1.7*HR + 413)
- S1 typically louder than S2 at apex (mitral area)
- S2 typically louder than S1 at base (aortic area)
- Both S1 and S2 are broadband transients, NOT pure tones

Position-specific characteristics:
- Aortic (2R): A2 loudest, S2 > S1, systolic murmurs radiate here
- Pulmonic (2L): P2 loudest, A2-P2 splitting audible, S2 > S1
- Tricuspid (4L): T1 loudest, S1 > S2, diastolic murmurs
- Mitral (apex): M1 loudest, S1 > S2, S3/S4 best heard here
"""

import numpy as np
import struct
import os

OUTPUT_DIR = "/qqvip/proj/BeatFlow/backend/uploads/pcg-samples"
SAMPLE_RATE = 44100
DURATION_SEC = 10.0
HR_BPM = 72.0


def write_wav(filepath: str, samples: np.ndarray, sr: int = SAMPLE_RATE):
    """Write mono 16-bit WAV file."""
    # Normalize to [-1, 1] then scale to int16
    peak = np.max(np.abs(samples))
    if peak > 0:
        samples = samples / peak * 0.85  # Leave headroom
    int_samples = np.clip(samples * 32767, -32768, 32767).astype(np.int16)
    
    n_samples = len(int_samples)
    data_size = n_samples * 2
    file_size = 36 + data_size
    
    with open(filepath, 'wb') as f:
        # RIFF header
        f.write(b'RIFF')
        f.write(struct.pack('<I', file_size))
        f.write(b'WAVE')
        # fmt chunk
        f.write(b'fmt ')
        f.write(struct.pack('<I', 16))      # chunk size
        f.write(struct.pack('<H', 1))       # PCM
        f.write(struct.pack('<H', 1))       # mono
        f.write(struct.pack('<I', sr))      # sample rate
        f.write(struct.pack('<I', sr * 2))  # byte rate
        f.write(struct.pack('<H', 2))       # block align
        f.write(struct.pack('<H', 16))      # bits per sample
        # data chunk
        f.write(b'data')
        f.write(struct.pack('<I', data_size))
        f.write(int_samples.tobytes())
    print(f"  Written: {filepath} ({n_samples/sr:.1f}s, {n_samples} samples)")


def modal_burst(sr, modes, duration_ms, amplitude, asymmetric_env=False):
    """Generate a multi-modal damped sinusoidal burst.
    
    modes: list of (freq_hz, rel_amplitude, damping_hz)
    If asymmetric_env=True, uses a sharp attack / slow decay envelope.
    """
    n = int(duration_ms / 1000.0 * sr)
    tau = np.arange(n, dtype=np.float64) / sr
    
    wave = np.zeros(n, dtype=np.float64)
    rng = np.random.default_rng(seed=42)
    
    for freq, rel_amp, damping in modes:
        # Add slight random phase for naturalness
        phase = rng.uniform(0, 2 * np.pi)
        wave += rel_amp * np.exp(-damping * tau) * np.sin(2 * np.pi * freq * tau + phase)
    
    # Normalize combined modes
    peak = np.max(np.abs(wave))
    if peak > 1e-10:
        wave /= peak
    
    if asymmetric_env:
        # Sharp attack (~5ms rise), natural exponential decay
        attack_samples = int(0.005 * sr)
        if attack_samples > 0 and attack_samples < n:
            attack = np.linspace(0, 1, attack_samples) ** 0.5  # concave rise
            wave[:attack_samples] *= attack
    
    return wave * amplitude


def add_burst(buffer, onset, burst):
    """Add a burst into the buffer at the given onset sample."""
    end = min(onset + len(burst), len(buffer))
    if onset < 0 or onset >= len(buffer):
        return
    actual = end - onset
    buffer[onset:end] += burst[:actual]


def generate_beat_positions(sr, beat_start, rr_samples, version_params):
    """Generate one beat for all 4 positions. Returns dict of position -> samples array."""
    p = version_params
    
    # Timing within the beat
    # S1 onset: ~50ms after beat start (electromechanical delay)
    s1_onset = beat_start + int(p['s1_delay_ms'] / 1000.0 * sr)
    
    # S2 onset: S1 + systolic period
    systolic_ms = p['systolic_ms']
    s2_onset = s1_onset + int(systolic_ms / 1000.0 * sr)
    
    # M1-T1 delay
    t1_delay_samples = int(p['m1_t1_delay_ms'] / 1000.0 * sr)
    
    # A2-P2 delay  
    a2_p2_delay_samples = int(p['a2_p2_delay_ms'] / 1000.0 * sr)
    
    # Generate sound components
    m1 = modal_burst(sr, p['m1_modes'], p['m1_dur_ms'], 1.0, asymmetric_env=p.get('asymmetric', False))
    t1 = modal_burst(sr, p['t1_modes'], p['t1_dur_ms'], 0.6, asymmetric_env=p.get('asymmetric', False))
    a2 = modal_burst(sr, p['a2_modes'], p['a2_dur_ms'], 0.9, asymmetric_env=p.get('asymmetric', False))
    p2_sound = modal_burst(sr, p['p2_modes'], p['p2_dur_ms'], 0.5, asymmetric_env=p.get('asymmetric', False))
    
    # Position weight matrix (component -> position -> weight)
    # Based on cardiac anatomy and sound transmission
    weights = {
        'M1': {'aortic': 0.25, 'pulmonic': 0.15, 'tricuspid': 0.55, 'mitral': 1.0},
        'T1': {'aortic': 0.15, 'pulmonic': 0.25, 'tricuspid': 1.0,  'mitral': 0.35},
        'A2': {'aortic': 1.0,  'pulmonic': 0.55, 'tricuspid': 0.25, 'mitral': 0.20},
        'P2': {'aortic': 0.35, 'pulmonic': 1.0,  'tricuspid': 0.20, 'mitral': 0.10},
    }
    
    positions = {}
    for pos in ['aortic', 'pulmonic', 'tricuspid', 'mitral']:
        buf = np.zeros(rr_samples, dtype=np.float64)
        s1_local = s1_onset - beat_start
        s2_local = s2_onset - beat_start
        
        # S1 components
        add_burst(buf, s1_local, m1 * weights['M1'][pos])
        add_burst(buf, s1_local + t1_delay_samples, t1 * weights['T1'][pos])
        
        # S2 components
        add_burst(buf, s2_local, a2 * weights['A2'][pos])
        add_burst(buf, s2_local + a2_p2_delay_samples, p2_sound * weights['P2'][pos])
        
        positions[pos] = buf
    
    return positions


def generate_version(name, description, params):
    """Generate all 4 position WAVs for a version."""
    print(f"\n{'='*60}")
    print(f"Version: {name}")
    print(f"  {description}")
    print(f"{'='*60}")
    
    sr = SAMPLE_RATE
    total_samples = int(DURATION_SEC * sr)
    rr_sec = 60.0 / HR_BPM
    rr_samples = int(rr_sec * sr)
    
    # Initialize position buffers
    position_buffers = {pos: np.zeros(total_samples, dtype=np.float64) for pos in ['aortic', 'pulmonic', 'tricuspid', 'mitral']}
    
    rng = np.random.default_rng(seed=123)
    
    # Generate beat by beat
    beat_start = 0
    beat_num = 0
    while beat_start + rr_samples <= total_samples:
        # Slight RR variability (±3%)
        jitter = 1.0 + rng.normal(0, 0.015)
        current_rr = int(rr_samples * jitter)
        current_rr = min(current_rr, total_samples - beat_start)
        
        beat_positions = generate_beat_positions(sr, 0, current_rr, params)
        
        for pos in position_buffers:
            end = min(beat_start + current_rr, total_samples)
            actual = end - beat_start
            position_buffers[pos][beat_start:end] += beat_positions[pos][:actual]
        
        beat_start += current_rr
        beat_num += 1
    
    print(f"  Generated {beat_num} beats")
    
    # Add background noise (tissue/blood flow)
    for pos in position_buffers:
        noise = rng.normal(0, params.get('noise_level', 0.01), total_samples)
        # Low-pass filter the noise (tissue noise is low freq)
        kernel_size = int(sr / 200)
        if kernel_size > 1:
            kernel = np.ones(kernel_size) / kernel_size
            noise = np.convolve(noise, kernel, mode='same')
        position_buffers[pos] += noise
    
    # Write WAVs
    version_dir = os.path.join(OUTPUT_DIR, name)
    os.makedirs(version_dir, exist_ok=True)
    
    for pos, buf in position_buffers.items():
        filepath = os.path.join(version_dir, f"{pos}.wav")
        write_wav(filepath, buf, sr)
    
    # Also write a mixed version (equal blend of all positions)
    mixed = sum(position_buffers.values()) / 4.0
    write_wav(os.path.join(version_dir, "mixed.wav"), mixed, sr)


# ========================================================================
# Version definitions
# ========================================================================

# --- V1: Current engine baseline (reproduce current acoustic_generator.py) ---
V1_CURRENT = {
    'name': 'v1-current-baseline',
    'description': 'Current V2 engine parameters as-is. M1@100Hz, A2@120Hz, A2-P2=20ms.',
    'params': {
        's1_delay_ms': 50.0,
        'systolic_ms': 290.0,  # Weissler at 72bpm
        'm1_t1_delay_ms': 10.0,
        'a2_p2_delay_ms': 20.0,
        'm1_modes': [(50.0, 0.25, 30.0), (100.0, 0.50, 40.0), (150.0, 0.25, 55.0)],
        'm1_dur_ms': 80.0,
        't1_modes': [(40.0, 0.40, 25.0), (80.0, 0.60, 40.0)],
        't1_dur_ms': 60.0,
        'a2_modes': [(80.0, 0.20, 35.0), (120.0, 0.55, 50.0), (200.0, 0.25, 70.0)],
        'a2_dur_ms': 60.0,
        'p2_modes': [(60.0, 0.45, 30.0), (110.0, 0.55, 50.0)],
        'p2_dur_ms': 50.0,
        'noise_level': 0.008,
    },
}

# --- V2: Physiological literature-based (Leatham / Shaver) ---
# Key insight: real heart sounds are BROADBAND transients, not narrow-band tones.
# S1 dominant energy: 25-45Hz body, harmonics to 140Hz
# S2 dominant energy: 50-80Hz body, harmonics to 200Hz
# S2 is generally shorter and sharper than S1
V2_PHYSIO_LITERATURE = {
    'name': 'v2-physio-literature',
    'description': 'Literature-based: S1 low-freq dominant (30-45Hz), S2 mid-freq (50-80Hz), broader bandwidth, sharper attack.',
    'params': {
        's1_delay_ms': 50.0,
        'systolic_ms': 300.0,
        'm1_t1_delay_ms': 25.0,   # Literature: 20-30ms M1-T1 split
        'a2_p2_delay_ms': 15.0,   # Literature: 10-30ms at rest, expiration
        'm1_modes': [
            (30.0,  0.35, 20.0),   # Deep body thud (dominant in S1)
            (60.0,  0.30, 30.0),   # Mid body
            (100.0, 0.20, 45.0),   # Upper harmonic
            (140.0, 0.15, 60.0),   # High harmonic (faint)
        ],
        'm1_dur_ms': 120.0,        # S1 is longer than S2
        't1_modes': [
            (25.0,  0.40, 18.0),   # Very low thud
            (50.0,  0.35, 28.0),   # Mid
            (85.0,  0.25, 40.0),   # Upper
        ],
        't1_dur_ms': 80.0,
        'a2_modes': [
            (50.0,  0.20, 30.0),   # Sub
            (80.0,  0.35, 40.0),   # Dominant (higher than S1)
            (130.0, 0.25, 55.0),   # Harmonic
            (200.0, 0.20, 75.0),   # High (sharper than S1)
        ],
        'a2_dur_ms': 80.0,         # S2 shorter than S1
        'p2_modes': [
            (40.0,  0.30, 25.0),
            (70.0,  0.40, 35.0),
            (110.0, 0.30, 50.0),
        ],
        'p2_dur_ms': 60.0,
        'asymmetric': True,         # Sharp attack envelope
        'noise_level': 0.010,
    },
}

# --- V3: Emphasis on broadband transient character ---
# Heart sounds are impulsive — think "thud/click", not "tone"
# Use many more modes with heavy damping for broadband character
V3_BROADBAND_TRANSIENT = {
    'name': 'v3-broadband-transient',
    'description': 'Broadband transient: many modes, heavy damping, impulsive character. S1="thud", S2="click".',
    'params': {
        's1_delay_ms': 50.0,
        'systolic_ms': 300.0,
        'm1_t1_delay_ms': 20.0,
        'a2_p2_delay_ms': 15.0,
        'm1_modes': [
            (25.0,  0.20, 25.0),
            (40.0,  0.25, 30.0),
            (60.0,  0.20, 40.0),
            (90.0,  0.15, 50.0),
            (120.0, 0.12, 60.0),
            (160.0, 0.08, 80.0),
        ],
        'm1_dur_ms': 100.0,
        't1_modes': [
            (20.0,  0.25, 20.0),
            (35.0,  0.30, 28.0),
            (55.0,  0.25, 38.0),
            (80.0,  0.20, 50.0),
        ],
        't1_dur_ms': 70.0,
        'a2_modes': [
            (40.0,  0.15, 30.0),
            (65.0,  0.25, 40.0),
            (95.0,  0.25, 55.0),
            (140.0, 0.20, 70.0),
            (200.0, 0.15, 90.0),
        ],
        'a2_dur_ms': 70.0,
        'p2_modes': [
            (35.0,  0.25, 25.0),
            (55.0,  0.30, 35.0),
            (85.0,  0.25, 50.0),
            (120.0, 0.20, 65.0),
        ],
        'p2_dur_ms': 55.0,
        'asymmetric': True,
        'noise_level': 0.012,
    },
}

# --- V4: Stethoscope-filtered realism ---
# Real stethoscope has 20-600Hz passband with resonance at ~100Hz
# This version pre-applies stethoscope frequency response
V4_STETHOSCOPE_FILTERED = {
    'name': 'v4-stethoscope-filtered',
    'description': 'Stethoscope-filtered: tuned for what you actually hear through a diaphragm. Resonance ~100Hz, 20-500Hz band.',
    'params': {
        's1_delay_ms': 50.0,
        'systolic_ms': 300.0,
        'm1_t1_delay_ms': 25.0,
        'a2_p2_delay_ms': 18.0,
        # After stethoscope filtering, dominant heard frequency is ~80-120Hz
        # So we model what the ear perceives, not raw chest wall vibration
        'm1_modes': [
            (40.0,  0.30, 22.0),   # Felt more than heard
            (80.0,  0.35, 32.0),   # Main heard component  
            (120.0, 0.25, 45.0),   # Resonance peak
            (160.0, 0.10, 65.0),   # Faint upper
        ],
        'm1_dur_ms': 110.0,
        't1_modes': [
            (35.0,  0.35, 20.0),
            (70.0,  0.35, 30.0),
            (100.0, 0.30, 42.0),
        ],
        't1_dur_ms': 75.0,
        'a2_modes': [
            (60.0,  0.20, 30.0),
            (100.0, 0.40, 42.0),   # Stethoscope resonance boosts this
            (150.0, 0.25, 58.0),
            (220.0, 0.15, 80.0),
        ],
        'a2_dur_ms': 75.0,
        'p2_modes': [
            (50.0,  0.30, 25.0),
            (90.0,  0.40, 38.0),
            (130.0, 0.30, 55.0),
        ],
        'p2_dur_ms': 55.0,
        'asymmetric': True,
        'noise_level': 0.008,
    },
}

# --- V5: Textbook "lub-dub" with clear timing ---
# Optimized for clarity rather than raw realism
# Distinct S1 and S2 with clear systolic gap
V5_TEXTBOOK_CLEAR = {
    'name': 'v5-textbook-clear',
    'description': 'Textbook "lub-dub": clear S1/S2 distinction, well-defined systolic gap, educational clarity.',
    'params': {
        's1_delay_ms': 50.0,
        'systolic_ms': 310.0,      # Slightly longer for clarity
        'm1_t1_delay_ms': 15.0,
        'a2_p2_delay_ms': 20.0,
        # S1 "lub" — deeper, longer
        'm1_modes': [
            (45.0,  0.40, 22.0),   # Deep dominant
            (90.0,  0.35, 35.0),   # Mid
            (135.0, 0.25, 50.0),   # Upper
        ],
        'm1_dur_ms': 130.0,        # Longer for "lub"
        't1_modes': [
            (35.0,  0.45, 20.0),
            (70.0,  0.35, 30.0),
            (95.0,  0.20, 42.0),
        ],
        't1_dur_ms': 90.0,
        # S2 "dub" — higher, shorter, crisper
        'a2_modes': [
            (70.0,  0.25, 35.0),
            (110.0, 0.40, 50.0),   # Higher than S1
            (170.0, 0.25, 70.0),
            (230.0, 0.10, 90.0),
        ],
        'a2_dur_ms': 70.0,         # Shorter for "dub"
        'p2_modes': [
            (60.0,  0.35, 28.0),
            (100.0, 0.40, 45.0),
            (150.0, 0.25, 60.0),
        ],
        'p2_dur_ms': 55.0,
        'asymmetric': True,
        'noise_level': 0.006,       # Less noise for clarity
    },
}


# ========================================================================
# Generate all versions
# ========================================================================

if __name__ == '__main__':
    versions = [
        V1_CURRENT,
        V2_PHYSIO_LITERATURE,
        V3_BROADBAND_TRANSIENT,
        V4_STETHOSCOPE_FILTERED,
        V5_TEXTBOOK_CLEAR,
    ]
    
    for v in versions:
        generate_version(v['name'], v['description'], v['params'])
    
    print(f"\n{'='*60}")
    print(f"All versions generated in: {OUTPUT_DIR}")
    print(f"Each version has: aortic.wav, pulmonic.wav, tricuspid.wav, mitral.wav, mixed.wav")
    print(f"\nVersions:")
    for v in versions:
        print(f"  {v['name']}/")
        print(f"    {v['description']}")
    print(f"{'='*60}")

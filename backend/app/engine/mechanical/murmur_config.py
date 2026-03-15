"""Murmur profile configuration for position-specific murmur modeling (PCG-13)."""
from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class MurmurProfile:
    shape: str          # "diamond" | "plateau" | "decrescendo" | "rumbling" | "machinery"
    timing: str         # "systolic" | "diastolic" | "continuous"
    freq_lo: float
    freq_hi: float
    amp_factor: float
    site_weights: dict[str, float]  # {aortic, pulmonic, tricuspid, mitral} → [0, 1]


MURMUR_PROFILES: dict[str, MurmurProfile] = {
    'aortic_stenosis': MurmurProfile(shape='diamond', timing='systolic', freq_lo=80, freq_hi=500, amp_factor=0.25, site_weights={'aortic': 1.0, 'pulmonic': 0.4, 'tricuspid': 0.3, 'mitral': 0.5}),
    'mitral_regurgitation': MurmurProfile(shape='plateau', timing='systolic', freq_lo=80, freq_hi=400, amp_factor=0.20, site_weights={'aortic': 0.2, 'pulmonic': 0.15, 'tricuspid': 0.3, 'mitral': 1.0}),
    'aortic_regurgitation': MurmurProfile(shape='decrescendo', timing='diastolic', freq_lo=60, freq_hi=350, amp_factor=0.18, site_weights={'aortic': 1.0, 'pulmonic': 0.5, 'tricuspid': 0.2, 'mitral': 0.3}),
    'mitral_stenosis': MurmurProfile(shape='rumbling', timing='diastolic', freq_lo=50, freq_hi=250, amp_factor=0.15, site_weights={'aortic': 0.1, 'pulmonic': 0.1, 'tricuspid': 0.2, 'mitral': 1.0}),
    'pda': MurmurProfile(shape='machinery', timing='continuous', freq_lo=100, freq_hi=600, amp_factor=0.22, site_weights={'aortic': 0.3, 'pulmonic': 1.0, 'tricuspid': 0.2, 'mitral': 0.2}),
    'tricuspid_regurgitation': MurmurProfile(shape='plateau', timing='systolic', freq_lo=70, freq_hi=350, amp_factor=0.18, site_weights={'aortic': 0.15, 'pulmonic': 0.3, 'tricuspid': 1.0, 'mitral': 0.2}),
    'vsd': MurmurProfile(shape='plateau', timing='systolic', freq_lo=200, freq_hi=600, amp_factor=0.30, site_weights={'aortic': 0.3, 'pulmonic': 0.4, 'tricuspid': 1.0, 'mitral': 0.5}),
}

MURMUR_TYPE_COMPAT: dict[str, str] = {
    'systolic': 'aortic_stenosis',
    'diastolic': 'aortic_regurgitation',
    '': '',
}

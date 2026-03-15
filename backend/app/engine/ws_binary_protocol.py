"""
WebSocket 二进制信号帧协议 v1。

帧格式 (小端序):
┌────────────────────────────────────────────┐
│ Header (20 bytes)                          │
│  [0]     u8   magic = 0xBF                 │
│  [1]     u8   version = 1                  │
│  [2:6]   u32  sequence number              │
│  [6:10]  u32  ecg_start_sample             │
│  [10:14] u32  pcg_start_sample             │
│  [14:16] u16  ecg_count (samples)          │
│  [16:18] u16  pcg_count (samples)          │
│  [18:20] u16  flags                        │
├────────────────────────────────────────────┤
│ ECG Block (ecg_count × 2 bytes)            │
│  int16[] — 量化: value_mV × 6553.6        │
├────────────────────────────────────────────┤
│ PCG Block (pcg_count × 2 bytes)            │
│  int16[] — 量化: value × 3276.8           │
├────────────────────────────────────────────┤
│ server_elapsed_sec (4 bytes, float32)      │
├────────────────────────────────────────────┤
│ Variable-length JSON (if flags indicate)   │
│  u16 json_length                           │
│  utf-8 json bytes                          │
└────────────────────────────────────────────┘
"""
from __future__ import annotations

import json
import struct
from typing import Any

MAGIC_BYTE = 0xBF
PROTOCOL_VERSION = 1

ECG_SCALE = 6553.6    # ±5mV → int16 (32768/5)
PCG_SCALE = 3276.8    # ±10  → int16 (32768/10)

FLAG_HAS_VITALS = 0x01
FLAG_HAS_ANNOTATIONS = 0x02
FLAG_HAS_LEADS = 0x04
FLAG_HAS_TREND = 0x08

# Header struct: u8, u8, u32, u32, u32, u16, u16, u16 = 1+1+4+4+4+2+2+2 = 20 bytes
_HEADER_FMT = '<BBIIIHH H'
_HEADER_SIZE = struct.calcsize(_HEADER_FMT)  # should be 20


class BinaryFrameEncoder:
    """有状态编码器，维护 vitals baseline 用于增量计算。"""

    def __init__(self) -> None:
        self._vitals_baseline: dict[str, Any] = {}

    def encode_ecg_samples(self, samples: list[float]) -> bytes:
        int_vals = [max(-32768, min(32767, int(round(v * ECG_SCALE)))) for v in samples]
        return struct.pack(f'<{len(int_vals)}h', *int_vals)

    def decode_ecg_samples(self, data: bytes, count: int) -> list[float]:
        int_vals = struct.unpack(f'<{count}h', data[:count * 2])
        return [v / ECG_SCALE for v in int_vals]

    def encode_pcg_samples(self, samples: list[float]) -> bytes:
        int_vals = [max(-32768, min(32767, int(round(v * PCG_SCALE)))) for v in samples]
        return struct.pack(f'<{len(int_vals)}h', *int_vals)

    def decode_pcg_samples(self, data: bytes, count: int) -> list[float]:
        int_vals = struct.unpack(f'<{count}h', data[:count * 2])
        return [v / PCG_SCALE for v in int_vals]

    def update_vitals_baseline(self, vitals: dict[str, Any]) -> None:
        self._vitals_baseline = dict(vitals)

    def compute_vitals_delta(
        self, current: dict[str, Any], tolerance: float = 0.01
    ) -> dict[str, Any]:
        delta: dict[str, Any] = {}
        for key, val in current.items():
            baseline_val = self._vitals_baseline.get(key)
            if baseline_val is None:
                delta[key] = val
            elif isinstance(val, (int, float)) and isinstance(baseline_val, (int, float)):
                if abs(val - baseline_val) > tolerance:
                    delta[key] = val
            elif val != baseline_val:
                delta[key] = val
        self._vitals_baseline.update(current)
        return delta


def encode_signal_frame(
    seq: int,
    ecg_samples: list[float],
    pcg_samples: list[float],
    ecg_start_sample: int,
    pcg_start_sample: int,
    vitals_delta: dict[str, Any],
    beat_annotations: list[dict],
    server_elapsed_sec: float,
    ecg_leads: dict[str, list[float]] | None = None,
    conduction_trend: list[dict] | None = None,
) -> bytes:
    encoder = BinaryFrameEncoder()

    flags = 0
    json_payload: dict[str, Any] = {}

    if vitals_delta:
        flags |= FLAG_HAS_VITALS
        json_payload["v"] = vitals_delta
    if beat_annotations:
        flags |= FLAG_HAS_ANNOTATIONS
        json_payload["a"] = beat_annotations
    if ecg_leads:
        flags |= FLAG_HAS_LEADS
        json_payload["l"] = sorted(ecg_leads.keys())
    if conduction_trend:
        flags |= FLAG_HAS_TREND
        json_payload["t"] = conduction_trend

    # Header (20 bytes): u8, u8, u32, u32, u32, u16, u16, u16
    header = struct.pack(
        _HEADER_FMT,
        MAGIC_BYTE,
        PROTOCOL_VERSION,
        seq,
        ecg_start_sample,
        pcg_start_sample,
        len(ecg_samples),
        len(pcg_samples),
        flags,
    )

    ecg_block = encoder.encode_ecg_samples(ecg_samples)
    pcg_block = encoder.encode_pcg_samples(pcg_samples)
    elapsed_block = struct.pack('<f', server_elapsed_sec)

    json_bytes = b''
    if json_payload:
        json_bytes = json.dumps(json_payload, separators=(',', ':')).encode('utf-8')

    json_header = struct.pack('<H', len(json_bytes))

    lead_blocks = b''
    if ecg_leads:
        for lead_name in sorted(ecg_leads.keys()):
            lead_blocks += encoder.encode_ecg_samples(ecg_leads[lead_name])

    return header + ecg_block + pcg_block + elapsed_block + json_header + json_bytes + lead_blocks


def decode_signal_frame(data: bytes) -> dict[str, Any]:
    encoder = BinaryFrameEncoder()
    offset = 0

    # Header (20 bytes)
    magic, version, seq, ecg_start, pcg_start, ecg_count, pcg_count, flags = struct.unpack_from(
        _HEADER_FMT, data, offset
    )
    offset += _HEADER_SIZE
    assert magic == MAGIC_BYTE, f"Bad magic: {magic:#x}"
    assert version == PROTOCOL_VERSION, f"Bad version: {version}"

    ecg = encoder.decode_ecg_samples(data[offset:offset + ecg_count * 2], ecg_count)
    offset += ecg_count * 2

    pcg = encoder.decode_pcg_samples(data[offset:offset + pcg_count * 2], pcg_count)
    offset += pcg_count * 2

    (elapsed,) = struct.unpack_from('<f', data, offset)
    offset += 4

    (json_len,) = struct.unpack_from('<H', data, offset)
    offset += 2

    result: dict[str, Any] = {
        "seq": seq,
        "ecg_start_sample": ecg_start,
        "pcg_start_sample": pcg_start,
        "ecg": ecg,
        "pcg": pcg,
        "server_elapsed_sec": elapsed,
        "vitals": {},
        "beat_annotations": [],
    }

    if json_len > 0:
        json_str = data[offset:offset + json_len].decode('utf-8')
        offset += json_len
        payload = json.loads(json_str)
        result["vitals"] = payload.get("v", {})
        result["beat_annotations"] = payload.get("a", [])

    return result

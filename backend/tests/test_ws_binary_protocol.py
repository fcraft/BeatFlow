"""WebSocket 二进制协议编码器测试。"""
import struct
import pytest
from app.engine.ws_binary_protocol import (
    BinaryFrameEncoder,
    MAGIC_BYTE,
    PROTOCOL_VERSION,
    encode_signal_frame,
    decode_signal_frame,
)


class TestBinaryFrameEncoder:
    """二进制信号帧编码/解码往返测试。"""

    def test_ecg_int16_quantization_precision(self):
        """ECG int16 量化: ±5mV 范围内精度 < 1mV。"""
        encoder = BinaryFrameEncoder()
        ecg_samples = [0.1234, -0.5678, 1.2, -2.3, 0.0001]
        encoded = encoder.encode_ecg_samples(ecg_samples)
        decoded = encoder.decode_ecg_samples(encoded, len(ecg_samples))
        for orig, dec in zip(ecg_samples, decoded):
            assert abs(orig - dec) < 0.001

    def test_pcg_int16_quantization_precision(self):
        """PCG int16 量化: 精度足够。"""
        encoder = BinaryFrameEncoder()
        pcg_samples = [0.5, -0.3, 0.01, -0.001, 0.0]
        encoded = encoder.encode_pcg_samples(pcg_samples)
        decoded = encoder.decode_pcg_samples(encoded, len(pcg_samples))
        for orig, dec in zip(pcg_samples, decoded):
            assert abs(orig - dec) < 0.01

    def test_full_frame_roundtrip(self):
        """完整帧编码→解码往返一致性。"""
        ecg = [0.1 * i for i in range(50)]
        pcg = [0.01 * i for i in range(400)]
        vitals = {"heart_rate": 72.5, "systolic_bp": 120.0}
        annotations = [{"beat_index": 1, "rr_sec": 0.833}]

        frame_bytes = encode_signal_frame(
            seq=42,
            ecg_samples=ecg,
            pcg_samples=pcg,
            ecg_start_sample=2100,
            pcg_start_sample=16800,
            vitals_delta=vitals,
            beat_annotations=annotations,
            server_elapsed_sec=33.451,
        )

        result = decode_signal_frame(frame_bytes)
        assert result["seq"] == 42
        assert result["ecg_start_sample"] == 2100
        assert len(result["ecg"]) == 50
        assert len(result["pcg"]) == 400
        assert result["vitals"]["heart_rate"] == pytest.approx(72.5, abs=0.5)

    def test_frame_size_much_smaller_than_json(self):
        """二进制帧应比等效 JSON 小至少 50%。"""
        import json
        ecg = [round(0.1 * i, 4) for i in range(50)]
        pcg = [round(0.01 * i, 4) for i in range(400)]
        vitals = {"heart_rate": 72.0}

        json_size = len(json.dumps({
            "type": "signal", "seq": 42,
            "ecg": ecg, "pcg": pcg,
            "vitals": vitals,
        }).encode())

        binary_size = len(encode_signal_frame(
            seq=42, ecg_samples=ecg, pcg_samples=pcg,
            ecg_start_sample=0, pcg_start_sample=0,
            vitals_delta=vitals, beat_annotations=[],
            server_elapsed_sec=0.0,
        ))

        assert binary_size < json_size * 0.5

    def test_vitals_delta_only_sends_changes(self):
        """增量 vitals 编码：仅变化字段。"""
        encoder = BinaryFrameEncoder()
        full_vitals = {"heart_rate": 72.0, "systolic_bp": 120.0, "spo2": 98.0}
        encoder.update_vitals_baseline(full_vitals)

        new_vitals = {"heart_rate": 75.0, "systolic_bp": 120.0, "spo2": 98.0}
        delta = encoder.compute_vitals_delta(new_vitals)
        assert "heart_rate" in delta
        assert "systolic_bp" not in delta
        assert "spo2" not in delta

    def test_empty_annotations_minimal_overhead(self):
        """无 beat_annotations 时二进制开销极小。"""
        frame = encode_signal_frame(
            seq=0, ecg_samples=[0.0]*50, pcg_samples=[0.0]*400,
            ecg_start_sample=0, pcg_start_sample=0,
            vitals_delta={}, beat_annotations=[],
            server_elapsed_sec=0.0,
        )
        # Header(20B) + ECG(100B) + PCG(800B) + elapsed(4B) + JSON header(2B) = 926 bytes
        assert len(frame) < 1000

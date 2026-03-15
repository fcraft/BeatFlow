import { describe, it, expect } from 'vitest'
import { decodeSignalFrame, MAGIC_BYTE, ECG_SCALE, PCG_SCALE } from '../wsBinaryProtocol'

describe('wsBinaryProtocol', () => {
  function buildTestFrame(options: {
    seq?: number
    ecgValues?: number[]
    pcgValues?: number[]
    jsonPayload?: Record<string, unknown>
  } = {}): ArrayBuffer {
    const seq = options.seq ?? 0
    const ecg = options.ecgValues ?? new Array(50).fill(0)
    const pcg = options.pcgValues ?? new Array(400).fill(0)
    const jsonStr = options.jsonPayload
      ? JSON.stringify(options.jsonPayload)
      : ''
    const jsonBytes = new TextEncoder().encode(jsonStr)

    const headerSize = 20
    const ecgSize = ecg.length * 2
    const pcgSize = pcg.length * 2
    const elapsedSize = 4
    const jsonHeaderSize = 2
    const totalSize = headerSize + ecgSize + pcgSize + elapsedSize + jsonHeaderSize + jsonBytes.length

    const buf = new ArrayBuffer(totalSize)
    const view = new DataView(buf)
    let offset = 0

    // Header (20 bytes)
    view.setUint8(offset, MAGIC_BYTE); offset += 1
    view.setUint8(offset, 1); offset += 1
    view.setUint32(offset, seq, true); offset += 4
    view.setUint32(offset, 0, true); offset += 4  // ecg_start
    view.setUint32(offset, 0, true); offset += 4  // pcg_start
    view.setUint16(offset, ecg.length, true); offset += 2  // ecg_count
    view.setUint16(offset, pcg.length, true); offset += 2  // pcg_count
    view.setUint16(offset, jsonStr.length > 0 ? 0x01 : 0, true); offset += 2  // flags

    // ECG
    for (const v of ecg) {
      view.setInt16(offset, Math.round(v * ECG_SCALE), true); offset += 2
    }
    // PCG
    for (const v of pcg) {
      view.setInt16(offset, Math.round(v * PCG_SCALE), true); offset += 2
    }
    // elapsed
    view.setFloat32(offset, 0.0, true); offset += 4
    // JSON header
    view.setUint16(offset, jsonBytes.length, true); offset += 2
    // JSON body
    new Uint8Array(buf, offset).set(jsonBytes)

    return buf
  }

  it('decodes sequence number', () => {
    const frame = buildTestFrame({ seq: 42 })
    const result = decodeSignalFrame(frame)
    expect(result.seq).toBe(42)
  })

  it('decodes ECG samples with sub-mV precision', () => {
    const ecg = [0.1, -0.5, 1.2, -2.3, 0.0]
    const padded = [...ecg, ...new Array(45).fill(0)]
    const frame = buildTestFrame({ ecgValues: padded })
    const result = decodeSignalFrame(frame)
    for (let i = 0; i < ecg.length; i++) {
      expect(Math.abs(result.ecg[i] - ecg[i])).toBeLessThan(0.001)
    }
  })

  it('decodes vitals delta from JSON payload', () => {
    const frame = buildTestFrame({
      jsonPayload: { v: { heart_rate: 85.0 } },
    })
    const result = decodeSignalFrame(frame)
    expect(result.vitalsDelta.heart_rate).toBe(85.0)
  })

  it('returns empty vitalsDelta when no JSON', () => {
    const frame = buildTestFrame()
    const result = decodeSignalFrame(frame)
    expect(result.vitalsDelta).toEqual({})
  })
})

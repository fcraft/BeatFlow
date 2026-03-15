/**
 * WebSocket 二进制信号帧协议 v1 解码器。
 * 与后端 ws_binary_protocol.py 对应。
 */

export const MAGIC_BYTE = 0xbf
export const ECG_SCALE = 6553.6
export const PCG_SCALE = 3276.8

export interface DecodedSignalFrame {
  seq: number
  ecgStartSample: number
  pcgStartSample: number
  ecg: Float32Array
  pcg: Float32Array
  serverElapsedSec: number
  vitalsDelta: Record<string, unknown>
  beatAnnotations: Array<Record<string, unknown>>
  conductionTrend?: Array<Record<string, unknown>>
  ecgLeads?: Record<string, Float32Array>
}

export function decodeSignalFrame(buffer: ArrayBuffer): DecodedSignalFrame {
  const view = new DataView(buffer)
  let offset = 0

  // Header (20 bytes)
  const magic = view.getUint8(offset); offset += 1
  const version = view.getUint8(offset); offset += 1
  if (magic !== MAGIC_BYTE || version !== 1) {
    throw new Error(`Invalid frame: magic=0x${magic.toString(16)}, version=${version}`)
  }

  const seq = view.getUint32(offset, true); offset += 4
  const ecgStart = view.getUint32(offset, true); offset += 4
  const pcgStart = view.getUint32(offset, true); offset += 4
  const ecgCount = view.getUint16(offset, true); offset += 2
  const pcgCount = view.getUint16(offset, true); offset += 2
  const flags = view.getUint16(offset, true); offset += 2

  // ECG (ecgCount × int16)
  const ecg = new Float32Array(ecgCount)
  for (let i = 0; i < ecgCount; i++) {
    ecg[i] = view.getInt16(offset, true) / ECG_SCALE
    offset += 2
  }

  // PCG (pcgCount × int16)
  const pcg = new Float32Array(pcgCount)
  for (let i = 0; i < pcgCount; i++) {
    pcg[i] = view.getInt16(offset, true) / PCG_SCALE
    offset += 2
  }

  // Server elapsed (float32)
  const serverElapsedSec = view.getFloat32(offset, true)
  offset += 4

  // JSON block
  const jsonLen = view.getUint16(offset, true)
  offset += 2

  let vitalsDelta: Record<string, unknown> = {}
  let beatAnnotations: Array<Record<string, unknown>> = []
  let conductionTrend: Array<Record<string, unknown>> | undefined
  let leadNames: string[] | undefined

  if (jsonLen > 0) {
    const jsonBytes = new Uint8Array(buffer, offset, jsonLen)
    const jsonStr = new TextDecoder().decode(jsonBytes)
    offset += jsonLen

    const payload = JSON.parse(jsonStr)
    vitalsDelta = payload.v ?? {}
    beatAnnotations = payload.a ?? []
    conductionTrend = payload.t
    leadNames = payload.l
  }

  // Lead binary blocks
  let ecgLeads: Record<string, Float32Array> | undefined
  if (leadNames && leadNames.length > 0) {
    ecgLeads = {}
    for (const name of leadNames.sort()) {
      const leadData = new Float32Array(ecgCount)
      for (let i = 0; i < ecgCount; i++) {
        leadData[i] = view.getInt16(offset, true) / ECG_SCALE
        offset += 2
      }
      ecgLeads[name] = leadData
    }
  }

  // suppress unused variable warning for flags
  void flags

  return {
    seq,
    ecgStartSample: ecgStart,
    pcgStartSample: pcgStart,
    ecg,
    pcg,
    serverElapsedSec,
    vitalsDelta,
    beatAnnotations,
    conductionTrend,
    ecgLeads,
  }
}

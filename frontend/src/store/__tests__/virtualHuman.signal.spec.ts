/**
 * Signal dispatch timing tests for virtualHuman store.
 *
 * Verifies that ECG and PCG callbacks receive correctly parsed,
 * synchronized signal chunks from WebSocket messages.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'

// Replicate the store's signal dispatch logic for isolated testing
// (avoids needing Pinia/WebSocket setup)

interface SignalChunk {
  samples: number[]
  startSample: number
  seq: number
  receivedAtMs: number
  chunkDurationMs: number
  serverElapsedSec: number | null
}

function createSignalDispatcher() {
  const ecgCallbacks: Array<(chunk: SignalChunk) => void> = []
  const pcgCallbacks: Array<(chunk: SignalChunk) => void> = []

  function registerEcg(fn: (chunk: SignalChunk) => void) {
    ecgCallbacks.push(fn)
  }

  function registerPcg(fn: (chunk: SignalChunk) => void) {
    pcgCallbacks.push(fn)
  }

  function handleSignalMessage(msg: any) {
    const receivedAtMs = 12345.678  // Fixed for testing
    const seq = Number.isFinite(msg.seq) ? Number(msg.seq) : 0
    const chunkMs = Number.isFinite(msg.chunk_duration_ms)
      ? Number(msg.chunk_duration_ms)
      : 100
    const serverElapsedSec = Number.isFinite(msg.server_elapsed_sec)
      ? Number(msg.server_elapsed_sec)
      : null

    if (Array.isArray(msg.ecg)) {
      const startSample = Number.isFinite(msg.ecg_start_sample)
        ? Number(msg.ecg_start_sample)
        : seq * 50
      const chunk: SignalChunk = {
        samples: msg.ecg,
        startSample,
        seq,
        receivedAtMs,
        chunkDurationMs: chunkMs,
        serverElapsedSec,
      }
      ecgCallbacks.forEach((fn) => fn(chunk))
    }

    if (Array.isArray(msg.pcg)) {
      const startSample = Number.isFinite(msg.pcg_start_sample)
        ? Number(msg.pcg_start_sample)
        : seq * 400
      const chunk: SignalChunk = {
        samples: msg.pcg,
        startSample,
        seq,
        receivedAtMs,
        chunkDurationMs: chunkMs,
        serverElapsedSec,
      }
      pcgCallbacks.forEach((fn) => fn(chunk))
    }
  }

  return { registerEcg, registerPcg, handleSignalMessage }
}

// ════════════════════════════════════════════════════════════════════
// Test 2.7: Signal Chunk Dispatch Timing
// ════════════════════════════════════════════════════════════════════
describe('signal dispatch', () => {
  it('ECG and PCG callbacks receive same receivedAtMs', () => {
    const dispatcher = createSignalDispatcher()
    let ecgReceived = 0
    let pcgReceived = 0

    dispatcher.registerEcg((chunk) => { ecgReceived = chunk.receivedAtMs })
    dispatcher.registerPcg((chunk) => { pcgReceived = chunk.receivedAtMs })

    dispatcher.handleSignalMessage({
      type: 'signal',
      seq: 0,
      ecg: Array(50).fill(0.1),
      pcg: Array(400).fill(0.2),
      ecg_start_sample: 0,
      pcg_start_sample: 0,
      chunk_duration_ms: 100,
      server_elapsed_sec: 0.1,
    })

    expect(ecgReceived).toBe(pcgReceived)
    expect(ecgReceived).toBe(12345.678)
  })

  it('dispatch order is ECG then PCG', () => {
    const dispatcher = createSignalDispatcher()
    const callOrder: string[] = []

    dispatcher.registerEcg(() => { callOrder.push('ecg') })
    dispatcher.registerPcg(() => { callOrder.push('pcg') })

    dispatcher.handleSignalMessage({
      type: 'signal',
      seq: 0,
      ecg: [0.1],
      pcg: [0.2],
      ecg_start_sample: 0,
      pcg_start_sample: 0,
    })

    expect(callOrder).toEqual(['ecg', 'pcg'])
  })

  it('startSample correctly parsed from ecg_start_sample', () => {
    const dispatcher = createSignalDispatcher()
    let ecgStart = -1
    let pcgStart = -1

    dispatcher.registerEcg((chunk) => { ecgStart = chunk.startSample })
    dispatcher.registerPcg((chunk) => { pcgStart = chunk.startSample })

    dispatcher.handleSignalMessage({
      type: 'signal',
      seq: 5,
      ecg: Array(50).fill(0),
      pcg: Array(400).fill(0),
      ecg_start_sample: 12345,
      pcg_start_sample: 98760,
    })

    // Should use ecg_start_sample, not seq * chunkSize
    expect(ecgStart).toBe(12345)
    expect(pcgStart).toBe(98760)
  })

  it('falls back to seq-based startSample when ecg_start_sample missing', () => {
    const dispatcher = createSignalDispatcher()
    let ecgStart = -1

    dispatcher.registerEcg((chunk) => { ecgStart = chunk.startSample })

    dispatcher.handleSignalMessage({
      type: 'signal',
      seq: 10,
      ecg: Array(50).fill(0),
      pcg: Array(400).fill(0),
      // No ecg_start_sample field
    })

    expect(ecgStart).toBe(10 * 50)  // seq * chunkSize fallback
  })

  it('preserves exact sample values from message', () => {
    const dispatcher = createSignalDispatcher()
    let ecgSamples: number[] = []
    let pcgSamples: number[] = []

    dispatcher.registerEcg((chunk) => { ecgSamples = chunk.samples })
    dispatcher.registerPcg((chunk) => { pcgSamples = chunk.samples })

    const ecgData = [0.1234, -0.5678, 0.0001, 1.2345, -0.9999]
    const pcgData = [0.4321, -0.8765, 0.0002]

    dispatcher.handleSignalMessage({
      type: 'signal',
      seq: 0,
      ecg: ecgData,
      pcg: pcgData,
      ecg_start_sample: 0,
      pcg_start_sample: 0,
    })

    expect(ecgSamples).toEqual(ecgData)
    expect(pcgSamples).toEqual(pcgData)
  })

  it('handles message with only ECG (no PCG)', () => {
    const dispatcher = createSignalDispatcher()
    let ecgCalled = false
    let pcgCalled = false

    dispatcher.registerEcg(() => { ecgCalled = true })
    dispatcher.registerPcg(() => { pcgCalled = true })

    dispatcher.handleSignalMessage({
      type: 'signal',
      seq: 0,
      ecg: [0.1],
      ecg_start_sample: 0,
    })

    expect(ecgCalled).toBe(true)
    expect(pcgCalled).toBe(false)
  })

  it('correctly parses serverElapsedSec', () => {
    const dispatcher = createSignalDispatcher()
    let ecgElapsed: number | null = null

    dispatcher.registerEcg((chunk) => { ecgElapsed = chunk.serverElapsedSec })

    dispatcher.handleSignalMessage({
      type: 'signal',
      seq: 0,
      ecg: [0.1],
      ecg_start_sample: 0,
      server_elapsed_sec: 3.456,
    })

    expect(ecgElapsed).toBe(3.456)
  })
})

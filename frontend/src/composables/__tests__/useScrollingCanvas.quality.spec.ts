/**
 * Quality tests for useScrollingCanvas — buffer integrity, drift correction,
 * buildPoints accuracy, and float32 precision.
 *
 * These tests replicate the composable's internal algorithms to verify
 * correctness without requiring a real canvas DOM element.
 */
import { describe, it, expect } from 'vitest'

// ── Replicate core buffer logic from useScrollingCanvas.ts ──────────

function createTestBuffer(sampleRate: number, displaySeconds = 5, playbackDelayMs = 180) {
  const historySeconds = Math.max(displaySeconds + 2, displaySeconds + playbackDelayMs / 1000 + 1)
  const bufferSize = Math.max(4, Math.round(sampleRate * historySeconds))
  const displaySamples = Math.max(2, Math.round(sampleRate * displaySeconds))
  const playbackDelaySamples = Math.max(1, Math.round(sampleRate * playbackDelayMs / 1000))

  const buffer = new Float32Array(bufferSize)
  let writePos = 0
  let storedSamples = 0
  let latestEndSample = 0
  let playbackOriginMs = 0
  let playbackOriginSample = 0
  let hasTimeline = false

  // Frame-locked virtual playhead
  let virtualPlayhead = 0
  let lastFrameTime = 0
  let virtualPlayheadActive = false

  function earliestStoredSample() {
    return latestEndSample - storedSamples
  }

  function writeValue(sample: number) {
    buffer[writePos] = sample
    writePos = (writePos + 1) % bufferSize
    storedSamples = Math.min(bufferSize, storedSamples + 1)
  }

  function sampleAt(absSample: number): number {
    if (storedSamples <= 0) return 0
    const earliest = earliestStoredSample()
    if (absSample < earliest || absSample >= latestEndSample) return 0
    const offset = absSample - earliest
    const startIdx = (writePos - storedSamples + bufferSize) % bufferSize
    return buffer[(startIdx + offset) % bufferSize]
  }

  function fillGap(gapSamples: number) {
    if (gapSamples <= 0) return
    const padValue = storedSamples > 0 ? sampleAt(latestEndSample - 1) : 0
    for (let i = 0; i < gapSamples; i++) {
      writeValue(padValue)
    }
    latestEndSample += gapSamples
  }

  function appendSamples(samples: number[], startSample: number, receivedAtMs: number) {
    if (!samples.length) return

    if (!hasTimeline) {
      latestEndSample = startSample
      hasTimeline = true
    }

    let adjStart = startSample
    let adjSamples = samples

    if (adjStart < latestEndSample) {
      const overlap = latestEndSample - adjStart
      if (overlap >= adjSamples.length) return
      adjSamples = adjSamples.slice(overlap)
      adjStart = latestEndSample
    } else if (adjStart > latestEndSample) {
      fillGap(adjStart - latestEndSample)
    }

    for (let i = 0; i < adjSamples.length; i++) {
      writeValue(adjSamples[i])
    }
    latestEndSample = adjStart + adjSamples.length

    // Drift correction
    const desiredPlayhead = Math.max(earliestStoredSample(), latestEndSample - playbackDelaySamples)
    if (playbackOriginMs === 0) {
      playbackOriginSample = desiredPlayhead
      playbackOriginMs = receivedAtMs
      virtualPlayhead = desiredPlayhead
      lastFrameTime = receivedAtMs
      virtualPlayheadActive = true
    } else {
      const currentEstimated = estimatePlaybackSample(receivedAtMs)
      const drift = desiredPlayhead - currentEstimated
      if (Math.abs(drift) > sampleRate * 0.5) {
        // Hard reset
        playbackOriginSample = desiredPlayhead
        playbackOriginMs = receivedAtMs
      } else if (Math.abs(drift) > sampleRate * 0.02) {
        // Gradual 20% correction
        const correctedSample = currentEstimated + drift * 0.2
        playbackOriginSample = correctedSample
        playbackOriginMs = receivedAtMs
      }
    }
  }

  function estimatePlaybackSample(nowMs: number, frameLocked = false): number {
    if (!hasTimeline || playbackOriginMs === 0) return latestEndSample

    if (frameLocked && virtualPlayheadActive) {
      const dt = lastFrameTime > 0 ? Math.max(0, Math.min(50, nowMs - lastFrameTime)) : 16.67
      const stepSamples = (dt / 1000) * sampleRate
      virtualPlayhead += stepSamples

      const wallClockEstimate = playbackOriginSample + ((nowMs - playbackOriginMs) / 1000) * sampleRate
      const drift = wallClockEstimate - virtualPlayhead
      virtualPlayhead += drift * 0.02

      lastFrameTime = nowMs
      return Math.max(earliestStoredSample(), Math.min(latestEndSample - 1, virtualPlayhead))
    }

    const elapsedSamples = ((nowMs - playbackOriginMs) / 1000) * sampleRate
    const unclamped = playbackOriginSample + elapsedSamples
    return Math.max(earliestStoredSample(), Math.min(latestEndSample - 1, unclamped))
  }

  function buildPoints(width: number, nowMs: number) {
    const effectiveWidth = Math.max(2, Math.floor(width))
    const endSampleF = estimatePlaybackSample(nowMs, true)
    const endSample = Math.floor(endSampleF)
    const startSample = Math.max(earliestStoredSample(), endSample - displaySamples + 1)
    const visibleSamples = Math.max(2, endSample - startSample + 1)
    const points = new Float32Array(effectiveWidth)
    const samplesPerPixel = visibleSamples / effectiveWidth
    const radius = Math.max(1, Math.min(8, Math.round(samplesPerPixel * 0.5)))

    for (let px = 0; px < effectiveWidth; px++) {
      const center = Math.round(startSample + (px / (effectiveWidth - 1)) * (visibleSamples - 1))
      let sum = 0
      let count = 0
      const from = Math.max(startSample, center - radius)
      const to = Math.min(endSample, center + radius)
      for (let sample = from; sample <= to; sample++) {
        sum += sampleAt(sample)
        count += 1
      }
      points[px] = count > 0 ? sum / count : 0
    }

    return points
  }

  return {
    appendSamples,
    sampleAt,
    estimatePlaybackSample,
    buildPoints,
    get bufferSize() { return bufferSize },
    get storedSamples() { return storedSamples },
    get latestEndSample() { return latestEndSample },
    get playbackOriginSample() { return playbackOriginSample },
    get playbackOriginMs() { return playbackOriginMs },
    get earliestStoredSample() { return earliestStoredSample() },
  }
}

// ════════════════════════════════════════════════════════════════════
// Test 2.1: Circular Buffer Write/Read Correctness
// ════════════════════════════════════════════════════════════════════
describe('circular buffer integrity', () => {
  it('preserves sample values through buffer wraparound', () => {
    // Use a very small sample rate to get a small buffer for testing
    const buf = createTestBuffer(10, 5, 0)  // bufferSize ≈ 70

    // Append 150 known values (will wrap around multiple times)
    const values: number[] = []
    for (let i = 0; i < 150; i++) {
      values.push(Math.sin(i * 0.1) * 0.5)
    }

    buf.appendSamples(values, 0, 1000)

    // The buffer should keep the last bufferSize samples
    const bufSize = buf.bufferSize
    const keptCount = Math.min(bufSize, 150)
    const startIdx = 150 - keptCount

    for (let i = startIdx; i < 150; i++) {
      const retrieved = buf.sampleAt(i)
      // Float32 precision: allow small error
      expect(Math.abs(retrieved - values[i])).toBeLessThan(1e-6)
    }
  })

  it('sampleAt returns 0 for out-of-range samples', () => {
    const buf = createTestBuffer(500, 5, 0)
    buf.appendSamples([1.0, 2.0, 3.0], 100, 1000)

    // Before range
    expect(buf.sampleAt(99)).toBe(0)
    // After range
    expect(buf.sampleAt(103)).toBe(0)
    // In range
    expect(buf.sampleAt(100)).toBeCloseTo(1.0, 5)
    expect(buf.sampleAt(101)).toBeCloseTo(2.0, 5)
    expect(buf.sampleAt(102)).toBeCloseTo(3.0, 5)
  })

  it('handles overlapping chunks by deduplicating', () => {
    const buf = createTestBuffer(500, 5, 0)

    // First chunk: samples 0-49
    const chunk1 = Array.from({ length: 50 }, (_, i) => i * 0.01)
    buf.appendSamples(chunk1, 0, 1000)

    // Overlapping chunk: starts at sample 25 (overlaps 25 samples)
    const chunk2 = Array.from({ length: 50 }, (_, i) => (i + 25) * 0.02)
    buf.appendSamples(chunk2, 25, 1100)

    // Samples 0-49 should have original values
    for (let i = 0; i < 50; i++) {
      expect(buf.sampleAt(i)).toBeCloseTo(i * 0.01, 5)
    }
    // Samples 50-74 should have new values from chunk2
    for (let i = 50; i < 75; i++) {
      expect(buf.sampleAt(i)).toBeCloseTo(i * 0.02, 5)
    }
  })

  it('fills gaps with last known value', () => {
    const buf = createTestBuffer(500, 5, 0)

    buf.appendSamples([1.0, 2.0, 3.0], 0, 1000)
    // Gap: samples 3-9 should be filled with last value (3.0)
    buf.appendSamples([10.0], 10, 1200)

    for (let i = 3; i < 10; i++) {
      expect(buf.sampleAt(i)).toBeCloseTo(3.0, 5)
    }
    expect(buf.sampleAt(10)).toBeCloseTo(10.0, 5)
  })
})

// ════════════════════════════════════════════════════════════════════
// Test 2.2: Drift Correction Behavior
// ════════════════════════════════════════════════════════════════════
describe('drift correction', () => {
  it('hard resets on gap > 500ms', () => {
    const buf = createTestBuffer(500, 5, 180)

    // First chunk at t=0
    const chunk1 = Array.from({ length: 50 }, () => 0.1)
    buf.appendSamples(chunk1, 0, 0)

    const origin1 = buf.playbackOriginSample

    // Second chunk at t=700ms with matching sample jump (350 samples gap)
    // This is > 500ms worth of samples = 250 samples, so hard reset
    const chunk2 = Array.from({ length: 50 }, () => 0.2)
    buf.appendSamples(chunk2, 400, 700)

    // After hard reset, origin should have moved significantly
    const origin2 = buf.playbackOriginSample
    expect(Math.abs(origin2 - origin1)).toBeGreaterThan(100)
  })

  it('gradual correction on small drift (20-500ms)', () => {
    const buf = createTestBuffer(500, 5, 180)

    // Feed 10 chunks normally (each 100ms apart, 50 samples)
    for (let i = 0; i < 10; i++) {
      const chunk = Array.from({ length: 50 }, () => 0.1)
      buf.appendSamples(chunk, i * 50, i * 100)
    }

    const originBefore = buf.playbackOriginSample

    // Now introduce a small drift: send chunk that arrives 50ms late
    // (receivedAtMs is 50ms ahead of expected based on sample timing)
    const lateChunk = Array.from({ length: 50 }, () => 0.1)
    buf.appendSamples(lateChunk, 500, 1050)

    // Origin should have been adjusted by drift correction logic.
    // The key invariant: playbackOriginSample is updated each chunk via
    // the 20% gradual correction formula. After 11 chunks, the origin
    // reflects accumulated corrections. We verify it has moved (not stuck).
    const originAfter = buf.playbackOriginSample
    const change = Math.abs(originAfter - originBefore)
    // Origin should have changed (drift correction is active)
    expect(change).toBeGreaterThan(0)
    // But should not be a catastrophic jump (> bufferSize)
    expect(change).toBeLessThan(buf.bufferSize)
  })

  it('initializes playback origin on first chunk', () => {
    const buf = createTestBuffer(500, 5, 180)

    expect(buf.playbackOriginMs).toBe(0)

    const chunk = Array.from({ length: 50 }, () => 0.1)
    buf.appendSamples(chunk, 1000, 5000)

    expect(buf.playbackOriginMs).toBe(5000)
    expect(buf.playbackOriginSample).toBeGreaterThan(0)
  })
})

// ════════════════════════════════════════════════════════════════════
// Test 2.3: buildPoints Accuracy
// ════════════════════════════════════════════════════════════════════
describe('buildPoints sampling', () => {
  it('correctly maps samples to pixels for simple case', () => {
    const buf = createTestBuffer(500, 5, 0)

    // Create a known signal: ramp from 0 to 1
    const n = 2500 // 5 seconds at 500Hz
    const ramp = Array.from({ length: n }, (_, i) => i / (n - 1))
    buf.appendSamples(ramp, 0, 0)

    // buildPoints with width=500, should produce a smooth ramp
    const points = buf.buildPoints(500, 5000)  // At t=5s, all data should be visible

    // Points should be monotonically increasing (roughly)
    let increasing = 0
    for (let i = 1; i < points.length; i++) {
      if (points[i] >= points[i - 1] - 0.01) increasing++
    }
    // Allow some noise from averaging
    expect(increasing / (points.length - 1)).toBeGreaterThan(0.9)
  })

  it('preserves peak amplitude reasonably', () => {
    const buf = createTestBuffer(500, 5, 0)

    // Create ECG-like signal with a sharp R-peak
    const n = 2500
    const signal = new Array(n).fill(0)
    // R-peak at sample 1250 (mid-point)
    signal[1249] = 0.5
    signal[1250] = 1.5  // The peak
    signal[1251] = 0.5

    buf.appendSamples(signal, 0, 0)
    const points = buf.buildPoints(500, 5000)

    // The max point should retain most of the peak
    const maxVal = Math.max(...Array.from(points))
    // With averaging radius, peak gets diluted but should still be significant
    expect(maxVal).toBeGreaterThan(0.3) // At least 20% of peak preserved
  })
})

// ════════════════════════════════════════════════════════════════════
// Test 2.4: Float32 Precision
// ════════════════════════════════════════════════════════════════════
describe('float32 buffer precision', () => {
  it('preserves ECG-scale values with adequate precision', () => {
    // ECG values typically range [-1.8, 1.8] mV
    // After round(v, 4) from backend, smallest step is 0.0001
    // Float32 has ~7 significant digits, so 0.0001 is well within range

    const testValues = [
      0.0001,    // Smallest backend step
      0.0012,    // Small baseline noise
      0.1234,    // Typical P-wave amplitude
      1.2345,    // R-peak amplitude
      -0.3456,   // S-wave
      0.0,       // Zero baseline
    ]

    const f32 = new Float32Array(testValues.length)
    for (let i = 0; i < testValues.length; i++) {
      f32[i] = testValues[i]
    }

    for (let i = 0; i < testValues.length; i++) {
      const error = Math.abs(f32[i] - testValues[i])
      // Float32 should preserve 4 decimal places easily
      expect(error).toBeLessThan(1e-6)
    }
  })

  it('preserves PCG-scale values with adequate precision', () => {
    // PCG normalized to roughly [-0.85, 0.85]
    const testValues = [0.8234, -0.7654, 0.0012, -0.0001, 0.4567]

    const f32 = new Float32Array(testValues.length)
    for (let i = 0; i < testValues.length; i++) {
      f32[i] = testValues[i]
    }

    for (let i = 0; i < testValues.length; i++) {
      const error = Math.abs(f32[i] - testValues[i])
      expect(error).toBeLessThan(1e-6)
    }
  })

  it('combined round(4) + float32 precision loss is negligible', () => {
    // Simulate the full precision chain:
    // Backend float64 -> round(v, 4) -> JSON -> frontend float64 -> Float32Array
    const original = 1.23456789  // High-precision backend value
    const rounded = Math.round(original * 10000) / 10000  // round(v, 4) = 1.2346
    const f32 = new Float32Array([rounded])[0]

    // Error from rounding
    const roundError = Math.abs(original - rounded)
    expect(roundError).toBeLessThan(0.0001) // < 0.01%

    // Error from Float32
    const f32Error = Math.abs(rounded - f32)
    expect(f32Error).toBeLessThan(1e-7) // Float32 handles 4-decimal values fine

    // Total chain error
    const totalError = Math.abs(original - f32)
    expect(totalError).toBeLessThan(0.0002) // Total < 0.02%
  })
})

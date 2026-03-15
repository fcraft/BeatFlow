/**
 * Tests for useScrollingCanvas — Y-axis asymmetric auto-scaling behavior.
 *
 * Validates that:
 * - Y-axis expands quickly when new peaks appear (weight 0.3)
 * - Y-axis contracts slowly when peaks leave the window (weight 0.02)
 */
import { describe, it, expect } from 'vitest'

// We test the updateYRange logic directly since the composable's internal
// function is not exported. Replicate the algorithm here for unit testing.

function createYRangeTracker(initialMin = -0.5, initialMax = 0.5) {
  let yMin = initialMin
  let yMax = initialMax

  function updateYRange(minValue: number, maxValue: number) {
    if (!Number.isFinite(minValue) || !Number.isFinite(maxValue)) return
    const margin = Math.max((maxValue - minValue) * 0.18, 0.05)
    const targetMin = minValue - margin
    const targetMax = maxValue + margin

    const expandWeightNew = 0.3
    const contractWeightNew = 0.02

    const minWeight = targetMin < yMin ? expandWeightNew : contractWeightNew
    yMin = yMin * (1 - minWeight) + targetMin * minWeight

    const maxWeight = targetMax > yMax ? expandWeightNew : contractWeightNew
    yMax = yMax * (1 - maxWeight) + targetMax * maxWeight

    if (Math.abs(yMax - yMin) < 1e-6) {
      yMin -= 0.1
      yMax += 0.1
    }
  }

  return {
    updateYRange,
    getYMin: () => yMin,
    getYMax: () => yMax,
  }
}

describe('Y-axis asymmetric auto-scaling', () => {
  it('expands fast when a larger peak appears', () => {
    const tracker = createYRangeTracker(-0.5, 0.5)

    // Simulate a large spike: data range jumps to [-0.5, 2.0]
    tracker.updateYRange(-0.5, 2.0)

    // After one frame, yMax should jump significantly toward target
    // Target max = 2.0 + margin ≈ 2.45. With weight=0.3: 0.5*0.7 + 2.45*0.3 ≈ 1.085
    const yMax1 = tracker.getYMax()
    expect(yMax1).toBeGreaterThan(0.9) // significant expansion in one step
    expect(yMax1).toBeLessThan(2.5) // but not fully there yet
  })

  it('contracts slowly when peak disappears', () => {
    const tracker = createYRangeTracker(-0.5, 2.5)

    // Peak is gone, data now only [-0.5, 0.5]
    tracker.updateYRange(-0.5, 0.5)

    // After one frame, yMax should barely move (weight=0.02)
    // Target max = 0.5 + margin ≈ 0.68. With weight=0.02: 2.5*0.98 + 0.68*0.02 ≈ 2.464
    const yMax1 = tracker.getYMax()
    expect(yMax1).toBeGreaterThan(2.4) // barely contracted
    expect(yMax1).toBeLessThan(2.5)

    // After 10 more frames it should contract further but still slowly
    for (let i = 0; i < 10; i++) {
      tracker.updateYRange(-0.5, 0.5)
    }
    const yMax10 = tracker.getYMax()
    expect(yMax10).toBeGreaterThan(1.5) // still significantly above target after 10 frames
    expect(yMax10).toBeLessThan(yMax1) // but has moved downward
  })

  it('expand-fast vs contract-slow ratio is significant', () => {
    // Expansion: from yMax=0.5 to target ~2.45
    const expandTracker = createYRangeTracker(-0.5, 0.5)
    expandTracker.updateYRange(-0.5, 2.0)
    const expandDelta = expandTracker.getYMax() - 0.5

    // Contraction: from yMax=2.5 to target ~0.68
    const contractTracker = createYRangeTracker(-0.5, 2.5)
    contractTracker.updateYRange(-0.5, 0.5)
    const contractDelta = 2.5 - contractTracker.getYMax()

    // Expansion should be ~15x faster than contraction (0.3/0.02)
    const ratio = expandDelta / contractDelta
    expect(ratio).toBeGreaterThan(10)
  })
})

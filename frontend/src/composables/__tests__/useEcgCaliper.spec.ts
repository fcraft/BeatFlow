import { describe, it, expect } from 'vitest'
import { pixelToMs, msToRate, useEcgCaliper } from '../useEcgCaliper'

describe('pixelToMs', () => {
  it('converts pixel distance to milliseconds', () => {
    // canvasWidth=1000, displaySeconds=5 → 5ms/px → 200px = 1000ms
    expect(pixelToMs(200, 1000, 5, 500)).toBe(1000)
  })
  it('returns 0 for 0 distance', () => {
    expect(pixelToMs(0, 1000, 5, 500)).toBe(0)
  })
  it('returns 0 for 0 canvas width', () => {
    expect(pixelToMs(100, 0, 5, 500)).toBe(0)
  })
})

describe('msToRate', () => {
  it('converts interval to bpm', () => {
    expect(msToRate(1000)).toBe(60)
    expect(msToRate(500)).toBe(120)
  })
  it('returns null for 0 interval', () => {
    expect(msToRate(0)).toBeNull()
  })
  it('returns null for negative interval', () => {
    expect(msToRate(-100)).toBeNull()
  })
})

describe('useEcgCaliper', () => {
  function create() {
    return useEcgCaliper({ canvasWidth: () => 1000, displaySeconds: 5, sampleRate: 500 })
  }

  it('starts inactive', () => {
    const c = create()
    expect(c.active.value).toBe(false)
  })

  it('enter activates and stores frozen data', () => {
    const c = create()
    c.enter(new Float32Array([1, 2, 3]))
    expect(c.active.value).toBe(true)
    expect(c.frozenData.value).toBeInstanceOf(Float32Array)
  })

  it('exit deactivates', () => {
    const c = create()
    c.enter(new Float32Array(0))
    c.exit()
    expect(c.active.value).toBe(false)
    expect(c.frozenData.value).toBeNull()
  })

  it('addMarker adds up to 6 markers', () => {
    const c = create()
    c.enter(new Float32Array(0))
    for (let i = 0; i < 7; i++) c.addMarker(i * 100)
    expect(c.markers.value).toHaveLength(6)
  })

  it('pairs are computed from sorted markers', () => {
    const c = create()
    c.enter(new Float32Array(0))
    c.addMarker(300)
    c.addMarker(100)
    expect(c.pairs.value).toHaveLength(1)
    expect(c.pairs.value[0].a.x).toBe(100)
    expect(c.pairs.value[0].b.x).toBe(300)
    expect(c.pairs.value[0].intervalMs).toBe(1000) // 200px * 5ms/px
    expect(c.pairs.value[0].bpm).toBe(60)
  })
})

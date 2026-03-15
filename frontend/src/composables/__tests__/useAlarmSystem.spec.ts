import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { ref, reactive, nextTick } from 'vue'
import {
  evaluateAlarms,
  createAlarmAudio,
  estimateDefibSuccess,
  useAlarmSystem,
  type AlarmState,
} from '../useAlarmSystem'

// ─── evaluateAlarms ───────────────────────────────────────────

describe('evaluateAlarms', () => {
  it('returns empty array for normal vitals', () => {
    const vitals = {
      heart_rate: 75,
      systolic_bp: 120,
      spo2: 98,
      respiratory_rate: 16,
      temperature: 36.8,
      rhythm: 'sinus',
    }
    expect(evaluateAlarms(vitals)).toEqual([])
  })

  it('HR > 120 → warning', () => {
    const alarms = evaluateAlarms({ heart_rate: 125 })
    expect(alarms).toHaveLength(1)
    expect(alarms[0].param).toBe('heart_rate')
    expect(alarms[0].level).toBe('warning')
  })

  it('HR > 150 → critical', () => {
    const alarms = evaluateAlarms({ heart_rate: 160 })
    expect(alarms).toHaveLength(1)
    expect(alarms[0].param).toBe('heart_rate')
    expect(alarms[0].level).toBe('critical')
  })

  it('HR < 50 → warning', () => {
    const alarms = evaluateAlarms({ heart_rate: 45 })
    expect(alarms).toHaveLength(1)
    expect(alarms[0].level).toBe('warning')
  })

  it('HR < 40 → critical', () => {
    const alarms = evaluateAlarms({ heart_rate: 35 })
    expect(alarms).toHaveLength(1)
    expect(alarms[0].level).toBe('critical')
  })

  it('SpO2 < 92 → warning', () => {
    const alarms = evaluateAlarms({ spo2: 90 })
    expect(alarms).toHaveLength(1)
    expect(alarms[0].param).toBe('spo2')
    expect(alarms[0].level).toBe('warning')
  })

  it('SpO2 < 85 → critical', () => {
    const alarms = evaluateAlarms({ spo2: 80 })
    expect(alarms).toHaveLength(1)
    expect(alarms[0].param).toBe('spo2')
    expect(alarms[0].level).toBe('critical')
  })

  it('rhythm "vf" → critical with "VF" in message', () => {
    const alarms = evaluateAlarms({ rhythm: 'vf' })
    expect(alarms).toHaveLength(1)
    expect(alarms[0].param).toBe('rhythm')
    expect(alarms[0].level).toBe('critical')
    expect(alarms[0].message).toContain('VF')
  })

  it('rhythm "asystole" → critical', () => {
    const alarms = evaluateAlarms({ rhythm: 'asystole' })
    expect(alarms).toHaveLength(1)
    expect(alarms[0].level).toBe('critical')
  })

  it('rhythm "vt" → critical with "VT" in message', () => {
    const alarms = evaluateAlarms({ rhythm: 'vt' })
    expect(alarms).toHaveLength(1)
    expect(alarms[0].level).toBe('critical')
    expect(alarms[0].message).toContain('VT')
  })

  it('SBP warning thresholds', () => {
    expect(evaluateAlarms({ systolic_bp: 85 })[0].level).toBe('warning')
    expect(evaluateAlarms({ systolic_bp: 170 })[0].level).toBe('warning')
  })

  it('SBP critical thresholds', () => {
    expect(evaluateAlarms({ systolic_bp: 60 })[0].level).toBe('critical')
    expect(evaluateAlarms({ systolic_bp: 210 })[0].level).toBe('critical')
  })

  it('RR warning and critical thresholds', () => {
    expect(evaluateAlarms({ respiratory_rate: 7 })[0].level).toBe('warning')
    expect(evaluateAlarms({ respiratory_rate: 35 })[0].level).toBe('warning')
    expect(evaluateAlarms({ respiratory_rate: 4 })[0].level).toBe('critical')
    expect(evaluateAlarms({ respiratory_rate: 45 })[0].level).toBe('critical')
  })

  it('temperature warning and critical thresholds', () => {
    expect(evaluateAlarms({ temperature: 35.5 })[0].level).toBe('warning')
    expect(evaluateAlarms({ temperature: 38.5 })[0].level).toBe('warning')
    expect(evaluateAlarms({ temperature: 34.5 })[0].level).toBe('critical')
    expect(evaluateAlarms({ temperature: 40.5 })[0].level).toBe('critical')
  })

  it('multiple alarms from multiple abnormal vitals', () => {
    const alarms = evaluateAlarms({ heart_rate: 160, spo2: 80, rhythm: 'vf' })
    expect(alarms.length).toBe(3)
  })

  it('alarm messages contain parameter label', () => {
    const alarms = evaluateAlarms({ heart_rate: 160 })
    expect(alarms[0].message).toContain('HR')
  })
})

// ─── createAlarmAudio ─────────────────────────────────────────

describe('createAlarmAudio', () => {
  let originalAudioContext: any

  beforeEach(() => {
    originalAudioContext = globalThis.AudioContext
  })

  afterEach(() => {
    ;(globalThis as any).AudioContext = originalAudioContext
  })

  it('plays warning beep when AudioContext is available', () => {
    const mockOscillator = {
      type: 'sine',
      frequency: { value: 0 },
      connect: vi.fn(),
      start: vi.fn(),
      stop: vi.fn(),
      disconnect: vi.fn(),
      onended: null as any,
    }
    const mockGain = {
      gain: { value: 1, setValueAtTime: vi.fn(), linearRampToValueAtTime: vi.fn() },
      connect: vi.fn(),
      disconnect: vi.fn(),
    }

    ;(globalThis as any).AudioContext = class {
      destination = {}
      state = 'running'
      createOscillator() { return mockOscillator }
      createGain() { return mockGain }
      async resume() {}
      async close() {}
    }

    const audio = createAlarmAudio()
    expect(audio.isAvailable()).toBe(true)
    audio.playWarning()
    expect(mockOscillator.frequency.value).toBe(440)
    expect(mockOscillator.start).toHaveBeenCalled()
    audio.dispose()
  })

  it('degrades gracefully when AudioContext is unavailable', () => {
    delete (globalThis as any).AudioContext

    const audio = createAlarmAudio()
    expect(audio.isAvailable()).toBe(false)
    // Should not throw
    audio.playWarning()
    audio.playCritical()
    audio.stop()
    audio.dispose()
  })

  it('playCritical starts repeating beeps', () => {
    vi.useFakeTimers()
    const startCalls: number[] = []
    const mockOscillator = {
      type: 'sine',
      frequency: { value: 0 },
      connect: vi.fn(),
      start: vi.fn(() => startCalls.push(1)),
      stop: vi.fn(),
      disconnect: vi.fn(),
      onended: null as any,
    }
    const mockGain = {
      gain: { value: 1, setValueAtTime: vi.fn(), linearRampToValueAtTime: vi.fn() },
      connect: vi.fn(),
      disconnect: vi.fn(),
    }

    ;(globalThis as any).AudioContext = class {
      destination = {}
      state = 'running'
      createOscillator() { return mockOscillator }
      createGain() { return mockGain }
      async resume() {}
      async close() {}
    }

    const audio = createAlarmAudio()
    audio.playCritical()
    expect(mockOscillator.frequency.value).toBe(880)
    expect(startCalls.length).toBe(1)

    // After 400ms, another beep should fire
    vi.advanceTimersByTime(400)
    expect(startCalls.length).toBe(2)

    audio.stop()
    vi.advanceTimersByTime(800)
    // No more beeps after stop
    expect(startCalls.length).toBe(2)

    audio.dispose()
    vi.useRealTimers()
  })
})

// ─── estimateDefibSuccess ─────────────────────────────────────

describe('estimateDefibSuccess', () => {
  it('returns base 0.55 with no modifiers', () => {
    expect(estimateDefibSuccess({})).toBeCloseTo(0.55)
  })

  it('amiodarone boosts probability', () => {
    expect(estimateDefibSuccess({ amiodarone_level: 1 })).toBeCloseTo(0.70)
  })

  it('damage_level reduces probability', () => {
    expect(estimateDefibSuccess({ damage_level: 1 })).toBeCloseTo(0.35)
  })

  it('defibrillation_count reduces probability', () => {
    expect(estimateDefibSuccess({ defibrillation_count: 5 })).toBeCloseTo(0.40)
  })

  it('clamps result to [0, 1]', () => {
    expect(estimateDefibSuccess({ damage_level: 5 })).toBe(0)
    expect(estimateDefibSuccess({ amiodarone_level: 10 })).toBe(1)
  })
})

// ─── useAlarmSystem composable ────────────────────────────────

describe('useAlarmSystem', () => {
  let originalAudioContext: any

  beforeEach(() => {
    originalAudioContext = globalThis.AudioContext
    // Provide a minimal AudioContext for composable tests
    ;(globalThis as any).AudioContext = class {
      destination = {}
      state = 'running'
      createOscillator() {
        return {
          type: 'sine', frequency: { value: 0 },
          connect: vi.fn(), start: vi.fn(), stop: vi.fn(),
          disconnect: vi.fn(), onended: null,
        }
      }
      createGain() {
        return {
          gain: { value: 1, setValueAtTime: vi.fn(), linearRampToValueAtTime: vi.fn() },
          connect: vi.fn(), disconnect: vi.fn(),
        }
      }
      async resume() {}
      async close() {}
    }
  })

  afterEach(() => {
    ;(globalThis as any).AudioContext = originalAudioContext
  })

  it('returns reactive alarm state', async () => {
    const vitals = reactive({ heart_rate: 75, spo2: 98 })
    const { activeAlarms, hasCritical, hasWarning, dispose } = useAlarmSystem(vitals)

    await nextTick()
    expect(activeAlarms.value).toEqual([])
    expect(hasCritical.value).toBe(false)
    expect(hasWarning.value).toBe(false)

    vitals.heart_rate = 130
    await nextTick()
    expect(activeAlarms.value.length).toBe(1)
    expect(hasWarning.value).toBe(true)

    dispose()
  })

  it('getAlarmLevel returns correct level for param', async () => {
    const vitals = reactive({ heart_rate: 160 })
    const { getAlarmLevel, dispose } = useAlarmSystem(vitals)

    await nextTick()
    expect(getAlarmLevel('heart_rate')).toBe('critical')
    expect(getAlarmLevel('spo2')).toBeNull()

    dispose()
  })

  it('muted ref suppresses audio', async () => {
    const muted = ref(true)
    const vitals = reactive({ heart_rate: 160 })
    const { activeAlarms, dispose } = useAlarmSystem(vitals, { muted })

    await nextTick()
    // Alarms still detected even when muted
    expect(activeAlarms.value.length).toBe(1)

    dispose()
  })
})

/**
 * Unit tests for useAudioPlayback composable
 *
 * 覆盖场景：
 *   1. 基本状态（initial / start / stop / volume）
 *   2. AudioWorklet 可用路径
 *   3. AudioWorklet 不可用 → ScriptProcessorNode 降级路径
 *   4. feedChunk 在两种路径下的行为
 *   5. 降噪模式滤波链
 *   6. 听诊模式滤波链
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { ref } from 'vue'
import { MockAudioContext, MockAudioContextNoWorklet } from '@/__tests__/setup'

vi.mock('vue', async (importOriginal) => {
  const actual = await importOriginal<typeof import('vue')>()
  return { ...actual, onUnmounted: vi.fn() }
})

import { useAudioPlayback } from '@/composables/useAudioPlayback'
import { AUSCULTATION_AREAS, type AuscultationAreaConfig } from '@/composables/useAuscultation'

// ── Helper：保存/恢复原始 AudioContext ──
let originalAudioContext: any

beforeEach(() => {
  originalAudioContext = (globalThis as any).AudioContext
})

afterEach(() => {
  (globalThis as any).AudioContext = originalAudioContext
})

// ════════════════════════════════════════════════════
// 基本状态
// ════════════════════════════════════════════════════
describe('useAudioPlayback — basic state', () => {
  it('should not be playing initially', () => {
    const { isPlaying } = useAudioPlayback()
    expect(isPlaying.value).toBe(false)
  })

  it('should have default volume of 0.7', () => {
    const { volume } = useAudioPlayback()
    expect(volume.value).toBe(0.7)
  })

  it('volume is reactive', () => {
    const { volume } = useAudioPlayback()
    volume.value = 0.3
    expect(volume.value).toBe(0.3)
  })

  it('stop without start is safe', () => {
    const { stop, isPlaying } = useAudioPlayback()
    stop()
    expect(isPlaying.value).toBe(false)
  })

  it('feedChunk without start is a silent no-op', () => {
    const { feedChunk } = useAudioPlayback()
    expect(() => feedChunk([0, 0.1, -0.1])).not.toThrow()
  })
})

// ════════════════════════════════════════════════════
// AudioWorklet 可用路径
// ════════════════════════════════════════════════════
describe('useAudioPlayback — AudioWorklet path', () => {
  beforeEach(() => {
    ;(globalThis as any).AudioContext = MockAudioContext
  })

  it('start sets isPlaying=true', async () => {
    const { start, isPlaying } = useAudioPlayback()
    await start()
    expect(isPlaying.value).toBe(true)
  })

  it('start is idempotent', async () => {
    const { start, isPlaying } = useAudioPlayback()
    await start()
    await start()
    expect(isPlaying.value).toBe(true)
  })

  it('stop sets isPlaying=false', async () => {
    const audio = useAudioPlayback()
    await audio.start()
    audio.stop()
    expect(audio.isPlaying.value).toBe(false)
  })

  it('feedChunk does not throw when playing', async () => {
    const audio = useAudioPlayback()
    await audio.start()
    expect(() => audio.feedChunk([0.1, 0.2, 0.3])).not.toThrow()
    audio.stop()
  })

  it('feedChunk handles a realistic 400-sample PCG chunk', async () => {
    const audio = useAudioPlayback()
    await audio.start()
    const chunk = Array.from({ length: 400 }, (_, i) =>
      0.3 * Math.sin(2 * Math.PI * 50 * i / 4000),
    )
    expect(() => audio.feedChunk(chunk)).not.toThrow()
    audio.stop()
  })

  it('feedChunk accepts timeline metadata chunks', async () => {
    const audio = useAudioPlayback()
    await audio.start()
    const chunk = Array.from({ length: 400 }, (_, i) =>
      0.2 * Math.sin(2 * Math.PI * 70 * i / 4000),
    )
    expect(() => audio.feedChunk({
      samples: chunk,
      startSample: 0,
      seq: 0,
      receivedAtMs: 0,
      chunkDurationMs: 100,
      serverElapsedSec: 0,
    })).not.toThrow()
    audio.stop()
  })
})

// ════════════════════════════════════════════════════
// AudioWorklet 不可用 → ScriptProcessorNode 降级
// ════════════════════════════════════════════════════
describe('useAudioPlayback — ScriptProcessor fallback', () => {
  beforeEach(() => {
    ;(globalThis as any).AudioContext = MockAudioContextNoWorklet
  })

  it('start succeeds when AudioWorklet is undefined', async () => {
    const { start, isPlaying } = useAudioPlayback()
    await start()
    expect(isPlaying.value).toBe(true)
  })

  it('feedChunk works in fallback mode', async () => {
    const audio = useAudioPlayback()
    await audio.start()
    expect(() => audio.feedChunk([0.1, 0.2, 0.3, 0.4])).not.toThrow()
    audio.stop()
  })

  it('stop cleans up fallback node', async () => {
    const audio = useAudioPlayback()
    await audio.start()
    audio.stop()
    expect(audio.isPlaying.value).toBe(false)
    // start again should work (no stale state)
    await audio.start()
    expect(audio.isPlaying.value).toBe(true)
    audio.stop()
  })
})

// ════════════════════════════════════════════════════
// 降噪模式
// ════════════════════════════════════════════════════
describe('useAudioPlayback — noise reduction mode', () => {
  beforeEach(() => {
    ;(globalThis as any).AudioContext = MockAudioContext
  })

  it('starts successfully with noise reduction enabled', async () => {
    const nr = ref(true)
    const audio = useAudioPlayback({ noiseReduction: nr })
    await audio.start()
    expect(audio.isPlaying.value).toBe(true)
    audio.stop()
  })

  it('starts successfully with noise reduction disabled', async () => {
    const nr = ref(false)
    const audio = useAudioPlayback({ noiseReduction: nr })
    await audio.start()
    expect(audio.isPlaying.value).toBe(true)
    audio.stop()
  })

  it('feedChunk works with noise reduction enabled', async () => {
    const nr = ref(true)
    const audio = useAudioPlayback({ noiseReduction: nr })
    await audio.start()
    expect(() => audio.feedChunk([0.1, -0.05, 0.2])).not.toThrow()
    audio.stop()
  })

  it('noise reduction works in ScriptProcessor fallback', async () => {
    ;(globalThis as any).AudioContext = MockAudioContextNoWorklet
    const nr = ref(true)
    const audio = useAudioPlayback({ noiseReduction: nr })
    await audio.start()
    expect(audio.isPlaying.value).toBe(true)
    audio.stop()
  })
})

// ════════════════════════════════════════════════════
// 听诊模式
// ════════════════════════════════════════════════════
describe('useAudioPlayback — auscultation mode', () => {
  beforeEach(() => {
    ;(globalThis as any).AudioContext = MockAudioContext
  })

  it('starts with auscultation config (mitral area)', async () => {
    const config = ref<AuscultationAreaConfig | null>(AUSCULTATION_AREAS.mitral)
    const audio = useAudioPlayback({ auscultationConfig: config })
    await audio.start()
    expect(audio.isPlaying.value).toBe(true)
    audio.stop()
  })

  it('starts with auscultation config (aortic area)', async () => {
    const config = ref<AuscultationAreaConfig | null>(AUSCULTATION_AREAS.aortic)
    const audio = useAudioPlayback({ auscultationConfig: config })
    await audio.start()
    expect(audio.isPlaying.value).toBe(true)
    audio.stop()
  })

  it('starts with null config (normal mode)', async () => {
    const config = ref<AuscultationAreaConfig | null>(null)
    const audio = useAudioPlayback({ auscultationConfig: config })
    await audio.start()
    expect(audio.isPlaying.value).toBe(true)
    audio.stop()
  })

  it('feedChunk works in auscultation mode', async () => {
    const config = ref<AuscultationAreaConfig | null>(AUSCULTATION_AREAS.tricuspid)
    const audio = useAudioPlayback({ auscultationConfig: config })
    await audio.start()
    const chunk = Array.from({ length: 400 }, (_, i) =>
      0.2 * Math.sin(2 * Math.PI * 60 * i / 4000),
    )
    expect(() => audio.feedChunk(chunk)).not.toThrow()
    audio.stop()
  })

  it('auscultation + noise reduction combined', async () => {
    const config = ref<AuscultationAreaConfig | null>(AUSCULTATION_AREAS.pulmonic)
    const nr = ref(true)
    const audio = useAudioPlayback({ auscultationConfig: config, noiseReduction: nr })
    await audio.start()
    expect(audio.isPlaying.value).toBe(true)
    expect(() => audio.feedChunk([0.1, 0.2])).not.toThrow()
    audio.stop()
  })

  it('updateAuscultationFilters does not throw when playing', async () => {
    const config = ref<AuscultationAreaConfig | null>(AUSCULTATION_AREAS.mitral)
    const audio = useAudioPlayback({ auscultationConfig: config })
    await audio.start()
    expect(() => audio.updateAuscultationFilters(AUSCULTATION_AREAS.aortic)).not.toThrow()
    audio.stop()
  })

  it('updateAuscultationFilters is safe when not playing', () => {
    const config = ref<AuscultationAreaConfig | null>(AUSCULTATION_AREAS.mitral)
    const audio = useAudioPlayback({ auscultationConfig: config })
    // Should not throw even without starting
    expect(() => audio.updateAuscultationFilters(AUSCULTATION_AREAS.aortic)).not.toThrow()
  })

  it('auscultation works in ScriptProcessor fallback', async () => {
    ;(globalThis as any).AudioContext = MockAudioContextNoWorklet
    const config = ref<AuscultationAreaConfig | null>(AUSCULTATION_AREAS.mitral)
    const audio = useAudioPlayback({ auscultationConfig: config })
    await audio.start()
    expect(audio.isPlaying.value).toBe(true)
    audio.stop()
  })
})

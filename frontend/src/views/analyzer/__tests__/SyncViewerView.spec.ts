import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest'
import SyncViewerView from '../SyncViewerView.vue'

vi.mock('vue-router', async (importOriginal) => {
  const actual = await importOriginal<typeof import('vue-router')>()
  return {
    ...actual,
    useRoute: () => ({ params: { id: 'assoc-test-id' } }),
  }
})

const createJsonResponse = (data: unknown) => ({
  ok: true,
  json: async () => data,
})

const associationResponse = {
  id: 'assoc-test-id',
  name: '同步测试关联',
  notes: '',
  pcg_offset: 0,
  video_offset: 0,
  ecg_file: { id: 'ecg-1', original_filename: 'ecg.wav' },
  pcg_file: { id: 'pcg-1', original_filename: 'pcg.wav' },
  video_file: null,
}

const waveformResponse = {
  samples: [0, 0.4, -0.2, 0.3, -0.1, 0],
  duration: 2,
  region_start: 0,
  region_end: 2,
}

const ctx2d = {
  clearRect: vi.fn(),
  fillRect: vi.fn(),
  beginPath: vi.fn(),
  moveTo: vi.fn(),
  lineTo: vi.fn(),
  stroke: vi.fn(),
  fillText: vi.fn(),
  strokeStyle: '',
  fillStyle: '',
  lineWidth: 1,
  lineJoin: 'round',
  font: '9px monospace',
  textAlign: 'center',
}

let fetchMock: any

describe('SyncViewerView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.setItem('token', 'test-token')

    vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(ctx2d as unknown as CanvasRenderingContext2D)
    vi.spyOn(HTMLMediaElement.prototype, 'load').mockImplementation(() => {})

    fetchMock = vi.fn(async (input: string | URL | Request) => {
      const url = typeof input === 'string' ? input : input instanceof URL ? input.toString() : input.url

      if (url.includes('/api/v1/associations/assoc-test-id')) {
        return createJsonResponse(associationResponse)
      }

      if (url.includes('/api/v1/files/ecg-1/waveform')) {
        return createJsonResponse(waveformResponse)
      }

      if (url.includes('/api/v1/files/pcg-1/waveform')) {
        return createJsonResponse(waveformResponse)
      }

      throw new Error(`Unhandled fetch: ${url}`)
    })
    vi.stubGlobal('fetch', fetchMock)
  })

  afterEach(() => {
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
    localStorage.clear()
  })

  it('先触发 play 再 seek 到正确位置（保持用户手势上下文）', async () => {
    const wrapper = mount(SyncViewerView, {
      global: {
        stubs: {
          AppLayout: { template: '<div><slot /></div>' },
          RouterLink: { template: '<a><slot /></a>' },
        },
        mocks: {
          $router: { back: vi.fn() },
        },
      },
    })

    await flushPromises()
    await flushPromises()

    const audioEl = wrapper.get('audio').element as HTMLAudioElement
    const mediaState = {
      currentTime: 0,
      pendingTime: 0,
      seeking: false,
      playTimes: [] as number[],
    }

    const playSpy = vi.fn(async () => {
      mediaState.playTimes.push(mediaState.currentTime)
    })

    Object.defineProperty(audioEl, 'duration', {
      configurable: true,
      get: () => 2,
    })
    Object.defineProperty(audioEl, 'readyState', {
      configurable: true,
      get: () => HTMLMediaElement.HAVE_METADATA,
    })
    Object.defineProperty(audioEl, 'seeking', {
      configurable: true,
      get: () => mediaState.seeking,
    })
    Object.defineProperty(audioEl, 'currentTime', {
      configurable: true,
      get: () => mediaState.currentTime,
      set: (value: number) => {
        mediaState.pendingTime = value
        mediaState.seeking = true
        setTimeout(() => {
          mediaState.currentTime = mediaState.pendingTime
          mediaState.seeking = false
          audioEl.dispatchEvent(new Event('seeked'))
          audioEl.dispatchEvent(new Event('canplay'))
        }, 20)
      },
    })
    Object.defineProperty(audioEl, 'play', {
      configurable: true,
      value: playSpy,
    })
    Object.defineProperty(audioEl, 'pause', {
      configurable: true,
      value: vi.fn(),
    })

    const vm = wrapper.vm as unknown as { playPos: number; play: () => Promise<void> }
    vm.playPos = 1.25

    await vm.play()

    // play() 应该立刻被调用（在 await syncAllToPos 之前），保持用户手势上下文
    expect(playSpy).toHaveBeenCalledTimes(1)
    // seek 完成后 audio 应该在正确的位置
    expect(mediaState.currentTime).toBeCloseTo(1.25, 2)

    wrapper.unmount()
  })

  it('短文件 detail 已完整覆盖时不会重复请求 waveform', async () => {
    const wrapper = mount(SyncViewerView, {
      global: {
        stubs: {
          AppLayout: { template: '<div><slot /></div>' },
          RouterLink: { template: '<a><slot /></a>' },
        },
        mocks: {
          $router: { back: vi.fn() },
        },
      },
    })

    await flushPromises()
    await flushPromises()

    const vm = wrapper.vm as unknown as {
      isPlaying: boolean
      ecgDuration: number
      ecgViewSecs: number
      ecgViewStart: number
      ecgDetailRange: { start: number; end: number } | null
      checkPlaybackDetailCoverage: (track: 'ecg' | 'pcg') => void
    }

    const baselineFetchCalls = fetchMock.mock.calls.length
    vm.isPlaying = true
    vm.ecgDuration = 2
    vm.ecgViewSecs = 2
    vm.ecgViewStart = 0
    vm.ecgDetailRange = { start: 0, end: 2 }

    vm.checkPlaybackDetailCoverage('ecg')
    await flushPromises()

    expect(fetchMock).toHaveBeenCalledTimes(baselineFetchCalls)

    wrapper.unmount()
  })
})

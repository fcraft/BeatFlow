/**
 * PCG 实时音频播放 composable
 *
 * 接收 4000Hz PCG chunk，上采样到 AudioContext.sampleRate，
 * 通过 AudioWorklet / ScriptProcessorNode 播放。
 *
 * 新版重点：
 * 1. 支持带 startSample 的 chunk 调度，按统一时间轴播放
 * 2. 给音频队列增加上限，避免“越播越晚”
 * 3. 当 chunk 明显迟到时自动重同步
 */
import { ref, watch, onUnmounted, type Ref } from 'vue'
import type { AuscultationAreaConfig } from './useAuscultation'
import type { SignalChunk } from '@/store/virtualHuman'

const PCG_SAMPLE_RATE = 4000
const TARGET_BUFFER_SEC = 0.12
const DISPATCH_LOOKAHEAD_SEC = 0.03
const MAX_AUDIO_QUEUE_SEC = 0.35
const MAX_AUDIO_LATE_SEC = 0.18

export interface AudioPlaybackOptions {
  noiseReduction?: Ref<boolean>
  auscultationConfig?: Ref<AuscultationAreaConfig | null>
}

export function useAudioPlayback(options?: AudioPlaybackOptions) {
  const isPlaying = ref(false)
  const volume = ref(0.7)

  let audioCtx: AudioContext | null = null
  let workletNode: AudioWorkletNode | null = null
  let scriptNode: ScriptProcessorNode | null = null
  let gainNode: GainNode | null = null
  let hpFilter: BiquadFilterNode | null = null
  let lpFilter: BiquadFilterNode | null = null
  let notch50: BiquadFilterNode | null = null
  let notch60: BiquadFilterNode | null = null
  let resonancePeak: BiquadFilterNode | null = null
  let ready = false

  let spBuffer: Float32Array[] = []
  let spReadOffset = 0
  let dispatchTimers: number[] = []
  let audioAnchorSample: number | null = null
  let audioAnchorTime: number | null = null
  let scheduledUntilSec: number | null = null

  function resample(input: number[], fromRate: number, toRate: number): Float32Array {
    if (fromRate === toRate) return new Float32Array(input)

    const ratio = toRate / fromRate
    const outLen = Math.max(1, Math.round(input.length * ratio))
    const out = new Float32Array(outLen)

    for (let i = 0; i < outLen; i++) {
      const srcIdx = i / ratio
      const lo = Math.floor(srcIdx)
      const hi = Math.min(lo + 1, input.length - 1)
      const frac = srcIdx - lo
      out[i] = input[lo] * (1 - frac) + input[hi] * frac
    }
    return out
  }

  function isWorkletAvailable(ctx: AudioContext): boolean {
    return !!(ctx.audioWorklet && typeof ctx.audioWorklet.addModule === 'function')
  }

  function clearDispatchTimers() {
    dispatchTimers.forEach((timer) => window.clearTimeout(timer))
    dispatchTimers = []
  }

  function clearRuntimeQueue() {
    if (workletNode) {
      workletNode.port.postMessage({ type: 'clear' })
    }
    spBuffer = []
    spReadOffset = 0
  }

  function createFilterChain(ctx: AudioContext): { input: AudioNode; output: AudioNode } {
    const nr = options?.noiseReduction?.value ?? false
    const ausc = options?.auscultationConfig?.value ?? null

    if (ausc) {
      hpFilter = ctx.createBiquadFilter()
      hpFilter.type = 'highpass'
      hpFilter.frequency.value = ausc.hpFreq
      hpFilter.Q.value = ausc.hpQ

      lpFilter = ctx.createBiquadFilter()
      lpFilter.type = 'lowpass'
      lpFilter.frequency.value = ausc.lpFreq
      lpFilter.Q.value = ausc.lpQ

      resonancePeak = ctx.createBiquadFilter()
      resonancePeak.type = 'peaking'
      resonancePeak.frequency.value = ausc.resonanceFreq
      resonancePeak.gain.value = ausc.resonanceGain
      resonancePeak.Q.value = ausc.resonanceQ

      hpFilter.connect(lpFilter)
      lpFilter.connect(resonancePeak)

      let lastNode: AudioNode = resonancePeak
      if (nr) {
        notch50 = ctx.createBiquadFilter()
        notch50.type = 'notch'
        notch50.frequency.value = 50
        notch50.Q.value = 30

        notch60 = ctx.createBiquadFilter()
        notch60.type = 'notch'
        notch60.frequency.value = 60
        notch60.Q.value = 30

        lastNode.connect(notch50)
        notch50.connect(notch60)
        lastNode = notch60
      }

      return { input: hpFilter, output: lastNode }
    }

    if (nr) {
      hpFilter = ctx.createBiquadFilter()
      hpFilter.type = 'highpass'
      hpFilter.frequency.value = 25
      hpFilter.Q.value = 1.0

      notch50 = ctx.createBiquadFilter()
      notch50.type = 'notch'
      notch50.frequency.value = 50
      notch50.Q.value = 30

      notch60 = ctx.createBiquadFilter()
      notch60.type = 'notch'
      notch60.frequency.value = 60
      notch60.Q.value = 30

      lpFilter = ctx.createBiquadFilter()
      lpFilter.type = 'lowpass'
      lpFilter.frequency.value = 500
      lpFilter.Q.value = 1.0

      resonancePeak = ctx.createBiquadFilter()
      resonancePeak.type = 'peaking'
      resonancePeak.frequency.value = 80
      resonancePeak.gain.value = 3
      resonancePeak.Q.value = 1.0

      hpFilter.connect(notch50)
      notch50.connect(notch60)
      notch60.connect(lpFilter)
      lpFilter.connect(resonancePeak)

      return { input: hpFilter, output: resonancePeak }
    }

    hpFilter = ctx.createBiquadFilter()
    hpFilter.type = 'highpass'
    hpFilter.frequency.value = 20
    hpFilter.Q.value = 0.707

    lpFilter = ctx.createBiquadFilter()
    lpFilter.type = 'lowpass'
    lpFilter.frequency.value = 600
    lpFilter.Q.value = 0.707

    hpFilter.connect(lpFilter)
    return { input: hpFilter, output: lpFilter }
  }

  function updateAuscultationFilters(config: AuscultationAreaConfig) {
    if (!audioCtx || !hpFilter || !lpFilter) return
    const t = audioCtx.currentTime
    const rampDur = 0.15

    hpFilter.frequency.linearRampToValueAtTime(config.hpFreq, t + rampDur)
    hpFilter.Q.linearRampToValueAtTime(config.hpQ, t + rampDur)

    lpFilter.frequency.linearRampToValueAtTime(config.lpFreq, t + rampDur)
    lpFilter.Q.linearRampToValueAtTime(config.lpQ, t + rampDur)

    if (resonancePeak) {
      resonancePeak.frequency.linearRampToValueAtTime(config.resonanceFreq, t + rampDur)
      resonancePeak.gain.linearRampToValueAtTime(config.resonanceGain, t + rampDur)
      resonancePeak.Q.linearRampToValueAtTime(config.resonanceQ, t + rampDur)
    }

    if (gainNode) {
      gainNode.gain.linearRampToValueAtTime(
        volume.value * config.gainMultiplier,
        t + rampDur,
      )
    }
  }

  function onAudioProcess(e: AudioProcessingEvent) {
    const output = e.outputBuffer.getChannelData(0)
    let written = 0

    while (written < output.length && spBuffer.length > 0) {
      const chunk = spBuffer[0]
      const available = chunk.length - spReadOffset
      const toCopy = Math.min(available, output.length - written)

      output.set(chunk.subarray(spReadOffset, spReadOffset + toCopy), written)
      written += toCopy
      spReadOffset += toCopy

      if (spReadOffset >= chunk.length) {
        spBuffer.shift()
        spReadOffset = 0
      }
    }

    if (written < output.length) {
      output.fill(0, written)
    }
  }

  function enqueueUpsampled(samples: Float32Array) {
    if (!audioCtx || !ready) return

    if (workletNode) {
      workletNode.port.postMessage({ type: 'samples', samples }, [samples.buffer])
    } else if (scriptNode) {
      spBuffer.push(samples)
    }
  }

  function resetAudioTimeline(startSample: number) {
    if (!audioCtx) return
    clearDispatchTimers()
    clearRuntimeQueue()
    audioAnchorSample = startSample
    audioAnchorTime = audioCtx.currentTime + TARGET_BUFFER_SEC
    scheduledUntilSec = audioAnchorTime
  }

  function scheduleUpsampled(samples: Float32Array, startTimeSec: number) {
    if (!audioCtx || !ready) return
    const now = audioCtx.currentTime
    const dispatchAt = Math.max(now, startTimeSec - DISPATCH_LOOKAHEAD_SEC)
    const delayMs = Math.max(0, (dispatchAt - now) * 1000)
    const timer = window.setTimeout(() => {
      enqueueUpsampled(samples)
      dispatchTimers = dispatchTimers.filter((id) => id !== timer)
    }, delayMs)
    dispatchTimers.push(timer)
  }

  function feedChunk(input: number[] | SignalChunk) {
    if (!audioCtx || !ready) return

    const samples = Array.isArray(input) ? input : input.samples
    if (!samples.length) return

    const upsampled = resample(samples, PCG_SAMPLE_RATE, audioCtx.sampleRate)

    if (Array.isArray(input)) {
      enqueueUpsampled(upsampled)
      return
    }

    if (audioAnchorSample === null || audioAnchorTime === null) {
      resetAudioTimeline(input.startSample)
    }
    if (audioAnchorSample === null || audioAnchorTime === null) {
      enqueueUpsampled(upsampled)
      return
    }

    let expectedStart = audioAnchorTime + (input.startSample - audioAnchorSample) / PCG_SAMPLE_RATE
    const now = audioCtx.currentTime
    const queueLead = (scheduledUntilSec ?? now) - now
    const tooLate = expectedStart < now - MAX_AUDIO_LATE_SEC
    const tooFarAhead = queueLead > MAX_AUDIO_QUEUE_SEC

    if (tooLate || tooFarAhead) {
      resetAudioTimeline(input.startSample)
      if (audioAnchorSample === null || audioAnchorTime === null) {
        enqueueUpsampled(upsampled)
        return
      }
      expectedStart = audioAnchorTime
    }

    const chunkSec = upsampled.length / audioCtx.sampleRate
    const queueStart = Math.max(expectedStart, scheduledUntilSec ?? expectedStart)
    scheduledUntilSec = queueStart + chunkSec
    scheduleUpsampled(upsampled, queueStart)
  }

  async function start() {
    if (isPlaying.value) return

    try {
      audioCtx = new AudioContext()
      if (audioCtx.state === 'suspended') {
        await audioCtx.resume()
      }

      gainNode = audioCtx.createGain()
      const ausc = options?.auscultationConfig?.value
      const gainMul = ausc?.gainMultiplier ?? 1.0
      gainNode.gain.value = volume.value * gainMul
      gainNode.connect(audioCtx.destination)

      const filters = createFilterChain(audioCtx)
      filters.output.connect(gainNode)

      if (isWorkletAvailable(audioCtx)) {
        await audioCtx.audioWorklet.addModule('/pcg-playback-processor.js')
        workletNode = new AudioWorkletNode(audioCtx, 'pcg-playback-processor')
        workletNode.connect(filters.input)
      } else {
        scriptNode = audioCtx.createScriptProcessor(4096, 0, 1)
        scriptNode.onaudioprocess = onAudioProcess
        scriptNode.connect(filters.input)
        spBuffer = []
        spReadOffset = 0
      }

      clearDispatchTimers()
      clearRuntimeQueue()
      audioAnchorSample = null
      audioAnchorTime = null
      scheduledUntilSec = null
      ready = true
      isPlaying.value = true
    } catch (err) {
      console.error('[useAudioPlayback] Failed to start:', err)
      cleanup()
    }
  }

  function stop() {
    cleanup()
    isPlaying.value = false
  }

  function cleanup() {
    ready = false
    clearDispatchTimers()
    audioAnchorSample = null
    audioAnchorTime = null
    scheduledUntilSec = null
    clearRuntimeQueue()

    if (workletNode) {
      workletNode.disconnect()
      workletNode = null
    }
    if (scriptNode) {
      scriptNode.onaudioprocess = null
      scriptNode.disconnect()
      scriptNode = null
    }
    if (hpFilter) { hpFilter.disconnect(); hpFilter = null }
    if (lpFilter) { lpFilter.disconnect(); lpFilter = null }
    if (notch50) { notch50.disconnect(); notch50 = null }
    if (notch60) { notch60.disconnect(); notch60 = null }
    if (resonancePeak) { resonancePeak.disconnect(); resonancePeak = null }
    if (gainNode) { gainNode.disconnect(); gainNode = null }
    if (audioCtx) {
      audioCtx.close().catch(() => {})
      audioCtx = null
    }
  }

  watch(volume, (v) => {
    if (gainNode && audioCtx) {
      const ausc = options?.auscultationConfig?.value
      const gainMul = ausc?.gainMultiplier ?? 1.0
      gainNode.gain.setValueAtTime(v * gainMul, audioCtx.currentTime)
    }
  })

  if (options?.auscultationConfig) {
    watch(options.auscultationConfig, (config) => {
      if (config && ready) {
        updateAuscultationFilters(config)
      }
    })
  }

  if (options?.noiseReduction) {
    watch(options.noiseReduction, () => {
      if (isPlaying.value) {
        stop()
        start()
      }
    })
  }

  onUnmounted(cleanup)

  return { isPlaying, volume, feedChunk, start, stop, updateAuscultationFilters }
}

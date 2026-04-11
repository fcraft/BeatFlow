/**
 * 环形缓冲区 + requestAnimationFrame 实时波形绘制 composable。
 *
 * 渲染模式: **扫描线覆盖** (sweep / overwrite)
 *   - 维护一个屏幕像素级持久缓冲 (screenBuffer)
 *   - 新数据到达时，只更新扫描头扫过的像素
 *   - 扫描头左侧 = 新波形，右侧 = 旧波形（上一轮残留）
 *   - 类似真实 ICU 监护仪
 *
 * Feature 2: 可选高斯平滑滤波 (off / low / high)
 */
import { onUnmounted, type Ref, type ComputedRef, isRef } from 'vue'
import type { SignalChunk } from '@/store/virtualHuman'

export type SmoothingLevel = 'off' | 'low' | 'high'

export interface ScrollingCanvasOptions {
  canvasRef: Ref<HTMLCanvasElement | null>
  sampleRate: number
  displaySeconds?: number
  lineColor?: string
  backgroundColor?: string
  gridColor?: string
  label?: string
  playbackDelayMs?: number
  drawOverlay?: (ctx: CanvasRenderingContext2D, w: number, h: number) => void
  smoothingLevel?: Ref<SmoothingLevel> | ComputedRef<SmoothingLevel>
}

function getNowMs() {
  return typeof performance !== 'undefined' && typeof performance.now === 'function'
    ? performance.now()
    : Date.now()
}

const GAUSSIAN_KERNELS: Record<SmoothingLevel, Float32Array | null> = {
  off: null,
  low: new Float32Array([0.15, 0.70, 0.15]),
  high: new Float32Array([0.03, 0.10, 0.22, 0.30, 0.22, 0.10, 0.03]),
}

function applyGaussianSmoothing(points: Float32Array, level: SmoothingLevel): void {
  const kernel = GAUSSIAN_KERNELS[level]
  if (!kernel) return
  const len = points.length
  const halfK = Math.floor(kernel.length / 2)
  const tmp = new Float32Array(len)
  for (let i = 0; i < len; i++) {
    let sum = 0, wSum = 0
    for (let k = 0; k < kernel.length; k++) {
      const idx = i + k - halfK
      if (idx >= 0 && idx < len) { sum += points[idx] * kernel[k]; wSum += kernel[k] }
    }
    tmp[i] = wSum > 0 ? sum / wSum : points[i]
  }
  points.set(tmp)
}

export function useScrollingCanvas(options: ScrollingCanvasOptions) {
  const {
    canvasRef, sampleRate,
    displaySeconds = 5,
    lineColor = '#22c55e',
    backgroundColor = '#111827',
    gridColor = 'rgba(55,65,81,0.5)',
    label = '',
    playbackDelayMs = 180,
    drawOverlay,
    smoothingLevel: smoothingLevelRef,
  } = options

  const historySeconds = Math.max(displaySeconds + 2, displaySeconds + playbackDelayMs / 1000 + 1)
  const bufferSize = Math.max(4, Math.round(sampleRate * historySeconds))
  const displaySamples = Math.max(2, Math.round(sampleRate * displaySeconds))
  const playbackDelaySamples = Math.max(1, Math.round(sampleRate * playbackDelayMs / 1000))

  // ── Sample ring buffer ──
  const buffer = new Float32Array(bufferSize)
  let writePos = 0
  let storedSamples = 0
  let latestEndSample = 0
  let playbackOriginMs = 0
  let playbackOriginSample = 0
  let hasTimeline = false

  // ── Screen pixel buffer (persistent across frames) ──
  const SCREEN_BUF_SIZE = 2048
  const screenValues = new Float32Array(SCREEN_BUF_SIZE)
  const screenWritten = new Uint8Array(SCREEN_BUF_SIZE)
  let screenWidth = 0
  let sweepPx = 0
  let prevSweepPx = -1    // previous frame's sweep position
  let sweepOriginPlayhead = 0  // playhead value when sweep started
  let sweepInited = false

  // ── Animation state ──
  let animId = 0
  let running = false
  let yMin = 0, yMax = 0, yRangeInitialized = false

  // ── Frame-locked virtual playhead ──
  let virtualPlayhead = 0
  let lastFrameTime = 0
  let virtualPlayheadActive = false

  function earliestStoredSample() { return latestEndSample - storedSamples }

  function writeValue(sample: number) {
    buffer[writePos] = sample
    writePos = (writePos + 1) % bufferSize
    storedSamples = Math.min(bufferSize, storedSamples + 1)
  }

  function sampleAt(absSample: number) {
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
    for (let i = 0; i < gapSamples; i++) writeValue(padValue)
    latestEndSample += gapSamples
  }

  function appendSamples(input: number[] | SignalChunk) {
    const chunk = Array.isArray(input)
      ? { samples: input, startSample: latestEndSample, receivedAtMs: getNowMs(), seq: -1, chunkDurationMs: 0, serverElapsedSec: null }
      : input
    if (!chunk.samples.length) return

    let startSample = Number.isFinite(chunk.startSample) ? chunk.startSample : latestEndSample
    let samples = chunk.samples

    if (!hasTimeline) { latestEndSample = startSample; hasTimeline = true }

    if (startSample < latestEndSample) {
      const overlap = latestEndSample - startSample
      if (overlap >= samples.length) return
      samples = samples.slice(overlap)
      startSample = latestEndSample
    } else if (startSample > latestEndSample) {
      fillGap(startSample - latestEndSample)
    }

    for (let i = 0; i < samples.length; i++) writeValue(samples[i])
    latestEndSample = startSample + samples.length

    // Drift correction
    const desiredPlayhead = Math.max(earliestStoredSample(), latestEndSample - playbackDelaySamples)
    if (playbackOriginMs === 0) {
      playbackOriginSample = desiredPlayhead
      playbackOriginMs = chunk.receivedAtMs
      virtualPlayhead = desiredPlayhead
      lastFrameTime = chunk.receivedAtMs
      virtualPlayheadActive = true
    } else {
      const est = estimatePlaybackSample(chunk.receivedAtMs)
      const drift = desiredPlayhead - est
      if (Math.abs(drift) > sampleRate * 2.0) {
        playbackOriginSample = desiredPlayhead; playbackOriginMs = chunk.receivedAtMs
      } else if (Math.abs(drift) > sampleRate * 0.5) {
        playbackOriginSample = est + drift * 0.15; playbackOriginMs = chunk.receivedAtMs
      } else if (Math.abs(drift) > sampleRate * 0.02) {
        playbackOriginSample = est + drift * 0.2; playbackOriginMs = chunk.receivedAtMs
      }
    }
  }

  function estimatePlaybackSample(nowMs = getNowMs(), frameLocked = false) {
    if (!hasTimeline || playbackOriginMs === 0) return latestEndSample
    if (frameLocked && virtualPlayheadActive) {
      const dt = lastFrameTime > 0 ? Math.max(0, Math.min(50, nowMs - lastFrameTime)) : 16.67
      virtualPlayhead += (dt / 1000) * sampleRate
      const wall = playbackOriginSample + ((nowMs - playbackOriginMs) / 1000) * sampleRate
      virtualPlayhead += (wall - virtualPlayhead) * 0.02
      lastFrameTime = nowMs
      return Math.max(earliestStoredSample(), Math.min(latestEndSample - 1, virtualPlayhead))
    }
    const elapsed = ((nowMs - playbackOriginMs) / 1000) * sampleRate
    return Math.max(earliestStoredSample(), Math.min(latestEndSample - 1, playbackOriginSample + elapsed))
  }

  // ── Update screen buffer: advance sweep head from lastPlayhead to currentPlayhead ──
  function updateScreenBuffer(currentPlayhead: number, w: number) {
    if (w <= 0) return

    // Handle canvas resize or first init
    if (w !== screenWidth || !sweepInited) {
      screenWidth = w
      screenValues.fill(0)
      screenWritten.fill(0)
      sweepOriginPlayhead = currentPlayhead
      prevSweepPx = -1
      sweepPx = 0
      sweepInited = true
      return
    }

    // Compute sweep position directly from elapsed playhead (no incremental accumulation)
    const elapsedSamples = currentPlayhead - sweepOriginPlayhead
    const totalPixelsAdvanced = (elapsedSamples / displaySamples) * w
    const newSweepPx = Math.floor(totalPixelsAdvanced % w)

    // How many pixels to fill since last frame?
    let pixelsToFill: number
    if (prevSweepPx < 0) {
      pixelsToFill = 0
    } else if (newSweepPx >= prevSweepPx) {
      pixelsToFill = newSweepPx - prevSweepPx
    } else {
      // Wrapped around
      pixelsToFill = (w - prevSweepPx) + newSweepPx
    }
    pixelsToFill = Math.min(pixelsToFill, w)

    if (pixelsToFill > 0) {
      const samplesPerPixel = displaySamples / w

      for (let i = 0; i < pixelsToFill; i++) {
        const px = (prevSweepPx + 1 + i) % w
        const sampleOffset = ((prevSweepPx + 1 + i) - newSweepPx) * samplesPerPixel
        const sampleCenter = Math.round(currentPlayhead + sampleOffset)
        const radius = Math.max(1, Math.min(4, Math.round(samplesPerPixel * 0.5)))
        let sum = 0, count = 0
        for (let s = sampleCenter - radius; s <= sampleCenter + radius; s++) {
          sum += sampleAt(s)
          count++
        }
        screenValues[px] = count > 0 ? sum / count : 0
        screenWritten[px] = 1
      }

      // Apply smoothing
      const level = smoothingLevelRef
        ? (isRef(smoothingLevelRef) ? smoothingLevelRef.value : smoothingLevelRef)
        : 'off'
      if (level !== 'off') {
        const kernel = GAUSSIAN_KERNELS[level]
        if (kernel) {
          const halfK = Math.floor(kernel.length / 2)
          for (let i = 0; i < pixelsToFill; i++) {
            const px = (prevSweepPx + 1 + i) % w
            let s = 0, ws = 0
            for (let k = 0; k < kernel.length; k++) {
              const idx = (px + k - halfK + w) % w
              if (screenWritten[idx]) { s += screenValues[idx] * kernel[k]; ws += kernel[k] }
            }
            if (ws > 0) screenValues[px] = s / ws
          }
        }
      }
    }

    prevSweepPx = newSweepPx
    sweepPx = newSweepPx
  }

  function updateYRange(w: number) {
    let mn = Infinity, mx = -Infinity
    for (let i = 0; i < w; i++) {
      if (!screenWritten[i]) continue
      const v = screenValues[i]
      if (v < mn) mn = v
      if (v > mx) mx = v
    }
    if (!Number.isFinite(mn) || !Number.isFinite(mx)) return

    const span = mx - mn
    const margin = Math.max(span * 0.15, 0.01)
    const tMin = mn - margin, tMax = mx + margin

    if (!yRangeInitialized) {
      yMin = tMin; yMax = tMax; yRangeInitialized = true
      return
    }
    yMin = tMin < yMin ? tMin : yMin * 0.995 + tMin * 0.005
    yMax = tMax > yMax ? tMax : yMax * 0.995 + tMax * 0.005
  }

  function draw() {
    const canvas = canvasRef.value
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const dpr = typeof window !== 'undefined' ? (window.devicePixelRatio || 1) : 1
    const rect = canvas.getBoundingClientRect()
    const w = Math.floor(rect.width)
    const h = rect.height
    if (!w || !h) return

    if (canvas.width !== w * dpr || canvas.height !== h * dpr) {
      canvas.width = w * dpr
      canvas.height = h * dpr
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
    }

    // Background
    ctx.fillStyle = backgroundColor
    ctx.fillRect(0, 0, w, h)

    // Grid: vertical second markers
    ctx.strokeStyle = gridColor
    ctx.lineWidth = 0.5
    for (let s = 1; s < displaySeconds; s++) {
      const x = (s / displaySeconds) * w
      ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, h); ctx.stroke()
    }

    if (hasTimeline && storedSamples > 0) {
      const playhead = Math.floor(estimatePlaybackSample(getNowMs(), true))
      updateScreenBuffer(playhead, w)
      updateYRange(w)

      const yRange = yMax - yMin
      if (yRange < 1e-8) { /* skip drawing */ }
      else {
        const toY = (v: number) => h - ((v - yMin) / yRange) * h

        // Draw new waveform (sweep head backwards to 0, then wrap)
        // We draw two segments: [0..sweepPx) = new, [sweepPx+2..w) = old
        ctx.strokeStyle = lineColor
        ctx.lineWidth = 1.2
        ctx.lineJoin = 'round'
        ctx.lineCap = 'round'

        // Segment 1: 0 → sweepPx (new data, left of sweep head)
        ctx.beginPath()
        let seg1Started = false
        for (let px = 0; px < sweepPx && px < w; px++) {
          if (!screenWritten[px]) { seg1Started = false; continue }
          const yVal = toY(screenValues[px])
          if (!seg1Started) { ctx.moveTo(px, yVal); seg1Started = true }
          else { ctx.lineTo(px, yVal) }
        }
        ctx.stroke()

        // Segment 2: sweepPx+2 → w (old data, right of sweep head)
        ctx.beginPath()
        let seg2Started = false
        for (let px = sweepPx + 2; px < w; px++) {
          if (!screenWritten[px]) { seg2Started = false; continue }
          const yVal = toY(screenValues[px])
          if (!seg2Started) { ctx.moveTo(px, yVal); seg2Started = true }
          else { ctx.lineTo(px, yVal) }
        }
        ctx.stroke()

        // Sweep head: subtle indicator
        ctx.strokeStyle = lineColor
        ctx.globalAlpha = 0.2
        ctx.lineWidth = 1
        ctx.beginPath()
        ctx.moveTo(sweepPx, 0)
        ctx.lineTo(sweepPx, h)
        ctx.stroke()
        ctx.globalAlpha = 1.0
      }
    }

    if (label) {
      ctx.fillStyle = 'rgba(156,163,175,0.7)'
      ctx.font = '11px Inter, sans-serif'
      ctx.fillText(label, 8, 16)
    }

    if (drawOverlay) drawOverlay(ctx, w, h)
  }

  function loop() {
    if (!running) return
    draw()
    animId = requestAnimationFrame(loop)
  }

  function start() { if (running) return; running = true; loop() }
  function stop() { running = false; if (animId) cancelAnimationFrame(animId); animId = 0 }

  function reset() {
    buffer.fill(0); writePos = 0; storedSamples = 0; latestEndSample = 0
    playbackOriginMs = 0; playbackOriginSample = 0; hasTimeline = false
    yMin = 0; yMax = 0; yRangeInitialized = false
    virtualPlayhead = 0; lastFrameTime = 0; virtualPlayheadActive = false
    screenValues.fill(0); screenWritten.fill(0); sweepPx = 0; screenWidth = 0
    prevSweepPx = -1; sweepOriginPlayhead = 0; sweepInited = false
  }

  onUnmounted(stop)
  return { appendSamples, start, stop, reset }
}

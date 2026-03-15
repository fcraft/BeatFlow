/**
 * 环形缓冲区 + requestAnimationFrame 实时滚动波形绘制 composable。
 *
 * 支持两种输入：
 * 1. 旧模式：直接 append number[]
 * 2. 新模式：append 带 startSample / receivedAtMs 的 chunk，按统一时间轴滚动
 *
 * Feature 1: 贝塞尔曲线渲染 + 渐进 drift 校正
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
  /** 在波形绘制完成后调用，传入 ctx、宽高，用于叠加自定义覆盖层 */
  drawOverlay?: (ctx: CanvasRenderingContext2D, w: number, h: number) => void
  /** 信号平滑级别（Feature 2）：off=原始 / low=轻度 / high=强平滑 */
  smoothingLevel?: Ref<SmoothingLevel> | ComputedRef<SmoothingLevel>
}

function getNowMs() {
  return typeof performance !== 'undefined' && typeof performance.now === 'function'
    ? performance.now()
    : Date.now()
}

// ── 高斯平滑核 (Feature 2) ────────────────────────────────────────
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
  // 使用临时缓冲避免原地修改影响后续像素
  const tmp = new Float32Array(len)

  for (let i = 0; i < len; i++) {
    let sum = 0
    let wSum = 0
    for (let k = 0; k < kernel.length; k++) {
      const idx = i + k - halfK
      if (idx >= 0 && idx < len) {
        sum += points[idx] * kernel[k]
        wSum += kernel[k]
      }
    }
    tmp[i] = wSum > 0 ? sum / wSum : points[i]
  }

  points.set(tmp)
}

export function useScrollingCanvas(options: ScrollingCanvasOptions) {
  const {
    canvasRef,
    sampleRate,
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

  const buffer = new Float32Array(bufferSize)
  let writePos = 0
  let storedSamples = 0
  let latestEndSample = 0
  let playbackOriginMs = 0
  let playbackOriginSample = 0
  let hasTimeline = false
  let animId = 0
  let running = false
  let yMin = -0.5
  let yMax = 0.5

  // ── Step 1A: Frame-locked virtual playhead state ──────────────
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
    for (let i = 0; i < gapSamples; i++) {
      writeValue(padValue)
    }
    latestEndSample += gapSamples
  }

  function appendSamples(input: number[] | SignalChunk) {
    const chunk = Array.isArray(input)
      ? {
          samples: input,
          startSample: latestEndSample,
          receivedAtMs: getNowMs(),
          seq: -1,
          chunkDurationMs: 0,
          serverElapsedSec: null,
        }
      : input

    if (!chunk.samples.length) return

    let startSample = Number.isFinite(chunk.startSample) ? chunk.startSample : latestEndSample
    let samples = chunk.samples

    if (!hasTimeline) {
      latestEndSample = startSample
      hasTimeline = true
    }

    if (startSample < latestEndSample) {
      const overlap = latestEndSample - startSample
      if (overlap >= samples.length) {
        return
      }
      samples = samples.slice(overlap)
      startSample = latestEndSample
    } else if (startSample > latestEndSample) {
      fillGap(startSample - latestEndSample)
    }

    for (let i = 0; i < samples.length; i++) {
      writeValue(samples[i])
    }
    latestEndSample = startSample + samples.length

    // ── Feature 1c: 渐进 drift 校正 ────────────────────────────
    // desiredPlayhead = 缓冲区最新数据 - 播放延迟
    // currentEstimated = 根据 wall-clock 推算的当前播放位置
    // drift = 两者之差
    const desiredPlayhead = Math.max(earliestStoredSample(), latestEndSample - playbackDelaySamples)
    if (playbackOriginMs === 0) {
      playbackOriginSample = desiredPlayhead
      playbackOriginMs = chunk.receivedAtMs
      // Initialize frame-locked virtual playhead
      virtualPlayhead = desiredPlayhead
      lastFrameTime = chunk.receivedAtMs
      virtualPlayheadActive = true
    } else {
      const currentEstimated = estimatePlaybackSample(chunk.receivedAtMs)
      const drift = desiredPlayhead - currentEstimated
      if (Math.abs(drift) > sampleRate * 2.0) {
        // 大间隙 / 重连 / Tab 长时间后台 → 硬重置
        playbackOriginSample = desiredPlayhead
        playbackOriginMs = chunk.receivedAtMs
      } else if (Math.abs(drift) > sampleRate * 0.5) {
        // Tab 短暂后台恢复 → 加速校正（15% 权重），比硬重置更平滑
        const correctedSample = currentEstimated + drift * 0.15
        playbackOriginSample = correctedSample
        playbackOriginMs = chunk.receivedAtMs
      } else if (Math.abs(drift) > sampleRate * 0.02) {
        // 小 drift → 渐进修正：同时更新 origin time + sample，保持估算连续
        // 将 20% 的 drift 修正到 origin 上，时间锚点也同步移到当前
        const correctedSample = currentEstimated + drift * 0.2
        playbackOriginSample = correctedSample
        playbackOriginMs = chunk.receivedAtMs
      }
    }
  }

  function estimatePlaybackSample(nowMs = getNowMs(), frameLocked = false) {
    if (!hasTimeline || playbackOriginMs === 0) {
      return latestEndSample
    }

    if (frameLocked && virtualPlayheadActive) {
      // Frame-locked path: advance virtualPlayhead by dt since last frame,
      // then apply 2% soft correction toward the wall-clock estimate
      const dt = lastFrameTime > 0 ? Math.max(0, Math.min(50, nowMs - lastFrameTime)) : 16.67
      const stepSamples = (dt / 1000) * sampleRate
      virtualPlayhead += stepSamples

      // Wall-clock reference for soft correction
      const wallClockEstimate = playbackOriginSample + ((nowMs - playbackOriginMs) / 1000) * sampleRate
      const drift = wallClockEstimate - virtualPlayhead
      virtualPlayhead += drift * 0.02

      lastFrameTime = nowMs

      return Math.max(earliestStoredSample(), Math.min(latestEndSample - 1, virtualPlayhead))
    }

    // Wall-clock fallback (used by appendSamples drift correction)
    const elapsedSamples = ((nowMs - playbackOriginMs) / 1000) * sampleRate
    const unclamped = playbackOriginSample + elapsedSamples
    return Math.max(earliestStoredSample(), Math.min(latestEndSample - 1, unclamped))
  }

  // ── buildPoints: 原始逐像素平均采样（稳定无过冲） ─────────────
  // 视觉平滑由 draw() 中的 Bézier 曲线渲染负责，buildPoints 只负责
  // 从环形缓冲区精确提取每像素值，不做任何插值（避免 overshoot 抖动）。
  function buildPoints(width: number) {
    const effectiveWidth = Math.max(2, Math.floor(width))
    const endSampleF = estimatePlaybackSample(getNowMs(), true)
    // 将浮点 playhead 对齐到整数样本边界 — 每帧使用固定的整数边界
    // 避免亚样本抖动导致 radius 平均窗口在两帧间跨越不同样本集合
    const endSample = Math.floor(endSampleF)
    const startSample = Math.max(earliestStoredSample(), endSample - displaySamples + 1)
    const visibleSamples = Math.max(2, endSample - startSample + 1)
    const points = new Float32Array(effectiveWidth)
    const samplesPerPixel = visibleSamples / effectiveWidth
    const radius = Math.max(1, Math.min(8, Math.round(samplesPerPixel * 0.5)))

    let mn = Infinity
    let mx = -Infinity

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
      const value = count > 0 ? sum / count : 0
      points[px] = value
      if (value < mn) mn = value
      if (value > mx) mx = value
    }

    // ── Feature 2: 应用高斯平滑（如果启用）──────────────────────
    const level = smoothingLevelRef
      ? (isRef(smoothingLevelRef) ? smoothingLevelRef.value : smoothingLevelRef)
      : 'off'
    if (level !== 'off') {
      applyGaussianSmoothing(points, level)
      // 重新计算 min/max
      mn = Infinity
      mx = -Infinity
      for (let i = 0; i < points.length; i++) {
        if (points[i] < mn) mn = points[i]
        if (points[i] > mx) mx = points[i]
      }
    }

    return { points, min: mn, max: mx }
  }

  function updateYRange(minValue: number, maxValue: number) {
    if (!Number.isFinite(minValue) || !Number.isFinite(maxValue)) return
    const margin = Math.max((maxValue - minValue) * 0.18, 0.05)
    const targetMin = minValue - margin
    const targetMax = maxValue + margin

    // Asymmetric smoothing: expand fast (0.7/0.3), contract slow (0.98/0.02)
    // This prevents vertical jitter when peaks enter/leave the window
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

  function draw() {
    const canvas = canvasRef.value
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const dpr = typeof window !== 'undefined' ? (window.devicePixelRatio || 1) : 1
    const rect = canvas.getBoundingClientRect()
    const w = rect.width
    const h = rect.height
    if (!w || !h) return

    if (canvas.width !== w * dpr || canvas.height !== h * dpr) {
      canvas.width = w * dpr
      canvas.height = h * dpr
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
    }

    ctx.fillStyle = backgroundColor
    ctx.fillRect(0, 0, w, h)

    ctx.strokeStyle = gridColor
    ctx.lineWidth = 0.5
    for (let i = 1; i < 5; i++) {
      const y = (i / 5) * h
      ctx.beginPath()
      ctx.moveTo(0, y)
      ctx.lineTo(w, y)
      ctx.stroke()
    }
    for (let s = 1; s < displaySeconds; s++) {
      const x = (s / displaySeconds) * w
      ctx.beginPath()
      ctx.moveTo(x, 0)
      ctx.lineTo(x, h)
      ctx.stroke()
    }

    const zeroY = h - ((0 - yMin) / (yMax - yMin)) * h
    ctx.strokeStyle = 'rgba(107,114,128,0.4)'
    ctx.lineWidth = 0.5
    ctx.setLineDash([4, 4])
    ctx.beginPath()
    ctx.moveTo(0, zeroY)
    ctx.lineTo(w, zeroY)
    ctx.stroke()
    ctx.setLineDash([])

    if (storedSamples >= 2 && latestEndSample > earliestStoredSample()) {
      const { points, min, max } = buildPoints(w)
      updateYRange(min, max)

      const yRange = yMax - yMin

      ctx.strokeStyle = lineColor
      ctx.lineWidth = 1.2
      ctx.lineJoin = 'round'
      ctx.lineCap = 'round'
      ctx.beginPath()

      // ── Feature 1b: 中点二次贝塞尔渲染 + QRS 尖峰保护 ────────
      const len = points.length
      const toX = (i: number) => (i / (len - 1)) * w
      const toY = (v: number) => h - ((v - yMin) / yRange) * h

      // QRS 尖峰保护：相邻值差超过 yRange 的 25% 时回退 lineTo
      const spikeThreshold = yRange * 0.25

      ctx.moveTo(toX(0), toY(points[0]))

      for (let i = 1; i < len - 1; i++) {
        const prevVal = points[i - 1]
        const currVal = points[i]
        const nextVal = points[i + 1]

        // 在值域空间检测尖峰（不是像素空间）
        const dyPrev = Math.abs(currVal - prevVal)
        const dyNext = Math.abs(nextVal - currVal)

        if (dyPrev > spikeThreshold || dyNext > spikeThreshold) {
          // 尖峰区域用直线保留锐利边缘
          ctx.lineTo(toX(i), toY(currVal))
        } else {
          // 平滑区域用二次贝塞尔
          const midX = (toX(i) + toX(i + 1)) / 2
          const midY = (toY(currVal) + toY(nextVal)) / 2
          ctx.quadraticCurveTo(toX(i), toY(currVal), midX, midY)
        }
      }
      // 最后一个点
      if (len >= 2) {
        ctx.lineTo(toX(len - 1), toY(points[len - 1]))
      }

      ctx.stroke()
    }

    if (label) {
      ctx.fillStyle = 'rgba(156,163,175,0.7)'
      ctx.font = '11px Inter, sans-serif'
      ctx.fillText(label, 8, 16)
    }

    // 自定义覆盖层绘制
    if (drawOverlay) {
      drawOverlay(ctx, w, h)
    }
  }

  function loop() {
    if (!running) return
    draw()
    animId = requestAnimationFrame(loop)
  }

  function start() {
    if (running) return
    running = true
    loop()
  }

  function stop() {
    running = false
    if (animId) cancelAnimationFrame(animId)
    animId = 0
  }

  function reset() {
    buffer.fill(0)
    writePos = 0
    storedSamples = 0
    latestEndSample = 0
    playbackOriginMs = 0
    playbackOriginSample = 0
    hasTimeline = false
    yMin = -0.5
    yMax = 0.5
    virtualPlayhead = 0
    lastFrameTime = 0
    virtualPlayheadActive = false
  }

  onUnmounted(stop)

  return { appendSamples, start, stop, reset }
}

/**
 * 虚拟人体录制 composable
 *
 * 功能：
 * 1. 接收 ECG (500Hz) 和 PCG (4000Hz) 原始样本流
 * 2. 支持听诊模式滤波：应用区域特定的 BiquadFilter 参数进行纯数学运算
 * 3. 听诊头膜片效果：区域切换时执行 fade-out(200ms) → silence(100ms) → fade-in(200ms)
 * 4. 双路 WAV 编码生成（ECG + PCG 各一个 16-bit PCM WAV 文件）
 * 5. 状态管理：recording, duration, pause/resume 等
 *
 * 关键实现细节：
 * - ECG 缓冲：500Hz × 16s ≈ 8000 样本、16-bit PCM → ≈16KB 内存
 * - PCG 缓冲：4000Hz × 16s ≈ 64000 样本、16-bit PCM → ≈128KB 内存
 * - Biquad 滤波：使用直接 IIR 形式（DF-2 结构），无 AudioContext 依赖
 * - Membrane 效果：样本级别的线性淡入淡出应用
 */

import { ref, computed, readonly } from 'vue'
import type { AuscultationAreaConfig } from './useAuscultation'

// ────────────────────────────────────────────────────────────────────
// 常量定义
// ────────────────────────────────────────────────────────────────────

const ECG_SAMPLE_RATE = 500  // ECG 采样率
const PCG_SAMPLE_RATE = 4000 // PCG 采样率

// 膜片效果参数（单位：ms）
const MEMBRANE_FADE_OUT_DURATION = 200  // 淡出时长
const MEMBRANE_SILENCE_DURATION = 100   // 静音时长
const MEMBRANE_FADE_IN_DURATION = 200   // 淡入时长
const MEMBRANE_TOTAL_DURATION = MEMBRANE_FADE_OUT_DURATION + MEMBRANE_SILENCE_DURATION + MEMBRANE_FADE_IN_DURATION

// ────────────────────────────────────────────────────────────────────
// Biquad 滤波器实现（纯数学 IIR，DF-2 结构）
// ────────────────────────────────────────────────────────────────────

export interface BiquadCoefficients {
  b0: number
  b1: number
  b2: number
  a1: number
  a2: number
}

/**
 * Biquad 滤波器状态容器（用于 DF-2 实现）
 */
class BiquadFilter {
  private b0: number = 1
  private b1: number = 0
  private b2: number = 0
  private a1: number = 0
  private a2: number = 0

  // DF-2 直接形式状态变量
  private w1: number = 0
  private w2: number = 0

  constructor(coeffs?: BiquadCoefficients) {
    if (coeffs) {
      this.setCoefficients(coeffs)
    }
  }

  setCoefficients(c: BiquadCoefficients) {
    this.b0 = c.b0
    this.b1 = c.b1
    this.b2 = c.b2
    this.a1 = c.a1
    this.a2 = c.a2
  }

  /**
   * 处理单个样本（DF-2 直接形式）
   * y[n] = b0·w[n] + b1·w[n-1] + b2·w[n-2]
   * w[n] = x[n] - a1·w[n-1] - a2·w[n-2]
   */
  process(sample: number): number {
    const w = sample - this.a1 * this.w1 - this.a2 * this.w2
    const y = this.b0 * w + this.b1 * this.w1 + this.b2 * this.w2
    this.w2 = this.w1
    this.w1 = w
    return y
  }

  /**
   * 批量处理样本数组
   */
  processArray(samples: Float32Array | number[]): Float32Array {
    const output = new Float32Array(samples.length)
    for (let i = 0; i < samples.length; i++) {
      output[i] = this.process(samples[i])
    }
    return output
  }

  reset() {
    this.w1 = 0
    this.w2 = 0
  }
}

// ────────────────────────────────────────────────────────────────────
// Biquad 系数计算函数
// ────────────────────────────────────────────────────────────────────

/**
 * 计算高通滤波器系数 (Highpass)
 */
function calcHighpassCoefficients(fc: number, sampleRate: number, Q: number): BiquadCoefficients {
  const w0 = (2 * Math.PI * fc) / sampleRate
  const alpha = Math.sin(w0) / (2 * Q)
  const cosW0 = Math.cos(w0)

  return {
    b0: (1 + cosW0) / 2,
    b1: -(1 + cosW0),
    b2: (1 + cosW0) / 2,
    a1: -2 * cosW0,
    a2: 1 - 2 * alpha,
  }
}

/**
 * 计算低通滤波器系数 (Lowpass)
 */
function calcLowpassCoefficients(fc: number, sampleRate: number, Q: number): BiquadCoefficients {
  const w0 = (2 * Math.PI * fc) / sampleRate
  const alpha = Math.sin(w0) / (2 * Q)
  const cosW0 = Math.cos(w0)

  return {
    b0: (1 - cosW0) / 2,
    b1: 1 - cosW0,
    b2: (1 - cosW0) / 2,
    a1: -2 * cosW0,
    a2: 1 - 2 * alpha,
  }
}

/**
 * 计算 Peaking EQ 系数（共鸣增强）
 */
function calcPeakingCoefficients(
  fc: number,
  sampleRate: number,
  Q: number,
  gainDb: number,
): BiquadCoefficients {
  const w0 = (2 * Math.PI * fc) / sampleRate
  const alpha = Math.sin(w0) / (2 * Q)
  const cosW0 = Math.cos(w0)
  const A = Math.pow(10, gainDb / 40)

  return {
    b0: 1 + alpha * A,
    b1: -2 * cosW0,
    b2: 1 - alpha * A,
    a1: -2 * cosW0,
    a2: 1 - alpha / A,
  }
}

// ────────────────────────────────────────────────────────────────────
// 膜片效果处理
// ────────────────────────────────────────────────────────────────────

/**
 * 应用膜片淡入淡出效果
 * - fade-out (0 → 1)
 * - silence (all 0)
 * - fade-in (0 → 1)
 */
function applyMembraneEffect(pcgSamples: Float32Array, sampleRate: number): Float32Array {
  const fadeOutSamples = Math.round((sampleRate * MEMBRANE_FADE_OUT_DURATION) / 1000)
  const silenceSamples = Math.round((sampleRate * MEMBRANE_SILENCE_DURATION) / 1000)
  const fadeInSamples = Math.round((sampleRate * MEMBRANE_FADE_IN_DURATION) / 1000)
  const totalSamples = fadeOutSamples + silenceSamples + fadeInSamples

  const output = new Float32Array(pcgSamples.length + totalSamples)

  // Fade-out
  for (let i = 0; i < fadeOutSamples; i++) {
    const factor = 1 - i / fadeOutSamples
    output[i] = pcgSamples[i] * factor
  }

  // Silence
  for (let i = 0; i < silenceSamples; i++) {
    output[fadeOutSamples + i] = 0
  }

  // Fade-in (对剩余样本)
  const startIdx = fadeOutSamples + silenceSamples
  for (let i = 0; i < Math.min(fadeInSamples, pcgSamples.length); i++) {
    const factor = i / fadeInSamples
    output[startIdx + i] = pcgSamples[i] * factor
  }

  // 复制剩余的 PCG 样本
  for (let i = fadeInSamples; i < pcgSamples.length; i++) {
    output[startIdx + i] = pcgSamples[i]
  }

  return output
}

// ────────────────────────────────────────────────────────────────────
// WAV 编码
// ────────────────────────────────────────────────────────────────────

/**
 * 将 Float32Array 样本转换为 16-bit PCM Int16Array
 */
function float32ToInt16(float32: Float32Array): Int16Array {
  const int16 = new Int16Array(float32.length)
  for (let i = 0; i < float32.length; i++) {
    // 限幅到 [-1, 1]
    const s = Math.max(-1, Math.min(1, float32[i]))
    // 转换为 16-bit 有符号整数
    int16[i] = s < 0 ? s * 0x8000 : s * 0x7fff
  }
  return int16
}

/**
 * 编码 WAV 文件格式（16-bit PCM, 单声道）
 */
function encodeWAV(samples: Float32Array, sampleRate: number): Blob {
  const int16 = float32ToInt16(samples)
  const dataLength = int16.length * 2
  const frameLength = dataLength + 36
  const arrayBuffer = new ArrayBuffer(44 + dataLength)
  const view = new DataView(arrayBuffer)

  // RIFF header
  const writeString = (offset: number, str: string) => {
    for (let i = 0; i < str.length; i++) {
      view.setUint8(offset + i, str.charCodeAt(i))
    }
  }

  writeString(0, 'RIFF')
  view.setUint32(4, frameLength, true)
  writeString(8, 'WAVE')

  // fmt sub-chunk
  writeString(12, 'fmt ')
  view.setUint32(16, 16, true) // sub-chunk1 size
  view.setUint16(20, 1, true) // PCM format
  view.setUint16(22, 1, true) // mono
  view.setUint32(24, sampleRate, true)
  view.setUint32(28, sampleRate * 2, true) // byte rate
  view.setUint16(32, 2, true) // block align
  view.setUint16(34, 16, true) // bits per sample

  // data sub-chunk
  writeString(36, 'data')
  view.setUint32(40, dataLength, true)

  // 写入 PCM 数据
  let offset = 44
  for (let i = 0; i < int16.length; i++) {
    view.setInt16(offset, int16[i], true)
    offset += 2
  }

  return new Blob([arrayBuffer], { type: 'audio/wav' })
}

// ────────────────────────────────────────────────────────────────────
// 主 Composable：useVirtualHumanRecorder
// ────────────────────────────────────────────────────────────────────

export interface VirtualHumanRecorderState {
  isRecording: boolean
  isPaused: boolean
  duration: number // 秒
}

export function useVirtualHumanRecorder() {
  // ── 录制状态 ──
  const isRecording = ref(false)
  const isPaused = ref(false)
  const duration = ref(0)
  let recordingStartTime = 0
  let totalPausedDuration = 0   // 累计暂停时长（ms）
  let pauseStartTime = 0        // 当前暂停开始时刻（ms），0 表示未暂停

  // ── 样本缓冲 ──
  const ecgSamples: number[] = []
  const pcgSamples: number[] = []

  // ── 听诊滤波链 ──
  const hpFilter = new BiquadFilter()
  const lpFilter = new BiquadFilter()
  const peakFilter = new BiquadFilter()

  // ── 膜片效果状态 ──
  let membraneEffectActive = false
  let membraneEffectStartTime = 0
  let lastAuscultationArea: string | null = null

  // ── 更新计时器 ──
  let durationUpdateInterval: ReturnType<typeof setInterval> | null = null

  /**
   * 初始化听诊滤波链
   */
  function initializeAuscultationFilters(config: AuscultationAreaConfig) {
    const hpCoeffs = calcHighpassCoefficients(config.hpFreq, PCG_SAMPLE_RATE, config.hpQ)
    const lpCoeffs = calcLowpassCoefficients(config.lpFreq, PCG_SAMPLE_RATE, config.lpQ)
    const peakCoeffs = calcPeakingCoefficients(config.resonanceFreq, PCG_SAMPLE_RATE, config.resonanceQ, config.resonanceGain)

    hpFilter.setCoefficients(hpCoeffs)
    lpFilter.setCoefficients(lpCoeffs)
    peakFilter.setCoefficients(peakCoeffs)
  }

  /**
   * 应用听诊滤波到 PCG 样本
   */
  function applyAuscultationFiltering(samples: number[], config: AuscultationAreaConfig): number[] {
    const float32 = new Float32Array(samples)
    let filtered = hpFilter.processArray(float32)
    filtered = lpFilter.processArray(filtered)
    filtered = peakFilter.processArray(filtered)

    // 应用增益倍数
    for (let i = 0; i < filtered.length; i++) {
      filtered[i] *= config.gainMultiplier
    }

    return Array.from(filtered)
  }

  /**
   * 通知听诊区域切换 → 触发膜片效果
   */
  function onAuscultationAreaChanged(newArea: string, auscultationConfig: AuscultationAreaConfig) {
    if (lastAuscultationArea !== newArea && isRecording.value && !isPaused.value) {
      lastAuscultationArea = newArea
      membraneEffectActive = true
      membraneEffectStartTime = Date.now()

      // 重新初始化新区域的滤波器
      initializeAuscultationFilters(auscultationConfig)
    }
  }

  /**
   * 开始录制
   */
  function startRecording(initialAuscultationConfig?: AuscultationAreaConfig) {
    if (isRecording.value) return

    isRecording.value = true
    isPaused.value = false
    recordingStartTime = Date.now()
    totalPausedDuration = 0
    pauseStartTime = 0
    duration.value = 0

    ecgSamples.length = 0
    pcgSamples.length = 0
    membraneEffectActive = false
    lastAuscultationArea = null

    // 如果有听诊配置，初始化滤波器
    if (initialAuscultationConfig) {
      initializeAuscultationFilters(initialAuscultationConfig)
    }

    // 每 100ms 更新一次时长显示
    durationUpdateInterval = setInterval(() => {
      if (isPaused.value) return // 暂停期间冻结显示
      const elapsed = (Date.now() - recordingStartTime - totalPausedDuration) / 1000
      duration.value = elapsed
    }, 100)
  }

  /**
   * 暂停录制
   */
  function pauseRecording() {
    if (!isRecording.value || isPaused.value) return
    isPaused.value = true
    pauseStartTime = Date.now()
  }

  /**
   * 恢复录制
   */
  function resumeRecording() {
    if (!isRecording.value || !isPaused.value) return
    isPaused.value = false
    totalPausedDuration += Date.now() - pauseStartTime
    pauseStartTime = 0
  }

  /**
   * 停止录制并导出 WAV 文件
   * @param auscultationEnabled 是否启用听诊模式
   * @param auscultationConfig 当前听诊区域配置
   */
  function stopRecording(
    auscultationEnabled: boolean = false,
    auscultationConfig?: AuscultationAreaConfig,
  ): { ecgBlob: Blob; pcgBlob: Blob } {
    if (!isRecording.value) {
      throw new Error('Recording is not in progress')
    }

    if (durationUpdateInterval) {
      clearInterval(durationUpdateInterval)
      durationUpdateInterval = null
    }

    isRecording.value = false
    isPaused.value = false

    // 转换为 Float32Array
    const ecgFloat = new Float32Array(ecgSamples)
    let pcgFloat = new Float32Array(pcgSamples)

    // 如果启用了听诊模式，应用滤波
    if (auscultationEnabled && auscultationConfig) {
      const filtered = applyAuscultationFiltering(Array.from(pcgFloat), auscultationConfig)
      pcgFloat = new Float32Array(filtered)
    }

    // 编码为 WAV
    const ecgBlob = encodeWAV(ecgFloat, ECG_SAMPLE_RATE)
    const pcgBlob = encodeWAV(pcgFloat, PCG_SAMPLE_RATE)

    return { ecgBlob, pcgBlob }
  }

  /**
   * 接收 ECG 样本（通常由虚拟人体 WebSocket 调用）
   */
  function feedEcgSamples(samples: number[]) {
    if (!isRecording.value || isPaused.value) return
    ecgSamples.push(...samples)
  }

  /**
   * 接收 PCG 样本（通常由虚拟人体 WebSocket 调用）
   * 如果膜片效果活跃，应用淡出→静音→淡入效果
   */
  function feedPcgSamples(samples: number[], shouldApplyMembraneEffect: boolean = false) {
    if (!isRecording.value || isPaused.value) return

    if (shouldApplyMembraneEffect && membraneEffectActive) {
      const elapsed = Date.now() - membraneEffectStartTime
      if (elapsed < MEMBRANE_TOTAL_DURATION) {
        // 仍在膜片效果窗口内
        const membraneBuffer = applyMembraneEffect(new Float32Array(samples), PCG_SAMPLE_RATE)
        pcgSamples.push(...Array.from(membraneBuffer))
      } else {
        // 膜片效果完成
        membraneEffectActive = false
        pcgSamples.push(...samples)
      }
    } else {
      pcgSamples.push(...samples)
    }
  }

  /**
   * 取消录制，清空缓冲
   */
  function cancelRecording() {
    if (durationUpdateInterval) {
      clearInterval(durationUpdateInterval)
      durationUpdateInterval = null
    }

    isRecording.value = false
    isPaused.value = false
    duration.value = 0
    ecgSamples.length = 0
    pcgSamples.length = 0
    membraneEffectActive = false
    lastAuscultationArea = null
  }

  return {
    // 状态（只读）
    isRecording: readonly(isRecording),
    isPaused: readonly(isPaused),
    duration: readonly(duration),

    // 方法
    startRecording,
    pauseRecording,
    resumeRecording,
    stopRecording,
    feedEcgSamples,
    feedPcgSamples,
    cancelRecording,
    onAuscultationAreaChanged,
  }
}

/**
 * useVirtualHumanRecorder composable 单元测试
 *
 * 覆盖：录制生命周期、WAV 编码、听诊滤波、膜片效果、暂停/恢复
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { useVirtualHumanRecorder } from '../useVirtualHumanRecorder'
import type { AuscultationAreaConfig } from '../useAuscultation'

// 测试用听诊配置（mitral 区域参数）
const MOCK_MITRAL_CONFIG: AuscultationAreaConfig = {
  id: 'mitral',
  label: '二尖瓣区',
  labelEn: 'Mitral (Apex)',
  location: '左侧第5肋间锁骨中线',
  clinicalTip: '',
  svgPosition: { x: 62, y: 68 },
  hpFreq: 20,
  lpFreq: 300,
  hpQ: 0.7,
  lpQ: 0.75,
  resonanceFreq: 55,
  resonanceGain: 4,
  resonanceQ: 0.8,
  gainMultiplier: 1.1,
}

const MOCK_AORTIC_CONFIG: AuscultationAreaConfig = {
  id: 'aortic',
  label: '主动脉瓣区',
  labelEn: 'Aortic',
  location: '右侧第2肋间胸骨旁',
  clinicalTip: '',
  svgPosition: { x: 38, y: 28 },
  hpFreq: 40,
  lpFreq: 400,
  hpQ: 0.8,
  lpQ: 0.9,
  resonanceFreq: 120,
  resonanceGain: 3,
  resonanceQ: 1.2,
  gainMultiplier: 1.0,
}

describe('useVirtualHumanRecorder', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('初始状态正确', () => {
    const rec = useVirtualHumanRecorder()
    expect(rec.isRecording.value).toBe(false)
    expect(rec.isPaused.value).toBe(false)
    expect(rec.duration.value).toBe(0)
  })

  it('开始录制后状态变为 recording', () => {
    const rec = useVirtualHumanRecorder()
    rec.startRecording()
    expect(rec.isRecording.value).toBe(true)
    expect(rec.isPaused.value).toBe(false)
  })

  it('暂停和恢复录制', () => {
    const rec = useVirtualHumanRecorder()
    rec.startRecording()

    rec.pauseRecording()
    expect(rec.isPaused.value).toBe(true)

    rec.resumeRecording()
    expect(rec.isPaused.value).toBe(false)
  })

  it('取消录制后恢复初始状态', () => {
    const rec = useVirtualHumanRecorder()
    rec.startRecording()
    rec.feedEcgSamples([0.1, 0.2, 0.3])
    rec.feedPcgSamples([0.1, 0.2, 0.3])

    rec.cancelRecording()
    expect(rec.isRecording.value).toBe(false)
    expect(rec.duration.value).toBe(0)
  })

  it('暂停时不接收样本', () => {
    const rec = useVirtualHumanRecorder()
    rec.startRecording()
    rec.feedEcgSamples([0.1, 0.2])

    rec.pauseRecording()
    rec.feedEcgSamples([0.3, 0.4]) // 暂停时不应被录入

    rec.resumeRecording()
    rec.feedEcgSamples([0.5, 0.6])

    const { ecgBlob } = rec.stopRecording()
    // 只有 4 个样本 (0.1, 0.2, 0.5, 0.6)
    // WAV header = 44 bytes, 4 samples × 2 bytes = 8 bytes
    expect(ecgBlob.size).toBe(44 + 4 * 2)
  })

  it('生成有效的 WAV 文件（正确的 header）', async () => {
    // 此测试需要真实计时器（FileReader 在 fake timers 下不工作）
    vi.useRealTimers()

    const rec = useVirtualHumanRecorder()
    rec.startRecording()

    // 喂入 500 个 ECG 样本（1 秒 @500Hz）
    const ecgData = Array.from({ length: 500 }, (_, i) => Math.sin(2 * Math.PI * i / 500) * 0.5)
    rec.feedEcgSamples(ecgData)

    // 喂入 4000 个 PCG 样本（1 秒 @4000Hz）
    const pcgData = Array.from({ length: 4000 }, (_, i) => Math.sin(2 * Math.PI * i / 4000) * 0.3)
    rec.feedPcgSamples(pcgData)

    const { ecgBlob, pcgBlob } = rec.stopRecording()

    // 验证 ECG WAV 大小
    // header(44) + 500 samples × 2 bytes = 1044
    expect(ecgBlob.size).toBe(44 + 500 * 2)
    expect(ecgBlob.type).toBe('audio/wav')

    // 验证 PCG WAV 大小
    expect(pcgBlob.size).toBe(44 + 4000 * 2)
    expect(pcgBlob.type).toBe('audio/wav')

    // 验证 WAV header（使用 FileReader 兼容 jsdom）
    const ecgBuffer = await new Promise<ArrayBuffer>((resolve, reject) => {
      const reader = new FileReader()
      reader.onload = () => resolve(reader.result as ArrayBuffer)
      reader.onerror = reject
      reader.readAsArrayBuffer(ecgBlob)
    })
    const view = new DataView(ecgBuffer)

    // RIFF
    expect(String.fromCharCode(view.getUint8(0), view.getUint8(1), view.getUint8(2), view.getUint8(3))).toBe('RIFF')
    // WAVE
    expect(String.fromCharCode(view.getUint8(8), view.getUint8(9), view.getUint8(10), view.getUint8(11))).toBe('WAVE')
    // fmt
    expect(String.fromCharCode(view.getUint8(12), view.getUint8(13), view.getUint8(14), view.getUint8(15))).toBe('fmt ')
    // PCM format (1)
    expect(view.getUint16(20, true)).toBe(1)
    // Mono (1)
    expect(view.getUint16(22, true)).toBe(1)
    // Sample rate (500 for ECG)
    expect(view.getUint32(24, true)).toBe(500)
    // 16 bits
    expect(view.getUint16(34, true)).toBe(16)
    // data
    expect(String.fromCharCode(view.getUint8(36), view.getUint8(37), view.getUint8(38), view.getUint8(39))).toBe('data')

    // 恢复 fake timers 供后续测试使用
    vi.useFakeTimers()
  })

  it('停止未开始的录制时抛出异常', () => {
    const rec = useVirtualHumanRecorder()
    expect(() => rec.stopRecording()).toThrow('Recording is not in progress')
  })

  it('重复开始录制不会出错', () => {
    const rec = useVirtualHumanRecorder()
    rec.startRecording()
    rec.startRecording() // 第二次调用应被忽略
    expect(rec.isRecording.value).toBe(true)
  })

  it('duration 随时间更新', () => {
    const rec = useVirtualHumanRecorder()
    rec.startRecording()

    // 推进 1 秒
    vi.advanceTimersByTime(1000)
    expect(rec.duration.value).toBeGreaterThan(0)

    rec.cancelRecording()
  })

  it('听诊模式下停止录制应用滤波', () => {
    const rec = useVirtualHumanRecorder()
    rec.startRecording(MOCK_MITRAL_CONFIG)

    // 喂入简单 PCG 信号
    const pcgData = Array.from({ length: 100 }, (_, i) => Math.sin(2 * Math.PI * 50 * i / 4000))
    rec.feedPcgSamples(pcgData)

    // 启用听诊模式时停止 → 应用滤波
    const { pcgBlob } = rec.stopRecording(true, MOCK_MITRAL_CONFIG)

    // 滤波后大小应与原始相同（样本数不变）
    expect(pcgBlob.size).toBe(44 + 100 * 2)
  })

  it('不启用听诊模式时 PCG 不应用滤波', () => {
    const rec = useVirtualHumanRecorder()
    rec.startRecording()

    const pcgData = [0.5, -0.5, 0.3, -0.3]
    rec.feedPcgSamples(pcgData)

    const { pcgBlob } = rec.stopRecording(false)
    expect(pcgBlob.size).toBe(44 + 4 * 2)
  })

  it('onAuscultationAreaChanged 触发膜片效果', () => {
    const rec = useVirtualHumanRecorder()
    rec.startRecording(MOCK_MITRAL_CONFIG)

    // 先喂一些 PCG 数据
    rec.feedPcgSamples([0.5, 0.5, 0.5])

    // 切换区域 → 触发膜片效果
    rec.onAuscultationAreaChanged('aortic', MOCK_AORTIC_CONFIG)

    // 膜片效果活跃期间 feed → 数据会包含淡入淡出
    rec.feedPcgSamples([0.5, 0.5, 0.5], true)

    const { pcgBlob } = rec.stopRecording(false)
    // 膜片效果会导致 PCG 样本数多于原始输入（加入了静音段）
    expect(pcgBlob.size).toBeGreaterThan(44 + 6 * 2)
  })

  it('未录制状态下 feed 不记录样本', () => {
    const rec = useVirtualHumanRecorder()

    rec.feedEcgSamples([0.1, 0.2])
    rec.feedPcgSamples([0.3, 0.4])

    // 开始录制后停止 → 应该没有数据
    rec.startRecording()
    const { ecgBlob, pcgBlob } = rec.stopRecording()

    expect(ecgBlob.size).toBe(44) // 空 WAV (只有 header)
    expect(pcgBlob.size).toBe(44)
  })
})

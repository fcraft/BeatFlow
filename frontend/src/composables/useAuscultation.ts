/**
 * 听诊模式 composable
 *
 * 定义 4 个经典心脏听诊区域及其音频滤波参数，
 * 管理听诊模式状态和区域切换。
 *
 * 听诊区域参数来源于临床心脏听诊学：
 * - 各区域对不同心音成分的敏感度不同
 * - 通过 BiquadFilterNode 参数差异模拟真实听诊器体件特性
 */
import { ref, computed } from 'vue'

/** 听诊区域标识 */
export type AuscultationArea = 'aortic' | 'pulmonic' | 'tricuspid' | 'mitral'

/** 单个听诊区域的完整配置 */
export interface AuscultationAreaConfig {
  /** 区域标识 */
  id: AuscultationArea
  /** 中文名称 */
  label: string
  /** 英文名称 */
  labelEn: string
  /** 解剖位置描述 */
  location: string
  /** 临床听诊提示 */
  clinicalTip: string
  /** SVG 坐标 (胸廓图上的相对位置 0-100) */
  svgPosition: { x: number; y: number }
  /** 高通滤波频率 (Hz) */
  hpFreq: number
  /** 低通滤波频率 (Hz) */
  lpFreq: number
  /** 高通 Q 因子 */
  hpQ: number
  /** 低通 Q 因子 */
  lpQ: number
  /** 共鸣增强中心频率 (Hz)，用 peaking filter */
  resonanceFreq: number
  /** 共鸣增强增益 (dB) */
  resonanceGain: number
  /** 共鸣增强 Q 因子 */
  resonanceQ: number
  /** 区域增益系数 (1.0 = 不变) */
  gainMultiplier: number
}

/**
 * 4 个经典心脏听诊区域配置
 *
 * 主动脉瓣区 (Aortic): S2 最响亮，高频杂音敏感
 * 肺动脉瓣区 (Pulmonic): S2 分裂可闻，中频为主
 * 三尖瓣区 (Tricuspid): S1 增强，低频丰富
 * 二尖瓣区/心尖 (Mitral): S1 最清晰，S3/S4/返流杂音可闻
 */
export const AUSCULTATION_AREAS: Record<AuscultationArea, AuscultationAreaConfig> = {
  aortic: {
    id: 'aortic',
    label: '主动脉瓣区',
    labelEn: 'Aortic',
    location: '右侧第2肋间胸骨旁',
    clinicalTip: 'S2最响亮，主动脉瓣狭窄/关闭不全杂音在此最清晰。收缩期喷射性杂音向颈部传导。',
    svgPosition: { x: 38, y: 28 },
    // 偏高频：强调 S2 和高频杂音
    hpFreq: 40,
    lpFreq: 400,
    hpQ: 0.8,
    lpQ: 0.9,
    resonanceFreq: 120,
    resonanceGain: 3,
    resonanceQ: 1.2,
    gainMultiplier: 1.0,
  },
  pulmonic: {
    id: 'pulmonic',
    label: '肺动脉瓣区',
    labelEn: 'Pulmonic',
    location: '左侧第2肋间胸骨旁',
    clinicalTip: 'P2（S2肺动脉成分）在此最清晰，深吸气时可闻及S2分裂。肺动脉高压时P2增强。',
    svgPosition: { x: 62, y: 28 },
    // 中高频：S2 分裂细节
    hpFreq: 35,
    lpFreq: 350,
    hpQ: 0.8,
    lpQ: 0.85,
    resonanceFreq: 100,
    resonanceGain: 2.5,
    resonanceQ: 1.0,
    gainMultiplier: 0.95,
  },
  tricuspid: {
    id: 'tricuspid',
    label: '三尖瓣区',
    labelEn: 'Tricuspid',
    location: '左侧第4肋间胸骨旁',
    clinicalTip: 'S1的三尖瓣成分在此最响。三尖瓣返流杂音随吸气增强（Carvallo征）。',
    svgPosition: { x: 55, y: 52 },
    // 中低频：S1 成分丰富
    hpFreq: 25,
    lpFreq: 280,
    hpQ: 0.7,
    lpQ: 0.8,
    resonanceFreq: 70,
    resonanceGain: 3.5,
    resonanceQ: 0.9,
    gainMultiplier: 1.05,
  },
  mitral: {
    id: 'mitral',
    label: '二尖瓣区',
    labelEn: 'Mitral (Apex)',
    location: '左侧第5肋间锁骨中线',
    clinicalTip: 'S1最清晰，S3/S4奔马律在此最易闻及。二尖瓣返流全收缩期杂音向腋下传导。使用钟型体件（低频模式）可更好听到S3/S4。',
    svgPosition: { x: 62, y: 68 },
    // 宽频低频增强：S1 + S3/S4 + 杂音全覆盖
    hpFreq: 20,
    lpFreq: 300,
    hpQ: 0.7,
    lpQ: 0.75,
    resonanceFreq: 55,
    resonanceGain: 4,
    resonanceQ: 0.8,
    gainMultiplier: 1.1,
  },
}

/** 区域顺序（用于 UI 列表渲染） */
export const AREA_ORDER: AuscultationArea[] = ['aortic', 'pulmonic', 'tricuspid', 'mitral']

/**
 * 听诊模式 composable
 *
 * 管理听诊模式的开关状态和当前选中区域。
 * 滤波器参数通过 computed 自动派生。
 */
export function useAuscultation() {
  const enabled = ref(false)
  const currentArea = ref<AuscultationArea>('mitral')
  const noiseReduction = ref(true)

  /** 当前区域的完整配置 */
  const areaConfig = computed(() => AUSCULTATION_AREAS[currentArea.value])

  /** 区域切换回调（录制功能用来触发膜片效果） */
  let onAreaChangeCallback: ((area: AuscultationArea, config: AuscultationAreaConfig) => void) | null = null

  /** 注册区域切换回调 */
  function onAreaChange(fn: (area: AuscultationArea, config: AuscultationAreaConfig) => void) {
    onAreaChangeCallback = fn
  }

  /** 取消区域切换回调 */
  function offAreaChange() {
    onAreaChangeCallback = null
  }

  /** 切换听诊区域 */
  function selectArea(area: AuscultationArea) {
    const prev = currentArea.value
    currentArea.value = area
    if (prev !== area && onAreaChangeCallback) {
      onAreaChangeCallback(area, AUSCULTATION_AREAS[area])
    }
  }

  /** 开启听诊模式 */
  function enable() {
    enabled.value = true
  }

  /** 关闭听诊模式 */
  function disable() {
    enabled.value = false
  }

  /** 切换听诊模式 */
  function toggle() {
    enabled.value = !enabled.value
  }

  return {
    enabled,
    currentArea,
    noiseReduction,
    areaConfig,
    selectArea,
    enable,
    disable,
    toggle,
    onAreaChange,
    offAreaChange,
  }
}

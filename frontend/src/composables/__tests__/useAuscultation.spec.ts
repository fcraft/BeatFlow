/**
 * Unit tests for useAuscultation composable
 *
 * 覆盖场景：
 *   1. 4 个听诊区域配置完整性
 *   2. 状态管理（enable/disable/toggle/selectArea）
 *   3. computed areaConfig 响应性
 *   4. 滤波参数合理性验证
 */
import { describe, it, expect, vi } from 'vitest'

vi.mock('vue', async (importOriginal) => {
  const actual = await importOriginal<typeof import('vue')>()
  return { ...actual, onUnmounted: vi.fn() }
})

import {
  useAuscultation,
  AUSCULTATION_AREAS,
  AREA_ORDER,
  type AuscultationArea,
} from '@/composables/useAuscultation'

// ════════════════════════════════════════════════════
// 区域配置完整性
// ════════════════════════════════════════════════════
describe('AUSCULTATION_AREAS — configuration', () => {
  it('has exactly 4 areas', () => {
    expect(Object.keys(AUSCULTATION_AREAS)).toHaveLength(4)
  })

  it('AREA_ORDER contains all 4 areas', () => {
    expect(AREA_ORDER).toHaveLength(4)
    expect(AREA_ORDER).toContain('aortic')
    expect(AREA_ORDER).toContain('pulmonic')
    expect(AREA_ORDER).toContain('tricuspid')
    expect(AREA_ORDER).toContain('mitral')
  })

  it.each(AREA_ORDER)('area "%s" has all required fields', (area) => {
    const config = AUSCULTATION_AREAS[area]
    expect(config.id).toBe(area)
    expect(config.label).toBeTruthy()
    expect(config.labelEn).toBeTruthy()
    expect(config.location).toBeTruthy()
    expect(config.clinicalTip).toBeTruthy()
    expect(config.svgPosition).toBeDefined()
    expect(config.svgPosition.x).toBeGreaterThan(0)
    expect(config.svgPosition.y).toBeGreaterThan(0)
  })

  it.each(AREA_ORDER)('area "%s" has valid filter parameters', (area) => {
    const config = AUSCULTATION_AREAS[area]
    // HP < LP (valid bandpass)
    expect(config.hpFreq).toBeLessThan(config.lpFreq)
    // Reasonable frequency ranges for cardiac auscultation
    expect(config.hpFreq).toBeGreaterThanOrEqual(15)
    expect(config.hpFreq).toBeLessThanOrEqual(50)
    expect(config.lpFreq).toBeGreaterThanOrEqual(150)
    expect(config.lpFreq).toBeLessThanOrEqual(500)
    // Q factors positive
    expect(config.hpQ).toBeGreaterThan(0)
    expect(config.lpQ).toBeGreaterThan(0)
    // Resonance within bandpass range
    expect(config.resonanceFreq).toBeGreaterThanOrEqual(config.hpFreq)
    expect(config.resonanceFreq).toBeLessThanOrEqual(config.lpFreq)
    // Resonance gain positive
    expect(config.resonanceGain).toBeGreaterThan(0)
    // Gain multiplier reasonable
    expect(config.gainMultiplier).toBeGreaterThan(0.5)
    expect(config.gainMultiplier).toBeLessThan(2.0)
  })

  it('aortic area emphasizes higher frequencies (S2)', () => {
    const aortic = AUSCULTATION_AREAS.aortic
    const mitral = AUSCULTATION_AREAS.mitral
    expect(aortic.hpFreq).toBeGreaterThan(mitral.hpFreq)
    expect(aortic.lpFreq).toBeGreaterThan(mitral.lpFreq)
  })

  it('mitral area has lowest HP freq (S3/S4 sensitive)', () => {
    const mitral = AUSCULTATION_AREAS.mitral
    const allHpFreqs = AREA_ORDER.map(a => AUSCULTATION_AREAS[a].hpFreq)
    expect(mitral.hpFreq).toBe(Math.min(...allHpFreqs))
  })
})

// ════════════════════════════════════════════════════
// useAuscultation 状态管理
// ════════════════════════════════════════════════════
describe('useAuscultation — state management', () => {
  it('defaults to disabled, mitral area, noise reduction on', () => {
    const { enabled, currentArea, noiseReduction } = useAuscultation()
    expect(enabled.value).toBe(false)
    expect(currentArea.value).toBe('mitral')
    expect(noiseReduction.value).toBe(true)
  })

  it('enable/disable/toggle work correctly', () => {
    const { enabled, enable, disable, toggle } = useAuscultation()
    enable()
    expect(enabled.value).toBe(true)
    disable()
    expect(enabled.value).toBe(false)
    toggle()
    expect(enabled.value).toBe(true)
    toggle()
    expect(enabled.value).toBe(false)
  })

  it('selectArea changes currentArea', () => {
    const { currentArea, selectArea } = useAuscultation()
    selectArea('aortic')
    expect(currentArea.value).toBe('aortic')
    selectArea('pulmonic')
    expect(currentArea.value).toBe('pulmonic')
    selectArea('tricuspid')
    expect(currentArea.value).toBe('tricuspid')
    selectArea('mitral')
    expect(currentArea.value).toBe('mitral')
  })

  it('areaConfig computed reflects current area', () => {
    const { areaConfig, selectArea } = useAuscultation()
    expect(areaConfig.value.id).toBe('mitral')

    selectArea('aortic')
    expect(areaConfig.value.id).toBe('aortic')
    expect(areaConfig.value.label).toBe('主动脉瓣区')

    selectArea('tricuspid')
    expect(areaConfig.value.id).toBe('tricuspid')
  })
})

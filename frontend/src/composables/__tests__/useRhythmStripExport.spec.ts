import { describe, it, expect } from 'vitest'
import { generateFilename, formatVitalsHeader } from '../useRhythmStripExport'

describe('generateFilename', () => {
  it('formats filename with rhythm and lead', () => {
    const name = generateFilename('normal', 'II', 'png')
    expect(name).toMatch(/^ECG_normal_II_\d{8}_\d{6}\.png$/)
  })

  it('handles different rhythm and lead', () => {
    const name = generateFilename('af', 'V1', 'png')
    expect(name).toMatch(/^ECG_af_V1_\d{8}_\d{6}\.png$/)
  })
})

describe('formatVitalsHeader', () => {
  it('includes HR and rhythm label', () => {
    const header = formatVitalsHeader({ heart_rate: 72, rhythm: 'normal' })
    expect(header).toContain('72 bpm')
    expect(header).toContain('窦性')
  })

  it('handles af rhythm', () => {
    const header = formatVitalsHeader({ heart_rate: 100, rhythm: 'af' })
    expect(header).toContain('100 bpm')
    expect(header).toContain('房颤')
  })

  it('handles missing values', () => {
    const header = formatVitalsHeader({})
    expect(header).toContain('0 bpm')
  })

  it('handles pvc rhythm', () => {
    const header = formatVitalsHeader({ heart_rate: 85, rhythm: 'pvc' })
    expect(header).toContain('85 bpm')
    expect(header).toContain('早搏')
  })

  it('handles vt rhythm', () => {
    const header = formatVitalsHeader({ heart_rate: 150, rhythm: 'vt' })
    expect(header).toContain('150 bpm')
    expect(header).toContain('VT')
  })
})

import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import ConditionTab from '../ConditionTab.vue'

// Mock the virtualHuman store with vitals
const mockSendCommand = vi.fn()
vi.mock('@/store/virtualHuman', () => ({
  useVirtualHumanStore: () => ({
    sendCommand: mockSendCommand,
    vitals: {
      rhythm: 'normal',
      murmur_severity: 0,
      damage_level: 0,
      pvc_pattern: 'isolated',
      conduction: {
        av_block_degree: 0,
      },
    },
  }),
}))

describe('ConditionTab', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    mockSendCommand.mockClear()
  })

  it('renders all condition buttons including AV block', () => {
    const wrapper = mount(ConditionTab)
    const buttons = wrapper.findAll('button')
    const labels = buttons.map((b) => b.text())

    // Check AV block buttons exist
    expect(labels).toContain('AVB I°')
    expect(labels).toContain('AVB II°')
    expect(labels).toContain('AVB III°')

    // Check other condition buttons still exist
    expect(labels).toContain('正常')
    expect(labels).toContain('房颤')
    expect(labels).toContain('SVT')
    expect(labels).toContain('VT')
  })

  it('emits correct command when AV block buttons are clicked', async () => {
    const wrapper = mount(ConditionTab)
    const buttons = wrapper.findAll('button')

    // Find and click AVB I° button
    const avb1 = buttons.find((b) => b.text() === 'AVB I°')
    expect(avb1).toBeDefined()
    await avb1!.trigger('click')
    expect(mockSendCommand).toHaveBeenCalledWith('condition_av_block_1', { severity: 0.5 })

    mockSendCommand.mockClear()

    // Find and click AVB II° button
    const avb2 = buttons.find((b) => b.text() === 'AVB II°')
    await avb2!.trigger('click')
    expect(mockSendCommand).toHaveBeenCalledWith('condition_av_block_2', { severity: 0.5 })

    mockSendCommand.mockClear()

    // Find and click AVB III° button
    const avb3 = buttons.find((b) => b.text() === 'AVB III°')
    await avb3!.trigger('click')
    expect(mockSendCommand).toHaveBeenCalledWith('condition_av_block_3', { severity: 0.5 })
  })
})

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import BottomSheet from '../BottomSheet.vue'

vi.mock('@/constants/zIndex', () => ({
  nextZIndex: () => 9001,
}))

describe('BottomSheet', () => {
  const globalConfig = {
    stubs: {
      Teleport: {
        template: '<div><slot /></div>',
      },
    },
  }

  it('renders when modelValue is true', () => {
    const wrapper = mount(BottomSheet, {
      props: { modelValue: true },
      global: globalConfig,
    })
    expect(wrapper.find('[data-testid="bottom-sheet-backdrop"]').exists()).toBe(true)
  })

  it('does not render when modelValue is false', () => {
    const wrapper = mount(BottomSheet, {
      props: { modelValue: false },
      global: globalConfig,
    })
    expect(wrapper.find('[data-testid="bottom-sheet-backdrop"]').exists()).toBe(false)
  })

  it('emits update:modelValue false on backdrop click', async () => {
    const wrapper = mount(BottomSheet, {
      props: { modelValue: true, closable: true },
      global: globalConfig,
    })
    await wrapper.find('[data-testid="bottom-sheet-backdrop"]').trigger('click')
    expect(wrapper.emitted('update:modelValue')).toBeTruthy()
    expect(wrapper.emitted('update:modelValue')![0]).toEqual([false])
  })

  it('renders default slot content', () => {
    const wrapper = mount(BottomSheet, {
      props: { modelValue: true },
      slots: { default: '<p data-testid="slot-content">Hello</p>' },
      global: globalConfig,
    })
    expect(wrapper.find('[data-testid="slot-content"]').text()).toBe('Hello')
  })

  it('renders header slot', () => {
    const wrapper = mount(BottomSheet, {
      props: { modelValue: true },
      slots: { header: '<h2 data-testid="header-slot">My Header</h2>' },
      global: globalConfig,
    })
    expect(wrapper.find('[data-testid="header-slot"]').text()).toBe('My Header')
  })

  it('hides close button when closable=false', () => {
    const wrapper = mount(BottomSheet, {
      props: { modelValue: true, closable: false },
      global: globalConfig,
    })
    expect(wrapper.find('[data-testid="bottom-sheet-close"]').exists()).toBe(false)
  })
})

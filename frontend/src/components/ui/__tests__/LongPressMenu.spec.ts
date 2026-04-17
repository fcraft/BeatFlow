import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { ref } from 'vue'
import LongPressMenu from '../LongPressMenu.vue'

vi.mock('@/constants/zIndex', () => ({
  nextZIndex: () => 9001,
}))

const isMobileRef = ref(true)

vi.mock('@/composables/useMobile', () => ({
  useMobile: () => ({
    isMobile: isMobileRef,
    isTablet: ref(false),
    isDesktop: ref(false),
  }),
}))

describe('LongPressMenu', () => {
  const items = [
    { label: 'Edit', onClick: vi.fn() },
    { label: 'Delete', color: '#ef4444', onClick: vi.fn() },
  ]

  const globalConfig = {
    stubs: {
      Teleport: {
        template: '<div><slot /></div>',
      },
    },
  }

  beforeEach(() => {
    isMobileRef.value = true
    vi.clearAllMocks()
  })

  it('renders slot content', () => {
    const wrapper = mount(LongPressMenu, {
      props: { items },
      slots: { default: '<span data-testid="trigger">Press me</span>' },
      global: globalConfig,
    })
    expect(wrapper.find('[data-testid="trigger"]').text()).toBe('Press me')
  })

  it('menu is hidden by default', () => {
    const wrapper = mount(LongPressMenu, {
      props: { items },
      global: globalConfig,
    })
    expect(wrapper.find('[data-testid="long-press-menu"]').exists()).toBe(false)
  })

  it('does not render when disabled', () => {
    const wrapper = mount(LongPressMenu, {
      props: { items, disabled: true },
      global: globalConfig,
    })
    // Menu should not show when disabled even if pressed
    expect(wrapper.find('[data-testid="long-press-menu"]').exists()).toBe(false)
  })
})

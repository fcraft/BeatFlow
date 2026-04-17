import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { ref } from 'vue'
import SwipeAction from '../SwipeAction.vue'

const isMobileRef = ref(true)

vi.mock('@/composables/useMobile', () => ({
  useMobile: () => ({
    isMobile: isMobileRef,
    isTablet: ref(false),
    isDesktop: ref(false),
  }),
}))

describe('SwipeAction', () => {
  const actions = [
    { label: 'Delete', color: '#ef4444', onClick: vi.fn() },
    { label: 'Archive', color: '#f59e0b', onClick: vi.fn() },
  ]

  beforeEach(() => {
    isMobileRef.value = true
    vi.clearAllMocks()
  })

  it('renders slot content', () => {
    const wrapper = mount(SwipeAction, {
      props: { actions },
      slots: { default: '<span data-testid="content">Item</span>' },
    })
    expect(wrapper.find('[data-testid="content"]').text()).toBe('Item')
  })

  it('renders action buttons when on mobile', () => {
    const wrapper = mount(SwipeAction, {
      props: { actions },
    })
    const swipeActions = wrapper.find('[data-testid="swipe-actions"]')
    expect(swipeActions.exists()).toBe(true)
    expect(swipeActions.text()).toContain('Delete')
    expect(swipeActions.text()).toContain('Archive')
  })

  it('actions hidden by default (translateX 0)', () => {
    const wrapper = mount(SwipeAction, {
      props: { actions },
    })
    const content = wrapper.find('[data-testid="swipe-content"]')
    expect(content.attributes('style')).toContain('translateX(0px)')
  })

  it('does not render swipe-actions on desktop', () => {
    isMobileRef.value = false
    const wrapper = mount(SwipeAction, {
      props: { actions },
    })
    expect(wrapper.find('[data-testid="swipe-actions"]').exists()).toBe(false)
  })

  it('respects disabled prop', () => {
    const wrapper = mount(SwipeAction, {
      props: { actions, disabled: true },
    })
    expect(wrapper.find('[data-testid="swipe-actions"]').exists()).toBe(false)
  })
})

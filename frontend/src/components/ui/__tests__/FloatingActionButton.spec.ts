import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { ref, defineComponent } from 'vue'
import FloatingActionButton from '../FloatingActionButton.vue'

vi.mock('@/constants/zIndex', () => ({
  nextZIndex: () => 9001,
}))

const isDesktopRef = ref(false)

vi.mock('@/composables/useMobile', () => ({
  useMobile: () => ({
    isMobile: ref(true),
    isTablet: ref(false),
    isDesktop: isDesktopRef,
  }),
}))

// Fake icon component
const FakeIcon = defineComponent({
  template: '<svg data-testid="icon" />',
})

describe('FloatingActionButton', () => {
  const globalConfig = {
    stubs: {
      Teleport: {
        template: '<div><slot /></div>',
      },
    },
  }

  beforeEach(() => {
    isDesktopRef.value = false
    vi.clearAllMocks()
  })

  it('renders on mobile', () => {
    const wrapper = mount(FloatingActionButton, {
      props: { icon: FakeIcon, label: 'Add' },
      global: globalConfig,
    })
    expect(wrapper.find('[data-testid="fab"]').exists()).toBe(true)
  })

  it('is hidden on desktop', () => {
    isDesktopRef.value = true
    const wrapper = mount(FloatingActionButton, {
      props: { icon: FakeIcon, label: 'Add' },
      global: globalConfig,
    })
    expect(wrapper.find('[data-testid="fab"]').exists()).toBe(false)
  })

  it('emits click when pressed', async () => {
    const wrapper = mount(FloatingActionButton, {
      props: { icon: FakeIcon, label: 'Add' },
      global: globalConfig,
    })
    await wrapper.find('[data-testid="fab"]').trigger('click')
    expect(wrapper.emitted('click')).toBeTruthy()
  })

  it('has aria-label', () => {
    const wrapper = mount(FloatingActionButton, {
      props: { icon: FakeIcon, label: 'Create new item' },
      global: globalConfig,
    })
    const fab = wrapper.find('[data-testid="fab"]')
    expect(fab.attributes('aria-label')).toBe('Create new item')
  })
})

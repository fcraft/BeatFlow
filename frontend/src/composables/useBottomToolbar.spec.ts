import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ref } from 'vue'

// Mock @vueuse/core before importing composable
vi.mock('@vueuse/core', () => ({
  useScroll: vi.fn(() => ({
    directions: {
      top: ref(false),
      bottom: ref(false),
      left: ref(false),
      right: ref(false),
    },
  })),
  useBreakpoints: vi.fn(() => ({
    smaller: vi.fn(() => ref(true)),
    between: vi.fn(() => ref(false)),
    greaterOrEqual: vi.fn(() => ref(false)),
  })),
}))

describe('useBottomToolbar', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('isVisible is true by default', async () => {
    const { useBottomToolbar } = await import('./useBottomToolbar')
    const { isVisible } = useBottomToolbar()
    expect(isVisible.value).toBe(true)
  })

  it('show() sets isVisible to true', async () => {
    const { useBottomToolbar } = await import('./useBottomToolbar')
    const { isVisible, show, hide } = useBottomToolbar()
    hide()
    expect(isVisible.value).toBe(false)
    show()
    expect(isVisible.value).toBe(true)
  })

  it('hide() sets isVisible to false', async () => {
    const { useBottomToolbar } = await import('./useBottomToolbar')
    const { isVisible, hide } = useBottomToolbar()
    expect(isVisible.value).toBe(true)
    hide()
    expect(isVisible.value).toBe(false)
  })
})

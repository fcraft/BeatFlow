import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'

const mockBreakpoints = {
  smaller: vi.fn(),
  between: vi.fn(),
  greaterOrEqual: vi.fn(),
}
vi.mock('@vueuse/core', () => ({
  useBreakpoints: vi.fn(() => mockBreakpoints),
}))

import { ref } from 'vue'
import { useMobile } from './useMobile'

describe('useMobile', () => {
  it('exports isMobile, isTablet, isDesktop as refs', () => {
    mockBreakpoints.smaller.mockReturnValue(ref(true))
    mockBreakpoints.between.mockReturnValue(ref(false))
    mockBreakpoints.greaterOrEqual.mockReturnValue(ref(false))

    const { isMobile, isTablet, isDesktop } = useMobile()
    expect(isMobile.value).toBe(true)
    expect(isTablet.value).toBe(false)
    expect(isDesktop.value).toBe(false)
  })

  it('detects tablet when between sm and lg', () => {
    mockBreakpoints.smaller.mockReturnValue(ref(false))
    mockBreakpoints.between.mockReturnValue(ref(true))
    mockBreakpoints.greaterOrEqual.mockReturnValue(ref(false))

    const { isMobile, isTablet, isDesktop } = useMobile()
    expect(isMobile.value).toBe(false)
    expect(isTablet.value).toBe(true)
    expect(isDesktop.value).toBe(false)
  })

  it('detects desktop when >= lg', () => {
    mockBreakpoints.smaller.mockReturnValue(ref(false))
    mockBreakpoints.between.mockReturnValue(ref(false))
    mockBreakpoints.greaterOrEqual.mockReturnValue(ref(true))

    const { isMobile, isTablet, isDesktop } = useMobile()
    expect(isMobile.value).toBe(false)
    expect(isTablet.value).toBe(false)
    expect(isDesktop.value).toBe(true)
  })
})

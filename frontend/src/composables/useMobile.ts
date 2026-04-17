import { useBreakpoints } from '@vueuse/core'
import type { Ref } from 'vue'

/**
 * Reactive breakpoint detection aligned with Tailwind defaults.
 *
 * - mobile:  < 640px  (sm)
 * - tablet:  640–1023px (sm – lg)
 * - desktop: >= 1024px (lg)
 */
export function useMobile(): {
  isMobile: Ref<boolean>
  isTablet: Ref<boolean>
  isDesktop: Ref<boolean>
} {
  const bp = useBreakpoints({ sm: 640, lg: 1024 })

  return {
    isMobile: bp.smaller('sm'),
    isTablet: bp.between('sm', 'lg'),
    isDesktop: bp.greaterOrEqual('lg'),
  }
}

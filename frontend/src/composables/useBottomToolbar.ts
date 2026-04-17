import { ref, watch, onUnmounted, getCurrentInstance } from 'vue'
import type { Ref } from 'vue'
import { useScroll } from '@vueuse/core'

/**
 * useBottomToolbar
 *
 * Scroll-aware bottom toolbar visibility.
 * Hides when scrolling down, shows when scrolling up.
 * Uses a 100ms debounce on hide to avoid flickering.
 */
export function useBottomToolbar(target?: Ref<HTMLElement | null>) {
  const isVisible = ref(true)
  let hideTimer: ReturnType<typeof setTimeout> | null = null

  const { directions } = useScroll(target ?? (typeof window !== 'undefined' ? window : null))

  const stopWatch = watch(
    () => ({ up: directions.top, down: directions.bottom }),
    ({ up, down }) => {
      if (down) {
        // Debounce hide: 100ms
        if (!hideTimer) {
          hideTimer = setTimeout(() => {
            isVisible.value = false
            hideTimer = null
          }, 100)
        }
      } else if (up) {
        if (hideTimer) {
          clearTimeout(hideTimer)
          hideTimer = null
        }
        isVisible.value = true
      }
    }
  )

  function show() {
    isVisible.value = true
  }

  function hide() {
    isVisible.value = false
  }

  // Only register lifecycle hook when inside a component
  if (getCurrentInstance()) {
    onUnmounted(() => {
      stopWatch()
      if (hideTimer) clearTimeout(hideTimer)
    })
  }

  return { isVisible, show, hide }
}

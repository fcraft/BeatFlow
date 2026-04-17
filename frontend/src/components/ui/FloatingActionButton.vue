<template>
  <Teleport to="body">
    <Transition name="fab">
      <button
        v-if="!isDesktop"
        data-testid="fab"
        :aria-label="label || 'Floating action button'"
        class="fixed flex items-center justify-center w-14 h-14 rounded-full shadow-lg bg-primary-600 hover:bg-primary-700 active:scale-95 transition-all text-white"
        :style="buttonStyle"
        @click="emit('click')"
      >
        <component :is="icon" :size="24" />
      </button>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { Component } from 'vue'
import { nextZIndex } from '@/constants/zIndex'
import { useMobile } from '@/composables/useMobile'

const props = withDefaults(defineProps<{
  icon: Component
  label?: string
  position?: 'bottom-right' | 'bottom-center'
  offset?: { bottom: number; right: number }
}>(), {
  position: 'bottom-right',
})

const emit = defineEmits<{
  click: []
}>()

const { isDesktop } = useMobile()
const zIndex = nextZIndex()

const buttonStyle = computed(() => {
  const bottom = props.offset?.bottom ?? 24
  const right = props.offset?.right ?? 24

  if (props.position === 'bottom-center') {
    return {
      bottom: `calc(${bottom}px + env(safe-area-inset-bottom, 0px))`,
      left: '50%',
      transform: 'translateX(-50%)',
      zIndex,
    }
  }

  return {
    bottom: `calc(${bottom}px + env(safe-area-inset-bottom, 0px))`,
    right: `${right}px`,
    zIndex,
  }
})
</script>

<style scoped>
.fab-enter-active,
.fab-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}

.fab-enter-from,
.fab-leave-to {
  opacity: 0;
  transform: scale(0.8);
}
</style>

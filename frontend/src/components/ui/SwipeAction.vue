<template>
  <div class="relative overflow-hidden">
    <!-- Content layer -->
    <div
      data-testid="swipe-content"
      class="relative bg-white"
      :style="contentStyle"
      @touchstart.passive="onTouchStart"
      @touchmove.passive="onTouchMove"
      @touchend.passive="onTouchEnd"
    >
      <slot />
    </div>

    <!-- Actions layer (only when enabled) -->
    <div
      v-if="enabled"
      data-testid="swipe-actions"
      class="absolute inset-y-0 right-0 flex items-stretch"
    >
      <button
        v-for="(action, index) in actions"
        :key="index"
        class="flex flex-col items-center justify-center px-4 min-w-[70px] text-sm font-medium"
        :class="action.color"
        @click="onActionClick(action)"
      >
        <component :is="action.icon" v-if="action.icon" :size="20" class="mb-1" />
        <span>{{ action.label }}</span>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, inject, provide } from 'vue'
import type { Component } from 'vue'
import { useMobile } from '@/composables/useMobile'

interface SwipeActionItem {
  label: string
  icon?: Component
  color: string
  onClick: () => void
}

const props = withDefaults(defineProps<{
  actions: SwipeActionItem[]
  threshold?: number
  maxOffset?: number
  disabled?: boolean
}>(), {
  threshold: 80,
  maxOffset: 140,
  disabled: false,
})

const emit = defineEmits<{
  open: []
  close: []
}>()

const { isMobile } = useMobile()

const enabled = computed(() => isMobile.value && !props.disabled)

// Mutual exclusion via provide/inject
const closeAllKey = 'swipe-action-close-all'
const closeOthers = inject<() => void>(closeAllKey, () => {})

function closeThis() {
  offset.value = 0
  emit('close')
}

provide(closeAllKey, closeThis)

// Swipe state
const offset = ref(0)
const dragging = ref(false)
const touchStartX = ref(0)
const touchStartY = ref(0)
const isOpen = ref(false)

const contentStyle = computed(() => ({
  transform: `translateX(${-offset.value}px)`,
  transition: dragging.value ? 'none' : 'transform 0.3s cubic-bezier(0.16, 1, 0.3, 1)',
}))

function onTouchStart(e: TouchEvent) {
  if (!enabled.value) return
  dragging.value = true
  touchStartX.value = e.touches[0].clientX
  touchStartY.value = e.touches[0].clientY
}

function onTouchMove(e: TouchEvent) {
  if (!enabled.value) return
  const dx = touchStartX.value - e.touches[0].clientX
  const dy = Math.abs(e.touches[0].clientY - touchStartY.value)

  // Ignore vertical scrolls
  if (dy > Math.abs(dx)) return

  if (dx > 0) {
    // Swiping left: reveal actions
    offset.value = Math.min(dx, props.maxOffset)
  } else {
    // Swiping right: close
    offset.value = Math.max(0, offset.value + dx)
  }
}

function onTouchEnd() {
  if (!enabled.value) return
  dragging.value = false

  if (offset.value > props.threshold) {
    offset.value = props.maxOffset
    if (!isOpen.value) {
      isOpen.value = true
      closeOthers()
      emit('open')
    }
  } else {
    offset.value = 0
    if (isOpen.value) {
      isOpen.value = false
      emit('close')
    }
  }
}

function onActionClick(action: SwipeActionItem) {
  action.onClick()
  offset.value = 0
  isOpen.value = false
  emit('close')
}
</script>

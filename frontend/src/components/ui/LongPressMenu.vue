<template>
  <div
    ref="wrapperRef"
    class="inline-block"
    :style="wrapperStyle"
    @touchstart.passive="onTouchStart"
    @touchmove.passive="onTouchMove"
    @touchend.passive="onTouchEnd"
    @touchcancel.passive="cancelPress"
    @contextmenu.prevent
  >
    <slot />
  </div>

  <Teleport to="body">
    <div
      v-if="menuVisible"
      data-testid="long-press-menu"
      class="fixed rounded-xl shadow-2xl bg-white border border-gray-100 overflow-hidden py-1 min-w-[160px]"
      :style="menuStyle"
      @click.stop
    >
      <button
        v-for="(item, index) in items"
        :key="index"
        class="flex items-center gap-3 w-full px-4 py-3 text-left text-sm hover:bg-gray-50 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
        :class="[item.color || 'text-gray-700']"
        :disabled="item.disabled"
        @click="onItemClick(item)"
      >
        <component :is="item.icon" v-if="item.icon" :size="18" />
        <span>{{ item.label }}</span>
      </button>
    </div>

    <!-- Click outside overlay -->
    <div
      v-if="menuVisible"
      class="fixed inset-0"
      :style="{ zIndex: menuZIndex - 1 }"
      @click="closeMenu"
      @touchstart.passive="closeMenu"
    />
  </Teleport>
</template>

<script setup lang="ts">
import { ref, computed, onUnmounted } from 'vue'
import type { Component } from 'vue'
import { nextZIndex } from '@/constants/zIndex'
import { useMobile } from '@/composables/useMobile'

interface MenuItem {
  label: string
  icon?: Component
  color?: string
  disabled?: boolean
  onClick: () => void
}

const props = withDefaults(defineProps<{
  items: MenuItem[]
  delay?: number
  disabled?: boolean
}>(), {
  delay: 500,
  disabled: false,
})

const emit = defineEmits<{
  open: []
  close: []
  select: [item: MenuItem]
}>()

const { isMobile } = useMobile()

const wrapperRef = ref<HTMLElement | null>(null)
const menuVisible = ref(false)
const menuZIndex = ref(9000)

// Trigger feedback
const isPressed = ref(false)
const wrapperStyle = computed(() => ({
  transform: isPressed.value ? 'scale(0.98)' : 'scale(1)',
  transition: 'transform 0.1s ease',
}))

// Menu position
const menuX = ref(0)
const menuY = ref(0)

const menuStyle = computed(() => ({
  left: `${menuX.value}px`,
  top: `${menuY.value}px`,
  zIndex: menuZIndex.value,
}))

// Touch tracking
let pressTimer: ReturnType<typeof setTimeout> | null = null
let startX = 0
let startY = 0

function onTouchStart(e: TouchEvent) {
  if (!isMobile.value || props.disabled) return

  startX = e.touches[0].clientX
  startY = e.touches[0].clientY
  isPressed.value = true

  pressTimer = setTimeout(() => {
    showMenu(startX, startY)
  }, props.delay)
}

function onTouchMove(e: TouchEvent) {
  if (!pressTimer) return
  const dx = Math.abs(e.touches[0].clientX - startX)
  const dy = Math.abs(e.touches[0].clientY - startY)
  if (dx > 10 || dy > 10) {
    cancelPress()
  }
}

function onTouchEnd() {
  cancelPress()
}

function cancelPress() {
  if (pressTimer) {
    clearTimeout(pressTimer)
    pressTimer = null
  }
  isPressed.value = false
}

function showMenu(x: number, y: number) {
  isPressed.value = false
  menuZIndex.value = nextZIndex()

  // Auto-position to stay in viewport
  const padding = 8
  const menuWidth = 180
  const menuHeight = props.items.length * 48 + 8
  const viewW = window.innerWidth
  const viewH = window.innerHeight

  menuX.value = Math.min(x, viewW - menuWidth - padding)
  menuY.value = Math.min(y, viewH - menuHeight - padding)
  menuY.value = Math.max(menuY.value, padding)

  menuVisible.value = true
  emit('open')
}

function closeMenu() {
  if (menuVisible.value) {
    menuVisible.value = false
    emit('close')
  }
}

function onItemClick(item: MenuItem) {
  if (item.disabled) return
  item.onClick()
  emit('select', item)
  closeMenu()
}

onUnmounted(() => {
  if (pressTimer) clearTimeout(pressTimer)
})
</script>

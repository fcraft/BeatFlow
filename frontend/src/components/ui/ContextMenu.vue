<template>
  <Teleport to="body">
    <div
      v-if="visible"
      :style="{ left: position.x + 'px', top: position.y + 'px', zIndex }"
      class="fixed min-w-[160px] bg-white border border-gray-200 rounded-lg shadow-lg py-1"
      @click.stop
    >
      <template v-for="(item, idx) in items" :key="idx">
        <div v-if="item.separator" class="border-t border-gray-100 my-1" />
        <button
          v-else
          class="w-full text-left px-3 py-1.5 text-sm flex items-center gap-2 hover:bg-gray-50 transition-colors"
          :class="item.disabled ? 'text-gray-300 cursor-not-allowed' : 'text-gray-700'"
          :disabled="item.disabled"
          @click="handleClick(item)"
        >
          <component :is="item.icon" v-if="item.icon" class="w-3.5 h-3.5 shrink-0" />
          <span class="flex-1">{{ item.label }}</span>
          <span v-if="item.shortcut" class="text-xs text-gray-400">{{ item.shortcut }}</span>
        </button>
      </template>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, type Component } from 'vue'
import { nextZIndex } from '@/constants/zIndex'

export interface ContextMenuItem {
  label: string
  icon?: Component
  shortcut?: string
  disabled?: boolean
  separator?: boolean
  onClick?: () => void
}

interface Props {
  items: ContextMenuItem[]
}

const props = defineProps<Props>()

const emit = defineEmits<{
  (e: 'close'): void
}>()

const visible = ref(false)
const position = ref({ x: 0, y: 0 })
const zIndex = nextZIndex()

function show(x: number, y: number) {
  // Keep menu within viewport
  const menuW = 180
  const menuH = Math.min(props.items.length * 32 + 16, 400)
  position.value = {
    x: Math.min(x, window.innerWidth - menuW),
    y: Math.min(y, window.innerHeight - menuH),
  }
  visible.value = true
}

function hide() {
  visible.value = false
  emit('close')
}

function handleClick(item: ContextMenuItem) {
  if (item.disabled) return
  if (item.onClick) item.onClick()
  hide()
}

function handleGlobalClick(e: MouseEvent) {
  hide()
}

function handleEscape(e: KeyboardEvent) {
  if (e.key === 'Escape') hide()
}

onMounted(() => {
  document.addEventListener('click', handleGlobalClick, true)
  document.addEventListener('keydown', handleEscape)
})

onUnmounted(() => {
  document.removeEventListener('click', handleGlobalClick, true)
  document.removeEventListener('keydown', handleEscape)
})

defineExpose({ show, hide })
</script>

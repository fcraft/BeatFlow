<script setup lang="ts">
/**
 * FloatingPanel — 通用可拖拽悬浮面板
 *
 * 用于 P-V 环、动作电位、Wiggers 图等临床可视化面板。
 */
import { ref, onMounted, onUnmounted } from 'vue'
import { X } from 'lucide-vue-next'

const props = withDefaults(defineProps<{
  title: string
  defaultX?: number
  defaultY?: number
  width?: number
  height?: number
}>(), {
  defaultX: 80,
  defaultY: 80,
  width: 360,
  height: 280,
})

const emit = defineEmits<{ close: [] }>()

const posX = ref(props.defaultX)
const posY = ref(props.defaultY)
const isDragging = ref(false)
let dragOffsetX = 0
let dragOffsetY = 0

function onPointerDown(e: PointerEvent) {
  isDragging.value = true
  dragOffsetX = e.clientX - posX.value
  dragOffsetY = e.clientY - posY.value
  ;(e.target as HTMLElement).setPointerCapture(e.pointerId)
}

function onPointerMove(e: PointerEvent) {
  if (!isDragging.value) return
  posX.value = Math.max(0, e.clientX - dragOffsetX)
  posY.value = Math.max(0, e.clientY - dragOffsetY)
}

function onPointerUp() {
  isDragging.value = false
}
</script>

<template>
  <Teleport to="body">
    <div
      class="fixed z-[900] rounded-xl border border-white/[0.12] bg-gray-950/70 backdrop-blur-xl shadow-2xl overflow-hidden"
      :style="{
        left: posX + 'px',
        top: posY + 'px',
        width: width + 'px',
        height: height + 'px',
      }"
    >
      <!-- Drag handle + title -->
      <div
        class="flex items-center justify-between px-3 py-1.5 bg-white/[0.06] border-b border-white/[0.08] cursor-move select-none"
        @pointerdown="onPointerDown"
        @pointermove="onPointerMove"
        @pointerup="onPointerUp"
      >
        <span class="text-xs font-medium text-white/70 tracking-wide">{{ title }}</span>
        <button
          class="p-0.5 rounded hover:bg-white/10 transition-colors"
          @click="emit('close')"
          @pointerdown.stop
        >
          <X :size="14" class="text-white/50" />
        </button>
      </div>
      <!-- Content slot -->
      <div class="p-2 h-[calc(100%-32px)] overflow-hidden">
        <slot />
      </div>
    </div>
  </Teleport>
</template>

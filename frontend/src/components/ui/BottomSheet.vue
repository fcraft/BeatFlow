<template>
  <Teleport to="body">
    <Transition name="bottom-sheet">
      <div
        v-if="modelValue"
        class="fixed inset-0 flex items-end"
        :style="{ zIndex: zIndex }"
      >
        <!-- Backdrop -->
        <div
          class="absolute inset-0 bg-black/50"
          data-testid="bottom-sheet-backdrop"
          @click="onBackdropClick"
        />

        <!-- Panel -->
        <div
          ref="panelRef"
          class="relative w-full bg-white rounded-t-2xl overflow-hidden"
          :style="panelStyle"
          @touchstart.passive="onTouchStart"
          @touchmove.passive="onTouchMove"
          @touchend.passive="onTouchEnd"
        >
          <!-- Drag handle -->
          <div class="flex justify-center pt-3 pb-1">
            <div class="w-10 h-1 rounded-full bg-gray-300" />
          </div>

          <!-- Header -->
          <div v-if="title || $slots.header || closable" class="flex items-center justify-between px-4 py-3">
            <slot name="header">
              <h3 v-if="title" class="text-lg font-semibold text-gray-900">{{ title }}</h3>
              <span v-else />
            </slot>
            <button
              v-if="closable"
              data-testid="bottom-sheet-close"
              class="p-1 rounded-full hover:bg-gray-100 transition-colors"
              @click="emit('update:modelValue', false)"
            >
              <X :size="20" class="text-gray-500" />
            </button>
          </div>

          <!-- Content -->
          <div class="overflow-y-auto pb-safe">
            <slot />
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { X } from 'lucide-vue-next'
import { nextZIndex } from '@/constants/zIndex'

const props = withDefaults(defineProps<{
  modelValue: boolean
  title?: string
  height?: string
  closable?: boolean
}>(), {
  height: 'auto',
  closable: true,
})

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
}>()

const zIndex = nextZIndex()
const panelRef = ref<HTMLElement | null>(null)

// Drag state
const dragStartY = ref(0)
const dragCurrentY = ref(0)
const isDragging = ref(false)

const panelStyle = computed(() => {
  const maxHeight = props.height === 'auto' ? '85vh' : props.height
  const translateY = isDragging.value
    ? Math.max(0, dragCurrentY.value - dragStartY.value)
    : 0

  return {
    maxHeight,
    transform: `translateY(${translateY}px)`,
    transition: isDragging.value ? 'none' : 'transform 0.3s ease',
  }
})

function onBackdropClick() {
  if (props.closable) {
    emit('update:modelValue', false)
  }
}

function onTouchStart(e: TouchEvent) {
  dragStartY.value = e.touches[0].clientY
  dragCurrentY.value = e.touches[0].clientY
  isDragging.value = true
}

function onTouchMove(e: TouchEvent) {
  if (!isDragging.value) return
  dragCurrentY.value = e.touches[0].clientY
}

function onTouchEnd() {
  if (!isDragging.value) return
  isDragging.value = false

  const panelHeight = panelRef.value?.offsetHeight ?? 0
  const dragDistance = dragCurrentY.value - dragStartY.value

  // Dismiss if dragged more than 30% of panel height
  if (panelHeight > 0 && dragDistance > panelHeight * 0.3) {
    emit('update:modelValue', false)
  }

  dragStartY.value = 0
  dragCurrentY.value = 0
}
</script>

<style scoped>
.bottom-sheet-enter-active,
.bottom-sheet-leave-active {
  transition: opacity 0.3s ease;
}

.bottom-sheet-enter-active .relative,
.bottom-sheet-leave-active .relative {
  transition: transform 0.3s ease;
}

.bottom-sheet-enter-from,
.bottom-sheet-leave-to {
  opacity: 0;
}

.bottom-sheet-enter-from .relative,
.bottom-sheet-leave-to .relative {
  transform: translateY(100%);
}

.pb-safe {
  padding-bottom: env(safe-area-inset-bottom, 0px);
}
</style>

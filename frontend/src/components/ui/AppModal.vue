<template>
  <Teleport to="body">
    <Transition name="modal">
      <div
        v-if="modelValue"
        class="fixed inset-0 z-40 flex items-end sm:items-center justify-center sm:p-4"
        @click.self="closeOnBackdrop && $emit('update:modelValue', false)"
      >
        <div class="absolute inset-0 bg-black/40 backdrop-blur-sm" />
        <div
          class="relative bg-white w-full flex flex-col max-h-[92vh]
                 rounded-t-2xl sm:rounded-2xl shadow-2xl"
          :style="smUp ? { maxWidth: width } : {}"
        >
          <!-- Mobile drag handle -->
          <div class="flex justify-center pt-3 pb-1 sm:hidden shrink-0">
            <div class="w-10 h-1 bg-gray-200 rounded-full" />
          </div>
          <!-- Header -->
          <div v-if="title" class="flex items-center justify-between px-5 py-3.5 sm:px-6 sm:py-4 border-b border-gray-100 shrink-0">
            <h3 class="text-base font-semibold text-gray-900">{{ title }}</h3>
            <button
              class="btn-icon rounded-lg text-gray-400"
              @click="$emit('update:modelValue', false)"
            >
              <X class="w-4 h-4" />
            </button>
          </div>
          <!-- Body -->
          <div class="px-5 py-4 sm:px-6 sm:py-5 overflow-y-auto flex-1">
            <slot />
          </div>
          <!-- Footer -->
          <div v-if="$slots.footer" class="px-5 py-3.5 sm:px-6 sm:py-4 border-t border-gray-100 flex justify-end gap-3 shrink-0">
            <slot name="footer" />
          </div>
          <!-- Mobile bottom safe area -->
          <div class="sm:hidden h-safe-bottom shrink-0" style="height: env(safe-area-inset-bottom, 0px)" />
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { X } from 'lucide-vue-next'

withDefaults(defineProps<{
  modelValue: boolean
  title?: string
  width?: string
  closeOnBackdrop?: boolean
}>(), { closeOnBackdrop: true, width: '480px' })
defineEmits(['update:modelValue'])

// Detect sm breakpoint (640px) for conditional maxWidth style
const smUp = ref(false)
const check = () => { smUp.value = window.innerWidth >= 640 }
onMounted(() => { check(); window.addEventListener('resize', check) })
onUnmounted(() => { window.removeEventListener('resize', check) })
</script>

<style>
.modal-enter-active, .modal-leave-active { transition: all 0.25s ease; }
.modal-enter-from, .modal-leave-to { opacity: 0; }
/* Desktop: scale in */
@media (min-width: 640px) {
  .modal-enter-from .relative, .modal-leave-to .relative { transform: scale(0.95); }
}
/* Mobile: slide up */
@media (max-width: 639px) {
  .modal-enter-from .relative, .modal-leave-to .relative { transform: translateY(100%); }
}
</style>

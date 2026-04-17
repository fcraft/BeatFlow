<template>
  <Teleport to="body">
    <Transition name="modal" appear>
      <div
        v-if="modelValue"
        class="fixed inset-0 z-40 modal-overlay"
        @click.self="handleBackdropClick"
      >
        <div class="modal-positioner" @click.self="handleBackdropClick">
          <div
            class="modal-panel relative bg-white w-full flex flex-col max-h-[92vh]
                   rounded-t-2xl sm:rounded-2xl shadow-2xl"
            :style="smUp ? { maxWidth: width } : { maxWidth: 'calc(100vw - 2rem)' }"
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
                @click="emit('update:modelValue', false)"
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
            <div class="sm:hidden shrink-0" style="height: env(safe-area-inset-bottom, 0px)" />
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { X } from 'lucide-vue-next'
import { useMobile } from '@/composables/useMobile'

const props = withDefaults(defineProps<{
  modelValue: boolean
  title?: string
  width?: string
  closeOnBackdrop?: boolean
  mobileMode?: 'center' | 'bottom-sheet'
}>(), { closeOnBackdrop: true, width: '480px', mobileMode: 'bottom-sheet' })

const emit = defineEmits(['update:modelValue'])

const { isMobile } = useMobile()
const smUp = computed(() => !isMobile.value)

function handleBackdropClick() {
  if (props.closeOnBackdrop) {
    emit('update:modelValue', false)
  }
}
</script>

<style>
/* ─── Overlay (backdrop + blur) ─── */
.modal-overlay {
  background: rgba(0, 0, 0, 0.4);
  backdrop-filter: blur(6px);
  -webkit-backdrop-filter: blur(6px);
}

/* ─── Positioner ─── */
.modal-positioner {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: flex-end;
  justify-content: center;
}
@media (min-width: 640px) {
  .modal-positioner {
    align-items: center;
    padding: 1rem;
  }
}

/* ─── Single transition: overlay fades, panel animates ─── */
.modal-enter-active {
  transition: background 0.3s ease, backdrop-filter 0.3s ease, -webkit-backdrop-filter 0.3s ease;
}
.modal-enter-active .modal-panel {
  transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}
.modal-leave-active {
  transition: background 0.25s ease 0.05s, backdrop-filter 0.25s ease 0.05s, -webkit-backdrop-filter 0.25s ease 0.05s;
}
.modal-leave-active .modal-panel {
  transition: all 0.2s ease-in;
}

/* ─── Enter from ─── */
.modal-enter-from {
  background: rgba(0, 0, 0, 0);
  backdrop-filter: blur(0px);
  -webkit-backdrop-filter: blur(0px);
}

/* ─── Leave to ─── */
.modal-leave-to {
  background: rgba(0, 0, 0, 0);
  backdrop-filter: blur(0px);
  -webkit-backdrop-filter: blur(0px);
}

/* ─── Desktop panel: scale ─── */
@media (min-width: 640px) {
  .modal-enter-from .modal-panel {
    opacity: 0;
    transform: scale(0.93) translateY(10px);
  }
  .modal-leave-to .modal-panel {
    opacity: 0;
    transform: scale(0.95) translateY(6px);
  }
}

/* ─── Mobile panel: slide up ─── */
@media (max-width: 639px) {
  .modal-enter-from .modal-panel {
    opacity: 0;
    transform: translateY(100%);
  }
  .modal-leave-to .modal-panel {
    opacity: 0;
    transform: translateY(60%);
  }
}
</style>

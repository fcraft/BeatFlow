<template>
  <div ref="wrapperRef" class="relative inline-block">
    <!-- Trigger slot -->
    <div @click="toggle">
      <slot name="trigger" :is-open="isOpen" />
    </div>

    <!-- Menu -->
    <Teleport to="body">
      <Transition
        enter-active-class="transition duration-150 ease-out"
        enter-from-class="opacity-0 -translate-y-1 scale-[0.98]"
        enter-to-class="opacity-100 translate-y-0 scale-100"
        leave-active-class="transition duration-100 ease-in"
        leave-from-class="opacity-100 translate-y-0 scale-100"
        leave-to-class="opacity-0 -translate-y-1 scale-[0.98]"
      >
        <div
          v-if="isOpen"
          ref="menuRef"
          data-app-dropdown
          class="fixed rounded-xl overflow-hidden py-1"
          :class="dark
            ? 'bg-gray-950/60 backdrop-blur-2xl backdrop-saturate-[1.8] border border-white/[0.15] ring-1 ring-black/30 shadow-2xl'
            : 'bg-white border border-gray-200 shadow-lg'"
          :style="menuStyle"
        >
          <slot :close="close" />
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, nextTick, onMounted, onUnmounted } from 'vue'
import { nextZIndex } from '@/constants/zIndex'

withDefaults(defineProps<{
  dark?: boolean
  width?: string
  align?: 'left' | 'right'
}>(), {
  dark: false,
  width: '160px',
  align: 'right',
})

const isOpen = ref(false)
const menuZIndex = ref(9000)

const wrapperRef = ref<HTMLElement | null>(null)
const menuRef = ref<HTMLElement | null>(null)

const pos = reactive({ top: 0, left: 0, right: 0 })
const menuStyle = computed(() => ({
  zIndex: menuZIndex.value,
  top: `${pos.top}px`,
  left: `${pos.left}px`,
  minWidth: '120px',
}))

function updatePos() {
  if (!wrapperRef.value) return
  const r = wrapperRef.value.getBoundingClientRect()
  pos.top = r.bottom + 4
  pos.left = r.left
}

function toggle() {
  isOpen.value = !isOpen.value
  if (isOpen.value) {
    menuZIndex.value = nextZIndex()
    nextTick(updatePos)
  }
}

function close() {
  isOpen.value = false
}

function onClickOutside(e: MouseEvent) {
  const t = e.target as Node
  if (wrapperRef.value?.contains(t)) return
  if (menuRef.value?.contains(t)) return
  if ((t as HTMLElement).closest?.('[data-app-dropdown]')) return
  isOpen.value = false
}

onMounted(() => {
  document.addEventListener('mousedown', onClickOutside)
  window.addEventListener('scroll', () => { if (isOpen.value) updatePos() }, true)
  window.addEventListener('resize', () => { if (isOpen.value) updatePos() })
})
onUnmounted(() => {
  document.removeEventListener('mousedown', onClickOutside)
})

defineExpose({ close, isOpen })
</script>

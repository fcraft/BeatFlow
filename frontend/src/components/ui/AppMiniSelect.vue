<template>
  <div ref="wrapperRef" class="inline-block" :class="block ? 'w-full' : ''">
    <!-- Trigger -->
    <button
      ref="triggerRef"
      type="button"
      class="app-mini-trigger"
      :class="[
        `app-mini-trigger--${size}`,
        block ? 'w-full' : '',
        isOpen ? 'app-mini-trigger--open' : '',
        disabled ? 'app-mini-trigger--disabled' : '',
      ]"
      :disabled="disabled"
      @click="toggle"
    >
      <span class="truncate">{{ currentLabel || placeholder }}</span>
      <svg class="app-mini-chevron" :class="isOpen && 'rotate-180'" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m6 9 6 6 6-6"/></svg>
    </button>

    <!-- Dropdown -->
    <Teleport to="body">
      <Transition
        enter-active-class="transition duration-120 ease-out"
        enter-from-class="opacity-0 -translate-y-0.5 scale-[0.98]"
        enter-to-class="opacity-100 translate-y-0 scale-100"
        leave-active-class="transition duration-75 ease-in"
        leave-from-class="opacity-100 translate-y-0 scale-100"
        leave-to-class="opacity-0 -translate-y-0.5 scale-[0.98]"
      >
        <div
          v-if="isOpen"
          ref="dropdownRef"
          data-app-select-dropdown
          class="fixed rounded-lg overflow-hidden py-0.5"
          :class="dark
            ? 'bg-gray-950/70 backdrop-blur-2xl border border-white/[0.12] shadow-2xl ring-1 ring-black/30'
            : 'bg-white border border-gray-200/80 shadow-lg ring-1 ring-black/[0.04]'"
          :style="dropdownStyle"
        >
          <div class="overflow-y-auto" style="max-height: 200px">
            <button
              v-for="opt in options"
              :key="String(opt.value)"
              class="app-mini-option"
              :class="[
                `app-mini-option--${size}`,
                dark
                  ? (opt.value === modelValue ? 'text-sky-400 bg-sky-400/10' : 'text-white/70 hover:bg-white/[0.06]')
                  : (opt.value === modelValue ? 'text-blue-600 bg-blue-50' : 'text-gray-700 hover:bg-gray-50'),
              ]"
              @click="select(opt)"
            >
              <svg v-if="opt.value === modelValue" class="shrink-0" :class="dark ? 'text-sky-400' : 'text-blue-500'" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
              <div v-else class="w-3" />
              <span class="truncate">{{ opt.label }}</span>
            </button>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, nextTick, onMounted, onUnmounted } from 'vue'
import { nextZIndex } from '@/constants/zIndex'

export interface MiniSelectOption {
  value: string | number
  label: string
}

const props = withDefaults(defineProps<{
  modelValue: string | number
  options: MiniSelectOption[]
  size?: 'xs' | 'sm' | 'md'
  placeholder?: string
  block?: boolean
  disabled?: boolean
  numeric?: boolean
  dark?: boolean
}>(), {
  size: 'sm',
  placeholder: '请选择',
  block: false,
  disabled: false,
  numeric: false,
  dark: false,
})

const emit = defineEmits<{
  'update:modelValue': [value: string | number]
}>()

const isOpen = ref(false)
const dropdownZ = ref(9000)
const wrapperRef = ref<HTMLElement | null>(null)
const triggerRef = ref<HTMLElement | null>(null)
const dropdownRef = ref<HTMLElement | null>(null)

const pos = reactive({ top: 0, left: 0, width: 0 })
const dropdownStyle = computed(() => ({
  zIndex: dropdownZ.value,
  top: `${pos.top}px`,
  left: `${pos.left}px`,
  minWidth: `${Math.max(pos.width, 80)}px`,
}))

const currentLabel = computed(() => {
  const opt = props.options.find(o => o.value === props.modelValue)
  return opt?.label ?? ''
})

function updatePos() {
  if (!triggerRef.value) return
  const r = triggerRef.value.getBoundingClientRect()
  pos.top = r.bottom + 3
  pos.left = r.left
  pos.width = r.width
}

function toggle() {
  if (props.disabled) return
  isOpen.value = !isOpen.value
  if (isOpen.value) {
    dropdownZ.value = nextZIndex()
    nextTick(updatePos)
  }
}

function select(opt: MiniSelectOption) {
  const val = props.numeric && typeof opt.value === 'string' ? Number(opt.value) : opt.value
  emit('update:modelValue', Number.isFinite(val as number) ? val : opt.value)
  isOpen.value = false
}

function onClickOutside(e: MouseEvent) {
  const t = e.target as Node
  if (wrapperRef.value?.contains(t)) return
  if (dropdownRef.value?.contains(t)) return
  isOpen.value = false
}

function onScrollResize() {
  if (isOpen.value) updatePos()
}

onMounted(() => {
  document.addEventListener('mousedown', onClickOutside)
  window.addEventListener('scroll', onScrollResize, true)
  window.addEventListener('resize', onScrollResize)
})
onUnmounted(() => {
  document.removeEventListener('mousedown', onClickOutside)
  window.removeEventListener('scroll', onScrollResize, true)
  window.removeEventListener('resize', onScrollResize)
})
</script>

<style scoped>
.app-mini-trigger {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: white;
  color: #374151;
  font-weight: 500;
  cursor: pointer;
  outline: none;
  transition: border-color 0.15s, box-shadow 0.15s;
  white-space: nowrap;
}
.app-mini-trigger:hover { border-color: #d1d5db; }
.app-mini-trigger--open { border-color: #93c5fd; box-shadow: 0 0 0 2px rgba(59,130,246,0.12); }
.app-mini-trigger--disabled { opacity: 0.5; cursor: not-allowed; pointer-events: none; }

.app-mini-trigger--xs { font-size: 11px; padding: 2px 6px; border-radius: 6px; }
.app-mini-trigger--sm { font-size: 12px; padding: 3px 8px; border-radius: 7px; }
.app-mini-trigger--md { font-size: 13px; padding: 5px 10px; border-radius: 8px; }

.app-mini-chevron {
  color: #9ca3af;
  flex-shrink: 0;
  transition: transform 0.15s;
}

.app-mini-option {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 6px;
  text-align: left;
  cursor: pointer;
  transition: background-color 0.1s;
  white-space: nowrap;
}
.app-mini-option--xs { font-size: 11px; padding: 3px 8px; }
.app-mini-option--sm { font-size: 12px; padding: 4px 10px; }
.app-mini-option--md { font-size: 13px; padding: 6px 12px; }
</style>

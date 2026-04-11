<template>
  <div ref="wrapperRef" class="inline-block" :class="block ? 'w-full' : ''">
    <!-- Trigger -->
    <button
      ref="triggerRef"
      type="button"
      class="flex items-center gap-2 text-left transition-all duration-200"
      :class="[
        block ? 'w-full' : '',
        dark
          ? [
              'px-3 py-2 border rounded-xl',
              'border-white/[0.12] bg-white/[0.06]',
              isOpen ? 'ring-2 ring-sky-400/40 border-sky-400/40' : 'hover:border-white/20 hover:bg-white/[0.08]'
            ]
          : [
              'px-3 py-2.5 border rounded-xl',
              'border-gray-200 bg-white',
              isOpen ? 'ring-2 ring-primary-500/20 border-primary-400' : 'hover:border-gray-300'
            ]
      ]"
      @click="toggle"
    >
      <component v-if="icon" :is="icon" class="w-4 h-4 shrink-0" :class="dark ? 'text-white/40' : 'text-gray-400'" />
      <span class="flex-1 truncate text-sm" :class="currentLabel
        ? (dark ? 'text-white/90' : 'text-gray-900')
        : (dark ? 'text-white/40' : 'text-gray-400')
      ">{{ currentLabel || placeholder }}</span>
      <ChevronDown class="w-3.5 h-3.5 shrink-0 transition-transform duration-200"
                   :class="[dark ? 'text-white/40' : 'text-gray-400', isOpen && 'rotate-180']" />
    </button>

    <!-- Dropdown -->
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
          ref="dropdownRef"
          data-app-select-dropdown
          class="fixed rounded-xl overflow-hidden"
          :class="dark
            ? 'bg-gray-950/60 backdrop-blur-2xl backdrop-saturate-[1.8] border border-white/[0.15] ring-1 ring-black/30 shadow-2xl'
            : 'bg-white/80 backdrop-blur-xl backdrop-saturate-[1.6] border border-gray-200/60 ring-1 ring-black/[0.04] shadow-xl'
          "
          :style="{ ...posStyle, zIndex: dropdownZIndex }"
        >
          <!-- Search (optional) -->
          <div v-if="searchable" class="px-3 py-2 border-b" :class="dark ? 'border-white/[0.08]' : 'border-gray-100'">
            <div class="flex items-center gap-2">
              <Search class="w-3.5 h-3.5 shrink-0" :class="dark ? 'text-white/30' : 'text-gray-400'" />
              <input
                ref="searchRef"
                v-model="query"
                type="text"
                class="w-full text-sm bg-transparent outline-none"
                :class="dark ? 'text-white/90 placeholder-white/30' : 'text-gray-900 placeholder-gray-400'"
                :placeholder="searchPlaceholder"
                @keydown.escape="isOpen = false"
              />
            </div>
          </div>

          <!-- Options -->
          <div class="overflow-y-auto" style="max-height: 220px">
            <button
              v-for="opt in filteredOptions"
              :key="String(opt.value)"
              class="w-full flex items-center gap-2.5 px-3 py-2 text-left text-sm transition-colors"
              :class="dark
                ? (opt.value === modelValue
                  ? 'bg-sky-400/10 text-sky-400 font-medium'
                  : 'text-white/70 hover:bg-white/[0.06] hover:text-white')
                : (opt.value === modelValue
                  ? 'bg-primary-500/10 text-primary-700 font-medium'
                  : 'text-gray-700 hover:bg-black/[0.03]')
              "
              @click="select(opt)"
            >
              <Check v-if="opt.value === modelValue" class="w-3.5 h-3.5 shrink-0" :class="dark ? 'text-sky-400' : 'text-primary-500'" />
              <div v-else class="w-3.5 h-3.5 shrink-0" />
              <component v-if="opt.icon" :is="opt.icon" class="w-3.5 h-3.5 shrink-0" :class="dark ? 'text-white/40' : 'text-gray-400'" />
              <span class="truncate">{{ opt.label }}</span>
              <span v-if="opt.badge" class="ml-auto text-xs shrink-0" :class="dark ? 'text-white/30' : 'text-gray-400'">{{ opt.badge }}</span>
            </button>
            <div v-if="filteredOptions.length === 0" class="px-3 py-4 text-center text-xs" :class="dark ? 'text-white/30' : 'text-gray-400'">
              无匹配选项
            </div>
          </div>

          <!-- Footer slot -->
          <div v-if="$slots.footer" class="border-t" :class="dark ? 'border-white/[0.08]' : 'border-gray-100'">
            <slot name="footer" :close="() => isOpen = false" />
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, nextTick, onMounted, onUnmounted, type Component } from 'vue'
import { ChevronDown, Search, Check } from 'lucide-vue-next'
import { nextZIndex } from '@/constants/zIndex'

export interface SelectOption {
  value: string | number
  label: string
  icon?: Component
  badge?: string
}

const props = withDefaults(defineProps<{
  modelValue: string | number
  options: SelectOption[]
  placeholder?: string
  icon?: Component
  dark?: boolean
  block?: boolean
  searchable?: boolean
  searchPlaceholder?: string
}>(), {
  placeholder: '请选择',
  dark: false,
  block: false,
  searchable: false,
  searchPlaceholder: '搜索...',
})

const emit = defineEmits<{
  'update:modelValue': [value: string | number]
}>()

const isOpen = ref(false)
const query = ref('')
const dropdownZIndex = ref(9000)

const wrapperRef = ref<HTMLElement | null>(null)
const triggerRef = ref<HTMLElement | null>(null)
const dropdownRef = ref<HTMLElement | null>(null)
const searchRef = ref<HTMLInputElement | null>(null)

const pos = reactive({ top: 0, left: 0, width: 0 })
const posStyle = computed(() => ({
  top: `${pos.top}px`,
  left: `${pos.left}px`,
  width: `${Math.max(pos.width, 160)}px`,
}))

function updatePos() {
  if (!triggerRef.value) return
  const r = triggerRef.value.getBoundingClientRect()
  pos.top = r.bottom + 4
  pos.left = r.left
  pos.width = r.width
}

const currentLabel = computed(() => {
  const opt = props.options.find(o => o.value === props.modelValue)
  return opt?.label ?? ''
})

const filteredOptions = computed(() => {
  if (!props.searchable || !query.value.trim()) return props.options
  const q = query.value.toLowerCase()
  return props.options.filter(o => o.label.toLowerCase().includes(q))
})

function toggle() {
  isOpen.value = !isOpen.value
  if (isOpen.value) {
    dropdownZIndex.value = nextZIndex()
    query.value = ''
    nextTick(() => {
      updatePos()
      searchRef.value?.focus()
    })
  }
}

function select(opt: SelectOption) {
  emit('update:modelValue', opt.value)
  isOpen.value = false
}

function onClickOutside(e: MouseEvent) {
  const t = e.target as Node
  if (!wrapperRef.value?.contains(t) && !dropdownRef.value?.contains(t)) {
    isOpen.value = false
  }
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

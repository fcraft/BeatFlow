<template>
  <div ref="trackRef" class="app-seg" :class="[`app-seg--${size}`, block && 'app-seg--block']">
    <!-- 滑动指示器 -->
    <div
      v-if="activeIndex >= 0"
      class="app-seg__indicator"
      :style="indicatorStyle"
    />
    <!-- 选项按钮 -->
    <button
      v-for="(opt, idx) in options"
      :key="String(opt.value)"
      :ref="el => setItemRef(idx, el as HTMLElement)"
      class="app-seg__item"
      :class="modelValue === opt.value && 'app-seg__item--active'"
      @click="emit('update:modelValue', opt.value)"
    >{{ opt.label }}</button>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, nextTick } from 'vue'

export interface SegmentOption {
  value: string | number
  label: string
}

const props = withDefaults(defineProps<{
  modelValue: string | number
  options: SegmentOption[]
  size?: 'xs' | 'sm' | 'md'
  block?: boolean
}>(), {
  size: 'sm',
  block: false,
})

const emit = defineEmits<{
  'update:modelValue': [value: string | number]
}>()

const activeIndex = computed(() =>
  props.options.findIndex(o => o.value === props.modelValue)
)

// ── DOM 测量驱动的指示器定位 ──
const trackRef = ref<HTMLElement | null>(null)
const itemRefs: HTMLElement[] = []

function setItemRef(idx: number, el: HTMLElement | null) {
  if (el) itemRefs[idx] = el
}

const indicatorPos = ref({ left: 0, width: 0 })

function updateIndicator() {
  const idx = activeIndex.value
  if (idx < 0 || !trackRef.value || !itemRefs[idx]) return
  const trackRect = trackRef.value.getBoundingClientRect()
  const itemRect = itemRefs[idx].getBoundingClientRect()
  indicatorPos.value = {
    left: itemRect.left - trackRect.left,
    width: itemRect.width,
  }
}

const indicatorStyle = computed(() => ({
  transform: `translateX(${indicatorPos.value.left}px)`,
  width: `${indicatorPos.value.width}px`,
}))

watch(activeIndex, () => nextTick(updateIndicator))
watch(() => props.options.length, () => nextTick(updateIndicator))
onMounted(() => nextTick(updateIndicator))
</script>

<style scoped>
.app-seg {
  position: relative;
  display: inline-flex;
  align-items: center;
  gap: 2px;
  background: #f3f4f6;
  border-radius: 8px;
  padding: 3px;
}
.app-seg--block { display: flex; width: 100%; }

/* ── 滑动指示器 ── */
.app-seg__indicator {
  position: absolute;
  top: 3px;
  bottom: 3px;
  left: 0;
  border-radius: 6px;
  background: white;
  box-shadow: 0 1px 3px rgba(0,0,0,0.08), 0 0 0 0.5px rgba(0,0,0,0.04);
  transition: transform 0.25s cubic-bezier(0.16, 1, 0.3, 1),
              width 0.25s cubic-bezier(0.16, 1, 0.3, 1);
  pointer-events: none;
  z-index: 0;
}

/* ── 选项按钮 ── */
.app-seg__item {
  position: relative;
  z-index: 1;
  flex: 0 0 auto;
  font-weight: 500;
  border-radius: 6px;
  transition: color 0.2s ease;
  color: #6b7280;
  cursor: pointer;
  white-space: nowrap;
  background: transparent;
}
.app-seg--block .app-seg__item { flex: 1; text-align: center; }

.app-seg__item:hover:not(.app-seg__item--active) { color: #374151; }
.app-seg__item--active { color: #111827; }

/* ── Size variants ── */
.app-seg--xs .app-seg__item { font-size: 11px; padding: 2px 8px; }
.app-seg--sm .app-seg__item { font-size: 12px; padding: 3px 12px; }
.app-seg--md .app-seg__item { font-size: 13px; padding: 5px 16px; }
</style>

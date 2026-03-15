<script setup lang="ts">
/**
 * 多导联 ECG 显示组件 — Grid 布局
 *
 * 根据选中导联数自适应布局：
 * - 1 导联: 满宽
 * - 2-3 导联: 1 列纵向堆叠
 * - 4-6 导联: 2 列 grid
 * - 7-12 导联: 标准 4 列 × 3 行（临床 12 导联格式）
 */
import { computed } from 'vue'
import { useVirtualHumanStore } from '@/store/virtualHuman'
import EcgLeadStrip from './EcgLeadStrip.vue'

const store = useVirtualHumanStore()

const gridClass = computed(() => {
  const n = store.selectedLeads.length
  if (n <= 1) return 'grid-cols-1'
  if (n <= 3) return 'grid-cols-1'
  if (n <= 6) return 'grid-cols-2'
  return 'grid-cols-4' // 7-12: 临床 4×3 标准布局
})

/** 按临床标准排列导联顺序（4 列 × 3 行） */
const CLINICAL_ORDER = ['I','aVR','V1','V4','II','aVL','V2','V5','III','aVF','V3','V6']

const orderedLeads = computed(() => {
  const selected = new Set(store.selectedLeads)
  if (selected.size >= 7) {
    // 临床 12 导联排列：过滤出已选的
    return CLINICAL_ORDER.filter(l => selected.has(l))
  }
  return store.selectedLeads
})
</script>

<template>
  <div
    class="w-full h-full grid gap-1 overflow-hidden"
    :class="gridClass"
  >
    <EcgLeadStrip
      v-for="lead in orderedLeads"
      :key="lead"
      :lead-name="lead"
    />
  </div>
</template>

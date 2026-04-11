<script setup lang="ts">
/**
 * 多导联 ECG 显示组件
 *
 * 桌面端布局（grid）:
 *   - 1-3 导联: 1 列纵向堆叠
 *   - 4-6 导联: 2 列 grid
 *   - 7-12 导联: 标准 4 列 × 3 行（临床格式）
 *
 * 移动端布局（< 768px）:
 *   - 始终单列，每条固定高度 48px
 *   - 可垂直滚动，一次可见约 2-3 条
 *   - 当前滚动位置有 fade 渐隐提示还有更多
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
  return 'grid-cols-4'
})

const CLINICAL_ORDER = ['I','aVR','V1','V4','II','aVL','V2','V5','III','aVF','V3','V6']

const orderedLeads = computed(() => {
  const selected = new Set(store.selectedLeads)
  if (selected.size >= 7) {
    return CLINICAL_ORDER.filter(l => selected.has(l))
  }
  return store.selectedLeads
})
</script>

<template>
  <div class="w-full h-full overflow-hidden">
    <!-- Desktop: grid layout -->
    <div class="w-full h-full grid gap-1 overflow-hidden cmd-desktop-only"
         :class="gridClass">
      <EcgLeadStrip
        v-for="lead in orderedLeads"
        :key="'d-' + lead"
        :lead-name="lead"
      />
    </div>

    <!-- Mobile: scrollable single-column strip list -->
    <div class="w-full h-full overflow-y-auto overflow-x-hidden cmd-mobile-only
                scrollbar-hide relative">
      <div class="flex flex-col gap-0.5">
        <div v-for="lead in orderedLeads" :key="'m-' + lead"
             class="shrink-0" style="height: 48px">
          <EcgLeadStrip :lead-name="lead" />
        </div>
      </div>
      <!-- Bottom fade hint when scrollable -->
      <div v-if="orderedLeads.length > 3"
           class="sticky bottom-0 left-0 right-0 h-6 pointer-events-none"
           style="background: linear-gradient(transparent, rgba(6,6,8,0.8))" />
    </div>
  </div>
</template>

<style scoped>
.scrollbar-hide::-webkit-scrollbar { display: none; }
.scrollbar-hide { -ms-overflow-style: none; scrollbar-width: none; }
</style>

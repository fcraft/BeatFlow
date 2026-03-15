<script setup lang="ts">
/**
 * 12 导联 ECG 选择器
 *
 * 提供 12 个导联 toggle 按钮 + "全部 12 导" 快捷按钮。
 * 选中的导联会持久化到 localStorage，刷新页面后自动恢复。
 */
import { onMounted, watch } from 'vue'
import { useVirtualHumanStore } from '@/store/virtualHuman'

const STORAGE_KEY = 'beatflow-selected-leads'

const store = useVirtualHumanStore()

// Restore persisted selection on mount
onMounted(() => {
  const saved = localStorage.getItem(STORAGE_KEY)
  if (saved) {
    try {
      const leads = JSON.parse(saved) as string[]
      if (Array.isArray(leads) && leads.length > 0) {
        store.setLeads(leads)
      }
    } catch { /* ignore invalid JSON */ }
  }
})

// Persist selection whenever it changes
watch(() => store.selectedLeads, (newLeads) => {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(newLeads))
}, { deep: true })

const ALL_12 = ['I','II','III','aVR','aVL','aVF','V1','V2','V3','V4','V5','V6']

/** 肢体导联 vs 胸导联分组 */
const limbLeads = ['I', 'II', 'III', 'aVR', 'aVL', 'aVF']
const chestLeads = ['V1', 'V2', 'V3', 'V4', 'V5', 'V6']

function isSelected(lead: string): boolean {
  return store.selectedLeads.includes(lead)
}

function toggleLead(lead: string) {
  const current = [...store.selectedLeads]
  const idx = current.indexOf(lead)
  if (idx !== -1) {
    // 不允许取消所有导联（至少保留一个）
    if (current.length <= 1) return
    current.splice(idx, 1)
  } else {
    current.push(lead)
  }
  store.setLeads(current)
}

function selectAll12() {
  store.setLeads([...ALL_12])
}

function selectSingle(lead: string) {
  store.setLeads([lead])
}

function isLimb(lead: string): boolean {
  return limbLeads.includes(lead)
}
</script>

<template>
  <div class="flex items-center gap-1.5 flex-wrap">
    <!-- 全部 12 导快捷按钮 -->
    <button
      class="px-2 py-0.5 text-[10px] font-medium rounded border transition-colors"
      :class="store.selectedLeads.length === 12
        ? 'text-emerald-600 bg-emerald-50 border-emerald-300'
        : 'text-gray-400 border-gray-200 hover:bg-gray-50'"
      @click="selectAll12"
    >
      全部12导
    </button>

    <span class="text-gray-300 text-[10px]">|</span>

    <!-- 逐导联 toggle -->
    <button
      v-for="lead in ALL_12"
      :key="lead"
      class="px-1.5 py-0.5 text-[10px] font-mono rounded border transition-colors"
      :class="isSelected(lead)
        ? (isLimb(lead)
            ? 'text-green-600 bg-green-50 border-green-300'
            : 'text-blue-600 bg-blue-50 border-blue-300')
        : 'text-gray-400 border-gray-200 hover:bg-gray-50'"
      @click="toggleLead(lead)"
      @dblclick.prevent="selectSingle(lead)"
      :title="`${lead} — 单击切换, 双击单选`"
    >
      {{ lead }}
    </button>
  </div>
</template>

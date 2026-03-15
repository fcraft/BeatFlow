<script setup lang="ts">
/**
 * CmdSyncIndicator — ECG-PCG 同步时序薄条
 */
import { computed } from 'vue'
import { useVirtualHumanStore } from '@/store/virtualHuman'

const store = useVirtualHumanStore()

const ann = computed(() => {
  const a = store.beatAnnotations
  return a.length > 0 ? a[a.length - 1] : null
})

const s1Delay = computed(() => {
  const v = ann.value
  if (!v?.qrs_ms) return '50'
  return String(Math.round(v.qrs_ms * 0.3 + 30))
})

const s2Delay = computed(() => {
  const v = ann.value
  if (!v?.qt_ms) return '30'
  return String(Math.round(v.qt_ms * 0.1 + 20))
})
</script>

<template>
  <div v-if="store.connected"
       class="flex items-center justify-center gap-6 py-1.5 shrink-0"
       style="background: rgba(255,255,255,0.02); font-family: var(--cmd-font-mono)">
    <span class="text-[10px] text-white/20">QRS→S1: ~{{ s1Delay }}ms</span>
    <span class="text-[10px] text-white/20">T→S2: ~{{ s2Delay }}ms</span>
    <span v-if="ann?.pr_ms" class="text-[10px] text-[#34C759]/60">PR {{ ann.pr_ms }}ms</span>
    <span v-if="ann?.qrs_ms" class="text-[10px] text-[#007AFF]/60">QRS {{ ann.qrs_ms }}ms</span>
    <span v-if="ann?.qt_ms" class="text-[10px] text-[#AF52DE]/60">QT {{ ann.qt_ms }}ms</span>
  </div>
</template>

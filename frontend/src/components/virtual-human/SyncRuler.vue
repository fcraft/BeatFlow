<script setup lang="ts">
/**
 * 同步标尺 — ECG 与 PCG 之间的时序关系指示条
 */
import { computed } from 'vue'
import { useVirtualHumanStore } from '@/store/virtualHuman'

const store = useVirtualHumanStore()

const latestAnnotation = computed(() => {
  const annotations = store.beatAnnotations
  if (annotations.length === 0) return null
  return annotations[annotations.length - 1]
})

const s1Delay = computed(() => {
  const ann = latestAnnotation.value
  if (!ann?.qrs_ms) return '50'
  return String(Math.round(ann.qrs_ms * 0.3 + 30))
})

const s2Delay = computed(() => {
  const ann = latestAnnotation.value
  if (!ann?.qt_ms) return '30'
  return String(Math.round(ann.qt_ms * 0.1 + 20))
})
</script>

<template>
  <div
    v-if="store.connected"
    class="flex items-center justify-center gap-4 py-1 bg-white/[0.04] border-y border-white/[0.06] rounded"
  >
    <span class="text-[10px] text-white/30">
      QRS→S1: ~{{ s1Delay }}ms
    </span>
    <span class="text-[10px] text-white/30">
      T→S2: ~{{ s2Delay }}ms
    </span>
    <span v-if="latestAnnotation?.pr_ms" class="text-[10px] text-green-400">
      PR: {{ latestAnnotation.pr_ms }}ms
    </span>
    <span v-if="latestAnnotation?.qrs_ms" class="text-[10px] text-blue-400">
      QRS: {{ latestAnnotation.qrs_ms }}ms
    </span>
    <span v-if="latestAnnotation?.qt_ms" class="text-[10px] text-purple-400">
      QT: {{ latestAnnotation.qt_ms }}ms
    </span>
  </div>
</template>

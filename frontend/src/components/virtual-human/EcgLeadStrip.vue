<script setup lang="ts">
/**
 * 单导联 ECG 波形条 — 用于多导联 grid 布局
 *
 * 每个实例独立持有一个 useScrollingCanvas，接收对应导联数据。
 * 导联名颜色编码：肢体导联绿色系、胸导联蓝色系。
 */
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useScrollingCanvas } from '@/composables/useScrollingCanvas'
import { useVirtualHumanStore } from '@/store/virtualHuman'
import type { SignalChunk } from '@/store/virtualHuman'

const props = defineProps<{
  leadName: string
}>()

const store = useVirtualHumanStore()
const canvasRef = ref<HTMLCanvasElement | null>(null)

const limbLeads = ['I', 'II', 'III', 'aVR', 'aVL', 'aVF']
const isLimb = limbLeads.includes(props.leadName)
const leadColor = isLimb ? '#22c55e' : '#3b82f6' // green vs blue

const smoothingLevel = computed(() => store.ecgSmoothingLevel)

const { appendSamples, start, stop } = useScrollingCanvas({
  canvasRef,
  sampleRate: 500,
  displaySeconds: 5,
  lineColor: leadColor,
  label: props.leadName,
  playbackDelayMs: 180,
  smoothingLevel,
})

function onLeadChunk(chunk: SignalChunk) {
  appendSamples(chunk)
}

onMounted(() => {
  if (props.leadName === 'II') {
    // Lead II 使用 legacy ecg callback
    store.registerEcgCallback(onLeadChunk)
  } else {
    store.registerLeadCallback(props.leadName, onLeadChunk)
  }
  start()
})

onUnmounted(() => {
  if (props.leadName === 'II') {
    store.unregisterEcgCallback(onLeadChunk)
  } else {
    store.unregisterLeadCallback(props.leadName, onLeadChunk)
  }
  stop()
})
</script>

<template>
  <div class="relative w-full h-full min-h-[60px] rounded overflow-hidden border border-gray-700">
    <canvas ref="canvasRef" class="w-full h-full block" />
  </div>
</template>

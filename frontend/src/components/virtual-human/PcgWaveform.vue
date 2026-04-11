<script setup lang="ts">
/**
 * 实时 PCG 波形 Canvas 组件 + 音频播放
 */
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { Volume2, VolumeX, Stethoscope } from 'lucide-vue-next'
import { useScrollingCanvas } from '@/composables/useScrollingCanvas'
import { useAudioPlayback } from '@/composables/useAudioPlayback'
import { useVirtualHumanStore } from '@/store/virtualHuman'
import { AUSCULTATION_AREAS } from '@/composables/useAuscultation'
import type { SignalChunk } from '@/store/virtualHuman'

const store = useVirtualHumanStore()
const canvasRef = ref<HTMLCanvasElement | null>(null)

const { appendSamples, start: startCanvas, stop: stopCanvas } = useScrollingCanvas({
  canvasRef,
  sampleRate: 4000,
  displaySeconds: 5,
  lineColor: '#f59e0b',
  label: 'PCG',
  playbackDelayMs: 180,
})

const auscultationConfig = computed(() => {
  if (!store.auscultationMode) return null
  return AUSCULTATION_AREAS[store.auscultationArea]
})

const noiseReduction = computed(() => store.noiseReduction)

const {
  isPlaying,
  volume,
  feedChunk,
  start: startAudio,
  stop: stopAudio,
} = useAudioPlayback({
  noiseReduction,
  auscultationConfig,
})

function onPcgData(chunk: SignalChunk) {
  appendSamples(chunk)
  feedChunk(chunk)
}

// P1-PCG: Switch between primary and position-specific PCG channels
let currentPositionCb: string | null = null

watch(
  [() => store.auscultationMode, () => store.auscultationArea],
  ([ausMode, pos], [prevMode, prevPos]) => {
    // Unregister previous position callback if any
    if (currentPositionCb) {
      store.unregisterPcgPositionCallback(currentPositionCb, onPcgData)
      currentPositionCb = null
    }

    if (ausMode && pos) {
      // Auscultation active: use position-specific channel
      // Only unregister from pcgCallbacks if we were previously in normal mode
      if (!prevMode) {
        store.unregisterPcgCallback(onPcgData)
      }
      store.registerPcgPositionCallback(pos, onPcgData)
      currentPositionCb = pos
    } else {
      // Normal mode: use primary channel
      // Only register if we were previously in auscultation mode (to avoid double registration)
      if (prevMode) {
        store.registerPcgCallback(onPcgData)
      }
    }
  },
  { immediate: true },
)

async function toggleAudio() {
  if (isPlaying.value) {
    stopAudio()
  } else {
    await startAudio()
  }
}

onMounted(() => {
  // Only register to primary callback if not in auscultation mode
  // (watcher with immediate: true handles auscultation mode)
  if (!store.auscultationMode) {
    store.registerPcgCallback(onPcgData)
  }
  startCanvas()
})

onUnmounted(() => {
  if (currentPositionCb) {
    store.unregisterPcgPositionCallback(currentPositionCb, onPcgData)
  }
  store.unregisterPcgCallback(onPcgData)
  stopCanvas()
  stopAudio()
})
</script>

<template>
  <div class="relative w-full h-full min-h-[160px] rounded-lg overflow-hidden border border-gray-700">
    <canvas ref="canvasRef" class="w-full h-full block" />

    <div class="absolute top-2 right-2 flex items-center gap-2 bg-gray-900/80 backdrop-blur-sm rounded-md px-2 py-1">
      <div
        v-if="store.auscultationMode"
        class="flex items-center gap-1 text-[10px] text-emerald-400 border-r border-gray-600 pr-2"
      >
        <Stethoscope :size="11" />
        <span>{{ AUSCULTATION_AREAS[store.auscultationArea].label }}</span>
      </div>

      <span
        v-if="store.noiseReduction && !store.auscultationMode"
        class="text-[10px] text-emerald-400 border-r border-gray-600 pr-2"
        title="降噪已开启"
      >
        NR
      </span>

      <button
        class="text-gray-300 hover:text-white transition-colors p-0.5"
        :title="isPlaying ? '静音' : '播放心音'"
        @click="toggleAudio"
      >
        <Volume2 v-if="isPlaying" :size="16" />
        <VolumeX v-else :size="16" class="text-gray-500" />
      </button>

      <input
        v-if="isPlaying"
        v-model.number="volume"
        type="range"
        min="0"
        max="1"
        step="0.05"
        class="w-16 h-1 accent-amber-500 cursor-pointer"
        title="音量"
      />
    </div>
  </div>
</template>

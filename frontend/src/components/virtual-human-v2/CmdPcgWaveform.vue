<script setup lang="ts">
/**
 * CmdPcgWaveform — PCG Canvas + 音频控制 (复用 useScrollingCanvas + useAudioPlayback)
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
  lineColor: '#FF9500',
  backgroundColor: '#060608',
  gridColor: 'rgba(255,255,255,0.03)',
  label: 'PCG',
  playbackDelayMs: 180,
})

const auscultationConfig = computed(() =>
  store.auscultationMode ? AUSCULTATION_AREAS[store.auscultationArea] : null
)
const noiseReduction = computed(() => store.noiseReduction)

const { isPlaying, volume, feedChunk, start: startAudio, stop: stopAudio } = useAudioPlayback({
  noiseReduction,
  auscultationConfig,
})

function onPcgData(chunk: SignalChunk) {
  appendSamples(chunk)
  feedChunk(chunk)
}

let currentPositionCb: string | null = null

watch(
  [() => store.auscultationMode, () => store.auscultationArea],
  ([ausMode, pos], [prevMode]) => {
    if (currentPositionCb) {
      store.unregisterPcgPositionCallback(currentPositionCb, onPcgData)
      currentPositionCb = null
    }
    if (ausMode && pos) {
      if (!prevMode) store.unregisterPcgCallback(onPcgData)
      store.registerPcgPositionCallback(pos, onPcgData)
      currentPositionCb = pos
    } else {
      if (prevMode) store.registerPcgCallback(onPcgData)
    }
  },
  { immediate: true },
)

async function toggleAudio() {
  if (isPlaying.value) stopAudio()
  else await startAudio()
}

onMounted(() => {
  if (!store.auscultationMode) store.registerPcgCallback(onPcgData)
  startCanvas()
})

onUnmounted(() => {
  if (currentPositionCb) store.unregisterPcgPositionCallback(currentPositionCb, onPcgData)
  store.unregisterPcgCallback(onPcgData)
  stopCanvas()
  stopAudio()
})
</script>

<template>
  <div class="relative w-full h-full rounded-xl overflow-hidden border border-white/[0.04]">
    <canvas ref="canvasRef" class="w-full h-full block" />
    <div class="absolute top-2 right-2 flex items-center gap-2 bg-black/60 backdrop-blur-sm rounded-lg px-2 py-1">
      <div v-if="store.auscultationMode"
           class="flex items-center gap-1 text-[10px] text-[#34C759] border-r border-white/10 pr-2">
        <Stethoscope :size="11" />
        <span>{{ AUSCULTATION_AREAS[store.auscultationArea].label }}</span>
      </div>
      <span v-if="store.noiseReduction && !store.auscultationMode"
            class="text-[10px] text-[#34C759] border-r border-white/10 pr-2">NR</span>
      <button class="text-white/50 hover:text-white transition-colors p-0.5"
              :title="isPlaying ? '静音' : '播放心音'" @click="toggleAudio">
        <Volume2 v-if="isPlaying" :size="15" />
        <VolumeX v-else :size="15" class="text-white/30" />
      </button>
      <input v-if="isPlaying" v-model.number="volume" type="range"
             min="0" max="1" step="0.05"
             class="w-14 h-1 accent-[#FF9500] cursor-pointer" />
    </div>
  </div>
</template>

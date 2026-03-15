<template>
  <div class="waveform-strip" :style="{ borderLeftColor: channel.color }">
    <div class="strip-label" :style="{ color: channel.color }">{{ channel.label }}</div>
    <canvas ref="canvasRef" class="strip-canvas" :width="canvasWidth" :height="canvasHeight" />
    <div class="strip-gain text-xs text-white/40">×{{ channel.gain.toFixed(1) }}</div>
  </div>
</template>

<script setup lang="ts">
import { ref, toRef, onMounted } from 'vue'
import { useWaveformRenderer } from '@/composables/useWaveformRenderer'
import type { WaveformChannel } from '@/store/waveform'

const props = defineProps<{ channel: WaveformChannel }>()

const canvasRef = ref<HTMLCanvasElement | null>(null)
const canvasWidth = ref(800)
const canvasHeight = ref(120)

const channelRef = toRef(props, 'channel')
useWaveformRenderer(canvasRef, channelRef)

onMounted(() => {
  // Auto-size canvas to container
  const el = canvasRef.value?.parentElement
  if (el) {
    canvasWidth.value = el.clientWidth - 80
    canvasHeight.value = Math.max(80, el.clientHeight - 10)
  }
})
</script>

<style scoped>
.waveform-strip {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.25rem 0.5rem;
  border-left: 3px solid;
  backdrop-filter: blur(10px);
  background: rgba(255, 255, 255, 0.03);
  border-radius: 8px;
  min-height: 100px;
}

.strip-label {
  writing-mode: vertical-rl;
  text-orientation: mixed;
  font-size: 0.75rem;
  font-weight: 600;
  min-width: 1.5rem;
  text-align: center;
}

.strip-canvas {
  flex: 1;
  border-radius: 4px;
}

.strip-gain {
  min-width: 2rem;
  text-align: center;
}
</style>

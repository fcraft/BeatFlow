<template>
  <div class="waveform-zone">
    <WaveformStrip
      v-for="channel in waveformStore.channels"
      :key="channel.id"
      :channel="channel"
    />
  </div>
</template>

<script setup lang="ts">
import { useWaveformStore } from '@/store/waveform'
import WaveformStrip from './WaveformStrip.vue'

const waveformStore = useWaveformStore()
</script>

<style scoped>
.waveform-zone {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  height: 100%;
}
</style>

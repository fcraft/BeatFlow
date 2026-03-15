<template>
  <div class="monitor-shell">
    <slot name="topbar" />
    <div class="waveform-zone glass-panel">
      <slot name="waveforms">
        <WaveformZone />
      </slot>
    </div>
    <slot name="bottom" />
  </div>
</template>

<script setup lang="ts">
import WaveformZone from './WaveformZone.vue'
</script>

<style scoped>
.monitor-shell {
  height: 100vh;
  background: linear-gradient(135deg, #0f0f1a, #1a1025, #0d1520);
  color: white;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  padding: 0.5rem;
  overflow: hidden;
}

.waveform-zone {
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.glass-panel {
  backdrop-filter: blur(20px);
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 16px;
  padding: 0.75rem;
}
</style>

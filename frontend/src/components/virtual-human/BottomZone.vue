<template>
  <div class="bottom-zone">
    <div class="glass-panel flex-1 min-w-0 overflow-auto">
      <VitalsDashboard />
    </div>
    <div class="glass-panel flex-[2] min-w-0 overflow-auto">
      <ControlPanel />
    </div>
  </div>
</template>

<script setup lang="ts">
import VitalsDashboard from './VitalsDashboard.vue'
import ControlPanel from './ControlPanel.vue'
</script>

<style scoped>
.bottom-zone {
  display: flex;
  gap: 0.75rem;
  padding: 0.75rem;
  min-height: 0;
}

.glass-panel {
  backdrop-filter: blur(20px);
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 16px;
  padding: 1rem;
}
</style>

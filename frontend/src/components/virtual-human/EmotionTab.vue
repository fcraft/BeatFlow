<script setup lang="ts">
import { ref, computed } from 'vue'
import { useVirtualHumanStore } from '@/store/virtualHuman'

const store = useVirtualHumanStore()
const lastClicked = ref('')
const isActive = computed(() => store.vitals.emotional_arousal > 0.15)

const emotions = [
  { cmd: 'startle',     label: '惊吓',   icon: '😱', desc: 'HR 瞬间 +40' },
  { cmd: 'anxiety',     label: '焦虑',   icon: '😰', desc: 'HR ~105' },
  { cmd: 'stress',      label: '压力',   icon: '😤', desc: 'HR ~110' },
  { cmd: 'fatigue',     label: '疲劳',   icon: '😩', desc: 'HR ~85' },
  { cmd: 'relaxation',  label: '放松',   icon: '😌', desc: 'HR ~62' },
]

function apply(cmd: string) {
  lastClicked.value = cmd
  store.sendCommand(cmd)
}
</script>

<template>
  <div class="glass-tab-root">
    <div class="glass-grid">
      <button
        v-for="em in emotions"
        :key="em.cmd"
        :class="['glass-card-btn', { 'glass-card-btn--active': isActive && lastClicked === em.cmd }]"
        @click="apply(em.cmd)"
      >
        <span class="glass-card-icon">{{ em.icon }}</span>
        <span class="glass-card-label">{{ em.label }}</span>
        <span class="glass-card-desc">{{ em.desc }}</span>
      </button>
    </div>
  </div>
</template>

<style scoped>
@import './glass-tab-shared.css';
</style>

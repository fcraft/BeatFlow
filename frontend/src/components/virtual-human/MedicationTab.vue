<script setup lang="ts">
/**
 * 药物与电解质 Tab — 控制药物给药和电解质水平
 */
import { ref, computed } from 'vue'
import { useVirtualHumanStore } from '@/store/virtualHuman'

const store = useVirtualHumanStore()
const dose = ref(0.5)

/** 从 vitals 派生 K⁺/Ca²⁺ 初始值 */
const potassium = ref(4.0)
const calcium = ref(9.5)

const medications = [
  { cmd: 'beta_blocker', label: 'β-阻滞剂', desc: 'HR↓ PR↑', levelKey: 'beta_blocker_level' as const },
  { cmd: 'amiodarone', label: '胺碘酮', desc: 'QT↑↑', levelKey: 'amiodarone_level' as const },
  { cmd: 'digoxin', label: '地高辛', desc: 'PR↑ ST↓', levelKey: 'digoxin_level' as const },
  { cmd: 'atropine', label: '阿托品', desc: 'HR↑ PR↓', levelKey: 'atropine_level' as const },
]

/** 活跃药物集合（level > 0.05） */
const activeMeds = computed(() => {
  const set = new Set<string>()
  for (const m of medications) {
    if ((store.vitals[m.levelKey] as number) > 0.05) {
      set.add(m.cmd)
    }
  }
  return set
})

function applyMed(cmd: string) {
  store.sendCommand(cmd, { dose: dose.value })
}

function onPotassiumChange() {
  if (potassium.value > 5.0) {
    store.sendCommand('hyperkalemia', { level: potassium.value })
  } else if (potassium.value < 3.5) {
    store.sendCommand('hypokalemia', { level: potassium.value })
  }
}

function onCalciumChange() {
  if (calcium.value > 10.5) {
    store.sendCommand('hypercalcemia', { level: calcium.value })
  } else if (calcium.value < 8.5) {
    store.sendCommand('hypocalcemia', { level: calcium.value })
  }
}
</script>

<template>
  <div class="glass-tab-root">
    <!-- 药物给药 -->
    <div>
      <span class="glass-section-title" style="margin-bottom: 8px; display: block;">药物给药</span>
      <div class="glass-grid glass-grid--4col">
        <button
          v-for="m in medications"
          :key="m.cmd"
          :class="['glass-card-btn', activeMeds.has(m.cmd) ? 'glass-card-btn--purple' : '']"
          @click="applyMed(m.cmd)"
        >
          <span class="glass-card-label">{{ m.label }}</span>
          <span class="glass-card-desc">{{ m.desc }}</span>
          <span v-if="activeMeds.has(m.cmd)" class="glass-card-value">
            {{ Math.round((store.vitals[m.levelKey] as number) * 100) }}%
          </span>
        </button>
      </div>
    </div>

    <!-- 剂量 -->
    <div class="glass-section">
      <div class="glass-slider-group">
        <div class="glass-slider-header">
          <span>药物剂量</span>
          <span class="glass-slider-value">{{ (dose * 100).toFixed(0) }}%</span>
        </div>
        <input
          v-model.number="dose"
          type="range" min="0.1" max="1.0" step="0.1"
          class="glass-range glass-range--indigo"
        />
        <div class="glass-slider-labels">
          <span>低剂量</span><span>中</span><span>高剂量</span>
        </div>
      </div>
    </div>

    <!-- 电解质 -->
    <hr class="glass-divider" />
    <div class="glass-section">
      <span class="glass-section-title">电解质水平</span>

      <!-- K+ -->
      <div class="glass-slider-group">
        <div class="glass-slider-header">
          <span>K<sup>+</sup></span>
          <span class="glass-slider-value">{{ potassium.toFixed(1) }} mEq/L</span>
        </div>
        <div class="relative">
          <input
            v-model.number="potassium"
            type="range" min="2.5" max="7.0" step="0.1"
            class="glass-range glass-range--green"
            @change="onPotassiumChange"
          />
          <div
            class="glass-range-indicator"
            :style="{
              left: ((3.5 - 2.5) / (7.0 - 2.5) * 100) + '%',
              width: ((5.0 - 3.5) / (7.0 - 2.5) * 100) + '%',
            }"
          />
        </div>
        <div class="glass-slider-labels">
          <span>2.5 低</span>
          <span style="color: #34C759;">3.5-5.0 正常</span>
          <span>7.0 高</span>
        </div>
      </div>

      <!-- Ca2+ -->
      <div class="glass-slider-group">
        <div class="glass-slider-header">
          <span>Ca<sup>2+</sup></span>
          <span class="glass-slider-value">{{ calcium.toFixed(1) }} mg/dL</span>
        </div>
        <div class="relative">
          <input
            v-model.number="calcium"
            type="range" min="6.0" max="14.0" step="0.1"
            class="glass-range glass-range--green"
            @change="onCalciumChange"
          />
          <div
            class="glass-range-indicator"
            :style="{
              left: ((8.5 - 6.0) / (14.0 - 6.0) * 100) + '%',
              width: ((10.5 - 8.5) / (14.0 - 6.0) * 100) + '%',
            }"
          />
        </div>
        <div class="glass-slider-labels">
          <span>6.0 低</span>
          <span style="color: #34C759;">8.5-10.5 正常</span>
          <span>14.0 高</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
@import './glass-tab-shared.css';
.relative { position: relative; }
</style>

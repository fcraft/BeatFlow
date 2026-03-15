<script setup lang="ts">
/**
 * 设置 Tab
 */
import { ref } from 'vue'
import { useVirtualHumanStore } from '@/store/virtualHuman'

const store = useVirtualHumanStore()

const damageLevel = ref(0)
const targetHr = ref(72)
const preload = ref(1.0)
const contractility = ref(1.0)
const tpr = ref(1.0)
const fio2 = ref(0.21)
const magnesium = ref(2.0)

function setDamage() { store.sendCommand('set_damage_level', { level: damageLevel.value }) }
function setHr() { store.sendCommand('set_heart_rate', { value: targetHr.value }) }
function setPreload() { store.sendCommand('set_preload', { level: preload.value }) }
function setContractility() { store.sendCommand('set_contractility', { level: contractility.value }) }
function setTpr() { store.sendCommand('set_tpr', { level: tpr.value }) }
function setFio2() { store.sendCommand('set_fio2', { level: fio2.value }) }
function setMagnesium() { store.sendCommand('set_magnesium', { level: magnesium.value }) }

function resetAll() {
  store.sendCommand('reset')
  damageLevel.value = 0
  targetHr.value = 72
  preload.value = 1.0
  contractility.value = 1.0
  tpr.value = 1.0
  fio2.value = 0.21
  magnesium.value = 2.0
}
</script>

<template>
  <div class="glass-tab-root">
    <!-- 损伤程度 -->
    <div class="glass-section">
      <div class="glass-slider-group">
        <div class="glass-slider-header">
          <span>心脏损伤程度</span>
          <span class="glass-slider-value">{{ (damageLevel * 100).toFixed(0) }}%</span>
        </div>
        <input v-model.number="damageLevel" type="range" min="0" max="1" step="0.05" class="glass-range glass-range--rose" @change="setDamage" />
        <p class="glass-hint">影响 ST 段压低、T 波改变、S3/S4 奔马律</p>
      </div>
    </div>

    <!-- 目标心率 -->
    <div class="glass-section">
      <div class="glass-slider-group">
        <div class="glass-slider-header">
          <span>目标心率</span>
          <span class="glass-slider-value">{{ targetHr }} bpm</span>
        </div>
        <input v-model.number="targetHr" type="range" min="30" max="250" step="1" class="glass-range glass-range--blue" @change="setHr" />
      </div>
    </div>

    <!-- 预负荷 -->
    <div class="glass-section">
      <div class="glass-slider-group">
        <div class="glass-slider-header">
          <span>预负荷 (Preload)</span>
          <span class="glass-slider-value">{{ preload.toFixed(2) }}</span>
        </div>
        <input v-model.number="preload" type="range" min="0.5" max="2.0" step="0.05" class="glass-range glass-range--teal" @change="setPreload" />
        <p class="glass-hint">影响心室舒张末容积 (EDV)，Frank-Starling 机制</p>
      </div>
    </div>

    <!-- 收缩力 -->
    <div class="glass-section">
      <div class="glass-slider-group">
        <div class="glass-slider-header">
          <span>收缩力 (Contractility)</span>
          <span class="glass-slider-value">{{ contractility.toFixed(2) }}</span>
        </div>
        <input v-model.number="contractility" type="range" min="0.2" max="2.5" step="0.05" class="glass-range glass-range--indigo" @change="setContractility" />
        <p class="glass-hint">影响心室最大弹性 E_max，正性/负性肌力效应</p>
      </div>
    </div>

    <!-- TPR -->
    <div class="glass-section">
      <div class="glass-slider-group">
        <div class="glass-slider-header">
          <span>TPR (总外周阻力)</span>
          <span class="glass-slider-value">{{ tpr.toFixed(2) }}</span>
        </div>
        <input v-model.number="tpr" type="range" min="0.3" max="3.0" step="0.05" class="glass-range glass-range--orange" @change="setTpr" />
        <p class="glass-hint">影响后负荷与舒张压</p>
      </div>
    </div>

    <!-- FiO2 -->
    <div class="glass-section">
      <div class="glass-slider-group">
        <div class="glass-slider-header">
          <span>FiO₂ (吸入氧浓度)</span>
          <span class="glass-slider-value">{{ (fio2 * 100).toFixed(0) }}%</span>
        </div>
        <input v-model.number="fio2" type="range" min="0.21" max="1.0" step="0.01" class="glass-range glass-range--cyan" @change="setFio2" />
        <p class="glass-hint">21% = 室内空气，100% = 纯氧</p>
      </div>
    </div>

    <!-- Mg²⁺ -->
    <div class="glass-section">
      <div class="glass-slider-group">
        <div class="glass-slider-header">
          <span>Mg²⁺ (血清镁)</span>
          <span class="glass-slider-value">{{ magnesium.toFixed(1) }} mg/dL</span>
        </div>
        <input v-model.number="magnesium" type="range" min="0.5" max="4.0" step="0.1" class="glass-range glass-range--emerald" @change="setMagnesium" />
        <p class="glass-hint">正常 1.7-2.2，低镁→QT延长</p>
      </div>
    </div>

    <!-- 重置 -->
    <button class="glass-pill-btn glass-pill-btn--ghost w-full" @click="resetAll">
      重置为健康基线
    </button>
  </div>
</template>

<style scoped>
@import './glass-tab-shared.css';
.w-full { width: 100%; }
</style>

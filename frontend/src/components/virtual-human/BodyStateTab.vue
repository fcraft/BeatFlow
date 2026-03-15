<script setup lang="ts">
/**
 * 体内状态 Tab — 控制咖啡因、饮酒、发热、熬夜、脱水等。
 * 选中时显示剂量/程度滑块。活跃状态从 vitals 派生高亮。
 */
import { ref, computed } from 'vue'
import { useVirtualHumanStore } from '@/store/virtualHuman'

const store = useVirtualHumanStore()
const active = ref('')

const states = [
  { cmd: 'caffeine',          label: '咖啡因', icon: '☕', desc: '心率↑ 交感↑', paramKey: 'dose',        min: 0.1, max: 1.0, step: 0.1, default: 0.5, vitalKey: 'caffeine_level' as const, threshold: 0.05 },
  { cmd: 'alcohol',           label: '饮酒',   icon: '🍺', desc: '血压↓ 心律↑', paramKey: 'dose',        min: 0.1, max: 1.0, step: 0.1, default: 0.4, vitalKey: 'alcohol_level' as const, threshold: 0.05 },
  { cmd: 'fever',             label: '发热',   icon: '🤒', desc: 'HR +10/°C',  paramKey: 'temperature', min: 37.5, max: 41.0, step: 0.5, default: 38.5, vitalKey: 'temperature' as const, threshold: 37.5 },
  { cmd: 'sleep_deprivation', label: '熬夜',   icon: '💤', desc: 'HRV↓ 早搏↑', paramKey: 'severity',    min: 0.1, max: 1.0, step: 0.1, default: 0.6, vitalKey: 'sleep_debt' as const, threshold: 0.1 },
  { cmd: 'dehydration',       label: '脱水',   icon: '💧', desc: 'HR↑ BP↓',    paramKey: 'severity',    min: 0.1, max: 1.0, step: 0.1, default: 0.5, vitalKey: 'dehydration_level' as const, threshold: 0.05 },
]

/** 活跃状态集合（从 vitals 派生） */
const activeStates = computed(() => {
  const set = new Set<string>()
  for (const s of states) {
    if ((store.vitals[s.vitalKey] as number) > s.threshold) {
      set.add(s.cmd)
    }
  }
  return set
})

const recoveries = [
  { cmd: 'hydrate', label: '补水',   icon: '💊', desc: '脱水归零' },
  { cmd: 'sleep',   label: '睡觉',   icon: '😴', desc: '疲劳+缺觉归零' },
]

const paramValue = ref(0.5)

function selectState(cmd: string, defaultVal: number) {
  active.value = cmd
  paramValue.value = defaultVal
}

function apply() {
  const item = states.find(s => s.cmd === active.value)
  if (item) {
    store.sendCommand(item.cmd, { [item.paramKey]: paramValue.value })
  }
}

function applyRecovery(cmd: string) {
  active.value = ''
  store.sendCommand(cmd)
}
</script>

<template>
  <div class="glass-tab-root">
    <!-- 状态按钮 -->
    <div class="glass-grid glass-grid--5col">
      <button
        v-for="s in states"
        :key="s.cmd"
        :class="[
          'glass-card-btn',
          active === s.cmd
            ? 'glass-card-btn--active'
            : activeStates.has(s.cmd)
              ? 'glass-card-btn--teal'
              : ''
        ]"
        @click="selectState(s.cmd, s.default)"
      >
        <span class="glass-card-icon" style="font-size: 18px;">{{ s.icon }}</span>
        <span class="glass-card-label">{{ s.label }}</span>
        <span class="glass-card-desc">{{ s.desc }}</span>
      </button>
    </div>

    <!-- 剂量/程度滑块 -->
    <div v-if="active" class="glass-section">
      <div class="glass-slider-group">
        <div class="glass-slider-header">
          <span>
            {{ states.find(s => s.cmd === active)?.label }} —
            {{ states.find(s => s.cmd === active)?.paramKey === 'temperature'
              ? `${paramValue.toFixed(1)}°C`
              : `${(paramValue * 100).toFixed(0)}%` }}
          </span>
        </div>
        <input
          v-model.number="paramValue"
          type="range"
          :min="states.find(s => s.cmd === active)?.min ?? 0"
          :max="states.find(s => s.cmd === active)?.max ?? 1"
          :step="states.find(s => s.cmd === active)?.step ?? 0.1"
          class="glass-range glass-range--orange"
        />
      </div>
      <button class="glass-pill-btn glass-pill-btn--primary w-full" @click="apply">
        应用
      </button>
    </div>

    <!-- 恢复 -->
    <hr class="glass-divider" />
    <div class="flex gap-2">
      <button
        v-for="r in recoveries"
        :key="r.cmd"
        class="glass-pill-btn glass-pill-btn--green flex-1"
        @click="applyRecovery(r.cmd)"
      >
        {{ r.icon }} {{ r.label }}
      </button>
    </div>
  </div>
</template>

<style scoped>
@import './glass-tab-shared.css';
.w-full { width: 100%; }
</style>

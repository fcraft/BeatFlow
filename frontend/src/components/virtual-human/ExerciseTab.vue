<script setup lang="ts">
import { ref, computed } from 'vue'
import { useVirtualHumanStore } from '@/store/virtualHuman'

const store = useVirtualHumanStore()

/**
 * 高亮逻辑：「即时反馈 + 真实值持久」
 *
 * - lastClicked: 点击时立即设置，提供即时视觉反馈
 * - vitalsActive: 从 exercise_intensity 派生的真实活跃状态（切 Tab 回来仍在）
 * - active: 优先用 vitalsActive（当 vitals 已经变化时），否则用 lastClicked（命令刚发出、vitals 还在过渡中）
 */
const lastClicked = ref('')

const vitalsActive = computed(() => {
  const intensity = store.vitals.exercise_intensity
  if (intensity >= 0.7) return 'run'
  if (intensity >= 0.4) return 'jog'
  if (intensity >= 0.2) return 'walk'
  if (intensity < 0.05) return 'rest'
  return '' // 过渡中的模糊区间，不覆盖 lastClicked
})

/** 最终高亮状态 */
const active = computed(() => {
  // 如果 vitals 有明确的活跃状态，使用它（持久）
  if (vitalsActive.value) return vitalsActive.value
  // 否则用 lastClicked（即时反馈）
  return lastClicked.value
})

const exercises = [
  { cmd: 'rest',          label: '休息',   icon: '😴', desc: '恢复静息状态' },
  { cmd: 'walk',          label: '步行',   icon: '🚶', desc: 'HR ~95' },
  { cmd: 'jog',           label: '慢跑',   icon: '🏃', desc: 'HR ~130' },
  { cmd: 'run',           label: '跑步',   icon: '💨', desc: 'HR ~165' },
  { cmd: 'climb_stairs',  label: '爬楼',   icon: '🏔', desc: 'HR ~140' },
  { cmd: 'squat',         label: '深蹲',   icon: '🏋', desc: 'HR ~120' },
]

function apply(cmd: string) {
  lastClicked.value = cmd
  store.sendCommand(cmd)
}
</script>

<template>
  <div class="glass-tab-root">
    <!-- 运动模式选择 -->
    <div class="glass-grid">
      <button
        v-for="ex in exercises"
        :key="ex.cmd"
        :class="['glass-card-btn', { 'glass-card-btn--active': active === ex.cmd }]"
        @click="apply(ex.cmd)"
      >
        <span class="glass-card-icon">{{ ex.icon }}</span>
        <span class="glass-card-label">{{ ex.label }}</span>
        <span class="glass-card-desc">{{ ex.desc }}</span>
      </button>
    </div>

    <!-- 体能 & 年龄滑块 -->
    <div class="glass-section">
      <div class="glass-slider-group">
        <div class="glass-slider-header">
          <span>体能水平</span>
          <span class="glass-slider-value">{{ (store.vitals.fitness_level ?? 0.5).toFixed(1) }}</span>
        </div>
        <input
          type="range" min="0" max="1" step="0.05"
          :value="store.vitals.fitness_level ?? 0.5"
          class="glass-range glass-range--blue"
          @input="store.sendCommand('set_fitness', { level: +($event.target as HTMLInputElement).value })"
        />
        <div class="glass-slider-labels">
          <span>久坐</span><span>运动员</span>
        </div>
      </div>
      <div class="glass-slider-group">
        <div class="glass-slider-header">
          <span>年龄</span>
          <span class="glass-slider-value">{{ store.vitals.age ?? 30 }} 岁</span>
        </div>
        <input
          type="range" min="15" max="85" step="1"
          :value="store.vitals.age ?? 30"
          class="glass-range glass-range--blue"
          @input="store.sendCommand('set_age', { value: +($event.target as HTMLInputElement).value })"
        />
        <div class="glass-slider-labels">
          <span>15</span><span>85</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
@import './glass-tab-shared.css';
</style>

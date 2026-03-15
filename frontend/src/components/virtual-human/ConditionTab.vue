<script setup lang="ts">
import { ref, computed } from 'vue'
import { useVirtualHumanStore } from '@/store/virtualHuman'

const store = useVirtualHumanStore()

/**
 * 高亮逻辑：「即时反馈 + 真实值持久」
 *
 * - lastClicked: 点击时立即设置
 * - vitalsActive: 从 rhythm / av_block / murmur / damage 派生
 * - active: vitalsActive 有明确非 normal 状态时用它，否则用 lastClicked
 */
const lastClicked = ref('')

const vitalsActive = computed(() => {
  const rhythm = store.vitals.rhythm
  const avBlock = store.vitals.conduction.av_block_degree

  if (rhythm === 'af') return 'condition_af'
  if (rhythm === 'pvc') return 'condition_pvc'
  if (rhythm === 'svt') return 'condition_svt'
  if (rhythm === 'vt') return 'condition_vt'
  if (rhythm === 'vf') return 'condition_vf'
  if (rhythm === 'asystole') return 'condition_asystole'
  if (avBlock >= 3) return 'condition_av_block_3'
  if (avBlock >= 2) return 'condition_av_block_2'
  if (avBlock >= 1) return 'condition_av_block_1'
  if (store.vitals.murmur_severity > 0) return 'condition_valve_disease'
  if (store.vitals.damage_level > 0.3) return 'condition_heart_failure'
  return '' // normal — 不强制覆盖 lastClicked
})

/** 最终高亮状态 */
const active = computed(() => {
  // vitals 有明确异常状态时 → 使用它（持久、准确）
  if (vitalsActive.value) return vitalsActive.value
  // vitals 为 normal 但用户刚点了某个按钮 → 显示 lastClicked（即时反馈）
  if (lastClicked.value) return lastClicked.value
  return 'condition_normal'
})

/** severity 从 vitals.damage_level 派生（只读显示） */
const severity = computed(() => store.vitals.damage_level || 0)

/** pvcPattern 从 vitals 派生 */
const pvcPattern = computed(() => store.vitals.pvc_pattern || 'isolated')

const conditions = [
  { cmd: 'condition_normal',         label: '正常' },
  { cmd: 'condition_tachycardia',    label: '心动过速' },
  { cmd: 'condition_bradycardia',    label: '心动过缓' },
  { cmd: 'condition_pvc',            label: '室性早搏' },
  { cmd: 'condition_af',             label: '房颤' },
  { cmd: 'condition_valve_disease',  label: '瓣膜病' },
  { cmd: 'condition_heart_failure',  label: '心力衰竭' },
  { cmd: 'condition_svt',            label: 'SVT' },
  { cmd: 'condition_vt',             label: 'VT' },
  { cmd: 'condition_vf',             label: 'VF' },
  { cmd: 'condition_asystole',       label: '心搏停止' },
  { cmd: 'condition_av_block_1',     label: 'AVB I°' },
  { cmd: 'condition_av_block_2',     label: 'AVB II°' },
  { cmd: 'condition_av_block_3',     label: 'AVB III°' },
  { cmd: 'condition_ischemia',       label: '心肌缺血' },
  { cmd: 'condition_pulm_hypertension', label: '肺高压' },
  { cmd: 'condition_rv_failure',     label: '右心衰' },
]

const pvcPatterns = [
  { key: 'isolated',  label: '孤立' },
  { key: 'bigeminy',  label: '二联律' },
  { key: 'trigeminy', label: '三联律' },
  { key: 'couplets',  label: '成对' },
]

const showPvcOptions = computed(() => active.value === 'condition_pvc')

/** 本地 severity 滑块值（用于发送命令） */
const severitySlider = ref(0.5)

/** 心律失常基质滑块 */
const afSubstrate = ref(0)
const svtSubstrate = ref(0)
const vtSubstrate = ref(0)

/** 当前 episode 信息 */
const episodeInfo = computed(() => {
  const ep = store.vitals.arrhythmia_episode_type
  const beats = store.vitals.arrhythmia_episode_beats
  if (!ep || beats <= 0) return null
  const labels: Record<string, string> = {
    paf: 'PAF 发作中', psvt: 'PSVT 发作中', nsvt: 'NSVT 发作中',
    vf: 'VF 室颤', asystole: '心搏停止',
  }
  return { label: labels[ep] || ep, beats }
})

function apply(cmd: string) {
  lastClicked.value = cmd
  store.sendCommand(cmd, { severity: severitySlider.value })
}

function onSeverityChange() {
  if (active.value && active.value !== 'condition_normal') {
    store.sendCommand(active.value, { severity: severitySlider.value })
  }
}

function setPvcPattern(pattern: string) {
  store.sendCommand('set_pvc_pattern', { pattern })
}

function onAfSubstrateChange() { store.sendCommand('set_af_substrate', { level: afSubstrate.value }) }
function onSvtSubstrateChange() { store.sendCommand('set_svt_substrate', { level: svtSubstrate.value }) }
function onVtSubstrateChange() { store.sendCommand('set_vt_substrate', { level: vtSubstrate.value }) }

const showEmergencyPanel = computed(() => {
  const r = store.vitals.rhythm
  return ['vf', 'vt', 'svt', 'af'].includes(r)
})

const canDefibrillate = computed(() => ['vf', 'vt'].includes(store.vitals.rhythm))
const canCardiovert = computed(() => ['af', 'svt', 'vt'].includes(store.vitals.rhythm))

const hrOverrideActive = computed(() => store.vitals.hr_override_active)
const hrOverrideValue = computed(() => store.vitals.hr_override_value)
function cancelHrOverride() { store.sendCommand('cancel_hr_override') }

function doDefibrillate() { store.sendCommand('defibrillate', {}) }
function doCardiovert() { store.sendCommand('cardiovert', {}) }
</script>

<template>
  <div class="glass-tab-root">
    <!-- 病变选择 -->
    <div class="glass-grid">
      <button
        v-for="c in conditions"
        :key="c.cmd"
        :class="[
          'glass-card-btn',
          active === c.cmd
            ? (c.cmd === 'condition_normal' ? 'glass-card-btn--active' : 'glass-card-btn--danger')
            : ''
        ]"
        @click="apply(c.cmd)"
      >
        <span class="glass-card-label">{{ c.label }}</span>
      </button>
    </div>

    <!-- HR Override 取消 -->
    <div v-if="hrOverrideActive" class="glass-section" style="border-color: rgba(245,158,11,0.2);">
      <div class="flex items-center justify-between">
        <span class="text-xs text-amber-300">HR 锁定: {{ hrOverrideValue }} bpm</span>
        <button class="glass-pill-btn glass-pill-btn--sm" style="background: rgba(245,158,11,0.2); color: #fbbf24; border: 1px solid rgba(245,158,11,0.3);" @click="cancelHrOverride">
          取消锁定
        </button>
      </div>
    </div>

    <!-- PVC 模式 -->
    <div v-if="showPvcOptions" class="glass-section">
      <span class="glass-section-title">PVC 模式</span>
      <div class="flex gap-2">
        <button
          v-for="p in pvcPatterns"
          :key="p.key"
          :class="[
            'glass-pill-btn glass-pill-btn--sm flex-1',
            pvcPattern === p.key ? 'glass-pill-btn--primary' : 'glass-pill-btn--ghost'
          ]"
          @click="setPvcPattern(p.key)"
        >
          {{ p.label }}
        </button>
      </div>
    </div>

    <!-- 严重程度 -->
    <div v-if="active !== 'condition_normal'" class="glass-section">
      <div class="glass-slider-group">
        <div class="glass-slider-header">
          <span>严重程度</span>
          <span class="glass-slider-value">{{ (severitySlider * 100).toFixed(0) }}%</span>
        </div>
        <input
          v-model.number="severitySlider"
          type="range" min="0" max="1" step="0.05"
          class="glass-range glass-range--red"
          @change="onSeverityChange"
        />
        <div class="glass-slider-labels">
          <span>轻微</span><span>中等</span><span>严重</span>
        </div>
      </div>
    </div>

    <!-- Episode 发作 -->
    <div v-if="episodeInfo" class="glass-chip--amber" style="display: flex; align-items: center; justify-content: space-between; padding: 8px 14px; border-radius: 12px; background: rgba(255,149,0,0.1); border: 1px solid rgba(255,149,0,0.25);">
      <span style="font-size: 12px; font-weight: 600; color: #FF9500;">{{ episodeInfo.label }}</span>
      <span style="font-size: 10px; font-family: monospace; color: rgba(255,149,0,0.7);">{{ episodeInfo.beats }} 拍</span>
    </div>

    <!-- 紧急干预 -->
    <div v-if="showEmergencyPanel" class="glass-section" style="border-color: rgba(255,59,48,0.2);">
      <span class="glass-section-title" style="color: #FF3B30;">紧急干预</span>
      <div class="flex gap-2">
        <button
          :disabled="!canDefibrillate"
          :class="['glass-pill-btn flex-1', canDefibrillate ? 'glass-pill-btn--danger' : 'glass-pill-btn--ghost']"
          @click="doDefibrillate"
        >
          ⚡ 除颤
        </button>
        <button
          :disabled="!canCardiovert"
          :class="['glass-pill-btn flex-1', canCardiovert ? 'glass-pill-btn--primary' : 'glass-pill-btn--ghost']"
          style="background: #FF9500; box-shadow: 0 4px 16px rgba(255,149,0,0.3);"
          @click="doCardiovert"
        >
          ⚡ 电复律
        </button>
      </div>
      <p class="glass-hint">除颤仅对 VF/VT 有效，电复律对 AF/SVT/VT 有效</p>
    </div>

    <!-- 心律失常基质 -->
    <div class="glass-section">
      <span class="glass-section-title">心律失常基质</span>
      <div class="glass-slider-group">
        <div class="glass-slider-header">
          <span>AF 基质</span>
          <span class="glass-slider-value">{{ (afSubstrate * 100).toFixed(0) }}%</span>
        </div>
        <input v-model.number="afSubstrate" type="range" min="0" max="1" step="0.05" class="glass-range glass-range--purple" @change="onAfSubstrateChange" />
      </div>
      <div class="glass-slider-group">
        <div class="glass-slider-header">
          <span>SVT 基质</span>
          <span class="glass-slider-value">{{ (svtSubstrate * 100).toFixed(0) }}%</span>
        </div>
        <input v-model.number="svtSubstrate" type="range" min="0" max="1" step="0.05" class="glass-range glass-range--orange" @change="onSvtSubstrateChange" />
      </div>
      <div class="glass-slider-group">
        <div class="glass-slider-header">
          <span>VT 基质</span>
          <span class="glass-slider-value">{{ (vtSubstrate * 100).toFixed(0) }}%</span>
        </div>
        <input v-model.number="vtSubstrate" type="range" min="0" max="1" step="0.05" class="glass-range glass-range--red" @change="onVtSubstrateChange" />
      </div>
      <p class="glass-hint">设置基质后，心律失常可在正常节律下自发触发短阵发作</p>
    </div>
  </div>
</template>

<style scoped>
@import './glass-tab-shared.css';
</style>

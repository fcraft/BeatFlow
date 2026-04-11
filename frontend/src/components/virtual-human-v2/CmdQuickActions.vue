<script setup lang="ts">
/**
 * CmdQuickActions — 桌面端快捷操作栏 + 临床场景预设
 *
 * 功能分区：
 *   1. 快捷命令行（运动/情绪/病变/用药/体内/紧急）— 带状态高亮
 *   2. 临床场景预设卡片 — 一键触发多命令组合
 */
import { computed, ref } from 'vue'
import { useVirtualHumanStore } from '@/store/virtualHuman'
import { useToastStore } from '@/store/toast'

const store = useVirtualHumanStore()
const toast = useToastStore()

const emit = defineEmits<{ (e: 'open-controls'): void }>()

// ══════════════════════════════════════════
// 快捷命令定义
// ══════════════════════════════════════════

const exerciseActions = [
  { cmd: 'rest', label: '休息', icon: '😴' },
  { cmd: 'walk', label: '步行', icon: '🚶' },
  { cmd: 'jog',  label: '慢跑', icon: '🏃' },
  { cmd: 'run',  label: '跑步', icon: '💨' },
]

const emotionActions = [
  { cmd: 'startle',    label: '惊吓', icon: '😱' },
  { cmd: 'anxiety',    label: '焦虑', icon: '😰' },
  { cmd: 'stress',     label: '压力', icon: '😤' },
  { cmd: 'relaxation', label: '放松', icon: '😌' },
]

const conditionActions = [
  { cmd: 'condition_normal', label: '正常', icon: '💚' },
  { cmd: 'condition_af',     label: '房颤', icon: '💔' },
  { cmd: 'condition_pvc',    label: 'PVC',  icon: '⚡' },
  { cmd: 'condition_svt',    label: 'SVT',  icon: '💛' },
  { cmd: 'condition_vf',     label: 'VF',   icon: '🔴' },
]

const medicationActions = [
  { cmd: 'beta_blocker', label: 'β-阻滞', icon: '💊' },
  { cmd: 'atropine',     label: '阿托品', icon: '💉' },
  { cmd: 'amiodarone',   label: '胺碘酮', icon: '🧪' },
]

const bodyActions = [
  { cmd: 'caffeine',    label: '咖啡因', icon: '☕' },
  { cmd: 'fever',       label: '发热',   icon: '🤒' },
  { cmd: 'dehydration', label: '脱水',   icon: '💧' },
]

const emergencyActions = [
  { cmd: 'defibrillate', label: '除颤',   icon: '⚡', danger: true },
  { cmd: 'cardiovert',   label: '电复律', icon: '🔋', danger: true },
  { cmd: 'reset',        label: '重置',   icon: '🔄', danger: false },
]

// ══════════════════════════════════════════
// 状态高亮 computed
// ══════════════════════════════════════════

const activeExercise = computed(() => {
  const i = store.vitals.exercise_intensity
  if (i >= 0.7) return 'run'
  if (i >= 0.4) return 'jog'
  if (i >= 0.2) return 'walk'
  if (i < 0.05) return 'rest'
  return ''
})

const activeEmotion = computed(() => {
  const a = store.vitals.emotional_arousal
  if (a < 0.1) return 'relaxation'
  if (a >= 0.8) return 'startle'
  if (a >= 0.6) return 'stress'
  if (a >= 0.3) return 'anxiety'
  return ''
})

const activeCondition = computed(() => {
  const r = store.vitals.rhythm
  if (r === 'af') return 'condition_af'
  if (r === 'vf') return 'condition_vf'
  if (r === 'vt') return 'condition_vt'
  if (r === 'svt') return 'condition_svt'
  if (store.vitals.conduction.av_block_degree > 0) return ''
  if (r === 'normal' && store.vitals.damage_level < 0.1) return 'condition_normal'
  return ''
})

const activeMeds = computed(() => {
  const set = new Set<string>()
  if (store.vitals.beta_blocker_level > 0.05) set.add('beta_blocker')
  if (store.vitals.atropine_level > 0.05) set.add('atropine')
  if (store.vitals.amiodarone_level > 0.05) set.add('amiodarone')
  return set
})

const activeBody = computed(() => {
  const set = new Set<string>()
  if (store.vitals.caffeine_level > 0.05) set.add('caffeine')
  if (store.vitals.temperature > 37.5) set.add('fever')
  if (store.vitals.dehydration_level > 0.05) set.add('dehydration')
  return set
})

const canDefibrillate = computed(() => ['vf', 'vt'].includes(store.vitals.rhythm))
const canCardiovert = computed(() => ['af', 'svt', 'vt'].includes(store.vitals.rhythm))

// ══════════════════════════════════════════
// 临床场景预设
// ══════════════════════════════════════════

interface Scenario {
  id: string
  label: string
  icon: string
  color: string        // tailwind-compatible hex
  desc: string
  commands: Array<{ cmd: string; params?: Record<string, any>; delayMs?: number }>
}

const scenarios: Scenario[] = [
  {
    id: 'ami',
    label: '急性心梗',
    icon: '🫀',
    color: '#FF3B30',
    desc: '缺血+心动过速+PVC',
    commands: [
      { cmd: 'condition_normal' },
      { cmd: 'set_damage_level', params: { level: 0.6 } },
      { cmd: 'condition_tachycardia', params: { heart_rate: 110 } },
      { cmd: 'condition_pvc', params: { severity: 0.5, pattern: 'bigeminy' }, delayMs: 300 },
    ],
  },
  {
    id: 'hf_exacerbation',
    label: '心衰加重',
    icon: '💔',
    color: '#AF52DE',
    desc: '心衰+房颤+脱水',
    commands: [
      { cmd: 'condition_heart_failure', params: { severity: 0.7 } },
      { cmd: 'condition_af', params: { severity: 0.6 }, delayMs: 200 },
      { cmd: 'dehydration', params: { severity: 0.5 }, delayMs: 400 },
    ],
  },
  {
    id: 'exercise_vt',
    label: '运动室速',
    icon: '🏃',
    color: '#FF9500',
    desc: '跑步→突发VT',
    commands: [
      { cmd: 'run' },
      { cmd: 'set_vt_substrate', params: { level: 0.8 }, delayMs: 500 },
      { cmd: 'condition_vt', params: { severity: 0.7 }, delayMs: 1500 },
    ],
  },
  {
    id: 'hyperkalemia_crisis',
    label: '高钾危象',
    icon: '⚠️',
    color: '#FFD60A',
    desc: '高钾+缓慢心率+T波尖',
    commands: [
      { cmd: 'condition_normal' },
      { cmd: 'hyperkalemia', params: { level: 6.5 } },
      { cmd: 'condition_bradycardia', params: { heart_rate: 42 }, delayMs: 300 },
    ],
  },
  {
    id: 'anaphylaxis',
    label: '过敏性休克',
    icon: '🚨',
    color: '#FF453A',
    desc: '窦速+低血压',
    commands: [
      { cmd: 'condition_tachycardia', params: { heart_rate: 135 } },
      { cmd: 'set_tpr', params: { level: 0.4 }, delayMs: 200 },
      { cmd: 'set_preload', params: { level: 0.6 }, delayMs: 300 },
    ],
  },
  {
    id: 'healthy',
    label: '健康基线',
    icon: '💚',
    color: '#34C759',
    desc: '一键恢复正常',
    commands: [
      { cmd: 'reset' },
    ],
  },
]

const activeScenarioId = ref<string | null>(null)
const scenarioLoading = ref(false)

async function applyScenario(scenario: Scenario) {
  scenarioLoading.value = true
  activeScenarioId.value = scenario.id
  for (const step of scenario.commands) {
    if (step.delayMs) await sleep(step.delayMs)
    store.sendCommand(step.cmd, step.params)
  }
  toast.success(`场景「${scenario.label}」已激活`)
  await sleep(600)
  scenarioLoading.value = false
}

function sleep(ms: number) {
  return new Promise(resolve => setTimeout(resolve, ms))
}

function send(cmd: string, params?: Record<string, any>) {
  store.sendCommand(cmd, params)
}
</script>

<template>
  <div class="flex flex-col h-full min-h-0 rounded-lg border border-white/[0.06] bg-white/[0.03] p-2.5 gap-1.5 overflow-y-auto">
    <!-- Header -->
    <div class="flex items-center justify-between shrink-0">
      <span class="text-[10px] font-semibold text-white/40 uppercase tracking-wider">快捷操作</span>
      <button class="text-[10px] text-[#007AFF] hover:text-[#007AFF]/80 transition-colors"
              @click="emit('open-controls')">
        更多 →
      </button>
    </div>

    <!-- ═══ Exercise row ═══ -->
    <div class="shrink-0">
      <div class="text-[9px] text-white/25 mb-0.5">运动</div>
      <div class="flex gap-1">
        <button v-for="a in exerciseActions" :key="a.cmd"
                class="qa-btn" :class="activeExercise === a.cmd ? 'qa-btn--active' : ''"
                @click="send(a.cmd)">
          <span class="text-[11px]">{{ a.icon }}</span>
          <span>{{ a.label }}</span>
        </button>
      </div>
    </div>

    <!-- ═══ Emotion row ═══ -->
    <div class="shrink-0">
      <div class="text-[9px] text-white/25 mb-0.5">情绪</div>
      <div class="flex gap-1">
        <button v-for="a in emotionActions" :key="a.cmd"
                class="qa-btn" :class="activeEmotion === a.cmd ? 'qa-btn--amber' : ''"
                @click="send(a.cmd)">
          {{ a.icon }} {{ a.label }}
        </button>
      </div>
    </div>

    <!-- ═══ Condition row ═══ -->
    <div class="shrink-0">
      <div class="text-[9px] text-white/25 mb-0.5">病变</div>
      <div class="flex gap-1">
        <button v-for="a in conditionActions" :key="a.cmd"
                class="qa-btn"
                :class="activeCondition === a.cmd
                  ? (a.cmd === 'condition_normal' ? 'qa-btn--green' : 'qa-btn--red')
                  : ''"
                @click="send(a.cmd)">
          {{ a.icon }} {{ a.label }}
        </button>
      </div>
    </div>

    <!-- ═══ Medication row ═══ -->
    <div class="shrink-0">
      <div class="text-[9px] text-white/25 mb-0.5">用药</div>
      <div class="flex gap-1">
        <button v-for="a in medicationActions" :key="a.cmd"
                class="qa-btn" :class="activeMeds.has(a.cmd) ? 'qa-btn--purple' : ''"
                @click="send(a.cmd, { dose: 0.5 })">
          {{ a.icon }} {{ a.label }}
        </button>
      </div>
    </div>

    <!-- ═══ Body state row ═══ -->
    <div class="shrink-0">
      <div class="text-[9px] text-white/25 mb-0.5">体内</div>
      <div class="flex gap-1">
        <button v-for="a in bodyActions" :key="a.cmd"
                class="qa-btn" :class="activeBody.has(a.cmd) ? 'qa-btn--teal' : ''"
                @click="send(a.cmd)">
          {{ a.icon }} {{ a.label }}
        </button>
      </div>
    </div>

    <!-- ═══ Emergency row ═══ -->
    <div class="shrink-0">
      <div class="flex gap-1">
        <button v-for="a in emergencyActions" :key="a.cmd"
                class="qa-btn text-[10px] font-semibold"
                :class="a.danger
                  ? (a.cmd === 'defibrillate' && !canDefibrillate) || (a.cmd === 'cardiovert' && !canCardiovert)
                    ? 'qa-btn--disabled'
                    : 'qa-btn--danger'
                  : ''"
                :disabled="a.danger && ((a.cmd === 'defibrillate' && !canDefibrillate) || (a.cmd === 'cardiovert' && !canCardiovert))"
                @click="send(a.cmd)">
          {{ a.icon }} {{ a.label }}
        </button>
      </div>
    </div>

    <!-- ═══ Divider ═══ -->
    <div class="shrink-0 border-t border-white/[0.06] my-0.5" />

    <!-- ═══ Scenario Presets ═══ -->
    <div class="shrink-0">
      <div class="text-[9px] text-white/25 mb-1">临床场景</div>
      <div class="grid grid-cols-3 gap-1">
        <button v-for="s in scenarios" :key="s.id"
                class="scenario-card"
                :class="{ 'scenario-card--active': activeScenarioId === s.id }"
                :style="activeScenarioId === s.id ? `--sc-color: ${s.color}` : ''"
                :disabled="scenarioLoading"
                @click="applyScenario(s)">
          <span class="text-[13px] leading-none">{{ s.icon }}</span>
          <span class="text-[10px] font-semibold leading-tight"
                :style="activeScenarioId === s.id ? `color: ${s.color}` : ''">
            {{ s.label }}
          </span>
          <span class="text-[8px] text-white/25 leading-tight">{{ s.desc }}</span>
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* ── Quick Action button base ── */
.qa-btn {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 2px;
  padding: 4px 0;
  border-radius: 8px;
  font-size: 10px;
  font-weight: 500;
  background: rgba(255, 255, 255, 0.04);
  color: rgba(255, 255, 255, 0.4);
  border: 1px solid rgba(255, 255, 255, 0.04);
  transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
}
.qa-btn:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.08);
}

/* Active states */
.qa-btn--active {
  background: rgba(0, 122, 255, 0.15);
  color: #007AFF;
  border-color: rgba(0, 122, 255, 0.25);
}
.qa-btn--amber {
  background: rgba(255, 149, 0, 0.12);
  color: #FF9500;
  border-color: rgba(255, 149, 0, 0.2);
}
.qa-btn--red {
  background: rgba(255, 59, 48, 0.12);
  color: #FF3B30;
  border-color: rgba(255, 59, 48, 0.2);
}
.qa-btn--green {
  background: rgba(52, 199, 89, 0.12);
  color: #34C759;
  border-color: rgba(52, 199, 89, 0.2);
}
.qa-btn--purple {
  background: rgba(175, 82, 222, 0.12);
  color: #AF52DE;
  border-color: rgba(175, 82, 222, 0.2);
}
.qa-btn--teal {
  background: rgba(90, 200, 250, 0.12);
  color: #5AC8FA;
  border-color: rgba(90, 200, 250, 0.2);
}
.qa-btn--danger {
  background: rgba(255, 59, 48, 0.12);
  color: #FF3B30;
  border-color: rgba(255, 59, 48, 0.2);
}
.qa-btn--danger:hover {
  background: rgba(255, 59, 48, 0.25);
}
.qa-btn--disabled {
  background: rgba(255, 255, 255, 0.02);
  color: rgba(255, 255, 255, 0.15);
  border-color: rgba(255, 255, 255, 0.03);
  cursor: not-allowed;
}

/* ── Scenario preset cards ── */
.scenario-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  padding: 6px 4px;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.06);
  cursor: pointer;
  transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1);
  -webkit-tap-highlight-color: transparent;
}
.scenario-card:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.07);
  border-color: rgba(255, 255, 255, 0.1);
  transform: translateY(-1px);
}
.scenario-card:active:not(:disabled) {
  transform: scale(0.97);
}
.scenario-card--active {
  background: color-mix(in srgb, var(--sc-color, #007AFF) 10%, transparent);
  border-color: color-mix(in srgb, var(--sc-color, #007AFF) 25%, transparent);
  box-shadow: 0 0 12px color-mix(in srgb, var(--sc-color, #007AFF) 15%, transparent);
}
.scenario-card:disabled {
  opacity: 0.5;
  cursor: wait;
}
</style>

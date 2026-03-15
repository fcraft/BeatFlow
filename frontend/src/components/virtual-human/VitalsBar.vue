<script setup lang="ts">
/**
 * VitalsBar — 底部常驻薄条 + 可展开详情面板
 * 单行: HR | BP | SpO2 | Temp | RR | CO | [展开▲] [控制⚙]
 */
import { computed } from 'vue'
import { ChevronUp, ChevronDown, Sliders } from 'lucide-vue-next'
import { useVirtualHumanStore } from '@/store/virtualHuman'
import type { AlarmLevel } from '@/composables/useAlarmSystem'

const props = defineProps<{
  expanded: boolean
  getAlarmLevel?: (param: string) => AlarmLevel | null
}>()
const emit = defineEmits<{
  'update:expanded': [value: boolean]
  'open-controls': []
}>()

const store = useVirtualHumanStore()
const v = computed(() => store.vitals)

function alarmClass(param: string): string {
  if (!props.getAlarmLevel) return ''
  const level = props.getAlarmLevel(param)
  if (level === 'critical') return 'alarm-critical-pulse'
  if (level === 'warning') return 'alarm-warning-pulse'
  return ''
}

// Color computeds
const hrColor = computed(() => {
  const hr = v.value.heart_rate
  if (hr > 150 || hr < 40) return 'text-red-400'
  if (hr > 100 || hr < 50) return 'text-yellow-400'
  return 'text-green-400'
})

const spo2Color = computed(() => {
  const s = v.value.spo2
  if (s < 90) return 'text-red-400'
  if (s < 95) return 'text-yellow-400'
  return 'text-cyan-400'
})

const coColor = computed(() => {
  const co = v.value.cardiac_output
  if (co < 2.5) return 'text-red-400'
  if (co < 4.0) return 'text-yellow-400'
  return 'text-green-400'
})

const efColor = computed(() => {
  const ef = v.value.ejection_fraction
  if (ef < 35) return 'text-red-400'
  if (ef < 50) return 'text-yellow-400'
  return 'text-blue-400'
})

const svColor = computed(() => {
  const sv = v.value.stroke_volume
  if (sv < 30) return 'text-red-400'
  if (sv < 50) return 'text-yellow-400'
  return 'text-purple-400'
})

const prColor = computed(() => {
  const pr = v.value.conduction.pr_interval_ms
  if (pr === 0) return 'text-white/30'
  if (pr > 200) return 'text-red-400'
  if (pr < 120) return 'text-yellow-400'
  return 'text-green-400'
})

const qrsColor = computed(() => {
  const qrs = v.value.conduction.qrs_duration_ms
  if (qrs > 120) return 'text-red-400'
  if (qrs > 100) return 'text-yellow-400'
  return 'text-green-400'
})

const kColor = computed(() => {
  const k = v.value.potassium_level
  if (k < 3.5 || k > 5.5) return 'text-red-400'
  if (k < 4.0 || k > 5.0) return 'text-yellow-400'
  return 'text-green-400'
})

const caColor = computed(() => {
  const ca = v.value.calcium_level
  if (ca < 8.5 || ca > 10.5) return 'text-red-400'
  if (ca < 9.0 || ca > 10.0) return 'text-yellow-400'
  return 'text-green-400'
})

const irrColor = computed(() => {
  const irr = v.value.ectopic_irritability
  if (irr > 0.7) return 'bg-red-400'
  if (irr > 0.4) return 'bg-yellow-400'
  return 'bg-green-400'
})

const RHYTHM_LABELS: Record<string, string> = {
  normal: 'Sinus', sinus: 'Sinus', af: 'AF', svt: 'SVT', vt: 'VT', vf: 'VF',
  pvc: 'PVC', flutter: 'Flutter',
}
const rhythmLabel = computed(() => {
  const rhythm = v.value.rhythm || ''
  return RHYTHM_LABELS[rhythm] || rhythm
})

/** AV block degree from store (conduction model computes it) */
const avBlockDegree = computed(() => {
  return v.value.conduction?.av_block_degree ?? 0
})

function nodeColor(state: string): string {
  switch (state) {
    case 'resting': return 'bg-green-400'
    case 'depolarized': return 'bg-yellow-400'
    case 'arp': return 'bg-red-400'
    case 'rrp': return 'bg-orange-400'
    default: return 'bg-gray-400'
  }
}

const activeMeds = computed(() => {
  const meds: { label: string; level: number }[] = []
  if (v.value.beta_blocker_level > 0.05) meds.push({ label: 'β-阻滞剂', level: v.value.beta_blocker_level })
  if (v.value.amiodarone_level > 0.05) meds.push({ label: '胺碘酮', level: v.value.amiodarone_level })
  if (v.value.digoxin_level > 0.05) meds.push({ label: '地高辛', level: v.value.digoxin_level })
  if (v.value.atropine_level > 0.05) meds.push({ label: '阿托品', level: v.value.atropine_level })
  return meds
})

const hasCardiacAbnormality = computed(() =>
  v.value.murmur_severity > 0 || v.value.damage_level > 0.1 ||
  v.value.rhythm === 'pvc' || v.value.gallop_s3 || v.value.gallop_s4
)

const pvcPatternLabel = computed(() => {
  const map: Record<string, string> = {
    isolated: '孤立', bigeminy: '二联律', trigeminy: '三联律', couplets: '成对',
  }
  return map[v.value.pvc_pattern] || v.value.pvc_pattern
})

const activeStates = computed(() => {
  const pills: { icon: string; label: string }[] = []
  if (v.value.caffeine_level > 0.05) pills.push({ icon: '☕', label: '咖啡因' })
  if (v.value.alcohol_level > 0.05) pills.push({ icon: '🍺', label: '酒精' })
  if (v.value.dehydration_level > 0.1) pills.push({ icon: '💧', label: '脱水' })
  if (v.value.temperature > 37.5) pills.push({ icon: '🤒', label: '发热' })
  if (v.value.sleep_debt > 0.1) pills.push({ icon: '💤', label: '缺觉' })
  return pills
})
</script>

<template>
  <div class="shrink-0 backdrop-blur-xl bg-white/[0.06] border border-white/[0.08] rounded-xl overflow-hidden">
    <!-- 单行薄条 -->
    <div class="flex items-center gap-4 px-4 py-1.5">
      <!-- HR -->
      <div class="flex items-center gap-1.5">
        <span class="text-[10px] text-white/40">HR</span>
        <span :class="['text-sm font-bold tabular-nums', hrColor, alarmClass('heart_rate')]">{{ Math.round(v.heart_rate) }}</span>
        <span class="text-[9px] text-white/30">bpm</span>
        <span class="text-[9px] px-1 py-0.5 rounded bg-white/[0.08] text-white/50">{{ rhythmLabel }}</span>
        <!-- HR Override 指示器 -->
        <span v-if="v.hr_override_active"
              class="text-[9px] px-1 py-0.5 rounded bg-amber-500/20 text-amber-300
                     border border-amber-500/30 flex items-center gap-0.5 cursor-pointer"
              title="点击取消 HR 覆盖"
              @click="store.sendCommand('cancel_hr_override')">
          锁定 {{ v.hr_override_value }} bpm ✕
        </span>
      </div>

      <div class="w-px h-4 bg-white/10" />

      <!-- BP -->
      <div class="flex items-center gap-1.5">
        <span class="text-[10px] text-white/40">BP</span>
        <span :class="['text-sm font-bold tabular-nums text-orange-400', alarmClass('systolic_bp')]">
          {{ Math.round(v.systolic_bp) }}/{{ Math.round(v.diastolic_bp) }}
        </span>
        <span class="text-[9px] text-white/30">mmHg</span>
      </div>

      <div class="w-px h-4 bg-white/10" />

      <!-- SpO2 -->
      <div class="flex items-center gap-1.5">
        <span class="text-[10px] text-white/40">SpO2</span>
        <span :class="['text-sm font-bold tabular-nums', spo2Color, alarmClass('spo2')]">{{ v.spo2.toFixed(1) }}</span>
        <span class="text-[9px] text-white/30">%</span>
        <span v-if="v.pao2 > 50" class="text-[8px] px-1 py-0.5 rounded bg-cyan-500/10 text-cyan-400/60 border border-cyan-500/20" title="SpO2 由 O₂-Hb 解离曲线物理模型驱动">PHY</span>
      </div>

      <div class="w-px h-4 bg-white/10" />

      <!-- Temp -->
      <div class="flex items-center gap-1.5">
        <span class="text-[10px] text-white/40">Temp</span>
        <span :class="['text-sm font-bold tabular-nums text-pink-400', alarmClass('temperature')]">{{ v.temperature.toFixed(1) }}</span>
        <span class="text-[9px] text-white/30">°C</span>
      </div>

      <div class="w-px h-4 bg-white/10" />

      <!-- RR -->
      <div class="flex items-center gap-1.5">
        <span class="text-[10px] text-white/40">RR</span>
        <span :class="['text-sm font-bold tabular-nums text-blue-400', alarmClass('respiratory_rate')]">{{ Math.round(v.respiratory_rate) }}</span>
        <span class="text-[9px] text-white/30">/min</span>
        <span v-if="v.paco2 > 0" class="text-[8px] px-1 py-0.5 rounded bg-blue-500/10 text-blue-400/60 border border-blue-500/20" title="RR 由化学感受器物理模型驱动">PHY</span>
      </div>

      <div class="w-px h-4 bg-white/10" />

      <!-- CO -->
      <div class="flex items-center gap-1.5">
        <span class="text-[10px] text-white/40">CO</span>
        <span :class="['text-sm font-bold tabular-nums', coColor]">{{ v.cardiac_output.toFixed(1) }}</span>
        <span class="text-[9px] text-white/30">L/min</span>
      </div>

      <!-- Spacer -->
      <div class="flex-1" />

      <!-- Expand toggle -->
      <button
        class="flex items-center gap-1 px-2 py-1 text-[10px] text-white/50 hover:text-white/80 hover:bg-white/5 rounded transition-colors"
        @click="emit('update:expanded', !props.expanded)"
      >
        <component :is="props.expanded ? ChevronDown : ChevronUp" :size="12" />
        {{ props.expanded ? '收起' : '详情' }}
      </button>

      <!-- Control drawer trigger -->
      <button
        class="flex items-center gap-1 px-2 py-1 text-[10px] text-white/50 hover:text-white/80 hover:bg-white/5 rounded transition-colors"
        @click="emit('open-controls')"
      >
        <Sliders :size="12" />
        控制
      </button>
    </div>

    <!-- 展开详情区域 -->
    <Transition name="expand">
      <div v-if="props.expanded" class="border-t border-white/[0.06] px-4 py-3">
        <div class="grid grid-cols-3 gap-3">

          <!-- 血流动力学 -->
          <div class="bg-white/[0.04] rounded-lg p-3 space-y-2">
            <h4 class="text-[10px] font-medium text-white/50 uppercase tracking-wider">血流动力学</h4>
            <div class="grid grid-cols-3 gap-2">
              <div class="text-center">
                <div class="text-[9px] text-white/30">CO</div>
                <div :class="['text-sm font-bold tabular-nums', coColor]">{{ v.cardiac_output.toFixed(1) }}</div>
                <div class="text-[9px] text-white/30">L/min</div>
              </div>
              <div class="text-center">
                <div class="text-[9px] text-white/30">EF</div>
                <div :class="['text-sm font-bold tabular-nums', efColor]">{{ v.ejection_fraction.toFixed(0) }}</div>
                <div class="text-[9px] text-white/30">%</div>
              </div>
              <div class="text-center">
                <div class="text-[9px] text-white/30">SV</div>
                <div :class="['text-sm font-bold tabular-nums', svColor]">{{ v.stroke_volume.toFixed(0) }}</div>
                <div class="text-[9px] text-white/30">mL</div>
              </div>
            </div>
          </div>

          <!-- 电生理传导 -->
          <div class="bg-white/[0.04] rounded-lg p-3 space-y-2">
            <h4 class="text-[10px] font-medium text-white/50 uppercase tracking-wider">电生理传导</h4>
            <!-- 传导通路 -->
            <div class="flex items-center gap-1 text-[10px]">
              <span :class="['w-2 h-2 rounded-full', nodeColor(v.conduction.sa_state)]" />
              <span class="text-white/40">SA</span>
              <span class="text-white/20">→</span>
              <span :class="['w-2 h-2 rounded-full', nodeColor(v.conduction.av_state)]" />
              <span class="text-white/40">AV</span>
              <span class="text-white/20">→</span>
              <span :class="['w-2 h-2 rounded-full', nodeColor(v.conduction.his_state)]" />
              <span class="text-white/40">His</span>
              <span class="text-white/20">→</span>
              <span :class="['w-2 h-2 rounded-full', nodeColor(v.conduction.purkinje_state)]" />
              <span class="text-white/40">Purk</span>
            </div>
            <div class="grid grid-cols-2 gap-2">
              <div>
                <div class="text-[9px] text-white/30">PR</div>
                <div :class="['text-sm font-bold tabular-nums', prColor]">
                  {{ v.conduction.pr_interval_ms > 0 ? Math.round(v.conduction.pr_interval_ms) : '—' }}
                  <span class="text-[9px] font-normal text-white/30">ms</span>
                </div>
              </div>
              <div>
                <div class="text-[9px] text-white/30">QRS</div>
                <div :class="['text-sm font-bold tabular-nums', qrsColor]">
                  {{ Math.round(v.conduction.qrs_duration_ms) }}
                  <span class="text-[9px] font-normal text-white/30">ms</span>
                </div>
              </div>
            </div>
            <!-- Extended conduction details -->
            <div class="grid grid-cols-4 gap-1 mt-2 pt-2 border-t border-white/[0.05]">
              <div class="text-center">
                <div class="text-[8px] text-white/25">SA Rate</div>
                <div class="text-[10px] font-bold tabular-nums text-white/60">
                  {{ v.conduction.sa_rate ? Math.round(v.conduction.sa_rate) : '—' }}
                  <span class="text-[8px] font-normal text-white/25">bpm</span>
                </div>
              </div>
              <div class="text-center">
                <div class="text-[8px] text-white/25">AV Ref</div>
                <div class="text-[10px] font-bold tabular-nums text-white/60">
                  {{ v.conduction.av_refractory_ms ? Math.round(v.conduction.av_refractory_ms) : '—' }}
                  <span class="text-[8px] font-normal text-white/25">ms</span>
                </div>
              </div>
              <div class="text-center">
                <div class="text-[8px] text-white/25">His</div>
                <div class="text-[10px] font-bold tabular-nums text-white/60">
                  {{ v.conduction.his_delay_ms ? Math.round(v.conduction.his_delay_ms) : '—' }}
                  <span class="text-[8px] font-normal text-white/25">ms</span>
                </div>
              </div>
              <div class="text-center">
                <div class="text-[8px] text-white/25">Purkinje</div>
                <div class="text-[10px] font-bold tabular-nums text-white/60">
                  {{ v.conduction.purkinje_delay_ms ? Math.round(v.conduction.purkinje_delay_ms) : '—' }}
                  <span class="text-[8px] font-normal text-white/25">ms</span>
                </div>
              </div>
            </div>
            <!-- Conduction status badges -->
            <div class="flex flex-wrap gap-1 mt-2">
              <span v-if="v.conduction.svt_active" class="px-1.5 py-0.5 text-[9px] bg-yellow-500/20 text-yellow-300 rounded-full border border-yellow-500/30">⚡ SVT</span>
              <div v-if="avBlockDegree > 0"
                   class="px-1.5 py-0.5 text-[9px] rounded-full border"
                   :class="avBlockDegree >= 3 ? 'bg-red-500/20 text-red-300 border-red-500/30' : avBlockDegree >= 2 ? 'bg-orange-500/20 text-orange-300 border-orange-500/30' : 'bg-yellow-500/20 text-yellow-300 border-yellow-500/30'">
                AV Block {{ avBlockDegree }}°
              </div>
              <div v-if="rhythmLabel && rhythmLabel !== 'Sinus'"
                   class="px-1.5 py-0.5 text-[9px] rounded-full border bg-amber-500/20 text-amber-300 border-amber-500/30">
                {{ rhythmLabel }}
              </div>
            </div>
          </div>

          <!-- 生理状态 -->
          <div class="bg-white/[0.04] rounded-lg p-3 space-y-2">
            <h4 class="text-[10px] font-medium text-white/50 uppercase tracking-wider">生理状态</h4>
            <div class="space-y-1.5">
              <div class="flex items-center gap-1.5">
                <span class="text-[9px] text-red-400 w-5">交感</span>
                <div class="flex-1 h-1.5 bg-white/[0.08] rounded-full overflow-hidden">
                  <div class="h-full bg-red-400 transition-all" :style="{ width: (v.sympathetic_tone * 100) + '%' }" />
                </div>
                <span class="text-[9px] text-white/30 w-7 text-right tabular-nums">{{ (v.sympathetic_tone * 100).toFixed(0) }}%</span>
              </div>
              <div class="flex items-center gap-1.5">
                <span class="text-[9px] text-blue-400 w-5">副交</span>
                <div class="flex-1 h-1.5 bg-white/[0.08] rounded-full overflow-hidden">
                  <div class="h-full bg-blue-400 transition-all" :style="{ width: (v.parasympathetic_tone * 100) + '%' }" />
                </div>
                <span class="text-[9px] text-white/30 w-7 text-right tabular-nums">{{ (v.parasympathetic_tone * 100).toFixed(0) }}%</span>
              </div>
              <div class="flex items-center gap-1.5">
                <span class="text-[9px] text-white/30 w-5">易激</span>
                <div class="flex-1 h-1.5 bg-white/[0.08] rounded-full overflow-hidden">
                  <div :class="['h-full transition-all', irrColor]" :style="{ width: (v.ectopic_irritability * 100) + '%' }" />
                </div>
                <span class="text-[9px] text-white/30 w-7 text-right tabular-nums">{{ (v.ectopic_irritability * 100).toFixed(0) }}%</span>
              </div>
            </div>
            <div v-if="activeStates.length > 0" class="flex flex-wrap gap-1 pt-1">
              <span v-for="s in activeStates" :key="s.label" class="px-1.5 py-0.5 text-[9px] bg-white/[0.08] text-white/50 rounded-full">{{ s.icon }} {{ s.label }}</span>
            </div>
          </div>

          <!-- 电解质 -->
          <div class="bg-white/[0.04] rounded-lg p-3 space-y-2">
            <h4 class="text-[10px] font-medium text-white/50 uppercase tracking-wider">电解质</h4>
            <div class="flex items-center justify-between">
              <span class="text-[9px] text-white/30">K⁺</span>
              <span :class="['text-sm font-bold tabular-nums', kColor]">{{ v.potassium_level.toFixed(1) }} <span class="text-[9px] font-normal text-white/30">mEq/L</span></span>
            </div>
            <div class="flex items-center justify-between">
              <span class="text-[9px] text-white/30">Ca²⁺</span>
              <span :class="['text-sm font-bold tabular-nums', caColor]">{{ v.calcium_level.toFixed(1) }} <span class="text-[9px] font-normal text-white/30">mg/dL</span></span>
            </div>
            <div class="flex items-center justify-between">
              <span class="text-[9px] text-white/30">Mg²⁺</span>
              <span :class="['text-sm font-bold tabular-nums', v.magnesium_level < 1.7 || v.magnesium_level > 2.5 ? 'text-red-400' : 'text-green-400']">{{ v.magnesium_level.toFixed(1) }} <span class="text-[9px] font-normal text-white/30">mg/dL</span></span>
            </div>
          </div>

          <!-- 呼吸系统 -->
          <div class="bg-white/[0.04] rounded-lg p-3 space-y-2">
            <h4 class="text-[10px] font-medium text-white/50 uppercase tracking-wider">呼吸系统</h4>
            <div class="grid grid-cols-2 gap-2">
              <div>
                <div class="text-[9px] text-white/30">PaO₂</div>
                <div :class="['text-sm font-bold tabular-nums', v.pao2 < 60 ? 'text-red-400' : v.pao2 < 80 ? 'text-yellow-400' : 'text-green-400']">{{ v.pao2.toFixed(0) }} <span class="text-[9px] font-normal text-white/30">mmHg</span></div>
              </div>
              <div>
                <div class="text-[9px] text-white/30">PaCO₂</div>
                <div :class="['text-sm font-bold tabular-nums', v.paco2 > 50 ? 'text-red-400' : v.paco2 < 35 ? 'text-yellow-400' : 'text-green-400']">{{ v.paco2.toFixed(0) }} <span class="text-[9px] font-normal text-white/30">mmHg</span></div>
              </div>
              <div>
                <div class="text-[9px] text-white/30">pH</div>
                <div :class="['text-sm font-bold tabular-nums', v.ph < 7.35 || v.ph > 7.45 ? 'text-red-400' : 'text-green-400']">{{ v.ph.toFixed(2) }}</div>
              </div>
              <div>
                <div class="text-[9px] text-white/30">FiO₂</div>
                <div class="text-sm font-bold tabular-nums text-white/60">{{ (v.fio2 * 100).toFixed(0) }}%</div>
              </div>
            </div>
          </div>

          <!-- 右心 / 肺循环 -->
          <div class="bg-white/[0.04] rounded-lg p-3 space-y-2">
            <h4 class="text-[10px] font-medium text-white/50 uppercase tracking-wider">右心 / 肺循环</h4>
            <div class="grid grid-cols-2 gap-2">
              <div>
                <div class="text-[9px] text-white/30">PA压</div>
                <div :class="['text-sm font-bold tabular-nums', v.pa_systolic > 35 ? 'text-red-400' : 'text-blue-400']">{{ v.pa_systolic.toFixed(0) }}/{{ v.pa_diastolic.toFixed(0) }} <span class="text-[9px] font-normal text-white/30">mmHg</span></div>
              </div>
              <div>
                <div class="text-[9px] text-white/30">RV EF</div>
                <div :class="['text-sm font-bold tabular-nums', v.rv_ejection_fraction < 40 ? 'text-red-400' : 'text-blue-400']">{{ v.rv_ejection_fraction.toFixed(0) }}%</div>
              </div>
              <div>
                <div class="text-[9px] text-white/30">RV SV</div>
                <div class="text-sm font-bold tabular-nums text-purple-400">{{ v.rv_stroke_volume.toFixed(0) }} <span class="text-[9px] font-normal text-white/30">mL</span></div>
              </div>
              <div>
                <div class="text-[9px] text-white/30">mPAP</div>
                <div :class="['text-sm font-bold tabular-nums', v.pa_mean > 25 ? 'text-red-400' : 'text-green-400']">{{ v.pa_mean.toFixed(0) }} <span class="text-[9px] font-normal text-white/30">mmHg</span></div>
              </div>
            </div>
          </div>

          <!-- 冠脉循环 -->
          <div class="bg-white/[0.04] rounded-lg p-3 space-y-2">
            <h4 class="text-[10px] font-medium text-white/50 uppercase tracking-wider">冠脉循环</h4>
            <div class="space-y-1.5">
              <div class="flex items-center justify-between">
                <span class="text-[9px] text-white/30">CPP</span>
                <span :class="['text-sm font-bold tabular-nums', v.coronary_perfusion_pressure < 50 ? 'text-red-400' : 'text-green-400']">{{ v.coronary_perfusion_pressure.toFixed(0) }} <span class="text-[9px] font-normal text-white/30">mmHg</span></span>
              </div>
              <div v-if="v.ischemia_level > 0.01" class="space-y-0.5">
                <div class="flex justify-between text-[9px]">
                  <span class="text-white/40">缺血程度</span>
                  <span class="text-red-400 tabular-nums">{{ (v.ischemia_level * 100).toFixed(0) }}%</span>
                </div>
                <div class="h-1 bg-white/[0.08] rounded-full overflow-hidden">
                  <div class="h-full bg-red-400 transition-all rounded-full" :style="{ width: (v.ischemia_level * 100) + '%' }" />
                </div>
              </div>
              <div v-if="v.coronary_stenosis > 0.01" class="flex items-center justify-between">
                <span class="text-[9px] text-white/30">狭窄</span>
                <span class="text-sm font-bold tabular-nums text-orange-400">{{ (v.coronary_stenosis * 100).toFixed(0) }}%</span>
              </div>
              <div v-if="v.raas_activation > 0.05" class="flex items-center justify-between">
                <span class="text-[9px] text-white/30">RAAS</span>
                <span class="text-sm font-bold tabular-nums text-yellow-400">{{ (v.raas_activation * 100).toFixed(0) }}%</span>
              </div>
            </div>
          </div>

          <!-- 药物浓度 -->
          <div v-if="activeMeds.length > 0" class="bg-white/[0.04] rounded-lg p-3 space-y-2">
            <h4 class="text-[10px] font-medium text-white/50 uppercase tracking-wider">药物浓度</h4>
            <div v-for="med in activeMeds" :key="med.label" class="space-y-0.5">
              <div class="flex justify-between text-[9px]">
                <span class="text-white/40">{{ med.label }}</span>
                <span class="text-purple-400 tabular-nums">{{ (med.level * 100).toFixed(0) }}%</span>
              </div>
              <div class="h-1 bg-white/[0.08] rounded-full overflow-hidden">
                <div class="h-full bg-purple-400 transition-all rounded-full" :style="{ width: (med.level * 100) + '%' }" />
              </div>
            </div>
          </div>

          <!-- 心脏结构 -->
          <div v-if="hasCardiacAbnormality" class="bg-white/[0.04] rounded-lg p-3 space-y-2">
            <h4 class="text-[10px] font-medium text-white/50 uppercase tracking-wider">心脏结构</h4>
            <div v-if="v.murmur_severity > 0" class="space-y-0.5">
              <div class="flex justify-between text-[9px]">
                <span class="text-white/40">杂音 ({{ v.murmur_type || '未分类' }})</span>
                <span class="text-red-400 tabular-nums">{{ (v.murmur_severity * 100).toFixed(0) }}%</span>
              </div>
              <div class="h-1 bg-white/[0.08] rounded-full overflow-hidden">
                <div class="h-full bg-red-400 transition-all rounded-full" :style="{ width: (v.murmur_severity * 100) + '%' }" />
              </div>
            </div>
            <div v-if="v.damage_level > 0.1" class="space-y-0.5">
              <div class="flex justify-between text-[9px]">
                <span class="text-white/40">损伤</span>
                <span class="text-orange-400 tabular-nums">{{ (v.damage_level * 100).toFixed(0) }}%</span>
              </div>
              <div class="h-1 bg-white/[0.08] rounded-full overflow-hidden">
                <div class="h-full bg-orange-400 transition-all rounded-full" :style="{ width: (v.damage_level * 100) + '%' }" />
              </div>
            </div>
            <div v-if="v.rhythm === 'pvc'" class="flex items-center gap-1">
              <span class="text-[9px] text-white/40">PVC:</span>
              <span class="text-[9px] text-orange-300 bg-orange-500/20 px-1.5 py-0.5 rounded-full border border-orange-500/30">{{ pvcPatternLabel }}</span>
            </div>
            <div v-if="v.gallop_s3" class="px-1.5 py-0.5 text-[9px] bg-orange-500/20 text-orange-300 rounded-full border border-orange-500/30">
              S3 奔马律
            </div>
            <div v-if="v.gallop_s4" class="px-1.5 py-0.5 text-[9px] bg-orange-500/20 text-orange-300 rounded-full border border-orange-500/30">
              S4 奔马律
            </div>
          </div>

        </div>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.expand-enter-active,
.expand-leave-active {
  transition: all 0.25s ease;
  overflow: hidden;
}
.expand-enter-from,
.expand-leave-to {
  max-height: 0;
  opacity: 0;
  padding-top: 0;
  padding-bottom: 0;
}
.expand-enter-to,
.expand-leave-from {
  max-height: 400px;
  opacity: 1;
}
.alarm-critical-pulse {
  animation: critical-flash 0.5s ease-in-out infinite;
}
.alarm-warning-pulse {
  animation: warning-flash 1s ease-in-out infinite;
}
@keyframes critical-flash {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}
@keyframes warning-flash {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.6; }
}
</style>

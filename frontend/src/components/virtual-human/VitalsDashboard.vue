<script setup lang="ts">
/**
 * 生命体征仪表盘：HR / BP / SpO2 / Temp / RR + 生理状态面板 + 电生理传导面板
 */
import { computed, ref } from 'vue'
import { ChevronDown, ChevronUp } from 'lucide-vue-next'
import { useVirtualHumanStore } from '@/store/virtualHuman'

const store = useVirtualHumanStore()
const v = computed(() => store.vitals)
const showPhysio = ref(true)
const showConduction = ref(false)
const showElectrolytes = ref(false)
const showMedications = ref(false)
const showCardiac = ref(false)
const showHemodynamics = ref(false)

// HR 颜色
const hrColor = computed(() => {
  const hr = v.value.heart_rate
  if (hr > 150 || hr < 40) return 'text-red-400'
  if (hr > 100 || hr < 50) return 'text-yellow-400'
  return 'text-green-400'
})

// SpO2 颜色
const spo2Color = computed(() => {
  const s = v.value.spo2
  if (s < 90) return 'text-red-400'
  if (s < 95) return 'text-yellow-400'
  return 'text-cyan-400'
})

// 节律标签
const rhythmLabel = computed(() => {
  const map: Record<string, string> = {
    normal: '窦性', af: '房颤', pvc: '早搏', vt: 'VT', svt: 'SVT',
  }
  return map[v.value.rhythm] || v.value.rhythm
})

// irritability 颜色
const irrColor = computed(() => {
  const irr = v.value.ectopic_irritability
  if (irr > 0.7) return 'bg-red-400'
  if (irr > 0.4) return 'bg-yellow-400'
  return 'bg-green-400'
})

// 活性状态药丸
const activeStates = computed(() => {
  const pills: { icon: string; label: string }[] = []
  if (v.value.caffeine_level > 0.05) pills.push({ icon: '☕', label: '咖啡因' })
  if (v.value.alcohol_level > 0.05) pills.push({ icon: '🍺', label: '酒精' })
  if (v.value.dehydration_level > 0.1) pills.push({ icon: '💧', label: '脱水' })
  if (v.value.temperature > 37.5) pills.push({ icon: '🤒', label: '发热' })
  if (v.value.sleep_debt > 0.1) pills.push({ icon: '💤', label: '缺觉' })
  return pills
})

// 传导节点状态颜色
function nodeColor(state: string): string {
  switch (state) {
    case 'resting': return 'bg-green-400'
    case 'depolarized': return 'bg-yellow-400'
    case 'arp': return 'bg-red-400'
    case 'rrp': return 'bg-orange-400'
    default: return 'bg-gray-400'
  }
}

// PR 间期颜色
const prColor = computed(() => {
  const pr = v.value.conduction.pr_interval_ms
  if (pr === 0) return 'text-gray-500' // 无 P 波
  if (pr > 200) return 'text-red-400'  // I 度 AVB
  if (pr < 120) return 'text-yellow-400' // 短 PR
  return 'text-green-400'
})

// QRS 时限颜色
const qrsColor = computed(() => {
  const qrs = v.value.conduction.qrs_duration_ms
  if (qrs > 120) return 'text-red-400'  // 宽 QRS
  if (qrs > 100) return 'text-yellow-400'
  return 'text-green-400'
})

// K⁺ 颜色
const kColor = computed(() => {
  const k = v.value.potassium_level
  if (k < 3.5 || k > 5.5) return 'text-red-400'
  if (k < 4.0 || k > 5.0) return 'text-yellow-400'
  return 'text-green-400'
})

// Ca²⁺ 颜色
const caColor = computed(() => {
  const ca = v.value.calcium_level
  if (ca < 8.5 || ca > 10.5) return 'text-red-400'
  if (ca < 9.0 || ca > 10.0) return 'text-yellow-400'
  return 'text-green-400'
})

// 活跃药物列表
const activeMeds = computed(() => {
  const meds: { label: string; level: number }[] = []
  if (v.value.beta_blocker_level > 0.05) meds.push({ label: 'β-阻滞剂', level: v.value.beta_blocker_level })
  if (v.value.amiodarone_level > 0.05) meds.push({ label: '胺碘酮', level: v.value.amiodarone_level })
  if (v.value.digoxin_level > 0.05) meds.push({ label: '地高辛', level: v.value.digoxin_level })
  if (v.value.atropine_level > 0.05) meds.push({ label: '阿托品', level: v.value.atropine_level })
  return meds
})

// 是否显示心脏结构异常
const hasCardiacAbnormality = computed(() =>
  v.value.murmur_severity > 0 || v.value.damage_level > 0.1 || v.value.rhythm === 'pvc'
)

// PVC 模式标签
const pvcPatternLabel = computed(() => {
  const map: Record<string, string> = {
    isolated: '孤立', bigeminy: '二联律', trigeminy: '三联律', couplets: '成对',
  }
  return map[v.value.pvc_pattern] || v.value.pvc_pattern
})

// CO 颜色
const coColor = computed(() => {
  const co = v.value.cardiac_output
  if (co < 2.5) return 'text-red-400'
  if (co < 4.0) return 'text-yellow-400'
  return 'text-green-400'
})

// EF 颜色
const efColor = computed(() => {
  const ef = v.value.ejection_fraction
  if (ef < 35) return 'text-red-400'
  if (ef < 50) return 'text-yellow-400'
  return 'text-blue-400'
})

// SV 颜色
const svColor = computed(() => {
  const sv = v.value.stroke_volume
  if (sv < 30) return 'text-red-400'
  if (sv < 50) return 'text-yellow-400'
  return 'text-purple-400'
})
</script>

<template>
  <div class="space-y-3">
    <!-- 心率 -->
    <div class="bg-gray-800 rounded-lg p-3 border border-gray-700">
      <div class="text-xs text-gray-400 mb-0.5 flex items-center justify-between">
        <span>HR</span>
        <span class="text-[10px] px-1.5 py-0.5 rounded bg-gray-700 text-gray-300">{{ rhythmLabel }}</span>
      </div>
      <div :class="['text-3xl font-bold tabular-nums', hrColor]">
        {{ Math.round(v.heart_rate) }}
        <span class="text-xs font-normal text-gray-500">bpm</span>
      </div>
    </div>

    <!-- 血压 -->
    <div class="bg-gray-800 rounded-lg p-3 border border-gray-700">
      <div class="text-xs text-gray-400 mb-0.5">BP</div>
      <div class="text-2xl font-bold tabular-nums text-orange-400">
        {{ Math.round(v.systolic_bp) }}<span class="text-gray-500">/</span>{{ Math.round(v.diastolic_bp) }}
        <span class="text-xs font-normal text-gray-500">mmHg</span>
      </div>
    </div>

    <!-- 血流动力学（折叠区域） -->
    <div class="bg-gray-800 rounded-lg border border-gray-700">
      <button
        class="w-full flex items-center justify-between px-3 py-2 text-xs text-gray-400 hover:text-gray-300 transition-colors"
        @click="showHemodynamics = !showHemodynamics"
      >
        <span class="font-medium">血流动力学</span>
        <component :is="showHemodynamics ? ChevronUp : ChevronDown" :size="14" />
      </button>

      <div v-if="showHemodynamics" class="px-3 pb-3">
        <div class="grid grid-cols-3 gap-2">
          <!-- CO -->
          <div class="text-center">
            <div class="text-[10px] text-gray-500 mb-0.5">CO</div>
            <div :class="['text-sm font-bold tabular-nums', coColor]">
              {{ v.cardiac_output.toFixed(1) }}
            </div>
            <div class="text-[10px] text-gray-500">L/min</div>
          </div>
          <!-- EF -->
          <div class="text-center">
            <div class="text-[10px] text-gray-500 mb-0.5">EF</div>
            <div :class="['text-sm font-bold tabular-nums', efColor]">
              {{ v.ejection_fraction.toFixed(0) }}
            </div>
            <div class="text-[10px] text-gray-500">%</div>
          </div>
          <!-- SV -->
          <div class="text-center">
            <div class="text-[10px] text-gray-500 mb-0.5">SV</div>
            <div :class="['text-sm font-bold tabular-nums', svColor]">
              {{ v.stroke_volume.toFixed(0) }}
            </div>
            <div class="text-[10px] text-gray-500">mL</div>
          </div>
        </div>
      </div>
    </div>

    <!-- 血氧 -->
    <div class="bg-gray-800 rounded-lg p-3 border border-gray-700">
      <div class="text-xs text-gray-400 mb-0.5">SpO2</div>
      <div :class="['text-2xl font-bold tabular-nums', spo2Color]">
        {{ v.spo2.toFixed(1) }}
        <span class="text-xs font-normal text-gray-500">%</span>
      </div>
    </div>

    <!-- 体温 -->
    <div class="bg-gray-800 rounded-lg p-3 border border-gray-700">
      <div class="text-xs text-gray-400 mb-0.5">Temp</div>
      <div class="text-2xl font-bold tabular-nums text-pink-400">
        {{ v.temperature.toFixed(1) }}
        <span class="text-xs font-normal text-gray-500">&#176;C</span>
      </div>
    </div>

    <!-- 呼吸频率 -->
    <div class="bg-gray-800 rounded-lg p-3 border border-gray-700">
      <div class="text-xs text-gray-400 mb-0.5">RR</div>
      <div class="text-2xl font-bold tabular-nums text-blue-400">
        {{ Math.round(v.respiratory_rate) }}
        <span class="text-xs font-normal text-gray-500">/min</span>
      </div>
    </div>

    <!-- 电生理传导（折叠区域） -->
    <div class="bg-gray-800 rounded-lg border border-gray-700">
      <button
        class="w-full flex items-center justify-between px-3 py-2 text-xs text-gray-400 hover:text-gray-300 transition-colors"
        @click="showConduction = !showConduction"
      >
        <span class="font-medium">电生理传导</span>
        <component :is="showConduction ? ChevronUp : ChevronDown" :size="14" />
      </button>

      <div v-if="showConduction" class="px-3 pb-3 space-y-2.5">
        <!-- 传导通路示意 -->
        <div class="flex items-center gap-1 text-[10px]">
          <div class="flex items-center gap-1">
            <span :class="['w-2 h-2 rounded-full', nodeColor(v.conduction.sa_state)]" />
            <span class="text-gray-400">SA</span>
          </div>
          <span class="text-gray-600">→</span>
          <div class="flex items-center gap-1">
            <span :class="['w-2 h-2 rounded-full', nodeColor(v.conduction.av_state)]" />
            <span class="text-gray-400">AV</span>
          </div>
          <span class="text-gray-600">→</span>
          <div class="flex items-center gap-1">
            <span :class="['w-2 h-2 rounded-full', nodeColor(v.conduction.his_state)]" />
            <span class="text-gray-400">His</span>
          </div>
          <span class="text-gray-600">→</span>
          <div class="flex items-center gap-1">
            <span :class="['w-2 h-2 rounded-full', nodeColor(v.conduction.purkinje_state)]" />
            <span class="text-gray-400">Purk</span>
          </div>
        </div>

        <!-- PR 间期 & QRS 时限 -->
        <div class="grid grid-cols-2 gap-2">
          <div>
            <div class="text-[10px] text-gray-500 mb-0.5">PR interval</div>
            <div :class="['text-sm font-bold tabular-nums', prColor]">
              {{ v.conduction.pr_interval_ms > 0 ? Math.round(v.conduction.pr_interval_ms) : '—' }}
              <span class="text-[10px] font-normal text-gray-500">ms</span>
            </div>
          </div>
          <div>
            <div class="text-[10px] text-gray-500 mb-0.5">QRS duration</div>
            <div :class="['text-sm font-bold tabular-nums', qrsColor]">
              {{ Math.round(v.conduction.qrs_duration_ms) }}
              <span class="text-[10px] font-normal text-gray-500">ms</span>
            </div>
          </div>
        </div>

        <!-- AV 传导延迟 -->
        <div>
          <div class="text-[10px] text-gray-500 mb-0.5">AV 延迟</div>
          <div class="text-sm font-bold tabular-nums text-violet-400">
            {{ Math.round(v.conduction.av_delay_ms) }}
            <span class="text-[10px] font-normal text-gray-500">ms</span>
          </div>
        </div>

        <!-- 状态标记 -->
        <div class="flex flex-wrap gap-1.5">
          <span
            v-if="v.conduction.svt_active"
            class="inline-flex items-center px-1.5 py-0.5 text-[10px] bg-yellow-900/50 text-yellow-300 rounded-full border border-yellow-700"
          >
            ⚡ SVT 折返
          </span>
          <span
            v-if="v.conduction.av_block_degree > 0"
            class="inline-flex items-center px-1.5 py-0.5 text-[10px] bg-red-900/50 text-red-300 rounded-full border border-red-700"
          >
            🚫 {{ v.conduction.av_block_degree }}° AVB
          </span>
          <span
            v-if="!v.conduction.p_wave_present"
            class="inline-flex items-center px-1.5 py-0.5 text-[10px] bg-gray-700 text-gray-400 rounded-full"
          >
            无 P 波
          </span>
          <span
            v-if="v.conduction.p_wave_retrograde"
            class="inline-flex items-center px-1.5 py-0.5 text-[10px] bg-purple-900/50 text-purple-300 rounded-full border border-purple-700"
          >
            ↩ 逆行 P 波
          </span>
        </div>

        <!-- 拍类型 -->
        <div class="text-[10px] text-gray-500">
          上次拍类型：<span class="text-gray-300">{{
            {
              sinus: '窦性',
              svt_reentry: 'SVT折返',
              pvc: 'PVC',
              af: '房颤',
              escape: '逸搏',
              none: '—',
            }[v.conduction.last_beat_type] || v.conduction.last_beat_type
          }}</span>
        </div>
      </div>
    </div>

    <!-- 生理状态（折叠区域） -->
    <div class="bg-gray-800 rounded-lg border border-gray-700">
      <button
        class="w-full flex items-center justify-between px-3 py-2 text-xs text-gray-400 hover:text-gray-300 transition-colors"
        @click="showPhysio = !showPhysio"
      >
        <span class="font-medium">生理状态</span>
        <component :is="showPhysio ? ChevronUp : ChevronDown" :size="14" />
      </button>

      <div v-if="showPhysio" class="px-3 pb-3 space-y-2.5">
        <!-- 自主神经平衡 -->
        <div>
          <div class="text-[10px] text-gray-500 mb-1">自主神经平衡</div>
          <div class="flex items-center gap-1.5">
            <span class="text-[10px] text-red-400 w-6">交感</span>
            <div class="flex-1 h-2 bg-gray-700 rounded-full overflow-hidden flex">
              <div
                class="h-full bg-red-400 transition-all"
                :style="{ width: (v.sympathetic_tone * 100) + '%' }"
              />
            </div>
            <span class="text-[10px] text-gray-500 w-8 text-right tabular-nums">
              {{ (v.sympathetic_tone * 100).toFixed(0) }}%
            </span>
          </div>
          <div class="flex items-center gap-1.5 mt-1">
            <span class="text-[10px] text-blue-400 w-6">副交</span>
            <div class="flex-1 h-2 bg-gray-700 rounded-full overflow-hidden flex">
              <div
                class="h-full bg-blue-400 transition-all"
                :style="{ width: (v.parasympathetic_tone * 100) + '%' }"
              />
            </div>
            <span class="text-[10px] text-gray-500 w-8 text-right tabular-nums">
              {{ (v.parasympathetic_tone * 100).toFixed(0) }}%
            </span>
          </div>
        </div>

        <!-- 异位灶易激惹性 -->
        <div>
          <div class="flex justify-between text-[10px] mb-1">
            <span class="text-gray-500">异位灶易激惹性</span>
            <span class="text-gray-400 tabular-nums">{{ (v.ectopic_irritability * 100).toFixed(0) }}%</span>
          </div>
          <div class="h-2 bg-gray-700 rounded-full overflow-hidden">
            <div
              :class="['h-full transition-all rounded-full', irrColor]"
              :style="{ width: (v.ectopic_irritability * 100) + '%' }"
            />
          </div>
        </div>

        <!-- 疲劳度 -->
        <div>
          <div class="flex justify-between text-[10px] mb-1">
            <span class="text-gray-500">疲劳度</span>
            <span class="text-gray-400 tabular-nums">{{ (v.fatigue_accumulated * 100).toFixed(0) }}%</span>
          </div>
          <div class="h-2 bg-gray-700 rounded-full overflow-hidden">
            <div
              class="h-full bg-amber-400 transition-all rounded-full"
              :style="{ width: (v.fatigue_accumulated * 100) + '%' }"
            />
          </div>
        </div>

        <!-- 状态药丸 -->
        <div v-if="activeStates.length > 0" class="flex flex-wrap gap-1.5 pt-1">
          <span
            v-for="s in activeStates"
            :key="s.label"
            class="inline-flex items-center gap-0.5 px-1.5 py-0.5 text-[10px] bg-gray-700 text-gray-300 rounded-full"
          >
            {{ s.icon }} {{ s.label }}
          </span>
        </div>
      </div>
    </div>

    <!-- 电解质（折叠区域） -->
    <div class="bg-gray-800 rounded-lg border border-gray-700">
      <button
        class="w-full flex items-center justify-between px-3 py-2 text-xs text-gray-400 hover:text-gray-300 transition-colors"
        @click="showElectrolytes = !showElectrolytes"
      >
        <span class="font-medium">电解质</span>
        <component :is="showElectrolytes ? ChevronUp : ChevronDown" :size="14" />
      </button>

      <div v-if="showElectrolytes" class="px-3 pb-3 space-y-2">
        <!-- K⁺ -->
        <div class="flex items-center justify-between">
          <span class="text-[10px] text-gray-500">K⁺</span>
          <div :class="['text-sm font-bold tabular-nums', kColor]">
            {{ v.potassium_level.toFixed(1) }}
            <span class="text-[10px] font-normal text-gray-500">mEq/L</span>
          </div>
        </div>
        <div class="h-1.5 bg-gray-700 rounded-full overflow-hidden">
          <div
            :class="['h-full transition-all rounded-full', v.potassium_level < 3.5 || v.potassium_level > 5.5 ? 'bg-red-400' : v.potassium_level < 4.0 || v.potassium_level > 5.0 ? 'bg-yellow-400' : 'bg-green-400']"
            :style="{ width: Math.min(100, ((v.potassium_level - 2.5) / (7.0 - 2.5)) * 100) + '%' }"
          />
        </div>

        <!-- Ca²⁺ -->
        <div class="flex items-center justify-between mt-2">
          <span class="text-[10px] text-gray-500">Ca²⁺</span>
          <div :class="['text-sm font-bold tabular-nums', caColor]">
            {{ v.calcium_level.toFixed(1) }}
            <span class="text-[10px] font-normal text-gray-500">mg/dL</span>
          </div>
        </div>
        <div class="h-1.5 bg-gray-700 rounded-full overflow-hidden">
          <div
            :class="['h-full transition-all rounded-full', v.calcium_level < 8.5 || v.calcium_level > 10.5 ? 'bg-red-400' : v.calcium_level < 9.0 || v.calcium_level > 10.0 ? 'bg-yellow-400' : 'bg-green-400']"
            :style="{ width: Math.min(100, ((v.calcium_level - 6.0) / (14.0 - 6.0)) * 100) + '%' }"
          />
        </div>
      </div>
    </div>

    <!-- 药物浓度（折叠区域，仅有活跃药物时显示） -->
    <div v-if="activeMeds.length > 0" class="bg-gray-800 rounded-lg border border-gray-700">
      <button
        class="w-full flex items-center justify-between px-3 py-2 text-xs text-gray-400 hover:text-gray-300 transition-colors"
        @click="showMedications = !showMedications"
      >
        <span class="font-medium">药物浓度 <span class="text-purple-400">({{ activeMeds.length }})</span></span>
        <component :is="showMedications ? ChevronUp : ChevronDown" :size="14" />
      </button>

      <div v-if="showMedications" class="px-3 pb-3 space-y-2">
        <div v-for="med in activeMeds" :key="med.label">
          <div class="flex justify-between text-[10px] mb-0.5">
            <span class="text-gray-400">{{ med.label }}</span>
            <span class="text-purple-400 tabular-nums">{{ (med.level * 100).toFixed(0) }}%</span>
          </div>
          <div class="h-1.5 bg-gray-700 rounded-full overflow-hidden">
            <div
              class="h-full bg-purple-400 transition-all rounded-full"
              :style="{ width: (med.level * 100) + '%' }"
            />
          </div>
        </div>
      </div>
    </div>

    <!-- 心脏结构（折叠区域，仅异常时显示） -->
    <div v-if="hasCardiacAbnormality" class="bg-gray-800 rounded-lg border border-gray-700">
      <button
        class="w-full flex items-center justify-between px-3 py-2 text-xs text-gray-400 hover:text-gray-300 transition-colors"
        @click="showCardiac = !showCardiac"
      >
        <span class="font-medium">心脏结构</span>
        <component :is="showCardiac ? ChevronUp : ChevronDown" :size="14" />
      </button>

      <div v-if="showCardiac" class="px-3 pb-3 space-y-2">
        <!-- 杂音 -->
        <div v-if="v.murmur_severity > 0">
          <div class="flex justify-between text-[10px] mb-0.5">
            <span class="text-gray-400">杂音 ({{ v.murmur_type || '未分类' }})</span>
            <span class="text-red-400 tabular-nums">{{ (v.murmur_severity * 100).toFixed(0) }}%</span>
          </div>
          <div class="h-1.5 bg-gray-700 rounded-full overflow-hidden">
            <div
              class="h-full bg-red-400 transition-all rounded-full"
              :style="{ width: (v.murmur_severity * 100) + '%' }"
            />
          </div>
        </div>

        <!-- 损伤程度 -->
        <div v-if="v.damage_level > 0.1">
          <div class="flex justify-between text-[10px] mb-0.5">
            <span class="text-gray-400">损伤程度</span>
            <span class="text-orange-400 tabular-nums">{{ (v.damage_level * 100).toFixed(0) }}%</span>
          </div>
          <div class="h-1.5 bg-gray-700 rounded-full overflow-hidden">
            <div
              class="h-full bg-orange-400 transition-all rounded-full"
              :style="{ width: (v.damage_level * 100) + '%' }"
            />
          </div>
        </div>

        <!-- PVC 模式 -->
        <div v-if="v.rhythm === 'pvc'" class="flex items-center gap-1.5">
          <span class="text-[10px] text-gray-400">PVC 模式:</span>
          <span class="text-[10px] text-orange-300 bg-orange-900/50 px-1.5 py-0.5 rounded-full border border-orange-700">
            {{ pvcPatternLabel }}
          </span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * CmdVitalsSidebar — 右侧固定窄栏，生命体征卡片 + 心跳脉冲动画
 */
import { ref, watch, computed } from 'vue'
import { Settings, ChevronDown, ChevronUp } from 'lucide-vue-next'
import { useVirtualHumanStore } from '@/store/virtualHuman'

const store = useVirtualHumanStore()
const expanded = ref(false)

const emit = defineEmits<{ (e: 'open-controls'): void }>()

// Pulse animation trigger: restart CSS animation when HR changes
const pulseKey = ref(0)
let lastHr = store.vitals.heart_rate
watch(() => store.vitals.heart_rate, (hr) => {
  if (Math.abs(hr - lastHr) > 0.5) {
    pulseKey.value++
    lastHr = hr
  }
})

type VitalDef = {
  key: string; label: string; unit: string
  getValue: () => string; getColor: () => string
  barColor: string; pulse?: boolean
}

function hrColor(): string {
  const hr = store.vitals.heart_rate
  if (hr < 50 || hr > 120) return '#FF3B30'
  if (hr < 60 || hr > 100) return '#FF9500'
  return '#34C759'
}
function bpColor(): string {
  const s = store.vitals.systolic_bp
  if (s > 180 || s < 90) return '#FF3B30'
  if (s > 140 || s < 100) return '#FF9500'
  return '#F2F2F7'
}
function spo2Color(): string {
  const v = store.vitals.spo2
  if (v < 90) return '#FF3B30'
  if (v < 95) return '#FF9500'
  return '#5AC8FA'
}

const vitals: VitalDef[] = [
  { key: 'hr', label: 'HR', unit: 'bpm', barColor: '#34C759', pulse: true,
    getValue: () => String(Math.round(store.vitals.heart_rate)),
    getColor: hrColor },
  { key: 'bp', label: 'BP', unit: 'mmHg', barColor: '#F2F2F7',
    getValue: () => `${Math.round(store.vitals.systolic_bp)}/${Math.round(store.vitals.diastolic_bp)}`,
    getColor: bpColor },
  { key: 'spo2', label: 'SpO₂', unit: '%', barColor: '#5AC8FA',
    getValue: () => String(Math.round(store.vitals.spo2)),
    getColor: spo2Color },
  { key: 'temp', label: 'Temp', unit: '°C', barColor: '#F2F2F7',
    getValue: () => store.vitals.temperature.toFixed(1),
    getColor: () => store.vitals.temperature > 37.5 ? '#FF9500' : '#F2F2F7' },
  { key: 'rr', label: 'RR', unit: '/min', barColor: '#F2F2F7',
    getValue: () => String(Math.round(store.vitals.respiratory_rate)),
    getColor: () => '#F2F2F7' },
  { key: 'co', label: 'CO', unit: 'L/min', barColor: '#34C759',
    getValue: () => store.vitals.cardiac_output.toFixed(1),
    getColor: () => store.vitals.cardiac_output < 4 ? '#FF9500' : '#34C759' },
]
</script>

<template>
  <aside class="flex flex-col h-full shrink-0 overflow-y-auto overflow-x-hidden"
         style="width: var(--cmd-sidebar-width, 240px);
                background: var(--cmd-surface);
                backdrop-filter: blur(24px) saturate(1.5);
                -webkit-backdrop-filter: blur(24px) saturate(1.5);
                border-left: 1px solid var(--cmd-border)">
    <!-- Vital cards -->
    <div class="flex flex-col gap-1.5 p-3">
      <div v-for="v in vitals" :key="v.key"
           class="relative flex items-center gap-3 px-3 py-2.5 rounded-xl
                  border border-white/[0.04] bg-white/[0.02]
                  hover:bg-white/[0.04] transition-colors duration-200"
           :class="{ 'cmd-pulse-beat': v.pulse }"
           :style="v.pulse ? `animation-iteration-count: 1; --pulse-key: ${pulseKey}` : ''">
        <!-- Left color bar -->
        <div class="w-[2px] h-8 rounded-full shrink-0" :style="{ background: v.barColor, opacity: 0.7 }" />
        <!-- Content -->
        <div class="flex-1 min-w-0">
          <div class="flex items-baseline justify-between">
            <span class="text-[10px] font-medium text-white/35 uppercase tracking-wider">{{ v.label }}</span>
            <span class="text-[9px] text-white/20" style="font-family: var(--cmd-font-mono)">{{ v.unit }}</span>
          </div>
          <div class="text-[22px] font-bold leading-tight tabular-nums mt-0.5"
               :style="{ color: v.getColor(), fontFamily: 'var(--cmd-font-mono)' }">
            {{ v.getValue() }}
          </div>
        </div>
      </div>
    </div>

    <!-- Expand/collapse for extended vitals -->
    <button class="flex items-center justify-center gap-1 py-1.5 text-[10px] text-white/25
                   hover:text-white/40 transition-colors border-t border-white/[0.04]"
            @click="expanded = !expanded">
      <component :is="expanded ? ChevronUp : ChevronDown" :size="12" />
      {{ expanded ? '收起' : '更多指标' }}
    </button>

    <!-- Extended vitals -->
    <Transition name="slide">
      <div v-if="expanded" class="flex flex-col gap-1 px-3 pb-2 text-[11px]" style="font-family: var(--cmd-font-mono)">
        <div class="flex justify-between text-white/30">
          <span>EF</span><span class="text-white/60">{{ store.vitals.ejection_fraction.toFixed(0) }}%</span>
        </div>
        <div class="flex justify-between text-white/30">
          <span>SV</span><span class="text-white/60">{{ store.vitals.stroke_volume.toFixed(0) }} mL</span>
        </div>
        <div class="flex justify-between text-white/30">
          <span>Symp</span><span class="text-white/60">{{ store.vitals.sympathetic_tone.toFixed(2) }}</span>
        </div>
        <div class="flex justify-between text-white/30">
          <span>Para</span><span class="text-white/60">{{ store.vitals.parasympathetic_tone.toFixed(2) }}</span>
        </div>
        <div class="flex justify-between text-white/30">
          <span>K⁺</span><span class="text-white/60">{{ store.vitals.potassium_level.toFixed(1) }}</span>
        </div>
        <div class="flex justify-between text-white/30">
          <span>Ca²⁺</span><span class="text-white/60">{{ store.vitals.calcium_level.toFixed(1) }}</span>
        </div>
        <div class="flex justify-between text-white/30">
          <span>PR</span><span class="text-white/60">{{ store.vitals.conduction.pr_interval_ms }}ms</span>
        </div>
        <div class="flex justify-between text-white/30">
          <span>QRS</span><span class="text-white/60">{{ store.vitals.conduction.qrs_duration_ms }}ms</span>
        </div>
      </div>
    </Transition>

    <!-- Spacer -->
    <div class="flex-1" />

    <!-- Control panel entry -->
    <div class="p-3 border-t border-white/[0.04]">
      <button class="w-full h-9 flex items-center justify-center gap-2
                     text-[12px] font-semibold text-[#007AFF]
                     bg-[#007AFF]/8 border border-[#007AFF]/20 rounded-full
                     hover:bg-[#007AFF]/15 transition-all duration-200"
              style="border-radius: 980px; transition-timing-function: var(--cmd-ease-spring)"
              @click="emit('open-controls')">
        <Settings :size="14" />
        控制面板
      </button>
    </div>
  </aside>
</template>

<style scoped>
.slide-enter-active, .slide-leave-active {
  transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
  overflow: hidden;
}
.slide-enter-from, .slide-leave-to {
  max-height: 0; opacity: 0;
}
.slide-enter-to, .slide-leave-from {
  max-height: 200px; opacity: 1;
}
</style>

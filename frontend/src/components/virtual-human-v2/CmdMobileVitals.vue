<script setup lang="ts">
/**
 * CmdMobileVitals — 移动端底部生命体征水平条
 *
 * 替代桌面端的 CmdVitalsSidebar，在小屏上提供紧凑的水平滚动布局。
 * 点击任意指标可展开详情抽屉，点击齿轮打开控制面板。
 */
import { ref, computed } from 'vue'
import { Settings, ChevronUp, X } from 'lucide-vue-next'
import { useVirtualHumanStore } from '@/store/virtualHuman'
import { nextZIndex } from '@/constants/zIndex'

const store = useVirtualHumanStore()
const emit = defineEmits<{ (e: 'open-controls'): void }>()

const showDrawer = ref(false)
const drawerZ = ref(0)

function toggleDrawer() {
  if (!showDrawer.value) {
    drawerZ.value = nextZIndex()
  }
  showDrawer.value = !showDrawer.value
}

function hrColor(): string {
  const hr = store.vitals.heart_rate
  if (hr < 50 || hr > 120) return '#FF3B30'
  if (hr < 60 || hr > 100) return '#FF9500'
  return '#34C759'
}

function spo2Color(): string {
  const v = store.vitals.spo2
  if (v < 90) return '#FF3B30'
  if (v < 95) return '#FF9500'
  return '#5AC8FA'
}

const vitals = computed(() => [
  { key: 'hr', label: 'HR', value: Math.round(store.vitals.heart_rate), unit: 'bpm', color: hrColor() },
  { key: 'bp', label: 'BP', value: `${Math.round(store.vitals.systolic_bp)}/${Math.round(store.vitals.diastolic_bp)}`, unit: '', color: '#F2F2F7' },
  { key: 'spo2', label: 'SpO₂', value: Math.round(store.vitals.spo2), unit: '%', color: spo2Color() },
  { key: 'temp', label: 'T', value: store.vitals.temperature.toFixed(1), unit: '°C', color: store.vitals.temperature > 37.5 ? '#FF9500' : '#F2F2F7' },
  { key: 'rr', label: 'RR', value: Math.round(store.vitals.respiratory_rate), unit: '/m', color: '#F2F2F7' },
  { key: 'co', label: 'CO', value: store.vitals.cardiac_output.toFixed(1), unit: 'L', color: store.vitals.cardiac_output < 4 ? '#FF9500' : '#34C759' },
])

const extendedVitals = computed(() => [
  { label: 'EF', value: `${store.vitals.ejection_fraction.toFixed(0)}%` },
  { label: 'SV', value: `${store.vitals.stroke_volume.toFixed(0)} mL` },
  { label: 'PR', value: `${store.vitals.conduction.pr_interval_ms}ms` },
  { label: 'QRS', value: `${store.vitals.conduction.qrs_duration_ms}ms` },
  { label: 'K⁺', value: store.vitals.potassium_level.toFixed(1) },
  { label: 'Ca²⁺', value: store.vitals.calcium_level.toFixed(1) },
  { label: 'Symp', value: `${(store.vitals.sympathetic_tone * 100).toFixed(0)}%` },
  { label: 'Para', value: `${(store.vitals.parasympathetic_tone * 100).toFixed(0)}%` },
])
</script>

<template>
  <!-- Bottom vitals bar -->
  <div class="shrink-0"
       style="background: var(--cmd-glass-subtle-bg);
              backdrop-filter: var(--cmd-glass-subtle-blur);
              -webkit-backdrop-filter: var(--cmd-glass-subtle-blur);
              border-top: 1px solid var(--cmd-border)">

    <div class="flex items-center h-[52px] px-2 gap-0.5">
      <!-- Vitals chips: horizontal scroll -->
      <div class="flex-1 flex items-center gap-1.5 overflow-x-auto scrollbar-hide min-w-0">
        <button v-for="v in vitals" :key="v.key"
                class="flex items-center gap-1 px-2 py-1.5 rounded-lg shrink-0
                       bg-white/[0.03] border border-white/[0.06]
                       active:bg-white/[0.08] transition-colors"
                @click="toggleDrawer">
          <span class="text-[9px] text-white/30 uppercase">{{ v.label }}</span>
          <span class="text-[14px] font-bold tabular-nums leading-none"
                :style="{ color: v.color, fontFamily: 'var(--cmd-font-mono)' }">
            {{ v.value }}
          </span>
          <span v-if="v.unit" class="text-[8px] text-white/20">{{ v.unit }}</span>
        </button>
      </div>

      <!-- Expand button -->
      <button class="w-8 h-8 flex items-center justify-center rounded-lg shrink-0
                     bg-white/[0.05] active:bg-white/[0.12] transition-colors"
              @click="toggleDrawer">
        <ChevronUp :size="14" class="text-white/40" />
      </button>

      <!-- Control panel button -->
      <button class="w-8 h-8 flex items-center justify-center rounded-lg shrink-0
                     bg-[#007AFF]/10 active:bg-[#007AFF]/20 transition-colors"
              @click="emit('open-controls')">
        <Settings :size="14" class="text-[#007AFF]" />
      </button>
    </div>
  </div>

  <!-- Detail drawer (slide up from bottom) -->
  <Teleport to="body">
    <Transition name="mvd">
      <div v-if="showDrawer" class="fixed inset-0" :style="{ zIndex: drawerZ }">
        <!-- Backdrop -->
        <div class="absolute inset-0 bg-black/40" @click="showDrawer = false" />
        <!-- Drawer -->
        <div class="absolute bottom-0 left-0 right-0 mvd-panel">
          <!-- Handle + header -->
          <div class="flex items-center justify-between px-4 pt-3 pb-2">
            <div class="flex items-center gap-2">
              <div class="w-8 h-1 rounded-full bg-white/20" />
              <span class="text-[13px] font-semibold text-white/80"
                    style="font-family: var(--cmd-font-display)">详细指标</span>
            </div>
            <button class="w-7 h-7 flex items-center justify-center rounded-full
                           bg-white/[0.08] active:bg-white/[0.15]"
                    @click="showDrawer = false">
              <X :size="14" class="text-white/50" />
            </button>
          </div>

          <!-- Grid of vitals -->
          <div class="grid grid-cols-4 gap-2 px-4 pb-4"
               style="font-family: var(--cmd-font-mono)">
            <div v-for="ev in extendedVitals" :key="ev.label"
                 class="flex flex-col items-center py-2.5 rounded-xl bg-white/[0.03] border border-white/[0.05]">
              <span class="text-[9px] text-white/30 uppercase">{{ ev.label }}</span>
              <span class="text-[15px] font-bold text-white/70 mt-0.5">{{ ev.value }}</span>
            </div>
          </div>

          <!-- Active effects -->
          <div v-if="store.derivedActiveStates.length > 0" class="px-4 pb-4">
            <div class="text-[10px] text-white/25 uppercase mb-1.5">活跃状态</div>
            <div class="flex flex-wrap gap-1.5">
              <span v-for="effect in store.derivedActiveStates" :key="effect.label"
                    class="inline-flex items-center gap-1 px-2 py-1 rounded-full text-[10px]
                           bg-white/[0.05] border border-white/[0.08] text-white/50">
                {{ effect.icon }} {{ effect.label }}
                <span v-if="effect.value != null" class="text-white/30">{{ effect.value }}%</span>
              </span>
            </div>
          </div>

          <!-- Safe area padding for mobile -->
          <div class="h-[env(safe-area-inset-bottom,0px)]" />
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.scrollbar-hide::-webkit-scrollbar { display: none; }
.scrollbar-hide { -ms-overflow-style: none; scrollbar-width: none; }

.mvd-panel {
  max-height: 60vh;
  overflow-y: auto;
  background: rgba(20, 20, 28, 0.92);
  backdrop-filter: blur(40px) saturate(1.8);
  -webkit-backdrop-filter: blur(40px) saturate(1.8);
  border-top: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 20px 20px 0 0;
}

.mvd-enter-active { transition: opacity 0.2s ease, transform 0.3s cubic-bezier(0.16, 1, 0.3, 1); }
.mvd-leave-active { transition: opacity 0.15s ease, transform 0.2s ease; }
.mvd-enter-from, .mvd-leave-to {
  opacity: 0;
}
.mvd-enter-from .mvd-panel,
.mvd-leave-to .mvd-panel {
  transform: translateY(100%);
}
</style>

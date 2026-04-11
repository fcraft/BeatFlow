<script setup lang="ts">
/**
 * CmdWaveflowPanel — 波形流容器
 *
 * 桌面端: ECG/PCG 限高，多余空间展示实时仪表盘面板（标注+趋势+效果）
 * 移动端: ECG/PCG 弹性占满，无仪表盘
 */
import { computed } from 'vue'
import { useVirtualHumanStore } from '@/store/virtualHuman'
import CmdEcgWaveform from './CmdEcgWaveform.vue'
import CmdPcgWaveform from './CmdPcgWaveform.vue'
import CmdSyncIndicator from './CmdSyncIndicator.vue'
import CmdWaveformToolbar from './CmdWaveformToolbar.vue'
import CmdAlarmBanner from './CmdAlarmBanner.vue'
import ActiveEffectsBar from '@/components/virtual-human/ActiveEffectsBar.vue'
import EcgMultiLeadDisplay from '@/components/virtual-human/EcgMultiLeadDisplay.vue'
import ConductionTrendChart from '@/components/virtual-human/ConductionTrendChart.vue'

const store = useVirtualHumanStore()

defineProps<{
  alarms: Array<{ level: string; message: string }>
  showPv: boolean
  showAp: boolean
  showWiggers: boolean
}>()

const emit = defineEmits<{
  (e: 'toggle-pv'): void
  (e: 'toggle-ap'): void
  (e: 'toggle-wiggers'): void
}>()

/** 缓存最后有效标注 */
let _lastAnn: any = null
const cachedAnn = computed(() => {
  const arr = store.beatAnnotations
  if (arr && arr.length > 0) _lastAnn = arr[arr.length - 1]
  return _lastAnn
})

const beatKindLabels: Record<string, string> = {
  sinus: '窦性', pvc: 'PVC', af: '房颤', svt_reentry: 'SVT',
  escape: '逸搏', nsvt: 'NSVT', normal: '窦性', vt: 'VT', vf: 'VF',
}
const beatKindColors: Record<string, string> = {
  sinus: '#34C759', pvc: '#FF9500', af: '#AF52DE',
  svt_reentry: '#FFD60A', escape: '#007AFF', nsvt: '#FF3B30',
  normal: '#34C759', vt: '#FF3B30', vf: '#FF3B30',
}
</script>

<template>
  <div class="flex flex-col h-full min-h-0 gap-1 md:gap-1.5 p-1.5 md:p-2">
    <!-- Active effects (desktop only) -->
    <ActiveEffectsBar class="shrink-0 cmd-desktop-only" />

    <!-- Alarm banner -->
    <CmdAlarmBanner :alarms="alarms" />

    <!-- Waveform toolbar -->
    <CmdWaveformToolbar
      :show-pv="showPv" :show-ap="showAp" :show-wiggers="showWiggers"
      @toggle-pv="emit('toggle-pv')"
      @toggle-ap="emit('toggle-ap')"
      @toggle-wiggers="emit('toggle-wiggers')" />

    <!-- ═══ Mobile: ECG/PCG flex fill ═══ -->
    <div class="cmd-mobile-only flex flex-col flex-1 min-h-0 gap-1">
      <div class="flex-[3] min-h-[80px]">
        <CmdEcgWaveform v-if="!store.multiLeadMode" />
        <EcgMultiLeadDisplay v-else />
      </div>
      <CmdSyncIndicator />
      <div class="flex-[2] min-h-[60px]">
        <CmdPcgWaveform />
      </div>
    </div>

    <!-- ═══ Desktop: ECG/PCG constrained + dashboard panel ═══ -->
    <div class="cmd-desktop-only flex flex-col flex-1 min-h-0 gap-1.5">
      <!-- ECG -->
      <div class="cmd-ecg-track min-h-[80px]">
        <CmdEcgWaveform v-if="!store.multiLeadMode" />
        <EcgMultiLeadDisplay v-else />
      </div>

      <!-- Sync -->
      <CmdSyncIndicator />

      <!-- PCG -->
      <div class="cmd-pcg-track min-h-[60px]">
        <CmdPcgWaveform />
      </div>

      <!-- Dashboard panel: fills remaining space -->
      <div class="flex-1 min-h-[80px] flex gap-1.5 overflow-hidden">
        <!-- Left: Trend chart (always visible) -->
        <div class="flex-1 min-w-0">
          <ConductionTrendChart />
        </div>

        <!-- Right: Beat info + Active effects -->
        <div class="w-[200px] shrink-0 flex flex-col gap-1.5">
          <!-- Current beat card -->
          <div class="flex-1 rounded-lg border border-white/[0.06] bg-white/[0.03] p-2.5 flex flex-col justify-center">
            <div v-if="cachedAnn" class="space-y-2">
              <!-- Beat kind badge -->
              <div class="flex items-center gap-2">
                <span class="text-[10px] font-bold px-2 py-0.5 rounded-full"
                      :style="{
                        color: beatKindColors[cachedAnn.beat_kind] || '#6C6C70',
                        background: (beatKindColors[cachedAnn.beat_kind] || '#6C6C70') + '1a'
                      }">
                  {{ beatKindLabels[cachedAnn.beat_kind] || cachedAnn.beat_kind }}
                </span>
                <span class="text-[10px] text-white/20 tabular-nums"
                      style="font-family: var(--cmd-font-mono)">
                  {{ cachedAnn.rr_sec ? (cachedAnn.rr_sec * 1000).toFixed(0) + 'ms RR' : '' }}
                </span>
              </div>
              <!-- Intervals grid -->
              <div class="grid grid-cols-3 gap-x-2 gap-y-1">
                <div v-if="cachedAnn.pr_interval_ms != null || cachedAnn.pr_ms != null">
                  <div class="text-[8px] text-white/25 uppercase">PR</div>
                  <div class="text-[13px] font-bold tabular-nums text-[#34C759]"
                       style="font-family: var(--cmd-font-mono)">
                    {{ Math.round(cachedAnn.pr_interval_ms ?? cachedAnn.pr_ms ?? 0) }}
                    <span class="text-[8px] font-normal text-white/20">ms</span>
                  </div>
                </div>
                <div>
                  <div class="text-[8px] text-white/25 uppercase">QRS</div>
                  <div class="text-[13px] font-bold tabular-nums text-[#007AFF]"
                       style="font-family: var(--cmd-font-mono)">
                    {{ Math.round(cachedAnn.qrs_duration_ms ?? cachedAnn.qrs_ms ?? 0) }}
                    <span class="text-[8px] font-normal text-white/20">ms</span>
                  </div>
                </div>
                <div>
                  <div class="text-[8px] text-white/25 uppercase">QT</div>
                  <div class="text-[13px] font-bold tabular-nums text-[#AF52DE]"
                       style="font-family: var(--cmd-font-mono)">
                    {{ Math.round(cachedAnn.qt_interval_ms ?? cachedAnn.qt_ms ?? 0) }}
                    <span class="text-[8px] font-normal text-white/20">ms</span>
                  </div>
                </div>
              </div>
            </div>
            <div v-else class="text-[10px] text-white/20 text-center">等待心拍数据...</div>
          </div>

          <!-- Active effects compact -->
          <div v-if="store.derivedActiveStates.length > 0"
               class="shrink-0 rounded-lg border border-white/[0.06] bg-white/[0.03] px-2.5 py-2 overflow-hidden">
            <div class="flex flex-wrap gap-1">
              <span v-for="effect in store.derivedActiveStates.slice(0, 6)" :key="effect.label"
                    class="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded-full text-[9px]
                           bg-white/[0.05] border border-white/[0.06] text-white/45 whitespace-nowrap">
                {{ effect.icon }} {{ effect.label }}
              </span>
              <span v-if="store.derivedActiveStates.length > 6"
                    class="text-[9px] text-white/20 self-center">
                +{{ store.derivedActiveStates.length - 6 }}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.cmd-ecg-track {
  height: var(--cmd-ecg-max-height, 180px);
  max-height: var(--cmd-ecg-max-height, 180px);
  flex-shrink: 0;
}
.cmd-pcg-track {
  height: var(--cmd-pcg-max-height, 140px);
  max-height: var(--cmd-pcg-max-height, 140px);
  flex-shrink: 0;
}
</style>

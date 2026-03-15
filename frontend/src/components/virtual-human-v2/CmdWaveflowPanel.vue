<script setup lang="ts">
/**
 * CmdWaveflowPanel — 左侧波形流容器
 */
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
</script>

<template>
  <div class="flex flex-col h-full min-h-0 gap-1.5 p-2">
    <!-- Active effects -->
    <ActiveEffectsBar class="shrink-0" />

    <!-- Alarm banner -->
    <CmdAlarmBanner :alarms="alarms" />

    <!-- Waveform toolbar -->
    <CmdWaveformToolbar
      :show-pv="showPv" :show-ap="showAp" :show-wiggers="showWiggers"
      @toggle-pv="emit('toggle-pv')"
      @toggle-ap="emit('toggle-ap')"
      @toggle-wiggers="emit('toggle-wiggers')" />

    <!-- ECG waveform (55%) -->
    <div class="flex-[55] min-h-0">
      <CmdEcgWaveform v-if="!store.multiLeadMode" />
      <EcgMultiLeadDisplay v-else />
    </div>

    <!-- Sync indicator -->
    <CmdSyncIndicator />

    <!-- PCG waveform (35%) -->
    <div class="flex-[35] min-h-0">
      <CmdPcgWaveform />
    </div>

    <!-- Trend chart (collapsible) -->
    <div v-if="store.showTrendChart" class="shrink-0 max-h-[120px]">
      <ConductionTrendChart />
    </div>
  </div>
</template>

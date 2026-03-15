<script setup lang="ts">
/**
 * 报警横幅 — 在监护仪顶部显示当前活动报警
 */
import { computed } from 'vue'
import type { AlarmState } from '@/composables/useAlarmSystem'

const props = defineProps<{
  alarms: AlarmState[]
}>()

const hasCritical = computed(() => props.alarms.some(a => a.level === 'critical'))
const bannerClass = computed(() =>
  hasCritical.value
    ? 'bg-red-500/20 border-red-500/40 text-red-300'
    : 'bg-yellow-500/20 border-yellow-500/40 text-yellow-300'
)
</script>

<template>
  <Transition name="alarm-slide">
    <div
      v-if="alarms.length > 0"
      :class="['flex items-center gap-3 px-4 py-2 border rounded-lg text-sm alarm-pulse', bannerClass]"
    >
      <span class="font-bold text-base">{{ hasCritical ? '🚨' : '⚠️' }}</span>
      <div class="flex-1 flex flex-wrap gap-2">
        <span
          v-for="(alarm, i) in alarms"
          :key="i"
          class="text-xs"
        >
          {{ alarm.message }}
        </span>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.alarm-pulse {
  animation: alarm-flash 1s ease-in-out infinite;
}
@keyframes alarm-flash {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.7; }
}
.alarm-slide-enter-active,
.alarm-slide-leave-active {
  transition: all 0.3s ease;
}
.alarm-slide-enter-from,
.alarm-slide-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}
</style>

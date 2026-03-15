<script setup lang="ts">
/**
 * CmdAlarmBanner — 报警横幅 (危急/警告两级脉冲动画)
 */
defineProps<{ alarms: Array<{ level: string; message: string }> }>()
</script>

<template>
  <div v-if="alarms.length > 0" class="flex flex-col gap-1 shrink-0">
    <div v-for="(alarm, i) in alarms" :key="i"
         class="flex items-center gap-2 px-3 py-1.5 rounded-xl text-xs font-semibold"
         :class="alarm.level === 'critical'
           ? 'bg-[#FF3B30]/15 text-[#FF3B30] border border-[#FF3B30]/25'
           : 'bg-[#FF9500]/12 text-[#FF9500] border border-[#FF9500]/20'"
         :style="alarm.level === 'critical' ? 'animation: cmd-alarm-pulse 1s ease-in-out infinite' : ''">
      <span class="w-2 h-2 rounded-full shrink-0"
            :class="alarm.level === 'critical' ? 'bg-[#FF3B30]' : 'bg-[#FF9500]'" />
      {{ alarm.message }}
    </div>
  </div>
</template>

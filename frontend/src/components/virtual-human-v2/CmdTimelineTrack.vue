<script setup lang="ts">
/**
 * CmdTimelineTrack — 底部时间线轨道 (36px)
 * 左: simTime | 中: 活跃效果 chips | 右: 当前拍信息
 */
import { computed } from 'vue'
import { useVirtualHumanStore } from '@/store/virtualHuman'
import { useConnectionStore } from '@/store/connection'

const store = useVirtualHumanStore()
const connectionStore = useConnectionStore()

function fmt(sec: number): string {
  const m = Math.floor(sec / 60)
  const s = Math.floor(sec % 60)
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}

const ann = computed(() => {
  const a = store.beatAnnotations
  return a.length > 0 ? a[a.length - 1] : null
})

const beatKindColors: Record<string, string> = {
  sinus: '#34C759', pvc: '#FF9500', af: '#AF52DE',
  svt_reentry: '#FFD60A', escape: '#007AFF', nsvt: '#FF3B30', normal: '#34C759',
}
</script>

<template>
  <footer v-if="store.connected"
          class="h-9 flex items-center gap-4 px-4 shrink-0 select-none"
          style="background: var(--cmd-glass-subtle-bg);
                 backdrop-filter: var(--cmd-glass-subtle-blur);
                 -webkit-backdrop-filter: var(--cmd-glass-subtle-blur);
                 border-top: 1px solid var(--cmd-border)">
    <!-- SimTime -->
    <span class="text-[11px] text-white/40 tabular-nums shrink-0"
          style="font-family: var(--cmd-font-mono)">
      {{ fmt(connectionStore.simTime) }}
    </span>

    <!-- Active effects chips -->
    <div class="flex-1 flex items-center gap-1.5 overflow-x-auto min-w-0 scrollbar-hide">
      <span v-for="effect in store.derivedActiveStates" :key="effect.label"
            class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[9px] font-semibold
                   bg-white/[0.05] border border-white/[0.08] text-white/50 shrink-0 whitespace-nowrap">
        <span>{{ effect.icon }}</span>
        {{ effect.label }}
        <span v-if="effect.value != null" class="text-white/30">{{ effect.value }}%</span>
      </span>
    </div>

    <!-- Current beat info -->
    <div v-if="ann" class="flex items-center gap-2 shrink-0" style="font-family: var(--cmd-font-mono)">
      <span class="text-[10px] font-bold px-1.5 py-0.5 rounded"
            :style="{ color: beatKindColors[ann.beat_kind] || '#6C6C70',
                      background: (beatKindColors[ann.beat_kind] || '#6C6C70') + '1a' }">
        {{ ann.beat_kind }}
      </span>
      <span class="text-[10px] text-white/25">
        PR {{ ann.pr_interval_ms?.toFixed(0) ?? '—' }}
        QRS {{ ann.qrs_duration_ms?.toFixed(0) ?? '—' }}
        QT {{ ann.qt_interval_ms?.toFixed(0) ?? '—' }}
      </span>
    </div>
  </footer>
</template>

<style scoped>
.scrollbar-hide::-webkit-scrollbar { display: none; }
.scrollbar-hide { -ms-overflow-style: none; scrollbar-width: none; }
</style>

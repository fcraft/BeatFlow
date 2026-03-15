<script setup lang="ts">
/**
 * CmdStatusBar — 极简顶部状态条 (40px)
 * 左: 连接圆点 + 标题 + simTime
 * 右: 档案名 + 录制 + 静音 + 卡尺 + 导出 + 保存 + 断开
 */
import { computed } from 'vue'
import { Save, Volume2, VolumeX, Menu, LogOut } from 'lucide-vue-next'
import { useVirtualHumanStore } from '@/store/virtualHuman'
import { useConnectionStore } from '@/store/connection'
import { exportCanvasAsPng } from '@/composables/useRhythmStripExport'
import RecordingPanel from '@/components/virtual-human/RecordingPanel.vue'

const store = useVirtualHumanStore()
const connectionStore = useConnectionStore()

const emit = defineEmits<{
  (e: 'open-nav'): void
  (e: 'export'): void
}>()

function formatTime(sec: number): string {
  const m = Math.floor(sec / 60)
  const s = Math.floor(sec % 60)
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}

const simTimeStr = computed(() =>
  store.connected ? formatTime(connectionStore.simTime) : '--:--'
)
</script>

<template>
  <header class="h-10 flex items-center justify-between px-4 shrink-0 select-none"
          style="font-family: var(--cmd-font-display)">
    <!-- Left -->
    <div class="flex items-center gap-3">
      <button class="w-8 h-8 flex items-center justify-center rounded-lg
                     hover:bg-white/[0.08] transition-colors duration-200"
              title="导航" @click="emit('open-nav')">
        <Menu :size="16" class="text-white/50" />
      </button>
      <div class="w-2 h-2 rounded-full shrink-0"
           :class="store.connected
             ? 'bg-[#34C759] shadow-[0_0_0_0_rgba(52,199,89,0.5)]'
             : 'bg-[#FF3B30]'"
           :style="store.connected ? 'animation: cmd-dot-pulse 2s ease-in-out infinite' : ''" />
      <span class="text-[15px] font-semibold tracking-[-0.02em] text-white/85">
        Virtual Patient
      </span>
      <span class="text-xs text-white/30 tabular-nums"
            style="font-family: var(--cmd-font-mono)">
        {{ simTimeStr }}
      </span>
    </div>

    <!-- Right -->
    <div class="flex items-center gap-2">
      <span v-if="store.profileName"
            class="text-[11px] font-medium text-[#34C759] bg-[#34C759]/10
                   px-2.5 py-0.5 rounded-full border border-[#34C759]/20">
        {{ store.profileName }}
      </span>
      <RecordingPanel v-if="store.connected" />
      <button v-if="store.connected"
              class="w-8 h-8 flex items-center justify-center rounded-lg
                     hover:bg-white/[0.08] transition-colors duration-200"
              :title="store.alarmMuted ? '取消静音' : '静音报警'"
              @click="store.alarmMuted = !store.alarmMuted">
        <component :is="store.alarmMuted ? VolumeX : Volume2" :size="14"
                   class="text-white/50 hover:text-white/90 transition-colors" />
      </button>
      <button v-if="store.connected"
              class="w-8 h-8 flex items-center justify-center rounded-lg
                     hover:bg-white/[0.08] transition-colors duration-200"
              :class="{ 'bg-[#007AFF]/15': store.caliperMode }"
              title="卡尺测量" @click="store.caliperMode = !store.caliperMode">
        <span class="text-sm" :class="store.caliperMode ? 'text-[#007AFF]' : 'text-white/50'">📐</span>
      </button>
      <button v-if="store.connected"
              class="w-8 h-8 flex items-center justify-center rounded-lg
                     hover:bg-white/[0.08] transition-colors duration-200"
              title="导出节律条" @click="emit('export')">
        <span class="text-sm text-white/50">📷</span>
      </button>
      <button v-if="store.connected && store.selectedProfileId"
              class="h-7 px-3 text-[11px] font-semibold text-[#007AFF]
                     border border-[#007AFF]/30 rounded-full
                     hover:bg-[#007AFF]/10 transition-all duration-200"
              style="border-radius: 980px"
              @click="store.saveState()">
        <Save :size="12" class="inline mr-1" />保存
      </button>
      <button v-if="store.connected"
              class="h-7 px-3 text-[11px] font-medium text-white/40
                     border border-white/15 rounded-full
                     hover:bg-white/[0.06] hover:text-white/60 transition-all duration-200"
              style="border-radius: 980px"
              @click="store.disconnect()">
        断开
      </button>
    </div>
  </header>
</template>

<script setup lang="ts">
/**
 * CmdStatusBar — 极简顶部状态条
 *
 * 桌面 (40px): 连接圆点 + 标题 + simTime | 档案名 + 录制 + 静音 + 卡尺 + 导出 + 保存 + 断开
 * 移动 (44px): 汉堡菜单 + 圆点 + 标题 | 保存 + 断开
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
  <header class="cmd-statusbar flex items-center justify-between px-3 md:px-4 shrink-0 select-none"
          style="font-family: var(--cmd-font-display)">
    <!-- Left -->
    <div class="flex items-center gap-2 md:gap-3 min-w-0">
      <button class="w-8 h-8 flex items-center justify-center rounded-lg
                     hover:bg-white/[0.08] transition-colors duration-200 shrink-0"
              title="导航" @click="emit('open-nav')">
        <Menu :size="16" class="text-white/50" />
      </button>
      <div class="w-2 h-2 rounded-full shrink-0"
           :class="store.connected
             ? 'bg-[#34C759] shadow-[0_0_0_0_rgba(52,199,89,0.5)]'
             : 'bg-[#FF3B30]'"
           :style="store.connected ? 'animation: cmd-dot-pulse 2s ease-in-out infinite' : ''" />
      <span class="text-[14px] md:text-[15px] font-semibold tracking-[-0.02em] text-white/85 truncate">
        Virtual Patient
      </span>
      <span class="text-xs text-white/30 tabular-nums shrink-0 cmd-desktop-only"
            style="font-family: var(--cmd-font-mono)">
        {{ simTimeStr }}
      </span>
    </div>

    <!-- Right -->
    <div class="flex items-center gap-1.5 md:gap-2 shrink-0">
      <!-- Desktop-only controls -->
      <span v-if="store.profileName"
            class="text-[11px] font-medium text-[#34C759] bg-[#34C759]/10
                   px-2.5 py-0.5 rounded-full border border-[#34C759]/20 cmd-desktop-only">
        {{ store.profileName }}
      </span>
      <RecordingPanel v-if="store.connected" class="cmd-desktop-only" />
      <button v-if="store.connected"
              class="w-8 h-8 flex items-center justify-center rounded-lg
                     hover:bg-white/[0.08] transition-colors duration-200 cmd-desktop-only"
              :title="store.alarmMuted ? '取消静音' : '静音报警'"
              @click="store.alarmMuted = !store.alarmMuted">
        <component :is="store.alarmMuted ? VolumeX : Volume2" :size="14"
                   class="text-white/50 hover:text-white/90 transition-colors" />
      </button>
      <button v-if="store.connected"
              class="w-8 h-8 flex items-center justify-center rounded-lg
                     hover:bg-white/[0.08] transition-colors duration-200 cmd-desktop-only"
              :class="{ 'bg-[#007AFF]/15': store.caliperMode }"
              title="卡尺测量" @click="store.caliperMode = !store.caliperMode">
        <span class="text-sm" :class="store.caliperMode ? 'text-[#007AFF]' : 'text-white/50'">📐</span>
      </button>
      <button v-if="store.connected"
              class="w-8 h-8 flex items-center justify-center rounded-lg
                     hover:bg-white/[0.08] transition-colors duration-200 cmd-desktop-only"
              title="导出节律条" @click="emit('export')">
        <span class="text-sm text-white/50">📷</span>
      </button>

      <!-- Always visible: save + disconnect -->
      <button v-if="store.connected && store.selectedProfileId"
              class="h-7 px-2.5 md:px-3 text-[11px] font-semibold text-[#007AFF]
                     border border-[#007AFF]/30 rounded-full
                     hover:bg-[#007AFF]/10 transition-all duration-200"
              style="border-radius: 980px"
              @click="store.saveState()">
        <Save :size="12" class="inline mr-0.5 md:mr-1" /><span class="cmd-desktop-only">保存</span>
      </button>
      <button v-if="store.connected"
              class="h-7 px-2.5 md:px-3 text-[11px] font-medium text-white/40
                     border border-white/15 rounded-full
                     hover:bg-white/[0.06] hover:text-white/60 transition-all duration-200"
              style="border-radius: 980px"
              @click="store.disconnect()">
        断开
      </button>
    </div>
  </header>
</template>

<style scoped>
.cmd-statusbar {
  height: var(--cmd-statusbar-height, 40px);
}
</style>

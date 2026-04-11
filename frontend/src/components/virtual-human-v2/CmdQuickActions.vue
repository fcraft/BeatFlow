<script setup lang="ts">
/**
 * CmdQuickActions — 桌面端快捷操作栏
 *
 * 替代电生理趋势图位置，提供控制面板中常用命令的快捷按钮。
 * 仅桌面端显示（由父组件控制 cmd-desktop-only）。
 */
import { computed } from 'vue'
import { useVirtualHumanStore } from '@/store/virtualHuman'

const store = useVirtualHumanStore()

const emit = defineEmits<{ (e: 'open-controls'): void }>()

/** 运动快捷 */
const exerciseActions = [
  { cmd: 'rest', label: '休息', icon: '😴' },
  { cmd: 'walk', label: '步行', icon: '🚶' },
  { cmd: 'jog',  label: '慢跑', icon: '🏃' },
  { cmd: 'run',  label: '跑步', icon: '💨' },
]

/** 情绪快捷 */
const emotionActions = [
  { cmd: 'startle',    label: '惊吓', icon: '😱' },
  { cmd: 'anxiety',    label: '焦虑', icon: '😰' },
  { cmd: 'relaxation', label: '放松', icon: '😌' },
]

/** 病变快捷 */
const conditionActions = [
  { cmd: 'condition_normal', label: '正常', icon: '💚' },
  { cmd: 'condition_af',     label: '房颤', icon: '💔' },
  { cmd: 'condition_pvc',    label: 'PVC',  icon: '⚡' },
  { cmd: 'condition_vf',     label: 'VF',   icon: '🔴' },
]

/** 紧急 */
const emergencyActions = [
  { cmd: 'defibrillate', label: '除颤', icon: '⚡', danger: true },
  { cmd: 'reset',        label: '重置', icon: '🔄', danger: false },
]

/** 当前运动状态高亮 */
const activeExercise = computed(() => {
  const i = store.vitals.exercise_intensity
  if (i >= 0.7) return 'run'
  if (i >= 0.4) return 'jog'
  if (i >= 0.2) return 'walk'
  if (i < 0.05) return 'rest'
  return ''
})

function send(cmd: string) {
  store.sendCommand(cmd)
}
</script>

<template>
  <div class="flex flex-col h-full min-h-0 rounded-lg border border-white/[0.06] bg-white/[0.03] p-2.5 gap-2 overflow-y-auto">
    <!-- Header -->
    <div class="flex items-center justify-between shrink-0">
      <span class="text-[10px] font-semibold text-white/40 uppercase tracking-wider">快捷操作</span>
      <button class="text-[10px] text-[#007AFF] hover:text-[#007AFF]/80 transition-colors"
              @click="emit('open-controls')">
        更多 →
      </button>
    </div>

    <!-- Exercise row -->
    <div class="shrink-0">
      <div class="text-[9px] text-white/25 mb-1">运动</div>
      <div class="flex gap-1">
        <button v-for="a in exerciseActions" :key="a.cmd"
                class="flex-1 flex items-center justify-center gap-0.5 py-1 rounded-lg text-[10px] font-medium transition-all duration-200"
                :class="activeExercise === a.cmd
                  ? 'bg-[#007AFF]/15 text-[#007AFF] border border-[#007AFF]/25'
                  : 'bg-white/[0.04] text-white/40 border border-white/[0.04] hover:bg-white/[0.08]'"
                @click="send(a.cmd)">
          <span class="text-[11px]">{{ a.icon }}</span>
          <span>{{ a.label }}</span>
        </button>
      </div>
    </div>

    <!-- Emotion row -->
    <div class="shrink-0">
      <div class="text-[9px] text-white/25 mb-1">情绪</div>
      <div class="flex gap-1">
        <button v-for="a in emotionActions" :key="a.cmd"
                class="flex-1 py-1 rounded-lg text-[10px] font-medium
                       bg-white/[0.04] text-white/40 border border-white/[0.04]
                       hover:bg-white/[0.08] transition-all duration-200"
                @click="send(a.cmd)">
          {{ a.icon }} {{ a.label }}
        </button>
      </div>
    </div>

    <!-- Condition row -->
    <div class="shrink-0">
      <div class="text-[9px] text-white/25 mb-1">病变</div>
      <div class="flex gap-1">
        <button v-for="a in conditionActions" :key="a.cmd"
                class="flex-1 py-1 rounded-lg text-[10px] font-medium transition-all duration-200"
                :class="a.cmd === 'condition_normal'
                  ? 'bg-white/[0.04] text-white/40 border border-white/[0.04] hover:bg-white/[0.08]'
                  : 'bg-[#FF3B30]/8 text-[#FF3B30]/70 border border-[#FF3B30]/15 hover:bg-[#FF3B30]/15'"
                @click="send(a.cmd)">
          {{ a.icon }} {{ a.label }}
        </button>
      </div>
    </div>

    <!-- Emergency row -->
    <div class="shrink-0">
      <div class="flex gap-1">
        <button v-for="a in emergencyActions" :key="a.cmd"
                class="flex-1 py-1 rounded-lg text-[10px] font-semibold transition-all duration-200"
                :class="a.danger
                  ? 'bg-[#FF3B30]/12 text-[#FF3B30] border border-[#FF3B30]/20 hover:bg-[#FF3B30]/25'
                  : 'bg-white/[0.04] text-white/40 border border-white/[0.04] hover:bg-white/[0.08]'"
                @click="send(a.cmd)">
          {{ a.icon }} {{ a.label }}
        </button>
      </div>
    </div>
  </div>
</template>

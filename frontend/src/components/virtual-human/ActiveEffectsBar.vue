<script setup lang="ts">
/**
 * ActiveEffectsBar — 水平药丸条，显示所有从 vitals 派生的活动效果。
 * 点击药丸可导航到对应 ControlPanel Tab。
 */
import { useVirtualHumanStore } from '@/store/virtualHuman'
import type { ActiveEffect } from '@/store/virtualHuman'

const store = useVirtualHumanStore()

/** 分类 → ControlPanel Tab key 映射 */
const categoryToTab: Record<string, string> = {
  exercise: 'exercise',
  emotion: 'emotion',
  condition: 'condition',
  medication: 'medication',
  body: 'body_state',
  electrolyte: 'medication', // 电解质在药物 Tab 中
}

/** 分类 → Tailwind 颜色类 */
const colorClasses: Record<string, { bg: string; text: string; border: string }> = {
  blue:    { bg: 'bg-blue-500/20',    text: 'text-blue-300',    border: 'border-blue-500/30' },
  amber:   { bg: 'bg-amber-500/20',   text: 'text-amber-300',   border: 'border-amber-500/30' },
  red:     { bg: 'bg-red-500/20',     text: 'text-red-300',     border: 'border-red-500/30' },
  purple:  { bg: 'bg-purple-500/20',  text: 'text-purple-300',  border: 'border-purple-500/30' },
  teal:    { bg: 'bg-teal-500/20',    text: 'text-teal-300',    border: 'border-teal-500/30' },
  emerald: { bg: 'bg-emerald-500/20', text: 'text-emerald-300', border: 'border-emerald-500/30' },
}

function getClasses(effect: ActiveEffect) {
  return colorClasses[effect.color] || colorClasses.blue
}

function formatValue(effect: ActiveEffect): string {
  if (effect.value == null) return ''
  // 电解质显示原始数值
  if (effect.category === 'electrolyte') return ` ${effect.value.toFixed(1)}`
  // 体温显示度数
  if (effect.label === '发热') return ` ${effect.value.toFixed(1)}°C`
  // 其余显示百分比
  return ` ${effect.value}%`
}

function navigate(effect: ActiveEffect) {
  const tab = categoryToTab[effect.category]
  if (tab) {
    store.controlPanelTab = tab
  }
}
</script>

<template>
  <div
    class="flex items-center gap-2 px-3 py-1.5 bg-white/[0.06] border border-white/[0.08] backdrop-blur-xl rounded-lg min-h-[36px]"
  >
    <span class="text-[10px] text-white/40 font-medium shrink-0">状态</span>

    <!-- 正常基线 -->
    <div v-if="store.derivedActiveStates.length === 0" class="flex items-center gap-1 text-xs text-emerald-400">
      <span>✓</span>
      <span>正常基线</span>
    </div>

    <!-- 活动效果药丸 -->
    <div v-else class="flex flex-wrap items-center gap-1.5">
      <button
        v-for="(effect, idx) in store.derivedActiveStates"
        :key="`${effect.category}-${effect.label}-${idx}`"
        :class="[
          'inline-flex items-center gap-1 px-2 py-0.5 text-[11px] font-medium rounded-full border transition-colors cursor-pointer hover:shadow-sm',
          getClasses(effect).bg,
          getClasses(effect).text,
          getClasses(effect).border,
        ]"
        :title="`点击切换到${effect.label}控制面板`"
        @click="navigate(effect)"
      >
        <span>{{ effect.icon }}</span>
        <span>{{ effect.label }}</span>
        <span v-if="effect.value != null" class="font-mono tabular-nums">{{ formatValue(effect) }}</span>
      </button>
    </div>
  </div>
</template>

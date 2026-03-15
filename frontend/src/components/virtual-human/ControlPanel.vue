<script setup lang="ts">
/**
 * 控制面板 — Apple Glass UI 风格
 *
 * 分段控制器切换 7 个功能 Tab，
 * activeTab 从 store.controlPanelTab 读取（跨 Tab 不丢失），
 * 图标 + 文字 + 活动效果数量徽章。
 */
import { computed, ref, type Component } from 'vue'
import { useVirtualHumanStore } from '@/store/virtualHuman'
import ExerciseTab from './ExerciseTab.vue'
import EmotionTab from './EmotionTab.vue'
import ConditionTab from './ConditionTab.vue'
import BodyStateTab from './BodyStateTab.vue'
import MedicationTab from './MedicationTab.vue'
import SettingsTab from './SettingsTab.vue'
import AuscultationPanel from './AuscultationPanel.vue'

const store = useVirtualHumanStore()

/** Tab key → 组件映射 */
const tabComponents: Record<string, Component> = {
  exercise: ExerciseTab,
  emotion: EmotionTab,
  condition: ConditionTab,
  body_state: BodyStateTab,
  medication: MedicationTab,
  auscultation: AuscultationPanel,
  settings: SettingsTab,
}

const tabs = [
  { key: 'exercise',     label: '运动',    icon: '🏃', badgeCategory: 'exercise' },
  { key: 'emotion',      label: '情绪',    icon: '😰', badgeCategory: 'emotion' },
  { key: 'condition',    label: '病变',    icon: '💔', badgeCategory: 'condition' },
  { key: 'body_state',   label: '体内',    icon: '🧬', badgeCategory: 'body' },
  { key: 'medication',   label: '药物',    icon: '💊', badgeCategory: 'medication' },
  { key: 'auscultation', label: '听诊',    icon: '🩺', badgeCategory: '' },
  { key: 'settings',     label: '设置',    icon: '⚙️', badgeCategory: '' },
] as const

/** 当前活动 Tab 对应的组件 */
const activeComponent = computed(() => tabComponents[store.controlPanelTab] || ExerciseTab)

/** Tab 对应的徽章数量 */
function getBadgeCount(badgeCategory: string): number {
  if (!badgeCategory) return 0
  if (badgeCategory === 'medication') {
    return (store.activeCountByCategory.medication || 0) + (store.activeCountByCategory.electrolyte || 0)
  }
  return store.activeCountByCategory[badgeCategory] || 0
}

/** 当前活动 tab 的索引，用于 indicator 滑动定位 */
const activeIndex = computed(() =>
  tabs.findIndex(t => t.key === store.controlPanelTab)
)
</script>

<template>
  <div class="control-panel">
    <!-- 分段控制器 -->
    <div class="seg-track">
      <!-- 滑动指示器 -->
      <div
        class="seg-indicator"
        :style="{
          width: (100 / tabs.length) + '%',
          transform: `translateX(${activeIndex * 100}%)`,
        }"
      />
      <!-- Tab 按钮 -->
      <button
        v-for="(tab, idx) in tabs"
        :key="tab.key"
        class="seg-item"
        :class="{ 'seg-item--active': store.controlPanelTab === tab.key }"
        @click="store.controlPanelTab = tab.key"
      >
        <span class="seg-icon">{{ tab.icon }}</span>
        <span class="seg-label">{{ tab.label }}</span>
        <!-- 徽章 -->
        <span
          v-if="getBadgeCount(tab.badgeCategory) > 0"
          class="seg-badge"
        >
          {{ getBadgeCount(tab.badgeCategory) }}
        </span>
      </button>
    </div>

    <!-- Tab 内容区 -->
    <div class="tab-content">
      <component :is="activeComponent" :key="store.controlPanelTab" />
    </div>
  </div>
</template>

<style scoped>
/* ── Apple Glass UI Design Tokens ── */
:root {
  --ease-apple: cubic-bezier(0.16, 1, 0.3, 1);
}

.control-panel {
  border-radius: 16px;
}

/* ── 分段控制器 (Segmented Control) ── */
.seg-track {
  position: relative;
  display: flex;
  padding: 3px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.08);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  gap: 2px;
}

.seg-indicator {
  position: absolute;
  top: 3px;
  left: 3px;
  bottom: 3px;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.12);
  backdrop-filter: blur(12px) saturate(1.5);
  -webkit-backdrop-filter: blur(12px) saturate(1.5);
  border: 1px solid rgba(255, 255, 255, 0.15);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
  transition: transform 0.35s cubic-bezier(0.16, 1, 0.3, 1);
  pointer-events: none;
  z-index: 0;
}

.seg-item {
  position: relative;
  z-index: 1;
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1px;
  padding: 6px 2px 5px;
  border-radius: 10px;
  border: none;
  background: transparent;
  cursor: pointer;
  transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1);
  -webkit-tap-highlight-color: transparent;
}

.seg-item:hover:not(.seg-item--active) {
  background: rgba(255, 255, 255, 0.04);
}

.seg-icon {
  font-size: 16px;
  line-height: 1;
  transition: transform 0.25s cubic-bezier(0.16, 1, 0.3, 1);
}

.seg-item--active .seg-icon {
  transform: scale(1.15);
}

.seg-label {
  font-size: 10px;
  font-weight: 500;
  letter-spacing: 0.02em;
  color: rgba(255, 255, 255, 0.35);
  transition: color 0.25s cubic-bezier(0.16, 1, 0.3, 1);
  white-space: nowrap;
}

.seg-item--active .seg-label {
  color: rgba(255, 255, 255, 0.9);
  font-weight: 600;
}

/* ── 徽章 ── */
.seg-badge {
  position: absolute;
  top: 2px;
  right: calc(50% - 18px);
  min-width: 14px;
  height: 14px;
  padding: 0 4px;
  font-size: 9px;
  font-weight: 700;
  line-height: 14px;
  text-align: center;
  color: #fff;
  background: #ff3b30; /* iOS system red */
  border-radius: 7px;
  box-shadow: 0 1px 4px rgba(255, 59, 48, 0.4);
  animation: badge-pop 0.35s cubic-bezier(0.16, 1, 0.3, 1);
}

@keyframes badge-pop {
  0% { transform: scale(0); }
  60% { transform: scale(1.2); }
  100% { transform: scale(1); }
}

/* ── Tab 内容区 ── */
.tab-content {
  padding: 16px 4px;
  color: white;
}
</style>

<script setup lang="ts">
/**
 * 12 导联 ECG 选择器 — 预设组合 + 分组快选
 *
 * 交互设计:
 *   - 默认收起: 显示当前导联摘要 pill，点击展开面板
 *   - 预设组合: 单导(II) / 肢体6导 / 胸前6导 / 标准12导 / 自定义
 *   - 分组快选: 肢体导联行 + 胸前导联行，每行有"全选/清空"
 *   - 单击导联 = toggle，至少保留 1 个导联
 *   - 持久化到 localStorage
 */
import { ref, computed, onMounted, watch, onBeforeUnmount } from 'vue'
import { ChevronDown } from 'lucide-vue-next'
import { useVirtualHumanStore } from '@/store/virtualHuman'
import { nextZIndex } from '@/constants/zIndex'

const STORAGE_KEY = 'beatflow-selected-leads'
const store = useVirtualHumanStore()

const ALL_12 = ['I','II','III','aVR','aVL','aVF','V1','V2','V3','V4','V5','V6'] as const
const LIMB = ['I', 'II', 'III', 'aVR', 'aVL', 'aVF']
const CHEST = ['V1', 'V2', 'V3', 'V4', 'V5', 'V6']

// ── Presets ──
interface Preset {
  key: string
  label: string
  icon: string
  leads: string[]
}

const presets: Preset[] = [
  { key: 'ii',     label: 'Lead II',    icon: '1',  leads: ['II'] },
  { key: 'limb',   label: '肢体 6 导',  icon: '6',  leads: [...LIMB] },
  { key: 'chest',  label: '胸前 6 导',  icon: '6',  leads: [...CHEST] },
  { key: 'std12',  label: '标准 12 导', icon: '12', leads: [...ALL_12] },
  { key: 'rhythm', label: '节律监测',   icon: '3',  leads: ['II', 'V1', 'V5'] },
]

// ── State ──
const isOpen = ref(false)
const panelRef = ref<HTMLElement | null>(null)
const triggerRef = ref<HTMLElement | null>(null)
const zIdx = ref(0)

// ── Derived ──
const selected = computed(() => new Set(store.selectedLeads))

const summaryText = computed(() => {
  const n = store.selectedLeads.length
  if (n === 1) return store.selectedLeads[0]
  if (n === 12) return '12 导联'
  // Check if matches a preset
  const match = presets.find(p =>
    p.leads.length === n && p.leads.every(l => selected.value.has(l))
  )
  if (match) return match.label
  return `${n} 导联`
})

const activePresetKey = computed(() => {
  for (const p of presets) {
    if (p.leads.length === store.selectedLeads.length &&
        p.leads.every(l => selected.value.has(l))) {
      return p.key
    }
  }
  return null
})

// ── Persistence ──
onMounted(() => {
  const saved = localStorage.getItem(STORAGE_KEY)
  if (saved) {
    try {
      const leads = JSON.parse(saved) as string[]
      if (Array.isArray(leads) && leads.length > 0) {
        store.setLeads(leads)
      }
    } catch { /* ignore */ }
  }
  document.addEventListener('mousedown', onClickOutside)
})

onBeforeUnmount(() => {
  document.removeEventListener('mousedown', onClickOutside)
})

watch(() => store.selectedLeads, (newLeads) => {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(newLeads))
}, { deep: true })

// ── Actions ──
function togglePanel() {
  if (!isOpen.value) {
    zIdx.value = nextZIndex()
  }
  isOpen.value = !isOpen.value
}

function applyPreset(preset: Preset) {
  store.setLeads([...preset.leads])
}

function toggleLead(lead: string) {
  const current = [...store.selectedLeads]
  const idx = current.indexOf(lead)
  if (idx !== -1) {
    if (current.length <= 1) return
    current.splice(idx, 1)
  } else {
    current.push(lead)
  }
  store.setLeads(current)
}

function selectGroup(group: string[]) {
  store.setLeads([...group])
}

function toggleGroup(group: string[]) {
  const allSelected = group.every(l => selected.value.has(l))
  if (allSelected) {
    // Deselect group, but keep at least 1 lead
    const remaining = store.selectedLeads.filter(l => !group.includes(l))
    if (remaining.length === 0) return
    store.setLeads(remaining)
  } else {
    // Add all from group
    const merged = new Set([...store.selectedLeads, ...group])
    store.setLeads([...merged])
  }
}

function isGroupAllSelected(group: string[]): boolean {
  return group.every(l => selected.value.has(l))
}

function isGroupPartial(group: string[]): boolean {
  const some = group.some(l => selected.value.has(l))
  const all = group.every(l => selected.value.has(l))
  return some && !all
}

function onClickOutside(e: MouseEvent) {
  if (!isOpen.value) return
  const target = e.target as Node
  if (panelRef.value?.contains(target)) return
  if (triggerRef.value?.contains(target)) return
  isOpen.value = false
}
</script>

<template>
  <div class="relative">
    <!-- Trigger pill -->
    <button
      ref="triggerRef"
      class="inline-flex items-center gap-1.5 h-6 px-2.5 text-[10px] font-semibold
             rounded-full border transition-all duration-200"
      :class="isOpen
        ? 'text-[#007AFF] bg-[#007AFF]/15 border-[#007AFF]/30'
        : 'text-white/50 bg-white/[0.04] border-white/[0.08] hover:bg-white/[0.08]'"
      style="border-radius: 980px"
      @click="togglePanel"
    >
      <span class="tabular-nums" style="font-family: var(--cmd-font-mono, monospace)">
        {{ summaryText }}
      </span>
      <ChevronDown :size="10" class="transition-transform duration-200"
                   :class="{ 'rotate-180': isOpen }" />
    </button>

    <!-- Dropdown panel -->
    <Teleport to="body">
      <Transition name="lead-panel">
        <div v-if="isOpen"
             ref="panelRef"
             class="lead-selector-panel"
             :style="{ zIndex: zIdx }">

          <!-- Presets -->
          <div class="px-3 pt-3 pb-2">
            <div class="text-[9px] text-white/25 uppercase tracking-wider mb-1.5">预设</div>
            <div class="flex flex-wrap gap-1.5">
              <button v-for="p in presets" :key="p.key"
                      class="inline-flex items-center gap-1 h-7 px-2.5 text-[11px] font-medium
                             rounded-full border transition-all duration-150 shrink-0 whitespace-nowrap"
                      :class="activePresetKey === p.key
                        ? 'text-[#007AFF] bg-[#007AFF]/15 border-[#007AFF]/30'
                        : 'text-white/45 border-white/[0.08] hover:bg-white/[0.06] hover:text-white/60'"
                      style="border-radius: 980px"
                      @click="applyPreset(p)">
                <span class="w-4 h-4 flex items-center justify-center rounded-full
                             text-[9px] font-bold bg-white/[0.08]">{{ p.icon }}</span>
                {{ p.label }}
              </button>
            </div>
          </div>

          <div class="border-t border-white/[0.06] mx-3" />

          <!-- Limb leads group -->
          <div class="px-3 pt-2 pb-1">
            <div class="flex items-center justify-between mb-1.5">
              <span class="text-[9px] text-white/25 uppercase tracking-wider">肢体导联</span>
              <button class="text-[9px] px-1.5 py-0.5 rounded text-white/30
                             hover:text-white/60 hover:bg-white/[0.06] transition-colors"
                      @click="toggleGroup(LIMB)">
                {{ isGroupAllSelected(LIMB) ? '清空' : '全选' }}
              </button>
            </div>
            <div class="flex gap-1">
              <button v-for="lead in LIMB" :key="lead"
                      class="lead-chip"
                      :class="selected.has(lead)
                        ? 'lead-chip--active-limb'
                        : 'lead-chip--inactive'"
                      @click="toggleLead(lead)">
                {{ lead }}
              </button>
            </div>
          </div>

          <!-- Chest leads group -->
          <div class="px-3 pt-1 pb-3">
            <div class="flex items-center justify-between mb-1.5">
              <span class="text-[9px] text-white/25 uppercase tracking-wider">胸前导联</span>
              <button class="text-[9px] px-1.5 py-0.5 rounded text-white/30
                             hover:text-white/60 hover:bg-white/[0.06] transition-colors"
                      @click="toggleGroup(CHEST)">
                {{ isGroupAllSelected(CHEST) ? '清空' : '全选' }}
              </button>
            </div>
            <div class="flex gap-1">
              <button v-for="lead in CHEST" :key="lead"
                      class="lead-chip"
                      :class="selected.has(lead)
                        ? 'lead-chip--active-chest'
                        : 'lead-chip--inactive'"
                      @click="toggleLead(lead)">
                {{ lead }}
              </button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<style scoped>
.lead-selector-panel {
  position: fixed;
  top: 80px;
  left: 50%;
  transform: translateX(-50%);
  width: 380px;
  max-width: calc(100vw - 24px);
  background: rgba(25, 25, 32, 0.92);
  backdrop-filter: blur(40px) saturate(1.8);
  -webkit-backdrop-filter: blur(40px) saturate(1.8);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 16px;
  box-shadow: 0 16px 48px rgba(0, 0, 0, 0.5), 0 0 0 1px rgba(0, 0, 0, 0.2);
}

/* ── Lead chip base ── */
.lead-chip {
  flex: 1;
  min-width: 0;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 600;
  font-family: var(--cmd-font-mono, 'JetBrains Mono', monospace);
  border-radius: 8px;
  border: 1px solid transparent;
  cursor: pointer;
  transition: all 0.15s cubic-bezier(0.16, 1, 0.3, 1);
  -webkit-tap-highlight-color: transparent;
}

.lead-chip--inactive {
  color: rgba(255, 255, 255, 0.30);
  background: rgba(255, 255, 255, 0.03);
  border-color: rgba(255, 255, 255, 0.06);
}
.lead-chip--inactive:hover {
  color: rgba(255, 255, 255, 0.50);
  background: rgba(255, 255, 255, 0.06);
}

.lead-chip--active-limb {
  color: #34C759;
  background: rgba(52, 199, 89, 0.12);
  border-color: rgba(52, 199, 89, 0.25);
  box-shadow: 0 0 8px rgba(52, 199, 89, 0.1);
}

.lead-chip--active-chest {
  color: #5AC8FA;
  background: rgba(90, 200, 250, 0.12);
  border-color: rgba(90, 200, 250, 0.25);
  box-shadow: 0 0 8px rgba(90, 200, 250, 0.1);
}

/* ── Transition ── */
.lead-panel-enter-active {
  transition: opacity 0.2s ease, transform 0.25s cubic-bezier(0.16, 1, 0.3, 1);
}
.lead-panel-leave-active {
  transition: opacity 0.15s ease, transform 0.15s ease;
}
.lead-panel-enter-from,
.lead-panel-leave-to {
  opacity: 0;
  transform: translateX(-50%) translateY(-8px) scale(0.97);
}
.lead-panel-enter-to,
.lead-panel-leave-from {
  transform: translateX(-50%) translateY(0) scale(1);
}

/* ── Mobile: wider chips ── */
@media (max-width: 767px) {
  .lead-selector-panel {
    top: auto;
    bottom: 60px;
    left: 8px;
    right: 8px;
    transform: none;
    width: auto;
  }
  .lead-panel-enter-from,
  .lead-panel-leave-to {
    opacity: 0;
    transform: translateY(12px);
  }
  .lead-panel-enter-to,
  .lead-panel-leave-from {
    transform: translateY(0);
  }
}
</style>

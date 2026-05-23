<script setup lang="ts">
import { ref, computed } from 'vue'
import { ChevronDown, ChevronRight, TrendingUp, TrendingDown, Minus, GitBranch } from 'lucide-vue-next'

export interface CausalEvent {
  id: string
  timestamp_ms: number
  source: string
  source_detail: string
  target: string
  target_path: string
  old_value: number | string | null
  new_value: number | string
  delta: number | null
  mechanism: string
  confidence: number
  parent_event_id: string | null
}

const props = defineProps<{
  events: CausalEvent[]
  maxVisible?: number
}>()

const expandedEventId = ref<string | null>(null)
const showAll = ref(false)

const visibleEvents = computed(() => {
  const limit = props.maxVisible ?? 5
  if (showAll.value) return props.events
  return props.events.slice(-limit)
})

const eventChains = computed(() => {
  const chainMap = new Map<string | null, CausalEvent[]>()
  for (const evt of props.events) {
    const parentId = evt.parent_event_id
    if (!chainMap.has(parentId)) chainMap.set(parentId, [])
    chainMap.get(parentId)!.push(evt)
  }
  return chainMap
})

// ── source label & color (dark theme) ──
const SOURCE_META: Record<string, { label: string; cls: string }> = {
  command:           { label: 'User',        cls: 'bg-blue-500/15 text-blue-400' },
  baroreflex:        { label: 'Baroreflex',  cls: 'bg-amber-500/15 text-amber-400' },
  chemoreflex:       { label: 'Chemoreflex', cls: 'bg-orange-500/15 text-orange-400' },
  raas:              { label: 'RAAS',        cls: 'bg-red-500/15 text-red-400' },
  exercise_model:    { label: 'Exercise',    cls: 'bg-green-500/15 text-green-400' },
  pharmacokinetics:  { label: 'Drug',        cls: 'bg-purple-500/15 text-purple-400' },
  hemorrhage:        { label: 'Hemorrhage',  cls: 'bg-red-500/15 text-red-400' },
  sepsis:            { label: 'Sepsis',      cls: 'bg-rose-500/15 text-rose-400' },
  hemodynamics:      { label: 'Hemo',        cls: 'bg-cyan-500/15 text-cyan-400' },
  ecg_morphology:    { label: 'ECG',         cls: 'bg-teal-500/15 text-teal-400' },
  pcg_acoustics:     { label: 'PCG',         cls: 'bg-indigo-500/15 text-indigo-400' },
}

function sourceMeta(source: string) {
  return SOURCE_META[source] || { label: source, cls: 'bg-white/10 text-white/50' }
}

function deltaIcon(delta: number | null) {
  if (delta === null) return Minus
  if (delta > 0) return TrendingUp
  if (delta < 0) return TrendingDown
  return Minus
}

function deltaClass(delta: number | null): string {
  if (delta === null) return 'text-white/25'
  if (delta > 0) return 'text-[#34C759]'
  if (delta < 0) return 'text-[#FF3B30]'
  return 'text-white/25'
}

function fmtDelta(delta: number | null): string {
  if (delta === null) return ''
  const sign = delta > 0 ? '+' : ''
  return `${sign}${delta.toFixed(1)}`
}

function fmtValue(v: number | string | null): string {
  if (v === null || v === undefined) return '—'
  if (typeof v === 'number') {
    if (Number.isInteger(v)) return String(v)
    return v.toFixed(1)
  }
  return String(v)
}

function toggleExpand(id: string) {
  expandedEventId.value = expandedEventId.value === id ? null : id
}

function getChainChildren(parentId: string | null): CausalEvent[] {
  return eventChains.value.get(parentId) || []
}
</script>

<template>
  <div class="flex flex-col min-h-0">
    <!-- Toolbar: count + show-all toggle -->
    <div class="flex items-center justify-between mb-2" v-if="events.length > 0">
      <span
        class="text-[10px] text-white/25 tabular-nums"
        style="font-family: var(--cmd-font-mono)"
      >{{ events.length }} events</span>
      <button
        v-if="events.length > (maxVisible ?? 5)"
        class="text-[10px] text-white/30 hover:text-white/60 transition-colors"
        @click="showAll = !showAll"
      >
        {{ showAll ? 'Show recent' : 'Show all' }}
      </button>
    </div>

    <!-- Empty state -->
    <div
      v-if="events.length === 0"
      class="py-8 text-center"
    >
      <GitBranch class="w-5 h-5 mx-auto mb-2 text-white/10" />
      <p class="text-xs text-white/20">
        No causal events yet — start a simulation to see physiological cause-effect chains
      </p>
    </div>

    <!-- Event list — no TransitionGroup, stable rendering -->
    <div v-else class="space-y-1 overflow-y-auto min-h-0" style="max-height: 55vh">
      <div
        v-for="evt in visibleEvents"
        :key="evt.id"
        class="rounded-lg border transition-colors duration-75"
        :class="expandedEventId === evt.id
          ? 'border-white/[0.10] bg-white/[0.04]'
          : 'border-transparent hover:border-white/[0.05] hover:bg-white/[0.02]'"
      >
        <!-- Event row -->
        <div
          class="flex items-start gap-2 px-2.5 py-2 cursor-pointer select-none"
          @click="toggleExpand(evt.id)"
        >
          <!-- Expand toggle -->
          <span class="mt-0.5 shrink-0 text-white/25">
            <ChevronRight v-if="expandedEventId !== evt.id" class="w-3 h-3" />
            <ChevronDown v-else class="w-3 h-3" />
          </span>

          <!-- Source badge -->
          <span
            class="text-[10px] px-1.5 py-0.5 rounded font-medium shrink-0 leading-tight"
            :class="sourceMeta(evt.source).cls"
          >{{ sourceMeta(evt.source).label }}</span>

          <!-- Target & value transition -->
          <span class="flex-1 min-w-0 text-xs leading-tight truncate">
            <span class="text-white/80">{{ evt.target }}</span>
            <span class="text-white/20 mx-0.5">·</span>
            <span
              class="tabular-nums"
              style="font-family: var(--cmd-font-mono)"
            >{{ fmtValue(evt.old_value) }} → {{ fmtValue(evt.new_value) }}</span>
          </span>

          <!-- Delta -->
          <span
            class="text-[10px] tabular-nums font-medium shrink-0 flex items-center gap-0.5"
            :class="deltaClass(evt.delta)"
            style="font-family: var(--cmd-font-mono)"
          >
            <component :is="deltaIcon(evt.delta)" class="w-2.5 h-2.5" />
            {{ fmtDelta(evt.delta) }}
          </span>
        </div>

        <!-- Expanded detail -->
        <div
          v-if="expandedEventId === evt.id"
          class="px-2.5 pb-2.5 border-t border-white/[0.06]"
        >
          <!-- Mechanism -->
          <div class="flex items-start gap-1.5 mt-2 text-[11px] text-white/45">
            <GitBranch class="w-3 h-3 mt-0.5 shrink-0 text-white/15" />
            <span>{{ evt.mechanism || 'No mechanism description available' }}</span>
          </div>

          <!-- Source detail -->
          <div class="mt-1 text-[10px] text-white/20">
            {{ evt.source }}<span v-if="evt.source_detail"> / {{ evt.source_detail }}</span>
          </div>

          <!-- Chain children -->
          <div
            v-if="getChainChildren(evt.id).length > 0"
            class="mt-2 ml-3 pl-2.5 border-l border-white/[0.08] space-y-1"
          >
            <div
              v-for="child in getChainChildren(evt.id)"
              :key="child.id"
              class="flex items-center gap-1.5 text-[10px]"
            >
              <span class="px-1 py-0.5 rounded" :class="sourceMeta(child.source).cls">
                {{ sourceMeta(child.source).label }}
              </span>
              <span class="text-white/60">{{ child.target }}</span>
              <span
                class="tabular-nums font-medium"
                :class="deltaClass(child.delta)"
                style="font-family: var(--cmd-font-mono)"
              >{{ fmtDelta(child.delta) }}</span>
            </div>
          </div>

          <!-- Event ID -->
          <div
            class="mt-1.5 text-[9px] text-white/10"
            style="font-family: var(--cmd-font-mono)"
          >{{ evt.id }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

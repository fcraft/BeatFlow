<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { Activity, ChevronDown, ChevronRight, GitBranch, TrendingUp, TrendingDown, Minus, Zap, X } from 'lucide-vue-next'

// ─── Types ───
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

// ─── Props ───
const props = defineProps<{
  events: CausalEvent[]
  maxVisible?: number
}>()

// ─── State ───
const expandedEventId = ref<string | null>(null)
const showAll = ref(false)

// ─── Computed ───
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

const latestEvents = computed(() => props.events.slice(-10))

// ─── Helpers ───
function sourceLabel(source: string): string {
  const map: Record<string, string> = {
    command: 'User',
    baroreflex: 'Baroreflex',
    chemoreflex: 'Chemoreflex',
    raas: 'RAAS',
    exercise_model: 'Exercise',
    pharmacokinetics: 'Drug',
    hemorrhage: 'Hemorrhage',
    sepsis: 'Sepsis',
    hemodynamics: 'Hemo',
    ecg_morphology: 'ECG',
    pcg_acoustics: 'PCG',
  }
  return map[source] || source
}

function sourceColor(source: string): string {
  const map: Record<string, string> = {
    command: 'bg-blue-100 text-blue-700',
    baroreflex: 'bg-amber-100 text-amber-700',
    chemoreflex: 'bg-orange-100 text-orange-700',
    raas: 'bg-red-100 text-red-700',
    exercise_model: 'bg-green-100 text-green-700',
    pharmacokinetics: 'bg-purple-100 text-purple-700',
    hemorrhage: 'bg-red-100 text-red-800',
    sepsis: 'bg-rose-100 text-rose-800',
    hemodynamics: 'bg-cyan-100 text-cyan-700',
    ecg_morphology: 'bg-teal-100 text-teal-700',
    pcg_acoustics: 'bg-indigo-100 text-indigo-700',
  }
  return map[source] || 'bg-gray-100 text-gray-600'
}

function deltaIcon(delta: number | null) {
  if (delta === null) return Minus
  if (delta > 0) return TrendingUp
  if (delta < 0) return TrendingDown
  return Minus
}

function deltaClass(delta: number | null): string {
  if (delta === null) return 'text-gray-400'
  if (delta > 0) return 'text-green-600'
  if (delta < 0) return 'text-red-600'
  return 'text-gray-400'
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
  <div class="space-y-3">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div class="flex items-center gap-2 text-sm font-semibold text-gray-700">
        <Activity class="w-4 h-4" />
        Causal Events
        <span class="text-xs text-gray-400 font-normal tabular-nums">
          ({{ events.length }})
        </span>
      </div>
      <button
        v-if="events.length > (maxVisible ?? 5)"
        class="btn-ghost btn-sm text-xs text-gray-500"
        @click="showAll = !showAll"
      >
        {{ showAll ? 'Show recent' : 'Show all' }}
      </button>
    </div>

    <!-- Empty state -->
    <div
      v-if="events.length === 0"
      class="p-6 text-center text-sm text-gray-400 border-2 border-dashed border-gray-200 rounded-lg"
    >
      <Zap class="w-5 h-5 mx-auto mb-1 opacity-40" />
      No causal events yet — start a simulation to see physiological cause-effect chains
    </div>

    <!-- Event stream -->
    <TransitionGroup
      v-else
      name="event"
      tag="div"
      class="space-y-2"
    >
      <div
        v-for="evt in visibleEvents"
        :key="evt.id"
        class="border border-gray-200 rounded-lg transition-all duration-150"
        :class="expandedEventId === evt.id ? 'bg-gray-50 shadow-sm' : 'bg-white hover:border-gray-300'"
      >
        <!-- Event row -->
        <div
          class="flex items-start gap-2.5 p-2.5 cursor-pointer select-none"
          @click="toggleExpand(evt.id)"
        >
          <button class="mt-0.5 flex-shrink-0 text-gray-400">
            <ChevronRight v-if="expandedEventId !== evt.id" class="w-3.5 h-3.5" />
            <ChevronDown v-else class="w-3.5 h-3.5" />
          </button>

          <!-- Source badge -->
          <span
            class="text-xs px-1.5 py-0.5 rounded font-medium flex-shrink-0"
            :class="sourceColor(evt.source)"
          >
            {{ sourceLabel(evt.source) }}
          </span>

          <!-- Target & delta -->
          <div class="flex-1 min-w-0">
            <span class="text-sm text-gray-800 font-medium">{{ evt.target }}</span>
            <span class="text-xs text-gray-500 ml-1">
              {{ fmtValue(evt.old_value) }} → {{ fmtValue(evt.new_value) }}
            </span>
          </div>

          <!-- Delta badge -->
          <span
            class="text-xs tabular-nums font-medium flex-shrink-0 flex items-center gap-0.5"
            :class="deltaClass(evt.delta)"
          >
            <component :is="deltaIcon(evt.delta)" class="w-3 h-3" />
            {{ fmtDelta(evt.delta) }}
          </span>

          <!-- Confidence -->
          <span
            v-if="evt.confidence < 1.0"
            class="text-xs text-gray-400 flex-shrink-0"
          >
            {{ (evt.confidence * 100).toFixed(0) }}%
          </span>
        </div>

        <!-- Expanded: mechanism + chain -->
        <div
          v-if="expandedEventId === evt.id"
          class="px-2.5 pb-2.5 border-t border-gray-100"
        >
          <!-- Mechanism -->
          <div class="flex items-start gap-2 mt-2 text-xs text-gray-600">
            <GitBranch class="w-3.5 h-3.5 mt-0.5 flex-shrink-0 text-gray-400" />
            <span>{{ evt.mechanism || 'No mechanism description available' }}</span>
          </div>

          <!-- Source detail -->
          <div class="mt-1 text-xs text-gray-400">
            Source: {{ evt.source }} / {{ evt.source_detail || '—' }}
          </div>

          <!-- Chain children -->
          <div
            v-if="getChainChildren(evt.id).length > 0"
            class="mt-2 ml-4 pl-3 border-l-2 border-gray-200 space-y-1"
          >
            <div
              v-for="child in getChainChildren(evt.id)"
              :key="child.id"
              class="flex items-center gap-2 text-xs"
            >
              <span
                class="px-1 py-0.5 rounded text-xs"
                :class="sourceColor(child.source)"
              >
                {{ sourceLabel(child.source) }}
              </span>
              <span class="text-gray-700">{{ child.target }}</span>
              <span class="tabular-nums font-medium" :class="deltaClass(child.delta)">
                {{ fmtDelta(child.delta) }}
              </span>
            </div>
          </div>

          <!-- Event ID -->
          <div class="mt-1.5 text-xs text-gray-300 font-mono">
            {{ evt.id }}
          </div>
        </div>
      </div>
    </TransitionGroup>
  </div>
</template>

<style scoped>
.event-enter-active {
  transition: all 0.3s ease-out;
}
.event-leave-active {
  transition: all 0.2s ease-in;
}
.event-enter-from {
  opacity: 0;
  transform: translateY(-8px);
}
.event-leave-to {
  opacity: 0;
  transform: translateX(12px);
}
</style>

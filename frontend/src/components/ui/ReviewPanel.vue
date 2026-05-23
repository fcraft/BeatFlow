<template>
  <div v-if="reviewStore.active" class="card p-5 mb-5 border-2 border-green-200 bg-green-50/30">
    <div class="flex items-center justify-between mb-3">
      <div>
        <h3 class="text-sm font-semibold text-green-800">检测结果审核</h3>
        <p class="text-xs text-green-600 mt-0.5">
          算法: {{ reviewStore.algorithmUsed }} · 共 {{ reviewStore.totalCount }} 个标记
          <span v-if="reviewStore.trustedCount > 0" class="ml-2 text-amber-600">
            锚点 {{ reviewStore.trustedCount }} 个
          </span>
        </p>
      </div>
      <div class="flex items-center gap-2">
        <button class="btn-ghost btn-sm text-gray-500" @click="reviewStore.deselectAll">取消全选</button>
        <button class="btn-ghost btn-sm text-gray-500" @click="reviewStore.selectAll">全选</button>
        <button class="btn-ghost btn-sm text-red-500" @click="handleReject">全部放弃</button>
        <button class="btn-primary btn-sm" :disabled="!canAccept" @click="handleAccept">
          <CheckCircle2 class="w-3.5 h-3.5" />
          接受选中 ({{ reviewStore.selectedCount }})
        </button>
      </div>
    </div>

    <!-- BPM estimate from trusted anchors -->
    <div v-if="bpmEstimate" class="flex items-center gap-2 mb-3 p-2.5 bg-amber-50 border border-amber-200 rounded-lg text-xs">
      <Star class="w-3.5 h-3.5 text-amber-500" />
      <span class="text-amber-700">
        锚点推算 BPM：<strong>{{ bpmEstimate.meanBpm }}</strong>
        (区间 {{ bpmEstimate.minBpm }}–{{ bpmEstimate.maxBpm }})
        · 基于 {{ bpmEstimate.anchorCount }} 个锚点
      </span>
      <span class="text-amber-400 ml-auto">
        框选区域重检测时将自动应用此 BPM 约束
      </span>
    </div>

    <!-- Filters -->
    <div class="flex flex-wrap items-center gap-3 mb-3">
      <label class="flex items-center gap-1.5 text-xs cursor-pointer select-none">
        <input type="checkbox" v-model="onlyLowConf" class="w-3.5 h-3.5 rounded accent-orange-500" />
        <span class="text-gray-500">仅低置信度</span>
        <span class="text-orange-400">(&lt;0.6)</span>
      </label>
      <template v-for="(count, type) in reviewStore.typeBreakdown" :key="type">
        <label class="flex items-center gap-1 text-xs cursor-pointer select-none">
          <input type="checkbox" :checked="typeFilter[type] ?? true" @change="toggleTypeFilter(type)" class="w-3.5 h-3.5 rounded" />
          <span :class="annotationBadge(type)">{{ type.toUpperCase() }}</span>
          <span class="text-gray-400">×{{ count }}</span>
        </label>
      </template>
      <!-- Trusted only filter -->
      <label class="flex items-center gap-1.5 text-xs cursor-pointer select-none" v-if="reviewStore.trustedCount > 0">
        <input type="checkbox" v-model="onlyTrusted" class="w-3.5 h-3.5 rounded accent-amber-500" />
        <span class="text-amber-600 flex items-center gap-0.5"><Star class="w-3 h-3" />仅锚点</span>
      </label>
    </div>

    <!-- Annotation list -->
    <div ref="listContainer" class="max-h-64 overflow-y-auto border border-gray-200 rounded-lg bg-white">
      <div
        v-for="item in filteredItems"
        :key="item.id"
        class="flex items-center gap-2 px-3 py-1.5 border-b border-gray-100 last:border-b-0 hover:bg-gray-50 transition-all duration-300"
        :class="[
          item.trusted ? 'bg-amber-50/60' : '',
          highlightedId === item.id ? 'bg-green-100 ring-2 ring-green-400 ring-inset' : '',
        ]"
      >
        <input
          type="checkbox"
          :checked="item.selected"
          @change="reviewStore.toggleSelect(item.id)"
          class="w-3.5 h-3.5 rounded shrink-0 accent-green-600"
        />
        <!-- Anchor toggle -->
        <button
          class="shrink-0 w-5 h-5 flex items-center justify-center rounded hover:bg-amber-100 transition-colors"
          :title="item.trusted ? '取消锚点' : '标记为锚点（识别准确的标注以引导重检测）'"
          @click="reviewStore.toggleTrusted(item.id)"
        >
          <Star class="w-3.5 h-3.5" :class="item.trusted ? 'text-amber-500 fill-amber-500' : 'text-gray-300'" />
        </button>
        <span class="text-xs px-1.5 py-0.5 rounded font-mono font-medium shrink-0" :class="annotationBadge(item.annotation_type)">
          {{ item.annotation_type.toUpperCase() }}
        </span>
        <span class="text-xs text-gray-600 truncate flex-1">
          {{ item.start_time.toFixed(3) }}s – {{ (item.end_time ?? item.start_time).toFixed(3) }}s
        </span>
        <span class="text-xs text-gray-400 shrink-0">{{ item.label }}</span>
        <div class="flex items-center gap-1 shrink-0">
          <div class="w-12 h-1.5 bg-gray-100 rounded-full overflow-hidden">
            <div
              class="h-full rounded-full transition-all"
              :class="confidenceColor(item.confidence)"
              :style="{ width: (item.confidence * 100) + '%' }"
            />
          </div>
          <span class="text-xs text-gray-400 w-8 text-right">{{ (item.confidence * 100).toFixed(0) }}%</span>
        </div>
      </div>
      <div v-if="filteredItems.length === 0" class="px-3 py-4 text-xs text-gray-400 text-center">
        无匹配标注
      </div>
    </div>

    <div v-if="accepting" class="flex items-center gap-2 mt-3 text-xs text-green-600">
      <span class="spinner w-3 h-3" />提交中…
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { CheckCircle2, Star } from 'lucide-vue-next'
import { useAnnotationReviewStore } from '@/store/annotationReview'
import { useToastStore } from '@/store/toast'
import { useAuthStore } from '@/store/auth'

const reviewStore = useAnnotationReviewStore()
const toast = useToastStore()
const auth = useAuthStore()

const emit = defineEmits<{
  (e: 'accepted'): void
  (e: 'rejected'): void
}>()

const onlyLowConf = ref(false)
const onlyTrusted = ref(false)
const typeFilter = ref<Record<string, boolean>>({})
const accepting = ref(false)

const canAccept = computed(() => reviewStore.selectedCount > 0 && !accepting.value)
const bpmEstimate = computed(() => reviewStore.anchorBpmEstimate)

const filteredItems = computed(() => {
  let items = reviewStore.items
  if (onlyLowConf.value) {
    items = items.filter(i => i.confidence < 0.6)
  }
  if (onlyTrusted.value) {
    items = items.filter(i => i.trusted)
  }
  const activeFilters = Object.entries(typeFilter.value).filter(([, v]) => !v)
  if (activeFilters.length > 0) {
    const hiddenTypes = new Set(activeFilters.map(([k]) => k))
    items = items.filter(i => !hiddenTypes.has(i.annotation_type))
  }
  return items
})

function toggleTypeFilter(type: string) {
  typeFilter.value[type] = !typeFilter.value[type]
}

function confidenceColor(conf: number): string {
  if (conf >= 0.8) return 'bg-green-500'
  if (conf >= 0.6) return 'bg-yellow-500'
  return 'bg-red-400'
}

function annotationBadge(type: string): string {
  const map: Record<string, string> = {
    s1: 'px-1.5 py-0.5 rounded text-xs font-mono bg-red-100 text-red-700',
    s2: 'px-1.5 py-0.5 rounded text-xs font-mono bg-blue-100 text-blue-700',
    qrs: 'px-1.5 py-0.5 rounded text-xs font-mono bg-green-100 text-green-700',
    p_wave: 'px-1.5 py-0.5 rounded text-xs font-mono bg-amber-100 text-amber-700',
    t_wave: 'px-1.5 py-0.5 rounded text-xs font-mono bg-orange-100 text-orange-700',
    q_wave: 'px-1.5 py-0.5 rounded text-xs font-mono bg-violet-100 text-violet-700',
    s_wave: 'px-1.5 py-0.5 rounded text-xs font-mono bg-purple-100 text-purple-700',
    murmur: 'px-1.5 py-0.5 rounded text-xs font-mono bg-fuchsia-100 text-fuchsia-700',
  }
  return map[type] ?? 'px-1.5 py-0.5 rounded text-xs font-mono bg-gray-100 text-gray-700'
}

async function handleAccept() {
  if (!canAccept.value) return
  accepting.value = true
  try {
    const items = reviewStore.getSelectedItems()
    const h: Record<string, string> = { 'Content-Type': 'application/json' }
    if (auth.token) h['Authorization'] = `Bearer ${auth.token}`
    const r = await fetch('/api/v1/annotations/accept', {
      method: 'POST',
      headers: h,
      body: JSON.stringify({ file_id: reviewStore.fileId, items }),
    })
    if (r.ok) {
      const result = await r.json()
      toast.success(`已接受 ${result.accepted_count} 个标记`)
      reviewStore.reset()
      emit('accepted')
    } else {
      const err = await r.json().catch(() => ({}))
      toast.error(err.detail ?? '提交失败')
    }
  } finally {
    accepting.value = false
  }
}

function handleReject() {
  reviewStore.reset()
  emit('rejected')
}

// ── Scroll-to-item + highlight exposed for waveform interaction ──────
const listContainer = ref<HTMLElement | null>(null)
const highlightedId = ref<string | null>(null)
let highlightTimer: ReturnType<typeof setTimeout> | null = null
const ROW_H = 32 // px per row (matches py-1.5 + content)

function scrollToItem(id: string) {
  if (!listContainer.value) return
  onlyLowConf.value = false
  onlyTrusted.value = false
  typeFilter.value = {}
  const idx = reviewStore.items.findIndex(i => i.id === id)
  if (idx === -1) return
  const offset = idx * ROW_H - 32
  listContainer.value.scrollTo({ top: Math.max(0, offset), behavior: 'smooth' })
}

function highlightItem(id: string) {
  scrollToItem(id)
  highlightedId.value = id
  if (highlightTimer) clearTimeout(highlightTimer)
  highlightTimer = setTimeout(() => { highlightedId.value = null }, 2000)
}

defineExpose({ scrollToItem, highlightItem })
</script>

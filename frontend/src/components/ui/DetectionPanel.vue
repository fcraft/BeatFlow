<template>
  <!-- Detection Settings Panel -->
  <div class="space-y-4">
    <!-- Algorithm Selector -->
    <div>
      <label class="label mb-2 block">检测算法</label>
      <div class="grid grid-cols-1 gap-2">
        <label
          v-for="algo in algorithms"
          :key="algo.id"
          class="flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-colors"
          :class="selectedAlgorithm === algo.id
            ? 'border-primary-500 bg-primary-50'
            : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'"
        >
          <input
            type="radio"
            :value="algo.id"
            v-model="selectedAlgorithm"
            class="mt-0.5 accent-primary-600"
          />
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-2">
              <span class="text-sm font-medium text-gray-800">{{ algo.label }}</span>
              <span
                v-if="algo.badge"
                class="text-xs px-1.5 py-0.5 rounded-full font-medium"
                :class="algo.badgeClass"
              >{{ algo.badge }}</span>
            </div>
            <p class="text-xs text-gray-500 mt-0.5 leading-relaxed">{{ algo.desc }}</p>
            <div v-if="algo.features?.length" class="flex flex-wrap gap-1 mt-1.5">
              <span
                v-for="f in algo.features"
                :key="f"
                class="text-xs px-1.5 py-0.5 bg-gray-100 text-gray-600 rounded"
              >{{ f }}</span>
            </div>
          </div>
        </label>
      </div>
    </div>

    <!-- Action Buttons -->
    <div class="flex items-center gap-2 pt-1">
      <button
        class="btn-primary flex-1"
        :disabled="running || !canRun"
        @click="runDetect"
      >
        <span v-if="running" class="spinner w-3.5 h-3.5" />
        <Cpu v-else class="w-3.5 h-3.5" />
        {{ running ? '检测中…' : '开始检测' }}
      </button>
      <button
        v-if="lastResult"
        class="btn-ghost btn-sm text-gray-500"
        @click="$emit('clear')"
        title="清除自动检测结果"
      >
        <Eraser class="w-3.5 h-3.5" />
      </button>
    </div>

    <!-- Last Result Summary -->
    <div
      v-if="lastResult"
      class="flex items-center gap-2 p-2.5 bg-green-50 border border-green-200 rounded-lg text-xs text-green-700"
    >
      <CheckCircle2 class="w-3.5 h-3.5 shrink-0" />
      <span>
        上次检测（{{ lastResult.algorithm }}）：共 <strong>{{ lastResult.count }}</strong> 个标记
        <span v-if="lastResult.breakdown.length" class="ml-1 text-green-600">
          — {{ lastResult.breakdown.join(' · ') }}
        </span>
      </span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { Cpu, Eraser, CheckCircle2 } from 'lucide-vue-next'

// ── Props ──────────────────────────────────────────────────────────────────
const props = defineProps<{
  fileId: string
  fileType: string   // 'pcg' | 'audio' | 'ecg' | ''
  authHeader: Record<string, string>
  isS1Only: boolean
}>()

const emit = defineEmits<{
  (e: 'detected', payload: { items: any[], algorithm: string, count: number }): void
  (e: 'clear'): void
  (e: 'error', msg: string): void
}>()

// ── Algorithm definitions ─────────────────────────────────────────────────
const algorithms = [
  {
    id: 'auto',
    label: '自动选择',
    badge: '推荐',
    badgeClass: 'bg-primary-100 text-primary-700',
    desc: '根据文件类型自动选择最佳算法（ECG: NeuroKit2，PCG: NeuroKit2 增强版）',
    features: [],
  },
  {
    id: 'neurokit2',
    label: 'NeuroKit2',
    badge: 'AI增强',
    badgeClass: 'bg-purple-100 text-purple-700',
    desc: '神经生理信号处理工具箱，支持 ECG 全波形（P/Q/R/S/T）和 PCG 精确分割',
    features: ['ECG全波形', 'PCG智能分类', '高精度'],
  },
  {
    id: 'wfdb',
    label: 'WFDB / XQRS',
    badge: 'PhysioNet',
    badgeClass: 'bg-blue-100 text-blue-700',
    desc: 'MIT PhysioNet 官方工具，XQRS 是经典的 QRS 检测算法，适合标准临床 ECG',
    features: ['临床标准', 'ECG专项', 'R峰精确'],
  },
  {
    id: 'scipy',
    label: 'SciPy 信号处理',
    badge: '内置',
    badgeClass: 'bg-gray-100 text-gray-600',
    desc: '基于 Pan-Tompkins 原理的内置检测，速度最快，适合快速预览',
    features: ['无依赖', '最快速', '基础精度'],
  },
]

// ── Wave type definitions ─────────────────────────────────────────────────
const isPCG = computed(() => props.fileType === 'pcg' || props.fileType === 'audio')

// ── State ─────────────────────────────────────────────────────────────────
const selectedAlgorithm = ref('auto')
const running = ref(false)
const lastResult = ref<{
  algorithm: string
  count: number
  breakdown: string[]
} | null>(null)

// Disable wfdb for PCG (it only supports ECG)
watch(selectedAlgorithm, (algo) => {
  if (algo === 'wfdb' && props.fileType !== 'ecg') {
    selectedAlgorithm.value = 'neurokit2'
  }
})

const canRun = computed(() =>
  !!props.fileId && !!props.fileType
)

// ── Detection ─────────────────────────────────────────────────────────────
const runDetect = async () => {
  if (!canRun.value) return
  running.value = true
  try {
    const params = new URLSearchParams({ algorithm: selectedAlgorithm.value })
    if (props.isS1Only) params.set('s1_only', 'true')
    const r = await fetch(`/api/v1/files/${props.fileId}/detect/preview?${params}`, {
      method: 'POST',
      headers: props.authHeader,
    })
    if (!r.ok) {
      const err = await r.json().catch(() => ({}))
      emit('error', err.detail ?? '检测失败')
      return
    }
    const data = await r.json()

    // Count per type for result summary
    const counts: Record<string, number> = {}
    for (const item of data.items) {
      counts[item.annotation_type] = (counts[item.annotation_type] ?? 0) + 1
    }
    const breakdown = Object.entries(counts).map(([k, v]) => `${k.toUpperCase()}×${v}`)

    lastResult.value = {
      algorithm: data.algorithm_used ?? selectedAlgorithm.value,
      count: data.detected_count,
      breakdown,
    }

    emit('detected', {
      items: data.items,
      algorithm: data.algorithm_used ?? selectedAlgorithm.value,
      count: data.detected_count,
    })
  } finally {
    running.value = false
  }
}

// Expose for parent to reset / read s1_only state
const reset = () => { lastResult.value = null }
defineExpose({ reset })
</script>

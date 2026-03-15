<template>
  <div class="space-y-4">
    <!-- Controls -->
    <div class="flex flex-wrap items-center gap-3">
      <!-- Mode -->
      <div class="flex items-center gap-1 bg-gray-100 rounded-lg p-1">
        <button
          v-for="m in MODES"
          :key="m.value"
          class="px-3 py-1 text-xs font-medium rounded-md transition-colors"
          :class="mode === m.value ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-500 hover:text-gray-700'"
          @click="mode = m.value"
        >{{ m.label }}</button>
      </div>

      <!-- Window size (time mode) -->
      <template v-if="mode === 'time'">
        <label class="text-xs text-gray-500 shrink-0">窗口</label>
        <select v-model.number="windowSec" class="select w-24 text-xs py-1">
          <option :value="1">1 秒</option>
          <option :value="2">2 秒</option>
          <option :value="5">5 秒</option>
          <option :value="10">10 秒</option>
          <option :value="30">30 秒</option>
          <option :value="60">60 秒</option>
        </select>
      </template>

      <!-- N beats (beat mode) -->
      <template v-else>
        <label class="text-xs text-gray-500 shrink-0">相邻</label>
        <select v-model.number="nBeats" class="select w-20 text-xs py-1">
          <option :value="1">1 拍</option>
          <option :value="2">2 拍</option>
          <option :value="3">3 拍</option>
          <option :value="4">4 拍</option>
          <option :value="5">5 拍</option>
          <option :value="8">8 拍</option>
        </select>
        <span class="text-xs text-gray-400">移动平均</span>
      </template>

      <!-- Beat type selector -->
      <label class="text-xs text-gray-500 shrink-0">Beat 类型</label>
      <div class="flex items-center gap-1">
        <button
          v-for="bt in availableBeatTypes"
          :key="bt"
          class="px-2 py-1 text-xs rounded-md border transition-colors"
          :class="beatType === bt
            ? 'border-blue-500 bg-blue-50 text-blue-700'
            : 'border-gray-200 text-gray-500 hover:border-blue-300'"
          @click="beatType = bt"
        >{{ bt.toUpperCase() }}</button>
      </div>

      <div class="flex-1" />

      <!-- Export -->
      <div class="relative" ref="exportMenuRef">
        <button class="btn-secondary btn-sm" :disabled="bpmPoints.length === 0" @click="showExportMenu = !showExportMenu">
          <Download class="w-3.5 h-3.5" />导出
          <ChevronDown class="w-3 h-3" />
        </button>
        <div v-if="showExportMenu"
          class="absolute right-0 top-full mt-1 w-36 bg-white border border-gray-200 rounded-xl shadow-lg z-10 py-1 text-sm">
          <button class="w-full text-left px-4 py-2 hover:bg-gray-50 flex items-center gap-2" @click="exportCSV">
            <FileText class="w-3.5 h-3.5 text-green-600" />导出 CSV
          </button>
          <button class="w-full text-left px-4 py-2 hover:bg-gray-50 flex items-center gap-2" @click="exportJSON">
            <Braces class="w-3.5 h-3.5 text-blue-600" />导出 JSON
          </button>
        </div>
      </div>
    </div>

    <!-- Stats row -->
    <div v-if="bpmPoints.length > 0" class="flex flex-wrap gap-4">
      <div v-for="s in stats" :key="s.label" class="flex flex-col">
        <span class="text-xs text-gray-400">{{ s.label }}</span>
        <span class="text-base font-bold tabular-nums" :class="s.color ?? 'text-gray-800'">{{ s.value }}</span>
      </div>
    </div>

    <!-- Canvas chart -->
    <div class="relative bg-gray-50 rounded-lg overflow-hidden select-none" :style="{ height: chartHeight + 'px' }">
      <canvas ref="chartCanvas" class="absolute inset-0 w-full h-full" />

      <!-- Tooltip -->
      <div v-if="tooltip"
        class="absolute pointer-events-none z-10 bg-gray-900 text-white text-xs rounded-lg px-3 py-2 shadow-xl whitespace-nowrap"
        :style="{ left: Math.min(tooltip.x + 12, chartContainerW - 160) + 'px', top: Math.max(8, tooltip.y - 36) + 'px' }">
        <div class="font-bold text-green-300">{{ tooltip.bpm.toFixed(1) }} BPM</div>
        <div class="text-gray-300">t = {{ tooltip.time.toFixed(2) }}s</div>
      </div>

      <!-- No data message -->
      <div v-if="bpmPoints.length === 0"
        class="absolute inset-0 flex flex-col items-center justify-center text-gray-400 gap-2">
        <Activity class="w-8 h-8 opacity-40" />
        <p class="text-sm">
          {{ availableBeatTypes.length === 0
            ? '无 S1/S2/QRS 标记，请先运行自动检测'
            : `当前「${beatType.toUpperCase()}」标记不足，请切换类型或增加标记` }}
        </p>
      </div>
    </div>

    <!-- Info footer -->
    <p class="text-xs text-gray-400">
      <span v-if="mode === 'time'">以 {{ windowSec }}s 时间窗口内的 {{ beatType.toUpperCase() }} 个数计算瞬时心率</span>
      <span v-else>取相邻 {{ nBeats }} 个 {{ beatType.toUpperCase() }} 的平均间期计算心率</span>
      &nbsp;·&nbsp;{{ bpmPoints.length }} 个采样点
    </p>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { Download, ChevronDown, FileText, Activity } from 'lucide-vue-next'
import { Braces } from 'lucide-vue-next'

interface Annotation {
  id: string
  annotation_type: string
  start_time: number
  end_time?: number
  confidence?: number
}

interface BpmPoint {
  time: number
  bpm: number
}

const props = withDefaults(defineProps<{
  annotations: Annotation[]
  duration: number
  chartHeight?: number
}>(), { chartHeight: 180 })

// ── Controls ──────────────────────────────────────────────────────
const MODES = [
  { value: 'beats' as const, label: '相邻拍' },
  { value: 'time' as const, label: '时间窗口' },
]
const mode = ref<'beats' | 'time'>('beats')
const windowSec = ref(5)
const nBeats = ref(1)
const beatType = ref('s1')

// ── Available beat types ──────────────────────────────────────────
const BEAT_TYPES = ['s1', 's2', 'qrs', 'p_wave', 'r_peak']
const availableBeatTypes = computed(() => {
  const types = new Set(props.annotations.map(a => a.annotation_type))
  return BEAT_TYPES.filter(t => types.has(t))
})

// Auto-select first available beat type
watch(availableBeatTypes, (types) => {
  if (!types.includes(beatType.value) && types.length > 0) {
    beatType.value = types[0]
  }
}, { immediate: true })

// ── BPM calculation ───────────────────────────────────────────────
const bpmPoints = computed<BpmPoint[]>(() => {
  const beats = props.annotations
    .filter(a => a.annotation_type === beatType.value)
    .map(a => a.start_time)
    .sort((a, b) => a - b)

  if (beats.length < 2) return []

  if (mode.value === 'beats') {
    // N-beat moving average: average interval over nBeats consecutive RR intervals
    const n = Math.max(1, nBeats.value)
    const points: BpmPoint[] = []
    for (let i = n; i < beats.length; i++) {
      const dt = beats[i] - beats[i - n]
      if (dt <= 0) continue
      const bpm = (n / dt) * 60
      if (bpm < 20 || bpm > 400) continue   // physiological guard
      points.push({ time: beats[i], bpm })
    }
    return points
  } else {
    // Sliding time-window: count beats in [t - W/2, t + W/2]
    const hw = windowSec.value / 2
    const step = Math.max(0.05, windowSec.value / 20)  // ~20 samples per window
    const points: BpmPoint[] = []
    const tStart = beats[0] + hw
    const tEnd = beats[beats.length - 1] - hw
    if (tStart >= tEnd) {
      // Window too large: just compute at each beat
      for (const t of beats) {
        const count = beats.filter(b => b >= t - hw && b <= t + hw).length
        const bpm = (count / windowSec.value) * 60
        if (bpm >= 20 && bpm <= 400) points.push({ time: t, bpm })
      }
      return points
    }
    for (let t = tStart; t <= tEnd; t += step) {
      const count = beats.filter(b => b >= t - hw && b <= t + hw).length
      const bpm = (count / windowSec.value) * 60
      if (bpm >= 20 && bpm <= 400) points.push({ time: t, bpm })
    }
    return points
  }
})

// ── Stats ─────────────────────────────────────────────────────────
const stats = computed(() => {
  if (bpmPoints.value.length === 0) return []
  const bpms = bpmPoints.value.map(p => p.bpm)
  const avg = bpms.reduce((a, b) => a + b, 0) / bpms.length
  const mn = Math.min(...bpms)
  const mx = Math.max(...bpms)
  const std = Math.sqrt(bpms.reduce((a, b) => a + (b - avg) ** 2, 0) / bpms.length)
  return [
    { label: '平均 BPM', value: avg.toFixed(1), color: 'text-blue-600' },
    { label: '最低 BPM', value: mn.toFixed(1), color: 'text-green-600' },
    { label: '最高 BPM', value: mx.toFixed(1), color: 'text-red-600' },
    { label: 'SD', value: std.toFixed(1), color: 'text-gray-600' },
    { label: '采样点', value: String(bpmPoints.value.length), color: 'text-gray-500' },
  ]
})

// ── Canvas rendering ──────────────────────────────────────────────
const chartCanvas = ref<HTMLCanvasElement | null>(null)
const chartContainerW = ref(600)
const tooltip = ref<{ x: number; y: number; bpm: number; time: number } | null>(null)

const PAD = { top: 16, right: 16, bottom: 36, left: 48 }
const GRID_LINES = 5

const draw = () => {
  const cvs = chartCanvas.value
  if (!cvs) return
  const W = cvs.offsetWidth || chartContainerW.value
  const H = props.chartHeight
  cvs.width = W
  cvs.height = H
  const ctx = cvs.getContext('2d')!
  ctx.clearRect(0, 0, W, H)

  const pts = bpmPoints.value
  if (pts.length === 0) return

  const innerW = W - PAD.left - PAD.right
  const innerH = H - PAD.top - PAD.bottom

  const bpms = pts.map(p => p.bpm)
  const times = pts.map(p => p.time)
  const bpmMin = Math.max(0, Math.min(...bpms) - 10)
  const bpmMax = Math.max(...bpms) + 10
  const tMin = times[0]
  const tMax = times[times.length - 1]
  const tSpan = tMax - tMin || 1
  const bSpan = bpmMax - bpmMin || 1

  const tx = (t: number) => PAD.left + ((t - tMin) / tSpan) * innerW
  const ty = (b: number) => PAD.top + (1 - (b - bpmMin) / bSpan) * innerH

  // Grid
  ctx.strokeStyle = '#e5e7eb'
  ctx.lineWidth = 1
  for (let i = 0; i <= GRID_LINES; i++) {
    const y = PAD.top + (i / GRID_LINES) * innerH
    ctx.beginPath(); ctx.moveTo(PAD.left, y); ctx.lineTo(PAD.left + innerW, y); ctx.stroke()
    const bVal = bpmMax - (i / GRID_LINES) * bSpan
    ctx.fillStyle = '#9ca3af'
    ctx.font = '11px ui-monospace, monospace'
    ctx.textAlign = 'right'
    ctx.fillText(bVal.toFixed(0), PAD.left - 6, y + 4)
  }

  // Time axis ticks
  const tickCount = Math.min(8, Math.floor(innerW / 60))
  ctx.fillStyle = '#9ca3af'
  ctx.font = '11px ui-monospace, monospace'
  ctx.textAlign = 'center'
  for (let i = 0; i <= tickCount; i++) {
    const t = tMin + (i / tickCount) * tSpan
    const x = tx(t)
    ctx.strokeStyle = '#e5e7eb'
    ctx.beginPath(); ctx.moveTo(x, PAD.top + innerH); ctx.lineTo(x, PAD.top + innerH + 4); ctx.stroke()
    ctx.fillText(t.toFixed(1) + 's', x, H - 6)
  }

  // Y axis label
  ctx.save()
  ctx.translate(14, PAD.top + innerH / 2)
  ctx.rotate(-Math.PI / 2)
  ctx.fillStyle = '#6b7280'
  ctx.font = '11px sans-serif'
  ctx.textAlign = 'center'
  ctx.fillText('BPM', 0, 0)
  ctx.restore()

  // Filled area under curve
  ctx.beginPath()
  ctx.moveTo(tx(times[0]), ty(bpms[0]))
  for (let i = 1; i < pts.length; i++) {
    ctx.lineTo(tx(times[i]), ty(bpms[i]))
  }
  ctx.lineTo(tx(times[times.length - 1]), PAD.top + innerH)
  ctx.lineTo(tx(times[0]), PAD.top + innerH)
  ctx.closePath()
  const grad = ctx.createLinearGradient(0, PAD.top, 0, PAD.top + innerH)
  grad.addColorStop(0, 'rgba(59,130,246,0.25)')
  grad.addColorStop(1, 'rgba(59,130,246,0.02)')
  ctx.fillStyle = grad
  ctx.fill()

  // Line
  ctx.beginPath()
  ctx.moveTo(tx(times[0]), ty(bpms[0]))
  for (let i = 1; i < pts.length; i++) {
    // Smooth: simple bezier via midpoints
    const mx = (tx(times[i - 1]) + tx(times[i])) / 2
    ctx.bezierCurveTo(mx, ty(bpms[i - 1]), mx, ty(bpms[i]), tx(times[i]), ty(bpms[i]))
  }
  ctx.strokeStyle = '#3b82f6'
  ctx.lineWidth = 2
  ctx.lineJoin = 'round'
  ctx.stroke()

  // Dots (only when few points)
  if (pts.length <= 80) {
    pts.forEach((p, i) => {
      ctx.beginPath()
      ctx.arc(tx(p.time), ty(p.bpm), 3, 0, Math.PI * 2)
      ctx.fillStyle = '#3b82f6'
      ctx.fill()
    })
  }
}

// ── Mouse hover tooltip ────────────────────────────────────────────
const onMouseMove = (e: MouseEvent) => {
  const cvs = chartCanvas.value
  if (!cvs || bpmPoints.value.length === 0) { tooltip.value = null; return }
  const rect = cvs.getBoundingClientRect()
  const mx = e.clientX - rect.left
  const my = e.clientY - rect.top
  const W = rect.width
  const H = props.chartHeight
  const innerW = W - PAD.left - PAD.right

  const times = bpmPoints.value.map(p => p.time)
  const tMin = times[0]
  const tMax = times[times.length - 1]
  const tSpan = tMax - tMin || 1

  if (mx < PAD.left || mx > W - PAD.right || my < PAD.top || my > H - PAD.bottom) {
    tooltip.value = null; return
  }

  const tHover = tMin + ((mx - PAD.left) / innerW) * tSpan
  // Find nearest point
  let nearestIdx = 0
  let minDist = Infinity
  bpmPoints.value.forEach((p, i) => {
    const d = Math.abs(p.time - tHover)
    if (d < minDist) { minDist = d; nearestIdx = i }
  })
  const pt = bpmPoints.value[nearestIdx]
  const bpms = bpmPoints.value.map(p => p.bpm)
  const bpmMin = Math.max(0, Math.min(...bpms) - 10)
  const bpmMax = Math.max(...bpms) + 10
  const bSpan = bpmMax - bpmMin || 1
  const innerH = H - PAD.top - PAD.bottom
  const ptX = PAD.left + ((pt.time - tMin) / tSpan) * innerW
  const ptY = PAD.top + (1 - (pt.bpm - bpmMin) / bSpan) * innerH
  tooltip.value = { x: ptX, y: ptY, bpm: pt.bpm, time: pt.time }
}

const onMouseLeave = () => { tooltip.value = null }

// ── Resize observer ────────────────────────────────────────────────
let ro: ResizeObserver | null = null
onMounted(() => {
  const cvs = chartCanvas.value?.parentElement
  if (cvs) {
    ro = new ResizeObserver(entries => {
      chartContainerW.value = entries[0].contentRect.width
      draw()
    })
    ro.observe(cvs)
  }
  chartCanvas.value?.parentElement?.addEventListener('mousemove', onMouseMove)
  chartCanvas.value?.parentElement?.addEventListener('mouseleave', onMouseLeave)
  draw()
})

onUnmounted(() => {
  ro?.disconnect()
  chartCanvas.value?.parentElement?.removeEventListener('mousemove', onMouseMove)
  chartCanvas.value?.parentElement?.removeEventListener('mouseleave', onMouseLeave)
})

watch([bpmPoints, () => props.chartHeight], () => nextTick(draw))

// ── Export ────────────────────────────────────────────────────────
const showExportMenu = ref(false)
const exportMenuRef = ref<HTMLElement | null>(null)

const closeExportMenu = (e: MouseEvent) => {
  if (exportMenuRef.value && !exportMenuRef.value.contains(e.target as Node)) {
    showExportMenu.value = false
  }
}
onMounted(() => document.addEventListener('click', closeExportMenu))
onUnmounted(() => document.removeEventListener('click', closeExportMenu))

const filename = () => {
  const modeStr = mode.value === 'time' ? `win${windowSec.value}s` : `n${nBeats.value}beats`
  return `bpm_${beatType.value}_${modeStr}`
}

const exportCSV = () => {
  showExportMenu.value = false
  if (bpmPoints.value.length === 0) return
  const header = 'time_s,bpm\n'
  const rows = bpmPoints.value.map(p => `${p.time.toFixed(4)},${p.bpm.toFixed(3)}`).join('\n')
  const blob = new Blob([header + rows], { type: 'text/csv' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a'); a.href = url; a.download = filename() + '.csv'; a.click()
  URL.revokeObjectURL(url)
}

const exportJSON = () => {
  showExportMenu.value = false
  if (bpmPoints.value.length === 0) return
  const data = {
    beat_type: beatType.value,
    mode: mode.value,
    window_sec: mode.value === 'time' ? windowSec.value : null,
    n_beats: mode.value === 'beats' ? nBeats.value : null,
    stats: stats.value.reduce((acc, s) => ({ ...acc, [s.label]: s.value }), {}),
    points: bpmPoints.value,
  }
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a'); a.href = url; a.download = filename() + '.json'; a.click()
  URL.revokeObjectURL(url)
}
</script>

<script setup lang="ts">
/**
 * 实时 ECG 波形 Canvas 组件
 *
 * 当 showAnnotations 开启时，在波形右侧叠加当前拍标注信息。
 * Feature 2: 支持信号平滑级别选择（off / low / high）。
 */
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useScrollingCanvas } from '@/composables/useScrollingCanvas'
import { useEcgCaliper } from '@/composables/useEcgCaliper'
import { useVirtualHumanStore } from '@/store/virtualHuman'
import type { SignalChunk } from '@/store/virtualHuman'

const store = useVirtualHumanStore()
const canvasRef = ref<HTMLCanvasElement | null>(null)

/** 拍类型 → 颜色 */
const beatKindColors: Record<string, string> = {
  sinus: '#22c55e',       // green
  pvc: '#f97316',         // orange
  af: '#a855f7',          // purple
  svt_reentry: '#eab308', // yellow
  escape: '#3b82f6',      // blue
  nsvt: '#ef4444',        // red
}

/** 拍类型 → 中文标签 */
const beatKindLabels: Record<string, string> = {
  sinus: '窦性',
  pvc: 'PVC',
  af: '房颤',
  svt_reentry: 'SVT',
  escape: '逸搏',
  nsvt: 'NSVT',
  normal: '窦性',
}

/** 缓存最后一个有效标注，防止 store 短暂为空时闪烁 */
let cachedAnnotation: Record<string, any> | null = null

/**
 * 在 ECG 波形上叠加标注信息：
 * - 右上角：当前拍类型标签（彩色）
 * - 右侧面板：P/QRS/QT/PR 数值
 */
function drawAnnotationOverlay(ctx: CanvasRenderingContext2D, w: number, h: number) {
  if (!store.showAnnotations) return
  const annotations = store.beatAnnotations
  if (annotations && annotations.length > 0) {
    cachedAnnotation = annotations[annotations.length - 1]
  }
  if (!cachedAnnotation) return

  const last = cachedAnnotation

  const beatKind = last.beat_kind || last.morphology || 'normal'
  const color = beatKindColors[beatKind] || '#94a3b8'
  const label = beatKindLabels[beatKind] || beatKind

  // ── 右上角：拍类型标签 ──
  ctx.save()
  const tagW = ctx.measureText(label).width + 12
  ctx.font = 'bold 10px Inter, system-ui, sans-serif'
  const actualTagW = ctx.measureText(label).width + 12
  const tagX = w - actualTagW - 8
  const tagY = 6
  const tagH = 18

  // 标签背景
  ctx.fillStyle = color
  ctx.globalAlpha = 0.85
  ctx.beginPath()
  roundRect(ctx, tagX, tagY, actualTagW, tagH, 4)
  ctx.fill()
  ctx.globalAlpha = 1

  // 标签文字
  ctx.fillStyle = '#ffffff'
  ctx.textAlign = 'center'
  ctx.textBaseline = 'middle'
  ctx.fillText(label, tagX + actualTagW / 2, tagY + tagH / 2)

  // ── 右侧：标注数值面板 ──
  const panelW = 72
  const panelH = 62
  const panelX = w - panelW - 8
  const panelY = tagY + tagH + 4

  // 半透明背景
  ctx.fillStyle = 'rgba(17, 24, 39, 0.75)'
  ctx.beginPath()
  roundRect(ctx, panelX, panelY, panelW, panelH, 4)
  ctx.fill()

  // 数值行
  ctx.font = '9px Inter, system-ui, sans-serif'
  ctx.textAlign = 'left'
  const lines: Array<{ label: string; value: string; color: string }> = []

  if (last.p_wave_present !== false) {
    lines.push({ label: 'P', value: 'yes', color: '#38bdf8' })  // sky-400
  } else {
    lines.push({ label: 'P', value: '—', color: '#6b7280' })
  }

  const prMs = last.pr_interval_ms ?? last.pr_ms
  if (prMs != null && prMs > 0) {
    lines.push({ label: 'PR', value: `${Math.round(prMs)}ms`, color: '#4ade80' }) // green-400
  }

  const qrsMs = last.qrs_duration_ms ?? last.qrs_ms
  if (qrsMs != null) {
    lines.push({ label: 'QRS', value: `${Math.round(qrsMs)}ms`, color: '#f87171' }) // red-400
  }

  const qtMs = last.qt_interval_ms ?? last.qt_ms
  if (qtMs != null) {
    lines.push({ label: 'QT', value: `${Math.round(qtMs)}ms`, color: '#c084fc' })  // purple-400
  }

  let lineY = panelY + 10
  for (const line of lines) {
    ctx.fillStyle = line.color
    ctx.fillText(line.label, panelX + 6, lineY)
    ctx.fillStyle = '#d1d5db'  // gray-300
    ctx.fillText(line.value, panelX + 30, lineY)
    lineY += 12
  }

  ctx.restore()
}

/** Canvas 圆角矩形辅助 */
function roundRect(
  ctx: CanvasRenderingContext2D,
  x: number, y: number, w: number, h: number, r: number,
) {
  ctx.moveTo(x + r, y)
  ctx.arcTo(x + w, y, x + w, y + h, r)
  ctx.arcTo(x + w, y + h, x, y + h, r)
  ctx.arcTo(x, y + h, x, y, r)
  ctx.arcTo(x, y, x + w, y, r)
  ctx.closePath()
}

/** Feature 2: 将 store 的 smoothingLevel 包装为 computed ref */
const smoothingLevel = computed(() => store.ecgSmoothingLevel)

const { appendSamples, start, stop } = useScrollingCanvas({
  canvasRef,
  sampleRate: 500,
  displaySeconds: 5,
  lineColor: '#22c55e',
  label: 'ECG',
  playbackDelayMs: 180,
  drawOverlay: drawAnnotationOverlay,
  smoothingLevel,
})

function onEcgChunk(chunk: SignalChunk) {
  appendSamples(chunk)
}

const overlayCanvasRef = ref<HTMLCanvasElement | null>(null)

const caliper = useEcgCaliper({
  canvasWidth: () => canvasRef.value?.clientWidth || 800,
  displaySeconds: 5,
  sampleRate: 500,
})

// Watch caliperMode to enter/exit
watch(() => store.caliperMode, (on) => {
  if (on) {
    stop()
    caliper.enter(new Float32Array(0))
  } else {
    caliper.exit()
    start()
  }
})

function onCaliperClick(e: MouseEvent) {
  const canvas = overlayCanvasRef.value
  if (!canvas) return
  const rect = canvas.getBoundingClientRect()
  const x = e.clientX - rect.left
  caliper.addMarker(x)
  drawCaliperOverlay()
}

function drawCaliperOverlay() {
  const canvas = overlayCanvasRef.value
  if (!canvas) return
  const ctx = canvas.getContext('2d')
  if (!ctx) return
  const dpr = window.devicePixelRatio || 1
  canvas.width = canvas.clientWidth * dpr
  canvas.height = canvas.clientHeight * dpr
  ctx.scale(dpr, dpr)
  ctx.clearRect(0, 0, canvas.clientWidth, canvas.clientHeight)

  // Draw markers as vertical dashed lines
  for (const marker of caliper.markers.value) {
    ctx.strokeStyle = '#ffffff'
    ctx.lineWidth = 1
    ctx.setLineDash([4, 4])
    ctx.beginPath()
    ctx.moveTo(marker.x, 0)
    ctx.lineTo(marker.x, canvas.clientHeight)
    ctx.stroke()
  }

  // Draw pair connections
  for (const pair of caliper.pairs.value) {
    ctx.strokeStyle = pair.color
    ctx.lineWidth = 2
    ctx.setLineDash([])
    const y = canvas.clientHeight / 2
    ctx.beginPath()
    ctx.moveTo(pair.a.x, y - 5)
    ctx.lineTo(pair.a.x, y + 5)
    ctx.moveTo(pair.a.x, y)
    ctx.lineTo(pair.b.x, y)
    ctx.moveTo(pair.b.x, y - 5)
    ctx.lineTo(pair.b.x, y + 5)
    ctx.stroke()
  }
}

onMounted(() => {
  store.registerEcgCallback(onEcgChunk)
  start()
})

onUnmounted(() => {
  store.unregisterEcgCallback(onEcgChunk)
  stop()
})
</script>

<template>
  <div class="relative w-full h-full min-h-[160px] rounded-lg overflow-hidden border border-gray-700">
    <canvas ref="canvasRef" class="w-full h-full block" />
    <!-- Caliper overlay -->
    <canvas
      v-if="store.caliperMode"
      ref="overlayCanvasRef"
      class="absolute inset-0 w-full h-full cursor-crosshair"
      @click="onCaliperClick"
    />
    <!-- Caliper measurements display -->
    <div v-if="store.caliperMode && caliper.pairs.value.length > 0" class="absolute bottom-2 left-2 space-y-1">
      <div
        v-for="pair in caliper.pairs.value"
        :key="pair.id"
        class="text-xs px-2 py-1 rounded bg-gray-900/80"
        :style="{ color: pair.color }"
      >
        {{ pair.intervalMs }} ms
        <span v-if="pair.bpm" class="text-white/50 ml-1">({{ pair.bpm }} bpm)</span>
      </div>
    </div>
    <!-- Freeze indicator -->
    <div v-if="store.caliperMode" class="absolute top-2 right-2 px-2 py-0.5 text-[10px] bg-sky-500/20 text-sky-400 rounded border border-sky-500/30">
      ❄️ 冻结
    </div>
    <!-- Feature 2: 信号平滑级别选择器 -->
    <select
      v-model="store.ecgSmoothingLevel"
      class="absolute top-2 left-16 bg-gray-800/80 text-gray-300 text-[10px] px-1.5 py-0.5 rounded border border-gray-600 outline-none cursor-pointer hover:bg-gray-700/80"
    >
      <option value="off">原始</option>
      <option value="low">轻度平滑</option>
      <option value="high">强平滑</option>
    </select>
  </div>
</template>

<script setup lang="ts">
/**
 * 电生理趋势图 — 显示 PR/QRS/QT 间期趋势（Canvas 绘制）
 */
import { ref, watch, onMounted, onUnmounted } from 'vue'
import { useVirtualHumanStore } from '@/store/virtualHuman'

const store = useVirtualHumanStore()
const canvas = ref<HTMLCanvasElement | null>(null)
let resizeObs: ResizeObserver | null = null

function draw() {
  const el = canvas.value
  if (!el) return
  const ctx = el.getContext('2d')
  if (!ctx) return

  const data = store.conductionTrend
  const w = el.width
  const h = el.height
  ctx.clearRect(0, 0, w, h)

  // Background
  ctx.fillStyle = 'rgba(255,255,255,0.03)'
  ctx.fillRect(0, 0, w, h)

  if (data.length === 0) return

  const maxMs = 600

  // Normal range bands
  const drawBand = (minMs: number, maxMs_: number, color: string) => {
    const yMin = h - (maxMs_ / maxMs) * h
    const yMax = h - (minMs / maxMs) * h
    ctx.fillStyle = color
    ctx.fillRect(0, yMin, w, yMax - yMin)
  }
  drawBand(120, 200, 'rgba(34,197,94,0.08)')  // PR normal
  drawBand(60, 120, 'rgba(59,130,246,0.08)')   // QRS normal
  drawBand(350, 440, 'rgba(168,85,247,0.08)')  // QT normal

  // Draw line for a key
  const drawLine = (key: string, color: string) => {
    ctx.beginPath()
    ctx.strokeStyle = color
    ctx.lineWidth = 1.5
    let started = false
    data.forEach((d: Record<string, number>, i: number) => {
      const val = d[key]
      if (val == null) return
      const x = (i / Math.max(data.length - 1, 1)) * w
      const y = h - (val / maxMs) * h
      if (!started) {
        ctx.moveTo(x, y)
        started = true
      } else {
        ctx.lineTo(x, y)
      }
    })
    ctx.stroke()
  }

  drawLine('pr_ms', '#22c55e')   // green for PR
  drawLine('qrs_ms', '#3b82f6')  // blue for QRS
  drawLine('qt_ms', '#a855f7')   // purple for QT

  // Legend
  ctx.font = '10px sans-serif'
  const legend = [
    { label: 'PR', color: '#22c55e', x: 8 },
    { label: 'QRS', color: '#3b82f6', x: 40 },
    { label: 'QT', color: '#a855f7', x: 80 },
  ]
  legend.forEach((l) => {
    ctx.fillStyle = l.color
    ctx.fillRect(l.x, 4, 10, 3)
    ctx.fillStyle = 'rgba(255,255,255,0.5)'
    ctx.fillText(l.label, l.x + 14, 10)
  })
}

function resizeCanvas() {
  const el = canvas.value
  if (!el) return
  const parent = el.parentElement
  el.width = el.offsetWidth
  // Use parent available height if possible, otherwise fallback to 120
  const availableH = parent ? parent.clientHeight - el.offsetTop : 0
  el.height = availableH > 40 ? availableH : 120
  draw()
}

watch(() => store.conductionTrend, draw, { deep: true })

onMounted(() => {
  resizeCanvas()
  if (canvas.value && typeof ResizeObserver !== 'undefined') {
    resizeObs = new ResizeObserver(resizeCanvas)
    resizeObs.observe(canvas.value)
  }
})

onUnmounted(() => {
  if (resizeObs) {
    resizeObs.disconnect()
    resizeObs = null
  }
})
</script>

<template>
  <div class="bg-white/[0.06] rounded-lg border border-white/[0.08] p-3 flex flex-col h-full min-h-0">
    <div class="flex items-center justify-between mb-2 shrink-0">
      <h4 class="text-xs font-medium text-white/60">电生理趋势</h4>
      <span class="text-[10px] text-white/30">最近 60 拍</span>
    </div>
    <div class="flex-1 min-h-0 relative">
      <canvas ref="canvas" class="w-full h-full" />
      <div
        v-if="store.conductionTrend.length === 0"
        class="absolute inset-0 flex items-center justify-center text-xs text-white/30"
      >
        连接后显示趋势数据
      </div>
    </div>
  </div>
</template>

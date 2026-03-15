<script setup lang="ts">
/**
 * CardiacCycleChart — Wiggers 图 (心动周期)
 *
 * 叠加: LV Pressure (red), Aortic Pressure (blue), LV Volume (green)
 */
import { ref, onMounted, onUnmounted } from 'vue'
import { useVirtualHumanStore } from '@/store/virtualHuman'
import FloatingPanel from './FloatingPanel.vue'

const emit = defineEmits<{ close: [] }>()
const store = useVirtualHumanStore()
const canvasRef = ref<HTMLCanvasElement | null>(null)

const CURVES = [
  { key: 'lv_pressure', color: '#ef4444', label: 'LV P' },
  { key: 'aortic_pressure', color: '#3b82f6', label: 'Ao P' },
  { key: 'lv_volume', color: '#22c55e', label: 'LV V' },
] as const

function draw() {
  const canvas = canvasRef.value
  if (!canvas) return
  const ctx = canvas.getContext('2d')
  if (!ctx) return

  const detail = store.physiologyDetail
  const cc = detail?.cardiac_cycle
  if (!cc) return

  const W = canvas.width
  const H = canvas.height
  const pad = { top: 14, right: 10, bottom: 24, left: 40 }
  const plotW = W - pad.left - pad.right
  const plotH = H - pad.top - pad.bottom

  ctx.clearRect(0, 0, W, H)

  // Grid
  ctx.strokeStyle = 'rgba(255,255,255,0.06)'
  ctx.lineWidth = 0.5
  for (let i = 0; i <= 4; i++) {
    const y = pad.top + (plotH * i) / 4
    ctx.beginPath(); ctx.moveTo(pad.left, y); ctx.lineTo(W - pad.right, y); ctx.stroke()
  }

  // Draw each curve (normalized to own range)
  for (const curve of CURVES) {
    const data = cc[curve.key as keyof typeof cc] as number[]
    if (!data || data.length === 0) continue

    const min = Math.min(...data)
    const max = Math.max(...data)
    const range = max - min || 1

    ctx.strokeStyle = curve.color
    ctx.lineWidth = 1.5
    ctx.globalAlpha = 0.85
    ctx.beginPath()
    for (let i = 0; i < data.length; i++) {
      const x = pad.left + (i / (data.length - 1)) * plotW
      const y = pad.top + plotH - ((data[i] - min) / range) * plotH
      if (i === 0) ctx.moveTo(x, y)
      else ctx.lineTo(x, y)
    }
    ctx.stroke()
    ctx.globalAlpha = 1.0
  }

  // X axis
  ctx.fillStyle = 'rgba(255,255,255,0.4)'
  ctx.font = '9px monospace'
  ctx.textAlign = 'center'
  ctx.fillText('Time (ms)', pad.left + plotW / 2, H - 2)

  // Legend
  let legendX = pad.left + 4
  ctx.font = '8px monospace'
  for (const curve of CURVES) {
    ctx.fillStyle = curve.color
    ctx.fillRect(legendX, pad.top - 10, 12, 3)
    ctx.fillStyle = 'rgba(255,255,255,0.5)'
    ctx.textAlign = 'left'
    ctx.fillText(curve.label, legendX + 15, pad.top - 6)
    legendX += 60
  }
}

let animId = 0
function renderLoop() {
  draw()
  animId = requestAnimationFrame(renderLoop)
}

function resizeCanvas() {
  const canvas = canvasRef.value
  if (!canvas) return
  const rect = canvas.parentElement?.getBoundingClientRect()
  if (rect) {
    canvas.width = rect.width * (window.devicePixelRatio || 1)
    canvas.height = rect.height * (window.devicePixelRatio || 1)
    canvas.style.width = rect.width + 'px'
    canvas.style.height = rect.height + 'px'
    const ctx = canvas.getContext('2d')
    if (ctx) ctx.scale(window.devicePixelRatio || 1, window.devicePixelRatio || 1)
  }
}

onMounted(() => {
  resizeCanvas()
  animId = requestAnimationFrame(renderLoop)
})

onUnmounted(() => {
  cancelAnimationFrame(animId)
})
</script>

<template>
  <FloatingPanel title="Cardiac Cycle (Wiggers)" :default-x="260" :default-y="340" :width="420" :height="280" @close="emit('close')">
    <canvas ref="canvasRef" class="w-full h-full block" />
  </FloatingPanel>
</template>

<script setup lang="ts">
/**
 * PvLoopChart — 压力-容积环实时可视化
 *
 * X轴: LV Volume (mL), Y轴: LV Pressure (mmHg)
 * 每拍更新一次。
 */
import { ref, onMounted, onUnmounted } from 'vue'
import { useVirtualHumanStore } from '@/store/virtualHuman'
import FloatingPanel from './FloatingPanel.vue'

const emit = defineEmits<{ close: [] }>()
const store = useVirtualHumanStore()
const canvasRef = ref<HTMLCanvasElement | null>(null)

function drawLoop() {
  const canvas = canvasRef.value
  if (!canvas) return
  const ctx = canvas.getContext('2d')
  if (!ctx) return

  const detail = store.physiologyDetail
  const pv = detail?.pv_loop
  if (!pv || !pv.lv_volume.length || !pv.lv_pressure.length) return

  const W = canvas.width
  const H = canvas.height
  const pad = { top: 20, right: 15, bottom: 30, left: 45 }
  const plotW = W - pad.left - pad.right
  const plotH = H - pad.top - pad.bottom

  ctx.clearRect(0, 0, W, H)

  // Data ranges
  const vols = pv.lv_volume
  const pres = pv.lv_pressure
  const vMin = Math.min(...vols) * 0.9
  const vMax = Math.max(...vols) * 1.1
  const pMin = Math.max(0, Math.min(...pres) - 10)
  const pMax = Math.max(...pres) * 1.1

  const xScale = (v: number) => pad.left + ((v - vMin) / (vMax - vMin)) * plotW
  const yScale = (p: number) => pad.top + plotH - ((p - pMin) / (pMax - pMin)) * plotH

  // Grid
  ctx.strokeStyle = 'rgba(255,255,255,0.08)'
  ctx.lineWidth = 0.5
  for (let i = 0; i <= 4; i++) {
    const y = pad.top + (plotH * i) / 4
    ctx.beginPath(); ctx.moveTo(pad.left, y); ctx.lineTo(W - pad.right, y); ctx.stroke()
    const x = pad.left + (plotW * i) / 4
    ctx.beginPath(); ctx.moveTo(x, pad.top); ctx.lineTo(x, H - pad.bottom); ctx.stroke()
  }

  // Axes labels
  ctx.fillStyle = 'rgba(255,255,255,0.4)'
  ctx.font = '9px monospace'
  ctx.textAlign = 'center'
  ctx.fillText('Volume (mL)', pad.left + plotW / 2, H - 4)
  ctx.save()
  ctx.translate(10, pad.top + plotH / 2)
  ctx.rotate(-Math.PI / 2)
  ctx.fillText('Pressure (mmHg)', 0, 0)
  ctx.restore()

  // Tick labels
  ctx.fillStyle = 'rgba(255,255,255,0.3)'
  ctx.font = '8px monospace'
  ctx.textAlign = 'right'
  for (let i = 0; i <= 4; i++) {
    const pVal = pMin + ((pMax - pMin) * (4 - i)) / 4
    ctx.fillText(pVal.toFixed(0), pad.left - 4, pad.top + (plotH * i) / 4 + 3)
  }
  ctx.textAlign = 'center'
  for (let i = 0; i <= 4; i++) {
    const vVal = vMin + ((vMax - vMin) * i) / 4
    ctx.fillText(vVal.toFixed(0), pad.left + (plotW * i) / 4, H - pad.bottom + 12)
  }

  // P-V loop
  ctx.strokeStyle = '#38bdf8'
  ctx.lineWidth = 2
  ctx.shadowColor = '#38bdf8'
  ctx.shadowBlur = 6
  ctx.beginPath()
  for (let i = 0; i < Math.min(vols.length, pres.length); i++) {
    const x = xScale(vols[i])
    const y = yScale(pres[i])
    if (i === 0) ctx.moveTo(x, y)
    else ctx.lineTo(x, y)
  }
  ctx.closePath()
  ctx.stroke()
  ctx.shadowBlur = 0
}

let animId = 0
function renderLoop() {
  drawLoop()
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
  <FloatingPanel title="P-V Loop" :default-x="60" :default-y="60" :width="380" :height="300" @close="emit('close')">
    <canvas ref="canvasRef" class="w-full h-full block" />
  </FloatingPanel>
</template>

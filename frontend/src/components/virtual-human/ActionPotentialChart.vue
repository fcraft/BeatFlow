<script setup lang="ts">
/**
 * ActionPotentialChart — 4节点动作电位叠加可视化
 *
 * SA (red), AV (orange), His (green), Purkinje (blue)
 */
import { ref, onMounted, onUnmounted } from 'vue'
import { useVirtualHumanStore } from '@/store/virtualHuman'
import FloatingPanel from './FloatingPanel.vue'

const emit = defineEmits<{ close: [] }>()
const store = useVirtualHumanStore()
const canvasRef = ref<HTMLCanvasElement | null>(null)

const NODE_COLORS: Record<string, string> = {
  sa: '#ef4444',       // red
  av: '#f97316',       // orange
  his: '#22c55e',      // green
  purkinje: '#3b82f6', // blue
}
const NODE_ORDER = ['sa', 'av', 'his', 'purkinje']

function draw() {
  const canvas = canvasRef.value
  if (!canvas) return
  const ctx = canvas.getContext('2d')
  if (!ctx) return

  const detail = store.physiologyDetail
  const aps = detail?.action_potentials
  if (!aps) return

  const W = canvas.width
  const H = canvas.height
  const pad = { top: 12, right: 10, bottom: 20, left: 35 }
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

  // Y axis label
  ctx.fillStyle = 'rgba(255,255,255,0.4)'
  ctx.font = '9px monospace'
  ctx.textAlign = 'right'
  ctx.fillText('1.0', pad.left - 4, pad.top + 4)
  ctx.fillText('0.0', pad.left - 4, H - pad.bottom + 4)

  // X axis label
  ctx.textAlign = 'center'
  ctx.fillText('Time (ms)', pad.left + plotW / 2, H - 2)

  // Draw each node trace
  for (const node of NODE_ORDER) {
    const trace = aps[node]
    if (!trace || trace.length === 0) continue

    ctx.strokeStyle = NODE_COLORS[node] || '#888'
    ctx.lineWidth = 1.5
    ctx.globalAlpha = 0.85
    ctx.beginPath()
    for (let i = 0; i < trace.length; i++) {
      const x = pad.left + (i / (trace.length - 1)) * plotW
      const y = pad.top + plotH - trace[i] * plotH
      if (i === 0) ctx.moveTo(x, y)
      else ctx.lineTo(x, y)
    }
    ctx.stroke()
    ctx.globalAlpha = 1.0
  }

  // Legend
  let legendX = pad.left + 4
  ctx.font = '8px monospace'
  for (const node of NODE_ORDER) {
    if (!aps[node]) continue
    ctx.fillStyle = NODE_COLORS[node] || '#888'
    ctx.fillRect(legendX, pad.top - 8, 12, 3)
    ctx.fillStyle = 'rgba(255,255,255,0.5)'
    ctx.textAlign = 'left'
    ctx.fillText(node.toUpperCase(), legendX + 15, pad.top - 4)
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
  <FloatingPanel title="Action Potentials" :default-x="460" :default-y="60" :width="380" :height="260" @close="emit('close')">
    <canvas ref="canvasRef" class="w-full h-full block" />
  </FloatingPanel>
</template>

<script setup lang="ts">
/**
 * CmdEcgWaveform — ECG Canvas (复用 useScrollingCanvas)
 */
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useScrollingCanvas } from '@/composables/useScrollingCanvas'
import { useEcgCaliper } from '@/composables/useEcgCaliper'
import { useVirtualHumanStore } from '@/store/virtualHuman'
import type { SignalChunk } from '@/store/virtualHuman'

const store = useVirtualHumanStore()
const canvasRef = ref<HTMLCanvasElement | null>(null)

const beatKindColors: Record<string, string> = {
  sinus: '#34C759', pvc: '#FF9500', af: '#AF52DE',
  svt_reentry: '#FFD60A', escape: '#007AFF', nsvt: '#FF3B30',
}
const beatKindLabels: Record<string, string> = {
  sinus: '窦性', pvc: 'PVC', af: '房颤', svt_reentry: 'SVT',
  escape: '逸搏', nsvt: 'NSVT', normal: '窦性',
}

let cachedAnnotation: Record<string, any> | null = null

function drawAnnotationOverlay(ctx: CanvasRenderingContext2D, w: number, h: number) {
  if (!store.showAnnotations) return
  const annotations = store.beatAnnotations
  if (annotations && annotations.length > 0) cachedAnnotation = annotations[annotations.length - 1]
  if (!cachedAnnotation) return

  const last = cachedAnnotation
  const beatKind = last.beat_kind || last.morphology || 'normal'
  const color = beatKindColors[beatKind] || '#6C6C70'
  const label = beatKindLabels[beatKind] || beatKind

  ctx.save()
  ctx.font = 'bold 10px Inter, system-ui, sans-serif'
  const tagW = ctx.measureText(label).width + 12
  const tagX = w - tagW - 8
  ctx.fillStyle = color
  ctx.globalAlpha = 0.85
  ctx.beginPath()
  ctx.roundRect(tagX, 6, tagW, 18, 4)
  ctx.fill()
  ctx.globalAlpha = 1
  ctx.fillStyle = '#ffffff'
  ctx.textAlign = 'center'
  ctx.textBaseline = 'middle'
  ctx.fillText(label, tagX + tagW / 2, 15)
  ctx.restore()
}

const smoothingLevel = computed(() => store.ecgSmoothingLevel)

/** 根据屏幕宽度计算显示秒数：手机 2.5s，平板 3.5s，桌面 5s */
const screenW = typeof window !== 'undefined' ? window.innerWidth : 1024
const dispSec = screenW < 768 ? 2.5 : screenW < 1024 ? 3.5 : 5

const { appendSamples, start, stop } = useScrollingCanvas({
  canvasRef,
  sampleRate: 500,
  displaySeconds: dispSec,
  lineColor: '#34C759',
  backgroundColor: '#060608',
  gridColor: 'rgba(255,255,255,0.03)',
  label: `ECG ${store.selectedLeads[0] || 'II'}`,
  playbackDelayMs: 180,
  drawOverlay: drawAnnotationOverlay,
  smoothingLevel,
})

function onEcgChunk(chunk: SignalChunk) { appendSamples(chunk) }

const overlayCanvasRef = ref<HTMLCanvasElement | null>(null)
const caliper = useEcgCaliper({
  canvasWidth: () => canvasRef.value?.clientWidth || 800,
  displaySeconds: dispSec,
  sampleRate: 500,
})

watch(() => store.caliperMode, (on) => {
  if (on) { stop(); caliper.enter(new Float32Array(0)) }
  else { caliper.exit(); start() }
})

function onCaliperClick(e: MouseEvent) {
  const canvas = overlayCanvasRef.value
  if (!canvas) return
  const rect = canvas.getBoundingClientRect()
  caliper.addMarker(e.clientX - rect.left)
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
  for (const marker of caliper.markers.value) {
    ctx.strokeStyle = '#ffffff'
    ctx.lineWidth = 1
    ctx.setLineDash([4, 4])
    ctx.beginPath()
    ctx.moveTo(marker.x, 0)
    ctx.lineTo(marker.x, canvas.clientHeight)
    ctx.stroke()
  }
  for (const pair of caliper.pairs.value) {
    ctx.strokeStyle = pair.color
    ctx.lineWidth = 2
    ctx.setLineDash([])
    const y = canvas.clientHeight / 2
    ctx.beginPath()
    ctx.moveTo(pair.a.x, y - 5); ctx.lineTo(pair.a.x, y + 5)
    ctx.moveTo(pair.a.x, y); ctx.lineTo(pair.b.x, y)
    ctx.moveTo(pair.b.x, y - 5); ctx.lineTo(pair.b.x, y + 5)
    ctx.stroke()
  }
}

onMounted(() => { store.registerEcgCallback(onEcgChunk); start() })
onUnmounted(() => { store.unregisterEcgCallback(onEcgChunk); stop() })
</script>

<template>
  <div class="relative w-full h-full rounded-xl overflow-hidden border border-white/[0.04]">
    <canvas ref="canvasRef" class="w-full h-full block" />
    <canvas v-if="store.caliperMode" ref="overlayCanvasRef"
            class="absolute inset-0 w-full h-full cursor-crosshair" @click="onCaliperClick" />
    <div v-if="store.caliperMode && caliper.pairs.value.length > 0"
         class="absolute bottom-2 left-2 space-y-1">
      <div v-for="pair in caliper.pairs.value" :key="pair.id"
           class="text-xs px-2 py-1 rounded-lg bg-black/70 backdrop-blur-sm"
           :style="{ color: pair.color }">
        {{ pair.intervalMs }} ms
        <span v-if="pair.bpm" class="text-white/40 ml-1">({{ pair.bpm }} bpm)</span>
      </div>
    </div>
    <div v-if="store.caliperMode"
         class="absolute top-2 right-2 px-2 py-0.5 text-[10px] bg-[#007AFF]/15 text-[#007AFF] rounded-full border border-[#007AFF]/25">
      ❄️ 冻结
    </div>
    <!-- Smoothing selector -->
    <select v-model="store.ecgSmoothingLevel"
            class="absolute top-2 left-20 bg-black/60 backdrop-blur-sm text-white/50
                   text-[10px] px-1.5 py-0.5 rounded-lg border border-white/[0.08]
                   outline-none cursor-pointer hover:bg-white/[0.08]">
      <option value="off">原始</option>
      <option value="low">轻度平滑</option>
      <option value="high">强平滑</option>
    </select>
  </div>
</template>

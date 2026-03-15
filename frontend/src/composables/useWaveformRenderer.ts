import { ref, onMounted, onBeforeUnmount, type Ref } from 'vue'
import { useWaveformStore, type WaveformChannel } from '@/store/waveform'

export function useWaveformRenderer(
  canvasRef: Ref<HTMLCanvasElement | null>,
  channel: Ref<WaveformChannel>,
) {
  const store = useWaveformStore()
  let animationId = 0

  function draw() {
    const canvas = canvasRef.value
    if (!canvas) { animationId = requestAnimationFrame(draw); return }

    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const { width, height } = canvas

    // Clear with slight fade for trail effect
    ctx.fillStyle = 'rgba(15, 15, 26, 0.3)'
    ctx.fillRect(0, 0, width, height)

    // Grid
    if (channel.value.gridEnabled) {
      ctx.strokeStyle = 'rgba(255,255,255,0.05)'
      ctx.lineWidth = 0.5
      const gridSpacing = 25 // pixels
      for (let x = 0; x < width; x += gridSpacing) {
        ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, height); ctx.stroke()
      }
      for (let y = 0; y < height; y += gridSpacing) {
        ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(width, y); ctx.stroke()
      }
    }

    // Draw waveform
    const buf = store.buffers.get(channel.value.id)
    const writePos = store.writePositions.get(channel.value.id) ?? 0
    if (!buf || writePos === 0) {
      animationId = requestAnimationFrame(draw)
      return
    }

    const samplesPerPixel = channel.value.sampleRate / (channel.value.speed * 2)
    const visibleSamples = Math.floor(width * samplesPerPixel)
    const startSample = Math.max(0, writePos - visibleSamples)

    ctx.beginPath()
    ctx.strokeStyle = channel.value.color
    ctx.lineWidth = 1.5

    const gain = channel.value.gain
    const midY = height / 2

    for (let px = 0; px < width; px++) {
      const sampleIdx = startSample + Math.floor(px * samplesPerPixel)
      const bufIdx = sampleIdx % buf.length
      const value = buf[bufIdx] * gain
      const y = midY - value * midY * 0.8

      if (px === 0) ctx.moveTo(px, y)
      else ctx.lineTo(px, y)
    }
    ctx.stroke()

    // Playhead
    ctx.strokeStyle = 'rgba(255,255,255,0.3)'
    ctx.lineWidth = 1
    ctx.beginPath()
    ctx.moveTo(width - 1, 0)
    ctx.lineTo(width - 1, height)
    ctx.stroke()

    animationId = requestAnimationFrame(draw)
  }

  onMounted(() => {
    // Init buffer if not already
    if (!store.buffers.has(channel.value.id)) {
      store.initBuffer(channel.value.id, channel.value.sampleRate)
    }
    animationId = requestAnimationFrame(draw)
  })

  onBeforeUnmount(() => {
    cancelAnimationFrame(animationId)
  })
}

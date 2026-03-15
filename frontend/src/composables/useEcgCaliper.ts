import { ref, computed } from 'vue'

// ── Pure helpers ─────────────────────────────────────────────────────────────

export function pixelToMs(
  pixelDist: number,
  canvasWidth: number,
  displaySeconds: number,
  _sampleRate: number
): number {
  if (canvasWidth <= 0) return 0
  return Math.round(Math.abs(pixelDist) * (displaySeconds * 1000) / canvasWidth)
}

export function msToRate(intervalMs: number): number | null {
  if (intervalMs <= 0) return null
  return Math.round(60000 / intervalMs)
}

// ── Types ────────────────────────────────────────────────────────────────────

export interface CaliperMarker {
  id: number
  x: number
}

export interface CaliperPair {
  id: number
  a: CaliperMarker
  b: CaliperMarker
  intervalMs: number
  bpm: number | null
  color: string
}

// ── Composable ───────────────────────────────────────────────────────────────

const PAIR_COLORS = ['#3b82f6', '#22c55e', '#f97316']
const MAX_MARKERS = 6

export function useEcgCaliper(options: {
  canvasWidth: () => number
  displaySeconds: number
  sampleRate: number
}) {
  const { canvasWidth, displaySeconds, sampleRate } = options

  const active = ref(false)
  const markers = ref<CaliperMarker[]>([])
  const frozenData = ref<Float32Array | null>(null)
  let nextId = 0

  // Sorted markers paired as (0+1), (2+3), (4+5), max 3 pairs
  const pairs = computed<CaliperPair[]>(() => {
    const sorted = [...markers.value].sort((a, b) => a.x - b.x)
    const result: CaliperPair[] = []
    for (let i = 0; i + 1 < sorted.length && result.length < 3; i += 2) {
      const a = sorted[i]
      const b = sorted[i + 1]
      const intervalMs = pixelToMs(b.x - a.x, canvasWidth(), displaySeconds, sampleRate)
      result.push({
        id: result.length,
        a,
        b,
        intervalMs,
        bpm: msToRate(intervalMs),
        color: PAIR_COLORS[result.length] ?? '#3b82f6',
      })
    }
    return result
  })

  function enter(bufferSnapshot: Float32Array) {
    active.value = true
    frozenData.value = bufferSnapshot
    markers.value = []
    nextId = 0
  }

  function exit() {
    active.value = false
    frozenData.value = null
    markers.value = []
    nextId = 0
  }

  function addMarker(x: number) {
    if (markers.value.length >= MAX_MARKERS) return
    markers.value = [...markers.value, { id: nextId++, x }]
  }

  function moveMarker(id: number, newX: number) {
    markers.value = markers.value.map(m => m.id === id ? { ...m, x: newX } : m)
  }

  function removeLastMarker() {
    if (markers.value.length === 0) return
    markers.value = markers.value.slice(0, -1)
  }

  function clearMarkers() {
    markers.value = []
  }

  return {
    active,
    markers,
    pairs,
    frozenData,
    enter,
    exit,
    addMarker,
    moveMarker,
    removeLastMarker,
    clearMarkers,
  }
}

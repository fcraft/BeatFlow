<template>
  <AppLayout>
    <div class="page-container">
      <button class="btn-ghost btn-sm mb-5 -ml-1" @click="$router.back()">
        <ChevronLeft class="w-4 h-4" />返回
      </button>

      <div v-if="loading" class="flex items-center justify-center py-32">
        <span class="spinner w-8 h-8" />
      </div>

      <template v-else-if="assoc">
        <!-- Header -->
        <div class="card p-5 mb-5">
          <div class="flex items-start gap-4">
            <div class="w-12 h-12 rounded-xl bg-indigo-50 flex items-center justify-center shrink-0">
              <Layers class="w-6 h-6 text-indigo-500" />
            </div>
            <div class="flex-1 min-w-0">
              <h1 class="text-lg font-bold text-gray-900">{{ assoc.name || '未命名关联' }}</h1>
              <p v-if="assoc.notes" class="text-xs text-gray-400 mt-0.5">{{ assoc.notes }}</p>
              <div class="flex flex-wrap gap-2 mt-2">
                <RouterLink v-if="assoc.ecg_file" :to="`/files/${assoc.ecg_file.id}`"
                  class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs bg-red-50 text-red-600 border border-red-100 hover:bg-red-100 hover:border-red-300 transition-colors group">
                  <Activity class="w-3 h-3" />ECG: {{ assoc.ecg_file.original_filename }}
                  <ExternalLink class="w-2.5 h-2.5 opacity-0 group-hover:opacity-60 transition-opacity" />
                </RouterLink>
                <RouterLink v-if="assoc.pcg_file" :to="`/files/${assoc.pcg_file.id}`"
                  class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs bg-purple-50 text-purple-600 border border-purple-100 hover:bg-purple-100 hover:border-purple-300 transition-colors group">
                  <Waves class="w-3 h-3" />PCG: {{ assoc.pcg_file.original_filename }}
                  <ExternalLink class="w-2.5 h-2.5 opacity-0 group-hover:opacity-60 transition-opacity" />
                </RouterLink>
                <RouterLink v-if="assoc.video_file" :to="`/files/${assoc.video_file.id}`"
                  class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs bg-blue-50 text-blue-600 border border-blue-100 hover:bg-blue-100 hover:border-blue-300 transition-colors group">
                  <Video class="w-3 h-3" />视频: {{ assoc.video_file.original_filename }}
                  <ExternalLink class="w-2.5 h-2.5 opacity-0 group-hover:opacity-60 transition-opacity" />
                </RouterLink>
              </div>
            </div>
          </div>
        </div>

        <!-- Sync Player -->
        <div class="card p-5 mb-5">
          <div class="flex items-center justify-between mb-4">
            <h3 class="text-sm font-semibold text-gray-900">同步播放</h3>
            <div class="flex items-center gap-2">
              <span class="text-xs text-gray-400 font-mono">{{ fmtTime(playPos) }} / {{ fmtTime(totalDuration) }}</span>
              <button
                class="w-9 h-9 rounded-full bg-blue-500 hover:bg-blue-600 flex items-center justify-center text-white transition-colors"
                @click="togglePlay"
              >
                <Pause v-if="isPlaying" class="w-4 h-4" />
                <Play v-else class="w-4 h-4 ml-0.5" />
              </button>
            </div>
          </div>

          <!-- Master progress bar — 支持点击 + 拖拽 seek -->
          <div class="relative h-3 bg-gray-100 rounded-full cursor-pointer mb-4 select-none"
            ref="masterBarRef"
            @mousedown="onMasterMouseDown">
            <div class="absolute inset-y-0 left-0 bg-blue-400 rounded-full pointer-events-none"
              :style="{ width: totalDuration > 0 ? (playPos / totalDuration * 100) + '%' : '0%' }" />
            <!-- Playhead thumb -->
            <div class="absolute top-1/2 -translate-y-1/2 w-3 h-3 bg-blue-500 rounded-full shadow transition-transform hover:scale-125 pointer-events-none"
              :style="{ left: `calc(${totalDuration > 0 ? (playPos / totalDuration * 100) : 0}% - 6px)` }" />
          </div>

          <!-- Volume (PCG audio) -->
          <div v-if="assoc.pcg_file" class="flex items-center gap-3">
            <Volume2 class="w-4 h-4 text-gray-400 shrink-0" />
            <input type="range" min="0" max="1" step="0.05" :value="volume"
              class="w-32 accent-purple-500" @input="setVolume" />
            <span class="text-xs text-gray-400">PCG 音量</span>
            <span class="ml-auto text-xs text-gray-400">ECG 无声</span>
          </div>

          <!-- Hidden audio -->
          <audio ref="pcgAudio" @timeupdate="onPcgTimeUpdate" @ended="onEnded" @loadedmetadata="onPcgMeta" />
          <video ref="videoEl" class="hidden" @timeupdate="onVideoTimeUpdate" @ended="onEnded" @loadedmetadata="onVideoMeta" />
        </div>

        <!-- Waveform tracks -->
        <div class="space-y-3 mb-5">

          <!-- ECG track -->
          <div v-if="assoc.ecg_file" class="card p-4">
            <div class="flex items-center justify-between mb-2">
              <span class="flex items-center gap-1.5 text-sm font-medium text-gray-800">
                <Activity class="w-4 h-4 text-red-500" />ECG 心电
                <span class="text-xs text-gray-400 font-normal">（基准轨道，无声）</span>
              </span>
              <div class="flex items-center gap-1.5">
                <span class="text-xs text-gray-400 font-mono">{{ ecgZoomLabel }}</span>
                <button class="btn-icon btn-sm rounded" @click="zoomEcg(1, (ecgContainer?.clientWidth||200)/2, ecgContainer?.clientWidth||200)"><ZoomOut class="w-3.5 h-3.5" /></button>
                <button class="btn-icon btn-sm rounded" @click="zoomEcg(-1, (ecgContainer?.clientWidth||200)/2, ecgContainer?.clientWidth||200)"><ZoomIn class="w-3.5 h-3.5" /></button>
                <button class="btn-icon btn-sm rounded" @click="resetEcgView"><Maximize2 class="w-3.5 h-3.5" /></button>
              </div>
            </div>
            <div ref="ecgContainer"
              class="relative bg-gray-950 rounded-lg overflow-hidden select-none"
              style="height:120px; cursor:grab"
              :style="{ cursor: ecgDragging ? 'grabbing' : 'grab' }"
              @wheel.prevent="onEcgWheel"
              @mousedown="onEcgMouseDown"
              @mousemove="onEcgMouseMove"
              @mouseup="onEcgMouseUp"
              @mouseleave="onEcgMouseLeave">
              <canvas ref="ecgCanvas" class="absolute inset-0 w-full h-full" />
              <!-- Playhead -->
              <div v-if="totalDuration > 0"
                class="absolute top-0 bottom-0 w-px bg-orange-400 pointer-events-none"
                :style="{ left: getPlayheadPct('ecg') + '%' }" />
              <div v-if="loadingEcgWave" class="absolute inset-0 flex items-center justify-center">
                <span class="spinner w-5 h-5" />
              </div>
              <div v-else-if="ecgWave.length === 0" class="absolute inset-0 flex items-center justify-center text-xs text-gray-500">
                暂无波形数据
              </div>
            </div>
          </div>

          <!-- PCG track -->
          <div v-if="assoc.pcg_file" class="card p-4">
            <div class="flex items-center justify-between mb-2">
              <span class="flex items-center gap-1.5 text-sm font-medium text-gray-800">
                <Waves class="w-4 h-4 text-purple-500" />PCG 心音
              </span>
              <div class="flex items-center gap-3">
                <!-- PCG offset fine-tune -->
                <div class="flex items-center gap-1.5 text-xs text-gray-500">
                  <span>偏移</span>
                  <input type="number" v-model.number="localPcgOffset"
                    step="0.001" min="-3600" max="3600"
                    class="input py-0.5 px-2 w-24 text-xs text-center font-mono"
                    @change="onOffsetChange" />
                  <span>秒</span>
                  <button class="btn-ghost btn-sm text-xs px-1" @click="localPcgOffset = 0; onOffsetChange()">重置</button>
                </div>
                <div class="flex items-center gap-1.5">
                  <span class="text-xs text-gray-400 font-mono">{{ pcgZoomLabel }}</span>
                  <button class="btn-icon btn-sm rounded" @click="zoomPcg(1, (pcgContainer?.clientWidth||200)/2, pcgContainer?.clientWidth||200)"><ZoomOut class="w-3.5 h-3.5" /></button>
                  <button class="btn-icon btn-sm rounded" @click="zoomPcg(-1, (pcgContainer?.clientWidth||200)/2, pcgContainer?.clientWidth||200)"><ZoomIn class="w-3.5 h-3.5" /></button>
                  <button class="btn-icon btn-sm rounded" @click="resetPcgView"><Maximize2 class="w-3.5 h-3.5" /></button>
                </div>
              </div>
            </div>
            <div ref="pcgContainer"
              class="relative bg-gray-950 rounded-lg overflow-hidden select-none"
              style="height:100px; cursor:grab"
              :style="{ cursor: pcgDragging ? 'grabbing' : 'grab' }"
              @wheel.prevent="onPcgWheel"
              @mousedown="onPcgMouseDown"
              @mousemove="onPcgMouseMove"
              @mouseup="onPcgMouseUp"
              @mouseleave="onPcgMouseLeave">
              <canvas ref="pcgCanvas" class="absolute inset-0 w-full h-full" />
              <!-- PCG playhead shifted by offset -->
              <div v-if="totalDuration > 0"
                class="absolute top-0 bottom-0 w-px bg-orange-400 pointer-events-none"
                :style="{ left: getPlayheadPct('pcg') + '%' }" />
              <div v-if="loadingPcgWave" class="absolute inset-0 flex items-center justify-center">
                <span class="spinner w-5 h-5" />
              </div>
              <div v-else-if="pcgWave.length === 0" class="absolute inset-0 flex items-center justify-center text-xs text-gray-500">
                暂无波形数据
              </div>
            </div>
            <!-- PCG offset slider (coarse) -->
            <div class="flex items-center gap-3 mt-2">
              <span class="text-xs text-gray-500 shrink-0">粗调</span>
              <input type="range" v-model.number="localPcgOffset"
                :min="-Math.min(10, totalDuration)" :max="Math.min(10, totalDuration)"
                step="0.01" class="flex-1 accent-purple-500" @input="onOffsetChange" />
            </div>
          </div>

          <!-- Video track -->
          <div v-if="assoc.video_file" class="card p-4">
            <div class="flex items-center justify-between mb-2">
              <span class="flex items-center gap-1.5 text-sm font-medium text-gray-800">
                <Video class="w-4 h-4 text-blue-500" />视频
              </span>
              <!-- Video offset -->
              <div class="flex items-center gap-1.5 text-xs text-gray-500">
                <span>偏移</span>
                <input type="number" v-model.number="localVideoOffset"
                  step="0.001" min="-3600" max="3600"
                  class="input py-0.5 px-2 w-24 text-xs text-center font-mono"
                  @change="onVideoOffsetChange" />
                <span>秒</span>
                <button class="btn-ghost btn-sm text-xs px-1" @click="localVideoOffset = 0; onVideoOffsetChange()">重置</button>
              </div>
            </div>
            <!-- Video element -->
            <div class="relative bg-black rounded-lg overflow-hidden" style="max-height:320px">
              <video
                ref="videoDisplay"
                class="w-full max-h-80 object-contain"
                :muted="true"
                @loadedmetadata="onVideoDisplayMeta"
              />
              <div v-if="!videoSrcLoaded" class="absolute inset-0 flex items-center justify-center">
                <span class="text-white text-sm">加载中...</span>
              </div>
            </div>
            <!-- Video offset slider -->
            <div class="flex items-center gap-3 mt-2">
              <span class="text-xs text-gray-500 shrink-0">粗调</span>
              <input type="range" v-model.number="localVideoOffset"
                :min="-Math.min(10, totalDuration)" :max="Math.min(10, totalDuration)"
                step="0.01" class="flex-1 accent-blue-500" @input="onVideoOffsetChange" />
            </div>
          </div>
        </div>

        <!-- Save offsets -->
        <div v-if="offsetsDirty" class="card p-4 border-amber-200 bg-amber-50 flex items-center justify-between">
          <span class="text-sm text-amber-800">偏移量已调整，是否保存到关联设置？</span>
          <div class="flex items-center gap-2">
            <button class="btn-ghost btn-sm" @click="discardOffsets">放弃</button>
            <button class="btn-primary btn-sm" :disabled="savingOffsets" @click="saveOffsets">
              <span v-if="savingOffsets" class="spinner w-3.5 h-3.5" />
              保存偏移
            </button>
          </div>
        </div>
      </template>

      <div v-else class="card p-10 text-center text-gray-400">
        <p class="text-sm">关联不存在或已删除</p>
        <button class="btn-secondary btn-sm mt-4" @click="$router.back()">返回</button>
      </div>
    </div>
  </AppLayout>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useRoute, RouterLink } from 'vue-router'
import {
  ChevronLeft, Activity, Waves, Video, Layers,
  Play, Pause, Volume2, ZoomIn, ZoomOut, Maximize2, ExternalLink,
} from 'lucide-vue-next'
import AppLayout from '@/components/layout/AppLayout.vue'
import { useAuthStore } from '@/store/auth'
import { useToastStore } from '@/store/toast'

const route = useRoute()
const auth = useAuthStore()
const toast = useToastStore()
const assocId = route.params.id as string

const authH = computed(() => auth.token ? { Authorization: `Bearer ${auth.token}` } : {})

// ── Data ───────────────────────────────────────────────────────────────────
const loading = ref(true)
const assoc = ref<any>(null)

// ── Playback ───────────────────────────────────────────────────────────────
const isPlaying = ref(false)
const playPos = ref(0)    // master position in seconds (based on ECG timeline)
const volume = ref(0.8)
const pcgAudio = ref<HTMLAudioElement | null>(null)
const videoEl = ref<HTMLVideoElement | null>(null)    // hidden, used for sync
const videoDisplay = ref<HTMLVideoElement | null>(null)
const videoSrcLoaded = ref(false)
const masterBarRef = ref<HTMLElement | null>(null)
let masterDragging = false
let rafId = 0
let masterTimer = 0
let seekingAudio = false    // 标记：audio/video 正在 seek，漂移校正暂停

// ── Offsets ────────────────────────────────────────────────────────────────
const localPcgOffset = ref(0)
const localVideoOffset = ref(0)
const offsetsDirty = ref(false)
const savingOffsets = ref(false)

// ── Durations ─────────────────────────────────────────────────────────────
const ecgDuration = ref(0)
const pcgDuration = ref(0)
const videoDuration = ref(0)
const totalDuration = computed(() => {
  const tracks: number[] = []
  if (ecgDuration.value > 0) tracks.push(ecgDuration.value)
  if (pcgDuration.value > 0) tracks.push(pcgDuration.value + localPcgOffset.value)
  if (videoDuration.value > 0) tracks.push(videoDuration.value + localVideoOffset.value)
  return tracks.length ? Math.max(...tracks) : 0
})

// ── Waveform ECG ───────────────────────────────────────────────────────────
const ecgWave = ref<number[]>([])            // overview：全文件低分辨率
const ecgDetailSamples = ref<number[]>([])   // detail：视口高分辨率
const ecgDetailRange = ref<{ start: number; end: number } | null>(null)
const loadingEcgWave = ref(false)
const ecgCanvas = ref<HTMLCanvasElement | null>(null)
const ecgContainer = ref<HTMLElement | null>(null)
const ecgViewStart = ref(0)
const ecgViewSecs = ref(10)
const ecgDragging = ref(false)
let ecgDragStartX = 0
let ecgDragStartView = 0

// ── Waveform PCG ───────────────────────────────────────────────────────────
const pcgWave = ref<number[]>([])            // overview
const pcgDetailSamples = ref<number[]>([])   // detail
const pcgDetailRange = ref<{ start: number; end: number } | null>(null)
const loadingPcgWave = ref(false)
const pcgCanvas = ref<HTMLCanvasElement | null>(null)
const pcgContainer = ref<HTMLElement | null>(null)
const pcgViewStart = ref(0)
const pcgViewSecs = ref(10)
const pcgDragging = ref(false)
let pcgDragStartX = 0
let pcgDragStartView = 0

// ── Detail fetch debounce ──────────────────────────────────────────────────
let ecgDetailTimer: ReturnType<typeof setTimeout> | null = null
let pcgDetailTimer: ReturnType<typeof setTimeout> | null = null
let ecgDetailFetching = false   // 防止并发请求
let pcgDetailFetching = false
const DETAIL_THRESHOLD_SECS = 60  // 视口 < 60s 时触发 detail fetch

// 交互（缩放/拖拽）使用 300ms 防抖触发
const scheduleDetailFetch = (track: 'ecg' | 'pcg') => {
  const timer = track === 'ecg' ? ecgDetailTimer : pcgDetailTimer
  if (timer) clearTimeout(timer)
  const newTimer = setTimeout(() => {
    doDetailFetch(track)
  }, 300)
  if (track === 'ecg') ecgDetailTimer = newTimer
  else pcgDetailTimer = newTimer
}

const getDetailFetchWindow = (track: 'ecg' | 'pcg', playbackPrefetch = isPlaying.value) => {
  const duration = track === 'ecg' ? ecgDuration.value : pcgDuration.value
  const viewSecs = track === 'ecg' ? ecgViewSecs.value : pcgViewSecs.value
  const viewStart = track === 'ecg' ? ecgViewStart.value : pcgViewStart.value
  const lookAhead = playbackPrefetch ? viewSecs * 3 : viewSecs * 0.5

  return {
    duration,
    viewSecs,
    start: Math.max(0, viewStart - viewSecs * 0.5),
    end: Math.min(duration, viewStart + viewSecs + lookAhead),
  }
}

// 播放时主动检查 detail 覆盖情况并预取（不走 debounce）
const checkPlaybackDetailCoverage = (track: 'ecg' | 'pcg') => {
  const detailRange = track === 'ecg' ? ecgDetailRange.value : pcgDetailRange.value
  const fetching = track === 'ecg' ? ecgDetailFetching : pcgDetailFetching
  const { duration, viewSecs, start, end } = getDetailFetchWindow(track, true)

  if (fetching) return  // 已有请求在飞，等它回来
  if (duration <= 0 || viewSecs >= DETAIL_THRESHOLD_SECS) return

  // 预取窗口必须先按文件时长裁剪，否则短文件会永远满足“还差一个视口”的条件，导致高频重复请求
  const needFetch = !detailRange ||
    detailRange.start > start + 0.001 ||
    detailRange.end < end - 0.001
  if (needFetch) {
    doDetailFetch(track)
  }
}

const doDetailFetch = (track: 'ecg' | 'pcg') => {
  const fileId = track === 'ecg' ? assoc.value?.ecg_file?.id : assoc.value?.pcg_file?.id
  const { duration, viewSecs, start, end } = getDetailFetchWindow(track)
  if (!fileId || duration <= 0 || viewSecs >= DETAIL_THRESHOLD_SECS) return
  fetchDetail(track, fileId, start, end)
}

const fetchDetail = async (track: 'ecg' | 'pcg', fileId: string, t0: number, t1: number) => {
  if (track === 'ecg') ecgDetailFetching = true
  else pcgDetailFetching = true
  const container = track === 'ecg' ? ecgContainer.value : pcgContainer.value
  const containerW = container?.clientWidth ?? 1200
  const pts = Math.min(12000, Math.max(2000, containerW * 4))
  try {
    const r = await fetch(
      `/api/v1/files/${fileId}/waveform?max_points=${pts}&start_time=${t0.toFixed(3)}&end_time=${t1.toFixed(3)}`,
      { headers: (authH.value as Record<string, string>) }
    )
    if (r.ok) {
      const d = await r.json()
      if (track === 'ecg') {
        ecgDetailSamples.value = d.samples ?? []
        ecgDetailRange.value = { start: d.region_start ?? t0, end: d.region_end ?? t1 }
        drawWaveform('ecg')
      } else {
        pcgDetailSamples.value = d.samples ?? []
        pcgDetailRange.value = { start: d.region_start ?? t0, end: d.region_end ?? t1 }
        drawWaveform('pcg')
      }
    }
  } catch { /* ignore */ }
  finally {
    if (track === 'ecg') ecgDetailFetching = false
    else pcgDetailFetching = false
  }
}

// ── Helpers ────────────────────────────────────────────────────────────────
const fmtTime = (s: number) => {
  const m = Math.floor(s / 60)
  const sec = (s - m * 60).toFixed(2).padStart(5, '0')
  return `${m}:${sec}`
}

const ecgZoomLabel = computed(() => `${ecgViewSecs.value.toFixed(1)}s/屏`)
const pcgZoomLabel = computed(() => `${pcgViewSecs.value.toFixed(1)}s/屏`)

// ── Load association ───────────────────────────────────────────────────────
const load = async () => {
  loading.value = true
  const r = await fetch(`/api/v1/associations/${assocId}`, { headers: (authH.value as Record<string, string>) })
  loading.value = false
  if (!r.ok) return
  assoc.value = await r.json()
  localPcgOffset.value = assoc.value.pcg_offset ?? 0
  localVideoOffset.value = assoc.value.video_offset ?? 0

  // Load waveforms
  if (assoc.value.ecg_file) loadWaveform('ecg', assoc.value.ecg_file.id)
  if (assoc.value.pcg_file) {
    loadWaveform('pcg', assoc.value.pcg_file.id)
    await nextTick()
    if (pcgAudio.value) {
      pcgAudio.value.src = `/api/v1/files/${assoc.value.pcg_file.id}/download?token=${auth.token}`
      pcgAudio.value.volume = volume.value
      pcgAudio.value.load()
    }
  }
  if (assoc.value.video_file) {
    await nextTick()
    if (videoDisplay.value) {
      videoDisplay.value.src = `/api/v1/files/${assoc.value.video_file.id}/download?token=${auth.token}`
      videoSrcLoaded.value = true
    }
  }
}

// ── Load waveform ──────────────────────────────────────────────────────────
const loadWaveform = async (track: 'ecg' | 'pcg', fileId: string) => {
  if (track === 'ecg') loadingEcgWave.value = true
  else loadingPcgWave.value = true

  // overview：全文件低分辨率固定 2000 点，用于缩略导航
  const r = await fetch(`/api/v1/files/${fileId}/waveform?max_points=2000`, { headers: (authH.value as Record<string, string>) })

  if (r.ok) {
    const data = await r.json()
    if (track === 'ecg') {
      ecgWave.value = data.samples || []
      ecgDuration.value = data.duration || 0
      const secs = Math.min(10, ecgDuration.value)
      ecgViewSecs.value = secs
      // Sync PCG view to match ECG
      pcgViewSecs.value = secs
      pcgViewStart.value = ecgViewStart.value
      loadingEcgWave.value = false
    } else {
      pcgWave.value = data.samples || []
      pcgDuration.value = data.duration || 0
      // Sync to ECG view if ECG already loaded, otherwise set own
      if (ecgWave.value.length > 0) {
        pcgViewSecs.value = ecgViewSecs.value
        pcgViewStart.value = ecgViewStart.value
      } else {
        pcgViewSecs.value = Math.min(10, pcgDuration.value)
      }
      loadingPcgWave.value = false
    }
    await nextTick()
    if (track === 'ecg') drawWaveform('ecg')
    else drawWaveform('pcg')
    // overview 加载完毕后立刻触发首次 detail fetch
    scheduleDetailFetch(track)
  } else {
    if (track === 'ecg') loadingEcgWave.value = false
    else loadingPcgWave.value = false
  }
}

// ── Draw waveform ──────────────────────────────────────────────────────────
const drawWaveform = (track: 'ecg' | 'pcg') => {
  const canvas = track === 'ecg' ? ecgCanvas.value : pcgCanvas.value
  const container = track === 'ecg' ? ecgContainer.value : pcgContainer.value
  const wave = track === 'ecg' ? ecgWave.value : pcgWave.value
  const duration = track === 'ecg' ? ecgDuration.value : pcgDuration.value
  const viewStart = track === 'ecg' ? ecgViewStart.value : pcgViewStart.value
  const viewSecs = track === 'ecg' ? ecgViewSecs.value : pcgViewSecs.value
  const color = track === 'ecg' ? '#4ade80' : '#c084fc'

  if (!canvas || !container || wave.length === 0) return
  const W = container.clientWidth || canvas.offsetWidth
  const H = container.clientHeight || canvas.offsetHeight
  canvas.width = W
  canvas.height = H
  const ctx = canvas.getContext('2d')
  if (!ctx) return

  ctx.clearRect(0, 0, W, H)
  ctx.fillStyle = '#0a0a0f'
  ctx.fillRect(0, 0, W, H)

  // grid lines
  ctx.strokeStyle = '#1e293b'
  ctx.lineWidth = 1
  for (let i = 1; i < 4; i++) {
    const y = (H / 4) * i
    ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke()
  }
  // time grid
  const secStep = viewSecs <= 2 ? 0.5 : viewSecs <= 5 ? 1 : viewSecs <= 20 ? 5 : 10
  const tStart = Math.ceil(viewStart / secStep) * secStep
  ctx.strokeStyle = '#1e293b'
  ctx.fillStyle = '#475569'
  ctx.font = '9px monospace'
  ctx.textAlign = 'center'
  for (let t = tStart; t < viewStart + viewSecs + secStep; t += secStep) {
    const x = ((t - viewStart) / viewSecs) * W
    if (x < 0 || x > W) continue
    ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, H); ctx.stroke()
    ctx.fillText(fmtTime(t), x, H - 3)
  }

  // waveform — 优先使用 detail 高分辨率数据，否则 fallback 到 overview
  const vEnd = viewStart + viewSecs
  const detailSamples = track === 'ecg' ? ecgDetailSamples.value : pcgDetailSamples.value
  const detailRange = track === 'ecg' ? ecgDetailRange.value : pcgDetailRange.value

  let seg: number[]
  if (
    detailRange &&
    detailSamples.length > 0 &&
    detailRange.start <= viewStart + 0.001 &&
    detailRange.end >= vEnd - 0.001
  ) {
    // 从 detail 数据里裁出当前视口对应片段
    const detailDur = detailRange.end - detailRange.start
    const di0 = Math.floor(((viewStart - detailRange.start) / detailDur) * detailSamples.length)
    const di1 = Math.min(detailSamples.length - 1, Math.ceil(((vEnd - detailRange.start) / detailDur) * detailSamples.length))
    seg = detailSamples.slice(Math.max(0, di0), di1 + 1)
  } else {
    // fallback：overview
    const ptsPerSec = wave.length / duration
    const i0 = Math.floor(viewStart * ptsPerSec)
    const i1 = Math.min(wave.length - 1, Math.ceil(vEnd * ptsPerSec))
    seg = wave.slice(i0, i1 + 1)
  }
  if (seg.length === 0) return

  const min = Math.min(...seg)
  const max = Math.max(...seg)
  const span = max - min || 1
  const pad = H * 0.1
  const mapY = (v: number) => pad + ((max - v) / span) * (H - 2 * pad)

  ctx.beginPath()
  ctx.strokeStyle = color
  ctx.lineWidth = 1.2
  ctx.lineJoin = 'round'
  for (let i = 0; i < seg.length; i++) {
    const x = (i / (seg.length - 1)) * W
    const y = mapY(seg[i])
    if (i === 0) ctx.moveTo(x, y)
    else ctx.lineTo(x, y)
  }
  ctx.stroke()
}

const drawAll = () => {
  drawWaveform('ecg')
  drawWaveform('pcg')
}

// ── Zoom / Pan ─────────────────────────────────────────────────────────────
// 以鼠标光标位置为中心缩放：保持鼠标指向的时间点不变
const zoomAroundCursor = (
  track: 'ecg' | 'pcg',
  delta: number,
  mouseX: number,
  containerWidth: number,
) => {
  const viewStart = track === 'ecg' ? ecgViewStart : pcgViewStart
  const viewSecs = track === 'ecg' ? ecgViewSecs : pcgViewSecs
  const duration = track === 'ecg' ? ecgDuration.value : pcgDuration.value

  // 鼠标在时间轴上的绝对位置
  const cursorFrac = containerWidth > 0 ? mouseX / containerWidth : 0.5
  const cursorTime = viewStart.value + cursorFrac * viewSecs.value

  // 新视口宽度
  const factor = delta > 0 ? 1.25 : 0.8  // 每档缩放 25%
  const newSecs = Math.max(0.5, Math.min(duration || 30, viewSecs.value * factor))
  viewSecs.value = newSecs

  // 重新计算 viewStart，使光标下的时间点保持不变
  viewStart.value = Math.max(0, Math.min(
    cursorTime - cursorFrac * newSecs,
    Math.max(0, duration - newSecs),
  ))
}

const zoomEcg = (delta: number, mouseX = 0, W = 1) => {
  zoomBoth(delta, mouseX, W)
}
const zoomPcg = (delta: number, mouseX = 0, W = 1) => {
  zoomBoth(delta, mouseX, W)
}

// Synchronized zoom: both tracks zoom together
const zoomBoth = (delta: number, mouseX: number, containerWidth: number) => {
  zoomAroundCursor('ecg', delta, mouseX, containerWidth)
  clampEcgView()
  // Mirror to PCG
  pcgViewStart.value = ecgViewStart.value
  pcgViewSecs.value = ecgViewSecs.value
  clampPcgView()
  drawAll()
  scheduleDetailFetch('ecg')
  scheduleDetailFetch('pcg')
}

const resetEcgView = () => { resetBothViews() }
const resetPcgView = () => { resetBothViews() }
const resetBothViews = () => {
  const secs = Math.min(10, Math.max(ecgDuration.value || 10, pcgDuration.value || 10))
  ecgViewStart.value = 0; ecgViewSecs.value = secs
  pcgViewStart.value = 0; pcgViewSecs.value = secs
  drawAll()
  scheduleDetailFetch('ecg')
  scheduleDetailFetch('pcg')
}

const clampEcgView = () => {
  ecgViewStart.value = Math.max(0, Math.min(ecgViewStart.value, Math.max(0, ecgDuration.value - ecgViewSecs.value)))
}
const clampPcgView = () => {
  pcgViewStart.value = Math.max(0, Math.min(pcgViewStart.value, Math.max(0, pcgDuration.value - pcgViewSecs.value)))
}

const onEcgWheel = (e: WheelEvent) => {
  const W = ecgContainer.value?.clientWidth || 1
  zoomBoth(e.deltaY > 0 ? 1 : -1, e.offsetX, W)
}
const onPcgWheel = (e: WheelEvent) => {
  const W = pcgContainer.value?.clientWidth || 1
  zoomBoth(e.deltaY > 0 ? 1 : -1, e.offsetX, W)
}

const onEcgMouseDown = (e: MouseEvent) => { ecgDragging.value = true; ecgDragStartX = e.clientX; ecgDragStartView = ecgViewStart.value }
const onEcgMouseMove = (e: MouseEvent) => {
  if (!ecgDragging.value || !ecgContainer.value) return
  const W = ecgContainer.value.clientWidth
  const dx = (e.clientX - ecgDragStartX) / W * ecgViewSecs.value
  ecgViewStart.value = Math.max(0, ecgDragStartView - dx)
  clampEcgView()
  // Sync PCG to ECG
  pcgViewStart.value = ecgViewStart.value
  clampPcgView()
  drawAll()
  scheduleDetailFetch('ecg')
  scheduleDetailFetch('pcg')
}
const onEcgMouseUp = () => {
  if (ecgDragging.value) {
    ecgDragging.value = false
    doDetailFetch('ecg')
    doDetailFetch('pcg')
  }
}
const onEcgMouseLeave = () => {
  if (ecgDragging.value) {
    ecgDragging.value = false
    doDetailFetch('ecg')
    doDetailFetch('pcg')
  }
}

const onPcgMouseDown = (e: MouseEvent) => { pcgDragging.value = true; pcgDragStartX = e.clientX; pcgDragStartView = pcgViewStart.value }
const onPcgMouseMove = (e: MouseEvent) => {
  if (!pcgDragging.value || !pcgContainer.value) return
  const W = pcgContainer.value.clientWidth
  const dx = (e.clientX - pcgDragStartX) / W * pcgViewSecs.value
  pcgViewStart.value = Math.max(0, pcgDragStartView - dx)
  clampPcgView()
  // Sync ECG to PCG
  ecgViewStart.value = pcgViewStart.value
  clampEcgView()
  drawAll()
  scheduleDetailFetch('ecg')
  scheduleDetailFetch('pcg')
}
const onPcgMouseUp = () => {
  if (pcgDragging.value) {
    pcgDragging.value = false
    doDetailFetch('ecg')
    doDetailFetch('pcg')
  }
}
const onPcgMouseLeave = () => {
  if (pcgDragging.value) {
    pcgDragging.value = false
    doDetailFetch('ecg')
    doDetailFetch('pcg')
  }
}

// ── Playhead ───────────────────────────────────────────────────────────────
const getPlayheadPct = (track: 'ecg' | 'pcg') => {
  const viewStart = track === 'ecg' ? ecgViewStart.value : pcgViewStart.value
  const viewSecs = track === 'ecg' ? ecgViewSecs.value : pcgViewSecs.value
  const pos = track === 'pcg' ? playPos.value - localPcgOffset.value : playPos.value
  return ((pos - viewStart) / viewSecs) * 100
}

// Auto-scroll waveform to follow playhead (synchronized)
const followPlayhead = () => {
  let moved = false
  if (ecgWave.value.length > 0 || pcgWave.value.length > 0) {
    const mid = ecgViewStart.value + ecgViewSecs.value / 2
    if (playPos.value > mid + ecgViewSecs.value * 0.3 || playPos.value < ecgViewStart.value) {
      ecgViewStart.value = Math.max(0, playPos.value - ecgViewSecs.value / 4)
      clampEcgView()
      // Mirror to PCG
      pcgViewStart.value = ecgViewStart.value
      clampPcgView()
      moved = true
    }
  }
  // detail fetch checks
  if (moved) {
    checkPlaybackDetailCoverage('ecg')
    checkPlaybackDetailCoverage('pcg')
  } else {
    if (ecgWave.value.length > 0) checkPlaybackDetailCoverage('ecg')
    if (pcgWave.value.length > 0) checkPlaybackDetailCoverage('pcg')
  }
}

// ── Master timer ───────────────────────────────────────────────────────────
let lastRafTime = 0
let seekRequestToken = 0
const rafLoop = (t: number) => {
  if (isPlaying.value) {
    if (lastRafTime > 0) {
      const dt = (t - lastRafTime) / 1000
      playPos.value = Math.min(totalDuration.value, playPos.value + dt)

      // Drift correction: sync playPos from audio currentTime to prevent desync
      // Skip while seeking — audio.currentTime is stale until seeked event fires
      if (!seekingAudio && pcgAudio.value && !pcgAudio.value.paused && pcgAudio.value.duration > 0) {
        const audioMasterPos = pcgAudio.value.currentTime + localPcgOffset.value
        if (Math.abs(audioMasterPos - playPos.value) > 0.15) {
          playPos.value = Math.min(totalDuration.value, audioMasterPos)
        }
      }

      if (playPos.value >= totalDuration.value) {
        isPlaying.value = false
        if (pcgAudio.value) pcgAudio.value.pause()
        if (videoDisplay.value) videoDisplay.value.pause()
        playPos.value = 0
        void syncAllToPos(0)
        lastRafTime = 0
        drawAll()
        return
      }
    }
    lastRafTime = t
    followPlayhead()
    drawAll()
    rafId = requestAnimationFrame(rafLoop)
  }
}

const waitForMediaSeek = async (media: HTMLMediaElement, rawTime: number) => {
  if (!media.src) return

  const duration = Number.isFinite(media.duration) ? media.duration : 0
  const targetTime = Math.max(
    0,
    Math.min(rawTime, duration > 0 ? Math.max(0, duration - 0.001) : rawTime),
  )

  if (Math.abs(media.currentTime - targetTime) < 0.01 && !media.seeking) return

  await new Promise<void>((resolve) => {
    let settled = false
    let timeoutId = 0

    const cleanup = () => {
      media.removeEventListener('seeked', finish)
      media.removeEventListener('canplay', finish)
      media.removeEventListener('loadedmetadata', onLoadedMeta)
      if (timeoutId) window.clearTimeout(timeoutId)
    }

    const finish = () => {
      if (settled) return
      settled = true
      cleanup()
      resolve()
    }

    const applySeek = () => {
      media.addEventListener('seeked', finish)
      media.addEventListener('canplay', finish)
      try {
        media.currentTime = targetTime
      } catch {
        finish()
        return
      }

      if (Math.abs(media.currentTime - targetTime) < 0.01 && !media.seeking) {
        finish()
      }
    }

    const onLoadedMeta = () => {
      applySeek()
    }

    timeoutId = window.setTimeout(finish, 500)

    if (media.readyState >= HTMLMediaElement.HAVE_METADATA) {
      applySeek()
    } else {
      media.addEventListener('loadedmetadata', onLoadedMeta)
    }
  })
}

const togglePlay = () => {
  if (isPlaying.value) {
    pause()
  } else {
    void play()
  }
}

const play = async () => {
  if (totalDuration.value === 0 || isPlaying.value) return
  isPlaying.value = true
  lastRafTime = 0

  // ── 重要：先在用户手势上下文中同步触发 play()，再做异步 seek ──
  // 浏览器的 Autoplay Policy 要求 play() 必须在用户点击的**同步调用链**中执行。
  // 如果先 await syncAllToPos 再 play，异步操作会打断用户手势上下文，
  // 导致 play() 被浏览器静默阻止（Promise 被 reject）→ 没有声音。
  //
  // 策略：先 play()（从当前位置起播），然后异步 seek 到正确位置，
  // seek 完成后音频会自动从正确位置继续播放。

  const playTasks: Promise<unknown>[] = []
  if (pcgAudio.value) {
    playTasks.push(pcgAudio.value.play().catch((err) => {
      console.warn('[SyncViewer] PCG audio play failed:', err)
    }))
  }
  if (videoDisplay.value) {
    playTasks.push(videoDisplay.value.play().catch((err) => {
      console.warn('[SyncViewer] Video play failed:', err)
    }))
  }
  await Promise.all(playTasks)

  if (!isPlaying.value) return

  // 现在媒体已在播放中，异步 seek 到主时间轴位置
  await syncAllToPos(playPos.value)
  if (!isPlaying.value) return

  rafId = requestAnimationFrame(rafLoop)
}

const pause = () => {
  isPlaying.value = false
  if (rafId) cancelAnimationFrame(rafId)
  if (pcgAudio.value) pcgAudio.value.pause()
  if (videoDisplay.value) videoDisplay.value.pause()
  drawAll()
}

const syncAllToPos = async (pos: number) => {
  const token = ++seekRequestToken
  seekingAudio = true

  const tasks: Promise<void>[] = []
  if (pcgAudio.value && pcgAudio.value.src) {
    tasks.push(waitForMediaSeek(pcgAudio.value, Math.max(0, pos - localPcgOffset.value)))
  }
  if (videoDisplay.value && videoDisplay.value.src) {
    tasks.push(waitForMediaSeek(videoDisplay.value, Math.max(0, pos - localVideoOffset.value)))
  }

  if (tasks.length === 0) {
    seekingAudio = false
    return
  }

  try {
    await Promise.all(tasks)
  } finally {
    if (seekRequestToken === token) {
      seekingAudio = false
    }
  }
}

const seekMaster = (e: MouseEvent) => {
  const el = masterBarRef.value
  if (!el) return
  const rect = el.getBoundingClientRect()
  const pct = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width))
  playPos.value = pct * totalDuration.value
  void syncAllToPos(playPos.value)
  followPlayhead()
  drawAll()
}

// Master bar 拖拽 seek
const onMasterMouseDown = (e: MouseEvent) => {
  masterDragging = true
  // 立刻 seek 到点击位置
  const el = masterBarRef.value
  if (!el) return
  const rect = el.getBoundingClientRect()
  const pct = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width))
  playPos.value = pct * totalDuration.value
  void syncAllToPos(playPos.value)
  followPlayhead()
  drawAll()

  const onMove = (ev: MouseEvent) => {
    if (!masterDragging || !masterBarRef.value) return
    const r = masterBarRef.value.getBoundingClientRect()
    const p = Math.max(0, Math.min(1, (ev.clientX - r.left) / r.width))
    playPos.value = p * totalDuration.value
    void syncAllToPos(playPos.value)
    followPlayhead()
    drawAll()
  }
  const onUp = () => {
    window.removeEventListener('mousemove', onMove)
    window.removeEventListener('mouseup', onUp)
    // 短暂延迟后清除 dragging 标记
    setTimeout(() => { masterDragging = false }, 50)
  }
  window.addEventListener('mousemove', onMove)
  window.addEventListener('mouseup', onUp)
  e.preventDefault()
}

const onPcgTimeUpdate = () => { /* PCG drives its own timeline; master RAF drives display */ }
const onVideoTimeUpdate = () => {}
const onEnded = () => {
  // Seeking can spuriously fire 'ended' — ignore if we didn't intend to stop
  if (seekingAudio) return
  // Only stop the master playback when ALL active media have ended,
  // not when a single track (shorter one) finishes
  if (isPlaying.value && playPos.value < totalDuration.value - 0.5) return
  isPlaying.value = false
  if (rafId) cancelAnimationFrame(rafId)
  if (pcgAudio.value) pcgAudio.value.pause()
  if (videoDisplay.value) videoDisplay.value.pause()
  playPos.value = 0
  void syncAllToPos(0)
  lastRafTime = 0
  drawAll()
}

const onPcgMeta = () => {
  if (pcgAudio.value) pcgDuration.value = pcgAudio.value.duration || pcgDuration.value
}
const onVideoMeta = () => {
  if (videoEl.value) videoDuration.value = videoEl.value.duration || 0
}
const onVideoDisplayMeta = () => {
  if (videoDisplay.value) videoDuration.value = videoDisplay.value.duration || videoDuration.value
}

const setVolume = (e: Event) => {
  volume.value = parseFloat((e.target as HTMLInputElement).value)
  if (pcgAudio.value) pcgAudio.value.volume = volume.value
}

// ── Offset change ──────────────────────────────────────────────────────────
const onOffsetChange = () => {
  offsetsDirty.value = true
  if (isPlaying.value && pcgAudio.value) {
    pcgAudio.value.currentTime = Math.max(0, playPos.value - localPcgOffset.value)
  }
}
const onVideoOffsetChange = () => {
  offsetsDirty.value = true
  if (isPlaying.value && videoDisplay.value) {
    videoDisplay.value.currentTime = Math.max(0, playPos.value - localVideoOffset.value)
  }
}

const discardOffsets = () => {
  localPcgOffset.value = assoc.value?.pcg_offset ?? 0
  localVideoOffset.value = assoc.value?.video_offset ?? 0
  offsetsDirty.value = false
}

const saveOffsets = async () => {
  savingOffsets.value = true
  const r = await fetch(`/api/v1/associations/${assocId}`, {
    method: 'PATCH',
    headers: { ...(authH.value as Record<string, string>), 'Content-Type': 'application/json' },
    body: JSON.stringify({
      pcg_offset: localPcgOffset.value,
      video_offset: localVideoOffset.value,
    }),
  })
  savingOffsets.value = false
  if (r.ok) {
    toast.success('偏移已保存')
    offsetsDirty.value = false
    assoc.value = await r.json()
  } else {
    toast.error('保存失败')
  }
}

// ── Lifecycle ──────────────────────────────────────────────────────────────
// ── Keyboard shortcuts ─────────────────────────────────────────────────────
const onKeyDown = (e: KeyboardEvent) => {
  if (e.code === 'Space' && !['INPUT', 'TEXTAREA', 'SELECT'].includes((e.target as HTMLElement)?.tagName)) {
    e.preventDefault()
    togglePlay()
  }
}

onMounted(async () => {
  await load()
  await nextTick()
  drawAll()
  window.addEventListener('resize', drawAll)
  window.addEventListener('keydown', onKeyDown)
})

onUnmounted(() => {
  if (rafId) cancelAnimationFrame(rafId)
  window.removeEventListener('resize', drawAll)
  window.removeEventListener('keydown', onKeyDown)
  if (pcgAudio.value) pcgAudio.value.pause()
  if (videoDisplay.value) videoDisplay.value.pause()
})
</script>

import { computed, reactive, ref } from 'vue'

import type { AuscultationArea } from '@/composables/useAuscultation'
import type { SmoothingLevel } from '@/composables/useScrollingCanvas'
/**
 * 虚拟人体 Pinia Store
 *
 * 管理 WebSocket 连接、实时 vitals、信号回调分发、档案管理。
 */
import { defineStore } from 'pinia'
import { decodeSignalFrame } from '@/lib/wsBinaryProtocol'
import { useAuthStore } from './auth'
import { useConnectionStore } from './connection'
import { useToastStore } from './toast'

/** P1-5: Valve event from physiology_detail */
export interface ValveEventData {
  valve: string
  action: string
  at_ms: number
  dp_dt: number
  area_ratio: number
}

/** 活动效果描述（从 vitals 派生） */
export interface ActiveEffect {
  category: 'exercise' | 'emotion' | 'condition' | 'medication' | 'body' | 'electrolyte'
  label: string
  icon: string
  color: string     // tailwind color key
  value?: number    // 百分比或数值
}

/** 虚拟人档案列表项 */
export interface ProfileItem {
  id: string
  name: string
  is_active: boolean
  heart_rate: number | null
  rhythm: string | null
  created_at: string
  updated_at: string
}

export interface SignalChunk {
  samples: number[]
  startSample: number
  seq: number
  receivedAtMs: number
  chunkDurationMs: number
  serverElapsedSec: number | null
}

type SignalCallback = (chunk: SignalChunk) => void

function nowMs() {
  return typeof performance !== 'undefined' && typeof performance.now === 'function'
    ? performance.now()
    : Date.now()
}

export const useVirtualHumanStore = defineStore('virtualHuman', () => {
  const auth = useAuthStore()
  const toast = useToastStore()

  const connected = ref(false)
  const connecting = ref(false)
  const latency = ref(0)
  const error = ref('')

  const profiles = ref<ProfileItem[]>([])
  const selectedProfileId = ref<string | null>(null)
  const profileName = ref<string | null>(null)
  const loadingProfiles = ref(false)

  const vitals = reactive({
    heart_rate: 72,
    systolic_bp: 120,
    diastolic_bp: 80,
    spo2: 98,
    temperature: 36.6,
    respiratory_rate: 16,
    rhythm: 'normal',
    murmur_type: null as string | null,
    damage_level: 0,
    exercise_intensity: 0,
    emotional_arousal: 0,
    murmur_severity: 0,
    fatigue_accumulated: 0,
    caffeine_level: 0,
    alcohol_level: 0,
    dehydration_level: 0,
    sleep_debt: 0,
    sympathetic_tone: 0.5,
    parasympathetic_tone: 0.5,
    ectopic_irritability: 0,
    pvc_pattern: 'isolated',
    // Phase 4 药物与电解质
    beta_blocker_level: 0,
    amiodarone_level: 0,
    digoxin_level: 0,
    atropine_level: 0,
    potassium_level: 4.0,
    calcium_level: 9.5,
    // Phase 1B 血流动力学
    cardiac_output: 5.0,        // L/min
    ejection_fraction: 60.0,    // %
    stroke_volume: 70.0,        // mL
    // 心脏电生理传导信息
    conduction: {
      sa_rate: 72,
      av_delay_ms: 120,
      av_refractory_ms: 430,
      his_delay_ms: 20,
      purkinje_delay_ms: 30,
      sa_state: 'resting',
      av_state: 'resting',
      his_state: 'resting',
      purkinje_state: 'resting',
      av_block_degree: 0,
      svt_active: false,
      svt_reentry_count: 0,
      last_beat_type: 'none',
      pr_interval_ms: 160,
      qrs_duration_ms: 90,
      p_wave_present: true,
      p_wave_retrograde: false,
      av_block_occurred: false,
      conducted: true,
    },
    // Phase 5 心律失常基质 + 发作
    af_substrate: 0,
    svt_substrate: 0,
    vt_substrate: 0,
    arrhythmia_episode_type: '',
    arrhythmia_episode_beats: 0,
    // Phase 6 除颤
    defibrillation_count: 0,
    // P2-5 gallop indicators
    gallop_s3: false,
    gallop_s4: false,
    // fitness & demographics
    fitness_level: 0.5,
    age: 30,
    // HR override (心率锁定)
    hr_override_active: false,
    hr_override_value: 0,
    // Phase 3: 新生理字段
    pao2: 95.0,                          // mmHg
    paco2: 40.0,                         // mmHg
    ph: 7.40,
    fio2: 0.21,
    magnesium_level: 2.0,                // mg/dL
    intrathoracic_pressure: -5.0,        // mmHg
    coronary_perfusion_pressure: 70.0,   // mmHg
    ischemia_level: 0,
    qt_adapted_ms: 0,
    hrv_rr_offset_ms: 0,
    rv_ejection_fraction: 55.0,          // %
    pa_systolic: 25.0,                   // mmHg
    pa_diastolic: 10.0,                  // mmHg
    pa_mean: 15.0,                       // mmHg
    rv_stroke_volume: 70.0,              // mL
    coronary_stenosis: 0,
    raas_activation: 0,
  })

  const interactions = ref<string[]>([])
  const categories = ref<Record<string, string[]>>({})
  const ecgSr = ref(500)
  const pcgSr = ref(4000)
  const chunkIntervalMs = ref(100)
  const ecgChunkSize = ref(50)
  const pcgChunkSize = ref(400)
  const streamProtocol = ref('legacy')
  const lastSignalSeq = ref(-1)

  /** 后端服务启动时间（ISO 字符串） */
  const serverStartedAt = ref<string | null>(null)

  const beatAnnotations = ref<any[]>([])
  const conductionTrend = ref<any[]>([])
  const showAnnotations = ref(false)
  const showTrendChart = ref(false)

  const auscultationMode = ref(false)
  const auscultationArea = ref<AuscultationArea>('mitral')
  const noiseReduction = ref(true)

  /** 控制面板当前 Tab（提升到 store，Tab 切换不丢失） */
  const controlPanelTab = ref<string>('exercise')

  /** Feature 2: ECG 信号平滑级别 */
  const ecgSmoothingLevel = ref<SmoothingLevel>('off')

  /** Alarm mute toggle */
  const alarmMuted = ref(true)

  /** Feature 4: Caliper measurement mode */
  const caliperMode = ref(false)

  /** P1: Physiology visualization data (updated per-beat) */
  const physiologyDetail = ref<{
    pv_loop?: { lv_pressure: number[]; lv_volume: number[] }
    action_potentials?: Record<string, number[]>
    cardiac_cycle?: {
      lv_pressure: number[]
      aortic_pressure: number[]
      lv_volume: number[]
      time_ms: number[]
    }
    valve_events?: ValveEventData[]
  } | null>(null)

  /** P1-5: Latest valve events (extracted from physiology_detail per beat) */
  const valveEvents = ref<ValveEventData[]>([])

  /** Feature 3: 12 导联 ECG */
  const ALL_12_LEADS = ['I','II','III','aVR','aVL','aVF','V1','V2','V3','V4','V5','V6'] as const
  const selectedLeads = ref<string[]>(['II'])
  const availableLeads = ref<string[]>([...ALL_12_LEADS])
  const multiLeadMode = computed(() => selectedLeads.value.length > 1)

  /** 每导联回调注册 */
  const leadCallbacks: Map<string, SignalCallback[]> = new Map()

  function registerLeadCallback(lead: string, fn: SignalCallback) {
    if (!leadCallbacks.has(lead)) leadCallbacks.set(lead, [])
    leadCallbacks.get(lead)!.push(fn)
  }

  function unregisterLeadCallback(lead: string, fn: SignalCallback) {
    const cbs = leadCallbacks.get(lead)
    if (!cbs) return
    const idx = cbs.indexOf(fn)
    if (idx !== -1) cbs.splice(idx, 1)
  }

  function setLeads(leads: string[]) {
    selectedLeads.value = leads
    sendCommand('set_leads', { leads })
  }

  const ecgCallbacks: SignalCallback[] = []
  const pcgCallbacks: SignalCallback[] = []

  /** P1-PCG: Per-position PCG callbacks */
  const pcgPositionCallbacks: Map<string, SignalCallback[]> = new Map()

  function registerPcgPositionCallback(position: string, fn: SignalCallback) {
    if (!pcgPositionCallbacks.has(position)) pcgPositionCallbacks.set(position, [])
    pcgPositionCallbacks.get(position)!.push(fn)
  }

  function unregisterPcgPositionCallback(position: string, fn: SignalCallback) {
    const cbs = pcgPositionCallbacks.get(position)
    if (!cbs) return
    const idx = cbs.indexOf(fn)
    if (idx !== -1) cbs.splice(idx, 1)
  }

  let ws: WebSocket | null = null
  let pingTimer: ReturnType<typeof setInterval> | null = null

  async function fetchProfiles() {
    if (!auth.token) return
    loadingProfiles.value = true
    try {
      const res = await fetch('/api/v1/virtual-human/profiles', {
        headers: { Authorization: `Bearer ${auth.token}` },
      })
      if (res.ok) {
        profiles.value = await res.json()
      }
    } catch {
      // silent
    } finally {
      loadingProfiles.value = false
    }
  }

  async function createProfile(name: string): Promise<string | null> {
    if (!auth.token) return null
    try {
      const res = await fetch('/api/v1/virtual-human/profiles', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${auth.token}`,
        },
        body: JSON.stringify({ name }),
      })
      if (res.ok) {
        const data = await res.json()
        await fetchProfiles()
        toast.success(`档案 "${name}" 已创建`)
        return data.id
      }
    } catch {
      toast.error('创建档案失败')
    }
    return null
  }

  async function deleteProfile(id: string) {
    if (!auth.token) return
    try {
      const res = await fetch(`/api/v1/virtual-human/profiles/${id}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${auth.token}` },
      })
      if (res.ok) {
        await fetchProfiles()
        toast.success('档案已删除')
      }
    } catch {
      toast.error('删除档案失败')
    }
  }

  function connect(profileId?: string | null) {
    if (ws || connecting.value) return
    connecting.value = true
    error.value = ''
    selectedProfileId.value = profileId || null
    lastSignalSeq.value = -1

    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = location.host
    const params = new URLSearchParams()
    params.set('protocol', 'binary')
    if (auth.token) params.set('token', auth.token)
    if (profileId) params.set('profile_id', profileId)
    const qs = params.toString()
    const url = `${protocol}//${host}/api/v1/ws/virtual-human${qs ? '?' + qs : ''}`

    ws = new WebSocket(url)
    ws.binaryType = 'arraybuffer'

    ws.onopen = () => {
      connected.value = true
      connecting.value = false
      pingTimer = setInterval(() => {
        if (ws?.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: 'ping' }))
        }
      }, 25000)
    }

    ws.onmessage = (event: MessageEvent) => {
      if (event.data instanceof ArrayBuffer) {
        handleBinaryMessage(event.data)
      } else {
        try {
          const msg = JSON.parse(event.data as string)
          handleMessage(msg)
        } catch (e) {
          console.error('Failed to parse WS message:', e)
        }
      }
    }

    ws.onerror = () => {
      error.value = '连接失败'
      connecting.value = false
    }

    ws.onclose = () => {
      connected.value = false
      connecting.value = false
      ws = null
      if (pingTimer) {
        clearInterval(pingTimer)
        pingTimer = null
      }
    }
  }

  function disconnect() {
    if (ws) {
      ws.close()
      ws = null
    }
    connected.value = false
    selectedProfileId.value = null
    profileName.value = null
    lastSignalSeq.value = -1
    if (pingTimer) {
      clearInterval(pingTimer)
      pingTimer = null
    }
  }

  function sendCommand(command: string, params?: Record<string, any>) {
    if (ws?.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'command', command, params }))
    }
  }

  function saveState() {
    if (ws?.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'save' }))
    }
  }

  function handleMessage(msg: any) {
    switch (msg.type) {
      case 'init':
        interactions.value = msg.interactions || []
        categories.value = msg.categories || {}
        ecgSr.value = msg.ecg_sr || 500
        pcgSr.value = msg.pcg_sr || 4000
        chunkIntervalMs.value = msg.chunk_interval_ms || 100
        ecgChunkSize.value = msg.ecg_chunk_size || 50
        pcgChunkSize.value = msg.pcg_chunk_size || 400
        streamProtocol.value = msg.stream_protocol || 'legacy'
        if (msg.vitals) {
          const { conduction: cond, ...rest } = msg.vitals
          Object.assign(vitals, rest)
          if (cond) Object.assign(vitals.conduction, cond)
        }
        if (msg.profile) {
          profileName.value = msg.profile.name
        }
        // Feature 3: 12-lead init
        if (msg.available_leads) {
          availableLeads.value = msg.available_leads
        }
        if (msg.selected_leads) {
          selectedLeads.value = msg.selected_leads
        }
        if (msg.server_started_at) {
          serverStartedAt.value = msg.server_started_at
        }
        break

      case 'signal': {
        if (msg.vitals) {
          const { conduction: cond, ...rest } = msg.vitals
          Object.assign(vitals, rest)
          if (cond) Object.assign(vitals.conduction, cond)
        }
        const receivedAtMs = nowMs()
        const seq = Number.isFinite(msg.seq) ? Number(msg.seq) : lastSignalSeq.value + 1
        const chunkMs = Number.isFinite(msg.chunk_duration_ms)
          ? Number(msg.chunk_duration_ms)
          : chunkIntervalMs.value
        const serverElapsedSec = Number.isFinite(msg.server_elapsed_sec)
          ? Number(msg.server_elapsed_sec)
          : null

        lastSignalSeq.value = seq
        latency.value = 0

        // Update simulation time display
        if (serverElapsedSec !== null) {
          useConnectionStore().updateSimTime(serverElapsedSec)
        }

        if (msg.beat_annotations) {
          beatAnnotations.value = msg.beat_annotations
        }
        if (msg.conduction_trend) {
          conductionTrend.value = msg.conduction_trend
        }

        if (Array.isArray(msg.ecg)) {
          const startSample = Number.isFinite(msg.ecg_start_sample)
            ? Number(msg.ecg_start_sample)
            : seq * ecgChunkSize.value
          const chunk: SignalChunk = {
            samples: msg.ecg,
            startSample,
            seq,
            receivedAtMs,
            chunkDurationMs: chunkMs,
            serverElapsedSec,
          }
          ecgCallbacks.forEach((fn) => fn(chunk))
          // Also dispatch to Lead II callbacks (ecg is always Lead II)
          const leadIICbs = leadCallbacks.get('II')
          if (leadIICbs) leadIICbs.forEach((fn) => fn(chunk))
        }

        // Feature 3: Multi-lead ECG data
        if (msg.ecg_leads && typeof msg.ecg_leads === 'object') {
          const ecgStartSample = Number.isFinite(msg.ecg_start_sample)
            ? Number(msg.ecg_start_sample)
            : seq * ecgChunkSize.value
          for (const [leadName, leadSamples] of Object.entries(msg.ecg_leads)) {
            if (!Array.isArray(leadSamples) || leadName === 'II') continue // II already handled above
            const leadChunk: SignalChunk = {
              samples: leadSamples as number[],
              startSample: ecgStartSample,
              seq,
              receivedAtMs,
              chunkDurationMs: chunkMs,
              serverElapsedSec,
            }
            const cbs = leadCallbacks.get(leadName)
            if (cbs) cbs.forEach((fn) => fn(leadChunk))
          }
        }

        if (Array.isArray(msg.pcg)) {
          const startSample = Number.isFinite(msg.pcg_start_sample)
            ? Number(msg.pcg_start_sample)
            : seq * pcgChunkSize.value
          const chunk: SignalChunk = {
            samples: msg.pcg,
            startSample,
            seq,
            receivedAtMs,
            chunkDurationMs: chunkMs,
            serverElapsedSec,
          }
          pcgCallbacks.forEach((fn) => fn(chunk))
        }

        // P1: Physiology detail (per-beat visualization data)
        if (msg.physiology_detail) {
          physiologyDetail.value = msg.physiology_detail
          // P1-5: Extract valve events
          if (Array.isArray(msg.physiology_detail.valve_events)) {
            valveEvents.value = msg.physiology_detail.valve_events
          }
        }

        // P1-PCG: Multi-position channel dispatch
        if (msg.pcg_channels && typeof msg.pcg_channels === 'object') {
          const pcgStartSample = Number.isFinite(msg.pcg_start_sample)
            ? Number(msg.pcg_start_sample)
            : seq * pcgChunkSize.value
          for (const [pos, samples] of Object.entries(msg.pcg_channels)) {
            if (!Array.isArray(samples)) continue
            const posChunk: SignalChunk = {
              samples: samples as number[],
              startSample: pcgStartSample,
              seq,
              receivedAtMs,
              chunkDurationMs: chunkMs,
              serverElapsedSec,
            }
            const cbs = pcgPositionCallbacks.get(pos)
            if (cbs) cbs.forEach((fn) => fn(posChunk))
          }
        }
        break
      }

      case 'save_result':
        if (msg.success) {
          toast.success('状态已保存')
        } else {
          toast.error('保存失败')
        }
        break

      case 'pong':
        break

      case 'error':
        error.value = msg.message || '未知错误'
        break
    }
  }

  function handleBinaryMessage(buffer: ArrayBuffer) {
    const frame = decodeSignalFrame(buffer)
    const receivedAtMs = nowMs()

    // 1. Incremental vitals update (only changed fields)
    if (frame.vitalsDelta && Object.keys(frame.vitalsDelta).length > 0) {
      const delta = frame.vitalsDelta as Record<string, any>
      const { conduction: cond, ...rest } = delta
      Object.assign(vitals, rest)
      if (cond) Object.assign(vitals.conduction, cond)
    }

    const seq = frame.seq
    lastSignalSeq.value = seq

    // Update simulation time display
    if (Number.isFinite(frame.serverElapsedSec)) {
      useConnectionStore().updateSimTime(frame.serverElapsedSec)
    }

    // 2. Beat annotations
    if (frame.beatAnnotations && frame.beatAnnotations.length > 0) {
      beatAnnotations.value = frame.beatAnnotations
    }

    // 3. Conduction trend
    if (frame.conductionTrend) {
      conductionTrend.value = frame.conductionTrend
    }

    // 4. Dispatch ECG callbacks
    const ecgSamples = Array.from(frame.ecg)
    const ecgChunk: SignalChunk = {
      samples: ecgSamples,
      startSample: frame.ecgStartSample,
      seq,
      receivedAtMs,
      chunkDurationMs: chunkIntervalMs.value,
      serverElapsedSec: frame.serverElapsedSec,
    }
    ecgCallbacks.forEach((fn) => fn(ecgChunk))
    const leadIICbs = leadCallbacks.get('II')
    if (leadIICbs) leadIICbs.forEach((fn) => fn(ecgChunk))

    // 5. Dispatch multi-lead ECG
    if (frame.ecgLeads) {
      for (const [leadName, leadData] of Object.entries(frame.ecgLeads)) {
        if (leadName === 'II') continue
        const leadChunk: SignalChunk = {
          samples: Array.from(leadData),
          startSample: frame.ecgStartSample,
          seq,
          receivedAtMs,
          chunkDurationMs: chunkIntervalMs.value,
          serverElapsedSec: frame.serverElapsedSec,
        }
        const cbs = leadCallbacks.get(leadName)
        if (cbs) cbs.forEach((fn) => fn(leadChunk))
      }
    }

    // 6. Dispatch PCG callbacks
    const pcgSamples = Array.from(frame.pcg)
    const pcgChunk: SignalChunk = {
      samples: pcgSamples,
      startSample: frame.pcgStartSample,
      seq,
      receivedAtMs,
      chunkDurationMs: chunkIntervalMs.value,
      serverElapsedSec: frame.serverElapsedSec,
    }
    pcgCallbacks.forEach((fn) => fn(pcgChunk))

    // 7. Dispatch per-position PCG callbacks (binary protocol fallback)
    // Binary protocol doesn't carry separate pcg_channels, so we fan out
    // the primary PCG data to all registered position callbacks.  This
    // ensures auscultation mode still receives data when using binary.
    if (pcgPositionCallbacks.size > 0) {
      for (const [, cbs] of pcgPositionCallbacks) {
        if (cbs && cbs.length > 0) {
          cbs.forEach((fn) => fn(pcgChunk))
        }
      }
    }
  }

  function toggleAnnotations() {
    showAnnotations.value = !showAnnotations.value
  }

  function toggleTrendChart() {
    showTrendChart.value = !showTrendChart.value
  }

  function registerEcgCallback(fn: SignalCallback) {
    ecgCallbacks.push(fn)
  }

  function registerPcgCallback(fn: SignalCallback) {
    pcgCallbacks.push(fn)
  }

  function unregisterEcgCallback(fn: SignalCallback) {
    const idx = ecgCallbacks.indexOf(fn)
    if (idx !== -1) ecgCallbacks.splice(idx, 1)
  }

  function unregisterPcgCallback(fn: SignalCallback) {
    const idx = pcgCallbacks.indexOf(fn)
    if (idx !== -1) pcgCallbacks.splice(idx, 1)
  }

  // ── 派生活动状态（从 vitals 真实值推导） ──────────────────

  const derivedActiveStates = computed<ActiveEffect[]>(() => {
    const effects: ActiveEffect[] = []

    // 运动
    if (vitals.exercise_intensity > 0.1) {
      let label = '步行'
      let icon = '🚶'
      if (vitals.exercise_intensity > 0.7) { label = '跑步'; icon = '💨' }
      else if (vitals.exercise_intensity > 0.4) { label = '慢跑'; icon = '🏃' }
      else if (vitals.exercise_intensity > 0.2) { label = '步行'; icon = '🚶' }
      effects.push({
        category: 'exercise', label, icon, color: 'blue',
        value: Math.round(vitals.exercise_intensity * 100),
      })
    }

    // 情绪
    if (vitals.emotional_arousal > 0.15) {
      effects.push({
        category: 'emotion', label: '情绪激活', icon: '😰', color: 'amber',
        value: Math.round(vitals.emotional_arousal * 100),
      })
    }

    // 心脏病变 — 节律
    const rhythmMap: Record<string, { label: string; icon: string }> = {
      af: { label: '房颤', icon: '💔' },
      pvc: { label: '早搏', icon: '⚡' },
      svt: { label: 'SVT', icon: '⚡' },
      vt: { label: 'VT', icon: '💔' },
    }
    if (vitals.rhythm !== 'normal' && rhythmMap[vitals.rhythm]) {
      const r = rhythmMap[vitals.rhythm]
      effects.push({ category: 'condition', label: r.label, icon: r.icon, color: 'red' })
    }

    // AVB
    if (vitals.conduction.av_block_degree > 0) {
      effects.push({
        category: 'condition',
        label: `AVB ${vitals.conduction.av_block_degree}°`,
        icon: '🚫',
        color: 'red',
      })
    }

    // 杂音
    if (vitals.murmur_severity > 0) {
      effects.push({
        category: 'condition',
        label: `杂音 ${(vitals.murmur_severity * 100).toFixed(0)}%`,
        icon: '🫀',
        color: 'red',
      })
    }

    // 药物
    const meds: Array<{ key: keyof typeof vitals; label: string }> = [
      { key: 'beta_blocker_level', label: 'β-阻滞剂' },
      { key: 'amiodarone_level', label: '胺碘酮' },
      { key: 'digoxin_level', label: '地高辛' },
      { key: 'atropine_level', label: '阿托品' },
    ]
    for (const m of meds) {
      const level = vitals[m.key] as number
      if (level > 0.05) {
        effects.push({
          category: 'medication', label: m.label, icon: '💊', color: 'purple',
          value: Math.round(level * 100),
        })
      }
    }

    // 体内状态
    if (vitals.caffeine_level > 0.05) {
      effects.push({
        category: 'body', label: '咖啡因', icon: '☕', color: 'teal',
        value: Math.round(vitals.caffeine_level * 100),
      })
    }
    if (vitals.alcohol_level > 0.05) {
      effects.push({
        category: 'body', label: '酒精', icon: '🍺', color: 'teal',
        value: Math.round(vitals.alcohol_level * 100),
      })
    }
    if (vitals.dehydration_level > 0.05) {
      effects.push({
        category: 'body', label: '脱水', icon: '💧', color: 'teal',
        value: Math.round(vitals.dehydration_level * 100),
      })
    }
    if (vitals.sleep_debt > 0.1) {
      effects.push({
        category: 'body', label: '缺觉', icon: '💤', color: 'teal',
        value: Math.round(vitals.sleep_debt * 100),
      })
    }
    if (vitals.temperature > 37.5) {
      effects.push({
        category: 'body', label: '发热', icon: '🤒', color: 'teal',
        value: vitals.temperature,
      })
    }

    // 电解质
    if (vitals.potassium_level > 5.0) {
      effects.push({
        category: 'electrolyte', label: `K⁺↑`, icon: 'K⁺', color: 'emerald',
        value: vitals.potassium_level,
      })
    } else if (vitals.potassium_level < 3.5) {
      effects.push({
        category: 'electrolyte', label: `K⁺↓`, icon: 'K⁺', color: 'emerald',
        value: vitals.potassium_level,
      })
    }
    if (vitals.calcium_level > 10.5) {
      effects.push({
        category: 'electrolyte', label: `Ca²⁺↑`, icon: 'Ca', color: 'emerald',
        value: vitals.calcium_level,
      })
    } else if (vitals.calcium_level < 8.5) {
      effects.push({
        category: 'electrolyte', label: `Ca²⁺↓`, icon: 'Ca', color: 'emerald',
        value: vitals.calcium_level,
      })
    }

    return effects
  })

  /** 按分类统计活动效果数量，用于 Tab 徽章 */
  const activeCountByCategory = computed(() => {
    const counts: Record<string, number> = {}
    for (const e of derivedActiveStates.value) {
      counts[e.category] = (counts[e.category] || 0) + 1
    }
    return counts
  })

  return {
    connected,
    connecting,
    latency,
    error,
    vitals,
    interactions,
    categories,
    ecgSr,
    pcgSr,
    chunkIntervalMs,
    ecgChunkSize,
    pcgChunkSize,
    streamProtocol,
    lastSignalSeq,
    auscultationMode,
    auscultationArea,
    noiseReduction,
    beatAnnotations,
    conductionTrend,
    showAnnotations,
    showTrendChart,
    profiles,
    selectedProfileId,
    profileName,
    loadingProfiles,
    connect,
    disconnect,
    sendCommand,
    saveState,
    fetchProfiles,
    createProfile,
    deleteProfile,
    registerEcgCallback,
    registerPcgCallback,
    unregisterEcgCallback,
    unregisterPcgCallback,
    toggleAnnotations,
    toggleTrendChart,
    controlPanelTab,
    derivedActiveStates,
    activeCountByCategory,
    // Server info
    serverStartedAt,
    // Feature 2
    ecgSmoothingLevel,
    // Alarm
    alarmMuted,
    // Feature 4: Caliper
    caliperMode,
    // Feature 3
    selectedLeads,
    availableLeads,
    multiLeadMode,
    registerLeadCallback,
    unregisterLeadCallback,
    setLeads,
    // P1-PCG: Multi-position PCG
    registerPcgPositionCallback,
    unregisterPcgPositionCallback,
    // P1: Physiology visualization
    physiologyDetail,
    // P1-5: Valve events
    valveEvents,
  }
})

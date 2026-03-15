/**
 * useAlarmSystem — Clinical alarm evaluation, audio alerts & defibrillation estimation.
 *
 * Exports:
 *   - evaluateAlarms(vitals)        → AlarmState[]
 *   - createAlarmAudio()            → AlarmAudio
 *   - estimateDefibSuccess(vitals)  → number [0,1]
 *   - useAlarmSystem(vitals, opts?) → reactive composable
 */

import { computed, watch, ref, type Ref, toValue } from 'vue'

// ─── Types ────────────────────────────────────────────────────

export type AlarmLevel = 'warning' | 'critical'

export interface AlarmState {
  param: string
  level: AlarmLevel
  message: string
  value?: number | string
}

export interface AlarmAudio {
  isAvailable(): boolean
  playWarning(): void
  playCritical(): void
  stop(): void
  dispose(): void
}

// ─── Labels ───────────────────────────────────────────────────

const LABELS: Record<string, string> = {
  heart_rate: 'HR',
  systolic_bp: 'SBP',
  spo2: 'SpO2',
  respiratory_rate: 'RR',
  temperature: 'Temp',
  rhythm: '节律',
}

// ─── Numeric alarm rules ──────────────────────────────────────

interface NumericRule {
  warningLow?: number
  warningHigh?: number
  criticalLow?: number
  criticalHigh?: number
}

const NUMERIC_RULES: Record<string, NumericRule> = {
  heart_rate:       { warningLow: 50, warningHigh: 120, criticalLow: 40, criticalHigh: 150 },
  systolic_bp:      { warningLow: 90, warningHigh: 160, criticalLow: 70, criticalHigh: 200 },
  spo2:             { warningLow: 92, criticalLow: 85 },
  respiratory_rate: { warningLow: 8,  warningHigh: 30,  criticalLow: 5,  criticalHigh: 40 },
  temperature:      { warningLow: 36.0, warningHigh: 38.0, criticalLow: 35.0, criticalHigh: 40.0 },
}

// ─── Rhythm alarm rules ───────────────────────────────────────

const RHYTHM_ALARMS: Record<string, { level: AlarmLevel; tag: string }> = {
  vf:       { level: 'critical', tag: 'VF（室颤）' },
  vt:       { level: 'critical', tag: 'VT（室速）' },
  asystole: { level: 'critical', tag: '心搏停止' },
}

// ─── evaluateAlarms ───────────────────────────────────────────

export function evaluateAlarms(vitals: Record<string, any>): AlarmState[] {
  const alarms: AlarmState[] = []

  for (const [param, rule] of Object.entries(NUMERIC_RULES)) {
    const val = vitals[param]
    if (val == null || typeof val !== 'number') continue

    const label = LABELS[param] ?? param

    // Check critical first (tighter range)
    if (rule.criticalLow != null && val < rule.criticalLow) {
      alarms.push({ param, level: 'critical', message: `${label} 严重偏低 (${val})`, value: val })
      continue
    }
    if (rule.criticalHigh != null && val > rule.criticalHigh) {
      alarms.push({ param, level: 'critical', message: `${label} 严重偏高 (${val})`, value: val })
      continue
    }
    if (rule.warningLow != null && val < rule.warningLow) {
      alarms.push({ param, level: 'warning', message: `${label} 偏低 (${val})`, value: val })
      continue
    }
    if (rule.warningHigh != null && val > rule.warningHigh) {
      alarms.push({ param, level: 'warning', message: `${label} 偏高 (${val})`, value: val })
      continue
    }
  }

  // Rhythm
  const rhythm = vitals.rhythm
  if (typeof rhythm === 'string') {
    const entry = RHYTHM_ALARMS[rhythm.toLowerCase()]
    if (entry) {
      alarms.push({
        param: 'rhythm',
        level: entry.level,
        message: `${LABELS.rhythm}: ${entry.tag}`,
        value: rhythm,
      })
    }
  }

  return alarms
}

// ─── createAlarmAudio ─────────────────────────────────────────

export function createAlarmAudio(): AlarmAudio {
  const hasAudioContext = typeof globalThis.AudioContext !== 'undefined'

  if (!hasAudioContext) {
    return {
      isAvailable: () => false,
      playWarning: () => {},
      playCritical: () => {},
      stop: () => {},
      dispose: () => {},
    }
  }

  let ctx: AudioContext | null = null
  let criticalTimer: ReturnType<typeof setInterval> | null = null

  function getContext(): AudioContext {
    if (!ctx) ctx = new AudioContext()
    return ctx
  }

  function beep(freq: number, durationMs: number) {
    const ac = getContext()
    const osc = ac.createOscillator()
    const gain = ac.createGain()
    osc.type = 'sine'
    osc.frequency.value = freq
    gain.gain.value = 0.3
    osc.connect(gain)
    gain.connect(ac.destination)
    osc.start()
    osc.stop(ac.currentTime + durationMs / 1000)
  }

  function stopCritical() {
    if (criticalTimer != null) {
      clearInterval(criticalTimer)
      criticalTimer = null
    }
  }

  return {
    isAvailable: () => true,

    playWarning() {
      stopCritical()
      beep(440, 200)
    },

    playCritical() {
      stopCritical()
      beep(880, 200)
      criticalTimer = setInterval(() => beep(880, 200), 400)
    },

    stop() {
      stopCritical()
    },

    dispose() {
      stopCritical()
      if (ctx) {
        ctx.close().catch(() => {})
        ctx = null
      }
    },
  }
}

// ─── estimateDefibSuccess ─────────────────────────────────────

export function estimateDefibSuccess(vitals: Record<string, any>): number {
  const base = 0.55
  const amioBoost = (vitals.amiodarone_level || 0) * 0.15
  const damagePenalty = (vitals.damage_level || 0) * 0.20
  const countPenalty = (vitals.defibrillation_count || 0) * 0.03
  return Math.max(0, Math.min(1, base + amioBoost - damagePenalty - countPenalty))
}

// ─── useAlarmSystem composable ────────────────────────────────

export function useAlarmSystem(
  vitals: Record<string, any>,
  options?: { muted?: Ref<boolean> },
) {
  const activeAlarms = ref<AlarmState[]>([])
  const audio = createAlarmAudio()

  const hasCritical = computed(() => activeAlarms.value.some(a => a.level === 'critical'))
  const hasWarning = computed(() => activeAlarms.value.some(a => a.level === 'warning'))

  function getAlarmLevel(param: string): AlarmLevel | null {
    const alarm = activeAlarms.value.find(a => a.param === param)
    return alarm?.level ?? null
  }

  // Watch vitals reactively
  watch(
    () => ({ ...vitals }),
    (v) => {
      activeAlarms.value = evaluateAlarms(v)

      const muted = toValue(options?.muted) ?? false

      if (muted || !audio.isAvailable()) {
        audio.stop()
        return
      }

      if (hasCritical.value) {
        audio.playCritical()
      } else if (hasWarning.value) {
        audio.playWarning()
      } else {
        audio.stop()
      }
    },
    { immediate: true, deep: true },
  )

  // Watch muted changes
  if (options?.muted) {
    watch(options.muted, (m) => {
      if (m) audio.stop()
    })
  }

  function dispose() {
    audio.dispose()
  }

  return { activeAlarms, hasCritical, hasWarning, getAlarmLevel, dispose }
}

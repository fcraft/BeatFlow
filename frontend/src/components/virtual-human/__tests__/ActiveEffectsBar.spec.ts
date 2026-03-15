import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import ActiveEffectsBar from '../ActiveEffectsBar.vue'

// Create a mock store factory with configurable vitals
function createMockStore(vitalsOverrides: Record<string, any> = {}) {
  const defaultVitals = {
    heart_rate: 72,
    systolic_bp: 120,
    diastolic_bp: 80,
    spo2: 98,
    temperature: 36.6,
    respiratory_rate: 16,
    rhythm: 'normal',
    murmur_type: null,
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
    beta_blocker_level: 0,
    amiodarone_level: 0,
    digoxin_level: 0,
    atropine_level: 0,
    potassium_level: 4.0,
    calcium_level: 9.5,
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
    ...vitalsOverrides,
  }

  // Build derived active states from vitals (mirror store logic)
  const derivedActiveStates: any[] = []

  if (defaultVitals.exercise_intensity > 0.1) {
    let label = '步行'
    let icon = '🚶'
    if (defaultVitals.exercise_intensity > 0.7) { label = '跑步'; icon = '💨' }
    else if (defaultVitals.exercise_intensity > 0.4) { label = '慢跑'; icon = '🏃' }
    derivedActiveStates.push({
      category: 'exercise', label, icon, color: 'blue',
      value: Math.round(defaultVitals.exercise_intensity * 100),
    })
  }
  if (defaultVitals.emotional_arousal > 0.15) {
    derivedActiveStates.push({
      category: 'emotion', label: '情绪激活', icon: '😰', color: 'amber',
      value: Math.round(defaultVitals.emotional_arousal * 100),
    })
  }
  const rhythmMap: Record<string, { label: string; icon: string }> = {
    af: { label: '房颤', icon: '💔' },
    pvc: { label: '早搏', icon: '⚡' },
    svt: { label: 'SVT', icon: '⚡' },
    vt: { label: 'VT', icon: '💔' },
  }
  if (defaultVitals.rhythm !== 'normal' && rhythmMap[defaultVitals.rhythm]) {
    const r = rhythmMap[defaultVitals.rhythm]
    derivedActiveStates.push({ category: 'condition', label: r.label, icon: r.icon, color: 'red' })
  }
  if (defaultVitals.beta_blocker_level > 0.05) {
    derivedActiveStates.push({
      category: 'medication', label: 'β-阻滞剂', icon: '💊', color: 'purple',
      value: Math.round(defaultVitals.beta_blocker_level * 100),
    })
  }
  if (defaultVitals.potassium_level > 5.0) {
    derivedActiveStates.push({
      category: 'electrolyte', label: 'K⁺↑', icon: 'K⁺', color: 'emerald',
      value: defaultVitals.potassium_level,
    })
  } else if (defaultVitals.potassium_level < 3.5) {
    derivedActiveStates.push({
      category: 'electrolyte', label: 'K⁺↓', icon: 'K⁺', color: 'emerald',
      value: defaultVitals.potassium_level,
    })
  }

  return {
    vitals: defaultVitals,
    derivedActiveStates,
    activeCountByCategory: {},
    controlPanelTab: 'exercise',
  }
}

let currentMockStore = createMockStore()

vi.mock('@/store/virtualHuman', () => ({
  useVirtualHumanStore: () => currentMockStore,
}))

describe('ActiveEffectsBar', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    currentMockStore = createMockStore()
  })

  it('shows normal baseline when all vitals are normal', () => {
    const wrapper = mount(ActiveEffectsBar)
    expect(wrapper.text()).toContain('正常基线')
  })

  it('shows exercise pill when exercise_intensity > 0.1', () => {
    currentMockStore = createMockStore({ exercise_intensity: 0.5 })
    const wrapper = mount(ActiveEffectsBar)
    expect(wrapper.text()).toContain('慢跑')
    expect(wrapper.text()).toContain('50%')
  })

  it('shows medication pill when beta_blocker_level > 0.05', () => {
    currentMockStore = createMockStore({ beta_blocker_level: 0.6 })
    const wrapper = mount(ActiveEffectsBar)
    expect(wrapper.text()).toContain('β-阻滞剂')
    expect(wrapper.text()).toContain('60%')
  })

  it('shows condition pill when rhythm is af', () => {
    currentMockStore = createMockStore({ rhythm: 'af' })
    const wrapper = mount(ActiveEffectsBar)
    expect(wrapper.text()).toContain('房颤')
  })

  it('shows electrolyte pill when potassium is high', () => {
    currentMockStore = createMockStore({ potassium_level: 6.5 })
    const wrapper = mount(ActiveEffectsBar)
    expect(wrapper.text()).toContain('K⁺↑')
    expect(wrapper.text()).toContain('6.5')
  })

  it('navigates tab on pill click', async () => {
    currentMockStore = createMockStore({ exercise_intensity: 0.5 })
    const wrapper = mount(ActiveEffectsBar)
    const pills = wrapper.findAll('button')
    expect(pills.length).toBeGreaterThan(0)
    await pills[0].trigger('click')
    expect(currentMockStore.controlPanelTab).toBe('exercise')
  })
})

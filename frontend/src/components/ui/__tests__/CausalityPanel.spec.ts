import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import CausalityPanel from '@/components/ui/CausalityPanel.vue'

function makeEvent(overrides: Partial<any> = {}) {
  return {
    id: 'evt-001',
    timestamp_ms: 1000,
    source: 'baroreflex',
    source_detail: 'MAP_drop_15mmHg',
    target: 'heart_rate',
    target_path: 'vitals.heart_rate',
    old_value: 72.0,
    new_value: 85.0,
    delta: 13.0,
    mechanism: 'MAP↓ → baroreceptor unloading → sympathetic↑ → HR↑',
    confidence: 1.0,
    parent_event_id: null,
    ...overrides,
  }
}

describe('CausalityPanel', () => {
  it('renders empty state when no events', () => {
    const wrapper = mount(CausalityPanel, { props: { events: [] } })
    expect(wrapper.text()).toContain('No causal events yet')
  })

  it('renders event count', () => {
    const events = [makeEvent(), makeEvent({ id: 'evt-002', source: 'exercise_model', target: 'contractility' })]
    const wrapper = mount(CausalityPanel, { props: { events } })
    expect(wrapper.text()).toContain('2 events')
  })

  it('renders source label', () => {
    const wrapper = mount(CausalityPanel, {
      props: { events: [makeEvent()] },
    })
    expect(wrapper.text()).toContain('Baroreflex')
  })

  it('renders old → new values', () => {
    const wrapper = mount(CausalityPanel, {
      props: { events: [makeEvent({ old_value: 72, new_value: 85 })] },
    })
    expect(wrapper.text()).toContain('72')
    expect(wrapper.text()).toContain('85')
  })

  it('renders delta with sign', () => {
    const wrapper = mount(CausalityPanel, {
      props: { events: [makeEvent({ delta: 13 })] },
    })
    expect(wrapper.text()).toContain('+13.0')
  })

  it('expands event on click to show mechanism', async () => {
    const wrapper = mount(CausalityPanel, {
      props: { events: [makeEvent({ mechanism: 'MAP↓ → baroreceptor unloading' })] },
    })
    const row = wrapper.find('.cursor-pointer')
    await row.trigger('click')
    expect(wrapper.text()).toContain('MAP↓ → baroreceptor unloading')
    expect(wrapper.text()).toContain('baroreflex / MAP_drop_15mmHg')
  })

  it('shows negative delta in red', () => {
    const wrapper = mount(CausalityPanel, {
      props: { events: [makeEvent({ delta: -5.0, old_value: 85, new_value: 80 })] },
    })
    expect(wrapper.text()).toContain('-5.0')
    const el = wrapper.find('[class*="text-\\[\\#FF3B30\\]"]')
    expect(el.exists()).toBe(true)
  })

  it('renders chain children when expanded', async () => {
    const parent = makeEvent()
    const child = makeEvent({ id: 'child-01', parent_event_id: parent.id, source: 'hemodynamics', target: 'blood_pressure', delta: -5 })
    const wrapper = mount(CausalityPanel, {
      props: { events: [parent, child] },
    })
    const row = wrapper.find('.cursor-pointer')
    await row.trigger('click')
    expect(wrapper.text()).toContain('blood_pressure')
  })
})

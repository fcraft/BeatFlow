import { describe, it, expect, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useWaveformStore } from '../waveform'

describe('useWaveformStore', () => {
  beforeEach(() => { setActivePinia(createPinia()) })

  it('has default channels', () => {
    const store = useWaveformStore()
    expect(store.channels.length).toBe(2)
    expect(store.channels[0].source).toBe('lead_II')
  })

  it('pushSamples writes to buffer', () => {
    const store = useWaveformStore()
    store.initBuffer('ecg-ii', 500)
    store.pushSamples('ecg-ii', [0.1, 0.2, 0.3])
    expect(store.writePositions.get('ecg-ii')).toBe(3)
  })

  it('addChannel and removeChannel', () => {
    const store = useWaveformStore()
    const initial = store.channels.length
    store.addChannel({
      id: 'test', type: 'ecg', source: 'V1', color: '#fff',
      gain: 1, speed: 25, sampleRate: 500, gridEnabled: false, label: 'V1',
    })
    expect(store.channels.length).toBe(initial + 1)
    store.removeChannel('test')
    expect(store.channels.length).toBe(initial)
  })
})

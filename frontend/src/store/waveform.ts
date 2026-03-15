import { defineStore } from 'pinia'
import { ref } from 'vue'

export interface WaveformChannel {
  id: string
  type: 'ecg' | 'pcg' | 'pressure' | 'volume'
  source: string
  color: string
  gain: number
  speed: number
  sampleRate: number
  gridEnabled: boolean
  label: string
}

export const useWaveformStore = defineStore('waveform', () => {
  const channels = ref<WaveformChannel[]>([
    {
      id: 'ecg-ii', type: 'ecg', source: 'lead_II',
      color: '#6ee7b7', gain: 1.0, speed: 25,
      sampleRate: 500, gridEnabled: true, label: 'II',
    },
    {
      id: 'pcg-main', type: 'pcg', source: 'pcg',
      color: '#fcd34d', gain: 1.0, speed: 25,
      sampleRate: 4000, gridEnabled: false, label: 'PCG',
    },
  ])

  const BUFFER_SECONDS = 300
  const buffers = ref<Map<string, Float32Array>>(new Map())
  const writePositions = ref<Map<string, number>>(new Map())

  function initBuffer(channelId: string, sampleRate: number) {
    const size = sampleRate * BUFFER_SECONDS
    buffers.value.set(channelId, new Float32Array(size))
    writePositions.value.set(channelId, 0)
  }

  function pushSamples(channelId: string, samples: number[]) {
    const buf = buffers.value.get(channelId)
    if (!buf) return
    let pos = writePositions.value.get(channelId) ?? 0
    for (const s of samples) {
      buf[pos % buf.length] = s
      pos++
    }
    writePositions.value.set(channelId, pos)
  }

  function addChannel(channel: WaveformChannel) {
    channels.value.push(channel)
    initBuffer(channel.id, channel.sampleRate)
  }

  function removeChannel(id: string) {
    channels.value = channels.value.filter(c => c.id !== id)
    buffers.value.delete(id)
    writePositions.value.delete(id)
  }

  return {
    channels, buffers, writePositions, BUFFER_SECONDS,
    initBuffer, pushSamples, addChannel, removeChannel,
  }
})

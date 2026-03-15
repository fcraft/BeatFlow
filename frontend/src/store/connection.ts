import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useConnectionStore = defineStore('connection', () => {
  const status = ref<'disconnected' | 'connecting' | 'connected'>('disconnected')
  const protocolVersion = ref(2)
  const simTime = ref(0)
  const warnings = ref<string[]>([])

  const isConnected = computed(() => status.value === 'connected')

  function setConnected(proto: number) {
    status.value = 'connected'
    protocolVersion.value = proto
  }

  function setDisconnected() {
    status.value = 'disconnected'
  }

  function updateSimTime(t: number) {
    simTime.value = t
  }

  function addWarning(msg: string) {
    warnings.value.push(msg)
    if (warnings.value.length > 20) warnings.value.shift()
  }

  return {
    status, protocolVersion, simTime, warnings, isConnected,
    setConnected, setDisconnected, updateSimTime, addWarning,
  }
})

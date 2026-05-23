/**
 * 波形区域选择 composable
 *
 * 管理波形 canvas 上的拖拽框选状态。
 * 输出所选区域的起止时间，以及用于 canvas 渲染的覆盖层坐标。
 */

import { ref, computed } from 'vue'

export interface RegionSelection {
  startTime: number
  endTime: number
  /** Width as fraction of total duration [0, 1] */
  startRatio: number
  endRatio: number
}

export function useRegionSelection() {
  const selecting = ref(false)
  const selected = ref(false)

  const startRatio = ref(0)
  const endRatio = ref(0)

  const startTime = computed(() => startRatio.value)
  const endTime = computed(() => endRatio.value)

  const active = computed(() => selecting.value || selected.value)

  const regionStart = computed(() => Math.min(startRatio.value, endRatio.value))
  const regionEnd = computed(() => Math.max(startRatio.value, endRatio.value))

  function begin(ratio: number) {
    selecting.value = true
    selected.value = false
    startRatio.value = ratio
    endRatio.value = ratio
  }

  function update(ratio: number) {
    if (!selecting.value) return
    endRatio.value = Math.max(0, Math.min(1, ratio))
  }

  function end() {
    if (!selecting.value) return
    selecting.value = false
    const start = regionStart.value
    const end = regionEnd.value
    if (Math.abs(end - start) < 0.001) {
      selected.value = false
    } else {
      selected.value = true
    }
  }

  function cancel() {
    selecting.value = false
    selected.value = false
  }

  function setRegion(startR: number, endR: number) {
    startRatio.value = Math.max(0, Math.min(1, startR))
    endRatio.value = Math.max(0, Math.min(1, endR))
    selecting.value = false
    selected.value = Math.abs(endR - startR) > 0.001
  }

  function toTimeRange(totalDuration: number): RegionSelection | null {
    if (!selected.value || totalDuration <= 0) return null
    return {
      startTime: regionStart.value * totalDuration,
      endTime: regionEnd.value * totalDuration,
      startRatio: regionStart.value,
      endRatio: regionEnd.value,
    }
  }

  return {
    selecting,
    selected,
    startRatio,
    endRatio,
    active,
    regionStart,
    regionEnd,
    begin,
    update,
    end,
    cancel,
    setRegion,
    toTimeRange,
  }
}

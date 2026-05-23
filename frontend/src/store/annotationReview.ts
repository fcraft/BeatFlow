/**
 * 标注审核 Store
 *
 * 管理检测预览结果的审核流程：接收 → 筛选 → 选择 → 提交。
 * 配合 POST /detect/preview 和 POST /annotations/accept 使用。
 *
 * v2 新增：锚点标记 + 区域合并 + BPM 推算
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export interface ReviewAnnotation {
  id: string
  annotation_type: string
  start_time: number
  end_time: number
  confidence: number
  label: string
  selected: boolean
  trusted: boolean
}

export const useAnnotationReviewStore = defineStore('annotationReview', () => {
  const fileId = ref('')
  const algorithmUsed = ref('')
  const items = ref<ReviewAnnotation[]>([])
  const active = ref(false)
  const pendingAccept = ref(false)

  const selectedCount = computed(() => items.value.filter(i => i.selected).length)
  const totalCount = computed(() => items.value.length)
  const trustedCount = computed(() => items.value.filter(i => i.trusted).length)
  const allSelected = computed(() => totalCount.value > 0 && selectedCount.value === totalCount.value)

  const typeBreakdown = computed(() => {
    const map: Record<string, number> = {}
    for (const item of items.value) {
      map[item.annotation_type] = (map[item.annotation_type] ?? 0) + 1
    }
    return map
  })

  const selectedBreakdown = computed(() => {
    const map: Record<string, number> = {}
    for (const item of items.value) {
      if (item.selected) {
        map[item.annotation_type] = (map[item.annotation_type] ?? 0) + 1
      }
    }
    return map
  })

  const lowConfidenceItems = computed(() =>
    items.value.filter(i => i.confidence < 0.6)
  )

  /** 已标记为锚点的标注，按时间排序 */
  const trustedAnchors = computed(() =>
    items.value.filter(i => i.trusted).sort((a, b) => a.start_time - b.start_time)
  )

  /** 基于锚点推算的 BPM 区间，锚点 < 3 个时返回 null */
  const anchorBpmEstimate = computed(() => {
    const anchors = trustedAnchors.value
    if (anchors.length < 3) return null
    const intervals: number[] = []
    for (let i = 1; i < anchors.length; i++) {
      const rr = anchors[i].start_time - anchors[i - 1].start_time
      if (rr > 0.2 && rr < 3.0) intervals.push(rr)
    }
    if (intervals.length === 0) return null
    const meanRR = intervals.reduce((s, v) => s + v, 0) / intervals.length
    const meanBpm = 60 / meanRR
    return {
      meanBpm: Math.round(meanBpm),
      minBpm: Math.max(20, Math.round(meanBpm * 0.75)),
      maxBpm: Math.min(250, Math.round(meanBpm * 1.35)),
      anchorCount: anchors.length,
    }
  })

  function makeItems(items_raw: any[], idxOff: number) {
    return items_raw.map((item: any, idx: number) => ({
      id: item._idx !== undefined ? String(item._idx) : String(idxOff + idx),
      annotation_type: item.annotation_type,
      start_time: item.start_time,
      end_time: item.end_time,
      confidence: item.confidence ?? 0,
      label: item.label ?? item.annotation_type?.toUpperCase() ?? '',
      selected: true,
      trusted: false,
    }))
  }

  function load(items_raw: any[], fid: string, algo: string) {
    fileId.value = fid
    algorithmUsed.value = algo
    items.value = makeItems(items_raw, 0)
    active.value = true
  }

  function toggleSelect(id: string) {
    const item = items.value.find(i => i.id === id)
    if (item) item.selected = !item.selected
  }

  function selectAll() {
    for (const item of items.value) item.selected = true
  }

  function deselectAll() {
    for (const item of items.value) item.selected = false
  }

  function selectByConfidence(minConfidence: number) {
    for (const item of items.value) {
      item.selected = item.confidence >= minConfidence
    }
  }

  function selectByType(annotationType: string, selected: boolean) {
    for (const item of items.value) {
      if (item.annotation_type === annotationType) {
        item.selected = selected
      }
    }
  }

  function toggleTrusted(id: string) {
    const item = items.value.find(i => i.id === id)
    if (item) item.trusted = !item.trusted
  }

  /** 获取 [t0, t1] 范围内及附近（前后各 margin 秒）的锚点 */
  function getTrustedAnchorsInRange(t0: number, t1: number, margin: number = 3): ReviewAnnotation[] {
    return trustedAnchors.value.filter(a =>
      a.start_time >= t0 - margin && a.start_time <= t1 + margin
    )
  }

  /** 计算指定锚点集合的 BPM 区间 */
  function computeBpmFromAnchors(anchors: ReviewAnnotation[]) {
    const sorted = [...anchors].sort((a, b) => a.start_time - b.start_time)
    const intervals: number[] = []
    for (let i = 1; i < sorted.length; i++) {
      const rr = sorted[i].start_time - sorted[i - 1].start_time
      if (rr > 0.2 && rr < 3.0) intervals.push(rr)
    }
    if (intervals.length < 2) return null
    const meanRR = intervals.reduce((s, v) => s + v, 0) / intervals.length
    const meanBpm = 60 / meanRR
    return {
      meanBpm: Math.round(meanBpm),
      minBpm: Math.max(20, Math.round(meanBpm * 0.75)),
      maxBpm: Math.min(250, Math.round(meanBpm * 1.35)),
      anchorCount: anchors.length,
    }
  }

  /**
   * 合并区域重检测结果：替换 [regionStart, regionEnd] 内的项，保留区域外的项。
   * 首次调用时自动将当前 items 保存为 baseItems（后续 merge 基于 baseItems 的干净副本）。
   */
  function mergeRegionItems(
    regionItems: any[],
    regionStart: number,
    regionEnd: number,
    fid: string,
    algo: string,
  ) {
    fileId.value = fid
    algorithmUsed.value = algo
    active.value = true

    // 保留区域外的原有项（保留 trusted 状态）
    const outside = items.value.filter(i => {
      const et = i.end_time ?? i.start_time
      return et <= regionStart || i.start_time >= regionEnd
    })
    // 新区域项
    const newItems = makeItems(regionItems, items.value.length)
    // 合并排序
    const merged = [...outside, ...newItems].sort((a, b) => a.start_time - b.start_time)
    items.value = merged
  }

  function getSelectedItems() {
    return items.value.filter(i => i.selected).map(i => ({
      annotation_type: i.annotation_type,
      start_time: i.start_time,
      end_time: i.end_time,
      confidence: i.confidence,
      label: i.label,
    }))
  }

  function reset() {
    fileId.value = ''
    algorithmUsed.value = ''
    items.value = []
    active.value = false
    pendingAccept.value = false
  }

  return {
    fileId,
    algorithmUsed,
    items,
    active,
    pendingAccept,
    selectedCount,
    totalCount,
    trustedCount,
    allSelected,
    typeBreakdown,
    selectedBreakdown,
    lowConfidenceItems,
    trustedAnchors,
    anchorBpmEstimate,
    load,
    toggleSelect,
    selectAll,
    deselectAll,
    selectByConfidence,
    selectByType,
    toggleTrusted,
    getTrustedAnchorsInRange,
    computeBpmFromAnchors,
    mergeRegionItems,
    getSelectedItems,
    reset,
  }
})

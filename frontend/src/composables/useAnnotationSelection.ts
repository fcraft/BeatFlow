/**
 * 标注多选 composable
 *
 * 管理标注列表的多选状态，支持 Shift 范围选择、Cmd/Ctrl 离散选择。
 */

import { ref, computed } from 'vue'

export function useAnnotationSelection() {
  const selectedIds = ref<Set<string>>(new Set())
  const lastClickedId = ref<string | null>(null)

  const selectedCount = computed(() => selectedIds.value.size)
  const hasSelection = computed(() => selectedIds.value.size > 0)

  function isSelected(id: string): boolean {
    return selectedIds.value.has(id)
  }

  function toggle(id: string, shiftKey: boolean = false, allIds: string[] = []) {
    if (shiftKey && lastClickedId.value && allIds.length > 0) {
      const lastIdx = allIds.indexOf(lastClickedId.value)
      const currIdx = allIds.indexOf(id)
      if (lastIdx >= 0 && currIdx >= 0) {
        const start = Math.min(lastIdx, currIdx)
        const end = Math.max(lastIdx, currIdx)
        for (let i = start; i <= end; i++) {
          selectedIds.value.add(allIds[i])
        }
        lastClickedId.value = id
        return
      }
    }

    lastClickedId.value = id
    if (selectedIds.value.has(id)) {
      selectedIds.value.delete(id)
    } else {
      selectedIds.value.add(id)
    }
  }

  function selectOnly(id: string) {
    selectedIds.value = new Set([id])
    lastClickedId.value = id
  }

  function selectRange(ids: string[]) {
    for (const id of ids) {
      selectedIds.value.add(id)
    }
  }

  function selectAll(ids: string[]) {
    selectedIds.value = new Set(ids)
  }

  function deselectAll() {
    selectedIds.value = new Set()
    lastClickedId.value = null
  }

  function getSelectedIds(): string[] {
    return Array.from(selectedIds.value)
  }

  function deleteSelected() {
    selectedIds.value = new Set()
    lastClickedId.value = null
  }

  return {
    selectedIds,
    selectedCount,
    hasSelection,
    isSelected,
    toggle,
    selectOnly,
    selectRange,
    selectAll,
    deselectAll,
    getSelectedIds,
    deleteSelected,
  }
}

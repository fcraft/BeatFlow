/**
 * 撤销/重做 composable
 *
 * 基于命令模式的操作栈，支持任意异步操作的撤销和重做。
 * 默认保存最近 20 步操作，超出时丢弃最早步骤。
 */

import { ref, computed } from 'vue'

export interface UndoableAction {
  label: string
  undo: () => Promise<void> | void
  redo: () => Promise<void> | void
}

export interface UndoRedoOptions {
  maxHistory?: number
}

export function useUndoRedo(options: UndoRedoOptions = {}) {
  const maxHistory = options.maxHistory ?? 20

  const undoStack = ref<UndoableAction[]>([])
  const redoStack = ref<UndoableAction[]>([])

  const canUndo = computed(() => undoStack.value.length > 0)
  const canRedo = computed(() => redoStack.value.length > 0)

  const historyLength = computed(() => undoStack.value.length)

  function record(label: string, undoFn: () => Promise<void> | void, redoFn: () => Promise<void> | void) {
    redoStack.value = []

    undoStack.value.push({
      label,
      undo: undoFn,
      redo: redoFn,
    })

    if (undoStack.value.length > maxHistory) {
      undoStack.value.shift()
    }
  }

  async function undo() {
    if (!canUndo.value) return
    const action = undoStack.value.pop()!
    redoStack.value.push(action)
    await action.undo()
  }

  async function redo() {
    if (!canRedo.value) return
    const action = redoStack.value.pop()!
    undoStack.value.push(action)
    await action.redo()
  }

  function clear() {
    undoStack.value = []
    redoStack.value = []
  }

  function lastAction(): string | null {
    if (undoStack.value.length === 0) return null
    return undoStack.value[undoStack.value.length - 1].label
  }

  return {
    record,
    undo,
    redo,
    canUndo,
    canRedo,
    historyLength,
    lastAction,
    clear,
  }
}

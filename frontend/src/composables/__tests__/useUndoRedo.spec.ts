/**
 * useUndoRedo unit tests
 */
import { describe, it, expect } from 'vitest'
import { useUndoRedo } from '../useUndoRedo'

describe('useUndoRedo', () => {
  it('initial state: cannot undo or redo', () => {
    const { canUndo, canRedo, historyLength } = useUndoRedo()
    expect(canUndo.value).toBe(false)
    expect(canRedo.value).toBe(false)
    expect(historyLength.value).toBe(0)
  })

  it('record enables undo', () => {
    const { record, canUndo } = useUndoRedo()
    record('test', () => {}, () => {})
    expect(canUndo.value).toBe(true)
  })

  it('undo pops action and enables redo', async () => {
    const { record, undo, canUndo, canRedo } = useUndoRedo()
    const undoFn = () => {}
    const redoFn = () => {}
    record('test', undoFn, redoFn)
    await undo()
    expect(canUndo.value).toBe(false)
    expect(canRedo.value).toBe(true)
  })

  it('redo restores undo capability', async () => {
    const { record, undo, redo, canUndo, canRedo } = useUndoRedo()
    record('test', () => {}, () => {})
    await undo()
    await redo()
    expect(canUndo.value).toBe(true)
    expect(canRedo.value).toBe(false)
  })

  it('new record clears redo stack', async () => {
    const { record, undo, canRedo } = useUndoRedo()
    record('a', () => {}, () => {})
    record('b', () => {}, () => {})
    await undo()
    expect(canRedo.value).toBe(true)
    record('c', () => {}, () => {})
    expect(canRedo.value).toBe(false)
  })

  it('undo and redo call correct functions', async () => {
    const { record, undo, redo } = useUndoRedo()
    let counter = 0

    // undo decrements, redo increments
    record(
      'add',
      () => { counter-- },
      () => { counter++ },
    )

    // undo executes undo function: counter = -1
    await undo()
    expect(counter).toBe(-1)

    // redo executes redo function: counter = 0
    await redo()
    expect(counter).toBe(0)
  })

  it('undo on empty stack does nothing', async () => {
    const { undo, canUndo } = useUndoRedo()
    await undo()
    expect(canUndo.value).toBe(false)
  })

  it('redo on empty stack does nothing', async () => {
    const { redo, canRedo } = useUndoRedo()
    await redo()
    expect(canRedo.value).toBe(false)
  })

  it('records label in history', () => {
    const { record, lastAction } = useUndoRedo()
    record('delete annotation', () => {}, () => {})
    expect(lastAction()).toBe('delete annotation')
  })

  it('respects maxHistory limit', () => {
    const { record, historyLength } = useUndoRedo({ maxHistory: 3 })
    record('a', () => {}, () => {})
    record('b', () => {}, () => {})
    record('c', () => {}, () => {})
    record('d', () => {}, () => {})
    expect(historyLength.value).toBe(3)
  })

  it('clear resets everything', () => {
    const { record, clear, canUndo, canRedo, historyLength } = useUndoRedo()
    record('a', () => {}, () => {})
    clear()
    expect(canUndo.value).toBe(false)
    expect(canRedo.value).toBe(false)
    expect(historyLength.value).toBe(0)
  })

  it('async undo/redo supported', async () => {
    const { record, undo, redo } = useUndoRedo()
    const steps: string[] = []

    record('async',
      async () => { steps.push('undo') },
      async () => { steps.push('redo') },
    )

    await undo()
    await redo()
    expect(steps).toEqual(['undo', 'redo'])
  })

  it('multiple records stack correctly', async () => {
    const { record, undo, canUndo, historyLength } = useUndoRedo()
    record('a', () => {}, () => {})
    record('b', () => {}, () => {})
    record('c', () => {}, () => {})

    expect(historyLength.value).toBe(3)

    await undo()
    expect(historyLength.value).toBe(2)
    expect(canUndo.value).toBe(true)

    await undo()
    expect(historyLength.value).toBe(1)

    await undo()
    expect(canUndo.value).toBe(false)
  })
})

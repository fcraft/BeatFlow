/**
 * useKeyboardShortcuts unit tests
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { ref } from 'vue'
import { useKeyboardShortcuts, type ShortcutDef } from '../useKeyboardShortcuts'

function fireKeydown(key: string, opts: { ctrl?: boolean; shift?: boolean; alt?: boolean } = {}) {
  window.dispatchEvent(new KeyboardEvent('keydown', {
    key,
    ctrlKey: opts.ctrl ?? false,
    shiftKey: opts.shift ?? false,
    altKey: opts.alt ?? false,
    metaKey: false,
    bubbles: true,
  }))
}

describe('useKeyboardShortcuts', () => {
  beforeEach(() => {
    document.body.innerHTML = ''
  })

  it('calls handler when matching key is pressed', () => {
    const handler = vi.fn()
    const shortcuts: ShortcutDef[] = [{ key: 'a', handler }]
    const { activate } = useKeyboardShortcuts(shortcuts)
    activate()

    fireKeydown('a')
    expect(handler).toHaveBeenCalledOnce()
  })

  it('does not call handler for non-matching key', () => {
    const handler = vi.fn()
    const shortcuts: ShortcutDef[] = [{ key: 'a', handler }]
    const { activate } = useKeyboardShortcuts(shortcuts)
    activate()

    fireKeydown('b')
    expect(handler).not.toHaveBeenCalled()
  })

  it('matches Ctrl+key combinations', () => {
    const handler = vi.fn()
    const shortcuts: ShortcutDef[] = [{ key: 'z', ctrl: true, handler }]
    const { activate } = useKeyboardShortcuts(shortcuts)
    activate()

    fireKeydown('z', { ctrl: true })
    expect(handler).toHaveBeenCalledOnce()
  })

  it('ignores Ctrl+key without ctrl modifier', () => {
    const handler = vi.fn()
    const shortcuts: ShortcutDef[] = [{ key: 'z', handler }]
    const { activate } = useKeyboardShortcuts(shortcuts)
    activate()

    fireKeydown('z', { ctrl: true })
    expect(handler).not.toHaveBeenCalled()
  })

  it('matches Shift+key combinations', () => {
    const handler = vi.fn()
    const shortcuts: ShortcutDef[] = [{ key: 'Tab', shift: true, handler }]
    const { activate } = useKeyboardShortcuts(shortcuts)
    activate()

    fireKeydown('Tab', { shift: true })
    expect(handler).toHaveBeenCalledOnce()
  })

  it('ignores single-letter shortcuts when input is focused', () => {
    const input = document.createElement('input')
    document.body.appendChild(input)
    input.focus()

    const handler = vi.fn()
    const shortcuts: ShortcutDef[] = [{ key: 'n', handler }]
    const { activate } = useKeyboardShortcuts(shortcuts)
    activate()

    fireKeydown('n')
    expect(handler).not.toHaveBeenCalled()
  })

  it('still fires Ctrl+letter shortcuts when input is focused', () => {
    const input = document.createElement('input')
    document.body.appendChild(input)
    input.focus()

    const handler = vi.fn()
    const shortcuts: ShortcutDef[] = [{ key: 'z', ctrl: true, handler }]
    const { activate } = useKeyboardShortcuts(shortcuts)
    activate()

    fireKeydown('z', { ctrl: true })
    expect(handler).toHaveBeenCalledOnce()
  })

  it('ignores shortcuts when textarea is focused', () => {
    const ta = document.createElement('textarea')
    document.body.appendChild(ta)
    ta.focus()

    const handler = vi.fn()
    const shortcuts: ShortcutDef[] = [{ key: 'e', handler }]
    const { activate } = useKeyboardShortcuts(shortcuts)
    activate()

    fireKeydown('e')
    expect(handler).not.toHaveBeenCalled()
  })

  it('ignores shortcuts when select is focused', () => {
    const select = document.createElement('select')
    document.body.appendChild(select)
    select.focus()

    const handler = vi.fn()
    const shortcuts: ShortcutDef[] = [{ key: 'd', handler }]
    const { activate } = useKeyboardShortcuts(shortcuts)
    activate()

    fireKeydown('d')
    expect(handler).not.toHaveBeenCalled()
  })

  it('respects enabled ref — disabled does not fire', () => {
    const handler = vi.fn()
    const enabled = ref(false)
    const shortcuts: ShortcutDef[] = [{ key: 'a', handler }]
    const { activate } = useKeyboardShortcuts(shortcuts, enabled)
    activate()

    fireKeydown('a')
    expect(handler).not.toHaveBeenCalled()
  })

  it('respects enabled ref — enabled fires', () => {
    const handler = vi.fn()
    const enabled = ref(true)
    const shortcuts: ShortcutDef[] = [{ key: 'a', handler }]
    const { activate } = useKeyboardShortcuts(shortcuts, enabled)
    activate()

    fireKeydown('a')
    expect(handler).toHaveBeenCalledOnce()
  })

  it('matches Space key', () => {
    const handler = vi.fn()
    const shortcuts: ShortcutDef[] = [{ key: ' ', handler }]
    const { activate } = useKeyboardShortcuts(shortcuts)
    activate()

    fireKeydown(' ')
    expect(handler).toHaveBeenCalledOnce()
  })

  it('matches Delete key', () => {
    const handler = vi.fn()
    const shortcuts: ShortcutDef[] = [{ key: 'Delete', handler }]
    const { activate } = useKeyboardShortcuts(shortcuts)
    activate()

    fireKeydown('Delete')
    expect(handler).toHaveBeenCalledOnce()
  })

  it('matches Escape key', () => {
    const handler = vi.fn()
    const shortcuts: ShortcutDef[] = [{ key: 'Escape', handler }]
    const { activate } = useKeyboardShortcuts(shortcuts)
    activate()

    fireKeydown('Escape')
    expect(handler).toHaveBeenCalledOnce()
  })

  it('matches Alt+key', () => {
    const handler = vi.fn()
    const shortcuts: ShortcutDef[] = [{ key: 'h', alt: true, handler }]
    const { activate } = useKeyboardShortcuts(shortcuts)
    activate()

    fireKeydown('h', { alt: true })
    expect(handler).toHaveBeenCalledOnce()
  })

  it('getShortcutList returns formatted list', () => {
    const shortcuts: ShortcutDef[] = [
      { key: 'z', ctrl: true, description: 'Undo', handler: vi.fn() },
      { key: ' ', description: 'Play/Pause', handler: vi.fn() },
    ]
    const { getShortcutList } = useKeyboardShortcuts(shortcuts)
    const list = getShortcutList()
    expect(list).toHaveLength(2)
    expect(list[0]).toEqual({ key: 'Ctrl+Z', description: 'Undo' })
    expect(list[1]).toEqual({ key: 'Space', description: 'Play/Pause' })
  })

  it('deactivate stops handler from firing', () => {
    const handler = vi.fn()
    const shortcuts: ShortcutDef[] = [{ key: 'a', handler }]
    const { activate, deactivate } = useKeyboardShortcuts(shortcuts)
    activate()
    deactivate()

    fireKeydown('a')
    expect(handler).not.toHaveBeenCalled()
  })
})

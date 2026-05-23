/**
 * 全局键盘快捷键管理 composable
 *
 * 支持快捷键注册/注销，自动忽略输入框内按键事件。
 * 支持组合键 (Ctrl/Shift/Alt/Meta + key)。
 *
 * 测试中若不在 Vue 组件上下文中，可调用返回的 activate() 手动启动。
 */

import { onMounted, onUnmounted, ref, type Ref, getCurrentInstance } from 'vue'

export interface ShortcutDef {
  key: string
  ctrl?: boolean
  shift?: boolean
  alt?: boolean
  meta?: boolean
  handler: () => void
  description?: string
}

const INPUT_ELEMENTS = new Set(['INPUT', 'TEXTAREA', 'SELECT'])

function isInputFocused(): boolean {
  const el = document.activeElement
  if (!el) return false
  return INPUT_ELEMENTS.has(el.tagName) || (el as HTMLElement).isContentEditable
}

function matchKey(e: KeyboardEvent, def: ShortcutDef): boolean {
  if (e.key.toLowerCase() !== def.key.toLowerCase()) return false
  if (!!def.ctrl !== (e.ctrlKey || e.metaKey)) return false
  if (!!def.shift !== e.shiftKey) return false
  if (!!def.alt !== e.altKey) return false
  return true
}

export function useKeyboardShortcuts(shortcuts: ShortcutDef[], enabled: Ref<boolean> = ref(true)) {
  let active = false

  function handleKeydown(e: KeyboardEvent) {
    if (!enabled.value) return

    for (const def of shortcuts) {
      if (matchKey(e, def)) {
        if (isInputFocused() && def.key.length === 1 && !def.ctrl) {
          continue
        }
        e.preventDefault()
        def.handler()
        return
      }
    }
  }

  function activate() {
    if (active) return
    active = true
    window.addEventListener('keydown', handleKeydown)
  }

  function deactivate() {
    if (!active) return
    active = false
    window.removeEventListener('keydown', handleKeydown)
  }

  // 在 Vue 组件上下文中自动挂载
  if (getCurrentInstance()) {
    onMounted(activate)
    onUnmounted(deactivate)
  }

  return {
    activate,
    deactivate,
    /** 获取所有已注册快捷键的描述列表 */
    getShortcutList: () => shortcuts.map(s => ({
      key: [
        s.ctrl ? 'Ctrl+' : '',
        s.shift ? 'Shift+' : '',
        s.alt ? 'Alt+' : '',
        s.key === ' ' ? 'Space' : s.key.toUpperCase(),
      ].join(''),
      description: s.description ?? '',
    })),
  }
}

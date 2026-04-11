import { defineStore } from 'pinia'
import { ref } from 'vue'

export type ToastType = 'success' | 'error' | 'warning' | 'info'

export interface ToastAction {
  label: string
  onClick: () => void
}

export interface Toast {
  id: number
  type: ToastType
  title?: string
  message: string
  action?: ToastAction
  duration: number
}

export interface ToastOptions {
  title?: string
  duration?: number
  action?: ToastAction
}

let nextId = 0

export const useToastStore = defineStore('toast', () => {
  const toasts = ref<Toast[]>([])

  const add = (type: ToastType, message: string, titleOrOpts?: string | ToastOptions, duration = 3500) => {
    const id = nextId++
    let title: string | undefined
    let action: ToastAction | undefined
    let dur = duration

    // Support both old API (title string) and new API (options object)
    if (typeof titleOrOpts === 'string') {
      title = titleOrOpts
    } else if (titleOrOpts && typeof titleOrOpts === 'object') {
      title = titleOrOpts.title
      action = titleOrOpts.action
      dur = titleOrOpts.duration ?? duration
    }

    toasts.value.push({ id, type, title, message, action, duration: dur })
    if (dur > 0) {
      setTimeout(() => remove(id), dur)
    }
  }

  const remove = (id: number) => {
    toasts.value = toasts.value.filter(t => t.id !== id)
  }

  const success = (message: string, titleOrOpts?: string | ToastOptions) => add('success', message, titleOrOpts)
  const error   = (message: string, titleOrOpts?: string | ToastOptions) => add('error', message, titleOrOpts)
  const warning = (message: string, titleOrOpts?: string | ToastOptions) => add('warning', message, titleOrOpts)
  const info    = (message: string, titleOrOpts?: string | ToastOptions) => add('info', message, titleOrOpts)

  return { toasts, add, remove, success, error, warning, info }
})

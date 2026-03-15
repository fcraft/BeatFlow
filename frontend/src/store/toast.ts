import { defineStore } from 'pinia'
import { ref } from 'vue'

type ToastType = 'success' | 'error' | 'warning' | 'info'

interface Toast {
  id: number
  type: ToastType
  title?: string
  message: string
}

let nextId = 0

export const useToastStore = defineStore('toast', () => {
  const toasts = ref<Toast[]>([])

  const add = (type: ToastType, message: string, title?: string, duration = 3500) => {
    const id = nextId++
    toasts.value.push({ id, type, title, message })
    setTimeout(() => remove(id), duration)
  }

  const remove = (id: number) => {
    toasts.value = toasts.value.filter(t => t.id !== id)
  }

  const success = (message: string, title?: string) => add('success', message, title)
  const error   = (message: string, title?: string) => add('error', message, title)
  const warning = (message: string, title?: string) => add('warning', message, title)
  const info    = (message: string, title?: string) => add('info', message, title)

  return { toasts, add, remove, success, error, warning, info }
})

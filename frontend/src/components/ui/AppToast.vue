<template>
  <Teleport to="body">
    <div class="fixed top-4 right-4 z-50 flex flex-col gap-2 w-80 pointer-events-none">
      <TransitionGroup name="toast" tag="div" class="flex flex-col gap-2">
        <div
          v-for="toast in toasts"
          :key="toast.id"
          class="pointer-events-auto flex items-start gap-3 p-4 rounded-xl shadow-lg border text-sm font-medium"
          :class="toastClass(toast.type)"
        >
          <component :is="toastIcon(toast.type)" class="w-5 h-5 mt-0.5 shrink-0" />
          <div class="flex-1 min-w-0">
            <div v-if="toast.title" class="font-semibold">{{ toast.title }}</div>
            <div class="text-xs opacity-90 mt-0.5">{{ toast.message }}</div>
          </div>
          <button @click="remove(toast.id)" class="opacity-60 hover:opacity-100 transition-opacity shrink-0">
            <X class="w-4 h-4" />
          </button>
        </div>
      </TransitionGroup>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { CheckCircle2, AlertCircle, Info, AlertTriangle, X } from 'lucide-vue-next'
import { useToastStore } from '@/store/toast'
import { storeToRefs } from 'pinia'

const toastStore = useToastStore()
const { toasts } = storeToRefs(toastStore)
const { remove } = toastStore

const toastClass = (type: string) => ({
  success: 'bg-emerald-50 border-emerald-200 text-emerald-800',
  error:   'bg-red-50 border-red-200 text-red-800',
  warning: 'bg-amber-50 border-amber-200 text-amber-800',
  info:    'bg-blue-50 border-blue-200 text-blue-800',
}[type] ?? 'bg-gray-50 border-gray-200 text-gray-800')

const toastIcon = (type: string) => ({
  success: CheckCircle2,
  error: AlertCircle,
  warning: AlertTriangle,
  info: Info,
}[type] ?? Info)
</script>

<style>
.toast-enter-active, .toast-leave-active { transition: all 0.25s ease; }
.toast-enter-from { opacity: 0; transform: translateX(100%); }
.toast-leave-to   { opacity: 0; transform: translateX(100%); }
.toast-move       { transition: transform 0.25s ease; }
</style>

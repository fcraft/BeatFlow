<template>
  <Teleport to="body">
    <!-- Desktop: top-right -->
    <div class="toast-container toast-container--desktop">
      <TransitionGroup name="toast-desktop" tag="div" class="flex flex-col gap-2.5">
        <div
          v-for="t in toasts"
          :key="t.id"
          class="toast-card"
          :style="cardVar(t.type)"
        >
          <!-- Countdown glow: full-width background gradient that shrinks (only for action toasts) -->
          <div v-if="t.action && t.duration > 0" class="toast-countdown" :style="{ animationDuration: t.duration + 'ms' }" />

          <!-- Content -->
          <div class="relative flex items-center gap-3 px-4 py-3.5">
            <div class="toast-icon-wrap">
              <component :is="toastIcon(t.type)" class="w-[18px] h-[18px]" style="color: var(--t-color)" />
            </div>
            <div class="flex-1 min-w-0">
              <div v-if="t.title" class="text-sm font-semibold text-white/90 leading-snug">{{ t.title }}</div>
              <div class="text-[13px] text-white/55 leading-snug" :class="t.title ? 'mt-0.5' : ''">{{ t.message }}</div>
              <button
                v-if="t.action"
                class="toast-action mt-2"
                @click="handleAction(t)"
              >
                {{ t.action.label }}
              </button>
            </div>
            <button
              @click="remove(t.id)"
              class="w-6 h-6 flex items-center justify-center rounded-md text-white/25 hover:text-white/50 hover:bg-white/[0.06] transition-all shrink-0"
            >
              <X class="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </TransitionGroup>
    </div>

    <!-- Mobile: bottom-center -->
    <div class="toast-container toast-container--mobile">
      <TransitionGroup name="toast-mobile" tag="div" class="flex flex-col gap-2">
        <div
          v-for="t in toasts"
          :key="t.id"
          class="toast-card"
          :style="cardVar(t.type)"
        >
          <div v-if="t.action && t.duration > 0" class="toast-countdown" :style="{ animationDuration: t.duration + 'ms' }" />
          <div class="relative flex items-center gap-3 px-3.5 py-3">
            <component :is="toastIcon(t.type)" class="w-[18px] h-[18px] shrink-0" style="color: var(--t-color)" />
            <div class="flex-1 min-w-0">
              <span class="text-[13px] text-white/80">
                <span v-if="t.title" class="font-semibold">{{ t.title }} </span>
                {{ t.message }}
              </span>
            </div>
            <button
              v-if="t.action"
              class="toast-action text-[12px] shrink-0"
              @click="handleAction(t)"
            >
              {{ t.action.label }}
            </button>
            <button
              @click="remove(t.id)"
              class="w-5 h-5 flex items-center justify-center text-white/25 hover:text-white/50 shrink-0"
            >
              <X class="w-3 h-3" />
            </button>
          </div>
        </div>
      </TransitionGroup>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { CheckCircle2, AlertCircle, Info, AlertTriangle, X } from 'lucide-vue-next'
import { useToastStore, type Toast } from '@/store/toast'
import { storeToRefs } from 'pinia'

const toastStore = useToastStore()
const { toasts } = storeToRefs(toastStore)
const { remove } = toastStore

function handleAction(t: Toast) {
  t.action?.onClick()
  remove(t.id)
}

const toastIcon = (type: string) => ({
  success: CheckCircle2,
  error: AlertCircle,
  warning: AlertTriangle,
  info: Info,
}[type] ?? Info)

const typeColors: Record<string, string> = {
  success: '16, 185, 129',
  error:   '239, 68, 68',
  warning: '245, 158, 11',
  info:    '59, 130, 246',
}

function cardVar(type: string) {
  const rgb = typeColors[type] ?? '156, 163, 175'
  return { '--t-rgb': rgb, '--t-color': `rgb(${rgb})` } as Record<string, string>
}
</script>

<style>
/* ─── Container positioning ─── */
.toast-container {
  position: fixed;
  z-index: 99999;
  pointer-events: none;
}
.toast-container--desktop {
  top: 1rem;
  right: 1rem;
  width: 360px;
}
.toast-container--mobile {
  display: none;
}

@media (max-width: 640px) {
  .toast-container--desktop { display: none; }
  .toast-container--mobile {
    display: block;
    bottom: 1rem;
    left: 0.75rem;
    right: 0.75rem;
  }
}

/* ─── Card: frosted glass with color tint ─── */
.toast-card {
  pointer-events: auto;
  position: relative;
  overflow: hidden;
  border-radius: 14px;
  background:
    linear-gradient(135deg, rgba(var(--t-rgb), 0.06) 0%, transparent 60%),
    rgba(28, 28, 32, 0.75);
  backdrop-filter: blur(24px) saturate(1.6);
  -webkit-backdrop-filter: blur(24px) saturate(1.6);
  border: 1px solid rgba(var(--t-rgb), 0.12);
  box-shadow:
    0 8px 32px rgba(0, 0, 0, 0.3),
    0 0 0 0.5px rgba(255, 255, 255, 0.04) inset,
    inset 0 1px 0 rgba(var(--t-rgb), 0.06);
}

/* ─── Countdown: background glow sweep that shrinks from full-width to 0 ─── */
.toast-countdown {
  position: absolute;
  inset: 0;
  pointer-events: none;
  z-index: 0;
  background: linear-gradient(
    90deg,
    rgba(var(--t-rgb), 0.10) 0%,
    rgba(var(--t-rgb), 0.04) 60%,
    transparent 100%
  );
  transform-origin: left center;
  animation: toast-countdown-sweep linear forwards;
}
@keyframes toast-countdown-sweep {
  from { clip-path: inset(0 0 0 0); }
  to   { clip-path: inset(0 100% 0 0); }
}

/* ─── Icon wrapper ─── */
.toast-icon-wrap {
  width: 28px;
  height: 28px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  background: rgba(var(--t-rgb), 0.12);
}

/* ─── Action button ─── */
.toast-action {
  font-size: 13px;
  font-weight: 600;
  padding: 4px 12px;
  border-radius: 8px;
  color: rgba(var(--t-rgb), 1);
  background: rgba(var(--t-rgb), 0.1);
  transition: background 0.15s;
}
.toast-action:hover {
  background: rgba(var(--t-rgb), 0.2);
}

/* ─── Desktop transitions ─── */
.toast-desktop-enter-active { transition: all 0.35s cubic-bezier(0.16, 1, 0.3, 1); }
.toast-desktop-leave-active { transition: all 0.25s ease-in; }
.toast-desktop-enter-from { opacity: 0; transform: translateX(80px) scale(0.95); }
.toast-desktop-leave-to { opacity: 0; transform: translateX(60px) scale(0.97); }
.toast-desktop-move { transition: transform 0.3s cubic-bezier(0.16, 1, 0.3, 1); }

/* ─── Mobile transitions ─── */
.toast-mobile-enter-active { transition: all 0.35s cubic-bezier(0.16, 1, 0.3, 1); }
.toast-mobile-leave-active { transition: all 0.25s ease-in; }
.toast-mobile-enter-from { opacity: 0; transform: translateY(30px) scale(0.95); }
.toast-mobile-leave-to { opacity: 0; transform: translateY(20px) scale(0.97); }
.toast-mobile-move { transition: transform 0.3s cubic-bezier(0.16, 1, 0.3, 1); }

/* ─── Reduced motion ─── */
@media (prefers-reduced-motion: reduce) {
  .toast-desktop-enter-active, .toast-desktop-leave-active,
  .toast-mobile-enter-active, .toast-mobile-leave-active,
  .toast-desktop-move, .toast-mobile-move {
    transition-duration: 0.1s !important;
  }
  .toast-countdown { animation: none !important; }
}
</style>

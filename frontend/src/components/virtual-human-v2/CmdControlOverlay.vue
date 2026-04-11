<script setup lang="ts">
/**
 * CmdControlOverlay — 控制面板
 *
 * 桌面: 全屏毛玻璃 Overlay，居中 max-w-3xl 卡片
 * 移动: 底部 Sheet，max-height 85vh，slide-up 动画
 */
import { X } from 'lucide-vue-next'
import ControlPanel from '@/components/virtual-human/ControlPanel.vue'
import { nextZIndex } from '@/constants/zIndex'
import { ref, watch } from 'vue'

const props = defineProps<{ open: boolean }>()
const emit = defineEmits<{ (e: 'update:open', v: boolean): void }>()

const zIdx = ref(0)

watch(() => props.open, (v) => {
  if (v) zIdx.value = nextZIndex()
})

function close() { emit('update:open', false) }
</script>

<template>
  <Teleport to="body">
    <Transition name="ctrl-overlay">
      <div v-if="open" class="fixed inset-0" :style="{ zIndex: zIdx }" @click.self="close">
        <!-- Backdrop -->
        <div class="absolute inset-0 bg-black/60 backdrop-blur-[40px]"
             style="-webkit-backdrop-filter: blur(40px)" @click="close" />

        <!-- Desktop: centered card -->
        <div class="ctrl-content cmd-desktop-only">
          <div class="ctrl-card ctrl-card--desktop overflow-y-auto">
            <div class="flex items-center justify-between px-6 pt-5 pb-3 sticky top-0 z-10"
                 style="background: var(--cmd-glass-strong-bg);
                        backdrop-filter: blur(20px);
                        -webkit-backdrop-filter: blur(20px)">
              <h2 class="text-base font-bold tracking-[-0.02em] text-white/90"
                  style="font-family: var(--cmd-font-display)">
                控制面板
              </h2>
              <button class="w-8 h-8 flex items-center justify-center rounded-full
                             bg-white/[0.08] hover:bg-white/[0.15] transition-colors"
                      @click="close">
                <X :size="16" class="text-white/60" />
              </button>
            </div>
            <div class="px-6 pb-6">
              <ControlPanel />
            </div>
          </div>
        </div>

        <!-- Mobile: bottom sheet -->
        <div class="ctrl-sheet cmd-mobile-only">
          <!-- Handle -->
          <div class="flex justify-center pt-2 pb-1" @click="close">
            <div class="w-9 h-1 rounded-full bg-white/25" />
          </div>
          <div class="flex items-center justify-between px-4 pb-2">
            <h2 class="text-[14px] font-bold text-white/85"
                style="font-family: var(--cmd-font-display)">
              控制面板
            </h2>
            <button class="w-7 h-7 flex items-center justify-center rounded-full
                           bg-white/[0.08] active:bg-white/[0.15]"
                    @click="close">
              <X :size="14" class="text-white/60" />
            </button>
          </div>
          <div class="px-3 pb-4 overflow-y-auto" style="max-height: calc(85vh - 60px)">
            <ControlPanel />
          </div>
          <div class="h-[env(safe-area-inset-bottom,0px)]" />
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style>
/* Desktop card */
.ctrl-content {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}
.ctrl-card--desktop {
  position: relative;
  z-index: 10;
  width: 100%;
  max-width: 48rem;
  max-height: 85vh;
  margin: 0 1rem;
  border-radius: 1.5rem;
  background: var(--cmd-glass-strong-bg);
  backdrop-filter: var(--cmd-glass-strong-blur);
  -webkit-backdrop-filter: var(--cmd-glass-strong-blur);
  border: 1px solid var(--cmd-glass-strong-border);
  box-shadow: 0 24px 80px rgba(0,0,0,0.6);
  animation: cmd-overlay-content-in 0.4s cubic-bezier(0.16, 1, 0.3, 1) forwards;
}

/* Mobile bottom sheet */
.ctrl-sheet {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  max-height: 85vh;
  background: rgba(20, 20, 28, 0.92);
  backdrop-filter: blur(40px) saturate(1.8);
  -webkit-backdrop-filter: blur(40px) saturate(1.8);
  border-top: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 20px 20px 0 0;
  box-shadow: 0 -12px 40px rgba(0, 0, 0, 0.4);
  animation: ctrl-sheet-in 0.35s cubic-bezier(0.16, 1, 0.3, 1) forwards;
}

@keyframes ctrl-sheet-in {
  from { transform: translateY(100%); opacity: 0; }
  to   { transform: translateY(0);    opacity: 1; }
}

/* Transition */
.ctrl-overlay-enter-active { transition: opacity 0.3s ease; }
.ctrl-overlay-leave-active { transition: opacity 0.2s ease; }
.ctrl-overlay-enter-from, .ctrl-overlay-leave-to { opacity: 0; }
</style>

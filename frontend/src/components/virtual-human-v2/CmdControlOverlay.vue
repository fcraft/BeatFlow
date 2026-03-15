<script setup lang="ts">
/**
 * CmdControlOverlay — 全屏毛玻璃 Overlay 控制面板
 * 打开后全屏覆盖，内嵌 ControlPanel 组件
 */
import { X } from 'lucide-vue-next'
import ControlPanel from '@/components/virtual-human/ControlPanel.vue'

defineProps<{ open: boolean }>()
const emit = defineEmits<{ (e: 'update:open', v: boolean): void }>()

function close() { emit('update:open', false) }
</script>

<template>
  <Teleport to="body">
    <Transition name="overlay">
      <div v-if="open" class="fixed inset-0 z-50 flex items-center justify-center"
           @click.self="close">
        <!-- Backdrop -->
        <div class="absolute inset-0 bg-black/60 backdrop-blur-[40px]"
             style="-webkit-backdrop-filter: blur(40px)" />

        <!-- Content -->
        <div class="relative z-10 w-full max-w-3xl max-h-[85vh] mx-4
                    overflow-y-auto rounded-3xl"
             style="background: var(--cmd-glass-strong-bg);
                    backdrop-filter: var(--cmd-glass-strong-blur);
                    -webkit-backdrop-filter: var(--cmd-glass-strong-blur);
                    border: 1px solid var(--cmd-glass-strong-border);
                    box-shadow: 0 24px 80px rgba(0,0,0,0.6);
                    animation: cmd-overlay-content-in 0.4s cubic-bezier(0.16, 1, 0.3, 1) forwards">
          <!-- Header -->
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

          <!-- Control panel content -->
          <div class="px-6 pb-6">
            <ControlPanel />
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style>
.overlay-enter-active { transition: opacity 0.3s ease; }
.overlay-leave-active { transition: opacity 0.2s ease; }
.overlay-enter-from, .overlay-leave-to { opacity: 0; }
</style>

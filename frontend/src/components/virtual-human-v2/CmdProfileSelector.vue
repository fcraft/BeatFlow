<script setup lang="ts">
/**
 * CmdProfileSelector — 未连接态全屏居中玻璃卡片
 */
import { onMounted } from 'vue'
import { Plus, Zap, User } from 'lucide-vue-next'
import { useVirtualHumanStore } from '@/store/virtualHuman'
import { useToastStore } from '@/store/toast'

const store = useVirtualHumanStore()
const toast = useToastStore()

onMounted(() => { store.fetchProfiles() })

async function handleCreate() {
  const name = prompt('输入档案名称')
  if (!name) return
  const id = await store.createProfile(name)
  if (id) store.connect(id)
}

function connectAnonymous() {
  store.connect(null)
}
</script>

<template>
  <div class="flex-1 flex items-center justify-center relative overflow-hidden">
    <!-- Ambient glow -->
    <div class="absolute w-[500px] h-[500px] rounded-full opacity-20 pointer-events-none"
         style="background: radial-gradient(circle, rgba(0,122,255,0.15) 0%, transparent 70%);
                top: 50%; left: 50%; transform: translate(-50%, -50%);
                animation: cmd-glass-reveal 2s ease-out" />

    <!-- Main card -->
    <div class="w-full max-w-md cmd-glass-reveal relative z-10"
         style="background: var(--cmd-glass-strong-bg);
                backdrop-filter: var(--cmd-glass-strong-blur);
                -webkit-backdrop-filter: var(--cmd-glass-strong-blur);
                border: 1px solid var(--cmd-glass-strong-border);
                border-radius: 20px;
                box-shadow: 0 12px 40px rgba(0,0,0,0.4);">
      <div class="p-6">
        <h2 class="text-lg font-bold tracking-[-0.02em] text-white/90 mb-1"
            style="font-family: var(--cmd-font-display)">
          选择患者档案
        </h2>
        <p class="text-xs text-white/35 mb-5">连接到档案以启动实时仿真监护</p>

        <!-- Profiles list -->
        <div v-if="store.loadingProfiles" class="py-8 text-center text-white/30 text-sm">加载中...</div>
        <div v-else class="flex flex-col gap-2 max-h-[280px] overflow-y-auto pr-1">
          <button v-for="p in store.profiles" :key="p.id"
                  class="group flex items-center gap-3 px-4 py-3 rounded-2xl text-left
                         border border-white/[0.06] bg-white/[0.03]
                         hover:border-[#007AFF]/30 hover:bg-[#007AFF]/[0.06]
                         transition-all duration-300"
                  style="transition-timing-function: var(--cmd-ease-spring)"
                  @click="store.connect(p.id)">
            <div class="w-9 h-9 rounded-xl flex items-center justify-center
                        bg-white/[0.06] group-hover:bg-[#007AFF]/15 transition-colors duration-300">
              <User :size="16" class="text-white/40 group-hover:text-[#007AFF] transition-colors" />
            </div>
            <div class="flex-1 min-w-0">
              <div class="text-sm font-medium text-white/80 truncate">{{ p.name }}</div>
              <div class="text-[10px] text-white/30 mt-0.5 tabular-nums" style="font-family: var(--cmd-font-mono)">
                {{ p.heart_rate ? `${p.heart_rate} bpm` : '—' }}
                <span v-if="p.rhythm" class="ml-2">{{ p.rhythm }}</span>
              </div>
            </div>
            <div class="w-1 h-6 rounded-full bg-[#007AFF] opacity-0 group-hover:opacity-100
                        transition-opacity duration-300" />
          </button>
        </div>

        <!-- Actions -->
        <div class="flex items-center gap-3 mt-5 pt-4 border-t border-white/[0.06]">
          <button class="flex-1 h-10 flex items-center justify-center gap-2
                         text-sm font-semibold text-white bg-[#007AFF] rounded-full
                         shadow-[0_4px_16px_rgba(0,122,255,0.3)]
                         hover:shadow-[0_4px_20px_rgba(0,122,255,0.4)]
                         hover:-translate-y-px transition-all duration-200"
                  style="border-radius: 980px; transition-timing-function: var(--cmd-ease-spring)"
                  @click="handleCreate">
            <Plus :size="15" />
            新建档案
          </button>
          <button class="h-10 px-5 text-sm font-medium text-white/50 border border-white/10 rounded-full
                         hover:bg-white/[0.05] hover:text-white/70 transition-all duration-200"
                  style="border-radius: 980px"
                  @click="connectAnonymous">
            <Zap :size="13" class="inline mr-1" />匿名
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

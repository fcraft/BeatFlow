<script setup lang="ts">
/**
 * Virtual Human V2 — Command Center 指挥中心式布局
 *
 * 桌面布局:
 *   StatusBar (40px)
 *   MainContent: 左 WaveflowPanel | 右 VitalsSidebar (200px)
 *   TimelineTrack (36px)
 *
 * 移动端布局 (< 768px):
 *   StatusBar (44px, 精简)
 *   WaveflowPanel (全宽, 波形限高)
 *   MobileVitalsBar (底部水平滚动条)
 *   控制面板 → 底部 Sheet
 */
import { ref, onMounted, onUnmounted, onBeforeUnmount, reactive, toRef } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { LogOut } from 'lucide-vue-next'
import { useVirtualHumanStore } from '@/store/virtualHuman'
import { useConnectionStore } from '@/store/connection'
import { useAuthStore } from '@/store/auth'
import { useToastStore } from '@/store/toast'
import { useNotificationStore } from '@/store/notification'
import { useNavItems } from '@/composables/useNavItems'
import { useAlarmSystem } from '@/composables/useAlarmSystem'

import '@/components/virtual-human-v2/cmd-tokens.css'

import CmdStatusBar from '@/components/virtual-human-v2/CmdStatusBar.vue'
import CmdProfileSelector from '@/components/virtual-human-v2/CmdProfileSelector.vue'
import CmdWaveflowPanel from '@/components/virtual-human-v2/CmdWaveflowPanel.vue'
import CmdVitalsSidebar from '@/components/virtual-human-v2/CmdVitalsSidebar.vue'
import CmdTimelineTrack from '@/components/virtual-human-v2/CmdTimelineTrack.vue'
import CmdControlOverlay from '@/components/virtual-human-v2/CmdControlOverlay.vue'
import CmdMobileVitals from '@/components/virtual-human-v2/CmdMobileVitals.vue'
import PvLoopChart from '@/components/virtual-human/PvLoopChart.vue'
import ActionPotentialChart from '@/components/virtual-human/ActionPotentialChart.vue'
import CardiacCycleChart from '@/components/virtual-human/CardiacCycleChart.vue'

const store = useVirtualHumanStore()
const connectionStore = useConnectionStore()
const authStore = useAuthStore()
const toast = useToastStore()
const notificationStore = useNotificationStore()
const router = useRouter()
const route = useRoute()
const { navItems } = useNavItems()
const alarmSystem = useAlarmSystem(store.vitals, { muted: toRef(store, 'alarmMuted') })

const showControlOverlay = ref(false)
const showPvLoop = ref(false)
const showApChart = ref(false)
const showCcChart = ref(false)

// Nav menu
const showNavMenu = ref(false)
const navTriggerRef = ref<HTMLElement | null>(null)
const navDropdownRef = ref<HTMLElement | null>(null)
const navMenuPos = reactive({ top: 0, left: 0 })

function toggleNavMenu() {
  showNavMenu.value = !showNavMenu.value
  if (showNavMenu.value && navTriggerRef.value) {
    const rect = navTriggerRef.value.getBoundingClientRect()
    navMenuPos.top = rect.bottom + 8
    navMenuPos.left = rect.left
  }
}

function navigateTo(to: string) { showNavMenu.value = false; router.push(to) }
function logout() {
  showNavMenu.value = false
  store.disconnect()
  authStore.logout()
  toast.success('已退出登录')
  router.push('/login')
}

function onClickOutsideNav(e: MouseEvent) {
  const target = e.target as Node
  if (navTriggerRef.value?.contains(target)) return
  if (navDropdownRef.value?.contains(target)) return
  showNavMenu.value = false
}

onMounted(() => {
  notificationStore.fetchUnreadCount()
  document.addEventListener('mousedown', onClickOutsideNav)
})

onBeforeUnmount(() => {
  document.removeEventListener('mousedown', onClickOutsideNav)
})

onUnmounted(() => {
  alarmSystem.dispose()
  store.disconnect()
})
</script>

<template>
  <div class="h-screen w-screen flex flex-col overflow-hidden select-none relative"
       style="background: var(--cmd-bg-gradient); color: var(--cmd-text-primary);
              font-family: var(--cmd-font-body)">

    <!-- Background ambient glow (hidden on mobile for perf) -->
    <div class="vhv2-glow vhv2-glow--1 cmd-desktop-only" />
    <div class="vhv2-glow vhv2-glow--2 cmd-desktop-only" />

    <!-- Status Bar -->
    <CmdStatusBar @open-nav="toggleNavMenu" />

    <!-- Main Content -->
    <div class="flex-1 flex min-h-0">
      <!-- LEFT: Waveform flow -->
      <div class="flex-1 min-w-0 flex flex-col h-full">
        <CmdProfileSelector v-if="!store.connected && !store.connecting" />
        <div v-else-if="store.connecting" class="flex-1 flex items-center justify-center h-full">
          <div class="text-white/30 text-sm">连接中...</div>
        </div>
        <CmdWaveflowPanel v-else
          :alarms="alarmSystem.activeAlarms.value"
          :show-pv="showPvLoop" :show-ap="showApChart" :show-wiggers="showCcChart"
          @toggle-pv="showPvLoop = !showPvLoop"
          @toggle-ap="showApChart = !showApChart"
          @toggle-wiggers="showCcChart = !showCcChart"
          @open-controls="showControlOverlay = true" />
      </div>

      <!-- RIGHT: Vitals sidebar — desktop only -->
      <CmdVitalsSidebar v-if="store.connected" class="cmd-desktop-only"
        @open-controls="showControlOverlay = true" />
    </div>

    <!-- Mobile vitals bar — mobile only, replaces sidebar -->
    <CmdMobileVitals v-if="store.connected" class="cmd-mobile-only"
      @open-controls="showControlOverlay = true" />

    <!-- Timeline Track (desktop only) -->
    <CmdTimelineTrack class="cmd-desktop-only" />

    <!-- Control Overlay -->
    <CmdControlOverlay v-model:open="showControlOverlay" />

    <!-- Floating physiology panels (desktop only) -->
    <PvLoopChart v-if="showPvLoop" class="cmd-desktop-only" @close="showPvLoop = false" />
    <ActionPotentialChart v-if="showApChart" class="cmd-desktop-only" @close="showApChart = false" />
    <CardiacCycleChart v-if="showCcChart" class="cmd-desktop-only" @close="showCcChart = false" />

    <!-- Navigation Menu (Teleport) -->
    <Teleport to="body">
      <Transition name="nav-menu">
        <div v-if="showNavMenu" ref="navDropdownRef"
             class="fixed w-56 py-2 z-[9999] rounded-2xl shadow-2xl ring-1 ring-black/30"
             :style="{ top: navMenuPos.top + 'px', left: navMenuPos.left + 'px',
                       background: 'var(--cmd-glass-strong-bg)',
                       backdropFilter: 'var(--cmd-glass-strong-blur)',
                       WebkitBackdropFilter: 'var(--cmd-glass-strong-blur)',
                       border: '1px solid var(--cmd-glass-strong-border)' }">
          <button v-for="item in navItems" :key="item.to"
                  class="w-full flex items-center gap-3 px-4 py-2.5 text-sm transition-colors"
                  :class="route.path === item.to
                    ? 'text-[#007AFF] bg-[#007AFF]/10'
                    : 'text-white/60 hover:bg-white/[0.08] hover:text-white'"
                  @click="navigateTo(item.to)">
            <component :is="item.icon" :size="16" class="shrink-0" />
            <span class="flex-1 text-left">{{ item.label }}</span>
            <span v-if="item.badge && item.badge > 0"
                  class="min-w-[18px] h-4.5 px-1 bg-[#FF3B30] text-white text-[10px] font-bold rounded-full flex items-center justify-center">
              {{ item.badge > 99 ? '99+' : item.badge }}
            </span>
          </button>
          <div class="border-t border-white/[0.06] mt-1 pt-1">
            <button class="w-full flex items-center gap-3 px-4 py-2.5 text-sm text-white/40
                           hover:bg-white/[0.08] hover:text-[#FF3B30] transition-colors"
                    @click="logout">
              <LogOut :size="16" class="shrink-0" />
              <span class="text-left">退出登录</span>
            </button>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<style>
.nav-menu-enter-active, .nav-menu-leave-active {
  transition: opacity 0.15s ease, transform 0.15s ease;
}
.nav-menu-enter-from, .nav-menu-leave-to {
  opacity: 0; transform: translateY(-4px) scale(0.95);
}

/* ─── Background ambient glow ─── */
.vhv2-glow {
  position: absolute;
  border-radius: 50%;
  pointer-events: none;
  z-index: 1;
  mix-blend-mode: screen;
}
.vhv2-glow--1 {
  width: 700px;
  height: 700px;
  background: radial-gradient(circle, rgba(0, 122, 255, 0.18) 0%, rgba(0, 122, 255, 0.04) 40%, transparent 70%);
  top: -20%;
  left: -10%;
  animation: vhv2-wander-1 45s ease-in-out infinite;
}
.vhv2-glow--2 {
  width: 600px;
  height: 600px;
  background: radial-gradient(circle, rgba(175, 82, 222, 0.12) 0%, rgba(175, 82, 222, 0.03) 40%, transparent 70%);
  bottom: -15%;
  right: -10%;
  animation: vhv2-wander-2 55s ease-in-out infinite;
}

@keyframes vhv2-wander-1 {
  0%   { transform: translate(0, 0) scale(1); }
  10%  { transform: translate(30vw, 15vh) scale(1.05); }
  20%  { transform: translate(55vw, -5vh) scale(0.9); }
  30%  { transform: translate(70vw, 30vh) scale(1.1); }
  40%  { transform: translate(45vw, 55vh) scale(0.95); }
  50%  { transform: translate(15vw, 65vh) scale(1.08); }
  60%  { transform: translate(-5vw, 40vh) scale(0.92); }
  70%  { transform: translate(10vw, 10vh) scale(1.12); }
  80%  { transform: translate(50vw, 20vh) scale(0.97); }
  90%  { transform: translate(25vw, -10vh) scale(1.03); }
  100% { transform: translate(0, 0) scale(1); }
}

@keyframes vhv2-wander-2 {
  0%   { transform: translate(0, 0) scale(1); }
  12%  { transform: translate(-25vw, -20vh) scale(1.06); }
  25%  { transform: translate(-50vw, 10vh) scale(0.93); }
  37%  { transform: translate(-35vw, -40vh) scale(1.1); }
  50%  { transform: translate(-10vw, -55vh) scale(0.88); }
  62%  { transform: translate(10vw, -30vh) scale(1.05); }
  75%  { transform: translate(-20vw, -10vh) scale(0.95); }
  87%  { transform: translate(-40vw, -45vh) scale(1.08); }
  100% { transform: translate(0, 0) scale(1); }
}

@media (prefers-reduced-motion: reduce) {
  .vhv2-glow { animation: none !important; }
}
</style>

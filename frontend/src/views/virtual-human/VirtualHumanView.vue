<script setup lang="ts">
/**
 * 虚拟人体模型 — 主页面（一屏布局）
 *
 * 布局结构:
 *   TopBar: 合并的单行顶栏（标题+连接+simTime+操作按钮+协议版本）
 *   WaveformArea: ECG + PCG 波形占满剩余空间
 *   VitalsBar: 底部常驻薄条（HR/BP/SpO2/Temp/RR/CO）+ 可展开详情
 *   ControlDrawer: 底部弹出毛玻璃抽屉（7个控制Tab）
 */
import { computed, ref, reactive, onUnmounted, onMounted, onBeforeUnmount, toRef, nextTick } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { Save, BarChart3, Eye, EyeOff, Volume2, VolumeX, Menu, LogOut } from 'lucide-vue-next'
import { useVirtualHumanStore } from '@/store/virtualHuman'
import { useConnectionStore } from '@/store/connection'
import { useAuthStore } from '@/store/auth'
import { useToastStore } from '@/store/toast'
import { useNotificationStore } from '@/store/notification'
import { useNavItems } from '@/composables/useNavItems'
import { exportCanvasAsPng } from '@/composables/useRhythmStripExport'
import { useAlarmSystem } from '@/composables/useAlarmSystem'

import MonitorShell from '@/components/virtual-human/MonitorShell.vue'
import EcgWaveform from '@/components/virtual-human/EcgWaveform.vue'
import EcgLeadSelector from '@/components/virtual-human/EcgLeadSelector.vue'
import EcgMultiLeadDisplay from '@/components/virtual-human/EcgMultiLeadDisplay.vue'
import PcgWaveform from '@/components/virtual-human/PcgWaveform.vue'
import SyncRuler from '@/components/virtual-human/SyncRuler.vue'
import ConductionTrendChart from '@/components/virtual-human/ConductionTrendChart.vue'
import ConnectionStatus from '@/components/virtual-human/ConnectionStatus.vue'
import ProfileSelector from '@/components/virtual-human/ProfileSelector.vue'
import RecordingPanel from '@/components/virtual-human/RecordingPanel.vue'
import ActiveEffectsBar from '@/components/virtual-human/ActiveEffectsBar.vue'
import AlarmBanner from '@/components/virtual-human/AlarmBanner.vue'
import VitalsBar from '@/components/virtual-human/VitalsBar.vue'
import ControlDrawer from '@/components/virtual-human/ControlDrawer.vue'
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

const showControlDrawer = ref(false)
const showVitalsDetail = ref(false)
const ecgWaveformRef = ref<any>(null)

/** P1: Floating panel toggles */
const showPvLoop = ref(false)
const showApChart = ref(false)
const showCcChart = ref(false)

/* ── 侧边导航菜单（Teleport 到 body，避免 stacking context 遮挡） ── */
const showNavMenu = ref(false)
const navTriggerRef = ref<HTMLElement | null>(null)
const navDropdownRef = ref<HTMLElement | null>(null)

/** 浮层定位：基于触发按钮的位置动态计算 */
const navMenuPos = reactive({ top: 0, left: 0 })

function updateNavMenuPos() {
  if (!navTriggerRef.value) return
  const rect = navTriggerRef.value.getBoundingClientRect()
  navMenuPos.top = rect.bottom + 8 // mt-2 = 8px
  navMenuPos.left = rect.left
}

function toggleNavMenu() {
  showNavMenu.value = !showNavMenu.value
  if (showNavMenu.value) {
    updateNavMenuPos()
  }
}

function navigateTo(to: string) {
  showNavMenu.value = false
  router.push(to)
}

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

function handleExport() {
  const waveformEl = ecgWaveformRef.value?.$el
  if (!waveformEl) return
  const canvas = waveformEl.querySelector('canvas')
  if (!canvas) return
  exportCanvasAsPng(canvas, store.vitals, store.selectedLeads[0] || 'II')
}

function formatTime(sec: number): string {
  const m = Math.floor(sec / 60)
  const s = Math.floor(sec % 60)
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}

/** 格式化后端启动时间为本地时分秒 */
function formatStartedAt(iso: string | null): string {
  if (!iso) return ''
  const d = new Date(iso)
  return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

/**
 * 缓存最后有效的标注数据。
 * store.beatAnnotations 每 100ms 清空再填充，直接绑定会导致 v-if 高频切换引起布局抖动。
 * 此 computed 仅在有新数据时更新，空数组时保留上次值。
 */
let _lastAnnotation: any = null
const cachedAnnotation = computed(() => {
  const arr = store.beatAnnotations
  if (arr && arr.length > 0) {
    _lastAnnotation = arr[arr.length - 1]
  }
  return _lastAnnotation
})

onUnmounted(() => {
  alarmSystem.dispose()
  store.disconnect()
})
</script>

<template>
  <MonitorShell>
    <!-- 合并后的单行顶栏 -->
    <template #topbar>
      <div class="flex items-center justify-between px-4 py-2 backdrop-blur-xl bg-white/[0.06] border border-white/[0.08] rounded-xl shrink-0">
        <div class="flex items-center gap-3">
          <!-- 导航菜单按钮 -->
          <button
            ref="navTriggerRef"
            class="p-1.5 rounded-lg hover:bg-white/10 transition-colors"
            title="导航菜单"
            @click="toggleNavMenu"
          >
            <Menu :size="18" class="text-white/60" />
          </button>

          <span class="text-lg font-semibold tracking-wide">🫀 Virtual Patient</span>
          <div
            class="w-2 h-2 rounded-full"
            :class="store.connected ? 'bg-emerald-400 animate-pulse' : 'bg-red-400'"
          />
          <span class="text-xs text-white/50">
            {{ store.connected ? formatTime(connectionStore.simTime) : '未连接' }}
          </span>
        </div>
        <div class="flex items-center gap-3">
          <span v-if="store.profileName" class="text-xs text-emerald-400 font-medium">
            {{ store.profileName }}
          </span>
          <ConnectionStatus />
          <RecordingPanel v-if="store.connected" />
          <button
            v-if="store.connected"
            class="p-1.5 rounded-lg hover:bg-white/10 transition-colors"
            :title="store.alarmMuted ? '取消静音' : '静音报警'"
            @click="store.alarmMuted = !store.alarmMuted"
          >
            <component :is="store.alarmMuted ? VolumeX : Volume2" :size="14" class="text-white/60" />
          </button>
          <button
            v-if="store.connected"
            class="p-1.5 rounded-lg hover:bg-white/10 transition-colors"
            :class="{ 'bg-sky-500/20': store.caliperMode }"
            title="卡尺测量"
            @click="store.caliperMode = !store.caliperMode"
          >
            <span class="text-sm" :class="store.caliperMode ? 'text-sky-400' : 'text-white/60'">📐</span>
          </button>
          <button
            v-if="store.connected"
            class="p-1.5 rounded-lg hover:bg-white/10 transition-colors"
            title="导出节律条"
            @click="handleExport"
          >
            <span class="text-sm text-white/60">📷</span>
          </button>
          <button
            v-if="store.connected && store.selectedProfileId"
            class="flex items-center gap-1 px-3 py-1.5 text-xs font-medium text-emerald-400 border border-emerald-500/40 rounded-lg hover:bg-emerald-500/10 transition-colors"
            @click="store.saveState()"
            title="保存当前状态"
          >
            <Save :size="13" />
            保存
          </button>
          <button
            v-if="store.connected"
            class="px-3 py-1.5 text-xs font-medium text-white/50 border border-white/20 rounded-lg hover:bg-white/10 transition-colors"
            @click="store.disconnect()"
          >
            断开
          </button>
          <span
            v-if="store.connected"
            class="text-[10px] px-2 py-0.5 rounded-full bg-white/10 text-white/50"
          >v{{ connectionStore.protocolVersion }}</span>
          <span
            v-if="store.connected && store.serverStartedAt"
            class="text-[10px] px-2 py-0.5 rounded-full bg-white/10 text-white/40"
            :title="'后端启动于 ' + store.serverStartedAt"
          >🚀 {{ formatStartedAt(store.serverStartedAt) }}</span>
        </div>
      </div>
    </template>

    <!-- 波形区域 -->
    <template #waveforms>
      <div class="h-full flex flex-col gap-2 min-h-0">
        <!-- 未连接时：档案选择器 -->
        <div v-if="!store.connected && !store.connecting" class="flex-1 flex items-start justify-center pt-6 px-2">
          <div class="w-full max-w-5xl bg-white/5 border border-white/10 rounded-xl p-6">
            <ProfileSelector />
          </div>
        </div>

        <!-- 连接中 -->
        <div v-else-if="store.connecting" class="flex-1 flex items-center justify-center">
          <div class="text-white/40 text-sm">连接中...</div>
        </div>

        <!-- 已连接：波形区域 -->
        <template v-else>
          <!-- 活动效果状态条 -->
          <div class="shrink-0">
            <ActiveEffectsBar />
          </div>

          <!-- 报警横幅 -->
          <AlarmBanner :alarms="alarmSystem.activeAlarms.value" class="shrink-0" />

          <!-- 波形工具栏 -->
          <div class="flex items-center gap-2 shrink-0 flex-wrap">
            <button
              class="flex items-center gap-1 px-2 py-1 text-[10px] font-medium rounded border transition-colors"
              :class="store.showAnnotations
                ? 'text-sky-400 bg-sky-400/10 border-sky-400/30'
                : 'text-white/40 border-white/20 hover:bg-white/5'"
              @click="store.toggleAnnotations()"
              title="显示/隐藏 ECG 标注"
            >
              <Eye v-if="store.showAnnotations" :size="12" />
              <EyeOff v-else :size="12" />
              标注
            </button>
            <button
              class="flex items-center gap-1 px-2 py-1 text-[10px] font-medium rounded border transition-colors"
              :class="store.showTrendChart
                ? 'text-purple-400 bg-purple-400/10 border-purple-400/30'
                : 'text-white/40 border-white/20 hover:bg-white/5'"
              @click="store.toggleTrendChart()"
              title="显示/隐藏趋势图"
            >
              <BarChart3 :size="12" />
              趋势
            </button>
            <!-- 导联选择器 -->
            <EcgLeadSelector class="ml-1" />
            <!-- P1: Physiology viz toggles -->
            <div class="flex items-center gap-1 ml-auto">
              <button
                class="px-2 py-1 text-[10px] font-medium rounded border transition-colors"
                :class="showPvLoop
                  ? 'text-sky-400 bg-sky-400/10 border-sky-400/30'
                  : 'text-white/40 border-white/20 hover:bg-white/5'"
                @click="showPvLoop = !showPvLoop"
                title="P-V Loop"
              >
                PV
              </button>
              <button
                class="px-2 py-1 text-[10px] font-medium rounded border transition-colors"
                :class="showApChart
                  ? 'text-red-400 bg-red-400/10 border-red-400/30'
                  : 'text-white/40 border-white/20 hover:bg-white/5'"
                @click="showApChart = !showApChart"
                title="Action Potentials"
              >
                AP
              </button>
              <button
                class="px-2 py-1 text-[10px] font-medium rounded border transition-colors"
                :class="showCcChart
                  ? 'text-emerald-400 bg-emerald-400/10 border-emerald-400/30'
                  : 'text-white/40 border-white/20 hover:bg-white/5'"
                @click="showCcChart = !showCcChart"
                title="Wiggers Diagram"
              >
                Wiggers
              </button>
            </div>
          </div>

          <!-- ECG 波形区域：单导联 vs 多导联 -->
          <div class="flex-1 min-h-0">
            <EcgWaveform v-if="!store.multiLeadMode" ref="ecgWaveformRef" />
            <EcgMultiLeadDisplay v-else />
          </div>

          <!-- ECG 标注信息条 -->
          <div
            v-show="store.showAnnotations && cachedAnnotation"
            class="shrink-0 flex items-center gap-3 px-2 py-1 bg-black/40 rounded text-[10px]"
          >
            <span class="text-sky-400">
              P: {{ cachedAnnotation?.p_start != null ? 'present' : '—' }}
            </span>
            <span class="text-red-400">
              QRS: {{ cachedAnnotation?.qrs_ms ?? '—' }}ms
            </span>
            <span class="text-purple-400">
              QT: {{ cachedAnnotation?.qt_ms ?? '—' }}ms
            </span>
            <span class="text-green-400">
              PR: {{ cachedAnnotation?.pr_ms ?? '—' }}ms
            </span>
          </div>

          <SyncRuler />

          <div class="flex-1 min-h-0">
            <PcgWaveform />
          </div>

          <!-- 趋势图（可折叠） -->
          <div v-if="store.showTrendChart" class="shrink-0">
            <ConductionTrendChart />
          </div>
        </template>
      </div>
    </template>

    <!-- 底部生命体征薄条 -->
    <template #bottom>
      <VitalsBar
        v-if="store.connected"
        v-model:expanded="showVitalsDetail"
        :get-alarm-level="alarmSystem.getAlarmLevel"
        @open-controls="showControlDrawer = true"
      />
    </template>
  </MonitorShell>

  <!-- 导航菜单浮层 — Teleport 到 body，规避 glass-panel stacking context 遮挡 -->
  <Teleport to="body">
    <Transition name="nav-menu">
      <div
        v-if="showNavMenu"
        ref="navDropdownRef"
        class="fixed w-56 py-2 bg-gray-950/60 backdrop-blur-2xl backdrop-saturate-[1.8] border border-white/[0.15] rounded-xl shadow-2xl ring-1 ring-black/30 z-[9999]"
        :style="{ top: navMenuPos.top + 'px', left: navMenuPos.left + 'px' }"
      >
        <button
          v-for="item in navItems"
          :key="item.to"
          class="w-full flex items-center gap-3 px-4 py-2.5 text-sm transition-colors"
          :class="route.path === item.to
            ? 'text-sky-400 bg-sky-400/10'
            : 'text-white/70 hover:bg-white/10 hover:text-white'"
          @click="navigateTo(item.to)"
        >
          <component :is="item.icon" :size="16" class="shrink-0" />
          <span class="flex-1 text-left">{{ item.label }}</span>
          <span
            v-if="item.badge && item.badge > 0"
            class="min-w-[18px] h-4.5 px-1 bg-red-500 text-white text-[10px] font-bold rounded-full flex items-center justify-center leading-none"
          >{{ item.badge > 99 ? '99+' : item.badge }}</span>
        </button>
        <div class="border-t border-white/10 mt-1 pt-1">
          <button
            class="w-full flex items-center gap-3 px-4 py-2.5 text-sm text-white/50 hover:bg-white/10 hover:text-red-400 transition-colors"
            @click="logout"
          >
            <LogOut :size="16" class="shrink-0" />
            <span class="text-left">退出登录</span>
          </button>
        </div>
      </div>
    </Transition>
  </Teleport>

  <!-- 控制面板抽屉 -->
  <ControlDrawer v-model:open="showControlDrawer" />

  <!-- P1: Floating physiology panels -->
  <PvLoopChart v-if="showPvLoop" @close="showPvLoop = false" />
  <ActionPotentialChart v-if="showApChart" @close="showApChart = false" />
  <CardiacCycleChart v-if="showCcChart" @close="showCcChart = false" />
</template>

<style>
/* 非 scoped：Teleport 到 body 的导航菜单过渡需要全局样式 */
.nav-menu-enter-active,
.nav-menu-leave-active {
  transition: opacity 0.15s ease, transform 0.15s ease;
}
.nav-menu-enter-from,
.nav-menu-leave-to {
  opacity: 0;
  transform: translateY(-4px) scale(0.95);
}
</style>

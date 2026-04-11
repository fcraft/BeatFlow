<script setup lang="ts">
/**
 * CmdProfileSelector — 未连接态全屏档案选择器
 *
 * 卡片式布局，展示档案摘要生命体征，支持新建、进入、删除。
 */
import { ref, nextTick, onMounted, computed } from 'vue'
import { Plus, Zap, User, X, Heart, Droplets, Activity, Trash2, Clock } from 'lucide-vue-next'
import { useVirtualHumanStore, type ProfileItem } from '@/store/virtualHuman'
import { useToastStore } from '@/store/toast'

const store = useVirtualHumanStore()
const toast = useToastStore()

onMounted(() => { store.fetchProfiles() })

// ─── 新建档案 ───
const creating = ref(false)
const newName = ref('')
const nameInputRef = ref<HTMLInputElement | null>(null)
const createLoading = ref(false)

function startCreate() {
  creating.value = true
  newName.value = ''
  nextTick(() => nameInputRef.value?.focus())
}

function cancelCreate() {
  creating.value = false
  newName.value = ''
}

async function confirmCreate() {
  const name = newName.value.trim()
  if (!name) return
  createLoading.value = true
  const id = await store.createProfile(name)
  createLoading.value = false
  if (id) {
    creating.value = false
    newName.value = ''
    store.connect(id)
  }
}

// ─── 删除档案 ───
const deletingId = ref<string | null>(null)

async function handleDelete(p: ProfileItem, e: Event) {
  e.stopPropagation()
  if (deletingId.value === p.id) {
    await store.deleteProfile(p.id)
    deletingId.value = null
  } else {
    deletingId.value = p.id
    setTimeout(() => { if (deletingId.value === p.id) deletingId.value = null }, 3000)
  }
}

// ─── 节律中文映射 ───
const rhythmLabel: Record<string, string> = {
  normal: '窦性',
  af: '房颤',
  pvc: '早搏',
  svt: 'SVT',
  vt: 'VT',
}

function formatRhythm(r: string | null): string {
  if (!r) return '—'
  return rhythmLabel[r] || r
}

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return '刚刚'
  if (mins < 60) return `${mins} 分钟前`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours} 小时前`
  const days = Math.floor(hours / 24)
  if (days < 30) return `${days} 天前`
  return new Date(iso).toLocaleDateString('zh-CN')
}

const hasProfiles = computed(() => store.profiles.length > 0)
</script>

<template>
  <!-- Mobile: full-height flex column; Desktop: centered card -->
  <div class="flex-1 flex flex-col md:items-center md:justify-center relative overflow-hidden px-2 py-2 md:p-4">
    <!-- Animated ambient glow orbs -->
    <div class="glow-orb glow-orb--primary cmd-desktop-only" />
    <div class="glow-orb glow-orb--accent cmd-desktop-only" />
    <div class="glow-orb glow-orb--teal cmd-desktop-only" />

    <!-- Main container: mobile=flex-col fill, desktop=auto-height card -->
    <div class="w-full max-w-2xl cmd-glass-reveal relative z-10 flex flex-col min-h-0 md:block md:max-h-[85vh]">

      <!-- Header (fixed) -->
      <div class="shrink-0 mb-3 md:mb-6 px-1 md:px-0">
        <h2 class="text-lg md:text-2xl font-bold tracking-[-0.02em] text-white/90"
            style="font-family: var(--cmd-font-display)">
          患者档案
        </h2>
        <p class="text-xs md:text-sm text-white/35 mt-0.5 md:mt-1">选择一个档案连接以启动实时仿真监护</p>
      </div>

      <!-- Profiles list (scrollable, fills remaining space) -->
      <div v-if="store.loadingProfiles" class="flex-1 flex items-center justify-center text-white/30 text-sm">加载中...</div>

      <div v-else-if="hasProfiles"
           class="flex-1 min-h-0 overflow-y-auto pr-0.5 md:pr-1 profile-scroll md:max-h-[50vh]">
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-2 md:gap-3">
          <button
            v-for="p in store.profiles" :key="p.id"
            class="profile-card group relative text-left overflow-hidden
                   border transition-all duration-300 rounded-xl md:rounded-2xl"
            :class="deletingId === p.id
              ? 'border-[#FF3B30]/20 bg-[#FF3B30]/[0.06]'
              : 'border-white/[0.06] bg-white/[0.03]'"
            style="transition-timing-function: var(--cmd-ease-spring)"
            @click="store.connect(p.id)"
          >
            <!-- Hover glow overlay -->
            <div class="card-glow" />

            <!-- Card content -->
            <div class="relative z-[1] p-3 md:p-4">
              <!-- Top row: avatar + name + actions -->
              <div class="flex items-start gap-3 mb-3">
                <div class="w-10 h-10 rounded-xl flex items-center justify-center shrink-0 transition-colors duration-300"
                     :class="p.has_snapshot
                       ? 'bg-[#007AFF]/15 text-[#007AFF]'
                       : 'bg-white/[0.06] text-white/30'">
                  <User :size="18" />
                </div>
                <div class="flex-1 min-w-0">
                  <div class="text-sm font-semibold text-white/85 truncate group-hover:text-white transition-colors">{{ p.name }}</div>
                  <div class="flex items-center gap-1.5 mt-0.5">
                    <Clock :size="10" class="text-white/25 shrink-0" />
                    <span class="text-[10px] text-white/30" style="font-family: var(--cmd-font-mono)">
                      {{ timeAgo(p.updated_at) }}
                    </span>
                  </div>
                </div>
                <!-- Delete button -->
                <button
                  class="w-7 h-7 rounded-lg flex items-center justify-center shrink-0
                         opacity-0 group-hover:opacity-100 transition-all duration-200"
                  :class="deletingId === p.id
                    ? 'bg-[#FF3B30]/20 text-[#FF3B30] !opacity-100'
                    : 'hover:bg-white/[0.08] text-white/30 hover:text-white/50'"
                  :title="deletingId === p.id ? '再次点击确认删除' : '删除档案'"
                  @click="handleDelete(p, $event)"
                >
                  <Trash2 :size="13" />
                </button>
              </div>

              <!-- Vitals summary -->
              <div v-if="p.has_snapshot" class="grid grid-cols-3 gap-2">
                <div class="vital-chip">
                  <Heart :size="11" class="text-[#FF3B30]" />
                  <span>{{ p.heart_rate ? Math.round(p.heart_rate) : '—' }}</span>
                </div>
                <div class="vital-chip">
                  <Activity :size="11" class="text-[#007AFF]" />
                  <span>{{ formatRhythm(p.rhythm) }}</span>
                </div>
                <div class="vital-chip">
                  <Droplets :size="11" class="text-[#5AC8FA]" />
                  <span>{{ p.spo2 ? Math.round(p.spo2) + '%' : '—' }}</span>
                </div>
              </div>
              <div v-else class="flex items-center gap-2 text-[10px] text-white/20">
                <div class="w-1.5 h-1.5 rounded-full bg-white/15" />
                <span>尚未运行 — 连接以初始化</span>
              </div>
            </div>

            <!-- Bottom indicator bar -->
            <div class="h-[2px] w-full transition-all duration-300 relative z-[1]"
                 :class="deletingId === p.id
                   ? 'bg-[#FF3B30]/40'
                   : p.has_snapshot
                     ? 'bg-[#007AFF]/20 group-hover:bg-[#007AFF]/50'
                     : 'bg-white/[0.04] group-hover:bg-white/[0.08]'" />
          </button>
        </div>
      </div>

      <!-- Empty state -->
      <div v-else class="flex-1 flex flex-col items-center justify-center">
        <div class="w-16 h-16 mx-auto mb-4 rounded-2xl bg-white/[0.04] flex items-center justify-center
                    shadow-[0_0_60px_rgba(0,122,255,0.08)]">
          <User :size="28" class="text-white/15" />
        </div>
        <p class="text-sm text-white/30">还没有任何档案</p>
        <p class="text-xs text-white/20 mt-1">创建一个新档案开始仿真</p>
      </div>

      <!-- Bottom section (fixed at bottom) -->
      <div class="shrink-0 mt-auto pt-2 md:pt-4">
        <!-- Inline create form -->
        <div class="create-wrapper" :class="creating ? 'create-wrapper--open' : 'create-wrapper--closed'">
          <div class="create-inner">
            <div class="mb-3 md:mb-4 p-3 md:p-4 rounded-xl md:rounded-2xl border border-white/[0.08] bg-white/[0.04]"
                 style="backdrop-filter: blur(8px); -webkit-backdrop-filter: blur(8px)">
              <label class="block text-xs font-medium text-white/50 mb-2">新建档案</label>
              <div class="flex items-center gap-2">
                <input
                  ref="nameInputRef"
                  v-model="newName"
                  type="text"
                  placeholder="例如：张三 / Patient-01"
                  class="cmd-input flex-1"
                  maxlength="100"
                  @keydown.enter="confirmCreate"
                  @keydown.escape="cancelCreate"
                />
                <button
                  class="h-9 px-4 text-sm font-semibold text-white bg-[#007AFF] rounded-xl
                         shadow-[0_2px_8px_rgba(0,122,255,0.25)]
                         hover:shadow-[0_2px_12px_rgba(0,122,255,0.35)]
                         disabled:opacity-40 disabled:cursor-not-allowed
                         transition-all duration-200 shrink-0"
                  :disabled="!newName.trim() || createLoading"
                  @click="confirmCreate"
                >
                  {{ createLoading ? '...' : '创建' }}
                </button>
                <button
                  class="h-9 w-9 flex items-center justify-center rounded-xl shrink-0
                         text-white/40 hover:text-white/70 hover:bg-white/[0.06]
                         transition-all duration-200"
                  @click="cancelCreate"
                >
                  <X :size="15" />
                </button>
              </div>
            </div>
          </div>
        </div>

        <!-- Actions bar -->
        <div class="flex items-center gap-2 md:gap-3 pt-2 md:pt-4 border-t border-white/[0.06] px-1 md:px-0 pb-[env(safe-area-inset-bottom,0px)]">
          <button v-if="!creating"
                  class="flex-1 h-10 md:h-11 flex items-center justify-center gap-2
                         text-sm font-semibold text-white bg-[#007AFF] rounded-full
                         shadow-[0_4px_16px_rgba(0,122,255,0.3)]
                         hover:shadow-[0_6px_24px_rgba(0,122,255,0.45)]
                         hover:-translate-y-px active:translate-y-0
                         transition-all duration-200"
                  style="border-radius: 980px; transition-timing-function: var(--cmd-ease-spring)"
                  @click="startCreate">
            <Plus :size="15" />
            新建档案
          </button>
          <button class="h-10 md:h-11 px-4 md:px-6 text-sm font-medium text-white/50 border border-white/10 rounded-full
                         hover:bg-white/[0.05] hover:text-white/70 hover:border-white/20
                         transition-all duration-200"
                  :class="creating ? 'flex-1' : ''"
                  style="border-radius: 980px"
                  @click="store.connect(null)">
            <Zap :size="13" class="inline mr-1.5" />匿名模式
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* ─── Animated glow orbs ─── */
.glow-orb {
  position: absolute;
  border-radius: 50%;
  pointer-events: none;
  filter: blur(80px);
}
.glow-orb--primary {
  width: 400px;
  height: 400px;
  background: rgba(0, 122, 255, 0.08);
  top: 20%;
  left: 30%;
  animation: orb-float-1 12s ease-in-out infinite;
}
.glow-orb--accent {
  width: 300px;
  height: 300px;
  background: rgba(175, 82, 222, 0.06);
  top: 60%;
  right: 20%;
  animation: orb-float-2 15s ease-in-out infinite;
}
.glow-orb--teal {
  width: 250px;
  height: 250px;
  background: rgba(48, 209, 188, 0.05);
  bottom: 10%;
  left: 15%;
  animation: orb-float-3 18s ease-in-out infinite;
}

@keyframes orb-float-1 {
  0%, 100% { transform: translate(0, 0) scale(1); }
  33% { transform: translate(40px, -30px) scale(1.1); }
  66% { transform: translate(-20px, 20px) scale(0.95); }
}
@keyframes orb-float-2 {
  0%, 100% { transform: translate(0, 0) scale(1); }
  33% { transform: translate(-30px, 20px) scale(1.05); }
  66% { transform: translate(25px, -25px) scale(0.9); }
}
@keyframes orb-float-3 {
  0%, 100% { transform: translate(0, 0) scale(1); }
  50% { transform: translate(35px, -15px) scale(1.08); }
}

/* ─── Profile card hover glow ─── */
.profile-card {
  position: relative;
}
.card-glow {
  position: absolute;
  inset: 0;
  opacity: 0;
  transition: opacity 0.4s ease;
  background: radial-gradient(
    ellipse 80% 80% at 50% 0%,
    rgba(0, 122, 255, 0.08) 0%,
    transparent 70%
  );
  pointer-events: none;
  z-index: 0;
}
.profile-card:hover .card-glow {
  opacity: 1;
}
.profile-card:hover {
  border-color: rgba(0, 122, 255, 0.2);
  box-shadow: 0 4px 24px rgba(0, 122, 255, 0.06), 0 0 0 1px rgba(0, 122, 255, 0.08);
}

/* ─── Vital chip ─── */
.vital-chip {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 8px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.04);
  font-size: 11px;
  color: rgba(255, 255, 255, 0.55);
  font-family: var(--cmd-font-mono);
  white-space: nowrap;
}

/* ─── Input ─── */
.cmd-input {
  height: 36px;
  padding: 0 12px;
  font-size: 14px;
  color: var(--cmd-text-primary);
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 12px;
  outline: none;
  font-family: var(--cmd-font-body);
  transition: border-color 0.2s, box-shadow 0.2s, background 0.2s;
  min-width: 0;
}
.cmd-input::placeholder {
  color: rgba(255, 255, 255, 0.2);
}
.cmd-input:focus {
  border-color: rgba(0, 122, 255, 0.5);
  box-shadow: 0 0 0 3px rgba(0, 122, 255, 0.12);
  background: rgba(255, 255, 255, 0.08);
}

/* ─── Profile list scrollbar ─── */
.profile-scroll::-webkit-scrollbar {
  width: 4px;
}
.profile-scroll::-webkit-scrollbar-track {
  background: transparent;
}
.profile-scroll::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.08);
  border-radius: 2px;
}
.profile-scroll::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.15);
}

/* ─── Create form smooth height transition ─── */
.create-wrapper {
  display: grid;
  transition: grid-template-rows 0.3s var(--cmd-ease-spring), opacity 0.25s ease;
}
.create-wrapper--open {
  grid-template-rows: 1fr;
  opacity: 1;
}
.create-wrapper--closed {
  grid-template-rows: 0fr;
  opacity: 0;
}
.create-inner {
  overflow: hidden;
}

/* ─── Reduced motion ─── */
@media (prefers-reduced-motion: reduce) {
  .glow-orb { animation: none !important; }
  .create-wrapper { transition-duration: 0.1s !important; }
}
</style>

<script setup lang="ts">
/**
 * 虚拟人体录制面板
 *
 * 以 Popover 形式嵌入顶栏，提供录制控制（开始/暂停/停止/取消）和项目选择，
 * 录制结束后上传 ECG + PCG WAV 到指定项目，自动刷新文件列表。
 */
import { ref, reactive, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { Circle, Square, Pause, Play, X, Upload, Disc } from 'lucide-vue-next'
import ProjectPicker from '@/components/ui/ProjectPicker.vue'
import { useVirtualHumanRecorder } from '@/composables/useVirtualHumanRecorder'
import { useVirtualHumanStore } from '@/store/virtualHuman'
import type { SignalChunk } from '@/store/virtualHuman'
import { useProjectStore } from '@/store/project'
import { useToastStore } from '@/store/toast'
import { AUSCULTATION_AREAS } from '@/composables/useAuscultation'
import type { AuscultationArea } from '@/composables/useAuscultation'

const vhStore = useVirtualHumanStore()
const projectStore = useProjectStore()
const toast = useToastStore()

const {
  isRecording, isPaused, duration,
  startRecording, pauseRecording, resumeRecording,
  stopRecording, feedEcgSamples, feedPcgSamples,
  cancelRecording, onAuscultationAreaChanged,
} = useVirtualHumanRecorder()

const selectedProjectId = ref('')
const showPanel = ref(false)
const uploading = ref(false)
const uploadProgress = ref('')

const panelRef = ref<HTMLElement | null>(null)
const triggerRef = ref<HTMLElement | null>(null)
const dropdownRef = ref<HTMLElement | null>(null)

/** 浮层定位：基于触发按钮计算，右对齐 */
const dropdownPos = reactive({ top: 0, right: 0 })

function updateDropdownPos() {
  if (!triggerRef.value) return
  const rect = triggerRef.value.getBoundingClientRect()
  dropdownPos.top = rect.bottom + 8 // mt-2 = 8px
  dropdownPos.right = window.innerWidth - rect.right
}

onMounted(async () => {
  await projectStore.fetchProjects()
  if (projectStore.projects.length > 0 && !selectedProjectId.value) {
    selectedProjectId.value = projectStore.projects[0].id
  }
  document.addEventListener('mousedown', onClickOutside)
})

onUnmounted(() => {
  removeCallbacks()
  document.removeEventListener('mousedown', onClickOutside)
})

function onClickOutside(e: MouseEvent) {
  if (isRecording.value) return // 录制中不允许点击外部关闭
  const target = e.target as HTMLElement
  // 检查是否在触发按钮内
  if (triggerRef.value?.contains(target)) return
  // 检查是否在 Teleport 出去的面板内
  if (dropdownRef.value?.contains(target)) return
  // 检查是否在 ProjectPicker 的 Teleport 下拉面板内（已挂载到 body，不在 panelRef DOM 子树中）
  if (target.closest?.('[data-project-picker-dropdown]')) return
  showPanel.value = false
}

const formattedDuration = computed(() => {
  const s = Math.floor(duration.value)
  const m = Math.floor(s / 60)
  const sec = s % 60
  return `${m.toString().padStart(2, '0')}:${sec.toString().padStart(2, '0')}`
})

// ---- 信号回调 ----
function ecgCallback(chunk: SignalChunk) {
  feedEcgSamples(chunk.samples)
}

function pcgCallback(chunk: SignalChunk) {
  const shouldApplyMembrane = vhStore.auscultationMode
  feedPcgSamples(chunk.samples, shouldApplyMembrane)
}

let callbacksRegistered = false

function ensureCallbacks() {
  if (!callbacksRegistered) {
    vhStore.registerEcgCallback(ecgCallback)
    vhStore.registerPcgCallback(pcgCallback)
    callbacksRegistered = true
  }
}

function removeCallbacks() {
  if (callbacksRegistered) {
    vhStore.unregisterEcgCallback(ecgCallback)
    vhStore.unregisterPcgCallback(pcgCallback)
    callbacksRegistered = false
  }
}

watch(
  () => vhStore.auscultationArea,
  (newArea) => {
    if (isRecording.value && vhStore.auscultationMode) {
      const config = AUSCULTATION_AREAS[newArea as AuscultationArea]
      onAuscultationAreaChanged(newArea, config)
    }
  },
)

// ---- 录制控制 ----
function handleStart() {
  if (!selectedProjectId.value) {
    toast.error('请先选择保存项目')
    return
  }

  const auscConfig = vhStore.auscultationMode
    ? AUSCULTATION_AREAS[vhStore.auscultationArea as AuscultationArea]
    : undefined

  ensureCallbacks()
  startRecording(auscConfig)
  toast.success('录制已开始')
}

function handlePauseResume() {
  if (isPaused.value) {
    resumeRecording()
  } else {
    pauseRecording()
  }
}

async function handleStop() {
  if (!isRecording.value) return

  const auscEnabled = vhStore.auscultationMode
  const auscConfig = auscEnabled
    ? AUSCULTATION_AREAS[vhStore.auscultationArea as AuscultationArea]
    : undefined

  let result: { ecgBlob: Blob; pcgBlob: Blob }
  try {
    result = stopRecording(auscEnabled, auscConfig)
  } catch {
    toast.error('停止录制失败')
    return
  }

  if (!selectedProjectId.value) {
    toast.error('未选择项目，录制数据已丢失')
    return
  }

  await uploadToProject(selectedProjectId.value, result.ecgBlob, result.pcgBlob)
}

function handleCancel() {
  cancelRecording()
  removeCallbacks()
  toast.info('录制已取消')
}

async function uploadToProject(projectId: string, ecgBlob: Blob, pcgBlob: Blob) {
  uploading.value = true
  const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19)
  const modeLabel = vhStore.auscultationMode
    ? `_${vhStore.auscultationArea}`
    : ''

  try {
    uploadProgress.value = '上传 ECG...'
    const ecgFile = new File([ecgBlob], `VH_ECG${modeLabel}_${timestamp}.wav`, { type: 'audio/wav' })
    const ecgResult = await projectStore.uploadFile(projectId, ecgFile)
    if (!ecgResult) {
      toast.error('ECG 文件上传失败')
      return
    }

    uploadProgress.value = '上传 PCG...'
    const pcgFile = new File([pcgBlob], `VH_PCG${modeLabel}_${timestamp}.wav`, { type: 'audio/wav' })
    const pcgResult = await projectStore.uploadFile(projectId, pcgFile)
    if (!pcgResult) {
      toast.error('PCG 文件上传失败')
      return
    }

    uploadProgress.value = '刷新项目文件...'
    await projectStore.fetchProjectFiles(projectId)

    toast.success('录制文件已保存到项目')
    cancelRecording()
    removeCallbacks()
    showPanel.value = false
  } catch {
    toast.error('上传录制文件失败')
  } finally {
    uploading.value = false
    uploadProgress.value = ''
  }
}

function togglePanel() {
  showPanel.value = !showPanel.value
  if (showPanel.value) {
    updateDropdownPos()
  }
}
</script>

<template>
  <div ref="panelRef">
    <!-- 触发按钮 —— 与顶栏保存/断开按钮风格一致 -->
    <button
      ref="triggerRef"
      :class="[
        'flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg transition-all',
        isRecording
          ? 'bg-red-500/15 text-red-400 border border-red-500/30 hover:bg-red-500/25'
          : 'text-white/50 border border-white/20 hover:bg-white/10'
      ]"
      @click="togglePanel"
    >
      <Disc :size="13" :class="isRecording && 'animate-pulse text-red-400'" />
      <template v-if="isRecording">
        <span class="font-mono tabular-nums">{{ formattedDuration }}</span>
      </template>
      <template v-else>录制</template>
    </button>

    <!-- Popover 面板 — Teleport 到 body，规避 stacking context 遮挡 -->
    <Teleport to="body">
      <Transition
        enter-active-class="transition duration-150 ease-out"
        enter-from-class="opacity-0 -translate-y-1 scale-95"
        enter-to-class="opacity-100 translate-y-0 scale-100"
        leave-active-class="transition duration-100 ease-in"
        leave-from-class="opacity-100 translate-y-0 scale-100"
        leave-to-class="opacity-0 -translate-y-1 scale-95"
      >
        <div
          v-if="showPanel"
          ref="dropdownRef"
          class="fixed z-[9999] w-80 bg-gray-950/60 backdrop-blur-2xl backdrop-saturate-[1.8] border border-white/[0.15] rounded-xl shadow-2xl ring-1 ring-black/30"
          :style="{ top: dropdownPos.top + 'px', right: dropdownPos.right + 'px' }"
        >
        <!-- 面板头部 -->
        <div class="px-4 py-3 border-b border-white/[0.08]">
          <div class="flex items-center justify-between">
            <div>
              <h3 class="text-sm font-semibold text-white/90">录制控制</h3>
              <p class="text-[11px] text-white/40 mt-0.5">ECG + PCG 双路 WAV</p>
            </div>
            <div
              v-if="isRecording"
              class="flex items-center gap-1.5"
            >
              <span class="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
              <span class="text-sm font-mono tabular-nums text-red-400 font-semibold">{{ formattedDuration }}</span>
            </div>
          </div>
        </div>

        <!-- 面板内容 -->
        <div class="p-4 space-y-3">
          <!-- 项目选择器 -->
          <div>
            <label class="block text-xs font-medium text-white/50 mb-1.5">保存到项目</label>
            <ProjectPicker
              v-model="selectedProjectId"
              placeholder="选择目标项目"
              dark
            />
          </div>

          <!-- 操作按钮区 -->
          <div class="flex items-center gap-2">
            <!-- 未录制态 -->
            <template v-if="!isRecording">
              <button
                class="flex-1 inline-flex items-center justify-center gap-1.5 px-3 py-2 text-sm font-medium text-white bg-red-500/90 rounded-lg hover:bg-red-500 transition-colors shadow-sm"
                :disabled="!selectedProjectId"
                :class="!selectedProjectId && 'opacity-50 cursor-not-allowed'"
                @click="handleStart"
              >
                <Circle :size="14" />
                开始录制
              </button>
            </template>

            <!-- 录制中态 -->
            <template v-else>
              <button
                class="inline-flex items-center justify-center gap-1.5 px-3 py-2 text-sm font-medium rounded-lg border transition-colors"
                :class="isPaused
                  ? 'text-sky-400 border-sky-400/30 bg-sky-400/10 hover:bg-sky-400/20'
                  : 'text-white/70 border-white/10 bg-white/5 hover:bg-white/10'
                "
                @click="handlePauseResume"
              >
                <Play v-if="isPaused" :size="14" />
                <Pause v-else :size="14" />
                {{ isPaused ? '继续' : '暂停' }}
              </button>

              <button
                class="flex-1 inline-flex items-center justify-center gap-1.5 px-3 py-2 text-sm font-medium text-white bg-emerald-500/90 rounded-lg hover:bg-emerald-500 transition-colors shadow-sm"
                @click="handleStop"
              >
                <Square :size="14" />
                停止并保存
              </button>

              <button
                class="inline-flex items-center justify-center p-2 text-white/40 hover:text-red-400 hover:bg-red-500/10 rounded-lg transition-colors"
                title="取消录制"
                @click="handleCancel"
              >
                <X :size="16" />
              </button>
            </template>
          </div>

          <!-- 上传进度 -->
          <div v-if="uploading" class="flex items-center gap-2 px-3 py-2 bg-amber-500/10 border border-amber-500/20 rounded-lg">
            <Upload :size="13" class="text-amber-400 shrink-0 animate-pulse" />
            <span class="text-xs text-amber-300">{{ uploadProgress }}</span>
          </div>
        </div>
      </div>
      </Transition>
    </Teleport>
  </div>
</template>

<template>
  <div ref="wrapperRef">
    <!-- Trigger button -->
    <button
      type="button"
      class="w-full flex items-center gap-2 px-3 py-2 border rounded-xl text-left transition-all"
      :class="dark
        ? [
            'border-white/[0.12] bg-white/[0.06]',
            open ? 'ring-2 ring-sky-400/40 border-sky-400/40' : 'hover:border-white/20 hover:bg-white/[0.08]'
          ]
        : [
            'border-gray-200',
            open ? 'ring-2 ring-primary-300 border-primary-400' : 'hover:border-gray-300'
          ]
      "
      ref="triggerRef"
      @click="toggle"
    >
      <FolderOpen class="w-4 h-4 shrink-0" :class="dark ? 'text-white/40' : 'text-gray-400'" />
      <span v-if="selectedProject" class="flex-1 truncate text-sm" :class="dark ? 'text-white/90' : 'text-gray-900'">{{ selectedProject.name }}</span>
      <span v-else class="flex-1 truncate text-sm" :class="dark ? 'text-white/40' : 'text-gray-400'">{{ placeholder }}</span>
      <ChevronDown class="w-3.5 h-3.5 shrink-0 transition-transform" :class="[dark ? 'text-white/40' : 'text-gray-400', open && 'rotate-180']" />
    </button>

    <!-- Dropdown — 全局挂载到 body，规避外层 overflow 裁切 -->
    <Teleport to="body">
      <Transition
        enter-active-class="transition duration-100 ease-out"
        enter-from-class="opacity-0 -translate-y-1"
        enter-to-class="opacity-100 translate-y-0"
        leave-active-class="transition duration-75 ease-in"
        leave-from-class="opacity-100 translate-y-0"
        leave-to-class="opacity-0 -translate-y-1"
      >
        <div v-if="open"
          ref="dropdownRef"
          data-project-picker-dropdown
          class="fixed z-[9999] rounded-xl shadow-lg overflow-hidden"
          :class="dark
            ? 'bg-gray-950/60 backdrop-blur-2xl backdrop-saturate-[1.8] border border-white/[0.15] ring-1 ring-black/30 shadow-2xl'
            : 'bg-white/75 backdrop-blur-xl backdrop-saturate-[1.6] border border-gray-200/60 ring-1 ring-black/[0.04] shadow-xl'
          "
          :style="dropdownStyle"
        >
          <!-- Search input -->
          <div class="px-3 py-2 border-b" :class="dark ? 'border-white/[0.08]' : 'border-gray-100'">
            <div class="flex items-center gap-2">
              <Search class="w-3.5 h-3.5 shrink-0" :class="dark ? 'text-white/30' : 'text-gray-400'" />
              <input
                ref="searchInputRef"
                v-model="query"
                type="text"
                class="w-full text-sm bg-transparent outline-none"
                :class="dark ? 'text-white/90 placeholder-white/30' : 'text-gray-900 placeholder-gray-400'"
                placeholder="搜索项目..."
                @keydown.escape="open = false"
              />
            </div>
          </div>

          <!-- List -->
          <div class="overflow-y-auto" style="max-height:220px">
            <div v-if="loadingProjects" class="flex justify-center py-4">
              <span class="spinner w-4 h-4" />
            </div>
            <template v-else>
              <button
                v-for="p in filteredProjects"
                :key="p.id"
                class="w-full flex items-center gap-2.5 px-3 py-2 text-left text-sm transition-colors"
                :class="dark
                  ? (p.id === modelValue
                    ? 'bg-sky-400/10 text-sky-400 font-medium'
                    : 'text-white/70 hover:bg-white/[0.06] hover:text-white')
                  : (p.id === modelValue
                    ? 'bg-primary-50 text-primary-700 font-medium'
                    : 'text-gray-700 hover:bg-gray-50')
                "
                @click="selectProject(p)"
              >
                <Check v-if="p.id === modelValue" class="w-3.5 h-3.5 shrink-0" :class="dark ? 'text-sky-400' : 'text-primary-500'" />
                <div v-else class="w-3.5 h-3.5 shrink-0" />
                <span class="truncate">{{ p.name }}</span>
                <span class="ml-auto text-xs shrink-0" :class="dark ? 'text-white/30' : 'text-gray-400'" v-if="p.is_public">公开</span>
              </button>
              <div v-if="filteredProjects.length === 0 && !showCreate" class="px-3 py-4 text-center text-xs" :class="dark ? 'text-white/30' : 'text-gray-400'">
                无匹配项目
              </div>
            </template>
          </div>

          <!-- Create new project inline -->
          <div class="border-t" :class="dark ? 'border-white/[0.08]' : 'border-gray-100'">
            <template v-if="!showCreate">
              <button
                class="w-full flex items-center gap-2 px-3 py-2.5 text-sm transition-colors"
                :class="dark
                  ? 'text-sky-400 hover:bg-white/[0.06]'
                  : 'text-primary-600 hover:bg-primary-50'
                "
                @click="showCreate = true"
              >
                <Plus class="w-3.5 h-3.5" />
                新建项目{{ query ? ` "${query}"` : '' }}
              </button>
            </template>
            <template v-else>
              <div class="px-3 py-3 space-y-2">
                <input
                  ref="createInputRef"
                  v-model="newName"
                  type="text"
                  class="w-full text-sm rounded-lg px-3 py-2 outline-none transition-colors"
                  :class="dark
                    ? 'bg-white/[0.06] border border-white/[0.12] text-white/90 placeholder-white/30 focus:border-sky-400/40 focus:ring-1 focus:ring-sky-400/20'
                    : 'input'
                  "
                  placeholder="项目名称"
                  @keydown.enter="createAndSelect"
                  @keydown.escape="showCreate = false"
                />
                <div class="flex items-center justify-end gap-2">
                  <button
                    class="px-2.5 py-1 text-xs rounded-md transition-colors"
                    :class="dark
                      ? 'text-white/50 hover:text-white/70 hover:bg-white/[0.06]'
                      : 'btn-ghost btn-sm'
                    "
                    @click="showCreate = false"
                  >取消</button>
                  <button
                    class="px-2.5 py-1 text-xs font-medium rounded-md transition-colors"
                    :class="dark
                      ? 'bg-sky-500/80 text-white hover:bg-sky-500 disabled:opacity-40 disabled:cursor-not-allowed'
                      : 'btn-primary btn-sm'
                    "
                    :disabled="!newName.trim() || creating"
                    @click="createAndSelect"
                  >
                    <span v-if="creating" class="spinner w-3 h-3" />
                    创建并选择
                  </button>
                </div>
              </div>
            </template>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch, nextTick, onMounted, onUnmounted } from 'vue'
import { FolderOpen, ChevronDown, Search, Check, Plus } from 'lucide-vue-next'
import { useProjectStore } from '@/store/project'
import { useToastStore } from '@/store/toast'

const props = withDefaults(defineProps<{
  modelValue: string
  placeholder?: string
  dark?: boolean
}>(), {
  placeholder: '请选择项目',
  dark: false,
})

const emit = defineEmits<{
  'update:modelValue': [value: string]
}>()

const projectStore = useProjectStore()
const toast = useToastStore()

const open = ref(false)
const query = ref('')
const showCreate = ref(false)
const newName = ref('')
const creating = ref(false)
const loadingProjects = ref(false)

const wrapperRef = ref<HTMLElement | null>(null)
const triggerRef = ref<HTMLElement | null>(null)
const dropdownRef = ref<HTMLElement | null>(null)
const searchInputRef = ref<HTMLInputElement | null>(null)
const createInputRef = ref<HTMLInputElement | null>(null)

// ---- Teleport 定位计算 ----
const dropdownPos = reactive({ top: 0, left: 0, width: 0 })

const dropdownStyle = computed(() => ({
  top: `${dropdownPos.top}px`,
  left: `${dropdownPos.left}px`,
  width: `${dropdownPos.width}px`,
  maxHeight: '320px',
}))

function updateDropdownPosition() {
  if (!triggerRef.value) return
  const rect = triggerRef.value.getBoundingClientRect()
  dropdownPos.top = rect.bottom + 4 // 4px gap
  dropdownPos.left = rect.left
  dropdownPos.width = rect.width
}

const selectedProject = computed(() =>
  projectStore.projects.find(p => p.id === props.modelValue) ?? null
)

const filteredProjects = computed(() => {
  const q = query.value.toLowerCase().trim()
  if (!q) return projectStore.projects
  return projectStore.projects.filter(p =>
    p.name.toLowerCase().includes(q)
  )
})

const toggle = () => {
  open.value = !open.value
  if (open.value) {
    query.value = ''
    showCreate.value = false
    if (!projectStore.projects.length) loadProjects()
    nextTick(() => {
      updateDropdownPosition()
      searchInputRef.value?.focus()
    })
  }
}

const loadProjects = async () => {
  loadingProjects.value = true
  await projectStore.fetchProjects()
  loadingProjects.value = false
}

const selectProject = (p: any) => {
  emit('update:modelValue', p.id)
  open.value = false
}

const createAndSelect = async () => {
  if (!newName.value.trim()) return
  creating.value = true
  const p = await projectStore.createProject({ name: newName.value.trim() })
  creating.value = false
  if (p) {
    toast.success(`项目 "${p.name}" 已创建`)
    emit('update:modelValue', p.id)
    newName.value = ''
    showCreate.value = false
    open.value = false
  } else {
    toast.error('创建项目失败')
  }
}

// Prefill new project name from search query
watch(showCreate, (v) => {
  if (v) {
    newName.value = query.value
    nextTick(() => createInputRef.value?.focus())
  }
})

// 滚动 / 缩放时更新位置
function onScrollOrResize() {
  if (open.value) updateDropdownPosition()
}

// Click outside to close — 同时检查 wrapper 和 teleport 出去的 dropdown
const onClickOutside = (e: MouseEvent) => {
  const target = e.target as Node
  const inWrapper = wrapperRef.value?.contains(target)
  const inDropdown = dropdownRef.value?.contains(target)
  if (!inWrapper && !inDropdown) {
    open.value = false
  }
}

onMounted(() => {
  document.addEventListener('mousedown', onClickOutside)
  window.addEventListener('scroll', onScrollOrResize, true)
  window.addEventListener('resize', onScrollOrResize)
  if (!projectStore.projects.length) loadProjects()
})
onUnmounted(() => {
  document.removeEventListener('mousedown', onClickOutside)
  window.removeEventListener('scroll', onScrollOrResize, true)
  window.removeEventListener('resize', onScrollOrResize)
})
</script>

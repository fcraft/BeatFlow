<template>
  <AppLayout>
    <div v-if="loading" class="flex items-center justify-center py-32">
      <span class="spinner w-8 h-8" />
    </div>

    <template v-else>
      <!-- Project header -->
      <div class="bg-white border-b border-gray-200">
        <div class="page-container pb-0">
          <!-- Breadcrumb -->
          <nav class="flex items-center gap-2 text-sm text-gray-500 mb-4">
            <RouterLink v-if="isMobile" to="/projects" class="hover:text-gray-700 flex items-center gap-1">
              <ArrowLeft class="w-4 h-4" />
              项目列表
            </RouterLink>
            <template v-else>
              <RouterLink to="/projects" class="hover:text-gray-700 flex items-center gap-1">
                <FolderOpen class="w-3.5 h-3.5" />
                项目列表
              </RouterLink>
              <ChevronRight class="w-3.5 h-3.5" />
              <span class="text-gray-900 font-medium">{{ project?.name ?? '...' }}</span>
            </template>
          </nav>

          <div class="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3 mb-5">
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-3 mb-1 flex-wrap">
                <h1 class="text-xl font-bold text-gray-900 truncate">{{ project?.name }}</h1>
                <span :class="project?.is_public ? 'badge-green' : 'badge-gray'">
                  {{ project?.is_public ? '公开' : '私有' }}
                </span>
              </div>
              <p class="text-sm text-gray-500">{{ project?.description || '暂无描述' }}</p>
              <div class="flex flex-wrap items-center gap-x-4 gap-y-1 mt-2 text-xs text-gray-400">
                <span v-if="!isMobile" class="flex items-center gap-1"><Calendar class="w-3 h-3" />创建 {{ formatDate(project?.created_at) }}</span>
                <span class="flex items-center gap-1"><Clock class="w-3 h-3" />更新 {{ formatDate(project?.updated_at) }}</span>
              </div>
            </div>
            <button class="btn-secondary btn-sm self-start shrink-0" @click="refresh">
              <RefreshCw class="w-3.5 h-3.5" :class="{ 'animate-spin': refreshing }" />
              刷新
            </button>
          </div>

          <!-- Tabs — horizontally scrollable on mobile -->
          <div class="relative">
            <div v-if="isMobile" class="absolute left-0 top-0 bottom-0 w-4 bg-gradient-to-r from-white to-transparent z-10 pointer-events-none" />
            <div class="flex items-center gap-0 border-b-0 overflow-x-auto scrollbar-hide -mb-px">
              <button
                v-for="tab in tabs"
                :key="tab.key"
                class="flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors shrink-0"
                :class="activeTab === tab.key
                  ? 'border-primary-600 text-primary-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700'"
                @click="activeTab = tab.key"
              >
                <component :is="tab.icon" class="w-4 h-4" />
                {{ tab.label }}
              </button>
            </div>
            <div v-if="isMobile" class="absolute right-0 top-0 bottom-0 w-4 bg-gradient-to-l from-white to-transparent z-10 pointer-events-none" />
          </div>
        </div>
      </div>

      <!-- Tab content -->
      <div ref="tabContentRef" class="page-container">
        <FileManager v-if="activeTab === 'files'" :project-id="projectId" />
        <AssociationManager v-else-if="activeTab === 'associations'" :project-id="projectId" />
        <MemberManager v-else-if="activeTab === 'members'" :project-id="projectId" />
        <ProjectSettings v-else-if="activeTab === 'settings'" :project="project" :project-id="projectId" @update="onUpdate" />
      </div>
    </template>
  </AppLayout>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter, RouterLink } from 'vue-router'
import { FolderOpen, ChevronRight, Calendar, Clock, RefreshCw, Files, Users, Settings, Link, ArrowLeft } from 'lucide-vue-next'
import { useSwipe } from '@vueuse/core'
import { useMobile } from '@/composables/useMobile'
import AppLayout from '@/components/layout/AppLayout.vue'
import FileManager from '@/components/project/FileManager.vue'
import MemberManager from '@/components/project/MemberManager.vue'
import ProjectSettings from '@/components/project/ProjectSettings.vue'
import AssociationManager from '@/components/project/AssociationManager.vue'
import { useProjectStore } from '@/store/project'
import { useToastStore } from '@/store/toast'
import type { Project } from '@/types/project'

const route = useRoute()
const router = useRouter()
const projectStore = useProjectStore()
const toast = useToastStore()

const projectId = route.params.id as string
const loading = ref(true)
const refreshing = ref(false)
const activeTab = ref(route.query.tab as string || 'files')

const project = computed(() => projectStore.currentProject)

const { isMobile } = useMobile()
const tabContentRef = ref<HTMLElement | null>(null)

const tabs = [
  { key: 'files',        label: '文件管理', icon: Files },
  { key: 'associations', label: '文件关联', icon: Link },
  { key: 'members',      label: '项目成员', icon: Users },
  { key: 'settings',     label: '设置',     icon: Settings },
]

const tabKeys = tabs.map(t => t.key)

useSwipe(tabContentRef, {
  onSwipeEnd(_e, direction) {
    if (!isMobile.value) return
    const currentIdx = tabKeys.indexOf(activeTab.value)
    if (direction === 'left' && currentIdx < tabKeys.length - 1) {
      activeTab.value = tabKeys[currentIdx + 1]
    } else if (direction === 'right' && currentIdx > 0) {
      activeTab.value = tabKeys[currentIdx - 1]
    }
  },
})

const refresh = async () => {
  refreshing.value = true
  await Promise.all([
    projectStore.fetchProjectDetail(projectId),
    projectStore.fetchProjectMembers(projectId),
    projectStore.fetchProjectFiles(projectId),
  ])
  refreshing.value = false
}

const onUpdate = (p: Project) => {
  toast.success('项目已更新')
  projectStore.fetchProjectDetail(projectId)
}

const formatDate = (d?: string) => {
  if (!d) return '—'
  return new Date(d).toLocaleDateString('zh-CN', { year: 'numeric', month: 'short', day: 'numeric' })
}

onMounted(async () => {
  await refresh()
  loading.value = false
})

watch(() => route.params.id, () => { if (route.params.id) refresh() })
</script>

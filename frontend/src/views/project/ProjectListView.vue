<template>
  <AppLayout>
    <div class="page-container">
      <!-- Header -->
      <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-6">
        <div>
          <h1 class="text-xl font-bold text-gray-900">我的项目</h1>
          <p class="text-sm text-gray-500 mt-0.5">管理您的心音心电数据分析项目</p>
        </div>
        <button class="btn-primary self-start sm:self-auto" @click="showCreate = true">
          <Plus class="w-4 h-4" />
          新建项目
        </button>
      </div>

      <!-- Filters -->
      <div class="flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-3 mb-5">
        <div class="relative flex-1">
          <Search class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input v-model="searchQuery" type="text" placeholder="搜索项目..." class="input pl-9" />
        </div>
        <div class="flex items-center gap-2">
          <select v-model="filterType" class="select flex-1 sm:w-36">
            <option value="all">全部项目</option>
            <option value="public">公开项目</option>
            <option value="private">私有项目</option>
          </select>
          <button class="btn-ghost btn-sm shrink-0" @click="refresh">
            <RefreshCw class="w-4 h-4" :class="{ 'animate-spin': loading }" />
          </button>
        </div>
      </div>

      <!-- Grid -->
      <div v-if="loading" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        <div v-for="n in 6" :key="n" class="card p-5 animate-pulse">
          <div class="h-4 bg-gray-200 rounded w-2/3 mb-3" />
          <div class="h-3 bg-gray-100 rounded w-1/2 mb-4" />
          <div class="h-12 bg-gray-100 rounded mb-4" />
          <div class="h-px bg-gray-100 mb-3" />
          <div class="flex justify-between">
            <div class="h-3 bg-gray-100 rounded w-1/3" />
            <div class="h-3 bg-gray-100 rounded w-1/4" />
          </div>
        </div>
      </div>

      <div v-else-if="filtered.length > 0" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        <div
          v-for="p in filtered"
          :key="p.id"
          class="card-hover p-5 flex flex-col"
          @click="goDetail(p.id)"
        >
          <div class="flex items-start justify-between mb-2">
            <h3 class="font-semibold text-gray-900 truncate flex-1 mr-2">{{ p.name }}</h3>
            <span :class="p.is_public ? 'badge-green' : 'badge-gray'">
              {{ p.is_public ? '公开' : '私有' }}
            </span>
          </div>
          <p class="text-sm text-gray-500 line-clamp-2 flex-1 mb-4">{{ p.description || '暂无描述' }}</p>
          <div class="border-t border-gray-100 pt-3 flex items-center justify-between">
            <span class="text-xs text-gray-400 flex items-center gap-1">
              <Calendar class="w-3 h-3" />
              {{ formatDate(p.created_at) }}
            </span>
            <div class="flex items-center gap-1" @click.stop>
              <button class="btn-icon btn-sm rounded-md" title="查看" @click="goDetail(p.id)">
                <Eye class="w-3.5 h-3.5" />
              </button>
              <button class="btn-icon btn-sm rounded-md" title="编辑" @click="startEdit(p)">
                <Pencil class="w-3.5 h-3.5" />
              </button>
              <button class="btn-icon btn-sm rounded-md hover:text-red-500 hover:bg-red-50" title="删除" @click="startDelete(p)">
                <Trash2 class="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        </div>
      </div>

      <div v-else class="card flex flex-col items-center justify-center py-20 text-center">
        <FolderOpen class="w-12 h-12 text-gray-300 mb-4" />
        <h3 class="text-lg font-semibold text-gray-600 mb-2">暂无项目</h3>
        <p class="text-sm text-gray-400 mb-6">创建第一个项目，开始分析心音心电数据</p>
        <button class="btn-primary" @click="showCreate = true">
          <Plus class="w-4 h-4" />
          创建项目
        </button>
      </div>
    </div>

    <!-- Create Modal -->
    <AppModal v-model="showCreate" title="新建项目" width="480px">
      <div class="space-y-4">
        <div>
          <label class="label">项目名称 <span class="text-red-500">*</span></label>
          <input v-model="form.name" type="text" placeholder="输入项目名称" class="input" />
        </div>
        <div>
          <label class="label">项目描述</label>
          <textarea v-model="form.description" rows="3" placeholder="描述这个项目的用途..." class="textarea" />
        </div>
        <label class="flex items-center gap-2.5 cursor-pointer">
          <input v-model="form.is_public" type="checkbox" class="accent-primary-600" />
          <span class="text-sm text-gray-700">设为公开项目（所有人可查看）</span>
        </label>
      </div>
      <template #footer>
        <button class="btn-secondary" @click="showCreate = false">取消</button>
        <button class="btn-primary" :disabled="creating || !form.name.trim()" @click="createProject">
          <span v-if="creating" class="spinner w-4 h-4" />
          创建
        </button>
      </template>
    </AppModal>

    <!-- Edit Modal -->
    <AppModal v-model="showEdit" title="编辑项目" width="480px">
      <div v-if="editTarget" class="space-y-4">
        <div>
          <label class="label">项目名称</label>
          <input v-model="editTarget.name" type="text" class="input" />
        </div>
        <div>
          <label class="label">项目描述</label>
          <textarea v-model="editTarget.description" rows="3" class="textarea" />
        </div>
        <label class="flex items-center gap-2.5 cursor-pointer">
          <input v-model="editTarget.is_public" type="checkbox" class="accent-primary-600" />
          <span class="text-sm text-gray-700">公开项目</span>
        </label>
      </div>
      <template #footer>
        <button class="btn-secondary" @click="showEdit = false">取消</button>
        <button class="btn-primary" :disabled="editing" @click="saveEdit">
          <span v-if="editing" class="spinner w-4 h-4" />
          保存
        </button>
      </template>
    </AppModal>

    <!-- Delete Modal -->
    <AppModal v-model="showDelete" title="确认删除" width="400px">
      <div class="text-center py-2">
        <div class="w-12 h-12 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-4">
          <AlertTriangle class="w-6 h-6 text-red-600" />
        </div>
        <p class="text-gray-800 font-medium mb-1">删除项目"{{ deleteTarget?.name }}"？</p>
        <p class="text-sm text-gray-500">此操作不可撤销，项目中所有数据将被永久删除。</p>
      </div>
      <template #footer>
        <button class="btn-secondary" @click="showDelete = false">取消</button>
        <button class="btn-danger" :disabled="deleting" @click="confirmDelete">
          <span v-if="deleting" class="spinner w-4 h-4" />
          确认删除
        </button>
      </template>
    </AppModal>
  </AppLayout>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Plus, Search, RefreshCw, Eye, Pencil, Trash2, FolderOpen, Calendar, AlertTriangle } from 'lucide-vue-next'
import AppLayout from '@/components/layout/AppLayout.vue'
import AppModal from '@/components/ui/AppModal.vue'
import { useProjectStore } from '@/store/project'
import { useToastStore } from '@/store/toast'
import type { Project } from '@/types/project'

const router = useRouter()
const projectStore = useProjectStore()
const toast = useToastStore()

const loading = ref(false)
const creating = ref(false)
const editing = ref(false)
const deleting = ref(false)
const searchQuery = ref('')
const filterType = ref<'all'|'public'|'private'>('all')

const showCreate = ref(false)
const showEdit = ref(false)
const showDelete = ref(false)
const editTarget = ref<Project | null>(null)
const deleteTarget = ref<Project | null>(null)

const form = reactive({ name: '', description: '', is_public: false })

const filtered = computed(() => {
  let list = projectStore.projects
  if (searchQuery.value) {
    const q = searchQuery.value.toLowerCase()
    list = list.filter(p => p.name.toLowerCase().includes(q) || p.description?.toLowerCase().includes(q))
  }
  if (filterType.value === 'public') list = list.filter(p => p.is_public)
  if (filterType.value === 'private') list = list.filter(p => !p.is_public)
  return list
})

const refresh = async () => {
  loading.value = true
  await projectStore.fetchProjects()
  loading.value = false
}

const goDetail = (id: string) => router.push(`/projects/${id}`)

const createProject = async () => {
  if (!form.name.trim()) return
  creating.value = true
  const p = await projectStore.createProject({ ...form })
  creating.value = false
  if (p) {
    toast.success('项目已创建')
    showCreate.value = false
    Object.assign(form, { name: '', description: '', is_public: false })
  } else {
    toast.error('创建失败，请重试')
  }
}

const startEdit = (p: Project) => {
  editTarget.value = { ...p }
  showEdit.value = true
}

const saveEdit = async () => {
  if (!editTarget.value) return
  editing.value = true
  const updated = await projectStore.updateProject(editTarget.value.id, {
    name: editTarget.value.name,
    description: editTarget.value.description,
    is_public: editTarget.value.is_public,
  })
  editing.value = false
  if (updated) {
    toast.success('项目已更新')
    showEdit.value = false
  } else {
    toast.error('保存失败')
  }
}

const startDelete = (p: Project) => {
  deleteTarget.value = p
  showDelete.value = true
}

const confirmDelete = async () => {
  if (!deleteTarget.value) return
  deleting.value = true
  const ok = await projectStore.deleteProject(deleteTarget.value.id)
  deleting.value = false
  if (ok) {
    toast.success('项目已删除')
    showDelete.value = false
  } else {
    toast.error('删除失败')
  }
}

const formatDate = (d: string) => new Date(d).toLocaleDateString('zh-CN', { year: 'numeric', month: 'short', day: 'numeric' })

onMounted(refresh)
</script>

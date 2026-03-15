<template>
  <div>
    <!-- Header -->
    <div class="flex items-center justify-between mb-5">
      <div>
        <h2 class="text-base font-semibold text-gray-900">文件关联</h2>
        <p class="text-xs text-gray-500 mt-0.5">将 ECG / PCG / 视频 关联在一起，支持同步预览和时间偏移微调</p>
      </div>
      <!-- Create button: only show for member+ -->
      <button v-if="permission.canManageAssociations" class="btn-primary btn-sm" @click="openCreate">
        <Link class="w-3.5 h-3.5" />新建关联
      </button>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="space-y-2">
      <div v-for="n in 3" :key="n" class="card p-4 animate-pulse flex items-center gap-4">
        <div class="w-10 h-10 bg-gray-200 rounded-lg" />
        <div class="flex-1 space-y-2">
          <div class="h-3.5 bg-gray-200 rounded w-1/3" />
          <div class="h-3 bg-gray-100 rounded w-1/2" />
        </div>
      </div>
    </div>

    <!-- Empty -->
    <div v-else-if="associations.length === 0"
      class="card flex flex-col items-center justify-center py-16 text-center">
      <LinkIcon class="w-10 h-10 text-gray-300 mb-3" />
      <h4 class="font-semibold text-gray-600 mb-1">暂无文件关联</h4>
      <p class="text-sm text-gray-400 mb-4">将多个信号文件关联后，可以进行同步预览</p>
      <!-- Create button: only show for member+ -->
      <button v-if="permission.canManageAssociations" class="btn-primary btn-sm" @click="openCreate">
        <Link class="w-3.5 h-3.5" />创建第一个关联
      </button>
    </div>

    <!-- List -->
    <div v-else class="space-y-3">
      <div
        v-for="assoc in associations"
        :key="assoc.id"
        class="card p-4 group hover:border-primary-200 hover:shadow-sm transition-all"
      >
        <div class="flex items-start gap-3">
          <!-- Icon -->
          <div class="w-10 h-10 rounded-lg bg-indigo-50 flex items-center justify-center shrink-0 mt-0.5">
            <Layers class="w-5 h-5 text-indigo-500" />
          </div>

          <!-- Info -->
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-2 flex-wrap">
              <span class="font-medium text-sm text-gray-900 truncate">{{ assoc.name || '未命名关联' }}</span>
              <span v-if="assoc.notes" class="text-xs text-gray-400 italic truncate">— {{ assoc.notes }}</span>
            </div>

            <!-- Slots chips -->
            <div class="flex items-center flex-wrap gap-2 mt-1.5">
              <template v-if="assoc.ecg_file">
                <span class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs bg-red-50 text-red-600 border border-red-100">
                  <Activity class="w-3 h-3" />ECG: {{ shortName(assoc.ecg_file.original_filename) }}
                </span>
              </template>
              <span v-else class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs bg-gray-100 text-gray-400">
                <Activity class="w-3 h-3" />无 ECG
              </span>

              <template v-if="assoc.pcg_file">
                <span class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs bg-purple-50 text-purple-600 border border-purple-100">
                  <Waves class="w-3 h-3" />PCG: {{ shortName(assoc.pcg_file.original_filename) }}
                  <span v-if="assoc.pcg_offset !== 0" class="opacity-70">
                    {{ assoc.pcg_offset > 0 ? '+' : '' }}{{ assoc.pcg_offset.toFixed(3) }}s
                  </span>
                </span>
              </template>
              <span v-else class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs bg-gray-100 text-gray-400">
                <Waves class="w-3 h-3" />无 PCG
              </span>

              <template v-if="assoc.video_file">
                <span class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs bg-blue-50 text-blue-600 border border-blue-100">
                  <Video class="w-3 h-3" />视频: {{ shortName(assoc.video_file.original_filename) }}
                  <span v-if="assoc.video_offset !== 0" class="opacity-70">
                    {{ assoc.video_offset > 0 ? '+' : '' }}{{ assoc.video_offset.toFixed(3) }}s
                  </span>
                </span>
              </template>
            </div>
          </div>

          <!-- Actions -->
          <div class="flex items-center gap-1 shrink-0">
            <RouterLink
              :to="`/sync/${assoc.id}`"
              class="btn-primary btn-sm"
              title="同步预览"
            >
              <PlayCircle class="w-3.5 h-3.5" />预览
            </RouterLink>
            <!-- Edit button: only show for member+ -->
            <button 
              v-if="permission.canManageAssociations"
              class="btn-icon btn-sm rounded-md" 
              title="编辑关联" 
              @click="openEdit(assoc)"
            >
              <Pencil class="w-3.5 h-3.5" />
            </button>
            <!-- Delete button: only show for admin+ -->
            <button 
              v-if="permission.canDelete"
              class="btn-icon btn-sm rounded-md hover:text-red-500 hover:bg-red-50" 
              title="删除" 
              @click="confirmDelete(assoc)"
            >
              <Trash2 class="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- ── Create / Edit Modal ── -->
    <AppModal v-model="showModal" :title="editing ? '编辑关联' : '新建文件关联'" width="560px">
      <div class="space-y-4">
        <!-- Name -->
        <div>
          <label class="label">关联名称</label>
          <input v-model="form.name" type="text" class="input" placeholder="例如：受试者01 第1次采集" />
        </div>

        <!-- ECG slot -->
        <div>
          <label class="label flex items-center gap-1">
            <Activity class="w-3.5 h-3.5 text-red-500" />ECG 文件
            <span class="ml-auto text-xs font-normal text-gray-400">（基准，偏移 = 0）</span>
          </label>
          <select v-model="form.ecg_file_id" class="select">
            <option value="">— 不绑定 —</option>
            <option v-for="f in ecgFiles" :key="f.id" :value="f.id">
              {{ f.original_filename }} {{ f.duration ? `(${f.duration.toFixed(1)}s)` : '' }}
            </option>
          </select>
        </div>

        <!-- PCG slot + offset -->
        <div class="space-y-2">
          <label class="label flex items-center gap-1">
            <Waves class="w-3.5 h-3.5 text-purple-500" />PCG 文件
          </label>
          <select v-model="form.pcg_file_id" class="select">
            <option value="">— 不绑定 —</option>
            <option v-for="f in pcgFiles" :key="f.id" :value="f.id">
              {{ f.original_filename }} {{ f.duration ? `(${f.duration.toFixed(1)}s)` : '' }}
            </option>
          </select>
          <div v-if="form.pcg_file_id" class="flex items-center gap-3">
            <label class="text-xs text-gray-500 shrink-0">PCG 偏移（秒）</label>
            <input type="range" v-model.number="form.pcg_offset"
              min="-10" max="10" step="0.001"
              class="flex-1 accent-purple-500" />
            <input type="number" v-model.number="form.pcg_offset"
              min="-3600" max="3600" step="0.001"
              class="input w-24 text-sm py-1 text-center font-mono" />
            <button class="btn-ghost btn-sm text-xs" @click="form.pcg_offset = 0">重置</button>
          </div>
        </div>

        <!-- Video slot + offset -->
        <div class="space-y-2">
          <label class="label flex items-center gap-1">
            <Video class="w-3.5 h-3.5 text-blue-500" />视频文件
          </label>
          <select v-model="form.video_file_id" class="select">
            <option value="">— 不绑定 —</option>
            <option v-for="f in videoFiles" :key="f.id" :value="f.id">
              {{ f.original_filename }} {{ f.duration ? `(${f.duration.toFixed(1)}s)` : '' }}
            </option>
          </select>
          <div v-if="form.video_file_id" class="flex items-center gap-3">
            <label class="text-xs text-gray-500 shrink-0">视频偏移（秒）</label>
            <input type="range" v-model.number="form.video_offset"
              min="-10" max="10" step="0.001"
              class="flex-1 accent-blue-500" />
            <input type="number" v-model.number="form.video_offset"
              min="-3600" max="3600" step="0.001"
              class="input w-24 text-sm py-1 text-center font-mono" />
            <button class="btn-ghost btn-sm text-xs" @click="form.video_offset = 0">重置</button>
          </div>
        </div>

        <!-- Notes -->
        <div>
          <label class="label">备注</label>
          <textarea v-model="form.notes" class="textarea" rows="2" placeholder="可选" />
        </div>
      </div>

      <template #footer>
        <button class="btn-secondary btn-sm" @click="showModal = false">取消</button>
        <button class="btn-primary btn-sm" :disabled="saving" @click="save">
          <span v-if="saving" class="spinner w-3.5 h-3.5" />
          {{ editing ? '保存' : '创建' }}
        </button>
      </template>
    </AppModal>

    <!-- Delete confirm -->
    <AppModal v-model="showDelete" title="删除关联" width="360px">
      <div class="text-center py-2">
        <div class="w-11 h-11 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-3">
          <AlertTriangle class="w-5 h-5 text-red-600" />
        </div>
        <p class="text-sm text-gray-800 font-medium">删除关联"{{ deleteTarget?.name || '未命名' }}"？</p>
        <p class="text-xs text-gray-400 mt-1">仅删除关联关系，不会删除文件本身。</p>
      </div>
      <template #footer>
        <button class="btn-secondary btn-sm" @click="showDelete = false">取消</button>
        <button class="btn-danger btn-sm" :disabled="deleting" @click="doDelete">
          <span v-if="deleting" class="spinner w-3.5 h-3.5" />删除
        </button>
      </template>
    </AppModal>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { RouterLink } from 'vue-router'
import {
  Activity, Waves, Video, Layers, Link, LinkIcon,
  PlayCircle, Pencil, Trash2, AlertTriangle,
} from 'lucide-vue-next'
import AppModal from '@/components/ui/AppModal.vue'
import { useProjectStore } from '@/store/project'
import { useToastStore } from '@/store/toast'
import { useAuthStore } from '@/store/auth'
import { useProjectPermission } from '@/composables/useProjectPermission'
import type { MediaFile } from '@/types/project'

const props = defineProps<{ projectId: string }>()

const projectStore = useProjectStore()
const toast = useToastStore()
const auth = useAuthStore()
const permission = useProjectPermission(() => props.projectId)

const authH = computed(() => auth.token ? { Authorization: `Bearer ${auth.token}` } : {})

// ── State ──────────────────────────────────────────────────────────────────
const loading = ref(true)
const associations = ref<any[]>([])
const showModal = ref(false)
const showDelete = ref(false)
const saving = ref(false)
const deleting = ref(false)
const editing = ref<any>(null)
const deleteTarget = ref<any>(null)

const form = ref({
  name: '',
  ecg_file_id: '',
  pcg_file_id: '',
  video_file_id: '',
  pcg_offset: 0,
  video_offset: 0,
  notes: '',
})

// ── File lists ─────────────────────────────────────────────────────────────
const allFiles = computed(() => projectStore.projectFiles)
const ecgFiles = computed(() => allFiles.value.filter(f => f.file_type === 'ecg'))
const pcgFiles = computed(() => allFiles.value.filter(f => f.file_type === 'pcg' || f.file_type === 'audio'))
const videoFiles = computed(() => allFiles.value.filter(f => f.file_type === 'video'))

// ── Helpers ────────────────────────────────────────────────────────────────
const shortName = (name: string) => name.length > 28 ? name.slice(0, 26) + '…' : name

// ── Load ───────────────────────────────────────────────────────────────────
const loadAssociations = async () => {
  loading.value = true
  try {
    const r = await fetch(`/api/v1/associations/project/${props.projectId}`, { headers: (authH.value as Record<string, string>) })
    loading.value = false
    if (r.ok) {
      associations.value = await r.json()
    } else {
      const err = await r.json().catch(() => ({}))
      toast.error(err.detail ?? '加载关联列表失败')
    }
  } catch {
    loading.value = false
    toast.error('加载关联列表失败（网络错误）')
  }
}

onMounted(async () => {
  // 如果项目文件列表为空（例如从其他页跳过来），先刷新一次
  if (projectStore.projectFiles.length === 0) {
    await projectStore.fetchProjectFiles(props.projectId)
  }
  await loadAssociations()
})

// ── CRUD ───────────────────────────────────────────────────────────────────
const openCreate = () => {
  editing.value = null
  form.value = { name: '', ecg_file_id: '', pcg_file_id: '', video_file_id: '', pcg_offset: 0, video_offset: 0, notes: '' }
  showModal.value = true
}

const openEdit = (assoc: any) => {
  editing.value = assoc
  form.value = {
    name: assoc.name || '',
    ecg_file_id: assoc.ecg_file_id || '',
    pcg_file_id: assoc.pcg_file_id || '',
    video_file_id: assoc.video_file_id || '',
    pcg_offset: assoc.pcg_offset,
    video_offset: assoc.video_offset,
    notes: assoc.notes || '',
  }
  showModal.value = true
}

const save = async () => {
  saving.value = true
  const body = {
    project_id: props.projectId,
    name: form.value.name || '未命名关联',
    ecg_file_id: form.value.ecg_file_id || null,
    pcg_file_id: form.value.pcg_file_id || null,
    video_file_id: form.value.video_file_id || null,
    pcg_offset: form.value.pcg_offset,
    video_offset: form.value.video_offset,
    notes: form.value.notes || null,
  }

  try {
    let r: Response
    if (editing.value) {
      r = await fetch(`/api/v1/associations/${editing.value.id}`, {
        method: 'PATCH',
        headers: { ...(authH.value as Record<string, string>), 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
    } else {
      r = await fetch('/api/v1/associations/', {
        method: 'POST',
        headers: { ...(authH.value as Record<string, string>), 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
    }
    const data = await r.json()
    if (!r.ok) throw new Error(data.detail ?? '操作失败')
    toast.success(editing.value ? '关联已更新' : '关联已创建')
    showModal.value = false
    await loadAssociations()
  } catch (e: any) {
    toast.error(e.message)
  } finally {
    saving.value = false
  }
}

const confirmDelete = (assoc: any) => {
  deleteTarget.value = assoc
  showDelete.value = true
}

const doDelete = async () => {
  if (!deleteTarget.value) return
  deleting.value = true
  const r = await fetch(`/api/v1/associations/${deleteTarget.value.id}`, {
    method: 'DELETE', headers: (authH.value as Record<string, string>),
  })
  deleting.value = false
  if (r.ok || r.status === 204) {
    toast.success('关联已删除')
    showDelete.value = false
    await loadAssociations()
  } else {
    toast.error('删除失败')
  }
}
</script>

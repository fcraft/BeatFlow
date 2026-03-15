<template>
  <div>
    <!-- Header -->
    <div class="flex items-center justify-between mb-5">
      <div>
        <h2 class="text-base font-semibold text-gray-900">文件管理</h2>
        <p class="text-xs text-gray-500 mt-0.5">上传和管理项目中的心音心电数据文件</p>
      </div>
      <div class="flex items-center gap-2">
        <!-- Upload button: only show for member+ -->
        <label v-if="permission.canUpload" class="btn-primary btn-sm cursor-pointer">
          <Upload class="w-3.5 h-3.5" />
          上传文件
          <input
            type="file"
            class="hidden"
            multiple
            accept=".wav,.mp3,.flac,.ogg,.mp4,.avi,.mov,audio/*,video/*"
            @change="onFileSelect"
          />
        </label>
        <button class="btn-secondary btn-sm" @click="showFilters = !showFilters">
          <Filter class="w-3.5 h-3.5" />
          筛选
        </button>
      </div>
    </div>

    <!-- Search bar -->
    <div class="flex items-center gap-2 mb-4">
      <div class="relative flex-1">
        <Search class="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-gray-400" />
        <input
          v-model="searchQuery"
          type="text"
          placeholder="搜索文件名..."
          class="input pl-9 w-full"
          @keydown.enter="doSearch"
        />
      </div>
      <button v-if="searchQuery" class="btn-ghost btn-sm text-gray-400" @click="searchQuery = ''; doSearch()">
        <X class="w-3.5 h-3.5" />
      </button>
    </div>

    <!-- Upload progress -->
    <div v-if="uploading" class="card px-4 py-3 mb-4 flex items-center gap-3">
      <span class="spinner w-4 h-4" />
      <span class="text-sm text-gray-600">正在上传 {{ uploadingName }}...</span>
    </div>

    <!-- Filters -->
    <div v-if="showFilters" class="card p-4 mb-4 flex flex-wrap items-end gap-4">
      <div>
        <label class="label">文件类型</label>
        <select v-model="filterType" class="select w-36">
          <option value="">全部类型</option>
          <option value="audio">音频</option>
          <option value="video">视频</option>
          <option value="ecg">ECG</option>
          <option value="pcg">PCG</option>
        </select>
      </div>
      <div>
        <label class="label">排序</label>
        <select v-model="sortBy" class="select w-32">
          <option value="name">按名称</option>
          <option value="size">按大小</option>
          <option value="date">按时间</option>
        </select>
      </div>
      <button class="btn-ghost btn-sm" @click="filterType = ''; sortBy = 'date'">重置</button>
    </div>

    <!-- File list -->
    <div v-if="loading" class="space-y-2">
      <div v-for="n in 4" :key="n" class="card p-4 flex items-center gap-4 animate-pulse">
        <div class="w-10 h-10 bg-gray-200 rounded-lg" />
        <div class="flex-1 space-y-2">
          <div class="h-3.5 bg-gray-200 rounded w-1/3" />
          <div class="h-3 bg-gray-100 rounded w-1/4" />
        </div>
      </div>
    </div>

    <div v-else-if="filteredFiles.length > 0" class="space-y-2">
      <div
        v-for="file in filteredFiles"
        :key="file.id"
        class="card px-4 py-3 flex items-center gap-4 hover:border-primary-200 hover:shadow-sm transition-all duration-150 cursor-pointer group"
        @click="goView(file.id)"
      >
        <!-- Icon -->
        <div class="w-10 h-10 rounded-lg flex items-center justify-center shrink-0"
          :class="fileIconBg(file.file_type)">
          <component :is="fileIcon(file.file_type)" class="w-5 h-5" :class="fileIconColor(file.file_type)" />
        </div>

        <!-- Info -->
        <div class="flex-1 min-w-0">
          <div class="font-medium text-sm text-gray-900 truncate">{{ file.original_filename || file.filename }}</div>
          <div class="flex items-center gap-3 mt-0.5 text-xs text-gray-400">
            <span>{{ formatSize(file.file_size) }}</span>
            <span v-if="file.duration">{{ formatDuration(file.duration) }}</span>
            <span v-if="file.sample_rate">{{ file.sample_rate }} Hz</span>
            <span>{{ formatDate(file.created_at) }}</span>
          </div>
        </div>

        <!-- Type badge -->
        <span class="shrink-0" :class="fileTypeBadge(file.file_type)">{{ file.file_type.toUpperCase() }}</span>

        <!-- Actions -->
        <div class="flex items-center gap-1 shrink-0 opacity-0 group-hover:opacity-100 transition-opacity" @click.stop>
          <button class="btn-icon btn-sm rounded-md" title="预览" @click="goView(file.id)">
            <Eye class="w-3.5 h-3.5" />
          </button>
          <button class="btn-icon btn-sm rounded-md" title="下载" @click="downloadFile(file)">
            <Download class="w-3.5 h-3.5" />
          </button>
          <!-- Share button: show for member+ -->
          <button 
            v-if="permission.canShare"
            class="btn-icon btn-sm rounded-md hover:text-blue-500 hover:bg-blue-50" 
            title="分享" 
            @click="openShare(file)"
          >
            <Share2 class="w-3.5 h-3.5" />
          </button>
          <!-- Delete button: only show for admin+ -->
          <button 
            v-if="permission.canDelete"
            class="btn-icon btn-sm rounded-md hover:text-red-500 hover:bg-red-50" 
            title="删除" 
            @click="removeFile(file)"
          >
            <Trash2 class="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    </div>

    <div v-else class="card flex flex-col items-center justify-center py-16 text-center">
      <FileX class="w-10 h-10 text-gray-300 mb-3" />
      <h4 class="font-semibold text-gray-600 mb-1">暂无文件</h4>
      <p class="text-sm text-gray-400">上传心音或心电数据文件开始分析</p>
    </div>

    <!-- Delete confirm -->
    <AppModal v-model="showDeleteFile" title="删除文件" width="380px">
      <div class="text-center py-2">
        <div class="w-11 h-11 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-3">
          <AlertTriangle class="w-5 h-5 text-red-600" />
        </div>
        <p class="text-gray-800 font-medium text-sm">删除文件"{{ deleteTarget?.filename }}"？</p>
        <p class="text-xs text-gray-500 mt-1">此操作不可撤销。</p>
      </div>
      <template #footer>
        <button class="btn-secondary btn-sm" @click="showDeleteFile = false">取消</button>
        <button class="btn-danger btn-sm" :disabled="deleting" @click="confirmDeleteFile">
          <span v-if="deleting" class="spinner w-3.5 h-3.5" />
          删除
        </button>
      </template>
    </AppModal>

    <!-- Share modal -->
    <ShareModal 
      v-model="showShare"
      :file-id="shareFile?.id"
      :file-name="shareFile?.original_filename"
      @created="onShareCreated"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Upload, Filter, Eye, Download, Trash2, FileX, AlertTriangle, Music, Video, Activity, File, Search, X, Share2 } from 'lucide-vue-next'
import AppModal from '@/components/ui/AppModal.vue'
import ShareModal from '@/components/share/ShareModal.vue'
import { useProjectStore } from '@/store/project'
import { useToastStore } from '@/store/toast'
import { useProjectPermission } from '@/composables/useProjectPermission'
import type { MediaFile } from '@/types/project'

const props = defineProps<{ projectId: string }>()
const router = useRouter()
const projectStore = useProjectStore()
const toast = useToastStore()
const permission = useProjectPermission(() => props.projectId)

const loading = ref(false)
const uploading = ref(false)
const uploadingName = ref('')
const deleting = ref(false)
const showFilters = ref(false)
const showDeleteFile = ref(false)
const showShare = ref(false)
const deleteTarget = ref<MediaFile | null>(null)
const shareFile = ref<MediaFile | null>(null)
const filterType = ref('')
const sortBy = ref('date')
const searchQuery = ref('')

const filteredFiles = computed(() => {
  let files = [...projectStore.projectFiles]
  // Client-side search (supplements server-side)
  if (searchQuery.value) {
    const q = searchQuery.value.toLowerCase()
    files = files.filter(f =>
      (f.original_filename || f.filename).toLowerCase().includes(q)
    )
  }
  if (filterType.value) files = files.filter(f => f.file_type === filterType.value)
  files.sort((a, b) => {
    if (sortBy.value === 'size') return b.file_size - a.file_size
    if (sortBy.value === 'name') return a.filename.localeCompare(b.filename)
    return new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
  })
  return files
})

const doSearch = () => {
  // Search is client-side since we already load all files
  // The computed `filteredFiles` handles filtering reactively
}

const fileIcon = (t: string) => ({ audio: Music, video: Video, ecg: Activity, pcg: Activity }[t] ?? File)
const fileIconBg = (t: string) => ({ audio: 'bg-blue-50', video: 'bg-purple-50', ecg: 'bg-red-50', pcg: 'bg-pink-50' }[t] ?? 'bg-gray-50')
const fileIconColor = (t: string) => ({ audio: 'text-blue-500', video: 'text-purple-500', ecg: 'text-red-500', pcg: 'text-pink-500' }[t] ?? 'text-gray-400')
const fileTypeBadge = (t: string) => ({ audio: 'badge-blue', video: 'badge-purple', ecg: 'badge-red', pcg: 'badge-purple' }[t] ?? 'badge-gray')

const onFileSelect = async (e: Event) => {
  const files = (e.target as HTMLInputElement).files
  if (!files?.length) return
  uploading.value = true
  let successCount = 0
  for (const file of Array.from(files)) {
    uploadingName.value = file.name
    const result = await projectStore.uploadFile(props.projectId, file)
    if (!result) {
      toast.error(`${file.name} 上传失败`)
    } else {
      successCount++
    }
  }
  uploading.value = false
  uploadingName.value = ''
  if (successCount > 0) {
    toast.success(`${successCount} 个文件上传完成（MP3/OGG/FLAC 已自动转换为 WAV）`)
    await projectStore.fetchProjectFiles(props.projectId)
  }
}

const goView = (id: string) => router.push(`/files/${id}`)

const downloadFile = async (file: MediaFile) => {
  const token = localStorage.getItem('token')
  const res = await fetch(`/api/v1/files/${file.id}/download`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) {
    toast.error('下载失败，请检查权限')
    return
  }
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = file.original_filename
  a.click()
  URL.revokeObjectURL(url)
}

const removeFile = (file: MediaFile) => {
  deleteTarget.value = file
  showDeleteFile.value = true
}

const confirmDeleteFile = async () => {
  if (!deleteTarget.value) return
  deleting.value = true
  const ok = await projectStore.deleteFile(deleteTarget.value.id)
  deleting.value = false
  if (ok) { toast.success('文件已删除'); showDeleteFile.value = false }
  else toast.error('删除失败')
}

const openShare = (file: MediaFile) => {
  shareFile.value = file
  showShare.value = true
}

const onShareCreated = () => {
  toast.success('分享已创建！')
}

const formatSize = (bytes: number) => {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 ** 2).toFixed(1)} MB`
}

const formatDuration = (s: number) => {
  const m = Math.floor(s / 60)
  const sec = Math.floor(s % 60)
  return `${m}:${sec.toString().padStart(2, '0')}`
}

const formatDate = (d: string) => new Date(d).toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })

onMounted(async () => {
  loading.value = true
  await projectStore.fetchProjectFiles(props.projectId)
  loading.value = false
})
</script>

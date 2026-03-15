<template>
  <AppModal v-model="showModal" title="分享文件" width="520px">
    <div class="space-y-4">
      <!-- Tabs for file/association type -->
      <div class="flex border-b border-gray-200">
        <button 
          :class="['px-4 py-2 text-sm font-medium transition-colors', 
            shareType === 'file' ? 'border-b-2 border-primary-500 text-primary-600' : 'text-gray-500 hover:text-gray-700']"
          @click="shareType = 'file'"
        >
          分享文件
        </button>
        <button 
          v-if="associationId"
          :class="['px-4 py-2 text-sm font-medium transition-colors',
            shareType === 'association' ? 'border-b-2 border-primary-500 text-primary-600' : 'text-gray-500 hover:text-gray-700']"
          @click="shareType = 'association'"
        >
          分享关联
        </button>
      </div>

      <!-- Share code (optional custom code) -->
      <div>
        <label class="label flex items-center justify-between">
          <span>分享码<span class="text-xs text-gray-400">(可选)</span></span>
          <button type="button" class="text-xs text-primary-600 hover:text-primary-700" @click="generateCode">
            生成
          </button>
        </label>
        <input 
          v-model="form.share_code"
          type="text"
          class="input"
          placeholder="留空自动生成，或输入 6-20 个字符"
          maxlength="20"
        />
        <p class="text-xs text-gray-400 mt-1">URL安全字符：字母、数字、下划线</p>
      </div>

      <!-- Expiry options -->
      <div>
        <label class="label">有效期</label>
        <div class="grid grid-cols-5 gap-2">
          <button 
            v-for="opt in expiryOptions" 
            :key="opt.value"
            :class="['btn btn-sm', form.expiry === opt.value ? 'btn-primary' : 'btn-ghost']"
            @click="form.expiry = opt.value"
          >
            {{ opt.label }}
          </button>
        </div>
        <!-- Custom date/time picker for "自定义" -->
        <div v-if="form.expiry === 'custom'" class="mt-3 space-y-2">
          <input 
            v-model="customExpiryDate"
            type="date"
            class="input"
          />
          <input 
            v-model="customExpiryTime"
            type="time"
            class="input"
          />
        </div>
      </div>

      <!-- Download limit (optional) -->
      <div>
        <label class="label flex items-center gap-2">
          <input 
            v-model="form.enableDownloadLimit"
            type="checkbox"
            class="w-4 h-4 accent-primary-600"
          />
          <span>限制下载次数</span>
        </label>
        <div v-if="form.enableDownloadLimit" class="mt-2">
          <input 
            v-model.number="form.max_downloads"
            type="number"
            class="input"
            min="1"
            max="1000"
            placeholder="最多下载次数"
          />
        </div>
      </div>

      <!-- Share link preview -->
      <div class="bg-gray-50 rounded-lg p-3 space-y-2">
        <p class="text-xs font-semibold text-gray-600 uppercase">分享链接</p>
        <div class="flex items-center gap-2">
          <code class="flex-1 text-xs font-mono text-gray-600 truncate">
            {{ sharePreview }}
          </code>
          <button 
            class="btn-icon btn-sm"
            title="复制"
            @click="copyLink"
          >
            <Copy class="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      <!-- Current shares list (if editing existing file) -->
      <div v-if="existingShares.length > 0" class="bg-blue-50 rounded-lg p-3 space-y-2">
        <p class="text-xs font-semibold text-blue-900">已有分享</p>
        <div class="space-y-1">
          <div 
            v-for="share in existingShares"
            :key="share.id"
            class="flex items-center justify-between text-xs text-blue-800 py-1"
          >
            <span>{{ share.share_code }} (查看: {{ share.view_count }}, 下载: {{ share.download_count }})</span>
            <button 
              class="text-red-600 hover:text-red-700"
              @click="deleteShare(share.id)"
            >
              删除
            </button>
          </div>
        </div>
      </div>
    </div>

    <template #footer>
      <button class="btn-secondary btn-sm" @click="showModal = false">取消</button>
      <button 
        class="btn-primary btn-sm"
        :disabled="loading"
        @click="createShare"
      >
        <span v-if="loading" class="spinner w-3.5 h-3.5" />
        创建分享
      </button>
    </template>
  </AppModal>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { Copy } from 'lucide-vue-next'
import AppModal from '@/components/ui/AppModal.vue'
import { useToastStore } from '@/store/toast'
import { useAuthStore } from '@/store/auth'

interface Props {
  modelValue: boolean
  fileId?: string
  associationId?: string
  fileName?: string
}

interface Emits {
  (e: 'update:modelValue', v: boolean): void
  (e: 'created'): void
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

const toast = useToastStore()
const auth = useAuthStore()

const showModal = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})

const shareType = ref<'file' | 'association'>('file')
const loading = ref(false)
const existingShares = ref<any[]>([])

const form = ref({
  share_code: '',
  expiry: '7d' as '1h' | '1d' | '7d' | '30d' | 'custom' | 'never',
  enableDownloadLimit: false,
  max_downloads: 10,
})

const customExpiryDate = ref('')
const customExpiryTime = ref('00:00')

const expiryOptions = [
  { label: '1小时', value: '1h' as const },
  { label: '1天', value: '1d' as const },
  { label: '7天', value: '7d' as const },
  { label: '30天', value: '30d' as const },
  { label: '自定义', value: 'custom' as const },
  { label: '永不过期', value: 'never' as const },
]

// Generate random share code
const generateCode = () => {
  const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_'
  let code = ''
  for (let i = 0; i < 16; i++) {
    code += chars.charAt(Math.floor(Math.random() * chars.length))
  }
  form.value.share_code = code
}

const sharePreview = computed(() => {
  const code = form.value.share_code || '[CODE]'
  if (shareType.value === 'file') {
    return `${window.location.origin}/share/file/${code}`
  } else {
    return `${window.location.origin}/share/association/${code}`
  }
})

const copyLink = async () => {
  try {
    await navigator.clipboard.writeText(sharePreview.value)
    toast.success('链接已复制到剪贴板')
  } catch {
    toast.error('复制失败')
  }
}

const fetchExistingShares = async () => {
  if (shareType.value === 'file' && props.fileId) {
    try {
      const token = localStorage.getItem('token')
      const res = await fetch(`/api/v1/files/${props.fileId}/shares`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (res.ok) {
        const data = await res.json()
        existingShares.value = data.items || []
      }
    } catch (err) {
      console.error('Failed to fetch shares:', err)
    }
  } else if (shareType.value === 'association' && props.associationId) {
    try {
      const token = localStorage.getItem('token')
      const res = await fetch(`/api/v1/associations/${props.associationId}/shares`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (res.ok) {
        const data = await res.json()
        existingShares.value = data.items || []
      }
    } catch (err) {
      console.error('Failed to fetch association shares:', err)
    }
  }
}

const deleteShare = async (shareId: string) => {
  if (!confirm('确认删除此分享？')) return
  try {
    const token = localStorage.getItem('token')
    const endpoint = shareType.value === 'file' ? 'file-shares' : 'association-shares'
    const res = await fetch(`/api/v1/${endpoint}/${shareId}`, {
      method: 'DELETE',
      headers: { Authorization: `Bearer ${token}` },
    })
    if (res.ok) {
      toast.success('分享已删除')
      await fetchExistingShares()
    } else {
      toast.error('删除失败')
    }
  } catch (err) {
    toast.error('删除失败')
    console.error(err)
  }
}

const createShare = async () => {
  if (!form.value.share_code && form.value.share_code.length > 0 && (form.value.share_code.length < 6 || form.value.share_code.length > 20)) {
    toast.error('分享码长度应在 6-20 字符之间')
    return
  }

  if (form.value.enableDownloadLimit && (!form.value.max_downloads || form.value.max_downloads < 1)) {
    toast.error('请输入有效的下载次数限制')
    return
  }

  loading.value = true

  try {
    const token = localStorage.getItem('token')
    const params = new URLSearchParams()
    
    if (form.value.share_code) {
      params.append('share_code', form.value.share_code)
    }
    
    // Handle expiry
    if (form.value.expiry === '1h') {
      params.append('expires_in_hours', '1')
    } else if (form.value.expiry === '1d') {
      params.append('expires_in_days', '1')
    } else if (form.value.expiry === '7d') {
      params.append('expires_in_days', '7')
    } else if (form.value.expiry === '30d') {
      params.append('expires_in_days', '30')
    } else if (form.value.expiry === 'custom') {
      const datetime = `${customExpiryDate.value}T${customExpiryTime.value}:00Z`
      params.append('expires_at_custom', datetime)
    }
    // 'never' = no expiry param
    
    if (form.value.enableDownloadLimit && form.value.max_downloads) {
      params.append('max_downloads', form.value.max_downloads.toString())
    }

    const endpoint = shareType.value === 'file' 
      ? `/api/v1/files/${props.fileId}/share` 
      : `/api/v1/associations/${props.associationId}/share`

    const res = await fetch(`${endpoint}?${params}`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` },
    })

    if (!res.ok) {
      const error = await res.json()
      toast.error(error.detail || '创建分享失败')
      return
    }

    const share = await res.json()
    toast.success(`分享已创建！链接: ${sharePreview.value}`)
    
    // Reset form
    form.value = {
      share_code: '',
      expiry: '7d',
      enableDownloadLimit: false,
      max_downloads: 10,
    }
    
    emit('created')
    await fetchExistingShares()
  } catch (err) {
    toast.error('创建分享失败')
    console.error(err)
  } finally {
    loading.value = false
  }
}

watch(() => props.modelValue, async (v) => {
  if (v) {
    await fetchExistingShares()
  }
})
</script>

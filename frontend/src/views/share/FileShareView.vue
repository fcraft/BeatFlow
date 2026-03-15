<template>
  <div class="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 py-8">
    <div class="max-w-4xl mx-auto px-4">
      <!-- Loading state -->
      <div v-if="loading" class="space-y-4">
        <div class="card p-8 space-y-4">
          <div class="h-8 bg-gray-200 rounded w-1/3 animate-pulse" />
          <div class="h-4 bg-gray-200 rounded w-2/3 animate-pulse" />
          <div class="h-96 bg-gray-200 rounded animate-pulse" />
        </div>
      </div>

      <!-- Error state -->
      <div v-else-if="error" class="card bg-red-50 border border-red-200 p-8 text-center">
        <AlertTriangle class="w-12 h-12 text-red-600 mx-auto mb-3" />
        <h2 class="text-xl font-semibold text-red-900 mb-2">无法加载分享</h2>
        <p class="text-red-700">{{ error }}</p>
        <RouterLink to="/" class="btn-primary btn-sm mt-4">
          返回首页
        </RouterLink>
      </div>

      <!-- Success state -->
      <div v-else-if="share && file" class="space-y-6">
        <!-- Header -->
        <div class="card border-l-4 border-primary-500 bg-gradient-to-r from-blue-50 to-transparent p-6">
          <div class="flex items-start justify-between">
            <div>
              <h1 class="text-2xl font-bold text-gray-900 mb-1">文件分享</h1>
              <p class="text-sm text-gray-600">来自 BeatFlow 的分享文件</p>
            </div>
            <component :is="fileIcon" class="w-8 h-8 text-primary-600" />
          </div>
        </div>

        <!-- File info -->
        <div class="card p-6 space-y-4">
          <div>
            <h2 class="text-lg font-semibold text-gray-900 mb-2">{{ file.original_filename }}</h2>
            <div class="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
              <div>
                <span class="text-gray-500">文件类型</span>
                <p class="font-medium text-gray-900">{{ file.file_type.toUpperCase() }}</p>
              </div>
              <div>
                <span class="text-gray-500">文件大小</span>
                <p class="font-medium text-gray-900">{{ formatSize(file.file_size) }}</p>
              </div>
              <div v-if="file.duration">
                <span class="text-gray-500">时长</span>
                <p class="font-medium text-gray-900">{{ formatDuration(file.duration) }}</p>
              </div>
              <div v-if="file.sample_rate">
                <span class="text-gray-500">采样率</span>
                <p class="font-medium text-gray-900">{{ file.sample_rate }} Hz</p>
              </div>
            </div>
          </div>
        </div>

        <!-- File preview -->
        <div class="card p-6 space-y-4">
          <h3 class="font-semibold text-gray-900">文件预览</h3>
          
          <!-- Audio player -->
          <div v-if="['audio', 'ecg', 'pcg'].includes(file.file_type)" class="bg-gray-100 rounded-lg p-4">
            <audio 
              controls 
              class="w-full"
              :src="`/api/v1/share/file/${share_code}/stream`"
            >
              您的浏览器不支持音频播放
            </audio>
          </div>

          <!-- Video player -->
          <div v-else-if="file.file_type === 'video'" class="bg-gray-100 rounded-lg overflow-hidden">
            <video 
              controls 
              class="w-full"
              :src="`/api/v1/share/file/${share_code}/stream`"
            >
              您的浏览器不支持视频播放
            </video>
          </div>

          <!-- Unsupported format -->
          <div v-else class="bg-gray-100 rounded-lg p-4 text-center text-gray-500">
            <FileX class="w-8 h-8 mx-auto mb-2 opacity-50" />
            <p class="text-sm">此文件类型不支持在线预览</p>
          </div>
        </div>

        <!-- Download and stats -->
        <div class="grid md:grid-cols-2 gap-6">
          <!-- Download section -->
          <div class="card p-6 space-y-4">
            <h3 class="font-semibold text-gray-900">下载文件</h3>
            <button 
              class="btn-primary w-full"
              :disabled="downloading"
              @click="downloadFile"
            >
              <span v-if="downloading" class="spinner w-4 h-4" />
              <Download class="w-4 h-4" v-else />
              {{ downloading ? '下载中...' : '下载文件' }}
            </button>
            <div v-if="share.max_downloads" class="text-xs text-gray-600">
              下载次数: {{ share.download_count }} / {{ share.max_downloads }}
            </div>
          </div>

          <!-- Share stats -->
          <div class="card p-6 space-y-4">
            <h3 class="font-semibold text-gray-900">分享信息</h3>
            <div class="space-y-2">
              <div class="flex justify-between">
                <span class="text-gray-600">查看次数</span>
                <span class="font-medium text-gray-900">{{ share.view_count }}</span>
              </div>
              <div class="flex justify-between">
                <span class="text-gray-600">下载次数</span>
                <span class="font-medium text-gray-900">{{ share.download_count }}</span>
              </div>
              <div v-if="share.expires_at" class="flex justify-between">
                <span class="text-gray-600">过期时间</span>
                <span :class="['font-medium', isExpired ? 'text-red-600' : 'text-gray-900']">
                  {{ formatExpiry(share.expires_at) }}
                </span>
              </div>
              <div v-else class="flex justify-between">
                <span class="text-gray-600">有效期</span>
                <span class="font-medium text-gray-900">永不过期</span>
              </div>
            </div>
          </div>
        </div>

        <!-- Footer -->
        <div class="text-center text-sm text-gray-500">
          <p>这是通过 BeatFlow 分享的文件。<RouterLink to="/" class="text-primary-600 hover:text-primary-700">访问平台</RouterLink></p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { Download, AlertTriangle, FileX, Music, Video, Activity, File } from 'lucide-vue-next'

const route = useRoute()
const share_code = route.params.code as string

const loading = ref(true)
const downloading = ref(false)
const error = ref('')
const share = ref<any>(null)
const file = ref<any>(null)

const isExpired = computed(() => {
  if (!share.value?.expires_at) return false
  return new Date(share.value.expires_at) < new Date()
})

const fileIcon = computed(() => {
  if (!file.value) return File
  const iconMap = { audio: Music, video: Video, ecg: Activity, pcg: Activity }
  return iconMap[file.value.file_type as keyof typeof iconMap] ?? File
})

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

const formatExpiry = (dateStr: string) => {
  const date = new Date(dateStr)
  const now = new Date()
  const diffMs = date.getTime() - now.getTime()
  
  if (diffMs < 0) return '已过期'
  
  const diffHours = Math.floor(diffMs / (1000 * 60 * 60))
  if (diffHours < 1) {
    const diffMins = Math.floor(diffMs / (1000 * 60))
    return `${diffMins} 分钟后过期`
  }
  if (diffHours < 24) return `${diffHours} 小时后过期`
  
  const diffDays = Math.floor(diffHours / 24)
  return `${diffDays} 天后过期`
}

const loadShare = async () => {
  try {
    loading.value = true
    const res = await fetch(`/api/v1/share/file/${share_code}`)
    
    if (!res.ok) {
      const data = await res.json()
      throw new Error(data.detail || '分享不存在或已过期')
    }
    
    const data = await res.json()
    share.value = data.share
    file.value = data.file
  } catch (err: any) {
    error.value = err.message || '加载分享失败'
  } finally {
    loading.value = false
  }
}

const downloadFile = async () => {
  try {
    downloading.value = true
    const res = await fetch(`/api/v1/share/file/${share_code}/download`)
    
    if (!res.ok) {
      throw new Error('下载失败')
    }
    
    const blob = await res.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = file.value?.original_filename || 'file'
    a.click()
    URL.revokeObjectURL(url)
    
    // Refresh share stats
    await loadShare()
  } catch (err: any) {
    error.value = err.message
  } finally {
    downloading.value = false
  }
}

onMounted(() => {
  loadShare()
})
</script>

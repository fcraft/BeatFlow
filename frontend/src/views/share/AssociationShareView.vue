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
      <div v-else-if="share && association" class="space-y-6">
        <!-- Header -->
        <div class="card border-l-4 border-indigo-500 bg-gradient-to-r from-indigo-50 to-transparent p-6">
          <div class="flex items-start justify-between">
            <div>
              <h1 class="text-2xl font-bold text-gray-900 mb-1">关联分享</h1>
              <p class="text-sm text-gray-600">多轨同步信号分享</p>
            </div>
            <Layers class="w-8 h-8 text-indigo-600" />
          </div>
        </div>

        <!-- Association info -->
        <div class="card p-6 space-y-4">
          <h2 class="text-lg font-semibold text-gray-900">
            {{ association.name || '未命名关联' }}
          </h2>
          
          <!-- Files in association -->
          <div class="space-y-3">
            <!-- ECG -->
            <div v-if="association.files.ecg" class="flex items-start gap-3 p-3 bg-red-50 rounded-lg">
              <Activity class="w-5 h-5 text-red-500 mt-1 shrink-0" />
              <div class="flex-1 min-w-0">
                <p class="text-sm font-medium text-gray-900 truncate">ECG: {{ association.files.ecg.original_filename }}</p>
                <p class="text-xs text-gray-500">{{ formatSize(association.files.ecg.file_size) }} · {{ formatDuration(association.files.ecg.duration) }}</p>
              </div>
            </div>
            <div v-else class="flex items-center gap-3 p-3 bg-gray-50 rounded-lg text-gray-400">
              <Activity class="w-5 h-5" />
              <span class="text-sm">无 ECG 文件</span>
            </div>

            <!-- PCG -->
            <div v-if="association.files.pcg" class="flex items-start gap-3 p-3 bg-purple-50 rounded-lg">
              <Waves class="w-5 h-5 text-purple-500 mt-1 shrink-0" />
              <div class="flex-1 min-w-0">
                <div class="flex items-center gap-1">
                  <p class="text-sm font-medium text-gray-900 truncate">PCG: {{ association.files.pcg.original_filename }}</p>
                  <span v-if="association.pcg_offset !== 0" class="text-xs text-gray-500">
                    ({{ association.pcg_offset > 0 ? '+' : '' }}{{ association.pcg_offset.toFixed(3) }}s)
                  </span>
                </div>
                <p class="text-xs text-gray-500">{{ formatSize(association.files.pcg.file_size) }} · {{ formatDuration(association.files.pcg.duration) }}</p>
              </div>
            </div>
            <div v-else class="flex items-center gap-3 p-3 bg-gray-50 rounded-lg text-gray-400">
              <Waves class="w-5 h-5" />
              <span class="text-sm">无 PCG 文件</span>
            </div>

            <!-- Video -->
            <div v-if="association.files.video" class="flex items-start gap-3 p-3 bg-blue-50 rounded-lg">
              <Video class="w-5 h-5 text-blue-500 mt-1 shrink-0" />
              <div class="flex-1 min-w-0">
                <div class="flex items-center gap-1">
                  <p class="text-sm font-medium text-gray-900 truncate">Video: {{ association.files.video.original_filename }}</p>
                  <span v-if="association.video_offset !== 0" class="text-xs text-gray-500">
                    ({{ association.video_offset > 0 ? '+' : '' }}{{ association.video_offset.toFixed(3) }}s)
                  </span>
                </div>
                <p class="text-xs text-gray-500">{{ formatSize(association.files.video.file_size) }}</p>
              </div>
            </div>
            <div v-else class="flex items-center gap-3 p-3 bg-gray-50 rounded-lg text-gray-400">
              <Video class="w-5 h-5" />
              <span class="text-sm">无视频文件</span>
            </div>
          </div>
        </div>

        <!-- File players -->
        <div class="space-y-4">
          <!-- ECG player -->
          <div v-if="association.files.ecg && stream_urls.ecg" class="card p-6 space-y-3">
            <h3 class="font-semibold text-gray-900 flex items-center gap-2">
              <Activity class="w-4 h-4 text-red-500" />
              {{ association.files.ecg.original_filename }}
            </h3>
            <audio 
              controls 
              class="w-full"
              :src="stream_urls.ecg"
            >
              您的浏览器不支持音频播放
            </audio>
          </div>

          <!-- PCG player -->
          <div v-if="association.files.pcg && stream_urls.pcg" class="card p-6 space-y-3">
            <h3 class="font-semibold text-gray-900 flex items-center gap-2">
              <Waves class="w-4 h-4 text-purple-500" />
              {{ association.files.pcg.original_filename }}
            </h3>
            <audio 
              controls 
              class="w-full"
              :src="stream_urls.pcg"
            >
              您的浏览器不支持音频播放
            </audio>
          </div>

          <!-- Video player -->
          <div v-if="association.files.video && stream_urls.video" class="card p-6 space-y-3">
            <h3 class="font-semibold text-gray-900 flex items-center gap-2">
              <Video class="w-4 h-4 text-blue-500" />
              {{ association.files.video.original_filename }}
            </h3>
            <video 
              controls 
              class="w-full rounded"
              :src="stream_urls.video"
            >
              您的浏览器不支持视频播放
            </video>
          </div>
        </div>

        <!-- Share stats -->
        <div class="card p-6 space-y-4">
          <h3 class="font-semibold text-gray-900">分享信息</h3>
          <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div>
              <span class="text-sm text-gray-600">查看次数</span>
              <p class="text-2xl font-semibold text-gray-900">{{ share.view_count }}</p>
            </div>
            <div>
              <span class="text-sm text-gray-600">下载次数</span>
              <p class="text-2xl font-semibold text-gray-900">{{ share.download_count }}</p>
            </div>
            <div v-if="share.max_downloads">
              <span class="text-sm text-gray-600">下载限制</span>
              <p class="text-2xl font-semibold text-gray-900">{{ share.download_count }}/{{ share.max_downloads }}</p>
            </div>
            <div v-if="share.expires_at">
              <span class="text-sm text-gray-600">过期时间</span>
              <p :class="['text-lg font-semibold', isExpired ? 'text-red-600' : 'text-gray-900']">
                {{ formatExpiry(share.expires_at) }}
              </p>
            </div>
          </div>
        </div>

        <!-- Footer -->
        <div class="text-center text-sm text-gray-500">
          <p>这是通过 BeatFlow 分享的文件关联。<RouterLink to="/" class="text-primary-600 hover:text-primary-700">访问平台</RouterLink></p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { AlertTriangle, Layers, Activity, Video, Waves } from 'lucide-vue-next'

const route = useRoute()
const share_code = route.params.code as string

const loading = ref(true)
const error = ref('')
const share = ref<any>(null)
const association = ref<any>(null)
const stream_urls = ref<Record<string, string>>({})

const isExpired = computed(() => {
  if (!share.value?.expires_at) return false
  return new Date(share.value.expires_at) < new Date()
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
    const res = await fetch(`/api/v1/share/association/${share_code}`)
    
    if (!res.ok) {
      const data = await res.json()
      throw new Error(data.detail || '分享不存在或已过期')
    }
    
    const data = await res.json()
    share.value = data.share
    association.value = data.association
    stream_urls.value = data.stream_urls || {}
  } catch (err: any) {
    error.value = err.message || '加载分享失败'
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadShare()
})
</script>

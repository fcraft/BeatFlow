<template>
  <div class="file-detail">
    <!-- 基本信息部分 -->
    <div class="basic-info">
      <div class="file-header">
        <div class="file-icon">
          <i :class="getFileTypeIcon(file?.file_type || '')" class="icon-large"></i>
        </div>
        <div class="file-title">
          <h3>{{ file?.original_filename || file?.filename }}</h3>
          <div class="file-tags">
            <Tag :value="file?.file_type?.toUpperCase() || 'OTHER'" 
                 :severity="getFileTypeSeverity(file?.file_type || '')" />
            <Tag value="详情" severity="info" />
          </div>
        </div>
      </div>

      <div class="info-grid">
        <div class="info-item">
          <label>文件大小</label>
          <span>{{ formatFileSize(file?.file_size || 0) }}</span>
        </div>
        <div class="info-item">
          <label>创建时间</label>
          <span>{{ formatDateTime(file?.created_at) }}</span>
        </div>
        <div class="info-item">
          <label>最后更新时间</label>
          <span>{{ formatDateTime(file?.updated_at) }}</span>
        </div>
        <div class="info-item">
          <label>文件ID</label>
          <span class="mono">{{ file?.id.slice(0, 12) }}...</span>
        </div>
      </div>
    </div>

    <!-- 音频/视频详细信息 -->
    <div v-if="isMediaFile" class="media-info">
      <h4>媒体信息</h4>
      <div class="info-grid">
        <template v-if="file?.duration">
          <div class="info-item">
            <label>时长</label>
            <span>{{ formatDuration(file.duration) }}</span>
          </div>
        </template>
        <template v-if="file?.sample_rate">
          <div class="info-item">
            <label>采样率</label>
            <span>{{ file.sample_rate.toLocaleString() }} Hz</span>
          </div>
        </template>
        <template v-if="file?.channels">
          <div class="info-item">
            <label>声道数</label>
            <span>{{ file.channels }}</span>
          </div>
        </template>
        <template v-if="file?.bit_depth">
          <div class="info-item">
            <label>位深度</label>
            <span>{{ file.bit_depth }} bit</span>
          </div>
        </template>
        <template v-if="file?.width && file?.height">
          <div class="info-item">
            <label>分辨率</label>
            <span>{{ file.width }} × {{ file.height }}</span>
          </div>
        </template>
        <template v-if="file?.frame_rate">
          <div class="info-item">
            <label>帧率</label>
            <span>{{ file.frame_rate }} fps</span>
          </div>
        </template>
      </div>
    </div>

    <!-- 波形预览 -->
    <div v-if="isAudioFile && showWaveform" class="waveform-section">
      <h4>波形预览</h4>
      <div ref="waveformContainer" class="waveform-container">
        <div v-if="loadingWaveform" class="waveform-loading">
          <i class="pi pi-spin pi-spinner"></i>
          <span>加载波形...</span>
        </div>
      </div>
      <div class="waveform-controls">
        <Button
          icon="pi pi-play"
          :label="isPlaying ? '暂停' : '播放'"
          @click="togglePlay"
          size="small"
        />
        <div class="volume-control">
          <label>音量</label>
          <Slider
            v-model="volume"
            :min="0"
            :max="100"
            style="width: 120px"
          />
        </div>
        <div class="time-display">
          <span>{{ formatTime(currentTime) }} / {{ formatTime(duration) }}</span>
        </div>
      </div>
    </div>

    <!-- 操作按钮 -->
    <div class="action-section">
      <div class="action-buttons">
        <Button
          label="预览"
          icon="pi pi-eye"
          @click="handlePreview"
          severity="info"
        />
        <Button
          label="下载"
          icon="pi pi-download"
          @click="handleDownload"
          severity="secondary"
        />
        <Button
          label="标记"
          icon="pi pi-tags"
          @click="handleAnnotate"
          severity="help"
        />
        <Button
          label="分析"
          icon="pi pi-chart-line"
          @click="handleAnalyze"
          severity="warning"
        />
        <Button
          label="删除"
          icon="pi pi-trash"
          @click="handleDelete"
          severity="danger"
        />
      </div>
    </div>

    <!-- 元数据显示 -->
    <div v-if="hasMetadata" class="metadata-section">
      <h4>元数据</h4>
      <div class="metadata-content">
        <pre>{{ formattedMetadata }}</pre>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useToast } from 'primevue/usetoast'
import type { MediaFile } from '@/types/project'
import { useProjectStore } from '@/store/project'
import Tag from 'primevue/tag'
import Button from 'primevue/button'
import Slider from 'primevue/slider'

interface Props {
  file: MediaFile | null
}

const props = defineProps<Props>()
const emit = defineEmits<{ deleted: [] }>()
const toast = useToast()
const projectStore = useProjectStore()

// 波形相关状态
const waveformContainer = ref<HTMLElement>()
const loadingWaveform = ref(false)
const isPlaying = ref(false)
const currentTime = ref(0)
const duration = ref(0)
const volume = ref(80)
let wavesurfer: any = null

// 计算属性
const isMediaFile = computed(() => {
  return props.file?.file_type === 'audio' || 
         props.file?.file_type === 'video' ||
         props.file?.file_type === 'ecg' ||
         props.file?.file_type === 'pcg'
})

const isAudioFile = computed(() => {
  return props.file?.file_type === 'audio' || 
         props.file?.file_type === 'ecg' || 
         props.file?.file_type === 'pcg'
})

const showWaveform = computed(() => {
  return isAudioFile.value && !loadingWaveform.value
})

const hasMetadata = computed(() => {
  return props.file?.metadata && Object.keys(props.file.metadata).length > 0
})

const formattedMetadata = computed(() => {
  if (!props.file?.metadata) return '{}'
  return JSON.stringify(props.file.metadata, null, 2)
})

// 方法
const getFileTypeIcon = (fileType: string) => {
  switch (fileType) {
    case 'audio':
      return 'pi pi-file-audio text-blue-500'
    case 'video':
      return 'pi pi-file-video text-purple-500'
    case 'ecg':
      return 'pi pi-heart text-red-500'
    case 'pcg':
      return 'pi pi-heart text-pink-500'
    default:
      return 'pi pi-file text-gray-500'
  }
}

const getFileTypeSeverity = (fileType: string) => {
  switch (fileType) {
    case 'audio':
      return 'info'
    case 'video':
      return 'help'
    case 'ecg':
      return 'danger'
    case 'pcg':
      return 'warning'
    default:
      return 'secondary'
  }
}

const formatFileSize = (bytes: number) => {
  const units = ['B', 'KB', 'MB', 'GB']
  let size = bytes
  let unitIndex = 0
  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024
    unitIndex++
  }
  return `${size.toFixed(1)} ${units[unitIndex]}`
}

const formatDateTime = (dateString?: string) => {
  if (!dateString) return '未知'
  const date = new Date(dateString)
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  })
}

const formatDuration = (seconds: number) => {
  const minutes = Math.floor(seconds / 60)
  const remainingSeconds = Math.floor(seconds % 60)
  return `${minutes}:${remainingSeconds.toString().padStart(2, '0')}`
}

const formatTime = (time: number) => {
  const minutes = Math.floor(time / 60)
  const seconds = Math.floor(time % 60)
  return `${minutes}:${seconds.toString().padStart(2, '0')}`
}

// 波形相关方法
const initializeWaveform = async () => {
  if (!isAudioFile.value || !props.file || loadingWaveform.value) return

  loadingWaveform.value = true
  
  try {
    // 动态导入 wavesurfer.js
    const Wavesurfer = await import('wavesurfer.js')
    
    if (waveformContainer.value) {
      wavesurfer = Wavesurfer.default.create({
        container: waveformContainer.value,
        waveColor: '#667eea',
        progressColor: '#764ba2',
        cursorColor: '#4a5568',
        barWidth: 2,
        barRadius: 3,
        cursorWidth: 1,
        height: 100,
        barGap: 3,
        plugins: []
      })

      // 加载音频
      const token = localStorage.getItem('token')
      const audioUrl = `/api/v1/files/${props.file.id}/stream?token=${token}`
      
      wavesurfer.load(audioUrl)

      // 事件监听
      wavesurfer.on('ready', () => {
        duration.value = wavesurfer.getDuration()
        loadingWaveform.value = false
      })

      wavesurfer.on('audioprocess', () => {
        currentTime.value = wavesurfer.getCurrentTime()
      })

      wavesurfer.on('finish', () => {
        isPlaying.value = false
      })
    }
  } catch (error) {
    console.error('初始化波形失败:', error)
    loadingWaveform.value = false
    toast.add({
      severity: 'error',
      summary: '波形加载失败',
      detail: '无法加载音频波形',
      life: 3000
    })
  }
}

const togglePlay = () => {
  if (!wavesurfer) return
  
  if (isPlaying.value) {
    wavesurfer.pause()
  } else {
    wavesurfer.play()
  }
  isPlaying.value = !isPlaying.value
}

// 操作处理方法
const handlePreview = () => {
  toast.add({
    severity: 'info',
    summary: '预览',
    detail: '打开预览面板',
    life: 2000
  })
}

const handleDownload = () => {
  if (!props.file) return
  const token = localStorage.getItem('token')
  const url = `/api/v1/files/${props.file.id}/stream?token=${token}`
  const a = document.createElement('a')
  a.href = url
  a.download = props.file.original_filename || props.file.filename
  a.click()
  toast.add({
    severity: 'success',
    summary: '下载开始',
    detail: '文件下载已开始',
    life: 2000
  })
}

const handleAnnotate = () => {
  toast.add({
    severity: 'info',
    summary: '标记',
    detail: '打开标记工具',
    life: 2000
  })
}

const handleAnalyze = () => {
  toast.add({
    severity: 'warn',
    summary: '分析',
    detail: '开始分析文件',
    life: 2000
  })
}

const handleDelete = async () => {
  if (!props.file || !confirm(`确定要删除文件 "${props.file.filename}" 吗？`)) return
  const ok = await projectStore.deleteFile(props.file.id)
  if (ok) {
    toast.add({
      severity: 'success',
      summary: '已删除',
      detail: '文件已删除',
      life: 2000
    })
    emit('deleted')
  } else {
    toast.add({
      severity: 'error',
      summary: '删除失败',
      detail: '无法删除文件',
      life: 3000
    })
  }
}

// 生命周期
onMounted(() => {
  if (isAudioFile.value) {
    initializeWaveform()
  }
})

onUnmounted(() => {
  if (wavesurfer) {
    wavesurfer.destroy()
  }
})
</script>

<style scoped>
.file-detail {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.basic-info {
  background: #f9fafb;
  border-radius: 8px;
  padding: 20px;
}

.file-header {
  display: flex;
  align-items: center;
  gap: 20px;
  margin-bottom: 24px;
}

.file-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 80px;
  height: 80px;
  background: white;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.icon-large {
  font-size: 2.5rem;
}

.file-title {
  flex: 1;
}

.file-title h3 {
  margin: 0 0 12px 0;
  font-size: 1.5rem;
  font-weight: 600;
  color: #1a202c;
}

.file-tags {
  display: flex;
  gap: 8px;
}

.info-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 20px;
}

.info-item {
  display: flex;
  flex-direction: column;
}

.info-item label {
  font-weight: 600;
  color: #4a5568;
  margin-bottom: 6px;
  font-size: 0.875rem;
}

.info-item span {
  color: #1a202c;
  font-size: 1rem;
}

.info-item .mono {
  font-family: 'Monaco', 'Courier New', monospace;
  font-size: 0.875rem;
  color: #718096;
}

.media-info {
  background: #f9fafb;
  border-radius: 8px;
  padding: 20px;
}

.media-info h4 {
  margin: 0 0 16px 0;
  font-size: 1.125rem;
  font-weight: 600;
  color: #1a202c;
}

.waveform-section {
  background: #f9fafb;
  border-radius: 8px;
  padding: 20px;
}

.waveform-section h4 {
  margin: 0 0 16px 0;
  font-size: 1.125rem;
  font-weight: 600;
  color: #1a202c;
}

.waveform-container {
  height: 120px;
  background: white;
  border-radius: 6px;
  margin-bottom: 16px;
  position: relative;
  overflow: hidden;
}

.waveform-loading {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  display: flex;
  align-items: center;
  gap: 12px;
  color: #718096;
}

.waveform-controls {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
}

.volume-control {
  display: flex;
  align-items: center;
  gap: 12px;
  flex: 1;
  max-width: 200px;
}

.volume-control label {
  font-weight: 600;
  color: #4a5568;
  font-size: 0.875rem;
}

.time-display {
  font-family: 'Monaco', 'Courier New', monospace;
  color: #718096;
  font-size: 0.875rem;
}

.action-section {
  background: #f9fafb;
  border-radius: 8px;
  padding: 20px;
}

.action-buttons {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.metadata-section {
  background: #f9fafb;
  border-radius: 8px;
  padding: 20px;
}

.metadata-section h4 {
  margin: 0 0 16px 0;
  font-size: 1.125rem;
  font-weight: 600;
  color: #1a202c;
}

.metadata-content {
  background: white;
  border-radius: 6px;
  padding: 20px;
  max-height: 300px;
  overflow: auto;
}

.metadata-content pre {
  margin: 0;
  font-family: 'Monaco', 'Courier New', monospace;
  font-size: 0.875rem;
  line-height: 1.5;
  color: #4a5568;
  white-space: pre-wrap;
  word-break: break-all;
}
</style>
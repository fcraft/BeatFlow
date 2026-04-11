<template>
  <AppSelect
    :model-value="modelValue"
    :options="fileOptions"
    :placeholder="placeholder"
    :icon="FileAudio"
    :dark="dark"
    :searchable="true"
    search-placeholder="搜索文件名…"
    block
    @update:model-value="onSelect"
  />
</template>

<script setup lang="ts">
import { computed, watch } from 'vue'
import { FileAudio } from 'lucide-vue-next'
import AppSelect, { type SelectOption } from '@/components/ui/AppSelect.vue'
import { useProjectStore } from '@/store/project'

const FILE_TYPE_LABELS: Record<string, string> = {
  audio: 'Audio', video: 'Video', ecg: 'ECG', pcg: 'PCG', other: '其他',
}

const props = withDefaults(defineProps<{
  modelValue: string
  projectId: string
  placeholder?: string
  dark?: boolean
  /** 仅显示指定类型的文件，如 'ecg' | 'pcg' | 'audio' */
  fileType?: string
}>(), {
  placeholder: '请选择文件',
  dark: false,
})

const emit = defineEmits<{
  'update:modelValue': [value: string]
}>()

const projectStore = useProjectStore()

const fileOptions = computed<SelectOption[]>(() => {
  let files = projectStore.projectFiles
  if (props.fileType) {
    files = files.filter(f => f.file_type === props.fileType)
  }
  return files.map(f => ({
    value: f.id,
    label: f.original_filename || f.filename,
    badge: FILE_TYPE_LABELS[f.file_type] ?? f.file_type,
  }))
})

function onSelect(val: string | number) {
  emit('update:modelValue', String(val))
}

// 当 projectId 变化时，自动加载该项目的文件列表
watch(() => props.projectId, (pid) => {
  if (pid) projectStore.fetchProjectFiles(pid)
}, { immediate: true })
</script>

<template>
  <AppSelect
    :model-value="modelValue"
    :options="projectOptions"
    :placeholder="placeholder"
    :icon="FolderOpen"
    :dark="dark"
    :searchable="true"
    search-placeholder="搜索项目..."
    block
    @update:model-value="onSelect"
  >
    <template #footer="{ close }">
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
          新建项目
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
            @keydown.enter="createAndSelect(close)"
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
              @click="createAndSelect(close)"
            >
              <span v-if="creating" class="spinner w-3 h-3" />
              创建并选择
            </button>
          </div>
        </div>
      </template>
    </template>
  </AppSelect>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick, onMounted } from 'vue'
import { FolderOpen, Plus } from 'lucide-vue-next'
import AppSelect, { type SelectOption } from '@/components/ui/AppSelect.vue'
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

const showCreate = ref(false)
const newName = ref('')
const creating = ref(false)
const createInputRef = ref<HTMLInputElement | null>(null)

const projectOptions = computed<SelectOption[]>(() =>
  projectStore.projects.map(p => ({
    value: p.id,
    label: p.name,
    badge: p.is_public ? '公开' : undefined,
  }))
)

function onSelect(val: string | number) {
  emit('update:modelValue', String(val))
}

async function createAndSelect(close: () => void) {
  if (!newName.value.trim()) return
  creating.value = true
  const p = await projectStore.createProject({ name: newName.value.trim() })
  creating.value = false
  if (p) {
    toast.success(`项目 "${p.name}" 已创建`)
    emit('update:modelValue', p.id)
    newName.value = ''
    showCreate.value = false
    close()
  } else {
    toast.error('创建项目失败')
  }
}

watch(showCreate, (v) => {
  if (v) {
    newName.value = ''
    nextTick(() => createInputRef.value?.focus())
  }
})

onMounted(() => {
  if (!projectStore.projects.length) projectStore.fetchProjects()
})
</script>

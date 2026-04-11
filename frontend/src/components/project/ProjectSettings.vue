<template>
  <div class="max-w-xl">
    <!-- Basic info: only show save button if admin -->
    <section class="mb-8">
      <h3 class="text-sm font-semibold text-gray-900 mb-4">基本信息</h3>
      <div class="space-y-4">
        <div>
          <label class="label">项目名称</label>
          <input v-model="form.name" type="text" class="input" :disabled="!permission.isAdmin" />
        </div>
        <div>
          <label class="label">项目描述</label>
          <textarea v-model="form.description" rows="3" class="textarea" :disabled="!permission.isAdmin" />
        </div>
        <AppCheckbox
          v-model="form.is_public"
          :disabled="!permission.isAdmin"
          :label="form.is_public ? '公开项目（所有人可查看）' : '私有项目（仅成员可查看）'"
        />
      </div>
      <!-- Save button: only show for admin -->
      <button 
        v-if="permission.isAdmin"
        class="btn-primary btn-sm mt-5" 
        :disabled="saving" 
        @click="save"
      >
        <span v-if="saving" class="spinner w-3.5 h-3.5" />
        <Save class="w-3.5 h-3.5" v-else />
        保存更改
      </button>
    </section>

    <div class="divider" />

    <!-- Danger zone: only show for admin -->
    <section v-if="permission.isAdmin">
      <h3 class="text-sm font-semibold text-red-600 mb-2">危险操作</h3>
      <p class="text-sm text-gray-500 mb-4">删除项目将永久移除所有相关文件和数据，此操作不可撤销。</p>
      <button class="btn-danger btn-sm" @click="showConfirm = true">
        <Trash2 class="w-3.5 h-3.5" />
        删除项目
      </button>
    </section>

    <AppModal v-model="showConfirm" title="确认删除项目" width="400px">
      <div class="text-center py-2">
        <div class="w-12 h-12 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-4">
          <AlertTriangle class="w-6 h-6 text-red-600" />
        </div>
        <p class="font-medium text-gray-800 mb-1">删除"{{ project?.name }}"</p>
        <p class="text-sm text-gray-500">此操作不可撤销，所有文件和数据将被永久删除。</p>
      </div>
      <template #footer>
        <button class="btn-secondary btn-sm" @click="showConfirm = false">取消</button>
        <button class="btn-danger btn-sm" :disabled="deleting" @click="doDelete">
          <span v-if="deleting" class="spinner w-3.5 h-3.5" />
          确认删除
        </button>
      </template>
    </AppModal>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { Save, Trash2, AlertTriangle } from 'lucide-vue-next'
import AppModal from '@/components/ui/AppModal.vue'
import AppCheckbox from '@/components/ui/AppCheckbox.vue'
import { useProjectStore } from '@/store/project'
import { useToastStore } from '@/store/toast'
import { useProjectPermission } from '@/composables/useProjectPermission'

const props = defineProps<{ project: any; projectId: string }>()
const emit = defineEmits(['update'])

const router = useRouter()
const projectStore = useProjectStore()
const toast = useToastStore()
const permission = useProjectPermission(() => props.projectId)

const saving = ref(false)
const deleting = ref(false)
const showConfirm = ref(false)

const form = ref({ name: '', description: '', is_public: false })

watch(() => props.project, p => {
  if (p) form.value = { name: p.name ?? '', description: p.description ?? '', is_public: p.is_public ?? false }
}, { immediate: true })

const save = async () => {
  if (!props.project?.id) return
  saving.value = true
  const updated = await projectStore.updateProject(props.project.id, form.value)
  saving.value = false
  if (updated) { toast.success('保存成功'); emit('update', updated) }
  else toast.error('保存失败')
}

const doDelete = async () => {
  if (!props.project?.id) return
  deleting.value = true
  const ok = await projectStore.deleteProject(props.project.id)
  deleting.value = false
  if (ok) { toast.success('项目已删除'); router.push('/projects') }
  else toast.error('删除失败')
}
</script>

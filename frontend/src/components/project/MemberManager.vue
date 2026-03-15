<template>
  <div>
    <div class="flex items-center justify-between mb-5">
      <div>
        <h2 class="text-base font-semibold text-gray-900">项目成员</h2>
        <p class="text-xs text-gray-500 mt-0.5">管理项目成员及其权限</p>
      </div>
      <button class="btn-primary btn-sm" @click="showAdd = true">
        <UserPlus class="w-3.5 h-3.5" />
        邀请成员
      </button>
    </div>

    <div v-if="loading" class="space-y-2">
      <div v-for="n in 3" :key="n" class="card p-4 flex items-center gap-4 animate-pulse">
        <div class="w-9 h-9 bg-gray-200 rounded-full" />
        <div class="flex-1 space-y-2">
          <div class="h-3.5 bg-gray-200 rounded w-1/4" />
          <div class="h-3 bg-gray-100 rounded w-1/3" />
        </div>
        <div class="h-5 bg-gray-100 rounded w-16" />
      </div>
    </div>

    <div v-else-if="members.length > 0" class="card divide-y divide-gray-100">
      <div v-for="m in members" :key="m.id" class="flex items-center gap-4 px-4 py-3">
        <div class="w-9 h-9 bg-primary-100 text-primary-700 rounded-full flex items-center justify-center text-sm font-semibold shrink-0">
          {{ m.user?.username?.[0]?.toUpperCase() ?? '?' }}
        </div>
        <div class="flex-1 min-w-0">
          <div class="text-sm font-medium text-gray-900">{{ m.user?.username ?? '—' }}</div>
          <div class="text-xs text-gray-400">{{ m.user?.email ?? '' }}</div>
        </div>
        <span :class="roleBadge(m.role)" class="shrink-0">{{ roleLabel(m.role) }}</span>
        <span class="text-xs text-gray-400 shrink-0 hidden sm:block">{{ formatDate(m.created_at) }}</span>
        <button
          v-if="m.role !== 'owner'"
          class="btn-icon btn-sm rounded-md hover:text-red-500 hover:bg-red-50 shrink-0"
          @click="remove(m.user_id)"
        >
          <Trash2 class="w-3.5 h-3.5" />
        </button>
        <div v-else class="w-8 shrink-0" />
      </div>
    </div>

    <div v-else class="card flex flex-col items-center py-14 text-center">
      <Users class="w-10 h-10 text-gray-300 mb-3" />
      <p class="text-sm text-gray-500">暂无成员</p>
    </div>

    <!-- Invite member modal -->
    <AppModal v-model="showAdd" title="邀请成员" width="400px">
      <div class="space-y-4">
        <div>
          <label class="label">邮箱地址</label>
          <input
            v-model="newEmail"
            type="email"
            placeholder="输入受邀者的注册邮箱"
            class="input"
          />
          <p class="text-xs text-gray-400 mt-1">受邀用户将在收件箱中收到邀请通知</p>
        </div>
        <div>
          <label class="label">角色</label>
          <select v-model="newRole" class="select">
            <option value="viewer">查看者</option>
            <option value="member">成员</option>
            <option value="admin">管理员</option>
          </select>
        </div>
      </div>
      <template #footer>
        <button class="btn-secondary btn-sm" @click="showAdd = false">取消</button>
        <button class="btn-primary btn-sm" :disabled="adding || !newEmail.trim()" @click="invite">
          <span v-if="adding" class="spinner w-3.5 h-3.5" />
          发送邀请
        </button>
      </template>
    </AppModal>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { UserPlus, Trash2, Users } from 'lucide-vue-next'
import AppModal from '@/components/ui/AppModal.vue'
import { useToastStore } from '@/store/toast'

const props = defineProps<{ projectId: string }>()
const toast = useToastStore()

const members = ref<any[]>([])
const loading = ref(false)
const adding = ref(false)
const showAdd = ref(false)
const newEmail = ref('')
const newRole = ref('member')

const headers = () => ({ Authorization: `Bearer ${localStorage.getItem('token')}` })

const roleLabel = (r: string) => ({ owner: '所有者', admin: '管理员', member: '成员', viewer: '查看者' }[r] ?? r)
const roleBadge = (r: string) => ({ owner: 'badge-red', admin: 'badge-amber', member: 'badge-blue', viewer: 'badge-gray' }[r] ?? 'badge-gray')

const load = async () => {
  loading.value = true
  const r = await fetch(`/api/v1/projects/${props.projectId}/members`, { headers: headers() })
  if (r.ok) members.value = await r.json()
  loading.value = false
}

const invite = async () => {
  if (!newEmail.value.trim()) return
  adding.value = true
  const r = await fetch(`/api/v1/projects/${props.projectId}/members`, {
    method: 'POST',
    headers: { ...headers(), 'Content-Type': 'application/json' },
    body: JSON.stringify({ email: newEmail.value.trim(), role: newRole.value }),
  })
  adding.value = false
  if (r.ok) {
    const data = await r.json()
    showAdd.value = false
    newEmail.value = ''
    if (data.type === 'invitation_sent') {
      toast.success(data.message)
    } else {
      // 直接添加（user_id 方式）时刷新列表
      await load()
      toast.success('成员已添加')
    }
  } else {
    const err = await r.json().catch(() => ({}))
    toast.error(err.detail || '操作失败')
  }
}

const remove = async (userId: string) => {
  const r = await fetch(`/api/v1/projects/${props.projectId}/members/${userId}`, { method: 'DELETE', headers: headers() })
  if (r.ok) { members.value = members.value.filter(m => m.user_id !== userId); toast.success('成员已移除') }
  else toast.error('移除失败')
}

const formatDate = (d: string) => new Date(d).toLocaleDateString('zh-CN')

onMounted(load)
</script>

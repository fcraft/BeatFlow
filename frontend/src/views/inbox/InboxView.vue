<template>
  <AppLayout>
    <div class="max-w-3xl mx-auto px-4 sm:px-6 py-8">
      <!-- 页面标题 -->
      <div class="flex items-center justify-between mb-6">
        <div>
          <h1 class="text-xl font-bold text-gray-900">收件箱</h1>
          <p class="text-sm text-gray-500 mt-0.5">管理通知和项目邀请</p>
        </div>
        <button
          v-if="unreadCount > 0"
          class="btn-secondary btn-sm"
          :disabled="markingAll"
          @click="markAllRead"
        >
          <span v-if="markingAll" class="spinner w-3.5 h-3.5" />
          全部标已读
        </button>
      </div>

      <!-- Tab 过滤 -->
      <div class="flex gap-1 mb-5 border-b border-gray-200">
        <button
          v-for="tab in tabs"
          :key="tab.key"
          class="px-4 py-2 text-sm font-medium border-b-2 transition-colors -mb-px"
          :class="activeTab === tab.key
            ? 'border-primary-600 text-primary-700'
            : 'border-transparent text-gray-500 hover:text-gray-700'"
          @click="activeTab = tab.key; loadNotifications()"
        >
          {{ tab.label }}
          <span
            v-if="tab.key === 'unread' && unreadCount > 0"
            class="ml-1.5 inline-flex items-center justify-center px-1.5 py-0.5 text-xs font-semibold bg-red-100 text-red-700 rounded-full"
          >{{ unreadCount }}</span>
        </button>
      </div>

      <!-- 列表 -->
      <div v-if="loading" class="space-y-3">
        <div v-for="n in 4" :key="n" class="card p-4 animate-pulse">
          <div class="flex gap-3">
            <div class="w-9 h-9 bg-gray-200 rounded-full shrink-0" />
            <div class="flex-1 space-y-2">
              <div class="h-4 bg-gray-200 rounded w-2/3" />
              <div class="h-3 bg-gray-100 rounded w-full" />
              <div class="h-3 bg-gray-100 rounded w-1/3" />
            </div>
          </div>
        </div>
      </div>

      <div v-else-if="notifications.length === 0" class="card flex flex-col items-center py-16 text-center">
        <Inbox class="w-12 h-12 text-gray-300 mb-3" />
        <p class="text-sm text-gray-500">暂无通知</p>
      </div>

      <div v-else class="space-y-3">
        <div
          v-for="notif in notifications"
          :key="notif.id"
          class="card p-4 cursor-pointer transition-colors hover:bg-gray-50"
          :class="!notif.is_read ? 'border-l-4 border-l-primary-500' : ''"
          @click="handleRead(notif)"
        >
          <div class="flex gap-3">
            <!-- 图标 -->
            <div
              class="w-9 h-9 rounded-full flex items-center justify-center shrink-0"
              :class="typeStyle(notif.notification_type).bg"
            >
              <component :is="typeStyle(notif.notification_type).icon" class="w-4 h-4" :class="typeStyle(notif.notification_type).color" />
            </div>

            <div class="flex-1 min-w-0">
              <div class="flex items-start justify-between gap-2">
                <p class="text-sm font-medium text-gray-900 leading-snug">{{ notif.title }}</p>
                <span class="text-xs text-gray-400 shrink-0 mt-0.5">{{ formatTime(notif.created_at) }}</span>
              </div>
              <p class="text-sm text-gray-500 mt-0.5 leading-relaxed">{{ notif.content }}</p>

              <!-- 邀请操作按钮 -->
              <div
                v-if="notif.notification_type === 'project_invite' && notif.status === 'pending'"
                class="flex gap-2 mt-3"
                @click.stop
              >
                <button
                  class="btn-primary btn-sm"
                  :disabled="processingId === notif.id"
                  @click="acceptInvite(notif)"
                >
                  <span v-if="processingId === notif.id" class="spinner w-3.5 h-3.5" />
                  接受邀请
                </button>
                <button
                  class="btn-secondary btn-sm"
                  :disabled="processingId === notif.id"
                  @click="rejectInvite(notif)"
                >
                  拒绝
                </button>
              </div>

              <!-- 状态标签 -->
              <div v-else-if="notif.notification_type === 'project_invite'" class="mt-2">
                <span
                  class="text-xs px-2 py-0.5 rounded-full font-medium"
                  :class="notif.status === 'accepted' ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'"
                >{{ notif.status === 'accepted' ? '已接受' : '已拒绝' }}</span>
              </div>
            </div>

            <!-- 删除按钮 -->
            <button
              class="btn-icon btn-sm rounded-md hover:text-red-500 hover:bg-red-50 shrink-0 self-start"
              @click.stop="deleteNotif(notif.id)"
            >
              <Trash2 class="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </div>

      <!-- 分页 -->
      <div v-if="total > size" class="flex items-center justify-center gap-3 mt-6">
        <button
          class="btn-secondary btn-sm"
          :disabled="page <= 1"
          @click="page--; loadNotifications()"
        >上一页</button>
        <span class="text-sm text-gray-500">{{ page }} / {{ Math.ceil(total / size) }}</span>
        <button
          class="btn-secondary btn-sm"
          :disabled="!hasNext"
          @click="page++; loadNotifications()"
        >下一页</button>
      </div>
    </div>
  </AppLayout>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Bell, Mail, Users, BarChart2, Inbox, Trash2 } from 'lucide-vue-next'
import AppLayout from '@/components/layout/AppLayout.vue'
import { useToastStore } from '@/store/toast'
import { useNotificationStore } from '@/store/notification'
import type { Notification } from '@/types/notification'

const router = useRouter()
const toast = useToastStore()
const notificationStore = useNotificationStore()

const notifications = ref<Notification[]>([])
const loading = ref(false)
const page = ref(1)
const size = 20
const total = ref(0)
const hasNext = ref(false)
const unreadCount = computed(() => notificationStore.unreadCount)
const activeTab = ref<'all' | 'unread' | 'invite'>('all')
const processingId = ref<string | null>(null)
const markingAll = ref(false)

const tabs: Array<{ key: 'all' | 'unread' | 'invite'; label: string }> = [
  { key: 'all', label: '全部' },
  { key: 'unread', label: '未读' },
  { key: 'invite', label: '邀请' },
]

const authHeaders = () => ({
  Authorization: `Bearer ${localStorage.getItem('token')}`,
})

const typeStyle = (type: string) => {
  switch (type) {
    case 'project_invite':
      return { icon: Users, bg: 'bg-blue-100', color: 'text-blue-600' }
    case 'system_announcement':
      return { icon: Bell, bg: 'bg-amber-100', color: 'text-amber-600' }
    case 'community_interaction':
      return { icon: Mail, bg: 'bg-purple-100', color: 'text-purple-600' }
    case 'analysis_complete':
      return { icon: BarChart2, bg: 'bg-green-100', color: 'text-green-600' }
    default:
      return { icon: Bell, bg: 'bg-gray-100', color: 'text-gray-500' }
  }
}

const formatTime = (dateStr: string) => {
  const d = new Date(dateStr)
  const now = new Date()
  const diff = now.getTime() - d.getTime()
  if (diff < 60000) return '刚刚'
  if (diff < 3600000) return `${Math.floor(diff / 60000)} 分钟前`
  if (diff < 86400000) return `${Math.floor(diff / 3600000)} 小时前`
  return d.toLocaleDateString('zh-CN')
}

const loadNotifications = async () => {
  loading.value = true
  const params = new URLSearchParams({
    page: String(page.value),
    size: String(size),
  })
  if (activeTab.value === 'unread') params.set('unread_only', 'true')
  if (activeTab.value === 'invite') params.set('notification_type', 'project_invite')

  const r = await fetch(`/api/v1/notifications/?${params}`, { headers: authHeaders() })
  if (r.ok) {
    const data = await r.json()
    notifications.value = data.items
    total.value = data.total
    hasNext.value = data.has_next
    notificationStore.unreadCount = data.unread_count
  }
  loading.value = false
}

const handleRead = async (notif: Notification) => {
  if (!notif.is_read) {
    await fetch(`/api/v1/notifications/${notif.id}/read`, {
      method: 'PATCH',
      headers: authHeaders(),
    })
    notif.is_read = true
    if (notificationStore.unreadCount > 0) notificationStore.unreadCount--
  }
}

const acceptInvite = async (notif: Notification) => {
  processingId.value = notif.id
  const r = await fetch(`/api/v1/notifications/${notif.id}/accept`, {
    method: 'POST',
    headers: authHeaders(),
  })
  processingId.value = null

  if (r.ok) {
    const data = await r.json()
    notif.status = 'accepted'
    notif.is_read = true
    notificationStore.fetchUnreadCount()
    toast.success('已接受邀请，正在跳转...')
    setTimeout(() => router.push(`/projects/${data.project_id}`), 800)
  } else {
    const err = await r.json().catch(() => ({}))
    toast.error(err.detail || '操作失败')
  }
}

const rejectInvite = async (notif: Notification) => {
  processingId.value = notif.id
  const r = await fetch(`/api/v1/notifications/${notif.id}/reject`, {
    method: 'POST',
    headers: authHeaders(),
  })
  processingId.value = null

  if (r.ok) {
    notif.status = 'rejected'
    notif.is_read = true
    notificationStore.fetchUnreadCount()
    toast.success('已拒绝邀请')
  } else {
    const err = await r.json().catch(() => ({}))
    toast.error(err.detail || '操作失败')
  }
}

const deleteNotif = async (id: string) => {
  const r = await fetch(`/api/v1/notifications/${id}`, {
    method: 'DELETE',
    headers: authHeaders(),
  })
  if (r.ok) {
    const removed = notifications.value.find(n => n.id === id)
    notifications.value = notifications.value.filter(n => n.id !== id)
    if (removed && !removed.is_read) notificationStore.fetchUnreadCount()
    toast.success('通知已删除')
  }
}

const markAllRead = async () => {
  markingAll.value = true
  await notificationStore.markAllRead()
  notifications.value = notifications.value.map(n => ({ ...n, is_read: true }))
  markingAll.value = false
  toast.success('已全部标为已读')
}

onMounted(loadNotifications)
</script>

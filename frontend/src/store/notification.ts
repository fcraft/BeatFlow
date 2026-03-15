import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useNotificationStore = defineStore('notification', () => {
  const unreadCount = ref(0)

  const authHeaders = () => ({
    Authorization: `Bearer ${localStorage.getItem('token')}`,
  })

  const fetchUnreadCount = async () => {
    try {
      const r = await fetch('/api/v1/notifications/unread-count', { headers: authHeaders() })
      if (r.ok) {
        const data = await r.json()
        unreadCount.value = data.count ?? 0
      }
    } catch {
      // 静默失败
    }
  }

  const markAllRead = async () => {
    try {
      const r = await fetch('/api/v1/notifications/read-all', {
        method: 'PATCH',
        headers: authHeaders(),
      })
      if (r.ok) unreadCount.value = 0
    } catch {
      // 静默失败
    }
  }

  return { unreadCount, fetchUnreadCount, markAllRead }
})

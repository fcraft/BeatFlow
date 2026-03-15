export interface NotificationSender {
  id: string
  username: string
}

export interface Notification {
  id: string
  notification_type: 'project_invite' | 'system_announcement' | 'community_interaction' | 'analysis_complete'
  title: string
  content: string
  is_read: boolean
  status: 'pending' | 'accepted' | 'rejected' | 'done'
  data: Record<string, any>
  sender?: NotificationSender
  created_at: string
}

export interface NotificationListResponse {
  items: Notification[]
  total: number
  page: number
  size: number
  has_next: boolean
  unread_count: number
}

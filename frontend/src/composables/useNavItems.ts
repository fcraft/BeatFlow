/**
 * 共享的导航菜单项配置
 *
 * AppLayout 侧边栏和 VirtualHumanView 导航浮层共用此数据源，
 * 保证两处导航始终一致，降低维护成本。
 */
import { computed, type Component } from 'vue'
import {
  FolderOpen,
  FlaskConical,
  Activity,
  Users,
  Inbox,
  Settings,
} from 'lucide-vue-next'
import { useAuthStore } from '@/store/auth'
import { useNotificationStore } from '@/store/notification'

export interface NavItem {
  to: string
  label: string
  icon: Component
  badge?: number
}

export function useNavItems() {
  const authStore = useAuthStore()
  const notificationStore = useNotificationStore()

  const navItems = computed<NavItem[]>(() => {
    const items: NavItem[] = [
      { to: '/projects',      label: '我的项目', icon: FolderOpen },
      { to: '/simulate',      label: '模拟生成', icon: FlaskConical },
      { to: '/virtual-human', label: '虚拟人体', icon: Activity },
      { to: '/community',     label: '社区广场', icon: Users },
      { to: '/inbox',         label: '收件箱',   icon: Inbox, badge: notificationStore.unreadCount },
    ]
    const user = authStore.user
    if (user && (user.is_superuser || user.role === 'admin')) {
      items.push({ to: '/admin', label: '系统管理', icon: Settings })
    }
    return items
  })

  return { navItems }
}

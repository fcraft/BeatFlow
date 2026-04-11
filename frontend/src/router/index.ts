import { createRouter, createWebHistory } from 'vue-router'

import { useAuthStore } from '@/store/auth'

/**
 * 页面过渡层级映射
 * 数值越大层级越深，用于决定 slide 方向：
 *   向深层 → slide-left（内容从右侧滑入）
 *   向浅层 → slide-right（内容从左侧滑入）
 *   同层   → fade
 */
const DEPTH: Record<string, number> = {
  home: 0,
  login: 1,
  register: 1,
  projects: 2,
  'project-detail': 3,
  'file-viewer': 4,
  'sync-viewer': 4,
  community: 2,
  simulate: 2,
  'virtual-human': 2,
  'virtual-human-v2': 2,
  inbox: 2,
  admin: 2,
}

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    { path: '/', name: 'home', component: () => import('@/views/HomeView.vue') },
    { path: '/login', name: 'login', component: () => import('@/views/auth/LoginView.vue') },
    { path: '/register', name: 'register', component: () => import('@/views/auth/RegisterView.vue') },
    { path: '/projects', name: 'projects', component: () => import('@/views/project/ProjectListView.vue'), meta: { requiresAuth: true } },
    { path: '/projects/:id', name: 'project-detail', component: () => import('@/views/project/ProjectDetailView.vue'), meta: { requiresAuth: true } },
    { path: '/files/:id', name: 'file-viewer', component: () => import('@/views/analyzer/FileViewerView.vue'), meta: { requiresAuth: true } },
    { path: '/sync/:id', name: 'sync-viewer', component: () => import('@/views/analyzer/SyncViewerView.vue'), meta: { requiresAuth: true } },
    { path: '/share/file/:code', name: 'file-share', component: () => import('@/views/share/FileShareView.vue') },
    { path: '/share/association/:code', name: 'association-share', component: () => import('@/views/share/AssociationShareView.vue') },
    { path: '/community', name: 'community', component: () => import('@/views/community/CommunityView.vue'), meta: { requiresAuth: true } },
    { path: '/simulate', name: 'simulate', component: () => import('@/views/simulator/SimulatorView.vue'), meta: { requiresAuth: true } },
    { path: '/virtual-human-legacy', name: 'virtual-human', component: () => import('@/views/virtual-human/VirtualHumanView.vue'), meta: { requiresAuth: true } },
    { path: '/virtual-human', name: 'virtual-human-v2', component: () => import('@/views/virtual-human/VirtualHumanV2View.vue'), meta: { requiresAuth: true } },
    { path: '/inbox', name: 'inbox', component: () => import('@/views/inbox/InboxView.vue'), meta: { requiresAuth: true } },
    { path: '/admin', name: 'admin', component: () => import('@/views/admin/AdminView.vue'), meta: { requiresAuth: true, requiresAdmin: true } },
  ]
})

// ── Auth guard (beforeEach) ──
router.beforeEach((to, from, next) => {
  const auth = useAuthStore()

  // 已登录用户访问首页/登录/注册页时，自动跳转到项目列表
  if (auth.isAuthenticated && (to.name === 'home' || to.name === 'login' || to.name === 'register')) {
    next('/projects')
    return
  }

  if (to.meta.requiresAuth && !auth.isAuthenticated) {
    next('/login')
    return
  }
  if (to.meta.requiresAdmin) {
    const user = auth.user
    if (!user || (!user.is_superuser && user.role !== 'admin')) {
      next('/projects')
      return
    }
  }

  // 根据页面层级深度决定过渡动画方向
  const fromDepth = DEPTH[from.name as string] ?? 0
  const toDepth = DEPTH[to.name as string] ?? 0

  if (toDepth > fromDepth) {
    to.meta.transition = 'page-slide-left'
  } else if (toDepth < fromDepth) {
    to.meta.transition = 'page-slide-right'
  } else {
    to.meta.transition = 'page-fade'
  }

  next()
})

export default router

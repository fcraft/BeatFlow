import { createRouter, createWebHistory } from 'vue-router'

import { useAuthStore } from '@/store/auth'

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

router.beforeEach((to, _from, next) => {
  const auth = useAuthStore()
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
  next()
})

export default router

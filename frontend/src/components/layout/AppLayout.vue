<template>
  <div class="flex h-screen bg-gray-50 overflow-hidden">
    <!-- Mobile overlay -->
    <Transition name="fade">
      <div
        v-if="mobileOpen"
        class="fixed inset-0 z-30 bg-black/40 lg:hidden"
        @click="mobileOpen = false"
      />
    </Transition>

    <!-- Sidebar -->
    <aside
      class="fixed inset-y-0 left-0 z-40 flex flex-col bg-white border-r border-gray-200 shrink-0
             transition-[width,transform] duration-200 ease-in-out
             lg:relative lg:translate-x-0"
      :class="[
        collapsed ? 'lg:w-16' : 'lg:w-60',
        mobileOpen ? 'translate-x-0 w-60' : '-translate-x-full w-60',
      ]"
    >
      <!-- Logo -->
      <RouterLink to="/" class="flex items-center gap-2.5 px-4 h-14 border-b border-gray-100 shrink-0" @click="mobileOpen = false">
        <div class="w-8 h-8 rounded-lg bg-primary-600 flex items-center justify-center shrink-0">
          <HeartPulse class="w-4 h-4 text-white" />
        </div>
        <span
          v-if="!collapsed"
          class="font-bold text-gray-900 text-sm"
        >BeatFlow</span>
      </RouterLink>

      <!-- Nav -->
      <nav class="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
        <RouterLink
          v-for="item in navItems"
          :key="item.to"
          :to="item.to"
          class="flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors duration-150 group relative"
          :class="isActive(item.to)
            ? 'bg-primary-50 text-primary-700'
            : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'"
          @click="mobileOpen = false"
        >
          <div class="relative shrink-0">
            <component :is="item.icon" class="w-4 h-4" />
            <span
              v-if="item.badge && item.badge > 0"
              class="absolute -top-1.5 -right-1.5 min-w-[14px] h-3.5 px-0.5 bg-red-500 text-white text-[9px] font-bold rounded-full flex items-center justify-center leading-none"
            >{{ item.badge > 99 ? '99+' : item.badge }}</span>
          </div>
          <span class="truncate" :class="collapsed ? 'lg:hidden' : ''">{{ item.label }}</span>
        </RouterLink>
      </nav>

      <!-- User -->
      <div class="border-t border-gray-100 p-3 shrink-0">
        <div v-if="authStore.user" class="flex items-center gap-3 px-2 py-2">
          <div class="w-8 h-8 bg-primary-100 text-primary-700 rounded-full flex items-center justify-center text-sm font-semibold shrink-0">
            {{ authStore.user.username?.[0]?.toUpperCase() ?? '?' }}
          </div>
          <div class="flex-1 min-w-0" :class="collapsed ? 'lg:hidden' : ''">
            <div class="text-sm font-medium text-gray-900 truncate">{{ authStore.user.username }}</div>
            <div class="text-xs text-gray-500 truncate">{{ authStore.user.email }}</div>
          </div>
        </div>
        <button
          class="mt-1 w-full flex items-center gap-3 px-3 py-2 text-sm text-gray-600 rounded-lg hover:bg-gray-100 transition-colors"
          @click="logout"
        >
          <LogOut class="w-4 h-4 shrink-0" />
          <span :class="collapsed ? 'lg:hidden' : ''">退出登录</span>
        </button>
      </div>
    </aside>

    <!-- Main -->
    <div class="flex-1 flex flex-col min-w-0 overflow-hidden">
      <!-- Top bar -->
      <header class="flex items-center gap-3 px-4 sm:px-6 h-14 bg-white border-b border-gray-200 shrink-0">
        <button class="btn-icon rounded-lg lg:hidden" @click="mobileOpen = !mobileOpen">
          <Menu class="w-4 h-4" />
        </button>
        <button class="btn-icon rounded-lg hidden lg:flex" @click="collapsed = !collapsed">
          <PanelLeft class="w-4 h-4" />
        </button>
        <div class="flex-1" />
        <RouterLink to="/inbox" class="btn-icon rounded-lg relative" title="收件箱">
          <Bell class="w-4 h-4" />
          <span
            v-if="notificationStore.unreadCount > 0"
            class="absolute -top-0.5 -right-0.5 min-w-[16px] h-4 px-0.5 bg-red-500 text-white text-[10px] font-bold rounded-full flex items-center justify-center leading-none"
          >{{ notificationStore.unreadCount > 99 ? '99+' : notificationStore.unreadCount }}</span>
        </RouterLink>
        <slot name="header-actions" />
      </header>

      <!-- Content -->
      <main class="flex-1 overflow-y-auto">
        <slot />
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, inject, watch, onMounted } from 'vue'
import type { Ref } from 'vue'
import { useRoute, useRouter, RouterLink } from 'vue-router'
import { HeartPulse, LogOut, PanelLeft, Menu, Bell } from 'lucide-vue-next'
import { useAuthStore } from '@/store/auth'
import { useToastStore } from '@/store/toast'
import { useNotificationStore } from '@/store/notification'
import { useNavItems } from '@/composables/useNavItems'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const toast = useToastStore()
const notificationStore = useNotificationStore()
const { navItems } = useNavItems()

const collapsed = ref(false)
const mobileOpen = ref(false)

// 同步折叠状态给 App.vue 的 SharedLogo
const parentCollapsed = inject<Ref<boolean>>('sidebar-collapsed')
watch(collapsed, (v) => {
  if (parentCollapsed) parentCollapsed.value = v
}, { immediate: true })

const isActive = (to: string) => route.path.startsWith(to)

const logout = () => {
  mobileOpen.value = false
  authStore.logout()
  toast.success('已退出登录')
  router.push('/login')
}

onMounted(() => {
  notificationStore.fetchUnreadCount()
})
</script>

<style scoped>
.fade-enter-active, .fade-leave-active { transition: opacity 0.2s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>

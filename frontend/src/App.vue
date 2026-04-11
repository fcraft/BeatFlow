<template>
  <div class="app-root min-h-screen transition-colors duration-500" :class="appBgClass">
    <SharedLogo :collapsed="sidebarCollapsed" />
    <SharedAuthCard />
    <RouterView v-slot="{ Component, route }">
      <Transition
        :name="routeTransition(route)"
        mode="out-in"
        appear
      >
        <component :is="Component" :key="route.path" />
      </Transition>
    </RouterView>
    <AppToast />
  </div>
</template>

<script setup lang="ts">
import { provide, ref, computed } from 'vue'
import { RouterView, useRoute } from 'vue-router'
import type { RouteLocationNormalizedLoaded } from 'vue-router'
import AppToast from '@/components/ui/AppToast.vue'
import SharedLogo from '@/components/shared/SharedLogo.vue'
import SharedAuthCard from '@/components/shared/SharedAuthCard.vue'

const sidebarCollapsed = ref(false)
provide('sidebar-collapsed', sidebarCollapsed)

const AUTH_ROUTES = new Set(['home', 'login', 'register'])
const prevRoute = ref<string>('')
const currentRoute = useRoute()

// 根据当前路由设置根背景，避免 out-in 过渡间隙露底色
const appBgClass = computed(() => {
  const name = currentRoute.name as string
  if (name === 'home') return 'bg-gradient-to-b from-slate-950 via-slate-900 to-slate-950'
  if (name === 'login' || name === 'register') return 'bg-gradient-to-br from-slate-900 via-primary-950 to-slate-900'
  return 'bg-gray-50'
})

function routeTransition(route: RouteLocationNormalizedLoaded): string {
  const to = route.name as string
  const from = prevRoute.value
  prevRoute.value = to

  if (AUTH_ROUTES.has(to) && AUTH_ROUTES.has(from)) {
    return 'auth-crossfade'
  }
  if (AUTH_ROUTES.has(from) && !AUTH_ROUTES.has(to)) {
    return 'auth-to-workspace'
  }
  if (!AUTH_ROUTES.has(from) && AUTH_ROUTES.has(to)) {
    return 'workspace-to-auth'
  }
  return (route.meta.transition as string) || 'page-fade'
}
</script>

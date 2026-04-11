<template>
  <div
    class="shared-logo"
    :class="layoutClass"
    :style="layoutStyle"
  >
    <RouterLink to="/" class="shared-logo__link" @click.prevent="handleClick">
      <div class="shared-logo__icon" :class="iconSizeClass">
        <HeartPulse class="shared-logo__svg" :class="svgSizeClass" />
      </div>
      <span
        v-if="!hideText"
        class="shared-logo__text"
        :class="textClass"
      >BeatFlow</span>
    </RouterLink>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter, RouterLink } from 'vue-router'
import { HeartPulse } from 'lucide-vue-next'

type LogoLayout = 'home' | 'auth-login' | 'auth-register' | 'workspace'

const route = useRoute()
const router = useRouter()

const props = defineProps<{
  /** 工作台侧边栏是否折叠 */
  collapsed?: boolean
}>()

const layout = computed<LogoLayout>(() => {
  const name = route.name as string
  if (name === 'home') return 'home'
  if (name === 'login') return 'auth-login'
  if (name === 'register') return 'auth-register'
  return 'workspace'
})

const isAuthOrHome = computed(() =>
  ['home', 'auth-login', 'auth-register'].includes(layout.value),
)

const hideText = computed(() =>
  layout.value === 'workspace' && props.collapsed,
)

const handleClick = () => {
  if (route.path !== '/') router.push('/')
}

// ─── 布局相关计算属性 ───

const layoutClass = computed(() => {
  const map: Record<LogoLayout, string> = {
    'home': 'shared-logo--home',
    'auth-login': 'shared-logo--auth-login',
    'auth-register': 'shared-logo--auth-register',
    'workspace': 'shared-logo--workspace',
  }
  return map[layout.value]
})

const layoutStyle = computed(() => {
  // 使用 CSS 类控制位置，这里只做动态 z-index
  return { zIndex: isAuthOrHome.value ? 60 : 'auto' }
})

const iconSizeClass = computed(() => {
  const map: Record<LogoLayout, string> = {
    'home': 'w-9 h-9 rounded-xl bg-primary-500',
    'auth-login': 'w-10 h-10 rounded-xl bg-primary-500',
    'auth-register': 'w-9 h-9 rounded-xl bg-primary-500',
    'workspace': 'w-8 h-8 rounded-lg bg-primary-600',
  }
  return map[layout.value]
})

const svgSizeClass = computed(() => {
  const map: Record<LogoLayout, string> = {
    'home': 'w-5 h-5',
    'auth-login': 'w-5 h-5',
    'auth-register': 'w-5 h-5',
    'workspace': 'w-4 h-4',
  }
  return map[layout.value]
})

const textClass = computed(() => {
  const base = isAuthOrHome.value ? 'text-white' : 'text-gray-900'
  const sizeMap: Record<LogoLayout, string> = {
    'home': 'text-lg font-bold tracking-tight',
    'auth-login': 'text-xl font-bold tracking-tight',
    'auth-register': 'text-2xl font-bold',
    'workspace': 'text-sm font-bold',
  }
  return `${base} ${sizeMap[layout.value]}`
})
</script>

<style scoped>
.shared-logo {
  position: fixed;
  transition:
    top 0.45s cubic-bezier(0.4, 0, 0.2, 1),
    left 0.45s cubic-bezier(0.4, 0, 0.2, 1),
    transform 0.45s cubic-bezier(0.4, 0, 0.2, 1);
  pointer-events: auto;
}

.shared-logo__link {
  display: flex;
  align-items: center;
  gap: 0.625rem;
  text-decoration: none;
  color: inherit;
}

.shared-logo__icon {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition:
    width 0.35s cubic-bezier(0.4, 0, 0.2, 1),
    height 0.35s cubic-bezier(0.4, 0, 0.2, 1),
    border-radius 0.35s cubic-bezier(0.4, 0, 0.2, 1),
    background-color 0.35s cubic-bezier(0.4, 0, 0.2, 1);
}

.shared-logo__svg {
  color: white;
  transition:
    width 0.35s cubic-bezier(0.4, 0, 0.2, 1),
    height 0.35s cubic-bezier(0.4, 0, 0.2, 1);
}

.shared-logo__text {
  transition:
    font-size 0.35s cubic-bezier(0.4, 0, 0.2, 1),
    color 0.35s cubic-bezier(0.4, 0, 0.2, 1),
    opacity 0.25s ease;
  white-space: nowrap;
}

/* ─── 位置布局 ─── */

/* 首页：左上 header 内 */
.shared-logo--home {
  top: 1.125rem; /* h-16 居中 */
  left: calc((100vw - 72rem) / 2 + 1.5rem); /* max-w-6xl + px-6 */
}
@media (max-width: 72rem) {
  .shared-logo--home {
    left: 1.5rem;
  }
}

/* 登录页：左侧面板顶部 */
.shared-logo--auth-login {
  top: 3rem;
  left: 3rem;
}
@media (max-width: 1024px) {
  /* 移动端居左 */
  .shared-logo--auth-login {
    top: 2rem;
    left: 2rem;
  }
}

/* 注册页：顶部居中 */
.shared-logo--auth-register {
  top: 2rem;
  left: 50%;
  transform: translateX(-50%);
}
@media (max-width: 1024px) {
  .shared-logo--auth-register {
    top: 0.75rem;
  }
}

/* 工作台：侧栏左上 */
.shared-logo--workspace {
  position: absolute; /* 相对于 AppLayout 侧栏 */
  top: 0.875rem; /* h-14 居中 */
  left: 1rem;
}

/* reduced motion */
@media (prefers-reduced-motion: reduce) {
  .shared-logo,
  .shared-logo__icon,
  .shared-logo__svg,
  .shared-logo__text {
    transition-duration: 0.1s !important;
  }
}
</style>

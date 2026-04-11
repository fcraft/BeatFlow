<template>
  <div
    class="shared-card"
    :class="stateClass"
    :style="cardStyle"
  >
    <!-- 内部表单内容切换 -->
    <div v-if="isVisible" ref="innerRef" class="shared-card__inner">
      <Transition name="card-content" mode="out-in" @enter="measureHeight" @after-enter="measureHeight">
        <div v-if="layout === 'login'" key="login" class="shared-card__form">
          <div class="mb-6">
            <h2 class="text-2xl font-bold text-gray-900">欢迎回来</h2>
            <p class="text-gray-500 text-sm mt-1">登录您的账户继续工作</p>
          </div>

          <form @submit.prevent="handleLogin" class="space-y-4">
            <div>
              <label class="label">邮箱</label>
              <input
                v-model="loginForm.email"
                type="email"
                placeholder="your@email.com"
                class="input"
                :class="{ 'input-error': loginError }"
                autocomplete="email"
                required
              />
            </div>
            <div>
              <label class="label">密码</label>
              <div class="relative">
                <input
                  v-model="loginForm.password"
                  :type="showLoginPwd ? 'text' : 'password'"
                  placeholder="输入密码"
                  class="input pr-10"
                  :class="{ 'input-error': loginError }"
                  autocomplete="current-password"
                  required
                />
                <button
                  type="button"
                  class="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                  @click="showLoginPwd = !showLoginPwd"
                >
                  <component :is="showLoginPwd ? EyeOff : Eye" class="w-4 h-4" />
                </button>
              </div>
            </div>
            <div v-if="loginError" class="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
              {{ loginError }}
            </div>
            <button type="submit" class="btn-primary w-full btn-lg mt-2" :disabled="loginLoading">
              <span v-if="loginLoading" class="spinner w-4 h-4" />
              {{ loginLoading ? '登录中...' : '登录' }}
            </button>
          </form>

          <p class="text-center text-sm text-gray-500 mt-6">
            没有账号？
            <RouterLink to="/register" class="text-primary-600 font-medium hover:text-primary-700">立即注册</RouterLink>
          </p>
        </div>

        <div v-else-if="layout === 'register'" key="register" class="shared-card__form">
          <div class="mb-6">
            <h2 class="text-2xl font-bold text-gray-900">创建账户</h2>
            <p class="text-gray-500 text-sm mt-1">加入 BeatFlow，开始分析心音心电数据</p>
          </div>

          <form @submit.prevent="handleRegister" class="space-y-4">
            <div class="grid grid-cols-2 gap-4">
              <div>
                <label class="label">姓名</label>
                <input v-model="regForm.full_name" type="text" placeholder="真实姓名" class="input" required />
              </div>
              <div>
                <label class="label">用户名</label>
                <input v-model="regForm.username" type="text" placeholder="用户名" class="input" required />
              </div>
            </div>
            <div>
              <label class="label">邮箱</label>
              <input
                v-model="regForm.email"
                type="email"
                placeholder="your@email.com"
                class="input"
                :class="{ 'input-error': emailError }"
                required
              />
              <p v-if="emailError" class="text-xs text-red-500 mt-1">{{ emailError }}</p>
            </div>
            <div>
              <label class="label">密码</label>
              <div class="relative">
                <input
                  v-model="regForm.password"
                  :type="showRegPwd ? 'text' : 'password'"
                  placeholder="至少 8 位，含大小写字母和数字"
                  class="input pr-10"
                  :class="{ 'input-error': pwdError }"
                  required
                />
                <button type="button" class="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400" @click="showRegPwd = !showRegPwd">
                  <component :is="showRegPwd ? EyeOff : Eye" class="w-4 h-4" />
                </button>
              </div>
            </div>
            <div>
              <label class="label">确认密码</label>
              <input
                v-model="regForm.confirm"
                :type="showRegPwd ? 'text' : 'password'"
                placeholder="再次输入密码"
                class="input"
                :class="{ 'input-error': pwdError }"
                required
              />
              <p v-if="pwdError" class="text-xs text-red-500 mt-1">{{ pwdError }}</p>
            </div>
            <label class="flex items-start gap-2.5 cursor-pointer mt-2">
              <input v-model="agreed" type="checkbox" class="mt-0.5 accent-primary-600" />
              <span class="text-sm text-gray-600">
                我已阅读并同意
                <a href="#" class="text-primary-600">服务条款</a>
                和
                <a href="#" class="text-primary-600">隐私政策</a>
              </span>
            </label>
            <div v-if="regError" class="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
              {{ regError }}
            </div>
            <button type="submit" class="btn-primary w-full btn-lg" :disabled="regLoading || !agreed">
              <span v-if="regLoading" class="spinner w-4 h-4" />
              {{ regLoading ? '注册中...' : '注册' }}
            </button>
          </form>

          <p class="text-center text-sm text-gray-500 mt-6">
            已有账号？
            <RouterLink to="/login" class="text-primary-600 font-medium">立即登录</RouterLink>
          </p>
        </div>
      </Transition>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch, onMounted, nextTick } from 'vue'
import { useRoute, useRouter, RouterLink } from 'vue-router'
import { Eye, EyeOff } from 'lucide-vue-next'
import { useAuthStore } from '@/store/auth'
import { useToastStore } from '@/store/toast'

type CardLayout = 'hidden' | 'login' | 'register' | 'fullscreen'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const toast = useToastStore()

// ─── Layout state ───

const layout = computed<CardLayout>(() => {
  const name = route.name as string
  if (name === 'login') return 'login'
  if (name === 'register') return 'register'
  // 工作台页面：卡片展开为全屏白色背景
  if (['projects', 'project-detail', 'file-viewer', 'sync-viewer',
       'community', 'simulate', 'virtual-human', 'virtual-human-v2',
       'inbox', 'admin'].includes(name)) return 'fullscreen'
  return 'hidden'
})

const isVisible = computed(() => layout.value === 'login' || layout.value === 'register')

// ─── Content height tracking for smooth height transition ───
const innerRef = ref<HTMLElement | null>(null)
const contentHeight = ref(0)

function measureHeight() {
  if (innerRef.value) {
    const formEl = innerRef.value.querySelector('.shared-card__form') as HTMLElement
    if (formEl) {
      contentHeight.value = formEl.scrollHeight
    }
  }
}

// Re-measure on route change
watch(() => route.name, async () => {
  await nextTick()
  await nextTick()
  measureHeight()
})

onMounted(() => {
  // Use ResizeObserver for dynamic content changes (e.g. error messages appearing)
  if (typeof ResizeObserver !== 'undefined' && innerRef.value) {
    const ro = new ResizeObserver(() => measureHeight())
    watch(innerRef, (el) => {
      if (el) ro.observe(el)
    }, { immediate: true })
  }
  nextTick(() => measureHeight())
})

const stateClass = computed(() => ({
  'shared-card--hidden': layout.value === 'hidden',
  'shared-card--login': layout.value === 'login',
  'shared-card--register': layout.value === 'register',
  'shared-card--fullscreen': layout.value === 'fullscreen',
}))

const cardStyle = computed(() => {
  if (layout.value === 'hidden') {
    return { pointerEvents: 'none' as const }
  }
  if (layout.value === 'fullscreen') {
    return { pointerEvents: 'none' as const }
  }
  // Login / register: use measured content height for smooth transition
  if (contentHeight.value > 0) {
    return { height: `${contentHeight.value}px` }
  }
  return {}
})

// ─── Login form ───

const loginForm = reactive({ email: '', password: '' })
const loginLoading = ref(false)
const loginError = ref('')
const showLoginPwd = ref(false)

const handleLogin = async () => {
  loginError.value = ''
  loginLoading.value = true
  const result = await authStore.login(loginForm.email, loginForm.password)
  loginLoading.value = false
  if (result.success) {
    toast.success(`欢迎回来，${result.user?.username}`)
    const redirect = route.query.redirect as string
    router.push(redirect || '/projects')
  } else {
    loginError.value = result.error || '邮箱或密码不正确'
  }
}

// ─── Register form ───

const regForm = reactive({ full_name: '', username: '', email: '', password: '', confirm: '' })
const regLoading = ref(false)
const regError = ref('')
const showRegPwd = ref(false)
const agreed = ref(false)

const emailError = computed(() => {
  if (!regForm.email) return ''
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(regForm.email) ? '' : '请输入有效邮箱'
})

const pwdError = computed(() => {
  if (!regForm.password) return ''
  if (regForm.password.length < 8) return '密码至少 8 位'
  if (!/[a-z]/.test(regForm.password)) return '密码必须包含小写字母'
  if (!/[A-Z]/.test(regForm.password)) return '密码必须包含大写字母'
  if (!/[0-9]/.test(regForm.password)) return '密码必须包含数字'
  if (regForm.confirm && regForm.password !== regForm.confirm) return '两次密码不一致'
  return ''
})

const handleRegister = async () => {
  if (emailError.value || pwdError.value) return
  regError.value = ''
  regLoading.value = true
  const result = await authStore.register({
    full_name: regForm.full_name,
    username: regForm.username,
    email: regForm.email,
    password: regForm.password,
  })
  regLoading.value = false
  if (result.success) {
    toast.success('账户创建成功，请登录')
    router.push('/login')
  } else {
    regError.value = result.error || '注册失败，请稍后重试'
  }
}

// Reset form errors on route change
watch(() => route.name, () => {
  loginError.value = ''
  regError.value = ''
})
</script>

<style scoped>
.shared-card {
  position: fixed;
  z-index: 50;
  background: white;
  overflow: hidden;
  transition:
    top 0.5s cubic-bezier(0.4, 0, 0.2, 1),
    left 0.5s cubic-bezier(0.4, 0, 0.2, 1),
    width 0.5s cubic-bezier(0.4, 0, 0.2, 1),
    height 0.5s cubic-bezier(0.4, 0, 0.2, 1),
    border-radius 0.5s cubic-bezier(0.4, 0, 0.2, 1),
    box-shadow 0.5s cubic-bezier(0.4, 0, 0.2, 1),
    opacity 0.4s cubic-bezier(0.4, 0, 0.2, 1),
    transform 0.5s cubic-bezier(0.4, 0, 0.2, 1);
}

.shared-card__inner {
  width: 100%;
  height: 100%;
  overflow-y: auto;
}

.shared-card__form {
  padding: 2rem;
}

/* ─── Hidden: seed point at hero center ─── */
.shared-card--hidden {
  top: 50vh;
  left: 50vw;
  width: 200px;
  height: 48px;
  border-radius: 1rem;
  transform: translate(-50%, -50%) scale(0);
  opacity: 0;
  box-shadow: none;
}

/* ─── Login: right-center card ─── */
.shared-card--login {
  /* Desktop: right panel center */
  top: 50%;
  left: calc(55% + (45% / 2)); /* 45% left panel + center of remaining 55% */
  width: 24rem; /* max-w-sm = 24rem */
  max-height: calc(100vh - 4rem);
  border-radius: 1rem;
  transform: translate(-50%, -50%);
  opacity: 1;
  box-shadow:
    0 25px 50px -12px rgba(0, 0, 0, 0.25),
    0 0 0 1px rgba(0, 0, 0, 0.03);
}
@media (max-width: 1024px) {
  .shared-card--login {
    left: 50%;
    width: calc(100vw - 4rem);
    max-width: 24rem;
  }
}

/* ─── Register: page-center card ─── */
.shared-card--register {
  top: 50%;
  left: 50%;
  width: 28rem; /* max-w-md = 28rem */
  max-height: calc(100vh - 4rem);
  border-radius: 1rem;
  transform: translate(-50%, -50%);
  opacity: 1;
  box-shadow:
    0 25px 50px -12px rgba(0, 0, 0, 0.25),
    0 0 0 1px rgba(0, 0, 0, 0.03);
}
@media (max-width: 1024px) {
  .shared-card--register {
    top: calc(50% + 1.5rem);
    width: calc(100vw - 4rem);
    max-width: 28rem;
    max-height: calc(100vh - 5rem);
  }
}

/* ─── Fullscreen: expand to cover viewport ─── */
.shared-card--fullscreen {
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  border-radius: 0;
  transform: none;
  opacity: 1;
  box-shadow: none;
}

/* ─── Inner content transitions ─── */
.card-content-enter-active {
  transition: opacity 0.25s ease 0.1s, transform 0.25s ease 0.1s;
}
.card-content-leave-active {
  transition: opacity 0.15s ease, transform 0.15s ease;
}
.card-content-enter-from {
  opacity: 0;
  transform: translateY(12px);
}
.card-content-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}

/* ─── Reduced motion ─── */
@media (prefers-reduced-motion: reduce) {
  .shared-card {
    transition-duration: 0.15s !important;
  }
  .card-content-enter-active,
  .card-content-leave-active {
    transition-duration: 0.1s !important;
    transition-delay: 0s !important;
  }
}
</style>

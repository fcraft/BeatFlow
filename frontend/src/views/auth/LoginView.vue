<template>
  <div class="min-h-screen bg-gradient-to-br from-slate-900 via-primary-950 to-slate-900 flex">
    <!-- Left decorative panel -->
    <div class="hidden lg:flex flex-col justify-between w-[45%] p-12 text-white">
      <div class="flex items-center gap-3">
        <div class="w-10 h-10 bg-primary-500 rounded-xl flex items-center justify-center">
          <HeartPulse class="w-5 h-5 text-white" />
        </div>
        <span class="text-xl font-bold tracking-tight">BeatFlow</span>
      </div>

      <div>
        <h1 class="text-4xl font-bold leading-tight mb-4">
          专业的心音心电<br />数据分析平台
        </h1>
        <p class="text-primary-200 text-lg leading-relaxed mb-8">
          支持 ECG/PCG 波形可视化、智能标记、多人协作与实时分析
        </p>

        <div class="space-y-4">
          <div v-for="feat in features" :key="feat.title" class="flex items-start gap-3">
            <div class="w-8 h-8 bg-primary-500/20 rounded-lg flex items-center justify-center shrink-0 mt-0.5">
              <component :is="feat.icon" class="w-4 h-4 text-primary-300" />
            </div>
            <div>
              <div class="font-medium text-white">{{ feat.title }}</div>
              <div class="text-sm text-primary-300">{{ feat.desc }}</div>
            </div>
          </div>
        </div>
      </div>

      <p class="text-primary-400 text-sm">© 2026 BeatFlow · 专为心音心电研究设计</p>
    </div>

    <!-- Right auth panel -->
    <div class="flex-1 flex items-center justify-center p-8 bg-white/5 backdrop-blur-sm lg:rounded-l-3xl">
      <div class="w-full max-w-sm">
        <!-- Mobile logo -->
        <div class="flex lg:hidden items-center gap-2 mb-8">
          <div class="w-8 h-8 bg-primary-500 rounded-lg flex items-center justify-center">
            <HeartPulse class="w-4 h-4 text-white" />
          </div>
          <span class="text-xl font-bold text-white">BeatFlow</span>
        </div>

        <div class="bg-white rounded-2xl shadow-2xl p-8">
          <div class="mb-6">
            <h2 class="text-2xl font-bold text-gray-900">欢迎回来</h2>
            <p class="text-gray-500 text-sm mt-1">登录您的账户继续工作</p>
          </div>

          <form @submit.prevent="handleSubmit" class="space-y-4">
            <div>
              <label class="label">邮箱</label>
              <input
                v-model="form.email"
                type="email"
                placeholder="your@email.com"
                class="input"
                :class="{ 'input-error': error }"
                autocomplete="email"
                required
              />
            </div>

            <div>
              <div class="flex items-center justify-between mb-1.5">
                <label class="label mb-0">密码</label>
              </div>
              <div class="relative">
                <input
                  v-model="form.password"
                  :type="showPassword ? 'text' : 'password'"
                  placeholder="输入密码"
                  class="input pr-10"
                  :class="{ 'input-error': error }"
                  autocomplete="current-password"
                  required
                />
                <button
                  type="button"
                  class="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                  @click="showPassword = !showPassword"
                >
                  <component :is="showPassword ? EyeOff : Eye" class="w-4 h-4" />
                </button>
              </div>
            </div>

            <div v-if="error" class="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
              {{ error }}
            </div>

            <button type="submit" class="btn-primary w-full btn-lg mt-2" :disabled="loading">
              <span v-if="loading" class="spinner w-4 h-4" />
              {{ loading ? '登录中...' : '登录' }}
            </button>
          </form>

          <p class="text-center text-sm text-gray-500 mt-6">
            没有账号？
            <RouterLink to="/register" class="text-primary-600 font-medium hover:text-primary-700">立即注册</RouterLink>
          </p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRouter, useRoute, RouterLink } from 'vue-router'
import { HeartPulse, Eye, EyeOff, Activity, Tag, Users } from 'lucide-vue-next'
import { useAuthStore } from '@/store/auth'
import { useToastStore } from '@/store/toast'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()
const toast = useToastStore()

const loading = ref(false)
const showPassword = ref(false)
const error = ref('')
const form = reactive({ email: '', password: '' })

const features = [
  { icon: Activity, title: '波形可视化', desc: '实时 ECG/PCG 波形展示与播放控制' },
  { icon: Tag,      title: '智能标记',   desc: '自动检测 S1/S2、QRS 等关键心音事件' },
  { icon: Users,    title: '多人协作',   desc: '团队实时协同标记与数据审查' },
]

const handleSubmit = async () => {
  error.value = ''
  loading.value = true
  const result = await authStore.login(form.email, form.password)
  loading.value = false
  if (result.success) {
    toast.success(`欢迎回来，${result.user?.username}`)
    const redirect = route.query.redirect as string
    router.push(redirect || '/projects')
  } else {
    error.value = result.error || '邮箱或密码不正确'
  }
}
</script>

<template>
  <div class="min-h-screen bg-gradient-to-br from-slate-900 via-primary-950 to-slate-900 flex items-center justify-center p-8">
    <div class="w-full max-w-md">
      <div class="flex items-center gap-2 mb-8 justify-center">
        <div class="w-9 h-9 bg-primary-500 rounded-xl flex items-center justify-center">
          <HeartPulse class="w-5 h-5 text-white" />
        </div>
        <span class="text-2xl font-bold text-white">BeatFlow</span>
      </div>

      <div class="bg-white rounded-2xl shadow-2xl p-8">
        <div class="mb-6">
          <h2 class="text-2xl font-bold text-gray-900">创建账户</h2>
          <p class="text-gray-500 text-sm mt-1">加入 BeatFlow，开始分析心音心电数据</p>
        </div>

        <form @submit.prevent="handleSubmit" class="space-y-4">
          <div class="grid grid-cols-2 gap-4">
            <div>
              <label class="label">姓名</label>
              <input v-model="form.full_name" type="text" placeholder="真实姓名" class="input" required />
            </div>
            <div>
              <label class="label">用户名</label>
              <input v-model="form.username" type="text" placeholder="用户名" class="input" required />
            </div>
          </div>

          <div>
            <label class="label">邮箱</label>
            <input
              v-model="form.email"
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
                v-model="form.password"
                :type="showPwd ? 'text' : 'password'"
                placeholder="至少 8 位，含大小写字母和数字"
                class="input pr-10"
                :class="{ 'input-error': pwdError }"
                required
              />
              <button type="button" class="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400" @click="showPwd = !showPwd">
                <component :is="showPwd ? EyeOff : Eye" class="w-4 h-4" />
              </button>
            </div>
          </div>

          <div>
            <label class="label">确认密码</label>
            <input
              v-model="form.confirm"
              :type="showPwd ? 'text' : 'password'"
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

          <div v-if="submitError" class="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
            {{ submitError }}
          </div>

          <button type="submit" class="btn-primary w-full btn-lg" :disabled="loading || !agreed">
            <span v-if="loading" class="spinner w-4 h-4" />
            {{ loading ? '注册中...' : '注册' }}
          </button>
        </form>

        <p class="text-center text-sm text-gray-500 mt-6">
          已有账号？
          <RouterLink to="/login" class="text-primary-600 font-medium">立即登录</RouterLink>
        </p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed } from 'vue'
import { useRouter, RouterLink } from 'vue-router'
import { HeartPulse, Eye, EyeOff } from 'lucide-vue-next'
import { useAuthStore } from '@/store/auth'
import { useToastStore } from '@/store/toast'

const router = useRouter()
const authStore = useAuthStore()
const toast = useToastStore()

const loading = ref(false)
const showPwd = ref(false)
const agreed = ref(false)
const submitError = ref('')
const form = reactive({ full_name: '', username: '', email: '', password: '', confirm: '' })

const emailError = computed(() => {
  if (!form.email) return ''
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email) ? '' : '请输入有效邮箱'
})

const pwdError = computed(() => {
  if (!form.password) return ''
  if (form.password.length < 8) return '密码至少 8 位'
  if (!/[a-z]/.test(form.password)) return '密码必须包含小写字母'
  if (!/[A-Z]/.test(form.password)) return '密码必须包含大写字母'
  if (!/[0-9]/.test(form.password)) return '密码必须包含数字'
  if (form.confirm && form.password !== form.confirm) return '两次密码不一致'
  return ''
})

const handleSubmit = async () => {
  if (emailError.value || pwdError.value) return
  submitError.value = ''
  loading.value = true
  const result = await authStore.register({
    full_name: form.full_name,
    username: form.username,
    email: form.email,
    password: form.password,
  })
  loading.value = false
  if (result.success) {
    toast.success('账户创建成功，请登录')
    router.push('/login')
  } else {
    submitError.value = result.error || '注册失败，请稍后重试'
  }
}
</script>

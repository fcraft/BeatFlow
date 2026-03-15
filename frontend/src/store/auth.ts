import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { User } from '@/types/user'

export const useAuthStore = defineStore('auth', () => {
  const user = ref<User | null>(null)
  const token = ref<string | null>(localStorage.getItem('token'))
  const isAuthenticated = computed(() => !!token.value)

  const login = async (email: string, password: string) => {
    try {
      const response = await fetch('/api/v1/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password })
      })
      if (!response.ok) {
        const errData = await response.json().catch(() => null)
        const message = errData?.detail || '登录失败'
        throw new Error(message)
      }
      const data = await response.json()
      // login returns flat UserWithToken object
      const { access_token, refresh_token, ...userData } = data
      user.value = userData
      token.value = access_token
      localStorage.setItem('token', access_token)
      return { success: true, user: userData }
    } catch (error) {
      return { success: false, error: (error as Error).message }
    }
  }

  const logout = () => {
    user.value = null
    token.value = null
    localStorage.removeItem('token')
  }

  const register = async (userData: Partial<User> & { password: string }) => {
    try {
      const response = await fetch('/api/v1/auth/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(userData)
      })
      if (!response.ok) {
        const errData = await response.json().catch(() => null)
        let message = '注册失败'
        if (errData?.detail) {
          if (typeof errData.detail === 'string') {
            message = errData.detail
          } else if (Array.isArray(errData.detail)) {
            message = errData.detail.map((e: any) => e.msg).join('；')
          }
        }
        throw new Error(message)
      }
      const data = await response.json()
      return { success: true, user: data.user }
    } catch (error) {
      return { success: false, error: (error as Error).message }
    }
  }

  const getCurrentUser = async () => {
    if (!token.value) return null
    try {
      const response = await fetch('/api/v1/auth/me', {
        headers: { 'Authorization': `Bearer ${token.value}` }
      })
      if (response.ok) {
        user.value = await response.json()
      } else {
        logout()
      }
    } catch {
      logout()
    }
  }

  return { user, token, isAuthenticated, login, logout, register, getCurrentUser }
})

/**
 * 全局 fetch 拦截器 — 监听 401 响应，自动处理登录态过期
 *
 * 使用方式：在 main.ts 中调用 installAuthInterceptor() 即可。
 * 原理：猴子补丁原生 fetch，对每个响应检查 status===401，
 *       触发 auth store logout + toast 提醒 + 跳转登录页。
 */

let installed = false
let handling401 = false  // 防抖：多个并发请求同时 401 时只提示一次

export function installAuthInterceptor() {
  if (installed) return
  installed = true

  const originalFetch = window.fetch.bind(window)

  window.fetch = async (...args: Parameters<typeof fetch>) => {
    const response = await originalFetch(...args)

    if (response.status === 401 && !handling401) {
      // 排除登录/注册请求本身（它们的 401 是正常业务错误）
      const url = typeof args[0] === 'string' ? args[0] : (args[0] as Request).url
      const isAuthEndpoint = url.includes('/auth/login') || url.includes('/auth/register')

      if (!isAuthEndpoint) {
        handling401 = true

        // 延迟导入避免循环依赖
        const { useAuthStore } = await import('@/store/auth')
        const { useToastStore } = await import('@/store/toast')
        const auth = useAuthStore()
        const toast = useToastStore()

        auth.logout()
        toast.warning('登录已过期，请重新登录', '认证失效')

        // 跳转到登录页（需要动态获取 router）
        const { default: router } = await import('@/router')
        const currentPath = router.currentRoute.value.fullPath
        if (currentPath !== '/login' && currentPath !== '/register') {
          router.push({ path: '/login', query: { redirect: currentPath } })
        }

        // 500ms 后重置防抖
        setTimeout(() => { handling401 = false }, 500)
      }
    }

    return response
  }
}

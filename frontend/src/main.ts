import { createApp } from 'vue'
import { createPinia } from 'pinia'

import App from './App.vue'
import router from './router'
import { installAuthInterceptor } from './composables/useAuthInterceptor'

import './styles/main.scss'

const app = createApp(App)
app.use(createPinia())
app.use(router)

// 安装全局 401 拦截器（登录态过期自动提醒 + 跳转登录页）
installAuthInterceptor()

app.mount('#app')

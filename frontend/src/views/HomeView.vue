<template>
  <div class="min-h-screen bg-gradient-to-br from-slate-900 via-primary-950 to-slate-900 flex flex-col">
    <!-- Nav -->
    <header class="flex items-center justify-between px-8 py-4">
      <div class="flex items-center gap-2.5">
        <div class="w-9 h-9 bg-primary-500 rounded-xl flex items-center justify-center">
          <HeartPulse class="w-5 h-5 text-white" />
        </div>
        <span class="text-xl font-bold text-white">BeatFlow</span>
      </div>
      <nav class="flex items-center gap-3">
        <RouterLink to="/login" class="btn-ghost text-white hover:bg-white/10">登录</RouterLink>
        <RouterLink to="/register" class="btn bg-white text-gray-900 border-white hover:bg-gray-100">注册</RouterLink>
      </nav>
    </header>

    <!-- Hero -->
    <main class="flex-1 flex flex-col items-center justify-center text-center px-8 py-20">
      <div class="inline-flex items-center gap-2 px-3 py-1.5 bg-primary-500/20 border border-primary-500/30 rounded-full text-primary-300 text-xs font-medium mb-8">
        <Activity class="w-3.5 h-3.5" />
        心音心电数据分析平台
      </div>

      <h1 class="text-5xl sm:text-6xl font-extrabold text-white leading-tight mb-6 max-w-3xl">
        专业的 <span class="text-primary-400">ECG/PCG</span><br />数据分析平台
      </h1>
      <p class="text-xl text-primary-200 max-w-xl mb-10 leading-relaxed">
        支持心音心电波形可视化、智能标记分析、多人协作与实时数据同步
      </p>

      <div class="flex items-center gap-4">
        <RouterLink to="/register" class="btn bg-primary-500 text-white border-primary-500 hover:bg-primary-400 btn-lg">
          免费开始使用
          <ArrowRight class="w-4 h-4" />
        </RouterLink>
        <RouterLink to="/login" class="btn bg-white/10 text-white border-white/20 hover:bg-white/20 btn-lg">
          登录账户
        </RouterLink>
      </div>

      <!-- Features -->
      <div class="grid grid-cols-1 sm:grid-cols-3 gap-5 mt-20 w-full max-w-3xl">
        <div v-for="feat in features" :key="feat.title"
          class="bg-white/5 border border-white/10 rounded-2xl p-6 text-left hover:bg-white/10 transition-colors">
          <div class="w-10 h-10 bg-primary-500/20 rounded-xl flex items-center justify-center mb-4">
            <component :is="feat.icon" class="w-5 h-5 text-primary-300" />
          </div>
          <h3 class="font-semibold text-white mb-1.5">{{ feat.title }}</h3>
          <p class="text-sm text-primary-300 leading-relaxed">{{ feat.desc }}</p>
        </div>
      </div>
    </main>

    <footer class="text-center text-primary-500 text-sm py-6">
      © 2026 BeatFlow · 专为心音心电研究设计
    </footer>
  </div>
</template>

<script setup lang="ts">
import { RouterLink } from 'vue-router'
import { HeartPulse, Activity, Tag, Users, BarChart2, ArrowRight } from 'lucide-vue-next'

const features = [
  { icon: Activity, title: '波形可视化', desc: '实时 ECG/PCG 波形展示，支持多文件同步播放与分析' },
  { icon: Tag,      title: '智能标记',   desc: '自动检测 S1/S2、QRS 等关键事件，支持手动精细标注' },
  { icon: Users,    title: '多人协作',   desc: '团队实时协同标记，WebSocket 数据同步与评论系统' },
]
</script>

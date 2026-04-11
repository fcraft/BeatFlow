<template>
  <div class="min-h-screen bg-gradient-to-br from-slate-900 via-primary-950 to-slate-900 flex">
    <!-- Left decorative panel (desktop only) -->
    <div class="hidden lg:flex flex-col justify-between w-[45%] p-12 text-white">
      <!-- Logo 占位 -->
      <div class="h-10" />

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

    <!-- Right panel: card rendered by SharedAuthCard, this is just the background -->
    <div class="flex-1 bg-white/5 backdrop-blur-sm lg:rounded-l-3xl" />
  </div>
</template>

<script setup lang="ts">
import { Activity, Tag, Users } from 'lucide-vue-next'

const features = [
  { icon: Activity, title: '波形可视化', desc: '实时 ECG/PCG 波形展示与播放控制' },
  { icon: Tag,      title: '智能标记',   desc: '自动检测 S1/S2、QRS 等关键心音事件' },
  { icon: Users,    title: '多人协作',   desc: '团队实时协同标记与数据审查' },
]
</script>

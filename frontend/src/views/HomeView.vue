<template>
  <div class="min-h-screen bg-gradient-to-b from-slate-950 via-slate-900 to-slate-950 text-white">
    <!-- ═══ Header ═══ -->
    <header class="fixed top-0 left-0 right-0 z-50 backdrop-blur-md bg-slate-950/70 border-b border-white/5">
      <div class="max-w-6xl mx-auto flex items-center justify-between px-6 h-16">
        <!-- Logo 占位（实际由 SharedLogo 渲染） -->
        <div class="w-[140px]" />
        <nav class="flex items-center gap-2">
          <RouterLink
            to="/login"
            class="px-4 py-2 text-sm font-medium text-primary-200 hover:text-white transition-colors no-underline"
          >登录</RouterLink>
          <RouterLink
            to="/register"
            class="px-5 py-2 text-sm font-medium bg-primary-500 hover:bg-primary-400 text-white rounded-lg transition-colors no-underline"
          >免费注册</RouterLink>
        </nav>
      </div>
    </header>

    <!-- ═══ Hero ═══ -->
    <section class="relative pt-32 pb-20 overflow-hidden">
      <!-- 背景装饰 -->
      <div class="absolute inset-0 overflow-hidden pointer-events-none">
        <div class="absolute top-20 left-1/2 -translate-x-1/2 w-[800px] h-[600px] bg-primary-500/10 rounded-full blur-[120px]" />
        <div class="absolute top-40 left-1/4 w-[300px] h-[300px] bg-blue-500/8 rounded-full blur-[80px]" />
        <div class="absolute top-60 right-1/4 w-[250px] h-[250px] bg-indigo-500/8 rounded-full blur-[80px]" />
      </div>

      <div class="relative max-w-4xl mx-auto text-center px-6">
        <!-- 标签 -->
        <div class="inline-flex items-center gap-2 px-4 py-1.5 bg-primary-500/15 border border-primary-500/25 rounded-full text-primary-300 text-xs font-medium mb-8 backdrop-blur-sm">
          <Activity class="w-3.5 h-3.5" />
          <span>专为心音心电研究设计的分析平台</span>
        </div>

        <h1 class="text-4xl sm:text-5xl lg:text-6xl font-extrabold leading-[1.15] mb-6 tracking-tight">
          专业的
          <span class="bg-gradient-to-r from-primary-400 via-blue-400 to-indigo-400 bg-clip-text text-transparent">
            ECG / PCG
          </span>
          <br class="hidden sm:block" />
          数据分析平台
        </h1>
        <p class="text-lg sm:text-xl text-slate-300 max-w-2xl mx-auto mb-10 leading-relaxed">
          支持心音心电波形可视化、智能事件检测与标注、多人实时协作，
          <br class="hidden sm:block" />
          助力高效科研与临床数据分析
        </p>

        <div class="flex flex-col sm:flex-row items-center justify-center gap-3">
          <RouterLink
            to="/register"
            class="btn bg-primary-500 text-white border-primary-500 hover:bg-primary-400 btn-lg group no-underline"
          >
            免费开始使用
            <ArrowRight class="w-4 h-4 transition-transform group-hover:translate-x-0.5" />
          </RouterLink>
          <RouterLink
            to="/login"
            class="btn bg-white/10 text-white border-white/15 hover:bg-white/15 btn-lg backdrop-blur-sm no-underline"
          >
            登录账户
          </RouterLink>
        </div>
      </div>
    </section>

    <!-- ═══ 数据统计 ═══ -->
    <section class="relative py-12">
      <div class="max-w-4xl mx-auto px-6">
        <div class="grid grid-cols-2 sm:grid-cols-4 gap-6 sm:gap-8">
          <div
            v-for="stat in stats" :key="stat.label"
            class="text-center"
          >
            <div class="text-3xl sm:text-4xl font-extrabold text-white mb-1">{{ stat.value }}</div>
            <div class="text-sm text-slate-400">{{ stat.label }}</div>
          </div>
        </div>
      </div>
    </section>

    <!-- ═══ 核心功能 ═══ -->
    <section class="py-20">
      <div class="max-w-5xl mx-auto px-6">
        <div class="text-center mb-14">
          <h2 class="text-3xl sm:text-4xl font-bold mb-4">强大的分析能力</h2>
          <p class="text-slate-400 text-lg max-w-xl mx-auto">从数据采集到分析报告，提供全链路的心音心电数据处理方案</p>
        </div>

        <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
          <div
            v-for="feat in features" :key="feat.title"
            class="group bg-white/[0.04] border border-white/[0.06] rounded-2xl p-6 hover:bg-white/[0.08] hover:border-primary-500/30 transition-all duration-300"
          >
            <div class="w-11 h-11 rounded-xl flex items-center justify-center mb-5"
              :class="feat.iconBg"
            >
              <component :is="feat.icon" class="w-5 h-5" :class="feat.iconColor" />
            </div>
            <h3 class="text-lg font-semibold text-white mb-2">{{ feat.title }}</h3>
            <p class="text-sm text-slate-400 leading-relaxed">{{ feat.desc }}</p>
          </div>
        </div>
      </div>
    </section>

    <!-- ═══ 工作流程 ═══ -->
    <section class="py-20 bg-white/[0.02]">
      <div class="max-w-5xl mx-auto px-6">
        <div class="text-center mb-14">
          <h2 class="text-3xl sm:text-4xl font-bold mb-4">简洁的工作流程</h2>
          <p class="text-slate-400 text-lg max-w-xl mx-auto">三步完成从数据上传到协作分析的全流程</p>
        </div>

        <div class="grid grid-cols-1 sm:grid-cols-3 gap-8">
          <div
            v-for="(step, idx) in steps" :key="step.title"
            class="relative text-center"
          >
            <div class="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-primary-500/15 border border-primary-500/25 mb-5">
              <span class="text-2xl font-bold text-primary-400">{{ idx + 1 }}</span>
            </div>
            <!-- 连接线 -->
            <div
              v-if="idx < steps.length - 1"
              class="hidden sm:block absolute top-7 left-[calc(50%+40px)] w-[calc(100%-80px)] border-t border-dashed border-white/10"
            />
            <h3 class="text-lg font-semibold text-white mb-2">{{ step.title }}</h3>
            <p class="text-sm text-slate-400 leading-relaxed">{{ step.desc }}</p>
          </div>
        </div>
      </div>
    </section>

    <!-- ═══ 技术优势 ═══ -->
    <section class="py-20">
      <div class="max-w-5xl mx-auto px-6">
        <div class="text-center mb-14">
          <h2 class="text-3xl sm:text-4xl font-bold mb-4">为什么选择 BeatFlow</h2>
          <p class="text-slate-400 text-lg max-w-xl mx-auto">专为心音心电研究场景深度定制的分析工具</p>
        </div>

        <div class="grid grid-cols-1 sm:grid-cols-2 gap-5">
          <div
            v-for="adv in advantages" :key="adv.title"
            class="flex gap-4 bg-white/[0.04] border border-white/[0.06] rounded-2xl p-6 hover:bg-white/[0.08] transition-colors"
          >
            <div class="w-10 h-10 rounded-xl bg-primary-500/15 flex items-center justify-center shrink-0">
              <component :is="adv.icon" class="w-5 h-5 text-primary-400" />
            </div>
            <div>
              <h3 class="font-semibold text-white mb-1">{{ adv.title }}</h3>
              <p class="text-sm text-slate-400 leading-relaxed">{{ adv.desc }}</p>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- ═══ CTA ═══ -->
    <section class="py-20">
      <div class="max-w-3xl mx-auto px-6 text-center">
        <div class="bg-gradient-to-br from-primary-500/15 via-blue-500/10 to-indigo-500/15 border border-primary-500/20 rounded-3xl p-12 sm:p-16 backdrop-blur-sm">
          <h2 class="text-3xl sm:text-4xl font-bold mb-4">立即开始使用</h2>
          <p class="text-slate-300 text-lg mb-8 max-w-lg mx-auto">
            免费创建账户，体验专业的心音心电数据分析平台
          </p>
          <div class="flex flex-col sm:flex-row items-center justify-center gap-3">
            <RouterLink
              to="/register"
              class="btn bg-primary-500 text-white border-primary-500 hover:bg-primary-400 btn-lg group no-underline"
            >
              免费注册
              <ArrowRight class="w-4 h-4 transition-transform group-hover:translate-x-0.5" />
            </RouterLink>
            <RouterLink
              to="/login"
              class="btn bg-white/10 text-white border-white/15 hover:bg-white/15 btn-lg no-underline"
            >
              已有账户？登录
            </RouterLink>
          </div>
        </div>
      </div>
    </section>

    <!-- ═══ Footer ═══ -->
    <footer class="border-t border-white/5 py-8">
      <div class="max-w-6xl mx-auto px-6 flex flex-col sm:flex-row items-center justify-between gap-4">
        <div class="flex items-center gap-2">
          <div class="w-7 h-7 bg-primary-500 rounded-lg flex items-center justify-center">
            <HeartPulse class="w-3.5 h-3.5 text-white" />
          </div>
          <span class="text-sm font-semibold text-white">BeatFlow</span>
        </div>
        <p class="text-sm text-slate-500">© 2026 BeatFlow · 专为心音心电研究设计</p>
      </div>
    </footer>
  </div>
</template>

<script setup lang="ts">
import { RouterLink } from 'vue-router'
import {
  HeartPulse, Activity, ArrowRight,
  BarChart2, Tag, Users, Zap, Share2, Shield,
  MonitorSmartphone, Database, Clock, Lock,
} from 'lucide-vue-next'

const stats = [
  { value: 'ECG', label: '心电数据支持' },
  { value: 'PCG', label: '心音数据支持' },
  { value: '实时', label: '多人协作同步' },
  { value: '全链路', label: '分析处理流程' },
]

const features = [
  { icon: BarChart2, title: '波形可视化', desc: '高精度实时 ECG/PCG 波形渲染，支持多导联同步显示与交互式缩放浏览', iconBg: 'bg-blue-500/15', iconColor: 'text-blue-400' },
  { icon: Tag, title: '智能检测标注', desc: '自动检测 S1/S2 心音事件、QRS 波群等关键特征，支持手动精细标注与校正', iconBg: 'bg-emerald-500/15', iconColor: 'text-emerald-400' },
  { icon: Users, title: '多人实时协作', desc: '基于 WebSocket 的团队实时协同标记，支持评论讨论与操作历史追溯', iconBg: 'bg-purple-500/15', iconColor: 'text-purple-400' },
  { icon: Zap, title: '模拟信号生成', desc: '内置虚拟人体引擎，可模拟多种心律模式的 ECG/PCG 信号数据', iconBg: 'bg-amber-500/15', iconColor: 'text-amber-400' },
  { icon: Share2, title: '一键分享', desc: '通过分享链接快速共享波形文件与标注结果，无需登录即可查看', iconBg: 'bg-rose-500/15', iconColor: 'text-rose-400' },
  { icon: Shield, title: '数据安全', desc: '基于项目的权限管理体系，支持成员角色分配与细粒度访问控制', iconBg: 'bg-cyan-500/15', iconColor: 'text-cyan-400' },
]

const steps = [
  { title: '上传数据', desc: '支持批量导入 ECG/PCG 文件，自动解析多种医疗数据格式' },
  { title: '分析标注', desc: '借助智能检测引擎自动标注关键事件，并支持手动精细调整' },
  { title: '协作分享', desc: '邀请团队成员实时协作，一键生成分享链接导出分析结果' },
]

const advantages = [
  { icon: MonitorSmartphone, title: '响应式设计', desc: '完美适配桌面与移动端，随时随地查看和分析数据' },
  { icon: Database, title: '项目化管理', desc: '以项目为单位组织数据文件，支持标签分类和全局搜索' },
  { icon: Clock, title: '实时同步', desc: 'WebSocket 驱动的毫秒级数据同步，确保团队成员看到一致的内容' },
  { icon: Lock, title: '安全可靠', desc: '完善的身份认证与授权机制，确保研究数据的安全性与隐私性' },
]
</script>

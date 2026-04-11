<template>
  <AppLayout>
    <div class="page-container">
      <!-- Header -->
      <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-6">
        <div>
          <h1 class="text-xl font-bold text-gray-900">信号模拟生成</h1>
          <p class="text-sm text-gray-500 mt-0.5">合成 ECG 心电图 + PCG 心音，支持多种心律异常及瓣膜病</p>
        </div>
      </div>

      <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">

        <!-- ── LEFT: Parameter Panel ─────────────────────────────── -->
        <div class="lg:col-span-2 space-y-5">

          <!-- Templates -->
          <div class="card p-5">
            <div class="flex items-center justify-between mb-3">
              <h3 class="text-sm font-semibold text-gray-900 flex items-center gap-2">
                <BookOpen class="w-4 h-4 text-blue-500" />一键套用模板
                <span v-if="lastTemplate" class="text-xs font-normal text-blue-600 bg-blue-50 px-2 py-0.5 rounded-full">
                  已选：{{ templates.find(t => t.id === lastTemplate)?.name ?? '' }}
                </span>
              </h3>
              <button class="text-xs text-gray-400 hover:text-gray-600 flex items-center gap-1 transition-colors"
                @click="showTemplates = !showTemplates">
                {{ showTemplates ? '收起' : '展开' }}
                <ChevronDown class="w-3.5 h-3.5 transition-transform" :class="showTemplates && 'rotate-180'" />
              </button>
            </div>

            <template v-if="showTemplates">
              <div v-if="loadingTemplates" class="flex justify-center py-6"><span class="spinner w-5 h-5" /></div>
              <template v-else>
                <!-- 搜索 + 分类筛选 -->
                <div class="flex flex-col sm:flex-row sm:items-center gap-2 mb-3">
                  <div class="relative flex-1">
                    <Search class="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-gray-400" />
                    <input v-model="templateSearch" type="text" placeholder="搜索模板..."
                      class="input pl-8 py-1.5 text-sm w-full" />
                  </div>
                  <div class="flex gap-1">
                    <button v-for="cat in TEMPLATE_CATEGORIES" :key="cat.value"
                      class="px-2.5 py-1 rounded-lg text-xs font-medium border transition-all"
                      :class="templateCategory === cat.value
                        ? 'bg-blue-500 text-white border-blue-500'
                        : 'bg-white text-gray-500 border-gray-200 hover:border-blue-300'"
                      @click="templateCategory = cat.value"
                    >{{ cat.label }}
                      <span class="ml-0.5 opacity-70">{{ cat.value === 'all' ? templates.length : templates.filter(t => t.category === cat.value).length }}</span>
                    </button>
                  </div>
                </div>

                <!-- 模板网格 -->
                <div v-if="filteredTemplates.length > 0" class="grid grid-cols-1 sm:grid-cols-2 gap-2">
                  <button
                    v-for="tpl in visibleTemplates"
                    :key="tpl.id"
                    class="text-left px-4 py-3 rounded-xl border transition-all duration-150"
                    :class="lastTemplate === tpl.id
                      ? 'border-blue-500 bg-blue-50'
                      : 'border-gray-200 hover:border-blue-300 hover:bg-gray-50'"
                    @click="applyTemplate(tpl)"
                  >
                    <div class="flex items-start justify-between gap-2">
                      <span class="text-sm font-medium text-gray-800 leading-tight">{{ tpl.name }}</span>
                      <span class="shrink-0 text-xs px-1.5 py-0.5 rounded-full font-medium"
                        :class="CATEGORY_BADGE[tpl.category] ?? 'bg-gray-100 text-gray-600'">
                        {{ CATEGORY_LABEL[tpl.category] ?? tpl.category }}
                      </span>
                    </div>
                    <p class="text-xs text-gray-400 mt-1 line-clamp-2">{{ tpl.description }}</p>
                  </button>
                </div>
                <p v-else class="text-sm text-gray-400 text-center py-4">无匹配模板</p>

                <!-- 展开更多 -->
                <button v-if="filteredTemplates.length > TEMPLATE_PAGE_SIZE && !templateShowAll"
                  class="mt-2 w-full text-xs text-blue-500 hover:text-blue-700 py-1.5 transition-colors"
                  @click="templateShowAll = true"
                >展开全部 {{ filteredTemplates.length }} 个模板 ↓</button>
                <button v-if="templateShowAll && filteredTemplates.length > TEMPLATE_PAGE_SIZE"
                  class="mt-2 w-full text-xs text-gray-400 hover:text-gray-600 py-1.5 transition-colors"
                  @click="templateShowAll = false"
                >收起 ↑</button>
              </template>
            </template>
          </div>

          <!-- ECG Parameters -->
          <div class="card p-5">
            <h3 class="text-sm font-semibold text-gray-900 mb-4 flex items-center gap-2">
              <Activity class="w-4 h-4 text-green-500" />ECG 参数
            </h3>
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <!-- Rhythm -->
              <div class="sm:col-span-2">
                <label class="label">心律类型</label>
                <div class="grid grid-cols-2 sm:grid-cols-4 gap-2">
                  <button
                    v-for="r in RHYTHMS"
                    :key="r.value"
                    class="flex flex-col items-start px-3 py-2.5 rounded-xl border text-left transition-all"
                    :class="form.ecg_rhythm === r.value
                      ? 'border-green-500 bg-green-50'
                      : 'border-gray-200 hover:border-green-300 hover:bg-gray-50'"
                    @click="form.ecg_rhythm = r.value; applyRhythmDefaults(r.value)"
                  >
                    <span class="text-xs font-semibold text-gray-800">{{ r.label }}</span>
                    <span class="text-xs text-gray-400 mt-0.5 leading-tight">{{ r.desc }}</span>
                  </button>
                </div>
              </div>

              <!-- Heart Rate -->
              <div>
                <label class="label">心率 (bpm) — {{ form.heart_rate }}</label>
                <div class="flex items-center gap-2">
                  <input type="range" v-model.number="form.heart_rate"
                    :min="hrRange.min" :max="hrRange.max" step="1" class="flex-1 accent-green-500" />
                  <input type="number" v-model.number="form.heart_rate"
                    :min="hrRange.min" :max="hrRange.max"
                    class="input w-20 text-center text-sm py-1" />
                </div>
              </div>

              <!-- HR std -->
              <div>
                <label class="label">心率变异 (SD) — {{ form.heart_rate_std }}</label>
                <div class="flex items-center gap-2">
                  <input type="range" v-model.number="form.heart_rate_std"
                    min="0" max="30" step="0.5" class="flex-1 accent-green-500" />
                  <span class="text-sm text-gray-600 w-10 text-right font-mono">{{ form.heart_rate_std }}</span>
                </div>
              </div>

              <!-- PVC ratio (only for pvc) -->
              <div v-if="form.ecg_rhythm === 'pvc'">
                <label class="label">PVC 比例 — {{ (form.pvc_ratio * 100).toFixed(0) }}%</label>
                <div class="flex items-center gap-2">
                  <input type="range" v-model.number="form.pvc_ratio"
                    min="0.05" max="0.5" step="0.05" class="flex-1 accent-orange-500" />
                  <span class="text-sm text-gray-600 w-10 text-right font-mono">{{ (form.pvc_ratio*100).toFixed(0) }}%</span>
                </div>
              </div>

              <!-- R-on-T parameters -->
              <template v-if="form.ecg_rhythm === 'ron_t'">
                <div class="sm:col-span-2 p-3 rounded-xl bg-red-50 border border-red-100">
                  <p class="text-xs text-red-700 mb-3 flex items-center gap-1.5">
                    <span class="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
                    R-on-T：PVC 落在 T 波易损期，可触发致命性心律失常
                  </p>
                  <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div>
                      <label class="label">触发 VT/VF 概率 — {{ (form.ron_t_vt_probability * 100).toFixed(0) }}%</label>
                      <input type="range" v-model.number="form.ron_t_vt_probability"
                        min="0" max="1" step="0.05" class="w-full accent-red-500" />
                    </div>
                    <div>
                      <label class="label">VF 比例 — {{ (form.ron_t_vf_ratio * 100).toFixed(0) }}%</label>
                      <input type="range" v-model.number="form.ron_t_vf_ratio"
                        min="0" max="1" step="0.05" class="w-full accent-red-500" />
                      <p class="text-xs text-gray-400 mt-1">0%=全 VT，100%=全 VF</p>
                    </div>
                  </div>
                </div>
              </template>

              <!-- Duration -->
              <div>
                <label class="label">时长（秒）— {{ form.duration }}s</label>
                <div class="flex items-center gap-2">
                  <input type="range" v-model.number="form.duration"
                    min="3" max="300" step="1" class="flex-1 accent-green-500" />
                  <span class="text-sm text-gray-600 w-10 text-right font-mono">{{ form.duration }}s</span>
                </div>
              </div>

              <!-- Noise -->
              <div>
                <label class="label">ECG 噪声 — {{ form.noise_level.toFixed(3) }}</label>
                <div class="flex items-center gap-2">
                  <input type="range" v-model.number="form.noise_level"
                    min="0" max="0.2" step="0.005" class="flex-1 accent-green-500" />
                  <span class="text-sm text-gray-600 w-12 text-right font-mono">{{ form.noise_level.toFixed(3) }}</span>
                </div>
              </div>
            </div>
          </div>

          <!-- PCG Parameters -->
          <div class="card p-5">
            <div class="flex items-center justify-between mb-4">
              <h3 class="text-sm font-semibold text-gray-900 flex items-center gap-2">
                <Waves class="w-4 h-4 text-purple-500" />PCG 心音参数
              </h3>
              <label class="flex items-center gap-2 cursor-pointer">
                <span class="text-xs text-gray-500">同时生成 PCG</span>
                <div class="relative inline-flex items-center">
                  <input type="checkbox" v-model="form.generate_pcg" class="sr-only peer" />
                  <div class="w-9 h-5 bg-gray-200 peer-checked:bg-purple-500 rounded-full transition-colors" />
                  <div class="absolute left-0.5 top-0.5 w-4 h-4 bg-white rounded-full shadow transition-transform peer-checked:translate-x-4" />
                </div>
              </label>
            </div>

            <template v-if="form.generate_pcg">
              <!-- PCG Abnormalities -->
              <div class="mb-4">
                <label class="label">心音异常（可多选）</label>
                <div class="grid grid-cols-1 sm:grid-cols-2 gap-2">
                  <label
                    v-for="ab in PCG_ABNORMALITIES"
                    :key="ab.value"
                    class="flex items-start gap-2.5 px-3 py-2.5 rounded-xl border cursor-pointer transition-all"
                    :class="form.pcg_abnormalities.includes(ab.value)
                      ? 'border-purple-400 bg-purple-50'
                      : 'border-gray-200 hover:border-purple-200'"
                  >
                    <input type="checkbox"
                      :value="ab.value"
                      v-model="form.pcg_abnormalities"
                      class="mt-0.5 accent-purple-500 shrink-0" />
                    <div>
                      <span class="text-sm font-medium text-gray-800">{{ ab.label }}</span>
                      <p class="text-xs text-gray-400 mt-0.5">{{ ab.desc }}</p>
                    </div>
                  </label>
                </div>
              </div>

              <div class="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <div>
                  <label class="label">S1 幅度 — {{ form.s1_amplitude.toFixed(1) }}×</label>
                  <input type="range" v-model.number="form.s1_amplitude"
                    min="0.1" max="3" step="0.1" class="w-full accent-purple-500" />
                </div>
                <div>
                  <label class="label">S2 幅度 — {{ form.s2_amplitude.toFixed(1) }}×</label>
                  <input type="range" v-model.number="form.s2_amplitude"
                    min="0.1" max="3" step="0.1" class="w-full accent-purple-500" />
                </div>
                <div>
                  <label class="label">背景噪声 — {{ form.pcg_noise_level.toFixed(4) }}</label>
                  <input type="range" v-model.number="form.pcg_noise_level"
                    min="0" max="0.05" step="0.001" class="w-full accent-purple-500" />
                </div>
              </div>

              <!-- 运动强度 -->
              <div class="mt-4">
                <label class="label flex items-center gap-2">
                  运动强度 — {{ form.exercise_intensity === 0 ? '静息' : form.exercise_intensity <= 0.3 ? '轻度' : form.exercise_intensity <= 0.6 ? '中度' : '剧烈' }}
                  <span class="text-xs text-gray-400 font-normal">（增加运动伪影和摩擦噪声）</span>
                </label>
                <div class="flex items-center gap-3">
                  <span class="text-xs text-gray-400 shrink-0">静息</span>
                  <input type="range" v-model.number="form.exercise_intensity"
                    min="0" max="1" step="0.05" class="flex-1 accent-orange-500" />
                  <span class="text-xs text-gray-400 shrink-0">剧烈</span>
                  <span class="text-sm font-mono text-gray-600 w-10 text-right">{{ (form.exercise_intensity * 100).toFixed(0) }}%</span>
                </div>
              </div>

              <!-- PCG 质量选项 -->
              <div class="mt-4 grid grid-cols-1 sm:grid-cols-2 gap-4">
                <!-- 采样率 -->
                <div>
                  <label class="label">PCG 采样率</label>
                  <div class="flex flex-wrap gap-2">
                    <button
                      v-for="sr in PCG_SAMPLE_RATES"
                      :key="sr.value"
                      @click="form.pcg_sample_rate = sr.value"
                      class="px-3 py-1.5 rounded-lg text-xs font-medium border transition-all"
                      :class="form.pcg_sample_rate === sr.value
                        ? 'bg-purple-500 text-white border-purple-500'
                        : 'bg-white text-gray-600 border-gray-200 hover:border-purple-300'"
                    >{{ sr.label }}</button>
                  </div>
                  <p class="text-xs text-gray-400 mt-1.5">
                    {{ form.pcg_sample_rate >= 44100 ? '高保真，适合研究分析' : form.pcg_sample_rate >= 16000 ? '中等质量，均衡选择' : '低采样率，文件较小' }}
                  </p>
                </div>

                <!-- 听诊器模式 -->
                <div>
                  <label class="label">音色模拟</label>
                  <label class="flex items-start gap-3 p-3 rounded-xl border cursor-pointer transition-all"
                    :class="form.stethoscope_mode ? 'border-purple-400 bg-purple-50' : 'border-gray-200 hover:border-purple-200'">
                    <input type="checkbox" v-model="form.stethoscope_mode" class="mt-0.5 accent-purple-500 shrink-0" />
                    <div>
                      <span class="text-sm font-medium text-gray-800">听诊器模式</span>
                      <p class="text-xs text-gray-500 mt-0.5">
                        对 PCG 进行频响塑形（20–800 Hz 通带 + 低频共鸣），使音频听起来像从听诊器中听到
                      </p>
                    </div>
                  </label>
                </div>
              </div>
            </template>
          </div>

          <!-- Advanced -->
          <div class="card p-5">
            <button class="w-full flex items-center justify-between text-sm font-semibold text-gray-700"
              @click="showAdvanced = !showAdvanced">
              <span class="flex items-center gap-2"><SlidersHorizontal class="w-4 h-4" />高级选项</span>
              <ChevronDown class="w-4 h-4 transition-transform" :class="showAdvanced && 'rotate-180'" />
            </button>
            <div v-if="showAdvanced" class="mt-4 grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label class="label">随机种子（空=随机）</label>
                <input v-model.number="form.random_seed" type="number" min="0"
                  placeholder="留空则每次随机" class="input" />
              </div>
              <div class="flex items-center pt-5">
                <AppCheckbox v-model="form.auto_detect" label="生成后自动创建标记（QRS/S1/S2 等）" />
              </div>
            </div>
          </div>
        </div>

        <!-- ── RIGHT: Project + Generate ────────────────────────── -->
        <div class="space-y-5">

          <!-- Project Selector -->
          <div class="card p-5">
            <h3 class="text-sm font-semibold text-gray-900 mb-3 flex items-center gap-2">
              <FolderOpen class="w-4 h-4 text-blue-500" />保存到项目
            </h3>
            <ProjectPicker v-model="form.project_id" placeholder="请选择目标项目" />
            <p class="text-xs text-gray-400 mt-2">ECG 和 PCG 文件将保存到所选项目中</p>
          </div>

          <!-- Generate Summary -->
          <div class="card p-5 bg-gradient-to-br from-blue-50 to-purple-50 border-blue-100">
            <h3 class="text-sm font-semibold text-gray-700 mb-3">生成预览</h3>
            <dl class="space-y-2 text-xs text-gray-600">
              <div class="flex justify-between">
                <dt class="text-gray-400">心律</dt>
                <dd class="font-medium text-gray-800">{{ rhythmLabel }}</dd>
              </div>
              <div class="flex justify-between">
                <dt class="text-gray-400">心率</dt>
                <dd class="font-medium text-gray-800">{{ form.heart_rate }} bpm</dd>
              </div>
              <div class="flex justify-between">
                <dt class="text-gray-400">时长</dt>
                <dd class="font-medium text-gray-800">{{ form.duration }}s</dd>
              </div>
              <div class="flex justify-between">
                <dt class="text-gray-400">预估 Beats</dt>
                <dd class="font-medium text-gray-800">~{{ estBeats }}</dd>
              </div>
              <div class="flex justify-between">
                <dt class="text-gray-400">PCG 心音异常</dt>
                <dd class="font-medium text-gray-800">
                  {{ form.generate_pcg
                    ? (form.pcg_abnormalities.length ? form.pcg_abnormalities.length + ' 项' : '正常')
                    : '不生成' }}
                </dd>
              </div>
              <div class="flex justify-between">
                <dt class="text-gray-400">输出文件</dt>
                <dd class="font-medium text-gray-800">{{ form.generate_pcg ? 'ECG + PCG' : 'ECG 仅' }}</dd>
              </div>
            </dl>

            <button
              class="mt-5 w-full btn-primary"
              :disabled="generating || !form.project_id"
              @click="generate"
            >
              <span v-if="generating" class="spinner w-4 h-4" />
              <Zap v-else class="w-4 h-4" />
              {{ generating ? '生成中…' : '开始生成' }}
            </button>
            <p v-if="!form.project_id" class="text-xs text-amber-600 mt-2 text-center">请先选择目标项目</p>
          </div>

          <!-- Result -->
          <div v-if="result" class="card p-5 border-green-200 bg-green-50">
            <div class="flex items-center gap-2 mb-3">
              <CheckCircle2 class="w-5 h-5 text-green-600 shrink-0" />
              <h3 class="text-sm font-semibold text-green-800">生成成功</h3>
            </div>
            <dl class="space-y-1.5 text-xs text-green-700 mb-4">
              <div class="flex justify-between"><dt>心律</dt><dd class="font-mono">{{ result.rhythm }}</dd></div>
              <div class="flex justify-between"><dt>R peaks</dt><dd class="font-mono">{{ result.r_peak_count }}</dd></div>
              <div class="flex justify-between"><dt>ECG 标记</dt><dd class="font-mono">{{ result.ecg_annotation_count }}</dd></div>
              <div v-if="result.pcg_file_id" class="flex justify-between"><dt>PCG 标记</dt><dd class="font-mono">{{ result.pcg_annotation_count }}</dd></div>
            </dl>
            <div class="flex flex-col gap-2">
              <RouterLink v-if="result.association_id"
                :to="`/sync/${result.association_id}`"
                class="btn-primary btn-sm w-full flex items-center justify-center gap-2">
                <Layers class="w-3.5 h-3.5" />同步预览 ECG + PCG
              </RouterLink>
              <RouterLink
                :to="`/files/${result.ecg_file_id}`"
                class="btn-secondary btn-sm w-full flex items-center justify-center gap-2">
                <Activity class="w-3.5 h-3.5" />查看 ECG 波形
              </RouterLink>
              <RouterLink v-if="result.pcg_file_id"
                :to="`/files/${result.pcg_file_id}`"
                class="btn-secondary btn-sm w-full flex items-center justify-center gap-2">
                <Waves class="w-3.5 h-3.5" />查看 PCG 心音
              </RouterLink>
              <RouterLink
                :to="`/projects/${form.project_id}?tab=associations`"
                class="btn-ghost btn-sm w-full flex items-center justify-center gap-2 text-green-700">
                <FolderOpen class="w-3.5 h-3.5" />查看项目关联列表
              </RouterLink>
            </div>
          </div>

          <!-- Recent generates (local history) -->
          <div v-if="history.length > 0" class="card p-5">
            <h3 class="text-sm font-semibold text-gray-900 mb-3 flex items-center gap-2">
              <History class="w-4 h-4 text-gray-400" />最近生成
            </h3>
            <div class="space-y-2">
              <div v-for="h in history.slice(0,5)" :key="h.ecg_file_id"
                class="flex items-center justify-between text-xs">
                <span class="text-gray-600 truncate flex-1">{{ h.rhythm }} · {{ h.heart_rate }}bpm · {{ h.duration }}s</span>
                <RouterLink :to="`/files/${h.ecg_file_id}`"
                  class="ml-2 text-blue-500 hover:underline shrink-0">ECG</RouterLink>
                <RouterLink v-if="h.pcg_file_id" :to="`/files/${h.pcg_file_id}`"
                  class="ml-2 text-purple-500 hover:underline shrink-0">PCG</RouterLink>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </AppLayout>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, nextTick } from 'vue'
import { RouterLink } from 'vue-router'
import {
  Activity, Waves, BookOpen, FolderOpen, Zap, CheckCircle2,
  SlidersHorizontal, ChevronDown, History, Layers, Search,
} from 'lucide-vue-next'
import AppLayout from '@/components/layout/AppLayout.vue'
import ProjectPicker from '@/components/ui/ProjectPicker.vue'
import AppCheckbox from '@/components/ui/AppCheckbox.vue'
import { useAuthStore } from '@/store/auth'
import { useToastStore } from '@/store/toast'

const auth = useAuthStore()
const toast = useToastStore()
const authHeader = computed((): Record<string, string> => auth.token ? { Authorization: `Bearer ${auth.token}` } : {})

// ── Data ───────────────────────────────────────────────────────────────────
const templates = ref<any[]>([])
const loadingTemplates = ref(false)
const generating = ref(false)
const result = ref<any>(null)
const lastTemplate = ref('')
const showAdvanced = ref(false)
const history = ref<any[]>([])

// ── Template filter/search ─────────────────────────────────────────────────
const showTemplates = ref(true)
const templateSearch = ref('')
const templateCategory = ref('all')
const templateShowAll = ref(false)
const TEMPLATE_PAGE_SIZE = 6

const TEMPLATE_CATEGORIES = [
  { value: 'all', label: '全部' },
  { value: 'normal', label: '正常' },
  { value: 'arrhythmia', label: '心律失常' },
  { value: 'valvular', label: '瓣膜病' },
]

const filteredTemplates = computed(() => {
  let list = templates.value
  if (templateCategory.value !== 'all') {
    list = list.filter(t => t.category === templateCategory.value)
  }
  const q = templateSearch.value.trim().toLowerCase()
  if (q) {
    list = list.filter(t =>
      t.name.toLowerCase().includes(q) || t.description.toLowerCase().includes(q)
    )
  }
  return list
})

const visibleTemplates = computed(() =>
  templateShowAll.value ? filteredTemplates.value : filteredTemplates.value.slice(0, TEMPLATE_PAGE_SIZE)
)

// ── Form ───────────────────────────────────────────────────────────────────
const form = ref({
  project_id: '',
  ecg_rhythm: 'normal',
  heart_rate: 72,
  heart_rate_std: 2,
  pvc_ratio: 0.15,
  noise_level: 0.01,
  duration: 10,
  generate_pcg: true,
  pcg_abnormalities: [] as string[],
  pcg_sample_rate: 8000,
  stethoscope_mode: true,
  pcg_noise_level: 0.003,
  s1_amplitude: 1.0,
  s2_amplitude: 0.7,
  exercise_intensity: 0.0,
  random_seed: null as number | null,
  auto_detect: true,
  // R-on-T specific
  ron_t_vt_probability: 0.6,
  ron_t_vf_ratio: 0.4,
})

// ── Rhythm definitions ─────────────────────────────────────────────────────
const RHYTHMS = [
  { value: 'normal',            label: '正常窦律',   desc: '60~100 bpm' },
  { value: 'tachycardia',       label: '窦性心动过速', desc: '≥100 bpm' },
  { value: 'bradycardia',       label: '窦性心动过缓', desc: '≤60 bpm' },
  { value: 'sinus_arrhythmia',  label: '窦性心律不齐', desc: '节律不规则' },
  { value: 'af',                label: '心房颤动 AF', desc: 'RR 完全不规则' },
  { value: 'pvc',               label: '室性早搏 PVC', desc: '宽QRS + 代偿间歇' },
  { value: 'svt',               label: '室上速 SVT',  desc: '130~250 bpm' },
  { value: 'vt',                label: '室性心动过速', desc: '宽QRS, 100~300bpm' },
  { value: 'ron_t',             label: 'R-on-T 🔴',   desc: 'PVC→VT/VF 危急' },
]

// HR range per rhythm
const HR_RANGE: Record<string, { min: number; max: number }> = {
  normal:           { min: 60, max: 100 },
  tachycardia:      { min: 100, max: 300 },
  bradycardia:      { min: 30, max: 60 },
  sinus_arrhythmia: { min: 40, max: 120 },
  af:               { min: 50, max: 200 },
  pvc:              { min: 50, max: 150 },
  svt:              { min: 130, max: 280 },
  vt:               { min: 100, max: 300 },
  ron_t:            { min: 50, max: 120 },
}
const hrRange = computed(() => HR_RANGE[form.value.ecg_rhythm] ?? { min: 30, max: 300 })

const RHYTHM_DEFAULTS: Record<string, Partial<typeof form.value>> = {
  normal:           { heart_rate: 72,  heart_rate_std: 2,  noise_level: 0.01 },
  tachycardia:      { heart_rate: 130, heart_rate_std: 3,  noise_level: 0.01 },
  bradycardia:      { heart_rate: 45,  heart_rate_std: 2,  noise_level: 0.01 },
  sinus_arrhythmia: { heart_rate: 72,  heart_rate_std: 15, noise_level: 0.015 },
  af:               { heart_rate: 90,  heart_rate_std: 5,  noise_level: 0.03 },
  pvc:              { heart_rate: 72,  heart_rate_std: 3,  pvc_ratio: 0.20, noise_level: 0.01 },
  svt:              { heart_rate: 190, heart_rate_std: 1,  noise_level: 0.01 },
  vt:               { heart_rate: 175, heart_rate_std: 2,  noise_level: 0.02 },
  ron_t:            { heart_rate: 72,  heart_rate_std: 2,  noise_level: 0.01 },
}

const applyRhythmDefaults = async (rhythm: string) => {
  const range = HR_RANGE[rhythm] ?? { min: 30, max: 300 }
  // 先等 hrRange computed 的新 min/max 渲染到 DOM
  await nextTick()
  const d = RHYTHM_DEFAULTS[rhythm]
  if (d) Object.assign(form.value, d)
  // clamp 心率到新范围内
  form.value.heart_rate = Math.max(range.min, Math.min(range.max, form.value.heart_rate))
}

// ── PCG Abnormalities ─────────────────────────────────────────────────────
const PCG_ABNORMALITIES = [
  { value: 'murmur_systolic',  label: '收缩期杂音', desc: 'S1→S2 之间高频吹风样杂音（二尖瓣关闭不全等）' },
  { value: 'murmur_diastolic', label: '舒张期杂音', desc: 'S2→下一S1 之间递减型杂音（主动脉瓣关闭不全等）' },
  { value: 'split_s2',         label: 'S2 分裂',    desc: 'S2 分裂为两个音（正常生理分裂或固定分裂）' },
  { value: 's3_gallop',        label: 'S3 奔马律',  desc: 'S2 后额外低频 S3（心力衰竭/容量负荷增加）' },
  { value: 's4_gallop',        label: 'S4 奔马律',  desc: 'S1 前额外低频 S4（高血压/肥厚型心肌病）' },
]

// ── PCG Sample Rates ────────────────────────────────────────────────────────
const PCG_SAMPLE_RATES = [
  { value: 4000,  label: '4 kHz' },
  { value: 8000,  label: '8 kHz' },
  { value: 16000, label: '16 kHz' },
  { value: 44100, label: '44.1 kHz' },
  { value: 48000, label: '48 kHz' },
]

const CATEGORY_BADGE: Record<string, string> = {
  normal:    'bg-green-100 text-green-700',
  arrhythmia:'bg-orange-100 text-orange-700',
  valvular:  'bg-purple-100 text-purple-700',
}
const CATEGORY_LABEL: Record<string, string> = {
  normal: '正常', arrhythmia: '心律失常', valvular: '瓣膜病',
}

// ── Computed ───────────────────────────────────────────────────────────────
const rhythmLabel = computed(
  () => RHYTHMS.find(r => r.value === form.value.ecg_rhythm)?.label ?? form.value.ecg_rhythm
)
const estBeats = computed(() => Math.round(form.value.heart_rate * form.value.duration / 60))

// ── Load data ──────────────────────────────────────────────────────────────
const loadTemplates = async () => {
  loadingTemplates.value = true
  const r = await fetch('/api/v1/simulate/templates', { headers: authHeader.value })
  loadingTemplates.value = false
  if (r.ok) templates.value = (await r.json()).templates
}

const applyTemplate = (tpl: any) => {
  lastTemplate.value = tpl.id
  Object.assign(form.value, tpl.params)
}

// ── Generate ───────────────────────────────────────────────────────────────
const generate = async () => {
  if (!form.value.project_id) { toast.error('请先选择目标项目'); return }
  generating.value = true
  result.value = null
  try {
    const body = { ...form.value }
    if (!body.random_seed) delete (body as any).random_seed
    const r = await fetch('/api/v1/simulate/generate', {
      method: 'POST',
      headers: { ...authHeader.value, 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    const data = await r.json()
    if (!r.ok) throw new Error(data.detail ?? '生成失败')
    result.value = data
    history.value.unshift(data)
    toast.success(`生成完成：${data.r_peak_count} 个 R peaks，${data.ecg_annotation_count + data.pcg_annotation_count} 个标记`)
  } catch (e: any) {
    toast.error(e.message ?? '生成失败')
  } finally {
    generating.value = false
  }
}

onMounted(() => {
  loadTemplates()
})
</script>

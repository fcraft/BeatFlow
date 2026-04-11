<script setup lang="ts">
/**
 * ComponentTestView — 项目组件展示测试页
 *
 * 用于快速预览和测试各种 UI 组件的表现。
 */
import { ref } from 'vue'
import AppLayout from '@/components/layout/AppLayout.vue'
import AppModal from '@/components/ui/AppModal.vue'
import AppCheckbox from '@/components/ui/AppCheckbox.vue'
import AppSwitch from '@/components/ui/AppSwitch.vue'
import AppSelect from '@/components/ui/AppSelect.vue'
import AppSegment from '@/components/ui/AppSegment.vue'
import AppMiniSelect from '@/components/ui/AppMiniSelect.vue'
import AppDropdown from '@/components/ui/AppDropdown.vue'
import { Download, ChevronDown, FileText } from 'lucide-vue-next'
import { useToastStore } from '@/store/toast'
import ProjectPicker from '@/components/ui/ProjectPicker.vue'
import FilePicker from '@/components/ui/FilePicker.vue'

const toast = useToastStore()

// ─── Toast demos ───
function fireSuccess() {
  toast.success('文件上传成功', '完成')
}
function fireError() {
  toast.error('网络连接失败，请检查网络设置')
}
function fireWarning() {
  toast.warning('登录即将过期，请及时保存工作', '注意')
}
function fireInfo() {
  toast.info('新版本 v2.1 已发布')
}
function fireWithAction() {
  toast.error('文件已删除', {
    title: '操作完成',
    duration: 8000,
    action: {
      label: '撤销',
      onClick: () => toast.success('已撤销删除'),
    },
  })
}
function fireMultiple() {
  toast.success('第 1 条：保存成功')
  setTimeout(() => toast.info('第 2 条：数据同步中'), 300)
  setTimeout(() => toast.warning('第 3 条：内存使用率 > 80%', '警告'), 600)
}
function fireLongAction() {
  toast.warning('你有未保存的更改', {
    title: '离开前确认',
    duration: 15000,
    action: {
      label: '立即保存',
      onClick: () => toast.success('已保存'),
    },
  })
}
function fireNoTitle() {
  toast.success('这是一条没有标题的简短通知')
}

// ─── Modal demo ───
const showModal = ref(false)
const showDangerModal = ref(false)

// ─── Checkbox demo ───
const check1 = ref(false)
const check2 = ref(true)
const check3 = ref(false)

// ─── Switch demo ───
const sw1 = ref(false)
const sw2 = ref(true)
const sw3 = ref(false)

// ─── Select demo ───
const sel1 = ref('beijing')
const sel2 = ref('')
const selectOptions = [
  { value: 'beijing', label: '北京' },
  { value: 'shanghai', label: '上海' },
  { value: 'guangzhou', label: '广州' },
  { value: 'shenzhen', label: '深圳' },
  { value: 'hangzhou', label: '杭州' },
]

// ─── Segment demo ───
const segMode = ref('a')
const segSize = ref('sm')
const segOptions = [
  { value: 'a', label: '选项 A' },
  { value: 'b', label: '选项 B' },
  { value: 'c', label: '选项 C' },
]
const segSizeOptions = [
  { value: 'xs', label: 'XS' },
  { value: 'sm', label: 'SM' },
  { value: 'md', label: 'MD' },
]

// ─── MiniSelect demo ───
const miniVal = ref(5)
const miniStr = ref('ecg')
const miniOptions = [
  { value: 1, label: '1 秒' }, { value: 2, label: '2 秒' },
  { value: 5, label: '5 秒' }, { value: 10, label: '10 秒' },
  { value: 30, label: '30 秒' },
]
const miniTypeOptions = [
  { value: 'ecg', label: 'ECG' }, { value: 'pcg', label: 'PCG' },
  { value: 'audio', label: '音频' }, { value: 'video', label: '视频' },
]

// ─── ProjectPicker & FilePicker demo ───
const pickerProjectId = ref('')
const pickerFileId = ref('')
</script>

<template>
  <AppLayout>
    <div class="max-w-4xl mx-auto px-6 py-8 space-y-10">
      <!-- Page header -->
      <div>
        <h1 class="text-2xl font-bold text-gray-900">组件测试</h1>
        <p class="text-sm text-gray-500 mt-1">用于预览和测试项目中各种 UI 组件的表现效果</p>
      </div>

      <!-- ─── Toast ─── -->
      <section>
        <h2 class="text-lg font-semibold text-gray-800 mb-1">Toast 通知</h2>
        <p class="text-sm text-gray-500 mb-4">磨砂玻璃风格，支持 4 种类型、Action 按钮、多条堆叠</p>

        <div class="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
          <button class="test-btn test-btn--emerald" @click="fireSuccess">Success</button>
          <button class="test-btn test-btn--red" @click="fireError">Error</button>
          <button class="test-btn test-btn--amber" @click="fireWarning">Warning</button>
          <button class="test-btn test-btn--blue" @click="fireInfo">Info</button>
        </div>
        <div class="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <button class="test-btn test-btn--slate" @click="fireWithAction">带 Action</button>
          <button class="test-btn test-btn--slate" @click="fireMultiple">多条堆叠</button>
          <button class="test-btn test-btn--slate" @click="fireLongAction">长倒计时</button>
          <button class="test-btn test-btn--slate" @click="fireNoTitle">无标题</button>
        </div>
      </section>

      <!-- ─── Modal ─── -->
      <section>
        <h2 class="text-lg font-semibold text-gray-800 mb-1">Modal 对话框</h2>
        <p class="text-sm text-gray-500 mb-4">通用模态框，v-model 控制显隐</p>

        <div class="flex gap-3">
          <button class="test-btn test-btn--blue" @click="showModal = true">普通 Modal</button>
          <button class="test-btn test-btn--red" @click="showDangerModal = true">危险操作</button>
        </div>

        <AppModal v-model="showModal" title="示例对话框">
          <p class="text-sm text-gray-600">这是一个普通的模态框内容区域。</p>
          <template #footer>
            <div class="flex justify-end gap-2">
              <button class="px-4 py-2 text-sm text-gray-600 hover:bg-gray-100 rounded-lg" @click="showModal = false">取消</button>
              <button class="px-4 py-2 text-sm text-white bg-primary-600 hover:bg-primary-700 rounded-lg" @click="showModal = false; toast.success('已确认')">确认</button>
            </div>
          </template>
        </AppModal>

        <AppModal v-model="showDangerModal" title="确认删除">
          <p class="text-sm text-gray-600">此操作不可撤销，确定要删除该项目吗？</p>
          <template #footer>
            <div class="flex justify-end gap-2">
              <button class="px-4 py-2 text-sm text-gray-600 hover:bg-gray-100 rounded-lg" @click="showDangerModal = false">取消</button>
              <button class="px-4 py-2 text-sm text-white bg-red-600 hover:bg-red-700 rounded-lg" @click="showDangerModal = false; toast.error('已删除', '操作完成')">删除</button>
            </div>
          </template>
        </AppModal>
      </section>

      <!-- ─── Form Controls ─── -->
      <section>
        <h2 class="text-lg font-semibold text-gray-800 mb-1">表单控件</h2>
        <p class="text-sm text-gray-500 mb-4">Checkbox、Switch、Select 自定义组件</p>

        <div class="grid grid-cols-1 sm:grid-cols-3 gap-6">
          <!-- Checkbox -->
          <div class="flex flex-col gap-4">
            <h3 class="text-sm font-medium text-gray-600">Checkbox</h3>
            <AppCheckbox v-model="check1" label="未选中" />
            <AppCheckbox v-model="check2" label="已选中" />
            <AppCheckbox v-model="check3" disabled label="禁用" />
            <AppCheckbox v-model="check1">
              <span class="text-sm text-gray-600">
                同意 <a href="#" class="text-primary-600">条款</a>
              </span>
            </AppCheckbox>
          </div>

          <!-- Switch -->
          <div class="flex flex-col gap-4">
            <h3 class="text-sm font-medium text-gray-600">Switch</h3>
            <AppSwitch v-model="sw1" label="关闭" />
            <AppSwitch v-model="sw2" label="开启" />
            <AppSwitch v-model="sw3" disabled label="禁用" />
          </div>

          <!-- Select -->
          <div class="flex flex-col gap-4">
            <h3 class="text-sm font-medium text-gray-600">Select</h3>
            <div>
              <label class="label">基础下拉</label>
              <AppSelect v-model="sel1" :options="selectOptions" block />
            </div>
            <div>
              <label class="label">可搜索</label>
              <AppSelect v-model="sel2" :options="selectOptions" placeholder="选择城市" searchable search-placeholder="搜索城市..." block />
            </div>
          </div>
        </div>
      </section>

      <!-- ─── Segment ─── -->
      <section>
        <h2 class="text-lg font-semibold text-gray-800 mb-1">Segment 分段选择器</h2>
        <p class="text-sm text-gray-500 mb-4">互斥按钮组，支持 xs/sm/md 三种尺寸</p>

        <div class="space-y-4">
          <div class="flex flex-wrap items-center gap-4">
            <div>
              <label class="label mb-1">尺寸切换</label>
              <AppSegment v-model="segSize" :options="segSizeOptions" size="xs" />
            </div>
            <div>
              <label class="label mb-1">当前尺寸：{{ segSize }}</label>
              <AppSegment v-model="segMode" :options="segOptions" :size="segSize as any" />
            </div>
          </div>
          <div>
            <label class="label mb-1">Block 模式（撑满宽度）</label>
            <AppSegment v-model="segMode" :options="segOptions" size="sm" block class="max-w-sm" />
          </div>
          <p class="text-xs text-gray-400">当前值：<code class="bg-gray-100 px-1 rounded">{{ segMode }}</code></p>
        </div>
      </section>

      <!-- ─── MiniSelect ─── -->
      <section>
        <h2 class="text-lg font-semibold text-gray-800 mb-1">MiniSelect 紧凑下拉</h2>
        <p class="text-sm text-gray-500 mb-4">自绘下拉（非系统原生），支持 xs/sm/md 尺寸、numeric 模式</p>

        <div class="flex flex-wrap items-end gap-6">
          <div>
            <label class="label">数值（numeric）</label>
            <AppMiniSelect v-model="miniVal" :options="miniOptions" size="sm" numeric />
          </div>
          <div>
            <label class="label">字符串</label>
            <AppMiniSelect v-model="miniStr" :options="miniTypeOptions" size="sm" />
          </div>
          <div>
            <label class="label">XS 尺寸</label>
            <AppMiniSelect v-model="miniVal" :options="miniOptions" size="xs" numeric />
          </div>
          <div>
            <label class="label">MD 尺寸</label>
            <AppMiniSelect v-model="miniStr" :options="miniTypeOptions" size="md" />
          </div>
          <div>
            <label class="label">禁用</label>
            <AppMiniSelect v-model="miniStr" :options="miniTypeOptions" size="sm" disabled />
          </div>
        </div>
        <p class="text-xs text-gray-400 mt-2">数值：<code class="bg-gray-100 px-1 rounded">{{ miniVal }}</code> ({{ typeof miniVal }})　字符串：<code class="bg-gray-100 px-1 rounded">{{ miniStr }}</code></p>
      </section>

      <!-- ─── Dropdown ─── -->
      <section>
        <h2 class="text-lg font-semibold text-gray-800 mb-1">Dropdown 下拉菜单</h2>
        <p class="text-sm text-gray-500 mb-4">通用 trigger + 菜单项，Teleport + 动态 z-index</p>

        <div class="flex gap-4">
          <AppDropdown>
            <template #trigger="{ isOpen }">
              <button class="btn-primary btn-sm flex items-center gap-1">
                操作菜单
                <ChevronDown class="w-3 h-3" :class="isOpen && 'rotate-180'" style="transition: transform 0.15s" />
              </button>
            </template>
            <template #default="{ close }">
              <button class="w-full text-left px-4 py-2 text-sm hover:bg-gray-50 flex items-center gap-2" @click="toast.success('导出成功'); close()">
                <FileText class="w-3.5 h-3.5 text-green-600" />导出 CSV
              </button>
              <button class="w-full text-left px-4 py-2 text-sm hover:bg-gray-50 flex items-center gap-2" @click="toast.info('已复制'); close()">
                <Download class="w-3.5 h-3.5 text-blue-600" />下载文件
              </button>
            </template>
          </AppDropdown>

          <AppDropdown>
            <template #trigger>
              <button class="test-btn test-btn--slate">更多选项 ▾</button>
            </template>
            <template #default="{ close }">
              <button class="w-full text-left px-4 py-2 text-sm hover:bg-gray-50" @click="close()">选项 A</button>
              <button class="w-full text-left px-4 py-2 text-sm hover:bg-gray-50" @click="close()">选项 B</button>
              <button class="w-full text-left px-4 py-2 text-sm text-red-600 hover:bg-red-50" @click="close()">危险操作</button>
            </template>
          </AppDropdown>
        </div>
      </section>

      <!-- ─── ProjectPicker & FilePicker ─── -->
      <section>
        <h2 class="text-lg font-semibold text-gray-800 mb-1">ProjectPicker & FilePicker</h2>
        <p class="text-sm text-gray-500 mb-4">项目选择器（支持搜索+新建）和文件选择器（依赖项目 ID、支持搜索+类型 badge）</p>

        <div class="grid grid-cols-1 sm:grid-cols-2 gap-4 max-w-lg">
          <div>
            <label class="label">选择项目</label>
            <ProjectPicker v-model="pickerProjectId" />
          </div>
          <div>
            <label class="label">选择文件</label>
            <FilePicker v-model="pickerFileId" :project-id="pickerProjectId" :placeholder="pickerProjectId ? '请选择文件' : '请先选择项目'" />
          </div>
        </div>
        <p class="text-xs text-gray-400 mt-2">
          项目 ID：<code class="bg-gray-100 px-1 rounded">{{ pickerProjectId || '—' }}</code>　
          文件 ID：<code class="bg-gray-100 px-1 rounded">{{ pickerFileId || '—' }}</code>
        </p>
      </section>

      <!-- ─── Typography ─── -->
      <section>
        <h2 class="text-lg font-semibold text-gray-800 mb-1">排版</h2>
        <p class="text-sm text-gray-500 mb-4">项目中使用的字体层级</p>

        <div class="space-y-3 p-5 bg-white rounded-xl border border-gray-200">
          <div class="text-2xl font-bold text-gray-900">Heading 2xl — 页面标题</div>
          <div class="text-xl font-semibold text-gray-800">Heading xl — 区块标题</div>
          <div class="text-lg font-semibold text-gray-800">Heading lg — 子标题</div>
          <div class="text-base text-gray-700">Body base — 正文内容 14px</div>
          <div class="text-sm text-gray-600">Body sm — 辅助信息 13px</div>
          <div class="text-xs text-gray-500">Caption xs — 标签/时间戳 12px</div>
        </div>
      </section>

      <!-- ─── Colors ─── -->
      <section>
        <h2 class="text-lg font-semibold text-gray-800 mb-1">主题色板</h2>
        <p class="text-sm text-gray-500 mb-4">Tailwind 项目色板</p>

        <div class="grid grid-cols-5 sm:grid-cols-11 gap-2">
          <div class="aspect-square rounded-lg flex items-center justify-center text-[10px] font-mono bg-primary-50 text-primary-900">50</div>
          <div class="aspect-square rounded-lg flex items-center justify-center text-[10px] font-mono bg-primary-100 text-primary-900">100</div>
          <div class="aspect-square rounded-lg flex items-center justify-center text-[10px] font-mono bg-primary-200 text-primary-900">200</div>
          <div class="aspect-square rounded-lg flex items-center justify-center text-[10px] font-mono bg-primary-300 text-primary-900">300</div>
          <div class="aspect-square rounded-lg flex items-center justify-center text-[10px] font-mono bg-primary-400 text-white">400</div>
          <div class="aspect-square rounded-lg flex items-center justify-center text-[10px] font-mono bg-primary-500 text-white">500</div>
          <div class="aspect-square rounded-lg flex items-center justify-center text-[10px] font-mono bg-primary-600 text-white">600</div>
          <div class="aspect-square rounded-lg flex items-center justify-center text-[10px] font-mono bg-primary-700 text-white">700</div>
          <div class="aspect-square rounded-lg flex items-center justify-center text-[10px] font-mono bg-primary-800 text-white">800</div>
          <div class="aspect-square rounded-lg flex items-center justify-center text-[10px] font-mono bg-primary-900 text-white">900</div>
          <div class="aspect-square rounded-lg flex items-center justify-center text-[10px] font-mono bg-primary-950 text-white">950</div>
        </div>

        <div class="flex gap-3 mt-4">
          <div class="flex-1 h-10 rounded-lg bg-emerald-500 flex items-center justify-center text-white text-xs font-medium">Success</div>
          <div class="flex-1 h-10 rounded-lg bg-red-500 flex items-center justify-center text-white text-xs font-medium">Error</div>
          <div class="flex-1 h-10 rounded-lg bg-amber-500 flex items-center justify-center text-white text-xs font-medium">Warning</div>
          <div class="flex-1 h-10 rounded-lg bg-blue-500 flex items-center justify-center text-white text-xs font-medium">Info</div>
        </div>
      </section>

      <!-- ─── Buttons ─── -->
      <section>
        <h2 class="text-lg font-semibold text-gray-800 mb-1">按钮</h2>
        <p class="text-sm text-gray-500 mb-4">项目中的按钮样式</p>

        <div class="flex flex-wrap gap-3">
          <button class="btn-primary btn-lg">Primary Large</button>
          <button class="btn-primary">Primary Default</button>
          <button class="btn-primary btn-lg" disabled>Disabled</button>
          <button class="px-4 py-2 text-sm text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50">Secondary</button>
          <button class="px-4 py-2 text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg hover:bg-red-100">Danger</button>
        </div>
      </section>

      <!-- ─── Inputs ─── -->
      <section>
        <h2 class="text-lg font-semibold text-gray-800 mb-1">表单输入</h2>
        <p class="text-sm text-gray-500 mb-4">输入框与表单控件</p>

        <div class="grid grid-cols-1 sm:grid-cols-2 gap-4 max-w-lg">
          <div>
            <label class="label">文本输入</label>
            <input type="text" class="input" placeholder="请输入..." />
          </div>
          <div>
            <label class="label">邮箱</label>
            <input type="email" class="input" placeholder="you@example.com" />
          </div>
          <div>
            <label class="label">错误状态</label>
            <input type="text" class="input input-error" value="invalid" />
            <p class="text-xs text-red-500 mt-1">该字段不合法</p>
          </div>
          <div>
            <label class="label">禁用状态</label>
            <input type="text" class="input" value="不可编辑" disabled />
          </div>
        </div>
      </section>
    </div>
  </AppLayout>
</template>

<style scoped>
.test-btn {
  padding: 8px 16px;
  font-size: 13px;
  font-weight: 600;
  border-radius: 10px;
  transition: all 0.15s;
  cursor: pointer;
  border: 1px solid transparent;
}
.test-btn:active { transform: scale(0.97); }

.test-btn--emerald { background: #ecfdf5; color: #059669; border-color: #a7f3d0; }
.test-btn--emerald:hover { background: #d1fae5; }

.test-btn--red { background: #fef2f2; color: #dc2626; border-color: #fecaca; }
.test-btn--red:hover { background: #fee2e2; }

.test-btn--amber { background: #fffbeb; color: #d97706; border-color: #fde68a; }
.test-btn--amber:hover { background: #fef3c7; }

.test-btn--blue { background: #eff6ff; color: #2563eb; border-color: #bfdbfe; }
.test-btn--blue:hover { background: #dbeafe; }

.test-btn--slate { background: #f8fafc; color: #475569; border-color: #e2e8f0; }
.test-btn--slate:hover { background: #f1f5f9; }
</style>

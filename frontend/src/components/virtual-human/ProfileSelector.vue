<script setup lang="ts">
/**
 * 档案选择器：连接前显示，列出用户虚拟人档案卡片。
 * 支持选择已有档案连接、新建档案、或进入演示模式。
 */
import { ref, onMounted } from 'vue'
import { Plus, Trash2, Play, User } from 'lucide-vue-next'
import { useVirtualHumanStore } from '@/store/virtualHuman'

const store = useVirtualHumanStore()

const showNewForm = ref(false)
const newName = ref('')
const creating = ref(false)

onMounted(() => {
  store.fetchProfiles()
})

async function createNew() {
  if (!newName.value.trim()) return
  creating.value = true
  const id = await store.createProfile(newName.value.trim())
  creating.value = false
  showNewForm.value = false
  newName.value = ''
  if (id) {
    store.connect(id)
  }
}

function connectProfile(id: string) {
  store.connect(id)
}

function connectDemo() {
  store.connect()
}

async function removeProfile(id: string, e: Event) {
  e.stopPropagation()
  if (confirm('确定删除此档案？状态将无法恢复。')) {
    await store.deleteProfile(id)
  }
}

function rhythmLabel(rhythm: string | null): string {
  if (!rhythm) return '—'
  const map: Record<string, string> = {
    normal: '正常', af: '房颤', pvc: '早搏', vt: 'VT', svt: 'SVT',
  }
  return map[rhythm] || rhythm
}
</script>

<template>
  <div class="space-y-4">
    <div class="flex items-center justify-between">
      <h2 class="text-lg font-semibold text-white/80">我的虚拟人</h2>
      <button
        class="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-sky-400 border border-sky-400/30 rounded-lg hover:bg-sky-500/10 transition-colors"
        @click="showNewForm = !showNewForm"
      >
        <Plus :size="14" />
        新建
      </button>
    </div>

    <!-- 新建表单 -->
    <div v-if="showNewForm" class="flex gap-2 items-center bg-white/[0.04] border border-white/10 rounded-lg p-3">
      <input
        v-model="newName"
        type="text"
        placeholder="输入名称（如：小明）"
        class="flex-1 px-3 py-1.5 text-sm bg-white/[0.06] border border-white/10 rounded-md text-white placeholder-white/30 focus:outline-none focus:ring-1 focus:ring-sky-400/50"
        maxlength="100"
        @keyup.enter="createNew"
      />
      <button
        :disabled="creating || !newName.trim()"
        class="px-3 py-1.5 text-xs font-medium text-white bg-primary-500 rounded-md hover:bg-primary-600 disabled:opacity-50 transition-colors"
        @click="createNew"
      >
        {{ creating ? '创建中...' : '创建并连接' }}
      </button>
    </div>

    <!-- 档案列表 -->
    <div v-if="store.loadingProfiles" class="text-center text-sm text-white/30 py-8">
      加载中...
    </div>

    <div v-else-if="store.profiles.length > 0" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
      <div
        v-for="p in store.profiles"
        :key="p.id"
        class="relative bg-white/[0.04] border border-white/10 rounded-xl p-5 hover:border-sky-400/30 hover:bg-white/[0.06] transition-all cursor-pointer group"
        @click="connectProfile(p.id)"
      >
        <!-- 删除按钮 -->
        <button
          class="absolute top-2 right-2 p-1 text-white/20 hover:text-red-400 opacity-0 group-hover:opacity-100 transition-all"
          title="删除档案"
          @click="removeProfile(p.id, $event)"
        >
          <Trash2 :size="14" />
        </button>

        <div class="flex items-center gap-2 mb-2">
          <div class="w-8 h-8 bg-sky-500/20 text-sky-400 rounded-full flex items-center justify-center">
            <User :size="16" />
          </div>
          <span class="font-medium text-white/80 text-sm truncate">{{ p.name }}</span>
        </div>

        <div class="text-xs text-white/30 space-y-0.5">
          <div v-if="p.heart_rate">HR: {{ Math.round(p.heart_rate) }} bpm</div>
          <div v-if="p.rhythm">{{ rhythmLabel(p.rhythm) }}</div>
          <div v-if="!p.heart_rate && !p.rhythm" class="text-white/20">新建档案</div>
        </div>

        <div class="mt-3">
          <button
            class="w-full flex items-center justify-center gap-1 px-2 py-1.5 text-xs font-medium text-sky-400 bg-sky-500/10 border border-sky-500/20 rounded-md hover:bg-sky-500/20 transition-colors"
          >
            <Play :size="12" />
            连接
          </button>
        </div>
      </div>
    </div>

    <div v-else class="text-center text-sm text-white/30 py-8">
      暂无档案，点击"新建"创建第一个虚拟人
    </div>

    <!-- 演示模式 -->
    <div class="border-t border-white/10 pt-3">
      <button
        class="w-full py-2.5 text-sm text-white/40 border border-dashed border-white/20 rounded-lg hover:bg-white/5 hover:text-white/60 transition-colors"
        @click="connectDemo"
      >
        演示模式
      </button>
    </div>
  </div>
</template>

<template>
  <AppLayout>
    <div class="max-w-6xl mx-auto px-4 sm:px-6 py-8">
      <!-- 页面标题 -->
      <div class="mb-6">
        <h1 class="text-xl font-bold text-gray-900">系统管理</h1>
        <p class="text-sm text-gray-500 mt-0.5">管理用户、文件和社区内容</p>
      </div>

      <!-- Tabs -->
      <div class="flex gap-1 mb-6 border-b border-gray-200">
        <button
          v-for="tab in tabs"
          :key="tab.key"
          class="px-4 py-2 text-sm font-medium border-b-2 transition-colors -mb-px"
          :class="activeTab === tab.key
            ? 'border-primary-600 text-primary-700'
            : 'border-transparent text-gray-500 hover:text-gray-700'"
          @click="activeTab = tab.key; loadTab()"
        >
          {{ tab.label }}
        </button>
      </div>

      <!-- ═══ 概览 ═══ -->
      <div v-if="activeTab === 'overview'">
        <div v-if="statsLoading" class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4">
          <div v-for="n in 5" :key="n" class="card p-5 animate-pulse">
            <div class="h-4 bg-gray-200 rounded w-2/3 mb-3" />
            <div class="h-8 bg-gray-100 rounded w-1/2" />
          </div>
        </div>
        <div v-else class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4">
          <div class="card p-5">
            <p class="text-xs text-gray-500 mb-1">注册用户</p>
            <p class="text-3xl font-bold text-gray-900">{{ stats?.user_count ?? 0 }}</p>
          </div>
          <div class="card p-5">
            <p class="text-xs text-gray-500 mb-1">项目数</p>
            <p class="text-3xl font-bold text-gray-900">{{ stats?.project_count ?? 0 }}</p>
          </div>
          <div class="card p-5">
            <p class="text-xs text-gray-500 mb-1">文件数</p>
            <p class="text-3xl font-bold text-gray-900">{{ stats?.file_count ?? 0 }}</p>
          </div>
          <div class="card p-5">
            <p class="text-xs text-gray-500 mb-1">帖子数</p>
            <p class="text-3xl font-bold text-gray-900">{{ stats?.post_count ?? 0 }}</p>
          </div>
          <div class="card p-5">
            <p class="text-xs text-gray-500 mb-1">总存储量</p>
            <p class="text-2xl font-bold text-gray-900">{{ formatBytes(stats?.total_storage_bytes ?? 0) }}</p>
          </div>
        </div>

        <!-- 发送公告 -->
        <div class="card p-5 mt-6">
          <h2 class="text-sm font-semibold text-gray-900 mb-4">发送系统公告</h2>
          <div class="space-y-3">
            <input v-model="announcement.title" type="text" placeholder="公告标题" class="input" />
            <textarea v-model="announcement.content" rows="3" placeholder="公告内容" class="input resize-none" />
            <button
              class="btn-primary btn-sm"
              :disabled="sendingAnnouncement || !announcement.title.trim()"
              @click="sendAnnouncement"
            >
              <span v-if="sendingAnnouncement" class="spinner w-3.5 h-3.5" />
              发送给所有用户
            </button>
          </div>
        </div>
      </div>

      <!-- ═══ 用户管理 ═══ -->
      <div v-if="activeTab === 'users'">
        <div class="flex items-center gap-3 mb-4">
          <input
            v-model="userQuery"
            type="text"
            placeholder="搜索用户名 / 邮箱..."
            class="input flex-1 max-w-xs"
            @input="debouncedLoadUsers"
          />
          <span class="text-sm text-gray-500">共 {{ userTotal }} 人</span>
        </div>

        <div class="card overflow-hidden">
          <div v-if="usersLoading" class="p-8 text-center text-gray-400 text-sm">加载中...</div>
          <table v-else class="w-full text-sm">
            <thead class="bg-gray-50 border-b border-gray-200">
              <tr>
                <th class="px-4 py-3 text-left text-xs font-medium text-gray-500">用户</th>
                <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 hidden sm:table-cell">邮箱</th>
                <th class="px-4 py-3 text-left text-xs font-medium text-gray-500">角色</th>
                <th class="px-4 py-3 text-left text-xs font-medium text-gray-500">状态</th>
                <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 hidden md:table-cell">注册时间</th>
                <th class="px-4 py-3 text-right text-xs font-medium text-gray-500">操作</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-gray-100">
              <tr v-for="u in users" :key="u.id" class="hover:bg-gray-50">
                <td class="px-4 py-3">
                  <div class="flex items-center gap-2">
                    <div class="w-7 h-7 bg-primary-100 text-primary-700 rounded-full flex items-center justify-center text-xs font-semibold shrink-0">
                      {{ u.username[0]?.toUpperCase() }}
                    </div>
                    <div>
                      <div class="font-medium text-gray-900">{{ u.username }}</div>
                      <div v-if="u.is_superuser" class="text-xs text-amber-600">超级管理员</div>
                    </div>
                  </div>
                </td>
                <td class="px-4 py-3 text-gray-500 hidden sm:table-cell">{{ u.email }}</td>
                <td class="px-4 py-3">
                  <select
                    :value="u.role"
                    class="text-xs border border-gray-200 rounded px-1.5 py-0.5 bg-white"
                    :disabled="u.is_superuser"
                    @change="updateRole(u.id, ($event.target as HTMLSelectElement).value)"
                  >
                    <option value="member">成员</option>
                    <option value="admin">管理员</option>
                  </select>
                </td>
                <td class="px-4 py-3">
                  <span
                    class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium"
                    :class="u.is_active ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'"
                  >{{ u.is_active ? '正常' : '已封禁' }}</span>
                </td>
                <td class="px-4 py-3 text-gray-400 text-xs hidden md:table-cell">{{ formatDate(u.created_at) }}</td>
                <td class="px-4 py-3 text-right">
                  <button
                    class="text-xs px-2 py-1 rounded transition-colors"
                    :class="u.is_active
                      ? 'text-red-600 hover:bg-red-50'
                      : 'text-green-600 hover:bg-green-50'"
                    :disabled="u.is_superuser"
                    @click="toggleActive(u)"
                  >
                    {{ u.is_active ? '封禁' : '激活' }}
                  </button>
                </td>
              </tr>
              <tr v-if="users.length === 0">
                <td colspan="6" class="px-4 py-8 text-center text-gray-400 text-sm">暂无用户</td>
              </tr>
            </tbody>
          </table>
        </div>
        <Pagination :page="userPage" :total="userTotal" :size="userSize" @change="p => { userPage = p; loadUsers() }" />
      </div>

      <!-- ═══ 文件管理 ═══ -->
      <div v-if="activeTab === 'files'">
        <div class="flex items-center gap-3 mb-4">
          <input
            v-model="fileQuery"
            type="text"
            placeholder="搜索文件名..."
            class="input flex-1 max-w-xs"
            @input="debouncedLoadFiles"
          />
          <span class="text-sm text-gray-500">共 {{ fileTotal }} 个文件</span>
          <!-- 批量删除按钮 -->
          <button
            v-if="selectedFileIds.size > 0"
            class="btn-sm bg-red-600 text-white hover:bg-red-700 rounded px-3 py-1.5 text-xs font-medium transition-colors"
            :disabled="batchDeleting"
            @click="batchDeleteFiles"
          >
            <span v-if="batchDeleting" class="spinner w-3 h-3 mr-1" />
            删除选中 ({{ selectedFileIds.size }})
          </button>
        </div>

        <div class="card overflow-hidden">
          <div v-if="filesLoading" class="p-8 text-center text-gray-400 text-sm">加载中...</div>
          <table v-else class="w-full text-sm">
            <thead class="bg-gray-50 border-b border-gray-200">
              <tr>
                <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 w-8">
                  <input
                    type="checkbox"
                    class="rounded border-gray-300"
                    :checked="files.length > 0 && selectedFileIds.size === files.length"
                    :indeterminate="selectedFileIds.size > 0 && selectedFileIds.size < files.length"
                    @change="toggleSelectAll"
                  />
                </th>
                <th class="px-4 py-3 text-left text-xs font-medium text-gray-500">文件名</th>
                <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 hidden sm:table-cell">所属项目</th>
                <th class="px-4 py-3 text-left text-xs font-medium text-gray-500">大小</th>
                <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 hidden md:table-cell">类型</th>
                <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 hidden md:table-cell">上传时间</th>
                <th class="px-4 py-3 text-right text-xs font-medium text-gray-500">操作</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-gray-100">
              <tr v-for="f in files" :key="f.id" class="hover:bg-gray-50" :class="selectedFileIds.has(f.id) ? 'bg-blue-50' : ''">
                <td class="px-4 py-3">
                  <input
                    type="checkbox"
                    class="rounded border-gray-300"
                    :checked="selectedFileIds.has(f.id)"
                    @change="toggleSelectFile(f.id)"
                  />
                </td>
                <td class="px-4 py-3">
                  <RouterLink
                    :to="`/files/${f.id}`"
                    class="font-medium text-primary-600 hover:underline truncate max-w-[200px] block"
                  >
                    {{ f.original_filename }}
                  </RouterLink>
                </td>
                <td class="px-4 py-3 text-gray-500 hidden sm:table-cell truncate max-w-[150px]">{{ f.project_name ?? f.project_id }}</td>
                <td class="px-4 py-3 text-gray-500">{{ formatBytes(f.file_size) }}</td>
                <td class="px-4 py-3 hidden md:table-cell">
                  <span class="badge-gray text-xs">{{ f.file_type }}</span>
                </td>
                <td class="px-4 py-3 text-gray-400 text-xs hidden md:table-cell">{{ formatDate(f.created_at) }}</td>
                <td class="px-4 py-3 text-right">
                  <button
                    class="text-xs text-red-600 hover:bg-red-50 px-2 py-1 rounded transition-colors"
                    @click="deleteFile(f.id)"
                  >删除</button>
                </td>
              </tr>
              <tr v-if="files.length === 0">
                <td colspan="7" class="px-4 py-8 text-center text-gray-400 text-sm">暂无文件</td>
              </tr>
            </tbody>
          </table>
        </div>
        <Pagination :page="filePage" :total="fileTotal" :size="fileSize" @change="p => { filePage = p; loadFiles() }" />
      </div>

      <!-- ═══ 社区管理 ═══ -->
      <div v-if="activeTab === 'community'">
        <div class="flex items-center gap-3 mb-4">
          <span class="text-sm text-gray-500">共 {{ postTotal }} 篇帖子</span>
        </div>

        <div class="card overflow-hidden">
          <div v-if="postsLoading" class="p-8 text-center text-gray-400 text-sm">加载中...</div>
          <table v-else class="w-full text-sm">
            <thead class="bg-gray-50 border-b border-gray-200">
              <tr>
                <th class="px-4 py-3 text-left text-xs font-medium text-gray-500">标题</th>
                <th class="px-4 py-3 text-left text-xs font-medium text-gray-500">作者</th>
                <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 hidden sm:table-cell">点赞</th>
                <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 hidden sm:table-cell">评论</th>
                <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 hidden md:table-cell">发布时间</th>
                <th class="px-4 py-3 text-right text-xs font-medium text-gray-500">操作</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-gray-100">
              <tr v-for="p in posts" :key="p.id" class="hover:bg-gray-50">
                <td class="px-4 py-3">
                  <button class="font-medium text-primary-600 hover:underline text-left truncate max-w-[250px]"
                    @click="openAdminPost(p)">{{ p.title }}</button>
                </td>
                <td class="px-4 py-3 text-gray-500">{{ p.author_username }}</td>
                <td class="px-4 py-3 text-gray-500 hidden sm:table-cell">{{ p.likes_count }}</td>
                <td class="px-4 py-3 text-gray-500 hidden sm:table-cell">{{ p.comments_count }}</td>
                <td class="px-4 py-3 text-gray-400 text-xs hidden md:table-cell">{{ formatDate(p.created_at) }}</td>
                <td class="px-4 py-3 text-right">
                  <button
                    class="text-xs text-red-600 hover:bg-red-50 px-2 py-1 rounded transition-colors"
                    @click="deletePost(p.id)"
                  >删除</button>
                </td>
              </tr>
              <tr v-if="posts.length === 0">
                <td colspan="6" class="px-4 py-8 text-center text-gray-400 text-sm">暂无帖子</td>
              </tr>
            </tbody>
          </table>
        </div>
        <Pagination :page="postPage" :total="postTotal" :size="postSize" @change="p => { postPage = p; loadPosts() }" />
      </div>

      <!-- ═══ 系统设置 ═══ -->
      <div v-if="activeTab === 'settings'">
        <div class="card p-6 space-y-6">
          <h2 class="text-sm font-semibold text-gray-900">存储配置</h2>

          <!-- 存储类型 -->
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-2">存储类型</label>
            <div class="flex gap-4">
              <label class="flex items-center gap-2 cursor-pointer">
                <input
                  type="radio"
                  name="storage_type"
                  value="local"
                  :checked="settingsForm.storage_type === 'local'"
                  class="text-primary-600"
                  @change="settingsForm.storage_type = 'local'"
                />
                <span class="text-sm text-gray-700">本地存储</span>
              </label>
              <label class="flex items-center gap-2 cursor-pointer">
                <input
                  type="radio"
                  name="storage_type"
                  value="cos"
                  :checked="settingsForm.storage_type === 'cos'"
                  class="text-primary-600"
                  @change="settingsForm.storage_type = 'cos'"
                />
                <span class="text-sm text-gray-700">腾讯云 COS (S3 兼容)</span>
              </label>
            </div>
          </div>

          <!-- COS 配置表单 -->
          <div v-if="settingsForm.storage_type === 'cos'" class="space-y-4 border-t pt-4">
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label class="block text-xs font-medium text-gray-600 mb-1">SecretId</label>
                <input v-model="settingsForm.cos_secret_id" type="text" class="input" placeholder="AKIDxxxxxxxx" />
              </div>
              <div>
                <label class="block text-xs font-medium text-gray-600 mb-1">SecretKey</label>
                <input v-model="settingsForm.cos_secret_key" type="password" class="input" placeholder="密钥" />
              </div>
              <div>
                <label class="block text-xs font-medium text-gray-600 mb-1">Bucket</label>
                <input v-model="settingsForm.cos_bucket_name" type="text" class="input" placeholder="bucket-1250000000" />
              </div>
              <div>
                <label class="block text-xs font-medium text-gray-600 mb-1">Region</label>
                <input v-model="settingsForm.cos_region" type="text" class="input" placeholder="ap-guangzhou" />
              </div>
              <div class="sm:col-span-2">
                <label class="block text-xs font-medium text-gray-600 mb-1">Endpoint (可选)</label>
                <input v-model="settingsForm.cos_endpoint" type="text" class="input" placeholder="https://cos.ap-guangzhou.myqcloud.com (留空自动生成)" />
              </div>
            </div>
          </div>

          <!-- 操作按钮 -->
          <div class="flex items-center gap-3 border-t pt-4">
            <button
              class="btn-primary btn-sm"
              :disabled="savingSettings"
              @click="saveSettings"
            >
              <span v-if="savingSettings" class="spinner w-3.5 h-3.5 mr-1" />
              保存设置
            </button>
            <button
              class="btn-secondary btn-sm"
              :disabled="testingStorage"
              @click="testStorage"
            >
              <span v-if="testingStorage" class="spinner w-3.5 h-3.5 mr-1" />
              测试连接
            </button>
            <span v-if="storageTestResult" class="text-sm" :class="storageTestResult.success ? 'text-green-600' : 'text-red-600'">
              {{ storageTestResult.message }}
            </span>
          </div>
        </div>
      </div>
    </div>
  </AppLayout>

  <!-- ── 帖子详情 Modal ─────────────────────────────────────── -->
  <AppModal v-model="showAdminPostDetail" :title="adminSelectedPost?.title ?? ''" width="680px">
    <div v-if="adminSelectedPost" class="space-y-4">
      <!-- 元信息 -->
      <div class="flex items-center gap-3 text-sm text-gray-500">
        <div class="w-7 h-7 rounded-full bg-blue-100 text-blue-600 flex items-center justify-center text-xs font-semibold">
          {{ adminSelectedPost.author_username?.[0]?.toUpperCase() ?? '?' }}
        </div>
        <span class="font-medium text-gray-700">{{ adminSelectedPost.author_username }}</span>
        <span>{{ formatDate(adminSelectedPost.created_at) }}</span>
        <span class="ml-auto flex items-center gap-3 text-xs">
          <span>👁 {{ adminSelectedPost.view_count }}</span>
          <span>❤ {{ adminSelectedPost.like_count }}</span>
        </span>
      </div>

      <!-- 正文 -->
      <p class="text-sm text-gray-800 leading-relaxed whitespace-pre-wrap border rounded-lg p-3 bg-gray-50">
        {{ adminSelectedPost.content }}
      </p>

      <!-- 标签 -->
      <div v-if="adminSelectedPost.tags?.length" class="flex flex-wrap gap-1.5">
        <span v-for="tag in adminSelectedPost.tags" :key="tag"
          class="px-2 py-0.5 text-xs rounded-full bg-gray-100 text-gray-600">{{ tag }}</span>
      </div>

      <!-- 评论区 -->
      <div class="border-t pt-4">
        <h3 class="text-sm font-semibold text-gray-700 mb-3">评论 ({{ adminComments.length }})</h3>
        <div v-if="adminCommentsLoading" class="text-center py-4 text-gray-400 text-sm">加载中...</div>
        <div v-else class="space-y-3 max-h-64 overflow-y-auto">
          <div v-for="c in adminComments" :key="c.id" class="flex gap-2.5">
            <div class="w-7 h-7 rounded-full bg-gray-100 text-gray-600 flex items-center justify-center text-xs font-semibold shrink-0">
              {{ c.author_username?.[0]?.toUpperCase() ?? '?' }}
            </div>
            <div class="flex-1">
              <div class="flex items-center gap-2 mb-0.5">
                <span class="text-xs font-medium text-gray-700">{{ c.author_username }}</span>
                <span class="text-xs text-gray-400">{{ formatDate(c.created_at) }}</span>
                <button class="ml-auto text-xs text-red-500 hover:text-red-700"
                  @click="adminDeleteComment(c.id)">删除</button>
              </div>
              <p class="text-sm text-gray-700">{{ c.content }}</p>
            </div>
          </div>
          <div v-if="adminComments.length === 0" class="text-xs text-gray-400 text-center py-2">暂无评论</div>
        </div>
      </div>

      <!-- 底部操作 -->
      <div class="flex justify-end border-t pt-3">
        <button class="text-xs text-red-600 hover:bg-red-50 px-3 py-1.5 rounded transition-colors"
          @click="deletePostFromDetail">删除帖子</button>
      </div>
    </div>
  </AppModal>
</template>

<script setup lang="ts">
import { ref, onMounted, defineComponent, h } from 'vue'
import { RouterLink } from 'vue-router'
import AppLayout from '@/components/layout/AppLayout.vue'
import AppModal from '@/components/ui/AppModal.vue'
import { useToastStore } from '@/store/toast'

const toast = useToastStore()

// ---- Pagination 子组件 ----
const Pagination = defineComponent({
  props: {
    page: { type: Number, required: true },
    total: { type: Number, required: true },
    size: { type: Number, required: true },
  },
  emits: ['change'],
  setup(props, { emit }) {
    const totalPages = () => Math.max(1, Math.ceil(props.total / props.size))
    return () => props.total <= props.size ? null : h('div', {
      class: 'flex items-center justify-center gap-3 mt-4',
    }, [
      h('button', {
        class: 'btn-secondary btn-sm',
        disabled: props.page <= 1,
        onClick: () => emit('change', props.page - 1),
      }, '上一页'),
      h('span', { class: 'text-sm text-gray-500' }, `${props.page} / ${totalPages()}`),
      h('button', {
        class: 'btn-secondary btn-sm',
        disabled: props.page >= totalPages(),
        onClick: () => emit('change', props.page + 1),
      }, '下一页'),
    ])
  },
})

const authHeaders = () => ({
  Authorization: `Bearer ${localStorage.getItem('token')}`,
  'Content-Type': 'application/json',
})

const tabs = [
  { key: 'overview', label: '概览' },
  { key: 'users', label: '用户管理' },
  { key: 'files', label: '文件管理' },
  { key: 'community', label: '社区管理' },
  { key: 'settings', label: '系统设置' },
]
const activeTab = ref('overview')

// ---- 概览 ----
const stats = ref<any>(null)
const statsLoading = ref(false)
const announcement = ref({ title: '', content: '' })
const sendingAnnouncement = ref(false)

const loadStats = async () => {
  statsLoading.value = true
  const r = await fetch('/api/v1/admin/stats', { headers: authHeaders() })
  if (r.ok) stats.value = await r.json()
  statsLoading.value = false
}

const sendAnnouncement = async () => {
  sendingAnnouncement.value = true
  const r = await fetch('/api/v1/admin/announcements', {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify(announcement.value),
  })
  sendingAnnouncement.value = false
  if (r.ok) {
    const data = await r.json()
    toast.success(`公告已发送给 ${data.sent_to} 名用户`)
    announcement.value = { title: '', content: '' }
  } else {
    const err = await r.json().catch(() => ({}))
    toast.error(err.detail || '发送失败')
  }
}

// ---- 用户管理 ----
const users = ref<any[]>([])
const usersLoading = ref(false)
const userPage = ref(1)
const userSize = 20
const userTotal = ref(0)
const userQuery = ref('')

let userDebounceTimer: ReturnType<typeof setTimeout>
const debouncedLoadUsers = () => {
  clearTimeout(userDebounceTimer)
  userDebounceTimer = setTimeout(() => { userPage.value = 1; loadUsers() }, 400)
}

const loadUsers = async () => {
  usersLoading.value = true
  const params = new URLSearchParams({ page: String(userPage.value), size: String(userSize) })
  if (userQuery.value) params.set('q', userQuery.value)
  const r = await fetch(`/api/v1/admin/users?${params}`, { headers: authHeaders() })
  if (r.ok) {
    const data = await r.json()
    users.value = data.items
    userTotal.value = data.total
  }
  usersLoading.value = false
}

const toggleActive = async (user: any) => {
  const r = await fetch(`/api/v1/admin/users/${user.id}/toggle-active`, {
    method: 'PATCH',
    headers: authHeaders(),
  })
  if (r.ok) {
    const data = await r.json()
    user.is_active = data.is_active
    toast.success(data.is_active ? '账号已激活' : '账号已封禁')
  } else {
    const err = await r.json().catch(() => ({}))
    toast.error(err.detail || '操作失败')
  }
}

const updateRole = async (userId: string, role: string) => {
  const r = await fetch(`/api/v1/admin/users/${userId}/role`, {
    method: 'PATCH',
    headers: authHeaders(),
    body: JSON.stringify({ role }),
  })
  if (r.ok) {
    const u = users.value.find(u => u.id === userId)
    if (u) u.role = role
    toast.success('角色已更新')
  } else {
    const err = await r.json().catch(() => ({}))
    toast.error(err.detail || '操作失败')
  }
}

// ---- 文件管理 ----
const files = ref<any[]>([])
const filesLoading = ref(false)
const filePage = ref(1)
const fileSize = 20
const fileTotal = ref(0)
const fileQuery = ref('')
const selectedFileIds = ref<Set<string>>(new Set())
const batchDeleting = ref(false)

let fileDebounceTimer: ReturnType<typeof setTimeout>
const debouncedLoadFiles = () => {
  clearTimeout(fileDebounceTimer)
  fileDebounceTimer = setTimeout(() => { filePage.value = 1; loadFiles() }, 400)
}

const loadFiles = async () => {
  filesLoading.value = true
  selectedFileIds.value = new Set()
  const params = new URLSearchParams({ page: String(filePage.value), size: String(fileSize) })
  if (fileQuery.value) params.set('q', fileQuery.value)
  const r = await fetch(`/api/v1/admin/files?${params}`, { headers: authHeaders() })
  if (r.ok) {
    const data = await r.json()
    files.value = data.items
    fileTotal.value = data.total
  }
  filesLoading.value = false
}

const toggleSelectFile = (id: string) => {
  const s = new Set(selectedFileIds.value)
  if (s.has(id)) s.delete(id)
  else s.add(id)
  selectedFileIds.value = s
}

const toggleSelectAll = () => {
  if (selectedFileIds.value.size === files.value.length) {
    selectedFileIds.value = new Set()
  } else {
    selectedFileIds.value = new Set(files.value.map(f => f.id))
  }
}

const deleteFile = async (id: string) => {
  if (!confirm('确认删除该文件？此操作不可恢复。')) return
  const r = await fetch(`/api/v1/admin/files/${id}`, {
    method: 'DELETE',
    headers: authHeaders(),
  })
  if (r.ok) {
    files.value = files.value.filter(f => f.id !== id)
    fileTotal.value--
    const s = new Set(selectedFileIds.value)
    s.delete(id)
    selectedFileIds.value = s
    toast.success('文件已删除')
  } else toast.error('删除失败')
}

const batchDeleteFiles = async () => {
  const ids = Array.from(selectedFileIds.value)
  if (ids.length === 0) return
  if (!confirm(`确认删除选中的 ${ids.length} 个文件？此操作不可恢复。`)) return

  batchDeleting.value = true
  const r = await fetch('/api/v1/admin/files/batch', {
    method: 'DELETE',
    headers: authHeaders(),
    body: JSON.stringify({ file_ids: ids }),
  })
  batchDeleting.value = false

  if (r.ok) {
    const data = await r.json()
    toast.success(`已删除 ${data.deleted} 个文件${data.failed.length > 0 ? `，${data.failed.length} 个失败` : ''}`)
    await loadFiles()
  } else {
    const err = await r.json().catch(() => ({}))
    toast.error(err.detail || '批量删除失败')
  }
}

// ---- 社区管理 ----
const posts = ref<any[]>([])
const postsLoading = ref(false)
const postPage = ref(1)
const postSize = 20
const postTotal = ref(0)

// ---- 帖子详情 Modal ----
const adminSelectedPost = ref<any>(null)
const showAdminPostDetail = ref(false)
const adminComments = ref<any[]>([])
const adminCommentsLoading = ref(false)

const openAdminPost = async (post: any) => {
  adminSelectedPost.value = post
  showAdminPostDetail.value = true
  adminCommentsLoading.value = true
  const [detailRes, commentRes] = await Promise.all([
    fetch(`/api/v1/community/posts/${post.id}`, { headers: authHeaders() }),
    fetch(`/api/v1/community/posts/${post.id}/comments`, { headers: authHeaders() }),
  ])
  adminCommentsLoading.value = false
  if (detailRes.ok) adminSelectedPost.value = await detailRes.json()
  if (commentRes.ok) adminComments.value = (await commentRes.json()).items
}

const adminDeleteComment = async (commentId: string) => {
  if (!adminSelectedPost.value) return
  const r = await fetch(
    `/api/v1/community/posts/${adminSelectedPost.value.id}/comments/${commentId}`,
    { method: 'DELETE', headers: authHeaders() }
  )
  if (r.ok) {
    adminComments.value = adminComments.value.filter(c => c.id !== commentId)
    toast.success('评论已删除')
  } else toast.error('删除失败')
}

const deletePostFromDetail = async () => {
  if (!adminSelectedPost.value || !confirm('确认删除该帖子？')) return
  const r = await fetch(`/api/v1/admin/community/posts/${adminSelectedPost.value.id}`, {
    method: 'DELETE', headers: authHeaders(),
  })
  if (r.ok) {
    showAdminPostDetail.value = false
    posts.value = posts.value.filter(p => p.id !== adminSelectedPost.value.id)
    postTotal.value--
    toast.success('帖子已删除')
  } else toast.error('删除失败')
}

const loadPosts = async () => {
  postsLoading.value = true
  const params = new URLSearchParams({ page: String(postPage.value), size: String(postSize) })
  const r = await fetch(`/api/v1/admin/community/posts?${params}`, { headers: authHeaders() })
  if (r.ok) {
    const data = await r.json()
    posts.value = data.items
    postTotal.value = data.total
  }
  postsLoading.value = false
}

const deletePost = async (id: string) => {
  if (!confirm('确认删除该帖子？此操作不可恢复。')) return
  const r = await fetch(`/api/v1/admin/community/posts/${id}`, {
    method: 'DELETE',
    headers: authHeaders(),
  })
  if (r.ok) {
    posts.value = posts.value.filter(p => p.id !== id)
    postTotal.value--
    toast.success('帖子已删除')
  } else toast.error('删除失败')
}

// ---- 系统设置 ----
interface SettingsForm {
  storage_type: string
  cos_secret_id: string
  cos_secret_key: string
  cos_bucket_name: string
  cos_region: string
  cos_endpoint: string
}
const settingsForm = ref<SettingsForm>({
  storage_type: 'local',
  cos_secret_id: '',
  cos_secret_key: '',
  cos_bucket_name: '',
  cos_region: '',
  cos_endpoint: '',
})
const savingSettings = ref(false)
const testingStorage = ref(false)
const storageTestResult = ref<{ success: boolean; message: string } | null>(null)

const loadSettings = async () => {
  const r = await fetch('/api/v1/admin/settings', { headers: authHeaders() })
  if (r.ok) {
    const data = await r.json()
    for (const item of data.items) {
      if (item.key in settingsForm.value) {
        (settingsForm.value as any)[item.key] = item.value || ''
      }
    }
  }
}

const saveSettings = async () => {
  savingSettings.value = true
  storageTestResult.value = null
  const payload: Record<string, string> = {}
  for (const [key, val] of Object.entries(settingsForm.value)) {
    payload[key] = val
  }
  const r = await fetch('/api/v1/admin/settings', {
    method: 'PUT',
    headers: authHeaders(),
    body: JSON.stringify({ settings: payload }),
  })
  savingSettings.value = false
  if (r.ok) {
    toast.success('设置已保存')
  } else {
    const err = await r.json().catch(() => ({}))
    toast.error(err.detail || '保存失败')
  }
}

const testStorage = async () => {
  testingStorage.value = true
  storageTestResult.value = null
  // 先保存当前设置，再测试
  const payload: Record<string, string> = {}
  for (const [key, val] of Object.entries(settingsForm.value)) {
    payload[key] = val
  }
  await fetch('/api/v1/admin/settings', {
    method: 'PUT',
    headers: authHeaders(),
    body: JSON.stringify({ settings: payload }),
  })
  const r = await fetch('/api/v1/admin/settings/test-storage', {
    method: 'POST',
    headers: authHeaders(),
  })
  testingStorage.value = false
  if (r.ok) {
    const data = await r.json()
    storageTestResult.value = data
    if (data.success) toast.success(data.message)
    else toast.error(data.message)
  } else {
    storageTestResult.value = { success: false, message: '请求失败' }
    toast.error('测试请求失败')
  }
}

// ---- 工具函数 ----
const formatDate = (d: string) => new Date(d).toLocaleDateString('zh-CN')
const formatBytes = (bytes: number) => {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`
  return `${(bytes / 1024 / 1024 / 1024).toFixed(2)} GB`
}

const loadTab = () => {
  if (activeTab.value === 'overview') loadStats()
  else if (activeTab.value === 'users') loadUsers()
  else if (activeTab.value === 'files') loadFiles()
  else if (activeTab.value === 'community') loadPosts()
  else if (activeTab.value === 'settings') loadSettings()
}

onMounted(() => {
  loadStats()
  loadUsers()
})
</script>

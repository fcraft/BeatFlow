<template>
  <AppLayout>
    <div class="page-container">
      <!-- Header -->
      <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-6">
        <div>
          <h1 class="text-xl font-bold text-gray-900">社区广场</h1>
          <p class="text-sm text-gray-500 mt-0.5">公开分享心音心电数据分析，与同行交流讨论</p>
        </div>
        <button class="btn-primary self-start sm:self-auto" @click="showNewPost = true">
          <Plus class="w-4 h-4" />发布帖子
        </button>
      </div>

      <!-- Filter bar -->
      <div class="flex items-center gap-2 mb-5">
        <input v-model="searchQuery" type="text" placeholder="搜索帖子标题或内容…" class="input flex-1"
          @keydown.enter="fetchPosts(true)" />
        <button class="btn-secondary btn-sm shrink-0" @click="fetchPosts(true)">
          <Search class="w-3.5 h-3.5" /><span class="hidden sm:inline">搜索</span>
        </button>
        <button v-if="searchQuery || searchTag" class="btn-ghost btn-sm shrink-0 text-gray-400" @click="searchQuery=''; searchTag=''; fetchPosts(true)">
          <X class="w-3.5 h-3.5" />
        </button>
      </div>

      <!-- Active tag filter indicator -->
      <div v-if="searchTag" class="flex items-center gap-2 mb-4">
        <span class="text-xs text-gray-500">按标签筛选:</span>
        <span class="flex items-center gap-1 px-2 py-0.5 text-xs rounded-full bg-blue-100 text-blue-700">
          {{ searchTag }}
          <button @click="searchTag = ''; fetchPosts(true)"><X class="w-2.5 h-2.5" /></button>
        </span>
      </div>

      <!-- Post list -->
      <div v-if="loading" class="flex justify-center py-20">
        <span class="spinner w-7 h-7" />
      </div>
      <div v-else-if="posts.length === 0" class="card p-12 text-center text-gray-400">
        <MessageSquare class="w-10 h-10 mx-auto mb-3 opacity-30" />
        <p class="text-sm">暂无帖子，来发布第一篇吧！</p>
      </div>
      <div v-else class="space-y-4">
        <div v-for="post in posts" :key="post.id"
          class="card p-5 hover:shadow-md transition-shadow cursor-pointer"
          @click="openPost(post)">
          <div class="flex items-start gap-3">
            <div class="w-9 h-9 rounded-full bg-blue-100 text-blue-600 flex items-center justify-center font-semibold text-sm shrink-0">
              {{ post.author_username?.[0]?.toUpperCase() ?? '?' }}
            </div>
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-2 mb-1">
                <span class="text-sm font-semibold text-gray-900">{{ post.title }}</span>
                <span v-if="post.file_id" class="badge badge-blue flex items-center gap-1">
                  <Activity class="w-2.5 h-2.5" />附波形
                </span>
              </div>
              <p class="text-sm text-gray-600 line-clamp-2 mb-2">{{ post.content }}</p>
              <div class="flex flex-wrap gap-1.5 mb-2">
                <button v-for="tag in post.tags" :key="tag"
                  class="px-2 py-0.5 text-xs rounded-full bg-gray-100 text-gray-600 hover:bg-blue-100 hover:text-blue-700 transition-colors"
                  @click.stop="searchTag = tag; fetchPosts(true)">{{ tag }}</button>
              </div>
              <div class="flex items-center gap-4 text-xs text-gray-400">
                <span>{{ post.author_username }}</span>
                <span>{{ formatDate(post.created_at) }}</span>
                <span class="flex items-center gap-1"><Eye class="w-3 h-3" />{{ post.view_count }}</span>
                <span class="flex items-center gap-1"><Heart class="w-3 h-3" />{{ post.like_count }}</span>
                <span class="flex items-center gap-1"><MessageSquare class="w-3 h-3" />{{ post.comment_count }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Pagination -->
      <div v-if="totalPages > 1" class="flex items-center justify-center gap-2 mt-6">
        <button class="btn-ghost btn-sm" :disabled="page === 1" @click="page--; fetchPosts()">
          <ChevronLeft class="w-4 h-4" />
        </button>
        <span class="text-sm text-gray-500">{{ page }} / {{ totalPages }}</span>
        <button class="btn-ghost btn-sm" :disabled="page >= totalPages" @click="page++; fetchPosts()">
          <ChevronRight class="w-4 h-4" />
        </button>
      </div>
    </div>

    <!-- ── New Post Modal ─────────────────────────────────────── -->
    <AppModal v-model="showNewPost" title="发布帖子" width="560px">
      <div class="space-y-4">
        <div>
          <label class="label">标题 *</label>
          <input v-model="newPost.title" type="text" class="input w-full" placeholder="帖子标题" />
        </div>
        <div>
          <label class="label">内容 *</label>
          <textarea v-model="newPost.content" class="input w-full" rows="5"
            placeholder="描述你的发现、问题或分析结果…" />
        </div>
        <div>
          <label class="label">关联文件（可选）</label>
          <select v-model="newPost.file_id" class="input w-full">
            <option value="">不关联文件</option>
            <option v-for="f in myFiles" :key="f.id" :value="f.id">
              {{ f.original_filename || f.filename }}（{{ FILE_TYPE_LABELS[f.file_type] ?? f.file_type }}）
            </option>
          </select>
        </div>
        <div>
          <label class="label">标签（回车添加）</label>
          <div class="flex flex-wrap gap-1.5 mb-2">
            <span v-for="(tag, i) in newPost.tags" :key="tag"
              class="flex items-center gap-1 px-2 py-0.5 text-xs rounded-full bg-blue-100 text-blue-700">
              {{ tag }}
              <button @click="newPost.tags.splice(i, 1)"><X class="w-2.5 h-2.5" /></button>
            </span>
          </div>
          <input type="text" class="input w-full" placeholder="输入标签后回车" v-model="tagInput"
            @keydown.enter.prevent="addTag" />
        </div>
        <div class="flex justify-end gap-2 pt-2">
          <button class="btn-ghost" @click="showNewPost = false">取消</button>
          <button class="btn-primary" :disabled="submitting || !newPost.title.trim() || !newPost.content.trim()"
            @click="submitPost">
            <span v-if="submitting" class="spinner w-3.5 h-3.5" />
            发布
          </button>
        </div>
      </div>
    </AppModal>

    <!-- ── Post Detail Modal ───────────────────────────────────── -->
    <AppModal v-model="showDetail" :title="selectedPost?.title ?? ''" width="680px">
      <div v-if="selectedPost" class="space-y-5">
        <!-- Meta -->
        <div class="flex items-center gap-3 text-sm text-gray-500">
          <div class="w-8 h-8 rounded-full bg-blue-100 text-blue-600 flex items-center justify-center font-semibold text-xs">
            {{ selectedPost.author_username?.[0]?.toUpperCase() ?? '?' }}
          </div>
          <span class="font-medium text-gray-700">{{ selectedPost.author_username }}</span>
          <span>{{ formatDate(selectedPost.created_at) }}</span>
          <span class="ml-auto flex items-center gap-3">
            <span class="flex items-center gap-1"><Eye class="w-3.5 h-3.5" />{{ selectedPost.view_count }}</span>
            <button class="flex items-center gap-1 hover:text-red-500 transition-colors" @click="likePost">
              <Heart class="w-3.5 h-3.5" :class="liked ? 'fill-red-500 text-red-500' : ''" />{{ selectedPost.like_count }}
            </button>
          </span>
        </div>

        <!-- Content -->
        <p class="text-sm text-gray-800 leading-relaxed whitespace-pre-wrap">{{ selectedPost.content }}</p>

        <!-- Tags -->
        <div v-if="selectedPost.tags?.length" class="flex flex-wrap gap-1.5">
          <span v-for="tag in selectedPost.tags" :key="tag"
            class="px-2 py-0.5 text-xs rounded-full bg-gray-100 text-gray-600">{{ tag }}</span>
        </div>

        <!-- Linked file -->
        <div v-if="selectedPost.file_id" class="flex items-center gap-2 p-3 bg-blue-50 rounded-lg text-sm">
          <Activity class="w-4 h-4 text-blue-500 shrink-0" />
          <span class="text-blue-800 font-medium truncate">{{ selectedPost.file_name || '关联文件' }}</span>
          <RouterLink :to="`/files/${selectedPost.file_id}`" class="ml-auto text-blue-600 hover:text-blue-800 shrink-0 text-xs">
            查看分析 →
          </RouterLink>
        </div>

        <!-- Delete button (only author) -->
        <div v-if="selectedPost.author_id === currentUserId" class="flex justify-end">
          <button class="btn-ghost btn-sm text-red-400 hover:text-red-600" @click="deletePost">
            <Trash2 class="w-3.5 h-3.5" />删除帖子
          </button>
        </div>

        <!-- Comments -->
        <div class="border-t pt-4">
          <h3 class="text-sm font-semibold text-gray-700 mb-3">评论 ({{ comments.length }})</h3>
          <div v-if="commentsLoading" class="flex justify-center py-4"><span class="spinner w-5 h-5" /></div>
          <div v-else class="space-y-3 mb-4 max-h-64 overflow-y-auto">
            <div v-for="c in comments" :key="c.id" class="flex gap-2.5">
              <div class="w-7 h-7 rounded-full bg-gray-100 text-gray-600 flex items-center justify-center text-xs font-semibold shrink-0">
                {{ c.author_username?.[0]?.toUpperCase() ?? '?' }}
              </div>
              <div class="flex-1">
                <div class="flex items-center gap-2 mb-0.5">
                  <span class="text-xs font-medium text-gray-700">{{ c.author_username }}</span>
                  <span class="text-xs text-gray-400">{{ formatDate(c.created_at) }}</span>
                  <button v-if="canDeleteComment(c)"
                    class="ml-auto text-xs text-gray-400 hover:text-red-500"
                    @click="deleteComment(c.id)">删除</button>
                </div>
                <p class="text-sm text-gray-700">{{ c.content }}</p>
              </div>
            </div>
            <div v-if="comments.length === 0" class="text-xs text-gray-400 text-center py-2">暂无评论</div>
          </div>
          <!-- New comment -->
          <div class="flex gap-2">
            <input v-model="newComment" type="text" class="input flex-1" placeholder="发表评论…"
              @keydown.enter="submitComment" />
            <button class="btn-primary btn-sm" :disabled="!newComment.trim() || commentSubmitting"
              @click="submitComment">
              <Send class="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </div>
    </AppModal>
  </AppLayout>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { Plus, Search, X, MessageSquare, Heart, Eye, Activity, ChevronLeft, ChevronRight, Trash2, Send } from 'lucide-vue-next'
import AppLayout from '@/components/layout/AppLayout.vue'
import AppModal from '@/components/ui/AppModal.vue'
import { useAuthStore } from '@/store/auth'
import { useToastStore } from '@/store/toast'

const auth = useAuthStore()
const toast = useToastStore()

const authHeader = computed((): Record<string, string> => auth.token ? { Authorization: `Bearer ${auth.token}` } : {})
const currentUserId = computed(() => auth.user?.id ?? '')
const isAdmin = computed(() => !!(auth.user?.is_superuser || auth.user?.role === 'admin'))

const canDeleteComment = (comment: any) =>
  comment.author_id === currentUserId.value ||
  selectedPost.value?.author_id === currentUserId.value ||
  isAdmin.value

const FILE_TYPE_LABELS: Record<string, string> = {
  audio: 'Audio', video: 'Video', ecg: 'ECG', pcg: 'PCG', other: '其他',
}

// ── List state ────────────────────────────────────────────────────
const posts = ref<any[]>([])
const loading = ref(false)
const page = ref(1)
const pageSize = 15
const total = ref(0)
const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize)))
const searchTag = ref('')
const searchQuery = ref('')

const fetchPosts = async (reset = false) => {
  if (reset) page.value = 1
  loading.value = true
  const skip = (page.value - 1) * pageSize
  const params = new URLSearchParams({ skip: String(skip), limit: String(pageSize) })
  if (searchTag.value) params.set('tag', searchTag.value)
  if (searchQuery.value) params.set('q', searchQuery.value)
  const r = await fetch(`/api/v1/community/posts?${params}`, { headers: authHeader.value })
  loading.value = false
  if (r.ok) {
    const d = await r.json()
    posts.value = d.items
    total.value = d.total
  }
}

const formatDate = (iso: string) => {
  if (!iso) return ''
  const d = new Date(iso)
  const now = new Date()
  const diff = (now.getTime() - d.getTime()) / 1000
  if (diff < 60) return '刚刚'
  if (diff < 3600) return `${Math.floor(diff / 60)} 分钟前`
  if (diff < 86400) return `${Math.floor(diff / 3600)} 小时前`
  return d.toLocaleDateString('zh-CN')
}

// ── My files (for linking) ─────────────────────────────────────────
const myFiles = ref<any[]>([])
const loadMyFiles = async () => {
  const r = await fetch('/api/v1/files/', { headers: authHeader.value })
  if (r.ok) {
    const d = await r.json()
    myFiles.value = d.items || []
  }
}

// ── New post ──────────────────────────────────────────────────────
const showNewPost = ref(false)
const newPost = ref({ title: '', content: '', file_id: '', tags: [] as string[] })
const tagInput = ref('')
const submitting = ref(false)

const addTag = () => {
  const t = tagInput.value.trim()
  if (t && !newPost.value.tags.includes(t)) newPost.value.tags.push(t)
  tagInput.value = ''
}

const submitPost = async () => {
  submitting.value = true
  const body: any = { title: newPost.value.title, content: newPost.value.content, tags: newPost.value.tags }
  if (newPost.value.file_id) body.file_id = newPost.value.file_id
  const r = await fetch('/api/v1/community/posts', {
    method: 'POST',
    headers: { ...authHeader.value, 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  submitting.value = false
  if (r.ok) {
    toast.success('帖子已发布')
    showNewPost.value = false
    newPost.value = { title: '', content: '', file_id: '', tags: [] }
    fetchPosts(true)
  } else {
    const e = await r.json().catch(() => ({}))
    toast.error(e.detail ?? '发布失败')
  }
}

// ── Post detail ───────────────────────────────────────────────────
const selectedPost = ref<any>(null)
const showDetail = ref(false)
const liked = ref(false)
const comments = ref<any[]>([])
const commentsLoading = ref(false)
const newComment = ref('')
const commentSubmitting = ref(false)

const openPost = async (post: any) => {
  selectedPost.value = post
  showDetail.value = true
  liked.value = false
  await loadComments(post.id)
  // Fetch fresh post detail (increments view count)
  const r = await fetch(`/api/v1/community/posts/${post.id}`, { headers: authHeader.value })
  if (r.ok) {
    const d = await r.json()
    selectedPost.value = d
    // Also update in list
    const idx = posts.value.findIndex(p => p.id === post.id)
    if (idx !== -1) posts.value[idx] = { ...posts.value[idx], view_count: d.view_count }
  }
}

const loadComments = async (postId: string) => {
  commentsLoading.value = true
  const r = await fetch(`/api/v1/community/posts/${postId}/comments`, { headers: authHeader.value })
  commentsLoading.value = false
  if (r.ok) comments.value = (await r.json()).items
}

const likePost = async () => {
  if (!selectedPost.value || liked.value) return
  const r = await fetch(`/api/v1/community/posts/${selectedPost.value.id}/like`, {
    method: 'POST', headers: authHeader.value,
  })
  if (r.ok) {
    const d = await r.json()
    selectedPost.value.like_count = d.like_count
    liked.value = true
  }
}

const deletePost = async () => {
  if (!selectedPost.value) return
  if (!confirm('确定要删除这篇帖子吗？')) return
  const r = await fetch(`/api/v1/community/posts/${selectedPost.value.id}`, {
    method: 'DELETE', headers: authHeader.value,
  })
  if (r.ok) {
    toast.success('帖子已删除')
    showDetail.value = false
    selectedPost.value = null
    fetchPosts(true)
  }
}

const submitComment = async () => {
  if (!newComment.value.trim() || !selectedPost.value) return
  commentSubmitting.value = true
  const r = await fetch(`/api/v1/community/posts/${selectedPost.value.id}/comments`, {
    method: 'POST',
    headers: { ...authHeader.value, 'Content-Type': 'application/json' },
    body: JSON.stringify({ content: newComment.value }),
  })
  commentSubmitting.value = false
  if (r.ok) {
    comments.value.push(await r.json())
    newComment.value = ''
    selectedPost.value.comment_count = (selectedPost.value.comment_count ?? 0) + 1
  } else {
    toast.error('评论失败')
  }
}

const deleteComment = async (commentId: string) => {
  if (!selectedPost.value) return
  const r = await fetch(`/api/v1/community/posts/${selectedPost.value.id}/comments/${commentId}`, {
    method: 'DELETE', headers: authHeader.value,
  })
  if (r.ok) {
    comments.value = comments.value.filter(c => c.id !== commentId)
    selectedPost.value.comment_count = Math.max(0, (selectedPost.value.comment_count ?? 1) - 1)
  }
}

onMounted(() => {
  fetchPosts()
  loadMyFiles()
})
</script>

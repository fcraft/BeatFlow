<template>
  <AppLayout>
    <div class="page-container">
      <button class="btn-ghost btn-sm mb-5 -ml-1" @click="$router.back()">
        <ChevronLeft class="w-4 h-4" />返回
      </button>

      <div v-if="loading" class="flex items-center justify-center py-32">
        <span class="spinner w-8 h-8" />
      </div>

      <template v-else-if="file">
        <!-- File header -->
        <div class="card p-5 mb-5 flex items-start gap-4">
          <div class="w-12 h-12 rounded-xl flex items-center justify-center shrink-0" :class="fileIconBg(file.file_type)">
            <component :is="fileIcon(file.file_type)" class="w-6 h-6" :class="fileIconColor(file.file_type)" />
          </div>
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-3 mb-1">
              <h1 class="text-lg font-bold text-gray-900 truncate">{{ file.original_filename || file.filename }}</h1>
              <button class="flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium border border-dashed transition-colors hover:opacity-80"
                :class="fileTypeBadge(file.file_type)" @click="showTypeModal = true" title="点击修改文件类型">
                <Pencil class="w-2.5 h-2.5" />
                {{ FILE_TYPE_LABELS[file.file_type] ?? file.file_type.toUpperCase() }}
              </button>
            </div>
            <div class="flex flex-wrap gap-4 text-xs text-gray-500">
              <span class="flex items-center gap-1"><HardDrive class="w-3 h-3" />{{ formatSize(file.file_size) }}</span>
              <span v-if="file.duration" class="flex items-center gap-1"><Clock class="w-3 h-3" />{{ formatDuration(file.duration) }}</span>
              <span v-if="file.sample_rate" class="flex items-center gap-1"><Cpu class="w-3 h-3" />{{ file.sample_rate }} Hz</span>
              <span v-if="file.channels" class="flex items-center gap-1"><Layers class="w-3 h-3" />{{ file.channels }} 声道</span>
              <span class="flex items-center gap-1"><Calendar class="w-3 h-3" />{{ formatDate(file.created_at) }}</span>
            </div>
          </div>
          <button class="btn-secondary btn-sm shrink-0" @click="download">
            <Download class="w-3.5 h-3.5" />下载
          </button>
          <button class="btn-ghost btn-sm shrink-0" @click="showShareModal = true" title="分享到社区">
            <Share2 class="w-3.5 h-3.5" />分享
          </button>
        </div>

        <!-- Waveform card -->
        <div class="card p-5 mb-5">
          <div class="flex items-center justify-between mb-3">
            <div>
              <h3 class="text-sm font-semibold text-gray-900">波形预览</h3>
              <p class="text-xs text-gray-400 mt-0.5">
                滚轮缩放 · 拖动平移
                <span v-if="!showAnnotationsOnWave && annotations.length > 0" class="ml-2 text-blue-400">
                  缩放至 {{ Math.round(ANNOTATION_ZOOM_THRESHOLD * 100) }}% 以内显示标记
                </span>
                <span v-else-if="showAnnotationsOnWave" class="ml-2 text-green-500 font-medium">标记已叠加显示</span>
              </p>
            </div>
            <div class="flex items-center gap-2">
              <span v-if="loadingWaveform" class="text-xs text-gray-400 flex items-center gap-1">
                <span class="spinner w-3.5 h-3.5" />加载中
              </span>
              <template v-if="!loadingWaveform && waveform.length > 0">
                <span class="text-xs text-gray-400 tabular-nums font-mono">{{ zoomLabel }}</span>
                <div class="flex items-center gap-1">
                  <button class="btn-icon btn-sm rounded" title="缩小" @click="zoom(0.5)"><ZoomOut class="w-3.5 h-3.5" /></button>
                  <button class="btn-icon btn-sm rounded" title="放大" @click="zoom(-0.5)"><ZoomIn class="w-3.5 h-3.5" /></button>
                  <button class="btn-icon btn-sm rounded" title="重置" @click="resetView"><Maximize2 class="w-3.5 h-3.5" /></button>
                </div>
              </template>
              <!-- Expand to big modal -->
              <button class="btn-icon btn-sm rounded" title="展开大面板" @click="openBigModal">
                <Expand class="w-3.5 h-3.5" />
              </button>
            </div>
          </div>

          <!-- Canvas -->
          <div ref="waveContainer"
            class="relative bg-gray-50 rounded-lg overflow-hidden select-none"
            style="height:180px"
            :style="{ cursor: waveDragging ? 'grabbing' : 'grab' }"
            @wheel.prevent="onWheel"
            @mousedown="onWaveMouseDown"
            @mousemove="onWaveMouseMove"
            @mouseleave="onWaveMouseLeave">
            <canvas ref="canvas" class="absolute inset-0 w-full h-full" />
            <div v-if="isPlaying || playPos > 0" class="absolute top-0 bottom-0 w-px bg-orange-400 pointer-events-none"
              :style="{ left: playheadX + 'px' }" />
            <div v-if="hoveredAnnotation"
              class="absolute pointer-events-none z-10 bg-gray-900 text-white text-xs rounded px-2 py-1 whitespace-nowrap shadow-lg"
              :style="{ left: Math.min(tooltipX, waveContainerW - 150) + 'px', top: '8px' }">
              <span class="font-bold">{{ hoveredAnnotation.annotation_type.toUpperCase() }}</span>
              <span v-if="hoveredAnnotation.label" class="opacity-70 ml-1">{{ hoveredAnnotation.label }}</span>
              <span class="opacity-50 ml-2">{{ hoveredAnnotation.start_time.toFixed(3) }}s – {{ (hoveredAnnotation.end_time ?? hoveredAnnotation.start_time).toFixed(3) }}s</span>
              <span v-if="hoveredAnnotation.confidence != null" class="opacity-50 ml-2">{{ (hoveredAnnotation.confidence * 100).toFixed(0) }}%</span>
            </div>
            <div v-if="!loadingWaveform && waveform.length === 0"
              class="absolute inset-0 flex items-center justify-center text-sm text-gray-400 gap-2">
              <BarChart2 class="w-4 h-4" />暂无波形数据
            </div>
          </div>

          <!-- Scrollbar -->
          <div v-if="!loadingWaveform && waveform.length > 0" class="mt-2 flex items-center gap-2">
            <span class="text-xs text-gray-400 tabular-nums font-mono w-14 shrink-0">{{ viewStartLabel }}</span>
            <div ref="scrollbarTrack"
              class="flex-1 relative h-4 select-none"
              @mousedown.prevent="onScrollbarTrackDown"
              @wheel.stop.prevent>
              <div class="absolute inset-y-1 inset-x-0 bg-gray-100 rounded-full cursor-pointer" />
              <!-- Thumb: draggable pan handle -->
              <div class="absolute inset-y-0.5 rounded-full transition-colors cursor-grab active:cursor-grabbing"
                :class="sbDragging ? 'bg-blue-500' : 'bg-blue-300 hover:bg-blue-400'"
                :style="{ left: scrollbarLeft + '%', width: Math.max(3, scrollbarWidth) + '%' }"
                @mousedown.stop.prevent="onScrollbarThumbDown" />
            </div>
            <span class="text-xs text-gray-400 tabular-nums font-mono w-14 shrink-0 text-right">{{ viewEndLabel }}</span>
          </div>
        </div>

        <!-- Audio player -->
        <div v-if="isAudioFile" class="card p-5 mb-5">
          <div class="flex items-center gap-4">
            <button class="w-10 h-10 rounded-full bg-blue-500 hover:bg-blue-600 flex items-center justify-center text-white transition-colors shrink-0"
              @click="togglePlay">
              <Pause v-if="isPlaying" class="w-5 h-5" />
              <Play v-else class="w-5 h-5 ml-0.5" />
            </button>
            <div class="flex-1 min-w-0">
              <div class="flex items-center justify-between text-xs text-gray-500 mb-1">
                <span class="font-mono">{{ fmtTime(playPos) }}</span>
                <span class="font-mono">{{ fmtTime(totalDuration) }}</span>
              </div>
              <div class="relative h-2 bg-gray-100 rounded-full cursor-pointer" @click="seekTo">
                <div class="absolute inset-y-0 left-0 bg-blue-400 rounded-full"
                  :style="{ width: totalDuration > 0 ? (playPos / totalDuration * 100) + '%' : '0%' }" />
              </div>
            </div>
            <div class="flex items-center gap-2 shrink-0">
              <Volume2 class="w-4 h-4 text-gray-400" />
              <input type="range" min="0" max="1" step="0.05" :value="volume"
                class="w-20 accent-blue-500" @input="setVolume" />
            </div>
          </div>
          <audio ref="audioEl" @timeupdate="onTimeUpdate" @ended="onEnded" @loadedmetadata="onAudioMeta" />
        </div>

        <!-- Auto-detect panel -->
        <div class="card p-5 mb-5">
          <div class="flex items-center justify-between mb-4">
            <div>
              <h3 class="text-sm font-semibold text-gray-900">自动检测</h3>
              <p class="text-xs text-gray-400 mt-0.5">
                <template v-if="detectConfig">
                  支持检测：
                  <span v-for="t in detectConfig.types" :key="t" class="inline-block mr-1 px-1.5 py-0.5 rounded text-xs font-mono" :class="annotationBadge(t)">{{ t.toUpperCase() }}</span>
                </template>
                <template v-else>当前文件类型不支持自动检测，请先修改类型为 PCG / Audio / ECG</template>
              </p>
            </div>
            <!-- Expand/collapse settings -->
            <button class="btn-ghost btn-sm text-gray-500 flex items-center gap-1" @click="showDetectPanel = !showDetectPanel">
              <Settings class="w-3.5 h-3.5" />
              {{ showDetectPanel ? '收起设置' : '展开设置' }}
            </button>
          </div>
          <template v-if="detectConfig">
            <DetectionPanel
              v-if="showDetectPanel"
              :file-id="fileId"
              :file-type="file.file_type"
              :auth-header="authHeader"
              @detected="onDetected"
              @clear="clearAutoAnnotations"
              @error="(msg) => toast.error(msg)"
            />
            <!-- Quick detect button when panel is collapsed -->
            <div v-else class="flex items-center gap-2">
              <button class="btn-primary btn-sm" :disabled="detecting" @click="runDetect">
                <span v-if="detecting" class="spinner w-3.5 h-3.5" />
                <Zap v-else class="w-3.5 h-3.5" />
                {{ detecting ? '检测中…' : '快速检测 (NeuroKit2)' }}
              </button>
              <span v-if="lastDetectResult" class="text-xs text-green-600 flex items-center gap-1">
                <CheckCircle2 class="w-3.5 h-3.5" />
                共 {{ lastDetectResult.detected_count }} 个标记
              </span>
            </div>
          </template>
        </div>

        <!-- BPM Analysis -->
        <div v-if="bpmAnnotations.length >= 2" class="card p-5 mb-5">
          <div class="flex items-center justify-between mb-4">
            <div>
              <h3 class="text-sm font-semibold text-gray-900">心率（BPM）分析</h3>
              <p class="text-xs text-gray-400 mt-0.5">基于标记点计算瞬时心率曲线</p>
            </div>
            <button class="btn-ghost btn-sm text-gray-500" @click="showBpmPanel = !showBpmPanel">
              <TrendingUp class="w-3.5 h-3.5" />
              {{ showBpmPanel ? '收起' : '展开' }}
            </button>
          </div>
          <BpmPanel
            v-if="showBpmPanel"
            :annotations="annotations"
            :duration="totalDuration"
            :chart-height="200"
          />
          <div v-else class="flex items-center gap-4 text-sm">
            <span class="text-gray-500">共 <b class="text-gray-800">{{ bpmAnnotations.length }}</b> 个 Beat 标记</span>
            <button class="btn-primary btn-sm" @click="showBpmPanel = true">
              <TrendingUp class="w-3.5 h-3.5" />查看 BPM 曲线
            </button>
          </div>
        </div>

        <!-- Annotations -->
        <div class="card p-5">
          <div class="flex items-center justify-between mb-4">
            <h3 class="text-sm font-semibold text-gray-900">
              标记列表<span class="ml-2 badge-gray">{{ annotations.length }}</span>
            </h3>
            <div class="flex items-center gap-2">
              <button class="btn-secondary btn-sm" @click="openBigModal">
                <Expand class="w-3.5 h-3.5" />展开编辑
              </button>
              <button class="btn-primary btn-sm" @click="openAddModal(null)">
                <Plus class="w-3.5 h-3.5" />添加标记
              </button>
            </div>
          </div>

          <div v-if="loadingAnnotations" class="py-8 flex justify-center"><span class="spinner" /></div>

          <template v-else-if="annotations.length > 0">
            <div class="overflow-x-auto">
              <table class="w-full text-sm">
                <thead>
                  <tr class="text-xs text-gray-500 border-b border-gray-100">
                    <th class="text-left py-2 pr-4 font-medium">类型</th>
                    <th class="text-left py-2 pr-4 font-medium">标签</th>
                    <th class="text-left py-2 pr-4 font-medium">开始 (s)</th>
                    <th class="text-left py-2 pr-4 font-medium">结束 (s)</th>
                    <th class="text-left py-2 pr-4 font-medium">置信度</th>
                    <th class="text-left py-2 pr-4 font-medium">来源</th>
                    <th class="py-2" />
                  </tr>
                </thead>
                <tbody class="divide-y divide-gray-50">
                  <tr v-for="a in pagedAnnotations" :key="a.id" class="hover:bg-gray-50 group cursor-pointer"
                    @click="jumpToAnnotation(a)">
                    <td class="py-2.5 pr-4"><span :class="annotationBadge(a.annotation_type)">{{ a.annotation_type }}</span></td>
                    <td class="py-2.5 pr-4 text-gray-700">{{ a.label || '—' }}</td>
                    <td class="py-2.5 pr-4 font-mono text-gray-600">{{ a.start_time.toFixed(3) }}</td>
                    <td class="py-2.5 pr-4 font-mono text-gray-600">{{ a.end_time?.toFixed(3) ?? '—' }}</td>
                    <td class="py-2.5 pr-4 text-gray-600">{{ a.confidence != null ? (a.confidence * 100).toFixed(1) + '%' : '—' }}</td>
                    <td class="py-2.5 pr-4">
                      <span v-if="a.source === 'auto'" class="badge-amber text-xs">自动</span>
                      <span v-else class="badge-gray text-xs">手动</span>
                    </td>
                    <td class="py-2.5">
                      <div class="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                        <button class="btn-icon btn-sm rounded hover:text-blue-500 hover:bg-blue-50"
                          @click.stop="openEditModal(a)"><Pencil class="w-3 h-3" /></button>
                        <button class="btn-icon btn-sm rounded hover:text-red-500 hover:bg-red-50"
                          @click.stop="delAnnotation(a.id)"><Trash2 class="w-3.5 h-3.5" /></button>
                      </div>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div v-if="totalAnnPages > 1" class="mt-4 flex items-center justify-between text-xs text-gray-500">
              <span>共 {{ annotations.length }} 条，第 {{ annPage }}/{{ totalAnnPages }} 页</span>
              <div class="flex items-center gap-1">
                <button class="btn-icon btn-sm rounded" :disabled="annPage <= 1" @click="annPage--"><ChevronLeft class="w-3.5 h-3.5" /></button>
                <template v-for="p in paginationPages" :key="p">
                  <span v-if="p === '...'" class="px-1 text-gray-300">…</span>
                  <button v-else class="w-7 h-7 rounded text-xs transition-colors"
                    :class="p === annPage ? 'bg-blue-500 text-white' : 'hover:bg-gray-100'"
                    @click="annPage = p as number">{{ p }}</button>
                </template>
                <button class="btn-icon btn-sm rounded" :disabled="annPage >= totalAnnPages" @click="annPage++"><ChevronRight class="w-3.5 h-3.5" /></button>
              </div>
            </div>
          </template>

          <div v-else class="py-12 flex flex-col items-center text-gray-400 gap-2">
            <Tag class="w-8 h-8" /><p class="text-sm">暂无标记</p>
          </div>
        </div>
      </template>

      <!-- Add/Edit annotation modal (small) -->
      <AppModal v-model="showEditModal" :title="editingAnnotation ? '编辑标记' : '添加标记'" width="420px">
        <div class="space-y-4">
          <div>
            <label class="label">标记类型</label>
            <select v-model="editForm.annotation_type" class="select" :disabled="!!editingAnnotation">
              <option v-for="t in annotationTypes" :key="t.value" :value="t.value">{{ t.label }}</option>
            </select>
          </div>
          <div><label class="label">标签</label><input v-model="editForm.label" type="text" placeholder="输入标签" class="input" /></div>
          <div class="grid grid-cols-2 gap-4">
            <div><label class="label">开始时间 (s)</label><input v-model.number="editForm.start_time" type="number" min="0" step="0.001" class="input" /></div>
            <div><label class="label">结束时间 (s)</label><input v-model.number="editForm.end_time" type="number" min="0" step="0.001" class="input" /></div>
          </div>
          <div><label class="label">置信度 (0–1)</label><input v-model.number="editForm.confidence" type="number" min="0" max="1" step="0.01" placeholder="可选" class="input" /></div>
        </div>
        <template #footer>
          <button class="btn-secondary btn-sm" @click="showEditModal = false">取消</button>
          <button class="btn-primary btn-sm" :disabled="saving" @click="saveAnnotation">
            <span v-if="saving" class="spinner w-3.5 h-3.5" />{{ editingAnnotation ? '保存' : '添加' }}
          </button>
        </template>
      </AppModal>

      <!-- File type modal -->
      <AppModal v-model="showTypeModal" title="修改文件类型" width="360px">
        <p class="text-xs text-gray-500 mb-4">选择该文件的信号类型，类型决定了自动检测所使用的算法。</p>
        <div class="grid grid-cols-1 gap-2">
          <button v-for="ft in FILE_TYPES" :key="ft.value"
            class="flex items-center gap-3 px-4 py-3 rounded-lg border text-left transition-colors"
            :class="file?.file_type === ft.value ? 'border-blue-500 bg-blue-50' : 'border-gray-200 hover:border-blue-300 hover:bg-gray-50'"
            @click="changeFileType(ft.value)">
            <component :is="ft.icon" class="w-4 h-4 shrink-0" :class="file?.file_type === ft.value ? 'text-blue-500' : 'text-gray-400'" />
            <div><div class="text-sm font-medium text-gray-800">{{ ft.label }}</div><div class="text-xs text-gray-400">{{ ft.desc }}</div></div>
            <span v-if="file?.file_type === ft.value" class="ml-auto text-blue-500"><CheckCircle2 class="w-4 h-4" /></span>
          </button>
        </div>
        <template #footer>
          <button class="btn-secondary btn-sm" @click="showTypeModal = false">关闭</button>
        </template>
      </AppModal>

      <!-- Share to community modal -->
      <AppModal v-model="showShareModal" title="分享到社区" width="520px">
        <div class="space-y-4">
          <div>
            <label class="label">帖子标题 *</label>
            <input v-model="shareForm.title" type="text" class="input w-full"
              :placeholder="`分享 ${file?.original_filename || file?.filename || '文件'}`" />
          </div>
          <div>
            <label class="label">分享描述 *</label>
            <textarea v-model="shareForm.content" class="input w-full" rows="4"
              placeholder="描述你的发现、分析结果或问题…" />
          </div>
          <div>
            <label class="label">标签（回车添加）</label>
            <div class="flex flex-wrap gap-1.5 mb-2">
              <span v-for="(tag, i) in shareForm.tags" :key="tag"
                class="flex items-center gap-1 px-2 py-0.5 text-xs rounded-full bg-blue-100 text-blue-700">
                {{ tag }}
                <button @click="shareForm.tags.splice(i, 1)"><X class="w-2.5 h-2.5" /></button>
              </span>
            </div>
            <input type="text" class="input w-full" placeholder="输入标签后回车" v-model="shareTagInput"
              @keydown.enter.prevent="addShareTag" />
          </div>
          <div class="flex justify-end gap-2 pt-2">
            <button class="btn-ghost" @click="showShareModal = false">取消</button>
            <button class="btn-primary" :disabled="shareSubmitting || !shareForm.title.trim() || !shareForm.content.trim()"
              @click="submitShare">
              <span v-if="shareSubmitting" class="spinner w-3.5 h-3.5" />
              发布到社区
            </button>
          </div>
        </div>
      </AppModal>

      <!-- ═══════════════ BIG MODAL ═══════════════ -->
      <Teleport to="body">
        <Transition name="modal">
          <div v-if="showBigModal"
            class="fixed inset-0 z-50 flex flex-col bg-gray-950 text-white"
            @keydown.esc="showBigModal = false">

            <!-- Big modal header -->
            <div class="flex items-center justify-between px-6 py-3 border-b border-gray-800 shrink-0">
              <div class="flex items-center gap-3">
                <component :is="fileIcon(file?.file_type)" class="w-5 h-5 text-blue-400" />
                <span class="text-sm font-semibold truncate max-w-xs">{{ file?.original_filename || file?.filename }}</span>
                <span class="text-xs text-gray-500">{{ annotations.length }} 个标记</span>
              </div>
              <div class="flex items-center gap-2">
                <button class="btn-primary btn-sm" @click="openAddModal('big')">
                  <Plus class="w-3.5 h-3.5" />添加标记
                </button>
                <button class="btn-icon btn-sm rounded text-gray-300 hover:text-white" @click="showBigModal = false">
                  <X class="w-5 h-5" />
                </button>
              </div>
            </div>

            <!-- Lane config controls -->
            <div class="px-4 py-2 flex items-center gap-4 border-b border-gray-800 shrink-0 text-xs">
              <span class="text-gray-400">每行时长</span>
              <select v-model.number="laneSeconds" class="bg-gray-800 border border-gray-700 text-gray-200 rounded px-2 py-1 text-xs focus:outline-none">
                <option :value="1">1 秒</option>
                <option :value="2">2 秒</option>
                <option :value="5">5 秒</option>
                <option :value="10">10 秒</option>
                <option :value="30">30 秒</option>
              </select>
              <span class="text-gray-400">每页行数</span>
              <select v-model.number="lanesPerPage" class="bg-gray-800 border border-gray-700 text-gray-200 rounded px-2 py-1 text-xs focus:outline-none">
                <option :value="2">2 行</option>
                <option :value="3">3 行</option>
                <option :value="4">4 行</option>
                <option :value="6">6 行</option>
                <option :value="8">8 行</option>
              </select>
              <!-- Quick add label -->
              <span class="text-gray-400 ml-2">双击快速添加</span>
              <select v-model="quickAddType" class="bg-gray-800 border border-gray-700 text-gray-200 rounded px-2 py-1 text-xs focus:outline-none">
                <option v-for="t in annotationTypes" :key="t.value" :value="t.value">{{ t.label }}</option>
              </select>
              <div class="ml-auto flex items-center gap-2">
                <button class="btn-icon btn-sm rounded text-gray-300 disabled:opacity-30" :disabled="bigPage === 0" @click="bigPage--">
                  <ChevronLeft class="w-4 h-4" />
                </button>
                <span class="text-gray-400 tabular-nums font-mono w-20 text-center">
                  {{ bigPage + 1 }} / {{ totalBigPages }}
                </span>
                <button class="btn-icon btn-sm rounded text-gray-300 disabled:opacity-30" :disabled="bigPage >= totalBigPages - 1" @click="bigPage++">
                  <ChevronRight class="w-4 h-4" />
                </button>
              </div>
            </div>
            <!-- Lane canvases -->
            <div class="flex flex-col bg-gray-950 overflow-y-auto px-2 py-1 shrink-0" style="max-height:calc(100vh - 280px); min-height:200px">
              <div v-for="(laneIdx, i) in currentPageLanes" :key="laneIdx"
                class="flex items-stretch mb-1">
                <!-- Time label column -->
                <div class="w-12 shrink-0 flex flex-col justify-between py-1 text-right pr-2">
                  <span class="text-xs font-mono text-gray-500 leading-none">{{ fmtTime(laneIdx * laneSeconds) }}</span>
                </div>
                <!-- Canvas lane -->
                <div class="flex-1 relative rounded overflow-hidden"
                  style="height:80px"
                  :style="{ cursor: laneCursor(laneIdx) }"
                  @mousemove="onLaneMouseMove(laneIdx, $event)"
                  @mouseleave="onLaneMouseLeave"
                  @mousedown="onLaneMouseDown(laneIdx, $event)"
                  @click="onLaneClick(laneIdx, $event)"
                  @dblclick="onLaneDblClick(laneIdx, $event)">
                  <canvas :ref="(el: any) => setLaneCanvas(el, i)" class="absolute inset-0 w-full h-full" />
                  <!-- Playhead -->
                  <div v-if="getLanePlayheadPct(laneIdx) >= 0"
                    class="absolute top-0 bottom-0 w-px bg-orange-400 pointer-events-none"
                    :style="{ left: getLanePlayheadPct(laneIdx) + '%' }" />
                  <!-- Hover tooltip (only on hovered lane) -->
                  <div v-if="bigHoveredLane === laneIdx && bigHoveredAnnotation"
                    class="absolute pointer-events-none z-10 bg-white text-gray-900 text-xs rounded px-2 py-1 whitespace-nowrap shadow-lg"
                    :style="{ left: Math.min(bigTooltipX, 300) + 'px', top: '4px' }">
                    <span class="font-bold">{{ bigHoveredAnnotation.annotation_type.toUpperCase() }}</span>
                    <span v-if="bigHoveredAnnotation.label" class="opacity-70 ml-1">{{ bigHoveredAnnotation.label }}</span>
                    <span class="opacity-50 ml-2">{{ bigHoveredAnnotation.start_time.toFixed(3) }}s</span>
                  </div>
                  <!-- Picking indicator -->
                  <div v-if="bigPickingField"
                    class="absolute inset-0 border-2 border-dashed border-blue-500/50 pointer-events-none rounded" />
                </div>
              </div>
              <div v-if="currentPageLanes.length === 0" class="py-8 text-center text-xs text-gray-500">
                暂无波形数据
              </div>
            </div>

            <!-- Big audio player -->
            <div v-if="isAudioFile" class="px-4 pb-3 shrink-0">
              <div class="flex items-center gap-4 bg-gray-900 rounded-lg px-4 py-2.5">
                <button class="w-8 h-8 rounded-full bg-blue-500 hover:bg-blue-600 flex items-center justify-center text-white transition-colors shrink-0"
                  @click="togglePlay">
                  <Pause v-if="isPlaying" class="w-4 h-4" />
                  <Play v-else class="w-4 h-4 ml-0.5" />
                </button>
                <div class="flex-1 min-w-0">
                  <div class="flex items-center justify-between text-xs text-gray-400 mb-1">
                    <span class="font-mono">{{ fmtTime(playPos) }}</span>
                    <span class="font-mono">{{ fmtTime(totalDuration) }}</span>
                  </div>
                  <div class="relative h-1.5 bg-gray-700 rounded-full cursor-pointer" @click="seekTo">
                    <div class="absolute inset-y-0 left-0 bg-blue-500 rounded-full"
                      :style="{ width: totalDuration > 0 ? (playPos / totalDuration * 100) + '%' : '0%' }" />
                  </div>
                </div>
                <div class="flex items-center gap-2 shrink-0">
                  <Volume2 class="w-3.5 h-3.5 text-gray-400" />
                  <input type="range" min="0" max="1" step="0.05" :value="volume"
                    class="w-20 accent-blue-500" @input="setVolume" />
                </div>
              </div>
            </div>

            <!-- Split: annotation list (virtual) + annotation detail/edit -->
            <div class="flex-1 flex min-h-0 border-t border-gray-800">

              <!-- LEFT: virtual list -->
              <div class="w-80 shrink-0 border-r border-gray-800 flex flex-col">
                <div class="px-4 py-2 border-b border-gray-800 flex items-center gap-2 shrink-0">
                  <!-- Filter by type -->
                  <select v-model="bigFilterType" class="flex-1 bg-gray-800 border border-gray-700 rounded-lg text-xs text-gray-200 px-2 py-1.5 focus:outline-none focus:border-blue-500">
                    <option value="">全部类型</option>
                    <option v-for="t in annotationTypes" :key="t.value" :value="t.value">{{ t.label }}</option>
                  </select>
                  <!-- Sort -->
                  <button class="btn-icon btn-sm rounded text-gray-400 hover:text-white" title="按时间排序" @click="toggleSort">
                    <ArrowUpDown class="w-3.5 h-3.5" />
                  </button>
                </div>
                <!-- Virtual scroll container -->
                <div ref="bigListContainer" class="flex-1 overflow-y-auto" @scroll="onBigListScroll">
                  <!-- Spacer top -->
                  <div :style="{ height: virtualPaddingTop + 'px' }" />
                  <!-- Rendered rows -->
                  <div v-for="a in virtualRows" :key="a.id"
                    class="flex items-center gap-2 px-3 py-2 cursor-pointer border-b border-gray-800/50 group transition-colors"
                    :class="bigSelectedId === a.id ? 'bg-blue-900/40' : 'hover:bg-gray-800'"
                    @click="selectAnnotation(a)">
                    <span class="shrink-0 w-16 text-xs truncate" :style="{ color: ANN_COLORS[a.annotation_type]?.line ?? '#94a3b8' }">
                      {{ a.annotation_type.toUpperCase() }}
                    </span>
                    <span class="flex-1 text-xs text-gray-300 truncate">{{ a.label || '—' }}</span>
                    <span class="text-xs text-gray-500 font-mono shrink-0">{{ a.start_time.toFixed(2) }}s</span>
                    <!-- actions -->
                    <div class="flex items-center gap-0.5 shrink-0 opacity-0 group-hover:opacity-100 transition-opacity">
                      <button class="w-5 h-5 flex items-center justify-center rounded hover:bg-blue-700" @click.stop="selectAnnotation(a, true)">
                        <Pencil class="w-3 h-3" />
                      </button>
                      <button class="w-5 h-5 flex items-center justify-center rounded hover:bg-red-700" @click.stop="delAnnotation(a.id)">
                        <Trash2 class="w-3 h-3" />
                      </button>
                    </div>
                  </div>
                  <!-- Spacer bottom -->
                  <div :style="{ height: virtualPaddingBottom + 'px' }" />
                  <div v-if="filteredAnnotations.length === 0" class="px-4 py-8 text-center text-xs text-gray-500">无标记</div>
                </div>
              </div>

              <!-- RIGHT: detail / inline edit -->
              <div class="flex-1 flex flex-col min-h-0 overflow-y-auto p-5">
                <template v-if="bigEditMode && bigEditForm">
                  <!-- Edit form -->
                  <div class="mb-3 flex items-center justify-between">
                    <h4 class="text-sm font-semibold text-gray-200">{{ bigEditingAnnotation ? '编辑标记' : '新增标记' }}</h4>
                    <button class="btn-icon btn-sm rounded text-gray-400 hover:text-white" @click="cancelBigEdit">
                      <X class="w-4 h-4" />
                    </button>
                  </div>
                  <div class="space-y-4 text-sm">
                    <div>
                      <label class="text-xs text-gray-400 block mb-1">标记类型</label>
                      <select v-model="bigEditForm.annotation_type" class="w-full bg-gray-800 border border-gray-700 rounded-lg text-gray-200 px-3 py-2 text-sm focus:outline-none focus:border-blue-500" :disabled="!!bigEditingAnnotation">
                        <option v-for="t in annotationTypes" :key="t.value" :value="t.value">{{ t.label }}</option>
                      </select>
                    </div>
                    <div>
                      <label class="text-xs text-gray-400 block mb-1">标签</label>
                      <input v-model="bigEditForm.label" type="text" class="w-full bg-gray-800 border border-gray-700 rounded-lg text-gray-200 px-3 py-2 text-sm focus:outline-none focus:border-blue-500" />
                    </div>
                    <!-- Time range pickers with "click on wave" support -->
                    <div class="grid grid-cols-2 gap-3">
                      <div>
                        <label class="text-xs text-gray-400 block mb-1">开始时间 (s)</label>
                        <div class="flex items-center gap-1.5">
                          <input v-model.number="bigEditForm.start_time" type="number" min="0" step="0.001" class="flex-1 bg-gray-800 border border-gray-700 rounded-lg text-gray-200 px-3 py-2 text-sm focus:outline-none focus:border-blue-500" />
                          <button class="w-8 h-8 flex items-center justify-center rounded-lg border border-dashed text-xs transition-colors"
                            :class="bigPickingField === 'start' ? 'border-blue-400 bg-blue-900/30 text-blue-400' : 'border-gray-700 text-gray-500 hover:text-gray-300'"
                            title="在波形上点击选取" @click="togglePicking('start')">
                            <Crosshair class="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </div>
                      <div>
                        <label class="text-xs text-gray-400 block mb-1">结束时间 (s)</label>
                        <div class="flex items-center gap-1.5">
                          <input v-model.number="bigEditForm.end_time" type="number" min="0" step="0.001" class="flex-1 bg-gray-800 border border-gray-700 rounded-lg text-gray-200 px-3 py-2 text-sm focus:outline-none focus:border-blue-500" />
                          <button class="w-8 h-8 flex items-center justify-center rounded-lg border border-dashed text-xs transition-colors"
                            :class="bigPickingField === 'end' ? 'border-blue-400 bg-blue-900/30 text-blue-400' : 'border-gray-700 text-gray-500 hover:text-gray-300'"
                            title="在波形上点击选取" @click="togglePicking('end')">
                            <Crosshair class="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </div>
                    </div>
                    <!-- Visual time range display -->
                    <div v-if="bigEditForm.start_time != null && bigEditForm.end_time != null && totalDuration > 0"
                      class="relative h-6 bg-gray-800 rounded-full overflow-hidden">
                      <div class="absolute inset-y-0 bg-blue-600/40 rounded-full"
                        :style="{
                          left: (bigEditForm.start_time / totalDuration * 100) + '%',
                          width: ((bigEditForm.end_time - bigEditForm.start_time) / totalDuration * 100) + '%'
                        }" />
                      <div class="absolute inset-0 flex items-center justify-center text-xs text-gray-400">
                        {{ (bigEditForm.end_time - bigEditForm.start_time).toFixed(3) }}s
                      </div>
                    </div>
                    <div>
                      <label class="text-xs text-gray-400 block mb-1">置信度 (0–1)</label>
                      <input v-model.number="bigEditForm.confidence" type="number" min="0" max="1" step="0.01" placeholder="可选" class="w-full bg-gray-800 border border-gray-700 rounded-lg text-gray-200 px-3 py-2 text-sm focus:outline-none focus:border-blue-500" />
                    </div>
                    <!-- Picking hint -->
                    <div v-if="bigPickingField" class="p-3 bg-blue-900/20 border border-blue-700/40 rounded-lg text-xs text-blue-300 flex items-center gap-2">
                      <Crosshair class="w-3.5 h-3.5 shrink-0" />
                      正在选取「{{ bigPickingField === 'start' ? '开始' : '结束' }}时间」，请在上方波形上点击目标位置
                    </div>
                  </div>
                  <div class="mt-5 flex items-center gap-3">
                    <button class="btn-secondary btn-sm" @click="cancelBigEdit">取消</button>
                    <button class="flex-1 btn-primary btn-sm" :disabled="saving" @click="saveBigAnnotation">
                      <span v-if="saving" class="spinner w-3.5 h-3.5" />{{ bigEditingAnnotation ? '保存修改' : '确认添加' }}
                    </button>
                    <button v-if="bigEditingAnnotation" class="btn-icon btn-sm rounded text-red-400 hover:bg-red-900/30 hover:text-red-300"
                      @click="delAnnotation(bigEditingAnnotation.id)"><Trash2 class="w-4 h-4" /></button>
                  </div>
                </template>

                <!-- Detail view (read-only) -->
                <template v-else-if="bigSelectedAnnotation">
                  <div class="mb-3 flex items-center justify-between">
                    <h4 class="text-sm font-semibold" :style="{ color: ANN_COLORS[bigSelectedAnnotation.annotation_type]?.line ?? '#fff' }">
                      {{ bigSelectedAnnotation.annotation_type.toUpperCase() }}
                    </h4>
                    <div class="flex items-center gap-2">
                      <button class="btn-icon btn-sm rounded text-gray-400 hover:text-white" @click="openBigEditInline(bigSelectedAnnotation)">
                        <Pencil class="w-4 h-4" />
                      </button>
                      <button class="btn-icon btn-sm rounded text-red-400 hover:bg-red-900/30" @click="delAnnotation(bigSelectedAnnotation.id)">
                        <Trash2 class="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                  <dl class="space-y-2 text-sm">
                    <div class="flex justify-between">
                      <dt class="text-gray-500">标签</dt><dd class="text-gray-200">{{ bigSelectedAnnotation.label || '—' }}</dd>
                    </div>
                    <div class="flex justify-between">
                      <dt class="text-gray-500">开始时间</dt><dd class="font-mono text-gray-200">{{ bigSelectedAnnotation.start_time.toFixed(4) }}s</dd>
                    </div>
                    <div class="flex justify-between">
                      <dt class="text-gray-500">结束时间</dt><dd class="font-mono text-gray-200">{{ bigSelectedAnnotation.end_time?.toFixed(4) ?? '—' }}s</dd>
                    </div>
                    <div class="flex justify-between">
                      <dt class="text-gray-500">时长</dt>
                      <dd class="font-mono text-gray-200">
                        {{ bigSelectedAnnotation.end_time != null ? (bigSelectedAnnotation.end_time - bigSelectedAnnotation.start_time).toFixed(4) + 's' : '—' }}
                      </dd>
                    </div>
                    <div class="flex justify-between">
                      <dt class="text-gray-500">置信度</dt>
                      <dd class="text-gray-200">{{ bigSelectedAnnotation.confidence != null ? (bigSelectedAnnotation.confidence * 100).toFixed(1) + '%' : '—' }}</dd>
                    </div>
                    <div class="flex justify-between">
                      <dt class="text-gray-500">来源</dt>
                      <dd><span :class="bigSelectedAnnotation.source === 'auto' ? 'badge-amber' : 'badge-gray'" class="text-xs">{{ bigSelectedAnnotation.source === 'auto' ? '自动' : '手动' }}</span></dd>
                    </div>
                  </dl>
                  <button class="mt-5 btn-primary btn-sm w-full" @click="openBigEditInline(bigSelectedAnnotation)">
                    <Pencil class="w-3.5 h-3.5" />编辑此标记
                  </button>
                </template>

                <!-- Empty state -->
                <div v-else class="flex-1 flex flex-col items-center justify-center text-gray-600 gap-3">
                  <Tag class="w-10 h-10" />
                  <p class="text-sm">从左侧选择标记查看详情</p>
                  <p class="text-xs">或点击「添加标记」新建</p>
                </div>
              </div>
            </div>
          </div>
        </Transition>
      </Teleport>
    </div>
  </AppLayout>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { useRoute } from 'vue-router'
import {
  ChevronLeft, ChevronRight, Download, BarChart2, Plus, Trash2, Tag,
  HardDrive, Clock, Cpu, Layers, Calendar, Music, Video,
  Activity, File, Pencil, Zap, CheckCircle2, ZoomIn, ZoomOut, Maximize2,
  Play, Pause, Volume2, Expand, X, ArrowUpDown, Crosshair, Share2, Settings,
  TrendingUp,
} from 'lucide-vue-next'
import AppLayout from '@/components/layout/AppLayout.vue'
import AppModal from '@/components/ui/AppModal.vue'
import DetectionPanel from '@/components/ui/DetectionPanel.vue'
import BpmPanel from '@/components/ui/BpmPanel.vue'
import { useToastStore } from '@/store/toast'

const route = useRoute()
const toast = useToastStore()
const fileId = route.params.id as string
const token = localStorage.getItem('token')
const authHeader = { Authorization: `Bearer ${token}` }

// ── Core data ─────────────────────────────────────────────────────
const file = ref<any>(null)
const loading = ref(true)
const loadingWaveform = ref(false)
const loadingAnnotations = ref(false)
const waveform = ref<number[]>([])           // overview：全文件低分辨率（用于缩略/lane视图）
const detailSamples = ref<number[]>([])       // detail：当前视口高分辨率数据
const detailRange = ref<{ start: number; end: number } | null>(null)  // detail 对应的时间范围（秒）
const annotations = ref<any[]>([])
const totalDuration = ref(0)

// ── Detail fetch debounce ──────────────────────────────────────────
let detailTimer: ReturnType<typeof setTimeout> | null = null
const DETAIL_THRESHOLD = 0.3  // 视口占总时长 < 30% 时启用 detail fetch

const scheduleDetailFetch = () => {
  if (detailTimer) clearTimeout(detailTimer)
  detailTimer = setTimeout(() => {
    if (totalDuration.value <= 0 || viewWindow.value >= DETAIL_THRESHOLD) return
    const t0 = viewStart.value * totalDuration.value
    const t1 = viewEnd.value * totalDuration.value
    // 拉取范围在视口基础上各扩展 50% 以便平移时不立即出现空白
    const span = t1 - t0
    const fetchStart = Math.max(0, t0 - span * 0.5)
    const fetchEnd = Math.min(totalDuration.value, t1 + span * 0.5)
    fetchDetail(fetchStart, fetchEnd)
  }, 300)
}

const fetchDetail = async (t0: number, t1: number) => {
  const containerW = waveContainer.value?.clientWidth ?? 800
  // detail 精度：每像素 4 个点，上限 12000
  const pts = Math.min(12000, Math.max(2000, containerW * 4))
  try {
    const r = await fetch(
      `/api/v1/files/${fileId}/waveform?max_points=${pts}&start_time=${t0.toFixed(3)}&end_time=${t1.toFixed(3)}`,
      { headers: authHeader }
    )
    if (r.ok) {
      const d = await r.json()
      detailSamples.value = d.samples ?? []
      detailRange.value = { start: d.region_start ?? t0, end: d.region_end ?? t1 }
      redrawAll()
    }
  } catch { /* ignore */ }
}

// ── Canvas (small) ────────────────────────────────────────────────
const canvas = ref<HTMLCanvasElement | null>(null)
const waveContainer = ref<HTMLElement | null>(null)
const waveContainerW = ref(800)

// ── Big modal multi-lane state ────────────────────────────────────
const laneSeconds = ref(5)
const lanesPerPage = ref(4)
const bigPage = ref(0)

const totalLanes = computed(() => totalDuration.value > 0 ? Math.ceil(totalDuration.value / laneSeconds.value) : 1)
const totalBigPages = computed(() => Math.ceil(totalLanes.value / lanesPerPage.value))
const currentPageLanes = computed(() => {
  const start = bigPage.value * lanesPerPage.value
  const end = Math.min(totalLanes.value, start + lanesPerPage.value)
  return Array.from({ length: end - start }, (_, i) => start + i)
})

const laneCanvases = ref<(HTMLCanvasElement | null)[]>([])
const setLaneCanvas = (el: any, i: number) => {
  laneCanvases.value[i] = el as HTMLCanvasElement | null
}
// ── UI ────────────────────────────────────────────────────────────
const showEditModal = ref(false)     // small modal for add/edit
const showTypeModal = ref(false)
const showShareModal = ref(false)
const showBigModal = ref(false)
const saving = ref(false)
const detecting = ref(false)
const lastDetectResult = ref<any>(null)
const showDetectPanel = ref(false)  // detection settings panel expanded state
const showBpmPanel = ref(true)      // BPM chart panel expanded state

// BPM-relevant annotations (S1, S2, QRS, P-wave, R-peak)
const BPM_BEAT_TYPES = ['s1', 's2', 'qrs', 'p_wave', 'r_peak']
const bpmAnnotations = computed(() =>
  annotations.value.filter(a => BPM_BEAT_TYPES.includes(a.annotation_type))
)

// ── Share to community ────────────────────────────────────────────
const shareForm = ref({ title: '', content: '', tags: [] as string[] })
const shareTagInput = ref('')
const shareSubmitting = ref(false)

const addShareTag = () => {
  const t = shareTagInput.value.trim()
  if (t && !shareForm.value.tags.includes(t)) shareForm.value.tags.push(t)
  shareTagInput.value = ''
}

const submitShare = async () => {
  if (!fileId) return
  shareSubmitting.value = true
  const r = await fetch('/api/v1/community/posts', {
    method: 'POST',
    headers: { ...authHeader, 'Content-Type': 'application/json' },
    body: JSON.stringify({
      title: shareForm.value.title,
      content: shareForm.value.content,
      file_id: fileId,
      tags: shareForm.value.tags,
    }),
  })
  shareSubmitting.value = false
  if (r.ok) {
    toast.success('已分享到社区')
    showShareModal.value = false
    shareForm.value = { title: '', content: '', tags: [] }
  } else {
    const e = await r.json().catch(() => ({}))
    toast.error(e.detail ?? '分享失败')
  }
}

// ── Small modal form ──────────────────────────────────────────────
const editingAnnotation = ref<any>(null)
const editForm = ref({ annotation_type: 's1', label: '', start_time: 0, end_time: 0, confidence: null as number | null })

// ── Pagination (small list) ───────────────────────────────────────
const annPage = ref(1)
const ANN_PAGE_SIZE = 20
const totalAnnPages = computed(() => Math.max(1, Math.ceil(annotations.value.length / ANN_PAGE_SIZE)))
const pagedAnnotations = computed(() => {
  const s = (annPage.value - 1) * ANN_PAGE_SIZE
  return annotations.value.slice(s, s + ANN_PAGE_SIZE)
})
const paginationPages = computed(() => {
  const total = totalAnnPages.value, cur = annPage.value
  if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1)
  const pages: (number | string)[] = [1]
  if (cur > 3) pages.push('...')
  for (let p = Math.max(2, cur - 1); p <= Math.min(total - 1, cur + 1); p++) pages.push(p)
  if (cur < total - 2) pages.push('...')
  pages.push(total)
  return pages
})

// ── Shared zoom / pan state (both canvases share same view) ───────
const viewStart = ref(0)
const viewEnd = ref(1)
const MIN_VIEW_WIDTH = 0.005

const viewWindow = computed(() => viewEnd.value - viewStart.value)
const ANNOTATION_ZOOM_THRESHOLD = 0.20
const showAnnotationsOnWave = computed(() => viewWindow.value <= ANNOTATION_ZOOM_THRESHOLD)
const zoomLabel = computed(() => { const s = 1 / viewWindow.value; return s < 10 ? `${s.toFixed(1)}×` : `${Math.round(s)}×` })

const fmtTime = (s: number) => s < 60 ? `${s.toFixed(2)}s` : `${Math.floor(s / 60)}:${(s % 60).toFixed(1).padStart(4, '0')}`
const viewStartLabel = computed(() => fmtTime(viewStart.value * totalDuration.value))
const viewEndLabel = computed(() => fmtTime(viewEnd.value * totalDuration.value))
const scrollbarLeft = computed(() => viewStart.value * 100)
const scrollbarWidth = computed(() => viewWindow.value * 100)

// ── Tooltip (small) ───────────────────────────────────────────────
const hoveredAnnotation = ref<any>(null)
const tooltipX = ref(0)

// ── Tooltip (big) ─────────────────────────────────────────────────
const bigHoveredAnnotation = ref<any>(null)
const bigTooltipX = ref(0)

// ── Colors ────────────────────────────────────────────────────────
const ANN_COLORS: Record<string, { line: string; bg: string }> = {
  s1:      { line: '#ef4444', bg: 'rgba(239,68,68,0.15)' },
  s2:      { line: '#3b82f6', bg: 'rgba(59,130,246,0.15)' },
  qrs:     { line: '#22c55e', bg: 'rgba(34,197,94,0.15)' },
  p_wave:  { line: '#f59e0b', bg: 'rgba(245,158,11,0.15)' },
  t_wave:  { line: '#f97316', bg: 'rgba(249,115,22,0.15)' },
  murmur:  { line: '#a855f7', bg: 'rgba(168,85,247,0.15)' },
  default: { line: '#94a3b8', bg: 'rgba(148,163,184,0.15)' },
}

// ── Draw helper ───────────────────────────────────────────────────
const drawCanvas = (
  c: HTMLCanvasElement,
  containerEl: HTMLElement,
  widthRef: { value: number },
  height: number,
  bgColor: string,
  gridColor: string,
  waveColor: string,
  alwaysShowAnnotations: boolean,
  highlightId?: string,
) => {
  const ctx = c.getContext('2d')!
  const W = containerEl.clientWidth || 800
  c.width = W; c.height = height
  widthRef.value = W
  ctx.clearRect(0, 0, W, height)

  // Background
  ctx.fillStyle = bgColor; ctx.fillRect(0, 0, W, height)

  // Grid
  ctx.strokeStyle = gridColor; ctx.lineWidth = 1
  for (let i = 0; i <= 4; i++) {
    const y = (height / 4) * i; ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke()
  }
  ctx.strokeStyle = gridColor === '#e5e7eb' ? '#d1d5db' : '#374151'; ctx.lineWidth = 1
  ctx.beginPath(); ctx.moveTo(0, height / 2); ctx.lineTo(W, height / 2); ctx.stroke()

  // Annotation overlays
  const dur = totalDuration.value
  const shouldShow = alwaysShowAnnotations || showAnnotationsOnWave.value
  if (annotations.value.length > 0 && dur > 0) {
    const tS = viewStart.value * dur, tE = viewEnd.value * dur, tR = tE - tS
    for (const ann of annotations.value) {
      const st = ann.start_time as number
      const et = (ann.end_time ?? st) as number
      if (et < tS || st > tE) continue
      const col = ANN_COLORS[ann.annotation_type] ?? ANN_COLORS.default
      const xS = Math.max(0, ((st - tS) / tR) * W)
      const xE = Math.min(W, ((et - tS) / tR) * W)
      const xMid = (xS + xE) / 2
      const spanW = Math.max(1, xE - xS)
      const isHighlighted = ann.id === highlightId

      if (shouldShow) {
        if (spanW > 2) {
          ctx.fillStyle = isHighlighted ? col.bg.replace('0.15', '0.35') : col.bg
          ctx.fillRect(xS, 0, spanW, height)
        }
        if (isHighlighted) {
          ctx.strokeStyle = col.line; ctx.lineWidth = 2; ctx.setLineDash([])
          ctx.strokeRect(xS, 0, spanW, height)
        }
        ctx.strokeStyle = col.line; ctx.lineWidth = isHighlighted ? 2 : 1.5; ctx.setLineDash([4, 3])
        ctx.beginPath(); ctx.moveTo(xMid, 0); ctx.lineTo(xMid, height); ctx.stroke()
        ctx.setLineDash([])
        const label = ann.annotation_type.replace('_wave', '').toUpperCase()
        ctx.font = `bold ${isHighlighted ? 11 : 10}px system-ui,sans-serif`
        const tw = ctx.measureText(label).width
        const tagX = Math.min(W - tw - 8, Math.max(2, xMid - tw / 2 - 3))
        ctx.fillStyle = col.line; roundRect(ctx, tagX, 4, tw + 6, 16, 3); ctx.fill()
        ctx.fillStyle = '#fff'; ctx.fillText(label, tagX + 3, 17)
      } else {
        ctx.strokeStyle = col.line; ctx.lineWidth = 1; ctx.globalAlpha = 0.5
        ctx.beginPath(); ctx.moveTo(xMid, 0); ctx.lineTo(xMid, 12); ctx.stroke()
        ctx.globalAlpha = 1
      }
    }
  }

  // Waveform — 优先使用 detail 高分辨率数据，否则 fallback 到 overview
  let samples: number[]
  const totalDur = totalDuration.value
  const vS = viewStart.value * totalDur
  const vE = viewEnd.value * totalDur

  const dr = detailRange.value
  if (
    dr &&
    detailSamples.value.length > 0 &&
    dr.start <= vS + 0.001 &&
    dr.end >= vE - 0.001
  ) {
    // 视口在 detail 范围内：从 detail 数据里裁出对应片段
    const detailDur = dr.end - dr.start
    const lo = Math.floor(((vS - dr.start) / detailDur) * detailSamples.value.length)
    const hi = Math.ceil(((vE - dr.start) / detailDur) * detailSamples.value.length)
    samples = detailSamples.value.slice(Math.max(0, lo), Math.min(detailSamples.value.length, hi))
  } else {
    // fallback：overview 数据
    if (waveform.value.length === 0) return
    const lo = Math.floor(viewStart.value * waveform.value.length)
    const hi = Math.ceil(viewEnd.value * waveform.value.length)
    samples = waveform.value.slice(lo, hi)
  }

  if (samples.length === 0) return
  ctx.strokeStyle = waveColor; ctx.lineWidth = viewWindow.value < 0.04 ? 1.5 : 1
  ctx.beginPath()
  for (let i = 0; i < samples.length; i++) {
    const x = (i / Math.max(1, samples.length - 1)) * W
    const y = height / 2 - samples[i] * (height / 2) * 0.85
    i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y)
  }
  ctx.stroke()
}

const drawWaveform = () => {
  const c = canvas.value, el = waveContainer.value
  if (!c || !el || !waveform.value.length) return
  drawCanvas(c, el, waveContainerW, 180, '#f9fafb', '#e5e7eb', '#3b82f6', false)
}

const LANE_H = 80
const drawLaneCanvas = (c: HTMLCanvasElement, laneIdx: number) => {
  const el = c.parentElement
  if (!el) return
  const W = el.clientWidth || 800
  c.width = W; c.height = LANE_H
  const ctx = c.getContext('2d')!
  const laneStart = laneIdx * laneSeconds.value
  const laneEnd = Math.min(totalDuration.value, laneStart + laneSeconds.value)
  const laneDur = laneEnd - laneStart
  if (laneDur <= 0) return

  ctx.fillStyle = '#111827'
  ctx.fillRect(0, 0, W, LANE_H)

  // Grid
  ctx.strokeStyle = '#1f2937'; ctx.lineWidth = 1
  ctx.beginPath(); ctx.moveTo(0, LANE_H / 2); ctx.lineTo(W, LANE_H / 2); ctx.stroke()
  ctx.globalAlpha = 0.4
  ctx.beginPath(); ctx.moveTo(0, LANE_H / 4); ctx.lineTo(W, LANE_H / 4); ctx.stroke()
  ctx.beginPath(); ctx.moveTo(0, LANE_H * 3 / 4); ctx.lineTo(W, LANE_H * 3 / 4); ctx.stroke()
  ctx.globalAlpha = 1

  // Annotations
  for (const ann of annotations.value) {
    const st = ann.start_time as number
    const et = (ann.end_time ?? st) as number
    if (et < laneStart || st > laneEnd) continue
    const col = ANN_COLORS[ann.annotation_type] ?? ANN_COLORS.default
    const xS = Math.max(0, ((st - laneStart) / laneDur) * W)
    const xE = Math.min(W, ((et - laneStart) / laneDur) * W)
    const xMid = (xS + xE) / 2
    const spanW = Math.max(1, xE - xS)
    const isSelected = ann.id === bigSelectedId.value

    if (spanW > 2) {
      ctx.fillStyle = isSelected ? col.bg.replace('0.15', '0.35') : col.bg
      ctx.fillRect(xS, 0, spanW, LANE_H)
    }
    if (isSelected) {
      ctx.strokeStyle = col.line; ctx.lineWidth = 2; ctx.setLineDash([])
      ctx.strokeRect(xS, 0, spanW, LANE_H)
    }
    ctx.strokeStyle = col.line; ctx.lineWidth = isSelected ? 2 : 1.5; ctx.setLineDash([3, 3])
    ctx.beginPath(); ctx.moveTo(xMid, 0); ctx.lineTo(xMid, LANE_H); ctx.stroke()
    ctx.setLineDash([])
    const lbl = ann.annotation_type.replace('_wave', '').toUpperCase()
    ctx.font = '9px system-ui,sans-serif'
    const tw = ctx.measureText(lbl).width
    const tagX = Math.min(W - tw - 6, Math.max(1, xMid - tw / 2 - 2))
    ctx.fillStyle = col.line; roundRect(ctx, tagX, 2, tw + 4, 13, 2); ctx.fill()
    ctx.fillStyle = '#fff'; ctx.fillText(lbl, tagX + 2, 12)
  }

  // Edit preview region
  if (bigEditMode.value && bigEditForm.value) {
    const st = bigEditForm.value.start_time ?? 0
    const et = bigEditForm.value.end_time ?? st
    if (et >= laneStart && st <= laneEnd) {
      const xS = Math.max(0, ((st - laneStart) / laneDur) * W)
      const xE = Math.min(W, ((et - laneStart) / laneDur) * W)
      ctx.fillStyle = 'rgba(99,102,241,0.25)'; ctx.fillRect(xS, 0, Math.max(2, xE - xS), LANE_H)
      ctx.strokeStyle = '#818cf8'; ctx.lineWidth = 1.5; ctx.setLineDash([4, 3])
      ctx.beginPath(); ctx.moveTo(xS, 0); ctx.lineTo(xS, LANE_H); ctx.stroke()
      if (xE !== xS) { ctx.beginPath(); ctx.moveTo(xE, 0); ctx.lineTo(xE, LANE_H); ctx.stroke() }
      ctx.setLineDash([])
    }
  }

  // Waveform
  const samples = waveform.value
  if (samples.length > 0 && totalDuration.value > 0) {
    const loFrac = laneStart / totalDuration.value
    const hiFrac = laneEnd / totalDuration.value
    const lo = Math.floor(loFrac * samples.length)
    const hi = Math.ceil(hiFrac * samples.length)
    const visible = samples.slice(lo, hi)
    ctx.strokeStyle = '#60a5fa'; ctx.lineWidth = 1
    ctx.beginPath()
    for (let i = 0; i < visible.length; i++) {
      const x = (i / Math.max(1, visible.length - 1)) * W
      const y = LANE_H / 2 - visible[i] * (LANE_H / 2) * 0.85
      i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y)
    }
    ctx.stroke()
  }

  // Time label (end of lane)
  ctx.fillStyle = '#374151'
  ctx.fillRect(W - 38, 0, 38, 14)
  ctx.fillStyle = '#9ca3af'; ctx.font = '9px monospace'
  ctx.fillText(fmtTime(laneEnd), W - 36, 11)
}

const drawBigMultiLane = async () => {
  await nextTick()
  // Trim stale entries from previous page
  laneCanvases.value.length = currentPageLanes.value.length
  currentPageLanes.value.forEach((laneIdx, i) => {
    const c = laneCanvases.value[i]
    if (c) drawLaneCanvas(c, laneIdx)
  })
}

const redrawAll = () => {
  drawWaveform()
  if (showBigModal.value) drawBigMultiLane()
  scheduleDetailFetch()
}

function roundRect(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, r: number) {
  ctx.beginPath()
  ctx.moveTo(x + r, y); ctx.lineTo(x + w - r, y); ctx.arcTo(x + w, y, x + w, y + r, r)
  ctx.lineTo(x + w, y + h - r); ctx.arcTo(x + w, y + h, x + w - r, y + h, r)
  ctx.lineTo(x + r, y + h); ctx.arcTo(x, y + h, x, y + h - r, r)
  ctx.lineTo(x, y + r); ctx.arcTo(x, y, x + r, y, r); ctx.closePath()
}

// ── View helpers ──────────────────────────────────────────────────
const clampView = (s: number, e: number): [number, number] => {
  const w = e - s; let ns = Math.max(0, s); let ne = ns + w
  if (ne > 1) { ne = 1; ns = Math.max(0, 1 - w) }
  return [ns, ne]
}
const zoom = (delta: number) => {
  const w = viewWindow.value, center = (viewStart.value + viewEnd.value) / 2
  const newW = Math.min(1, Math.max(MIN_VIEW_WIDTH, w + delta * w))
  const [s, e] = clampView(center - newW / 2, center + newW / 2)
  viewStart.value = s; viewEnd.value = e; redrawAll()
}
const resetView = () => { viewStart.value = 0; viewEnd.value = 1; redrawAll() }

// ── Small canvas interactions ──────────────────────────────────────
const waveDragging = ref(false)
// Use plain vars (not refs) for drag state to avoid reactive stale-read issues
let _wvDragStartX = 0
let _wvDragStartViewStart = 0
let _wvDragViewWindow = 0

const onWheel = (e: WheelEvent) => {
  if (sbDragging.value) return
  const rect = (e.currentTarget as HTMLElement).getBoundingClientRect()
  const frac = (e.clientX - rect.left) / rect.width
  const pivot = viewStart.value + frac * viewWindow.value
  const factor = e.deltaY > 0 ? 1.25 : 0.8
  const newW = Math.min(1, Math.max(MIN_VIEW_WIDTH, viewWindow.value * factor))
  const [s, en] = clampView(pivot - frac * newW, pivot - frac * newW + newW)
  viewStart.value = s; viewEnd.value = en; redrawAll()
}

const onWaveMouseDown = (e: MouseEvent) => {
  // Capture drag state in plain vars — immune to Vue reactivity batching
  _wvDragStartX = e.clientX
  _wvDragStartViewStart = viewStart.value
  _wvDragViewWindow = viewWindow.value
  waveDragging.value = true

  const onMove = (me: MouseEvent) => {
    if (!waveDragging.value || !waveContainer.value) return
    const rect = waveContainer.value.getBoundingClientRect()
    const dx = (me.clientX - _wvDragStartX) / rect.width
    // Always pan relative to the snapshot taken at mousedown
    const newStart = Math.max(0, Math.min(1 - _wvDragViewWindow, _wvDragStartViewStart - dx * _wvDragViewWindow))
    viewStart.value = newStart
    viewEnd.value = newStart + _wvDragViewWindow
    redrawAll()
  }
  const onUp = () => {
    waveDragging.value = false
    window.removeEventListener('mousemove', onMove)
    window.removeEventListener('mouseup', onUp)
  }
  window.addEventListener('mousemove', onMove)
  window.addEventListener('mouseup', onUp)
}

const onWaveMouseMove = (e: MouseEvent) => {
  // Only used for annotation hover tooltip now — drag is handled via window listeners
  if (!showAnnotationsOnWave.value || !totalDuration.value) { hoveredAnnotation.value = null; return }
  if (!waveContainer.value) return
  const rect = waveContainer.value.getBoundingClientRect()
  const frac = (e.clientX - rect.left) / rect.width
  const t = (viewStart.value + frac * viewWindow.value) * totalDuration.value
  hoveredAnnotation.value = annotations.value.find(a => t >= (a.start_time - 0.02) && t <= ((a.end_time ?? a.start_time) + 0.02)) ?? null
  tooltipX.value = e.clientX - rect.left
}
const onWaveMouseUp = () => { waveDragging.value = false; }
const onWaveMouseLeave = () => { hoveredAnnotation.value = null }

// ── Scrollbar ─────────────────────────────────────────────────────
const scrollbarTrack = ref<HTMLElement | null>(null)
const sbDragging = ref(false)

// Track background click → jump view center to click position
const onScrollbarTrackDown = (e: MouseEvent) => {
  if (!scrollbarTrack.value) return
  const rect = scrollbarTrack.value.getBoundingClientRect()
  const frac = (e.clientX - rect.left) / rect.width
  // Only jump if click lands outside the current thumb
  if (frac < viewStart.value || frac > viewStart.value + viewWindow.value) {
    const half = viewWindow.value / 2
    const [s, en] = clampView(frac - half, frac - half + viewWindow.value)
    viewStart.value = s; viewEnd.value = en; redrawAll()
  }
}

// Thumb mousedown → pure pan, no jump, snapshotted at mousedown
const onScrollbarThumbDown = (e: MouseEvent) => {
  if (!scrollbarTrack.value) return
  sbDragging.value = true
  const rect = scrollbarTrack.value.getBoundingClientRect()
  const cursorFrac = (e.clientX - rect.left) / rect.width
  // Snapshot: offset of mouse within thumb, and window width
  const thumbOffset = cursorFrac - viewStart.value   // mouse-to-thumb-left distance
  const snapWindow = viewWindow.value                  // freeze window width for this drag

  const onMove = (me: MouseEvent) => {
    if (!scrollbarTrack.value) return
    const r = scrollbarTrack.value.getBoundingClientRect()
    const f = (me.clientX - r.left) / r.width
    const newStart = Math.max(0, Math.min(1 - snapWindow, f - thumbOffset))
    viewStart.value = newStart
    viewEnd.value = newStart + snapWindow
    redrawAll()
  }
  const onUp = () => {
    sbDragging.value = false
    window.removeEventListener('mousemove', onMove)
    window.removeEventListener('mouseup', onUp)
  }
  window.addEventListener('mousemove', onMove)
  window.addEventListener('mouseup', onUp)
}

// ── Big modal lane interactions ───────────────────────────────────
const bigPickingField = ref<'start' | 'end' | null>(null)
const bigHoveredLane = ref(-1)
const quickAddType = ref('s1')

// Drag-to-move annotation state
const laneDragAnn = ref<any>(null)
const laneDragStartX = ref(0)
const laneDragOrigStart = ref(0)
const laneDragOrigEnd = ref(0)
const laneDragLaneIdx = ref(0)
const laneDragging = ref(false)

const laneCursor = (laneIdx: number) => {
  if (bigPickingField.value) return 'crosshair'
  if (laneDragging.value) return 'grabbing'
  if (bigHoveredAnnotation.value && bigHoveredLane.value === laneIdx) return 'grab'
  return 'default'
}

const getLanePlayheadPct = (laneIdx: number): number => {
  if (!totalDuration.value || (!isPlaying.value && playPos.value === 0)) return -1
  const laneStart = laneIdx * laneSeconds.value
  const laneEnd = Math.min(totalDuration.value, laneStart + laneSeconds.value)
  if (playPos.value < laneStart || playPos.value > laneEnd) return -1
  return ((playPos.value - laneStart) / (laneEnd - laneStart)) * 100
}

const onLaneMouseMove = (laneIdx: number, e: MouseEvent) => {
  if (!totalDuration.value) return
  const rect = (e.currentTarget as HTMLElement).getBoundingClientRect()
  const frac = (e.clientX - rect.left) / rect.width
  const laneStart = laneIdx * laneSeconds.value
  const laneEnd = Math.min(totalDuration.value, laneStart + laneSeconds.value)
  const t = laneStart + frac * (laneEnd - laneStart)

  // Handle annotation drag
  if (laneDragging.value && laneDragAnn.value) {
    const laneDur = laneEnd - laneStart
    const dxFrac = (e.clientX - laneDragStartX.value) / rect.width
    const dt = dxFrac * (laneDur)
    const dur = laneDragOrigEnd.value - laneDragOrigStart.value
    let newStart = laneDragOrigStart.value + dt
    let newEnd = newStart + dur
    if (newStart < 0) { newStart = 0; newEnd = dur }
    if (newEnd > totalDuration.value) { newEnd = totalDuration.value; newStart = Math.max(0, totalDuration.value - dur) }
    laneDragAnn.value.start_time = parseFloat(newStart.toFixed(4))
    laneDragAnn.value.end_time = parseFloat(newEnd.toFixed(4))
    drawBigMultiLane()
    return
  }

  bigHoveredAnnotation.value = annotations.value.find(a => t >= a.start_time - 0.02 && t <= (a.end_time ?? a.start_time) + 0.02) ?? null
  bigTooltipX.value = e.clientX - rect.left
  bigHoveredLane.value = laneIdx
}

const onLaneMouseLeave = () => {
  if (!laneDragging.value) {
    bigHoveredAnnotation.value = null; bigHoveredLane.value = -1
  }
}

const onLaneMouseDown = (laneIdx: number, e: MouseEvent) => {
  if (bigPickingField.value) return
  if (!bigHoveredAnnotation.value) return
  e.preventDefault()
  e.stopPropagation()
  laneDragging.value = true
  laneDragAnn.value = bigHoveredAnnotation.value
  laneDragStartX.value = e.clientX
  laneDragOrigStart.value = bigHoveredAnnotation.value.start_time
  laneDragOrigEnd.value = bigHoveredAnnotation.value.end_time ?? bigHoveredAnnotation.value.start_time
  laneDragLaneIdx.value = laneIdx

  const onUp = async (ue: MouseEvent) => {
    window.removeEventListener('mousemove', onGlobalMove)
    window.removeEventListener('mouseup', onUp)
    if (!laneDragAnn.value) { laneDragging.value = false; return }
    // Save to backend
    const ann = laneDragAnn.value
    laneDragging.value = false
    if (ann.start_time !== laneDragOrigStart.value || ann.end_time !== laneDragOrigEnd.value) {
      const r = await fetch(`/api/v1/annotations/${ann.id}`, {
        method: 'PUT',
        headers: { ...authHeader, 'Content-Type': 'application/json' },
        body: JSON.stringify({ start_time: ann.start_time, end_time: ann.end_time, label: ann.label }),
      })
      if (r.ok) {
        const updated = await r.json()
        const idx = annotations.value.findIndex(a => a.id === updated.id)
        if (idx !== -1) annotations.value[idx] = updated
        drawBigMultiLane()
        toast.success('标记位置已更新')
      } else {
        // Revert on failure
        ann.start_time = laneDragOrigStart.value
        ann.end_time = laneDragOrigEnd.value
        drawBigMultiLane()
        toast.error('更新失败')
      }
    }
    laneDragAnn.value = null
  }
  const onGlobalMove = (me: MouseEvent) => {
    if (!laneDragging.value) return
    const laneStart = laneIdx * laneSeconds.value
    const laneEnd = Math.min(totalDuration.value, laneStart + laneSeconds.value)
    const laneDur = laneEnd - laneStart
    // Find the lane element
    const laneEls = document.querySelectorAll('[data-lane-idx]')
    // Fallback: estimate width from the first canvas
    const canvas = laneCanvases.value[0]
    const W = canvas?.parentElement?.clientWidth || 800
    const dxFrac = (me.clientX - laneDragStartX.value) / W
    const dt = dxFrac * (laneEnd - laneStart)
    const dur = laneDragOrigEnd.value - laneDragOrigStart.value
    let newStart = laneDragOrigStart.value + dt
    let newEnd = newStart + dur
    if (newStart < 0) { newStart = 0; newEnd = dur }
    if (newEnd > totalDuration.value) { newEnd = totalDuration.value; newStart = Math.max(0, totalDuration.value - dur) }
    if (laneDragAnn.value) {
      laneDragAnn.value.start_time = parseFloat(newStart.toFixed(4))
      laneDragAnn.value.end_time = parseFloat(newEnd.toFixed(4))
      drawBigMultiLane()
    }
  }
  window.addEventListener('mousemove', onGlobalMove)
  window.addEventListener('mouseup', onUp)
}

const onLaneDblClick = async (laneIdx: number, e: MouseEvent) => {
  if (!totalDuration.value) return
  if (bigPickingField.value) return
  // Don't create if clicked on existing annotation
  if (bigHoveredAnnotation.value) return
  e.preventDefault()
  const rect = (e.currentTarget as HTMLElement).getBoundingClientRect()
  const frac = (e.clientX - rect.left) / rect.width
  const laneStart = laneIdx * laneSeconds.value
  const laneEnd = Math.min(totalDuration.value, laneStart + laneSeconds.value)
  const t = parseFloat((laneStart + frac * (laneEnd - laneStart)).toFixed(4))
  const half = 0.04
  const start_time = parseFloat(Math.max(0, t - half).toFixed(4))
  const end_time = parseFloat(Math.min(totalDuration.value, t + half).toFixed(4))
  const r = await fetch('/api/v1/annotations/', {
    method: 'POST',
    headers: { ...authHeader, 'Content-Type': 'application/json' },
    body: JSON.stringify({
      file_id: fileId,
      annotation_type: quickAddType.value,
      start_time,
      end_time,
      label: quickAddType.value.replace('_wave', '').toUpperCase(),
      confidence: null,
    }),
  })
  if (r.ok) {
    annotations.value.push(await r.json())
    drawBigMultiLane()
    toast.success('已快速添加标记')
  } else {
    toast.error('添加失败')
  }
}
const onLaneClick = (laneIdx: number, e: MouseEvent) => {
  if (!totalDuration.value) return
  if (bigPickingField.value && bigEditForm.value) {
    const rect = (e.currentTarget as HTMLElement).getBoundingClientRect()
    const frac = (e.clientX - rect.left) / rect.width
    const laneStart = laneIdx * laneSeconds.value
    const laneEnd = Math.min(totalDuration.value, laneStart + laneSeconds.value)
    const t = parseFloat((laneStart + frac * (laneEnd - laneStart)).toFixed(4))
    if (bigPickingField.value === 'start') {
      bigEditForm.value.start_time = t
      bigPickingField.value = 'end'
    } else {
      bigEditForm.value.end_time = Math.max(t, bigEditForm.value.start_time)
      bigPickingField.value = null
    }
    drawBigMultiLane()
    return
  }
  if (bigHoveredAnnotation.value) {
    selectAnnotation(bigHoveredAnnotation.value)
  }
}

const togglePicking = (field: 'start' | 'end') => {
  bigPickingField.value = bigPickingField.value === field ? null : field
}

// ── Big modal state ───────────────────────────────────────────────
const bigFilterType = ref('')
const bigSortAsc = ref(true)
const bigSelectedId = ref<string | null>(null)
const bigEditMode = ref(false)
const bigEditingAnnotation = ref<any>(null)
const bigEditForm = ref<any>(null)

const filteredAnnotations = computed(() => {
  let list = bigFilterType.value
    ? annotations.value.filter(a => a.annotation_type === bigFilterType.value)
    : [...annotations.value]
  list.sort((a, b) => bigSortAsc.value ? a.start_time - b.start_time : b.start_time - a.start_time)
  return list
})

const bigSelectedAnnotation = computed(() => filteredAnnotations.value.find(a => a.id === bigSelectedId.value) ?? null)

const toggleSort = () => { bigSortAsc.value = !bigSortAsc.value }

// ── Virtual list ──────────────────────────────────────────────────
const ROW_HEIGHT = 40  // px per row
const bigListContainer = ref<HTMLElement | null>(null)
const bigListScrollTop = ref(0)
const bigListViewportH = ref(400)

const onBigListScroll = (e: Event) => {
  bigListScrollTop.value = (e.target as HTMLElement).scrollTop
}

const virtualStart = computed(() => Math.max(0, Math.floor(bigListScrollTop.value / ROW_HEIGHT) - 5))
const virtualEnd = computed(() => Math.min(
  filteredAnnotations.value.length,
  Math.ceil((bigListScrollTop.value + bigListViewportH.value) / ROW_HEIGHT) + 5
))
const virtualRows = computed(() => filteredAnnotations.value.slice(virtualStart.value, virtualEnd.value))
const virtualPaddingTop = computed(() => virtualStart.value * ROW_HEIGHT)
const virtualPaddingBottom = computed(() => (filteredAnnotations.value.length - virtualEnd.value) * ROW_HEIGHT)

// ── Big modal actions ─────────────────────────────────────────────
const openBigModal = async () => {
  laneCanvases.value = []
  showBigModal.value = true
  await nextTick()
  drawBigMultiLane()
  if (bigListContainer.value) {
    bigListViewportH.value = bigListContainer.value.clientHeight
  }
  if (bigListContainer.value && !bigListResizeObs) {
    bigListResizeObs = new ResizeObserver(() => {
      if (bigListContainer.value) bigListViewportH.value = bigListContainer.value.clientHeight
    })
    bigListResizeObs.observe(bigListContainer.value)
  }
}

const selectAnnotation = (a: any, openEdit = false) => {
  bigSelectedId.value = a.id
  bigEditMode.value = false
  // Navigate to the right page
  if (totalDuration.value > 0) {
    const laneIdx = Math.floor(a.start_time / laneSeconds.value)
    const newPage = Math.floor(laneIdx / lanesPerPage.value)
    if (newPage !== bigPage.value) bigPage.value = newPage
  }
  drawBigMultiLane()
  if (isAudioFile.value && audioEl.value) {
    audioEl.value.currentTime = a.start_time
    playPos.value = a.start_time
  }
  if (openEdit) openBigEditInline(a)
}

const openBigEditInline = (a: any) => {
  bigEditingAnnotation.value = a
  bigEditForm.value = { annotation_type: a.annotation_type, label: a.label, start_time: a.start_time, end_time: a.end_time, confidence: a.confidence }
  bigEditMode.value = true
  bigPickingField.value = null
  drawBigMultiLane()
}

const cancelBigEdit = () => {
  bigEditMode.value = false
  bigEditingAnnotation.value = null
  bigEditForm.value = null
  bigPickingField.value = null
  drawBigMultiLane()
}

const saveBigAnnotation = async () => {
  if (!bigEditForm.value) return
  saving.value = true
  if (bigEditingAnnotation.value) {
    // UPDATE
    const r = await fetch(`/api/v1/annotations/${bigEditingAnnotation.value.id}`, {
      method: 'PUT',
      headers: { ...authHeader, 'Content-Type': 'application/json' },
      body: JSON.stringify({
        start_time: bigEditForm.value.start_time,
        end_time: bigEditForm.value.end_time,
        label: bigEditForm.value.label || bigEditForm.value.annotation_type.toUpperCase(),
        confidence: bigEditForm.value.confidence,
      }),
    })
    saving.value = false
    if (r.ok) {
      const updated = await r.json()
      const idx = annotations.value.findIndex(a => a.id === updated.id)
      if (idx !== -1) annotations.value[idx] = updated
      toast.success('标记已更新')
      cancelBigEdit()
      bigSelectedId.value = updated.id
      drawBigMultiLane()
    } else toast.error('更新失败')
  } else {
    // CREATE
    const r = await fetch('/api/v1/annotations/', {
      method: 'POST',
      headers: { ...authHeader, 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...bigEditForm.value, file_id: fileId, label: bigEditForm.value.label || bigEditForm.value.annotation_type.toUpperCase() }),
    })
    saving.value = false
    if (r.ok) {
      const created = await r.json()
      annotations.value.push(created)
      toast.success('标记已添加')
      bigSelectedId.value = created.id
      cancelBigEdit()
      drawBigMultiLane()
    } else toast.error('添加失败')
  }
}

// ── Audio player ──────────────────────────────────────────────────
const audioEl = ref<HTMLAudioElement | null>(null)
const isPlaying = ref(false)
const playPos = ref(0)
const volume = ref(1)

const isAudioFile = computed(() => file.value && ['audio', 'pcg'].includes(file.value.file_type))

const playheadX = computed(() => {
  if (!totalDuration.value) return -1
  const frac = playPos.value / totalDuration.value
  if (frac < viewStart.value || frac > viewEnd.value) return -1
  return ((frac - viewStart.value) / viewWindow.value) * waveContainerW.value
})

let audioBlobUrl = ''

const initAudio = async () => {
  if (!isAudioFile.value || !audioEl.value) return
  const res = await fetch(`/api/v1/files/${fileId}/download`, { headers: authHeader })
  if (!res.ok) return
  const blob = await res.blob()
  audioBlobUrl = URL.createObjectURL(blob)
  audioEl.value.src = audioBlobUrl
  audioEl.value.volume = volume.value
}

const togglePlay = () => {
  if (!audioEl.value) return
  if (isPlaying.value) { audioEl.value.pause() } else { audioEl.value.play() }
  isPlaying.value = !isPlaying.value
}

const onTimeUpdate = () => {
  if (audioEl.value) {
    playPos.value = audioEl.value.currentTime
    if (showBigModal.value && totalDuration.value > 0) {
      const currentLane = Math.floor(playPos.value / laneSeconds.value)
      const newPage = Math.floor(currentLane / lanesPerPage.value)
      if (newPage !== bigPage.value && newPage < totalBigPages.value) {
        bigPage.value = newPage
      }
    }
    if (showBigModal.value) drawBigMultiLane()
    else drawWaveform()
  }
}
const onEnded = () => { isPlaying.value = false }
const onAudioMeta = () => { if (audioEl.value && !totalDuration.value) totalDuration.value = audioEl.value.duration }

const seekTo = (e: MouseEvent) => {
  if (!audioEl.value || !totalDuration.value) return
  const rect = (e.currentTarget as HTMLElement).getBoundingClientRect()
  const frac = (e.clientX - rect.left) / rect.width
  audioEl.value.currentTime = frac * totalDuration.value
  playPos.value = audioEl.value.currentTime
}

const setVolume = (e: Event) => {
  volume.value = parseFloat((e.target as HTMLInputElement).value)
  if (audioEl.value) audioEl.value.volume = volume.value
}

const jumpToAnnotation = (ann: any) => {
  if (!totalDuration.value) return
  if (showBigModal.value) {
    selectAnnotation(ann)
    return
  }
  // small canvas mode
  const center = (ann.start_time + (ann.end_time ?? ann.start_time)) / 2
  const frac = center / totalDuration.value
  const half = Math.max(0.05, viewWindow.value / 2)
  const [s, e] = clampView(frac - half, frac + half)
  viewStart.value = s; viewEnd.value = e; drawWaveform()
  if (audioEl.value) { audioEl.value.currentTime = ann.start_time; playPos.value = ann.start_time }
}

// ── Small modal form helpers ──────────────────────────────────────
const openAddModal = (context: 'small' | 'big' | null) => {
  if (context === 'big') {
    // Open inline in big modal
    bigEditingAnnotation.value = null
    bigEditForm.value = { annotation_type: 's1', label: '', start_time: 0, end_time: 0, confidence: null }
    bigEditMode.value = true
    bigPickingField.value = null
  } else {
    editingAnnotation.value = null
    editForm.value = { annotation_type: 's1', label: '', start_time: 0, end_time: 0, confidence: null }
    showEditModal.value = true
  }
}

const openEditModal = (a: any) => {
  editingAnnotation.value = a
  editForm.value = { annotation_type: a.annotation_type, label: a.label, start_time: a.start_time, end_time: a.end_time, confidence: a.confidence }
  showEditModal.value = true
}

const saveAnnotation = async () => {
  saving.value = true
  if (editingAnnotation.value) {
    const r = await fetch(`/api/v1/annotations/${editingAnnotation.value.id}`, {
      method: 'PUT',
      headers: { ...authHeader, 'Content-Type': 'application/json' },
      body: JSON.stringify({ start_time: editForm.value.start_time, end_time: editForm.value.end_time, label: editForm.value.label || editForm.value.annotation_type.toUpperCase(), confidence: editForm.value.confidence }),
    })
    saving.value = false
    if (r.ok) {
      const updated = await r.json()
      const idx = annotations.value.findIndex(a => a.id === updated.id)
      if (idx !== -1) annotations.value[idx] = updated
      showEditModal.value = false; toast.success('标记已更新'); drawWaveform()
    } else toast.error('更新失败')
  } else {
    const r = await fetch('/api/v1/annotations/', {
      method: 'POST',
      headers: { ...authHeader, 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...editForm.value, file_id: fileId, label: editForm.value.label || editForm.value.annotation_type.toUpperCase() }),
    })
    saving.value = false
    if (r.ok) {
      annotations.value.push(await r.json()); showEditModal.value = false
      editForm.value = { annotation_type: 's1', label: '', start_time: 0, end_time: 0, confidence: null }
      toast.success('标记已添加'); redrawAll()
    } else toast.error('添加失败')
  }
}

const delAnnotation = async (id: string) => {
  const r = await fetch(`/api/v1/annotations/${id}`, { method: 'DELETE', headers: authHeader })
  if (r.ok) {
    annotations.value = annotations.value.filter(a => a.id !== id)
    if (bigSelectedId.value === id) { bigSelectedId.value = null; bigEditMode.value = false }
    if (pagedAnnotations.value.length === 0 && annPage.value > 1) annPage.value--
    toast.success('已删除'); redrawAll()
  }
}

// ── File type / detect ────────────────────────────────────────────
const annotationTypes = [
  { label: 'S1 心音', value: 's1' }, { label: 'S2 心音', value: 's2' },
  { label: 'QRS 波', value: 'qrs' }, { label: 'P 波', value: 'p_wave' },
  { label: 'T 波', value: 't_wave' }, { label: '杂音', value: 'murmur' },
  { label: '其他', value: 'other' },
]
const FILE_TYPE_LABELS: Record<string, string> = {
  audio: 'Audio 音频', video: 'Video 视频', ecg: 'ECG 心电', pcg: 'PCG 心音', other: '其他',
}
const FILE_TYPES = [
  { value: 'pcg',   label: 'PCG 心音',   desc: '心音信号，支持 S1/S2 检测',   icon: Activity },
  { value: 'ecg',   label: 'ECG 心电',   desc: '心电信号，支持 QRS/P/T 检测', icon: Activity },
  { value: 'audio', label: 'Audio 音频', desc: '通用音频，支持 S1/S2 检测',   icon: Music },
  { value: 'video', label: 'Video 视频', desc: '视频文件，暂不支持自动检测',  icon: Video },
  { value: 'other', label: '其他',       desc: '其他类型，暂不支持自动检测',  icon: File },
]
const DETECT_CONFIG: Record<string, { types: string[] }> = {
  pcg: { types: ['s1', 's2'] }, audio: { types: ['s1', 's2'] }, ecg: { types: ['qrs', 'p_wave', 't_wave'] },
}
const detectConfig = computed(() => file.value ? DETECT_CONFIG[file.value.file_type] ?? null : null)
const fileIcon = (t: string) => ({ audio: Music, video: Video, ecg: Activity, pcg: Activity }[t] ?? File)
const fileIconBg = (t: string) => ({ audio: 'bg-blue-50', video: 'bg-purple-50', ecg: 'bg-red-50', pcg: 'bg-pink-50' }[t] ?? 'bg-gray-50')
const fileIconColor = (t: string) => ({ audio: 'text-blue-500', video: 'text-purple-500', ecg: 'text-red-500', pcg: 'text-pink-500' }[t] ?? 'text-gray-400')
const fileTypeBadge = (t: string) => ({ audio: 'badge-blue', video: 'badge-purple', ecg: 'badge-red', pcg: 'badge-purple' }[t] ?? 'badge-gray')
const annotationBadge = (t: string) => ({
  s1: 'badge-red', s2: 'badge-blue', qrs: 'badge-green', p_wave: 'badge-amber', t_wave: 'badge-amber', murmur: 'badge-amber',
}[t] ?? 'badge-gray')

const changeFileType = async (newType: string) => {
  if (!file.value || file.value.file_type === newType) { showTypeModal.value = false; return }
  const r = await fetch(`/api/v1/files/${fileId}/type`, {
    method: 'PATCH', headers: { ...authHeader, 'Content-Type': 'application/json' },
    body: JSON.stringify({ file_type: newType }),
  })
  if (r.ok) { file.value = await r.json(); lastDetectResult.value = null; toast.success(`文件类型已修改为 ${FILE_TYPE_LABELS[newType] ?? newType}`) }
  else toast.error((await r.json().catch(() => ({}))).detail ?? '修改失败')
  showTypeModal.value = false
  if (['audio', 'pcg'].includes(newType)) await nextTick().then(initAudio)
}

const runDetect = async () => {
  if (!detectConfig.value || detecting.value) return
  detecting.value = true; lastDetectResult.value = null
  const r = await fetch(`/api/v1/files/${fileId}/detect?algorithm=auto`, { method: 'POST', headers: authHeader })
  detecting.value = false
  if (r.ok) {
    const result = await r.json(); lastDetectResult.value = result
    await loadAnnotations(); toast.success(`检测完成（${result.algorithm_used ?? 'auto'}），生成 ${result.detected_count} 个标记`)
  } else toast.error((await r.json().catch(() => ({}))).detail ?? '检测失败')
}

// Called by DetectionPanel when detection finishes
const onDetected = async (payload: { items: any[], algorithm: string, count: number }) => {
  lastDetectResult.value = { detected_count: payload.count }
  await loadAnnotations()
  toast.success(`检测完成（${payload.algorithm}），生成 ${payload.count} 个标记`)
}

// Clear auto-generated annotations
const clearAutoAnnotations = async () => {
  // Delete all annotations with source=auto for this file by re-running detect
  // with 0-length result — instead simply reload (backend already replaced them)
  annotations.value = annotations.value.filter(a => a.source !== 'auto')
  redrawAll()
  await nextTick()
  redrawAll()
  toast.success('已清除自动标记')
}

const download = async () => {
  const res = await fetch(`/api/v1/files/${fileId}/download`, { headers: authHeader })
  if (!res.ok) { toast.error('下载失败，请检查权限'); return }
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a'); a.href = url; a.download = file.value?.original_filename ?? 'file'
  a.click(); URL.revokeObjectURL(url)
}

// ── Data loaders ──────────────────────────────────────────────────
const loadFile = async () => {
  const r = await fetch(`/api/v1/files/${fileId}`, { headers: authHeader })
  if (r.ok) { file.value = await r.json(); if (file.value?.duration) totalDuration.value = file.value.duration }
  loading.value = false
}
const loadWaveform = async () => {
  loadingWaveform.value = true
  // overview：全文件低分辨率（用于缩略图和 lane 视图），固定 2000 点
  const r = await fetch(`/api/v1/files/${fileId}/waveform?max_points=2000`, { headers: authHeader })
  if (r.ok) {
    const d = await r.json()
    waveform.value = d.samples ?? []
    if (d.duration > 0) totalDuration.value = d.duration
    await nextTick(); redrawAll()
  }
  loadingWaveform.value = false
}
const loadAnnotations = async () => {
  loadingAnnotations.value = true
  const r = await fetch(`/api/v1/annotations/?file_id=${fileId}&limit=1000`, { headers: authHeader })
  if (r.ok) annotations.value = (await r.json()).items ?? []
  loadingAnnotations.value = false
  redrawAll()
}

const formatSize = (b: number) => b < 1024 ** 2 ? `${(b / 1024).toFixed(1)} KB` : `${(b / 1024 ** 2).toFixed(1)} MB`
const formatDuration = (s: number) => `${Math.floor(s / 60)}:${Math.floor(s % 60).toString().padStart(2, '0')}`
const formatDate = (d: string) => new Date(d).toLocaleString('zh-CN')

// ── Resize observers ──────────────────────────────────────────────
let resizeObs: ResizeObserver | null = null
let bigListResizeObs: ResizeObserver | null = null

onMounted(async () => {
  await loadFile()
  await Promise.all([loadWaveform(), loadAnnotations()])
  if (waveContainer.value) {
    resizeObs = new ResizeObserver(() => drawWaveform())
    resizeObs.observe(waveContainer.value)
  }
  await nextTick()
  await initAudio()
})

onUnmounted(() => {
  resizeObs?.disconnect()
  bigListResizeObs?.disconnect()
  if (audioBlobUrl) URL.revokeObjectURL(audioBlobUrl)
  audioEl.value?.pause()
})

// ── Multi-lane watches ────────────────────────────────────────────
watch([currentPageLanes, () => annotations.value.length, bigSelectedId, bigEditForm], () => {
  if (showBigModal.value) drawBigMultiLane()
}, { deep: true })

watch([laneSeconds, lanesPerPage], () => {
  bigPage.value = 0
  laneCanvases.value = []
  if (showBigModal.value) nextTick().then(() => drawBigMultiLane())
})

watch(bigPage, () => {
  laneCanvases.value = []
  if (showBigModal.value) nextTick().then(() => drawBigMultiLane())
})
</script>

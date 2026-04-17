# BeatFlow 移动端交互优化设计

**日期**: 2026-04-18
**范围**: 项目管理核心页面（列表+详情）+ 文件查看器（FileViewer / SyncViewer / 分享页）
**方案**: 渐进增强 — 桌面端交互不变，移动端叠加手势层和布局调整

---

## 1. 基础设施层

### 1.1 新增依赖

安装 `@vueuse/core`（~18KB gzip），提供：

- `useBreakpoints` — 响应式断点检测
- `useLongPress` — 长按手势识别
- `useSwipe` — 滑动方向识别

### 1.2 移动端检测 Composable

新建 `src/composables/useMobile.ts`：

- 基于 Tailwind 默认断点定义三档：`mobile`（<640px）、`tablet`（640-1023px）、`desktop`（>=1024px）
- 导出 `isMobile`、`isTablet`、`isDesktop` 三个响应式布尔值
- 全局复用，所有需要区分端的组件引入此 composable

### 1.3 Playwright 配置扩展

`playwright.config.ts` 新增三组 project：

| 项目名 | 设备 | 视口 | 触屏 |
|--------|------|------|------|
| `mobile-iphone-se` | iPhone SE | 375x667 | Yes |
| `mobile-iphone-14` | iPhone 14 | 390x844 | Yes |
| `tablet-ipad` | iPad | 768x1024 | Yes |

现有 `desktop-chromium`（1280x900）保持不变。

---

## 2. 通用组件设计

所有新组件放在 `src/components/ui/`，并在 `ComponentTestView.vue` 中添加演示区块。

### 2.1 SwipeAction.vue — 左滑操作栏

**职责**: 包裹任意列表项，支持左滑露出操作按钮区域。

**Props**:
- `actions: Array<{ label: string, icon?: Component, color: string, onClick: () => void }>` — 操作按钮定义
- `threshold?: number` — 滑动阈值，默认 80px
- `maxOffset?: number` — 最大展开距离，默认 140px
- `disabled?: boolean`

**Emits**: `open`, `close`

**特性**:
- 同一父容器内互斥（通过 provide/inject，一个展开时其他自动关闭）
- 桌面端自动禁用（内部用 `useMobile` 判断）
- 支持右滑回弹关闭

**Slots**: 默认 slot 放置列表项内容；`#actions` 具名 slot 可自定义操作区域（覆盖 props 中的 actions）

### 2.2 LongPressMenu.vue — 长按上下文菜单

**职责**: 包裹目标元素，长按后在手指位置弹出上下文菜单。

**Props**:
- `items: Array<{ label: string, icon?: Component, color?: string, disabled?: boolean, onClick: () => void }>`
- `delay?: number` — 长按阈值，默认 500ms
- `disabled?: boolean`

**Emits**: `open`, `close`, `select(item)`

**特性**:
- 菜单用 Teleport 渲染到 body，`nextZIndex()` 管理层级
- 自动计算弹出方向（避免溢出视口）
- 点击外部自动关闭
- 长按时目标元素加 `scale-[0.98]` 视觉反馈
- 桌面端自动禁用

**Slots**: 默认 slot 放置被长按的元素

### 2.3 BottomSheet.vue — 底部滑入面板

**职责**: 移动端替代居中模态框，从底部滑入。

**Props**:
- `modelValue: boolean` — v-model 控制显隐
- `title?: string`
- `height?: string` — 默认 'auto'（自适应内容高度，最大不超过 85vh），可传 '50vh'、'80vh' 等固定值
- `closable?: boolean` — 显示关闭按钮，默认 true

**Emits**: `update:modelValue`

**特性**:
- 背景遮罩 + 点击关闭
- 支持下拉拖拽关闭（拖拽超过 30% 高度释放则关闭）
- `nextZIndex()` 管理层级
- 圆角顶部 + 拖拽指示条

**Slots**: `#header` 自定义头部；默认 slot 放内容

### 2.4 FloatingActionButton.vue (FAB) — 悬浮操作按钮

**职责**: 移动端底部悬浮的圆形操作按钮。

**Props**:
- `icon: Component` — lucide 图标组件
- `label?: string` — 无障碍标签
- `position?: 'bottom-right' | 'bottom-center'` — 默认 bottom-right
- `offset?: { bottom: number, right: number }`

**Emits**: `click`

**特性**:
- 仅移动端/平板显示（`useMobile` 控制），桌面端自动隐藏
- 固定定位 + `nextZIndex()` 层级
- 按下缩放动画反馈

### 2.5 AppModal.vue 改造

- 新增 prop：`mobileMode?: 'center' | 'bottom-sheet'`，默认 `'bottom-sheet'`
- 移动端自动切换为底部滑入（内部复用 BottomSheet 的动画逻辑），平板/桌面保持居中
- 加 `max-w-[calc(100vw-2rem)]` 防溢出
- 向后兼容：不传 `mobileMode` 时默认走底部滑入，传 `'center'` 则所有端都居中

### 2.6 组件依赖关系

```
SwipeAction         --> useMobile (composable)
LongPressMenu       --> useMobile + nextZIndex
BottomSheet         --> nextZIndex + useSwipe (下拉关闭)
FloatingActionButton --> useMobile + nextZIndex
AppModal (改造)      --> useMobile + BottomSheet (动画复用)
```

### 2.7 新增 Composable

**`useBottomToolbar.ts`** — 底部固定工具栏逻辑:
- 管理底部工具栏的显示/隐藏状态
- 滚动向下时自动隐藏（节省空间），滚动向上或停止滚动时显示
- 提供 `isVisible` 响应式状态 + `show()`/`hide()` 方法
- FileViewerView 和 SyncViewerView 共用

---

## 3. 项目列表页（ProjectListView）移动端优化

### 3.1 布局调整

**Header 区域**:
- 创建项目按钮在移动端改为底部悬浮 FAB 按钮（圆形 + 图标），释放顶部空间
- 桌面端保持现有文字按钮 "新建项目"

**筛选栏**:
- 移动端：搜索框独占一行，类型筛选和刷新按钮并排第二行
- 平板/桌面：保持现有水平排列

**项目卡片网格**:
- 现有 `grid-cols-1 sm:grid-cols-2 lg:grid-cols-3` 保持不变
- 移动端卡片操作按钮（编辑/删除）改为左滑呼出（SwipeAction 组件）
- 卡片表面只保留项目名称、描述、公开/私有标签

### 3.2 手势交互

**卡片左滑**（SwipeAction）:
- 左滑超过 80px 阈值后露出操作栏（编辑蓝色 + 删除红色两个色块按钮）
- 最大展开 140px
- 点击其他区域或右滑回弹关闭
- 同一时间只允许一个卡片展开（互斥）

**卡片长按**（LongPressMenu）:
- 500ms 阈值触发
- 弹出上下文菜单：查看详情 / 编辑 / 删除
- 长按时加 `scale-[0.98]` 缩放动画

**桌面端**: 保留现有 hover 显示操作按钮行为，完全不变。

### 3.3 模态框适配

- 创建/编辑/删除模态框加 `max-w-[calc(100vw-2rem)]` 防溢出
- 移动端模态框从底部滑入（AppModal mobileMode='bottom-sheet'）
- 平板/桌面保持居中弹出

---

## 4. 项目详情页（ProjectDetailView）移动端优化

### 4.1 Tab 导航

- 移动端 tab 栏两侧加渐变遮罩（fade-out），暗示内容可滚动
- 内容区域支持 `useSwipe` 左右滑动切换 tab
- tab 切换加 `transition` 滑入动画（左滑：下一个 tab 从右侧滑入；右滑：反之）
- 切换后当前 tab 自动 `scrollIntoView`

### 4.2 Header 区域

- 面包屑：移动端简化为返回箭头 + "项目列表" 文字
- 创建时间/更新时间：移动端只显示更新时间
- 刷新按钮：移动端移到 header 右上角

### 4.3 FileManager（文件管理 Tab）

- 桌面端：保留现有 `group-hover:opacity-100` 操作按钮
- 移动端：左滑呼出操作栏（预览/下载/分享/删除），使用 SwipeAction 组件
- 长按弹出完整上下文菜单（LongPressMenu 组件）
- 上传按钮：移动端改为底部悬浮 FAB（FloatingActionButton 组件）
- 搜索/筛选栏：移动端搜索框独占一行，筛选下拉收纳到漏斗图标按钮

### 4.4 MemberManager（成员管理 Tab）

- 成员行：移动端隐藏日期列（已有 `hidden sm:block`）
- 移除成员按钮：移动端直接显示，用红色文字 "移除"
- 邀请成员模态框：底部滑入式

### 4.5 ProjectSettings（设置 Tab）

- `max-w-xl` 在移动端自然全宽，保持不变
- 删除确认使用 BottomSheet

---

## 5. 文件查看器移动端优化

### 5.1 FileViewerView（单文件查看器）

**波形/音频区域**:
- 波形高度响应式：`h-20 sm:h-24 md:h-[120px]`（80px -> 96px -> 120px）
- 文件图标响应式：`w-14 h-14 sm:w-16 sm:h-16 md:w-20 md:h-20`（56px -> 64px -> 80px）
- 音频播放控制栏：移动端改为底部固定栏，播放按钮 48x48px

**文件信息网格**:
- 移动端：`minmax(150px, 1fr)` 替代 `minmax(200px, 1fr)`

**操作按钮栏**:
- 移动端：收纳到底部固定工具栏（`useBottomToolbar`），与播放控制合并
- 桌面端：保留头部按钮排列

### 5.2 SyncViewerView（同步查看器）

- 轨道波形高度：移动端 60px，桌面端 100px
- 同步控制栏底部固定，滑块全宽
- 轨道列表支持纵向滚动

### 5.3 分享页面（FileShareView / AssociationShareView）

- 波形/播放控制与 FileViewerView 移动端一致
- 头部信息（文件名/项目名/分享者）移动端单行截断

---

## 6. Playwright E2E 测试设计

### 6.1 测试文件结构

```
frontend/e2e/
├── mobile/
│   ├── project-list.mobile.spec.ts
│   ├── project-detail.mobile.spec.ts
│   ├── file-viewer.mobile.spec.ts
│   └── sync-viewer.mobile.spec.ts
├── helpers/
│   └── touch.ts
└── (现有测试文件保持不变)
```

### 6.2 测试工具封装

`e2e/helpers/touch.ts` 封装手势模拟：
- `swipeLeft(page, element, distance)` — 模拟左滑
- `swipeRight(page, element, distance)` — 模拟右滑
- `longPress(page, element, duration)` — 模拟长按
- `swipeDown(page, element, distance)` — 模拟下拉

基于 Playwright 的 `page.touchscreen.tap()` + `dispatchEvent` 组合实现。

### 6.3 项目列表测试（project-list.mobile.spec.ts）

**布局验证**:
- 移动端卡片为单列
- FAB 按钮可见且在视口右下角
- 筛选栏正确堆叠
- iPad 卡片为双列

**手势交互**:
- 左滑卡片 → 操作栏可见（编辑+删除）
- 右滑回弹 → 操作栏关闭
- 互斥：左滑 A → 左滑 B → A 自动关闭
- 长按 600ms → 上下文菜单弹出（查看详情/编辑/删除）

**核心流程**:
- FAB → 底部滑入创建面板 → 填表 → 创建成功
- 左滑 → 删除 → 确认（BottomSheet）→ 卡片消失

### 6.4 项目详情测试（project-detail.mobile.spec.ts）

**Tab 导航**:
- tab 栏可水平滚动（渐变遮罩可见）
- 内容区左滑 → 下一个 tab
- 内容区右滑 → 上一个 tab
- 切换后当前 tab scrollIntoView

**FileManager 手势**:
- 左滑文件项 → 操作栏露出
- 长按文件项 → 上下文菜单
- 桌面视口下手势组件不渲染

**成员管理**: 移动端日期列隐藏，邀请成员使用 BottomSheet

**项目设置**: 删除确认使用 BottomSheet

### 6.5 文件查看器测试（file-viewer.mobile.spec.ts）

- 波形容器高度移动端为 80px
- 底部工具栏可见（播放控制 + 操作按钮）
- 下滚 → 工具栏隐藏；上滚 → 工具栏出现
- 播放按钮可点击

### 6.6 同步查看器测试（sync-viewer.mobile.spec.ts）

- 轨道波形高度 60px
- 同步控制栏底部固定
- 轨道列表可纵向滚动

---

## 7. 文档更新

完成实施后需同步更新：
- `docs/features.md` — 新增通用组件（SwipeAction/LongPressMenu/BottomSheet/FAB）、新增 composables（useMobile/useBottomToolbar）、E2E 测试章节更新
- `docs/architecture.md` — 无 Schema 变更，无需更新

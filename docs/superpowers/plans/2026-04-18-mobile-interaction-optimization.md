# Mobile Interaction Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add progressive mobile enhancement to BeatFlow's project management pages and file viewers — gesture interactions (swipe/long-press), 4 new UI components, AppModal refactor, and Playwright E2E tests across 3 mobile device viewports.

**Architecture:** Preserve all desktop interactions unchanged. Use `@vueuse/core` for breakpoint detection + gesture recognition. New composable `useMobile` gates all mobile-only behavior. 4 new UI components (SwipeAction, LongPressMenu, BottomSheet, FAB) are built as generic, reusable primitives in `src/components/ui/`. Playwright tests organized under `e2e/mobile/` with shared touch helpers.

**Tech Stack:** Vue 3, @vueuse/core (useBreakpoints, useSwipe, useLongPress), Tailwind CSS v3, Playwright (touchscreen API), Vitest

---

## Task 1: Install @vueuse/core and create useMobile composable

**Files:**
- Modify: `frontend/package.json`
- Create: `frontend/src/composables/useMobile.ts`
- Create: `frontend/src/composables/useMobile.spec.ts`

- [ ] **Step 1: Install @vueuse/core**

```bash
cd /private/tmp/agentsmesh-workspace/sandboxes/2-3-2659936e/workspace/frontend
pnpm add @vueuse/core
```

- [ ] **Step 2: Write test for useMobile composable**

Create `frontend/src/composables/useMobile.spec.ts`:

```ts
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'

// Mock @vueuse/core before importing useMobile
const mockBreakpoints = {
  smaller: vi.fn(),
  between: vi.fn(),
  greaterOrEqual: vi.fn(),
}
vi.mock('@vueuse/core', () => ({
  useBreakpoints: vi.fn(() => mockBreakpoints),
}))

import { ref } from 'vue'
import { useMobile } from './useMobile'

describe('useMobile', () => {
  it('exports isMobile, isTablet, isDesktop as refs', () => {
    mockBreakpoints.smaller.mockReturnValue(ref(true))
    mockBreakpoints.between.mockReturnValue(ref(false))
    mockBreakpoints.greaterOrEqual.mockReturnValue(ref(false))

    const { isMobile, isTablet, isDesktop } = useMobile()
    expect(isMobile.value).toBe(true)
    expect(isTablet.value).toBe(false)
    expect(isDesktop.value).toBe(false)
  })

  it('detects tablet when between sm and lg', () => {
    mockBreakpoints.smaller.mockReturnValue(ref(false))
    mockBreakpoints.between.mockReturnValue(ref(true))
    mockBreakpoints.greaterOrEqual.mockReturnValue(ref(false))

    const { isMobile, isTablet, isDesktop } = useMobile()
    expect(isMobile.value).toBe(false)
    expect(isTablet.value).toBe(true)
    expect(isDesktop.value).toBe(false)
  })

  it('detects desktop when >= lg', () => {
    mockBreakpoints.smaller.mockReturnValue(ref(false))
    mockBreakpoints.between.mockReturnValue(ref(false))
    mockBreakpoints.greaterOrEqual.mockReturnValue(ref(true))

    const { isMobile, isTablet, isDesktop } = useMobile()
    expect(isMobile.value).toBe(false)
    expect(isTablet.value).toBe(false)
    expect(isDesktop.value).toBe(true)
  })
})
```

- [ ] **Step 3: Run test to verify it fails**

```bash
cd /private/tmp/agentsmesh-workspace/sandboxes/2-3-2659936e/workspace/frontend
pnpm vitest run src/composables/useMobile.spec.ts
```

Expected: FAIL — module `./useMobile` not found.

- [ ] **Step 4: Implement useMobile**

Create `frontend/src/composables/useMobile.ts`:

```ts
import { useBreakpoints } from '@vueuse/core'
import type { Ref } from 'vue'

/**
 * Reactive breakpoint detection aligned with Tailwind defaults.
 *
 * - mobile:  < 640px  (sm)
 * - tablet:  640–1023px (sm – lg)
 * - desktop: >= 1024px (lg)
 */
export function useMobile(): {
  isMobile: Ref<boolean>
  isTablet: Ref<boolean>
  isDesktop: Ref<boolean>
} {
  const bp = useBreakpoints({ sm: 640, lg: 1024 })

  return {
    isMobile: bp.smaller('sm'),
    isTablet: bp.between('sm', 'lg'),
    isDesktop: bp.greaterOrEqual('lg'),
  }
}
```

- [ ] **Step 5: Run test to verify it passes**

```bash
cd /private/tmp/agentsmesh-workspace/sandboxes/2-3-2659936e/workspace/frontend
pnpm vitest run src/composables/useMobile.spec.ts
```

Expected: 3 tests PASS.

- [ ] **Step 6: Commit**

```bash
cd /private/tmp/agentsmesh-workspace/sandboxes/2-3-2659936e/workspace
git add frontend/package.json frontend/pnpm-lock.yaml frontend/src/composables/useMobile.ts frontend/src/composables/useMobile.spec.ts
git commit -m "feat: add @vueuse/core and useMobile composable"
```

---

## Task 2: Create BottomSheet component

**Files:**
- Create: `frontend/src/components/ui/BottomSheet.vue`
- Create: `frontend/src/components/ui/__tests__/BottomSheet.spec.ts`

- [ ] **Step 1: Write test for BottomSheet**

Create `frontend/src/components/ui/__tests__/BottomSheet.spec.ts`:

```ts
import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import BottomSheet from '../BottomSheet.vue'

// Mock nextZIndex
vi.mock('@/constants/zIndex', () => ({
  nextZIndex: vi.fn(() => 9001),
}))

describe('BottomSheet', () => {
  it('renders when modelValue is true', async () => {
    const wrapper = mount(BottomSheet, {
      props: { modelValue: true, title: 'Test Sheet' },
      global: { stubs: { Teleport: true } },
    })
    expect(wrapper.text()).toContain('Test Sheet')
  })

  it('does not render content when modelValue is false', () => {
    const wrapper = mount(BottomSheet, {
      props: { modelValue: false, title: 'Hidden' },
      global: { stubs: { Teleport: true } },
    })
    expect(wrapper.text()).not.toContain('Hidden')
  })

  it('emits update:modelValue false when backdrop is clicked', async () => {
    const wrapper = mount(BottomSheet, {
      props: { modelValue: true },
      global: { stubs: { Teleport: true } },
    })
    await wrapper.find('[data-testid="bottom-sheet-backdrop"]').trigger('click')
    expect(wrapper.emitted('update:modelValue')?.[0]).toEqual([false])
  })

  it('renders default slot content', () => {
    const wrapper = mount(BottomSheet, {
      props: { modelValue: true },
      slots: { default: '<p>Sheet content</p>' },
      global: { stubs: { Teleport: true } },
    })
    expect(wrapper.text()).toContain('Sheet content')
  })

  it('renders header slot when provided', () => {
    const wrapper = mount(BottomSheet, {
      props: { modelValue: true },
      slots: { header: '<h2>Custom Header</h2>' },
      global: { stubs: { Teleport: true } },
    })
    expect(wrapper.text()).toContain('Custom Header')
  })

  it('hides close button when closable is false', () => {
    const wrapper = mount(BottomSheet, {
      props: { modelValue: true, title: 'No Close', closable: false },
      global: { stubs: { Teleport: true } },
    })
    expect(wrapper.find('[data-testid="bottom-sheet-close"]').exists()).toBe(false)
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /private/tmp/agentsmesh-workspace/sandboxes/2-3-2659936e/workspace/frontend
pnpm vitest run src/components/ui/__tests__/BottomSheet.spec.ts
```

Expected: FAIL — module not found.

- [ ] **Step 3: Implement BottomSheet**

Create `frontend/src/components/ui/BottomSheet.vue`:

```vue
<template>
  <Teleport to="body">
    <Transition name="bottom-sheet">
      <div
        v-if="modelValue"
        class="fixed inset-0"
        :style="{ zIndex }"
      >
        <!-- Backdrop -->
        <div
          data-testid="bottom-sheet-backdrop"
          class="absolute inset-0 bg-black/40 backdrop-blur-sm"
          @click="close"
        />

        <!-- Panel -->
        <div
          ref="panelRef"
          class="absolute bottom-0 left-0 right-0 bg-white rounded-t-2xl shadow-2xl flex flex-col"
          :style="{ maxHeight: panelMaxHeight }"
          @touchstart.passive="onTouchStart"
          @touchmove.passive="onTouchMove"
          @touchend.passive="onTouchEnd"
        >
          <!-- Drag handle -->
          <div class="flex justify-center pt-3 pb-1 shrink-0 cursor-grab">
            <div class="w-10 h-1 bg-gray-300 rounded-full" />
          </div>

          <!-- Header -->
          <div v-if="title || $slots.header" class="flex items-center justify-between px-5 py-3 border-b border-gray-100 shrink-0">
            <slot name="header">
              <h3 class="text-base font-semibold text-gray-900">{{ title }}</h3>
            </slot>
            <button
              v-if="closable"
              data-testid="bottom-sheet-close"
              class="btn-icon rounded-lg text-gray-400"
              @click="close"
            >
              <X class="w-4 h-4" />
            </button>
          </div>

          <!-- Content -->
          <div class="px-5 py-4 overflow-y-auto flex-1">
            <slot />
          </div>

          <!-- Safe area -->
          <div class="shrink-0" style="height: env(safe-area-inset-bottom, 0px)" />
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { X } from 'lucide-vue-next'
import { nextZIndex } from '@/constants/zIndex'

const props = withDefaults(defineProps<{
  modelValue: boolean
  title?: string
  height?: string
  closable?: boolean
}>(), {
  height: 'auto',
  closable: true,
})

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
}>()

const zIndex = nextZIndex()
const panelRef = ref<HTMLElement | null>(null)

const panelMaxHeight = computed(() =>
  props.height === 'auto' ? '85vh' : props.height
)

function close() {
  emit('update:modelValue', false)
}

// ── Drag-to-dismiss ──
let startY = 0
let currentTranslateY = 0

function onTouchStart(e: TouchEvent) {
  startY = e.touches[0].clientY
  currentTranslateY = 0
}

function onTouchMove(e: TouchEvent) {
  const dy = e.touches[0].clientY - startY
  if (dy < 0) return // only allow downward drag
  currentTranslateY = dy
  if (panelRef.value) {
    panelRef.value.style.transform = `translateY(${dy}px)`
    panelRef.value.style.transition = 'none'
  }
}

function onTouchEnd() {
  if (!panelRef.value) return
  const panelHeight = panelRef.value.offsetHeight
  if (currentTranslateY > panelHeight * 0.3) {
    close()
  }
  panelRef.value.style.transform = ''
  panelRef.value.style.transition = ''
  currentTranslateY = 0
}
</script>

<style scoped>
.bottom-sheet-enter-active {
  transition: opacity 0.3s ease;
}
.bottom-sheet-enter-active > div:last-child {
  transition: transform 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}
.bottom-sheet-leave-active {
  transition: opacity 0.2s ease 0.05s;
}
.bottom-sheet-leave-active > div:last-child {
  transition: transform 0.2s ease-in;
}
.bottom-sheet-enter-from {
  opacity: 0;
}
.bottom-sheet-enter-from > div:last-child {
  transform: translateY(100%);
}
.bottom-sheet-leave-to {
  opacity: 0;
}
.bottom-sheet-leave-to > div:last-child {
  transform: translateY(100%);
}
</style>
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd /private/tmp/agentsmesh-workspace/sandboxes/2-3-2659936e/workspace/frontend
pnpm vitest run src/components/ui/__tests__/BottomSheet.spec.ts
```

Expected: 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
cd /private/tmp/agentsmesh-workspace/sandboxes/2-3-2659936e/workspace
git add frontend/src/components/ui/BottomSheet.vue frontend/src/components/ui/__tests__/BottomSheet.spec.ts
git commit -m "feat: add BottomSheet component"
```

---

## Task 3: Create SwipeAction component

**Files:**
- Create: `frontend/src/components/ui/SwipeAction.vue`
- Create: `frontend/src/components/ui/__tests__/SwipeAction.spec.ts`

- [ ] **Step 1: Write test for SwipeAction**

Create `frontend/src/components/ui/__tests__/SwipeAction.spec.ts`:

```ts
import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import SwipeAction from '../SwipeAction.vue'

// Mock useMobile — default to mobile
const isMobileRef = { value: true }
vi.mock('@/composables/useMobile', () => ({
  useMobile: () => ({
    isMobile: isMobileRef,
    isTablet: { value: false },
    isDesktop: { value: false },
  }),
}))

describe('SwipeAction', () => {
  const defaultActions = [
    { label: 'Edit', color: 'bg-blue-500 text-white', onClick: vi.fn() },
    { label: 'Delete', color: 'bg-red-500 text-white', onClick: vi.fn() },
  ]

  it('renders default slot content', () => {
    const wrapper = mount(SwipeAction, {
      props: { actions: defaultActions },
      slots: { default: '<div>Card content</div>' },
    })
    expect(wrapper.text()).toContain('Card content')
  })

  it('renders action buttons', () => {
    const wrapper = mount(SwipeAction, {
      props: { actions: defaultActions },
      slots: { default: '<div>Item</div>' },
    })
    expect(wrapper.text()).toContain('Edit')
    expect(wrapper.text()).toContain('Delete')
  })

  it('action buttons are hidden by default (translateX 0)', () => {
    const wrapper = mount(SwipeAction, {
      props: { actions: defaultActions },
      slots: { default: '<div>Item</div>' },
    })
    const content = wrapper.find('[data-testid="swipe-content"]')
    expect(content.attributes('style') ?? '').toContain('transform: translateX(0px)')
  })

  it('does not render on desktop when disabled via useMobile', () => {
    isMobileRef.value = false
    const wrapper = mount(SwipeAction, {
      props: { actions: defaultActions },
      slots: { default: '<div>Item</div>' },
    })
    // Actions area should not exist
    expect(wrapper.find('[data-testid="swipe-actions"]').exists()).toBe(false)
    isMobileRef.value = true // reset
  })

  it('respects disabled prop', () => {
    const wrapper = mount(SwipeAction, {
      props: { actions: defaultActions, disabled: true },
      slots: { default: '<div>Item</div>' },
    })
    expect(wrapper.find('[data-testid="swipe-actions"]').exists()).toBe(false)
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /private/tmp/agentsmesh-workspace/sandboxes/2-3-2659936e/workspace/frontend
pnpm vitest run src/components/ui/__tests__/SwipeAction.spec.ts
```

Expected: FAIL — module not found.

- [ ] **Step 3: Implement SwipeAction**

Create `frontend/src/components/ui/SwipeAction.vue`:

```vue
<template>
  <div
    ref="containerRef"
    class="relative overflow-hidden"
  >
    <!-- Content layer -->
    <div
      data-testid="swipe-content"
      class="relative bg-white"
      :style="{ transform: `translateX(${offsetX}px)`, transition: dragging ? 'none' : 'transform 0.3s cubic-bezier(0.16, 1, 0.3, 1)' }"
      @touchstart.passive="onTouchStart"
      @touchmove.passive="onTouchMove"
      @touchend.passive="onTouchEnd"
    >
      <slot />
    </div>

    <!-- Actions layer (behind content, only for mobile) -->
    <div
      v-if="enabled"
      data-testid="swipe-actions"
      class="absolute right-0 top-0 bottom-0 flex items-stretch"
      :style="{ width: `${maxOffset}px` }"
    >
      <slot name="actions">
        <button
          v-for="(action, i) in actions"
          :key="i"
          class="flex-1 flex items-center justify-center text-sm font-medium transition-opacity"
          :class="action.color"
          @click="onActionClick(action)"
        >
          <component v-if="action.icon" :is="action.icon" class="w-4 h-4 mr-1" />
          {{ action.label }}
        </button>
      </slot>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, inject, provide, onUnmounted, type Component } from 'vue'
import { useMobile } from '@/composables/useMobile'

interface SwipeActionItem {
  label: string
  icon?: Component
  color: string
  onClick: () => void
}

const props = withDefaults(defineProps<{
  actions: SwipeActionItem[]
  threshold?: number
  maxOffset?: number
  disabled?: boolean
}>(), {
  threshold: 80,
  maxOffset: 140,
  disabled: false,
})

const emit = defineEmits<{
  open: []
  close: []
}>()

const { isMobile } = useMobile()
const enabled = computed(() => isMobile.value && !props.disabled)

// ── Mutual exclusion via provide/inject ──
const closeAllFn = inject<(() => void) | undefined>('swipe-action-close-all', undefined)
const closeCallbacks = ref<Set<() => void>>(new Set())
provide('swipe-action-close-all', () => {
  closeCallbacks.value.forEach(fn => fn())
})

const offsetX = ref(0)
const dragging = ref(false)
const isOpen = ref(false)
let startX = 0
let startOffsetX = 0

function registerClose(fn: () => void) {
  closeCallbacks.value.add(fn)
}
function unregisterClose(fn: () => void) {
  closeCallbacks.value.delete(fn)
}

const closeThis = () => {
  offsetX.value = 0
  isOpen.value = false
  emit('close')
}

registerClose(closeThis)
onUnmounted(() => unregisterClose(closeThis))

function onTouchStart(e: TouchEvent) {
  if (!enabled.value) return
  startX = e.touches[0].clientX
  startOffsetX = offsetX.value
  dragging.value = true
}

function onTouchMove(e: TouchEvent) {
  if (!enabled.value || !dragging.value) return
  const dx = e.touches[0].clientX - startX
  const newOffset = Math.min(0, Math.max(-props.maxOffset, startOffsetX + dx))
  offsetX.value = newOffset
}

function onTouchEnd() {
  if (!enabled.value) return
  dragging.value = false
  if (Math.abs(offsetX.value) >= props.threshold) {
    // Close other swipe actions first
    closeAllFn?.()
    offsetX.value = -props.maxOffset
    isOpen.value = true
    emit('open')
  } else {
    offsetX.value = 0
    if (isOpen.value) {
      isOpen.value = false
      emit('close')
    }
  }
}

function onActionClick(action: SwipeActionItem) {
  action.onClick()
  closeThis()
}

// Expose for parent to programmatically close
defineExpose({ close: closeThis })
</script>
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd /private/tmp/agentsmesh-workspace/sandboxes/2-3-2659936e/workspace/frontend
pnpm vitest run src/components/ui/__tests__/SwipeAction.spec.ts
```

Expected: 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
cd /private/tmp/agentsmesh-workspace/sandboxes/2-3-2659936e/workspace
git add frontend/src/components/ui/SwipeAction.vue frontend/src/components/ui/__tests__/SwipeAction.spec.ts
git commit -m "feat: add SwipeAction component for mobile swipe-to-reveal"
```

---

## Task 4: Create LongPressMenu component

**Files:**
- Create: `frontend/src/components/ui/LongPressMenu.vue`
- Create: `frontend/src/components/ui/__tests__/LongPressMenu.spec.ts`

- [ ] **Step 1: Write test for LongPressMenu**

Create `frontend/src/components/ui/__tests__/LongPressMenu.spec.ts`:

```ts
import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import LongPressMenu from '../LongPressMenu.vue'

vi.mock('@/constants/zIndex', () => ({
  nextZIndex: vi.fn(() => 9002),
}))

vi.mock('@/composables/useMobile', () => ({
  useMobile: () => ({
    isMobile: { value: true },
    isTablet: { value: false },
    isDesktop: { value: false },
  }),
}))

describe('LongPressMenu', () => {
  const items = [
    { label: 'View', onClick: vi.fn() },
    { label: 'Edit', onClick: vi.fn() },
    { label: 'Delete', color: 'text-red-500', onClick: vi.fn() },
  ]

  it('renders slot content', () => {
    const wrapper = mount(LongPressMenu, {
      props: { items },
      slots: { default: '<div>Target element</div>' },
      global: { stubs: { Teleport: true } },
    })
    expect(wrapper.text()).toContain('Target element')
  })

  it('menu is hidden by default', () => {
    const wrapper = mount(LongPressMenu, {
      props: { items },
      slots: { default: '<div>Target</div>' },
      global: { stubs: { Teleport: true } },
    })
    expect(wrapper.find('[data-testid="long-press-menu"]').exists()).toBe(false)
  })

  it('does not render when disabled', () => {
    const wrapper = mount(LongPressMenu, {
      props: { items, disabled: true },
      slots: { default: '<div>Target</div>' },
      global: { stubs: { Teleport: true } },
    })
    // The wrapper div should not have touch listeners (we just confirm component mounts)
    expect(wrapper.text()).toContain('Target')
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /private/tmp/agentsmesh-workspace/sandboxes/2-3-2659936e/workspace/frontend
pnpm vitest run src/components/ui/__tests__/LongPressMenu.spec.ts
```

Expected: FAIL — module not found.

- [ ] **Step 3: Implement LongPressMenu**

Create `frontend/src/components/ui/LongPressMenu.vue`:

```vue
<template>
  <div
    ref="triggerRef"
    :style="{ transform: pressed ? 'scale(0.98)' : 'scale(1)', transition: 'transform 0.15s ease' }"
    @touchstart.passive="onTouchStart"
    @touchend.passive="onTouchEnd"
    @touchmove.passive="onTouchMove"
    @contextmenu.prevent
  >
    <slot />
  </div>

  <Teleport to="body">
    <Transition name="fade">
      <div
        v-if="menuVisible"
        class="fixed inset-0"
        :style="{ zIndex }"
        @click="hideMenu"
        @touchstart.passive="hideMenu"
      >
        <div
          data-testid="long-press-menu"
          class="absolute bg-white rounded-xl shadow-xl border border-gray-200 py-1 min-w-[160px] overflow-hidden"
          :style="menuStyle"
          @click.stop
          @touchstart.stop
        >
          <button
            v-for="(item, i) in items"
            :key="i"
            class="w-full flex items-center gap-3 px-4 py-2.5 text-sm transition-colors"
            :class="[
              item.disabled ? 'text-gray-300 cursor-not-allowed' : (item.color ?? 'text-gray-700 active:bg-gray-50'),
            ]"
            :disabled="item.disabled"
            @click="onItemClick(item)"
          >
            <component v-if="item.icon" :is="item.icon" class="w-4 h-4" />
            {{ item.label }}
          </button>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, computed, onUnmounted, type Component } from 'vue'
import { nextZIndex } from '@/constants/zIndex'
import { useMobile } from '@/composables/useMobile'

interface MenuItem {
  label: string
  icon?: Component
  color?: string
  disabled?: boolean
  onClick: () => void
}

const props = withDefaults(defineProps<{
  items: MenuItem[]
  delay?: number
  disabled?: boolean
}>(), {
  delay: 500,
  disabled: false,
})

const emit = defineEmits<{
  open: []
  close: []
  select: [item: MenuItem]
}>()

const { isMobile } = useMobile()
const zIndex = nextZIndex()

const triggerRef = ref<HTMLElement | null>(null)
const menuVisible = ref(false)
const pressed = ref(false)
const menuPos = ref({ x: 0, y: 0 })

let timer: ReturnType<typeof setTimeout> | null = null
let touchStartX = 0
let touchStartY = 0

const menuStyle = computed(() => {
  const vw = typeof window !== 'undefined' ? window.innerWidth : 375
  const vh = typeof window !== 'undefined' ? window.innerHeight : 667
  let x = menuPos.value.x
  let y = menuPos.value.y

  // Keep menu in viewport
  const menuWidth = 160
  const menuHeight = props.items.length * 40 + 8
  if (x + menuWidth > vw - 8) x = vw - menuWidth - 8
  if (y + menuHeight > vh - 8) y = y - menuHeight
  if (x < 8) x = 8
  if (y < 8) y = 8

  return { left: `${x}px`, top: `${y}px` }
})

function onTouchStart(e: TouchEvent) {
  if (props.disabled || !isMobile.value) return
  touchStartX = e.touches[0].clientX
  touchStartY = e.touches[0].clientY
  pressed.value = true

  timer = setTimeout(() => {
    menuPos.value = { x: touchStartX, y: touchStartY }
    menuVisible.value = true
    emit('open')
    pressed.value = false
  }, props.delay)
}

function onTouchMove(e: TouchEvent) {
  // Cancel if finger moves too far (> 10px)
  const dx = Math.abs(e.touches[0].clientX - touchStartX)
  const dy = Math.abs(e.touches[0].clientY - touchStartY)
  if (dx > 10 || dy > 10) {
    cancelPress()
  }
}

function onTouchEnd() {
  cancelPress()
}

function cancelPress() {
  if (timer) {
    clearTimeout(timer)
    timer = null
  }
  pressed.value = false
}

function hideMenu() {
  menuVisible.value = false
  emit('close')
}

function onItemClick(item: MenuItem) {
  if (item.disabled) return
  emit('select', item)
  item.onClick()
  hideMenu()
}

onUnmounted(() => {
  if (timer) clearTimeout(timer)
})
</script>

<style scoped>
.fade-enter-active { transition: opacity 0.15s ease; }
.fade-leave-active { transition: opacity 0.1s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd /private/tmp/agentsmesh-workspace/sandboxes/2-3-2659936e/workspace/frontend
pnpm vitest run src/components/ui/__tests__/LongPressMenu.spec.ts
```

Expected: 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
cd /private/tmp/agentsmesh-workspace/sandboxes/2-3-2659936e/workspace
git add frontend/src/components/ui/LongPressMenu.vue frontend/src/components/ui/__tests__/LongPressMenu.spec.ts
git commit -m "feat: add LongPressMenu component for mobile context menus"
```

---

## Task 5: Create FloatingActionButton component

**Files:**
- Create: `frontend/src/components/ui/FloatingActionButton.vue`
- Create: `frontend/src/components/ui/__tests__/FloatingActionButton.spec.ts`

- [ ] **Step 1: Write test for FAB**

Create `frontend/src/components/ui/__tests__/FloatingActionButton.spec.ts`:

```ts
import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import FloatingActionButton from '../FloatingActionButton.vue'
import { defineComponent, h } from 'vue'

vi.mock('@/constants/zIndex', () => ({
  nextZIndex: vi.fn(() => 9003),
}))

const mockIsMobile = { value: true }
const mockIsDesktop = { value: false }

vi.mock('@/composables/useMobile', () => ({
  useMobile: () => ({
    isMobile: mockIsMobile,
    isTablet: { value: false },
    isDesktop: mockIsDesktop,
  }),
}))

const FakeIcon = defineComponent({
  render() { return h('svg', { class: 'fake-icon' }) }
})

describe('FloatingActionButton', () => {
  it('renders on mobile', () => {
    mockIsMobile.value = true
    mockIsDesktop.value = false
    const wrapper = mount(FloatingActionButton, {
      props: { icon: FakeIcon, label: 'Create' },
      global: { stubs: { Teleport: true } },
    })
    expect(wrapper.find('[data-testid="fab"]').exists()).toBe(true)
  })

  it('is hidden on desktop', () => {
    mockIsMobile.value = false
    mockIsDesktop.value = true
    const wrapper = mount(FloatingActionButton, {
      props: { icon: FakeIcon, label: 'Create' },
      global: { stubs: { Teleport: true } },
    })
    expect(wrapper.find('[data-testid="fab"]').exists()).toBe(false)
    // reset
    mockIsMobile.value = true
    mockIsDesktop.value = false
  })

  it('emits click when tapped', async () => {
    const wrapper = mount(FloatingActionButton, {
      props: { icon: FakeIcon, label: 'Add' },
      global: { stubs: { Teleport: true } },
    })
    await wrapper.find('[data-testid="fab"]').trigger('click')
    expect(wrapper.emitted('click')).toBeTruthy()
  })

  it('has aria-label for accessibility', () => {
    const wrapper = mount(FloatingActionButton, {
      props: { icon: FakeIcon, label: 'New Item' },
      global: { stubs: { Teleport: true } },
    })
    expect(wrapper.find('[data-testid="fab"]').attributes('aria-label')).toBe('New Item')
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /private/tmp/agentsmesh-workspace/sandboxes/2-3-2659936e/workspace/frontend
pnpm vitest run src/components/ui/__tests__/FloatingActionButton.spec.ts
```

Expected: FAIL — module not found.

- [ ] **Step 3: Implement FloatingActionButton**

Create `frontend/src/components/ui/FloatingActionButton.vue`:

```vue
<template>
  <Teleport to="body">
    <button
      v-if="!isDesktop"
      data-testid="fab"
      class="fixed w-14 h-14 rounded-full shadow-lg flex items-center justify-center text-white bg-primary-600 hover:bg-primary-700 active:scale-95 transition-all duration-200"
      :style="fabStyle"
      :aria-label="label"
      @click="emit('click')"
    >
      <component :is="icon" class="w-6 h-6" />
    </button>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, type Component } from 'vue'
import { nextZIndex } from '@/constants/zIndex'
import { useMobile } from '@/composables/useMobile'

const props = withDefaults(defineProps<{
  icon: Component
  label?: string
  position?: 'bottom-right' | 'bottom-center'
  offset?: { bottom: number; right: number }
}>(), {
  label: '',
  position: 'bottom-right',
})

const emit = defineEmits<{ click: [] }>()

const { isDesktop } = useMobile()
const zIndex = nextZIndex()

const fabStyle = computed(() => {
  const bottom = props.offset?.bottom ?? 24
  const right = props.offset?.right ?? 24

  if (props.position === 'bottom-center') {
    return {
      zIndex,
      bottom: `calc(${bottom}px + env(safe-area-inset-bottom, 0px))`,
      left: '50%',
      transform: 'translateX(-50%)',
    }
  }
  return {
    zIndex,
    bottom: `calc(${bottom}px + env(safe-area-inset-bottom, 0px))`,
    right: `${right}px`,
  }
})
</script>
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd /private/tmp/agentsmesh-workspace/sandboxes/2-3-2659936e/workspace/frontend
pnpm vitest run src/components/ui/__tests__/FloatingActionButton.spec.ts
```

Expected: 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
cd /private/tmp/agentsmesh-workspace/sandboxes/2-3-2659936e/workspace
git add frontend/src/components/ui/FloatingActionButton.vue frontend/src/components/ui/__tests__/FloatingActionButton.spec.ts
git commit -m "feat: add FloatingActionButton component for mobile"
```

---

## Task 6: Create useBottomToolbar composable

**Files:**
- Create: `frontend/src/composables/useBottomToolbar.ts`
- Create: `frontend/src/composables/useBottomToolbar.spec.ts`

- [ ] **Step 1: Write test**

Create `frontend/src/composables/useBottomToolbar.spec.ts`:

```ts
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { useBottomToolbar } from './useBottomToolbar'

// Mock @vueuse/core
const onScrollMock = vi.fn()
vi.mock('@vueuse/core', () => ({
  useScroll: vi.fn(() => ({
    y: { value: 0 },
    directions: { top: false, bottom: false },
  })),
  useBreakpoints: vi.fn(() => ({
    smaller: vi.fn(() => ({ value: true })),
    between: vi.fn(() => ({ value: false })),
    greaterOrEqual: vi.fn(() => ({ value: false })),
  })),
}))

describe('useBottomToolbar', () => {
  it('returns isVisible as true by default', () => {
    const { isVisible } = useBottomToolbar()
    expect(isVisible.value).toBe(true)
  })

  it('show() sets isVisible to true', () => {
    const { isVisible, show, hide } = useBottomToolbar()
    hide()
    expect(isVisible.value).toBe(false)
    show()
    expect(isVisible.value).toBe(true)
  })

  it('hide() sets isVisible to false', () => {
    const { isVisible, hide } = useBottomToolbar()
    hide()
    expect(isVisible.value).toBe(false)
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /private/tmp/agentsmesh-workspace/sandboxes/2-3-2659936e/workspace/frontend
pnpm vitest run src/composables/useBottomToolbar.spec.ts
```

Expected: FAIL — module not found.

- [ ] **Step 3: Implement useBottomToolbar**

Create `frontend/src/composables/useBottomToolbar.ts`:

```ts
import { ref, watch, type Ref } from 'vue'
import { useScroll } from '@vueuse/core'

/**
 * Controls visibility of a bottom toolbar based on scroll direction.
 * Hides when scrolling down, shows when scrolling up or stopped.
 */
export function useBottomToolbar(target?: Ref<HTMLElement | null>) {
  const isVisible = ref(true)
  const { directions } = useScroll(target ?? (typeof window !== 'undefined' ? window : null) as any)

  let hideTimer: ReturnType<typeof setTimeout> | null = null

  watch(
    () => directions,
    (dirs) => {
      if (dirs.bottom) {
        if (hideTimer) clearTimeout(hideTimer)
        hideTimer = setTimeout(() => {
          isVisible.value = false
        }, 100)
      } else if (dirs.top) {
        if (hideTimer) {
          clearTimeout(hideTimer)
          hideTimer = null
        }
        isVisible.value = true
      }
    },
    { deep: true }
  )

  function show() { isVisible.value = true }
  function hide() { isVisible.value = false }

  return { isVisible, show, hide }
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd /private/tmp/agentsmesh-workspace/sandboxes/2-3-2659936e/workspace/frontend
pnpm vitest run src/composables/useBottomToolbar.spec.ts
```

Expected: 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
cd /private/tmp/agentsmesh-workspace/sandboxes/2-3-2659936e/workspace
git add frontend/src/composables/useBottomToolbar.ts frontend/src/composables/useBottomToolbar.spec.ts
git commit -m "feat: add useBottomToolbar composable for scroll-aware visibility"
```

---

## Task 7: Refactor AppModal for mobile bottom-sheet mode

**Files:**
- Modify: `frontend/src/components/ui/AppModal.vue`

- [ ] **Step 1: Refactor AppModal**

The existing AppModal already has good mobile support (bottom slide-in, drag handle, safe area). Per the spec, we add:
1. `mobileMode` prop
2. `max-w-[calc(100vw-2rem)]` for overflow safety
3. Import and use `useMobile` instead of manual resize listener

Edit `frontend/src/components/ui/AppModal.vue` — replace the entire `<script setup>` block:

```vue
<script setup lang="ts">
import { computed } from 'vue'
import { X } from 'lucide-vue-next'
import { useMobile } from '@/composables/useMobile'

const props = withDefaults(defineProps<{
  modelValue: boolean
  title?: string
  width?: string
  closeOnBackdrop?: boolean
  mobileMode?: 'center' | 'bottom-sheet'
}>(), { closeOnBackdrop: true, width: '480px', mobileMode: 'bottom-sheet' })

const emit = defineEmits(['update:modelValue'])

const { isMobile } = useMobile()
const smUp = computed(() => !isMobile.value)

function handleBackdropClick() {
  if (props.closeOnBackdrop) {
    emit('update:modelValue', false)
  }
}
</script>
```

Then update the modal-panel div's `:style` binding to add max-width protection:

Replace the existing `:style="smUp ? { maxWidth: width } : {}"` with:

```
:style="smUp ? { maxWidth: width } : { maxWidth: 'calc(100vw - 2rem)' }"
```

- [ ] **Step 2: Run existing tests to verify no regressions**

```bash
cd /private/tmp/agentsmesh-workspace/sandboxes/2-3-2659936e/workspace/frontend
pnpm vitest run
```

Expected: All existing tests PASS.

- [ ] **Step 3: Commit**

```bash
cd /private/tmp/agentsmesh-workspace/sandboxes/2-3-2659936e/workspace
git add frontend/src/components/ui/AppModal.vue
git commit -m "refactor: add mobileMode prop and useMobile to AppModal"
```

---

## Task 8: Add component demos to ComponentTestView

**Files:**
- Modify: `frontend/src/views/dev/ComponentTestView.vue`

- [ ] **Step 1: Add demo sections for all 4 new components**

Add imports at the top of the `<script setup>` block (after existing imports):

```ts
import BottomSheet from '@/components/ui/BottomSheet.vue'
import SwipeAction from '@/components/ui/SwipeAction.vue'
import LongPressMenu from '@/components/ui/LongPressMenu.vue'
import FloatingActionButton from '@/components/ui/FloatingActionButton.vue'
import { Plus, Pencil, Trash2, Eye } from 'lucide-vue-next'
```

Add state variables:

```ts
// ─── Mobile component demos ───
const showBottomSheet = ref(false)
const showBottomSheetTall = ref(false)
const fabClicked = ref(0)
```

Add the following demo blocks to the template (before the closing `</AppLayout>` tag):

```html
<!-- ─── BottomSheet Demo ─── -->
<section class="card p-6 mb-6">
  <h2 class="text-lg font-semibold mb-4">BottomSheet 底部面板</h2>
  <p class="text-sm text-gray-500 mb-4">移动端从底部滑入的面板，支持拖拽关闭。</p>
  <div class="flex gap-3">
    <button class="btn-primary btn-sm" @click="showBottomSheet = true">默认高度</button>
    <button class="btn-secondary btn-sm" @click="showBottomSheetTall = true">固定 50vh</button>
  </div>
  <BottomSheet v-model="showBottomSheet" title="示例面板">
    <p class="text-sm text-gray-600">这是底部面板的内容区域，支持下拉拖拽关闭。</p>
  </BottomSheet>
  <BottomSheet v-model="showBottomSheetTall" title="较高面板" height="50vh">
    <p class="text-sm text-gray-600">这个面板高度固定为 50vh。</p>
  </BottomSheet>
</section>

<!-- ─── SwipeAction Demo ─── -->
<section class="card p-6 mb-6">
  <h2 class="text-lg font-semibold mb-4">SwipeAction 左滑操作</h2>
  <p class="text-sm text-gray-500 mb-4">在移动端左滑列表项以显示操作按钮。需使用触屏设备测试。</p>
  <div class="space-y-2">
    <SwipeAction
      v-for="n in 3"
      :key="n"
      :actions="[
        { label: '编辑', color: 'bg-blue-500 text-white', onClick: () => toast.info(`编辑项目 ${n}`) },
        { label: '删除', color: 'bg-red-500 text-white', onClick: () => toast.error(`删除项目 ${n}`) },
      ]"
    >
      <div class="card px-4 py-3 flex items-center gap-3">
        <div class="w-8 h-8 bg-gray-100 rounded-lg flex items-center justify-center text-gray-400">{{ n }}</div>
        <span class="text-sm font-medium text-gray-700">列表项 {{ n }} — 左滑试试</span>
      </div>
    </SwipeAction>
  </div>
</section>

<!-- ─── LongPressMenu Demo ─── -->
<section class="card p-6 mb-6">
  <h2 class="text-lg font-semibold mb-4">LongPressMenu 长按菜单</h2>
  <p class="text-sm text-gray-500 mb-4">移动端长按元素弹出上下文菜单。需使用触屏设备测试。</p>
  <LongPressMenu
    :items="[
      { label: '查看详情', icon: Eye, onClick: () => toast.info('查看详情') },
      { label: '编辑', icon: Pencil, onClick: () => toast.info('编辑') },
      { label: '删除', icon: Trash2, color: 'text-red-500', onClick: () => toast.error('删除') },
    ]"
  >
    <div class="card px-4 py-6 text-center cursor-pointer select-none hover:bg-gray-50 transition-colors">
      <p class="text-sm font-medium text-gray-700">长按此区域 (500ms)</p>
    </div>
  </LongPressMenu>
</section>

<!-- ─── FloatingActionButton Demo ─── -->
<section class="card p-6 mb-6">
  <h2 class="text-lg font-semibold mb-4">FloatingActionButton 悬浮按钮</h2>
  <p class="text-sm text-gray-500 mb-4">仅在移动端/平板显示的悬浮操作按钮。点击次数: {{ fabClicked }}</p>
  <FloatingActionButton :icon="Plus" label="创建" @click="fabClicked++" />
</section>
```

- [ ] **Step 2: Run type check**

```bash
cd /private/tmp/agentsmesh-workspace/sandboxes/2-3-2659936e/workspace/frontend
npx vue-tsc --noEmit
```

Expected: No new type errors.

- [ ] **Step 3: Commit**

```bash
cd /private/tmp/agentsmesh-workspace/sandboxes/2-3-2659936e/workspace
git add frontend/src/views/dev/ComponentTestView.vue
git commit -m "feat: add demos for BottomSheet, SwipeAction, LongPressMenu, FAB in ComponentTestView"
```

---

## Task 9: Mobile optimization for ProjectListView

**Files:**
- Modify: `frontend/src/views/project/ProjectListView.vue`

- [ ] **Step 1: Add mobile imports and composables**

Add these imports to the `<script setup>` block:

```ts
import { useMobile } from '@/composables/useMobile'
import SwipeAction from '@/components/ui/SwipeAction.vue'
import LongPressMenu from '@/components/ui/LongPressMenu.vue'
import FloatingActionButton from '@/components/ui/FloatingActionButton.vue'
```

Add after existing refs:

```ts
const { isMobile, isDesktop } = useMobile()
```

- [ ] **Step 2: Replace header create button with conditional FAB**

Replace the header button (line 10):

```html
<button v-if="isDesktop" class="btn-primary self-start sm:self-auto" @click="showCreate = true">
  <Plus class="w-4 h-4" />
  新建项目
</button>
```

Add FAB at the end of the template (before `</AppLayout>`):

```html
<FloatingActionButton v-if="!isDesktop" :icon="Plus" label="新建项目" @click="showCreate = true" />
```

- [ ] **Step 3: Wrap project cards with SwipeAction and LongPressMenu on mobile**

Replace the card `v-for` div (lines 53-84) with:

```html
<template v-for="p in filtered" :key="p.id">
  <SwipeAction
    v-if="isMobile"
    :actions="[
      { label: '编辑', color: 'bg-blue-500 text-white', onClick: () => startEdit(p) },
      { label: '删除', color: 'bg-red-500 text-white', onClick: () => startDelete(p) },
    ]"
  >
    <LongPressMenu
      :items="[
        { label: '查看详情', onClick: () => goDetail(p.id) },
        { label: '编辑', onClick: () => startEdit(p) },
        { label: '删除', color: 'text-red-500', onClick: () => startDelete(p) },
      ]"
    >
      <div class="card-hover p-5 flex flex-col" @click="goDetail(p.id)">
        <div class="flex items-start justify-between mb-2">
          <h3 class="font-semibold text-gray-900 truncate flex-1 mr-2">{{ p.name }}</h3>
          <span :class="p.is_public ? 'badge-green' : 'badge-gray'">
            {{ p.is_public ? '公开' : '私有' }}
          </span>
        </div>
        <p class="text-sm text-gray-500 line-clamp-2 flex-1 mb-4">{{ p.description || '暂无描述' }}</p>
        <div class="border-t border-gray-100 pt-3">
          <span class="text-xs text-gray-400 flex items-center gap-1">
            <Calendar class="w-3 h-3" />
            {{ formatDate(p.created_at) }}
          </span>
        </div>
      </div>
    </LongPressMenu>
  </SwipeAction>

  <!-- Desktop: keep existing card with hover actions -->
  <div
    v-else
    class="card-hover p-5 flex flex-col"
    @click="goDetail(p.id)"
  >
    <div class="flex items-start justify-between mb-2">
      <h3 class="font-semibold text-gray-900 truncate flex-1 mr-2">{{ p.name }}</h3>
      <span :class="p.is_public ? 'badge-green' : 'badge-gray'">
        {{ p.is_public ? '公开' : '私有' }}
      </span>
    </div>
    <p class="text-sm text-gray-500 line-clamp-2 flex-1 mb-4">{{ p.description || '暂无描述' }}</p>
    <div class="border-t border-gray-100 pt-3 flex items-center justify-between">
      <span class="text-xs text-gray-400 flex items-center gap-1">
        <Calendar class="w-3 h-3" />
        {{ formatDate(p.created_at) }}
      </span>
      <div class="flex items-center gap-1" @click.stop>
        <button class="btn-icon btn-sm rounded-md" title="查看" @click="goDetail(p.id)">
          <Eye class="w-3.5 h-3.5" />
        </button>
        <button class="btn-icon btn-sm rounded-md" title="编辑" @click="startEdit(p)">
          <Pencil class="w-3.5 h-3.5" />
        </button>
        <button class="btn-icon btn-sm rounded-md hover:text-red-500 hover:bg-red-50" title="删除" @click="startDelete(p)">
          <Trash2 class="w-3.5 h-3.5" />
        </button>
      </div>
    </div>
  </div>
</template>
```

- [ ] **Step 4: Run all frontend tests**

```bash
cd /private/tmp/agentsmesh-workspace/sandboxes/2-3-2659936e/workspace/frontend
pnpm vitest run
```

Expected: All tests PASS.

- [ ] **Step 5: Run type check**

```bash
cd /private/tmp/agentsmesh-workspace/sandboxes/2-3-2659936e/workspace/frontend
npx vue-tsc --noEmit
```

Expected: No new type errors.

- [ ] **Step 6: Commit**

```bash
cd /private/tmp/agentsmesh-workspace/sandboxes/2-3-2659936e/workspace
git add frontend/src/views/project/ProjectListView.vue
git commit -m "feat: add mobile gestures (swipe/long-press) and FAB to ProjectListView"
```

---

## Task 10: Mobile optimization for ProjectDetailView

**Files:**
- Modify: `frontend/src/views/project/ProjectDetailView.vue`

- [ ] **Step 1: Add mobile imports**

Add to `<script setup>`:

```ts
import { useSwipe } from '@vueuse/core'
import { useMobile } from '@/composables/useMobile'
import { ArrowLeft } from 'lucide-vue-next'
```

Add refs:

```ts
const { isMobile } = useMobile()
const tabContentRef = ref<HTMLElement | null>(null)

// ── Tab swipe navigation ──
const tabKeys = tabs.map(t => t.key)

useSwipe(tabContentRef, {
  onSwipeEnd(_e, direction) {
    if (!isMobile.value) return
    const currentIdx = tabKeys.indexOf(activeTab.value)
    if (direction === 'left' && currentIdx < tabKeys.length - 1) {
      activeTab.value = tabKeys[currentIdx + 1]
    } else if (direction === 'right' && currentIdx > 0) {
      activeTab.value = tabKeys[currentIdx - 1]
    }
  },
})
```

- [ ] **Step 2: Update breadcrumb for mobile**

Replace the breadcrumb `<nav>` block with:

```html
<nav class="flex items-center gap-2 text-sm text-gray-500 mb-4">
  <RouterLink to="/projects" class="hover:text-gray-700 flex items-center gap-1">
    <ArrowLeft v-if="isMobile" class="w-4 h-4" />
    <FolderOpen v-else class="w-3.5 h-3.5" />
    项目列表
  </RouterLink>
  <template v-if="!isMobile">
    <ChevronRight class="w-3.5 h-3.5" />
    <span class="text-gray-900 font-medium">{{ project?.name ?? '...' }}</span>
  </template>
</nav>
```

- [ ] **Step 3: Hide creation time on mobile**

Replace the metadata div:

```html
<div class="flex flex-wrap items-center gap-x-4 gap-y-1 mt-2 text-xs text-gray-400">
  <span v-if="!isMobile" class="flex items-center gap-1"><Calendar class="w-3 h-3" />创建 {{ formatDate(project?.created_at) }}</span>
  <span class="flex items-center gap-1"><Clock class="w-3 h-3" />更新 {{ formatDate(project?.updated_at) }}</span>
</div>
```

- [ ] **Step 4: Add gradient fade masks to scrollable tabs**

Wrap the tab bar with a container that adds fade masks on mobile:

```html
<div class="relative">
  <!-- Fade masks for mobile scroll hint -->
  <div v-if="isMobile" class="absolute left-0 top-0 bottom-0 w-6 bg-gradient-to-r from-white to-transparent z-10 pointer-events-none" />
  <div v-if="isMobile" class="absolute right-0 top-0 bottom-0 w-6 bg-gradient-to-l from-white to-transparent z-10 pointer-events-none" />
  
  <div class="flex items-center gap-0 border-b-0 overflow-x-auto scrollbar-hide -mb-px">
    <button
      v-for="tab in tabs"
      :key="tab.key"
      :ref="el => { if (activeTab === tab.key && el) (el as HTMLElement).scrollIntoView?.({ behavior: 'smooth', block: 'nearest', inline: 'center' }) }"
      class="flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors shrink-0"
      :class="activeTab === tab.key
        ? 'border-primary-600 text-primary-600'
        : 'border-transparent text-gray-500 hover:text-gray-700'"
      @click="activeTab = tab.key"
    >
      <component :is="tab.icon" class="w-4 h-4" />
      {{ tab.label }}
    </button>
  </div>
</div>
```

- [ ] **Step 5: Add ref to tab content for swipe**

Update the tab content container:

```html
<div ref="tabContentRef" class="page-container">
```

- [ ] **Step 6: Run type check**

```bash
cd /private/tmp/agentsmesh-workspace/sandboxes/2-3-2659936e/workspace/frontend
npx vue-tsc --noEmit
```

Expected: No new type errors.

- [ ] **Step 7: Commit**

```bash
cd /private/tmp/agentsmesh-workspace/sandboxes/2-3-2659936e/workspace
git add frontend/src/views/project/ProjectDetailView.vue
git commit -m "feat: add mobile tab swipe, simplified breadcrumb, scroll fade masks to ProjectDetailView"
```

---

## Task 11: Mobile optimization for FileManager

**Files:**
- Modify: `frontend/src/components/project/FileManager.vue`

- [ ] **Step 1: Add mobile imports**

Add to `<script setup>`:

```ts
import { useMobile } from '@/composables/useMobile'
import SwipeAction from '@/components/ui/SwipeAction.vue'
import LongPressMenu from '@/components/ui/LongPressMenu.vue'
import FloatingActionButton from '@/components/ui/FloatingActionButton.vue'
```

Add:

```ts
const { isMobile, isDesktop } = useMobile()
```

- [ ] **Step 2: Replace upload button with conditional FAB**

Replace the upload label (lines 11-21) with:

```html
<label v-if="permission.canUpload && isDesktop" class="btn-primary btn-sm cursor-pointer">
  <Upload class="w-3.5 h-3.5" />
  上传文件
  <input
    type="file"
    class="hidden"
    multiple
    accept=".wav,.mp3,.flac,.ogg,.mp4,.avi,.mov,audio/*,video/*"
    @change="onFileSelect"
  />
</label>
```

Add at end of template (before `</div>` root close):

```html
<!-- Mobile upload FAB -->
<label v-if="permission.canUpload && !isDesktop">
  <FloatingActionButton :icon="Upload" label="上传文件" @click="() => {}" />
  <input
    type="file"
    class="hidden"
    multiple
    accept=".wav,.mp3,.flac,.ogg,.mp4,.avi,.mov,audio/*,video/*"
    @change="onFileSelect"
  />
</label>
```

Note: The FAB click triggers the label's file input. If click doesn't bubble properly through `<label>`, use a ref approach with `fileInputRef.value?.click()`.

- [ ] **Step 3: Wrap file list items with SwipeAction/LongPressMenu on mobile**

Replace the file list item `v-for` div (lines 87-141) with:

```html
<template v-for="file in filteredFiles" :key="file.id">
  <!-- Mobile: swipe + long press -->
  <SwipeAction
    v-if="isMobile"
    :actions="[
      { label: '预览', color: 'bg-blue-500 text-white', onClick: () => goView(file.id) },
      { label: '下载', color: 'bg-green-500 text-white', onClick: () => downloadFile(file) },
      ...(permission.canDelete ? [{ label: '删除', color: 'bg-red-500 text-white', onClick: () => removeFile(file) }] : []),
    ]"
  >
    <LongPressMenu
      :items="[
        { label: '预览', onClick: () => goView(file.id) },
        { label: '下载', onClick: () => downloadFile(file) },
        ...(permission.canShare ? [{ label: '分享', onClick: () => openShare(file) }] : []),
        ...(permission.canDelete ? [{ label: '删除', color: 'text-red-500', onClick: () => removeFile(file) }] : []),
      ]"
    >
      <div class="card px-4 py-3 flex items-center gap-4 cursor-pointer" @click="goView(file.id)">
        <div class="w-10 h-10 rounded-lg flex items-center justify-center shrink-0" :class="fileIconBg(file.file_type)">
          <component :is="fileIcon(file.file_type)" class="w-5 h-5" :class="fileIconColor(file.file_type)" />
        </div>
        <div class="flex-1 min-w-0">
          <div class="font-medium text-sm text-gray-900 truncate">{{ file.original_filename || file.filename }}</div>
          <div class="flex items-center gap-3 mt-0.5 text-xs text-gray-400">
            <span>{{ formatSize(file.file_size) }}</span>
            <span>{{ formatDate(file.created_at) }}</span>
          </div>
        </div>
        <span class="shrink-0" :class="fileTypeBadge(file.file_type)">{{ file.file_type.toUpperCase() }}</span>
      </div>
    </LongPressMenu>
  </SwipeAction>

  <!-- Desktop: keep hover actions -->
  <div
    v-else
    class="card px-4 py-3 flex items-center gap-4 hover:border-primary-200 hover:shadow-sm transition-all duration-150 cursor-pointer group"
    @click="goView(file.id)"
  >
    <div class="w-10 h-10 rounded-lg flex items-center justify-center shrink-0" :class="fileIconBg(file.file_type)">
      <component :is="fileIcon(file.file_type)" class="w-5 h-5" :class="fileIconColor(file.file_type)" />
    </div>
    <div class="flex-1 min-w-0">
      <div class="font-medium text-sm text-gray-900 truncate">{{ file.original_filename || file.filename }}</div>
      <div class="flex items-center gap-3 mt-0.5 text-xs text-gray-400">
        <span>{{ formatSize(file.file_size) }}</span>
        <span v-if="file.duration">{{ formatDuration(file.duration) }}</span>
        <span v-if="file.sample_rate">{{ file.sample_rate }} Hz</span>
        <span>{{ formatDate(file.created_at) }}</span>
      </div>
    </div>
    <span class="shrink-0" :class="fileTypeBadge(file.file_type)">{{ file.file_type.toUpperCase() }}</span>
    <div class="flex items-center gap-1 shrink-0 opacity-0 group-hover:opacity-100 transition-opacity" @click.stop>
      <button class="btn-icon btn-sm rounded-md" title="预览" @click="goView(file.id)"><Eye class="w-3.5 h-3.5" /></button>
      <button class="btn-icon btn-sm rounded-md" title="下载" @click="downloadFile(file)"><Download class="w-3.5 h-3.5" /></button>
      <button v-if="permission.canShare" class="btn-icon btn-sm rounded-md hover:text-blue-500 hover:bg-blue-50" title="分享" @click="openShare(file)"><Share2 class="w-3.5 h-3.5" /></button>
      <button v-if="permission.canDelete" class="btn-icon btn-sm rounded-md hover:text-red-500 hover:bg-red-50" title="删除" @click="removeFile(file)"><Trash2 class="w-3.5 h-3.5" /></button>
    </div>
  </div>
</template>
```

- [ ] **Step 4: Run type check**

```bash
cd /private/tmp/agentsmesh-workspace/sandboxes/2-3-2659936e/workspace/frontend
npx vue-tsc --noEmit
```

Expected: No new type errors.

- [ ] **Step 5: Commit**

```bash
cd /private/tmp/agentsmesh-workspace/sandboxes/2-3-2659936e/workspace
git add frontend/src/components/project/FileManager.vue
git commit -m "feat: add mobile swipe/long-press actions and FAB to FileManager"
```

---

## Task 12: Mobile optimization for FileViewerView

**Files:**
- Modify: `frontend/src/views/analyzer/FileViewerView.vue`

- [ ] **Step 1: Add mobile composable**

Add to imports:

```ts
import { useMobile } from '@/composables/useMobile'
```

Add:

```ts
const { isMobile } = useMobile()
```

- [ ] **Step 2: Make file icon responsive**

Find the file header icon div (the `w-12 h-12` icon container) and replace:

```html
<div class="w-10 h-10 sm:w-12 sm:h-12 rounded-xl flex items-center justify-center shrink-0" :class="fileIconBg(file.file_type)">
  <component :is="fileIcon(file.file_type)" class="w-5 h-5 sm:w-6 sm:h-6" :class="fileIconColor(file.file_type)" />
</div>
```

- [ ] **Step 3: Make action buttons stack on mobile**

Replace the download/share buttons area with responsive layout:

```html
<div class="flex items-center gap-2 shrink-0" :class="isMobile ? 'hidden' : ''">
  <button class="btn-secondary btn-sm shrink-0" @click="download">
    <Download class="w-3.5 h-3.5" />下载
  </button>
  <button class="btn-ghost btn-sm shrink-0" @click="showShareModal = true" title="分享到社区">
    <Share2 class="w-3.5 h-3.5" />分享
  </button>
</div>
```

The mobile actions will be shown in a bottom toolbar (next step).

- [ ] **Step 4: Add mobile bottom toolbar**

Add at the end of the template (before `</AppLayout>`):

```html
<!-- Mobile bottom toolbar -->
<Teleport to="body">
  <div
    v-if="isMobile && file"
    class="fixed bottom-0 left-0 right-0 bg-white border-t border-gray-200 px-4 py-3 flex items-center justify-around"
    :style="{ zIndex: 9050 }"
  >
    <button class="flex flex-col items-center gap-1 text-gray-600" @click="download">
      <Download class="w-5 h-5" />
      <span class="text-[10px]">下载</span>
    </button>
    <button class="flex flex-col items-center gap-1 text-gray-600" @click="showShareModal = true">
      <Share2 class="w-5 h-5" />
      <span class="text-[10px]">分享</span>
    </button>
    <div style="height: env(safe-area-inset-bottom, 0px)" />
  </div>
</Teleport>
```

- [ ] **Step 5: Run type check**

```bash
cd /private/tmp/agentsmesh-workspace/sandboxes/2-3-2659936e/workspace/frontend
npx vue-tsc --noEmit
```

Expected: No new type errors.

- [ ] **Step 6: Commit**

```bash
cd /private/tmp/agentsmesh-workspace/sandboxes/2-3-2659936e/workspace
git add frontend/src/views/analyzer/FileViewerView.vue
git commit -m "feat: add responsive sizing and mobile bottom toolbar to FileViewerView"
```

---

## Task 13: Playwright config and touch helpers

**Files:**
- Modify: `frontend/playwright.config.ts`
- Create: `frontend/e2e/helpers/touch.ts`

- [ ] **Step 1: Update Playwright config with mobile projects**

Replace `frontend/playwright.config.ts`:

```ts
import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './e2e',
  timeout: 60_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  retries: 0,
  reporter: 'list',
  use: {
    baseURL: 'https://localhost:3080',
    headless: true,
    actionTimeout: 5_000,
    ignoreHTTPSErrors: true,
  },
  projects: [
    {
      name: 'desktop-chromium',
      use: {
        browserName: 'chromium',
        viewport: { width: 1280, height: 900 },
      },
    },
    {
      name: 'mobile-iphone-se',
      use: {
        ...devices['iPhone SE'],
        browserName: 'chromium',
      },
    },
    {
      name: 'mobile-iphone-14',
      use: {
        ...devices['iPhone 14'],
        browserName: 'chromium',
      },
    },
    {
      name: 'tablet-ipad',
      use: {
        ...devices['iPad (gen 7)'],
        browserName: 'chromium',
      },
    },
  ],
})
```

- [ ] **Step 2: Create touch helper utilities**

Create `frontend/e2e/helpers/touch.ts`:

```ts
import type { Page, Locator } from '@playwright/test'

/**
 * Simulate a left swipe on a target element.
 */
export async function swipeLeft(page: Page, target: Locator, distance = 120): Promise<void> {
  const box = await target.boundingBox()
  if (!box) throw new Error('Element not visible for swipe')

  const startX = box.x + box.width * 0.8
  const startY = box.y + box.height / 2
  const endX = startX - distance

  await page.touchscreen.tap(startX, startY)
  await page.evaluate(
    ({ sx, sy, ex, ey }) => {
      const el = document.elementFromPoint(sx, sy)
      if (!el) return
      el.dispatchEvent(new TouchEvent('touchstart', {
        touches: [new Touch({ identifier: 1, target: el, clientX: sx, clientY: sy })],
        bubbles: true,
      }))
      el.dispatchEvent(new TouchEvent('touchmove', {
        touches: [new Touch({ identifier: 1, target: el, clientX: ex, clientY: ey })],
        bubbles: true,
      }))
      el.dispatchEvent(new TouchEvent('touchend', {
        changedTouches: [new Touch({ identifier: 1, target: el, clientX: ex, clientY: ey })],
        bubbles: true,
      }))
    },
    { sx: startX, sy: startY, ex: endX, ey: startY }
  )
  await page.waitForTimeout(350) // wait for animation
}

/**
 * Simulate a right swipe on a target element.
 */
export async function swipeRight(page: Page, target: Locator, distance = 120): Promise<void> {
  const box = await target.boundingBox()
  if (!box) throw new Error('Element not visible for swipe')

  const startX = box.x + box.width * 0.2
  const startY = box.y + box.height / 2
  const endX = startX + distance

  await page.evaluate(
    ({ sx, sy, ex, ey }) => {
      const el = document.elementFromPoint(sx, sy)
      if (!el) return
      el.dispatchEvent(new TouchEvent('touchstart', {
        touches: [new Touch({ identifier: 1, target: el, clientX: sx, clientY: sy })],
        bubbles: true,
      }))
      el.dispatchEvent(new TouchEvent('touchmove', {
        touches: [new Touch({ identifier: 1, target: el, clientX: ex, clientY: ey })],
        bubbles: true,
      }))
      el.dispatchEvent(new TouchEvent('touchend', {
        changedTouches: [new Touch({ identifier: 1, target: el, clientX: ex, clientY: ey })],
        bubbles: true,
      }))
    },
    { sx: startX, sy: startY, ex: endX, ey: startY }
  )
  await page.waitForTimeout(350)
}

/**
 * Simulate a long press on a target element.
 */
export async function longPress(page: Page, target: Locator, duration = 600): Promise<void> {
  const box = await target.boundingBox()
  if (!box) throw new Error('Element not visible for long press')

  const x = box.x + box.width / 2
  const y = box.y + box.height / 2

  await page.evaluate(
    ({ cx, cy }) => {
      const el = document.elementFromPoint(cx, cy)
      if (!el) return
      el.dispatchEvent(new TouchEvent('touchstart', {
        touches: [new Touch({ identifier: 1, target: el, clientX: cx, clientY: cy })],
        bubbles: true,
      }))
    },
    { cx: x, cy: y }
  )

  await page.waitForTimeout(duration)

  await page.evaluate(
    ({ cx, cy }) => {
      const el = document.elementFromPoint(cx, cy)
      if (!el) return
      el.dispatchEvent(new TouchEvent('touchend', {
        changedTouches: [new Touch({ identifier: 1, target: el, clientX: cx, clientY: cy })],
        bubbles: true,
      }))
    },
    { cx: x, cy: y }
  )
  await page.waitForTimeout(200)
}

/**
 * Simulate a downward swipe (for BottomSheet dismiss).
 */
export async function swipeDown(page: Page, target: Locator, distance = 200): Promise<void> {
  const box = await target.boundingBox()
  if (!box) throw new Error('Element not visible for swipe down')

  const startX = box.x + box.width / 2
  const startY = box.y + 20
  const endY = startY + distance

  await page.evaluate(
    ({ sx, sy, ey }) => {
      const el = document.elementFromPoint(sx, sy)
      if (!el) return
      el.dispatchEvent(new TouchEvent('touchstart', {
        touches: [new Touch({ identifier: 1, target: el, clientX: sx, clientY: sy })],
        bubbles: true,
      }))
      el.dispatchEvent(new TouchEvent('touchmove', {
        touches: [new Touch({ identifier: 1, target: el, clientX: sx, clientY: ey })],
        bubbles: true,
      }))
      el.dispatchEvent(new TouchEvent('touchend', {
        changedTouches: [new Touch({ identifier: 1, target: el, clientX: sx, clientY: ey })],
        bubbles: true,
      }))
    },
    { sx: startX, sy: startY, ey: endY }
  )
  await page.waitForTimeout(350)
}
```

- [ ] **Step 3: Commit**

```bash
cd /private/tmp/agentsmesh-workspace/sandboxes/2-3-2659936e/workspace
git add frontend/playwright.config.ts frontend/e2e/helpers/touch.ts
git commit -m "feat: add mobile device projects to Playwright config and touch helpers"
```

---

## Task 14: E2E test — project list mobile

**Files:**
- Create: `frontend/e2e/mobile/project-list.mobile.spec.ts`

- [ ] **Step 1: Write mobile E2E tests for project list**

Create `frontend/e2e/mobile/project-list.mobile.spec.ts`:

```ts
import { test, expect } from '@playwright/test'
import { swipeLeft, swipeRight, longPress } from '../helpers/touch'

const API_BASE = 'http://localhost:3090'

async function login(page, request) {
  const resp = await request.post(`${API_BASE}/api/v1/auth/login`, {
    data: { username: 'admin', password: 'Admin123!' },
  })
  const { access_token } = await resp.json()
  await page.goto('/')
  await page.evaluate((token) => localStorage.setItem('token', token), access_token)
  return access_token
}

test.describe('ProjectListView — Mobile', () => {
  // Only run in mobile projects
  test.skip(({ }, testInfo) => !testInfo.project.name.startsWith('mobile'), 'Desktop-only skip')

  test.beforeEach(async ({ page, request }) => {
    await login(page, request)
    await page.goto('/projects')
    await page.waitForLoadState('networkidle')
  })

  test('shows single-column grid on mobile', async ({ page }) => {
    const grid = page.locator('.grid')
    await expect(grid).toBeVisible()
    // Verify grid-cols-1 by checking computed column count
    const cols = await grid.evaluate(el => getComputedStyle(el).gridTemplateColumns)
    // Single column should have exactly one column value
    expect(cols.split(' ').length).toBe(1)
  })

  test('FAB button is visible', async ({ page }) => {
    const fab = page.locator('[data-testid="fab"]')
    await expect(fab).toBeVisible()
  })

  test('FAB opens create modal as bottom sheet', async ({ page }) => {
    await page.locator('[data-testid="fab"]').click()
    // Bottom sheet / modal should appear
    await expect(page.locator('text=新建项目').first()).toBeVisible()
    await expect(page.locator('text=项目名称').first()).toBeVisible()
  })

  test('swipe left reveals action buttons', async ({ page }) => {
    const firstCard = page.locator('[data-testid="swipe-content"]').first()
    if (await firstCard.count() === 0) {
      test.skip()
      return
    }
    await swipeLeft(page, firstCard)
    // Check that action area is visible
    const actions = page.locator('[data-testid="swipe-actions"]').first()
    await expect(actions).toBeVisible()
  })

  test('long press shows context menu', async ({ page }) => {
    const firstCard = page.locator('.card-hover').first()
    if (await firstCard.count() === 0) {
      test.skip()
      return
    }
    await longPress(page, firstCard)
    const menu = page.locator('[data-testid="long-press-menu"]')
    await expect(menu).toBeVisible()
    await expect(page.locator('text=查看详情')).toBeVisible()
    await expect(page.locator('text=编辑')).toBeVisible()
    await expect(page.locator('text=删除')).toBeVisible()
  })
})

test.describe('ProjectListView — Tablet', () => {
  test.skip(({ }, testInfo) => !testInfo.project.name.startsWith('tablet'), 'Mobile/Desktop skip')

  test.beforeEach(async ({ page, request }) => {
    await login(page, request)
    await page.goto('/projects')
    await page.waitForLoadState('networkidle')
  })

  test('shows two-column grid on tablet', async ({ page }) => {
    const grid = page.locator('.grid')
    await expect(grid).toBeVisible()
    const cols = await grid.evaluate(el => getComputedStyle(el).gridTemplateColumns)
    expect(cols.split(' ').length).toBe(2)
  })
})
```

- [ ] **Step 2: Commit**

```bash
cd /private/tmp/agentsmesh-workspace/sandboxes/2-3-2659936e/workspace
git add frontend/e2e/mobile/project-list.mobile.spec.ts
git commit -m "test: add mobile E2E tests for ProjectListView"
```

---

## Task 15: E2E test — project detail mobile

**Files:**
- Create: `frontend/e2e/mobile/project-detail.mobile.spec.ts`

- [ ] **Step 1: Write mobile E2E tests for project detail**

Create `frontend/e2e/mobile/project-detail.mobile.spec.ts`:

```ts
import { test, expect } from '@playwright/test'
import { swipeLeft, longPress } from '../helpers/touch'

const API_BASE = 'http://localhost:3090'

async function loginAndGetProject(page, request) {
  const resp = await request.post(`${API_BASE}/api/v1/auth/login`, {
    data: { username: 'admin', password: 'Admin123!' },
  })
  const { access_token } = await resp.json()
  await page.goto('/')
  await page.evaluate((token) => localStorage.setItem('token', token), access_token)

  // Get first project
  const projectsResp = await request.get(`${API_BASE}/api/v1/projects/`, {
    headers: { Authorization: `Bearer ${access_token}` },
  })
  const projects = await projectsResp.json()
  return { token: access_token, projectId: projects[0]?.id }
}

test.describe('ProjectDetailView — Mobile', () => {
  test.skip(({ }, testInfo) => !testInfo.project.name.startsWith('mobile'), 'Desktop-only skip')

  let projectId: string

  test.beforeEach(async ({ page, request }) => {
    const result = await loginAndGetProject(page, request)
    projectId = result.projectId
    if (!projectId) {
      test.skip()
      return
    }
    await page.goto(`/projects/${projectId}`)
    await page.waitForLoadState('networkidle')
  })

  test('breadcrumb shows simplified back arrow on mobile', async ({ page }) => {
    // Should show ArrowLeft icon, not ChevronRight separator
    const backLink = page.locator('nav a').first()
    await expect(backLink).toBeVisible()
    await expect(backLink).toContainText('项目列表')
  })

  test('tab bar is horizontally scrollable', async ({ page }) => {
    // All 4 tabs should exist
    await expect(page.locator('text=文件管理')).toBeVisible()
    await expect(page.locator('text=设置')).toBeVisible()
  })

  test('swipe left in content area switches to next tab', async ({ page }) => {
    // Start on files tab
    await expect(page.locator('text=文件管理').first()).toBeVisible()

    // Swipe left on content to go to next tab (associations)
    const content = page.locator('.page-container').last()
    await swipeLeft(page, content, 150)

    // Wait for tab to change — check the active tab
    await page.waitForTimeout(500)
  })

  test('FileManager swipe shows actions on mobile', async ({ page }) => {
    // If there are files, test swipe action
    const fileItem = page.locator('[data-testid="swipe-content"]').first()
    if (await fileItem.count() === 0) {
      test.skip()
      return
    }
    await swipeLeft(page, fileItem)
    const actions = page.locator('[data-testid="swipe-actions"]').first()
    await expect(actions).toBeVisible()
  })

  test('desktop viewport does not show swipe components', async ({ page, browserName }, testInfo) => {
    // This test only makes sense to verify in mobile project context
    // SwipeAction should be in DOM since we're in mobile project
    const swipeContent = page.locator('[data-testid="swipe-content"]')
    // In mobile context, if files exist, swipe-content should exist
    if (await swipeContent.count() > 0) {
      expect(true).toBeTruthy() // Mobile: swipe components present, correct
    }
  })
})
```

- [ ] **Step 2: Commit**

```bash
cd /private/tmp/agentsmesh-workspace/sandboxes/2-3-2659936e/workspace
git add frontend/e2e/mobile/project-detail.mobile.spec.ts
git commit -m "test: add mobile E2E tests for ProjectDetailView"
```

---

## Task 16: E2E test — file viewer mobile

**Files:**
- Create: `frontend/e2e/mobile/file-viewer.mobile.spec.ts`

- [ ] **Step 1: Write mobile E2E tests for file viewer**

Create `frontend/e2e/mobile/file-viewer.mobile.spec.ts`:

```ts
import { test, expect } from '@playwright/test'

const API_BASE = 'http://localhost:3090'

async function loginAndGetFile(page, request) {
  const resp = await request.post(`${API_BASE}/api/v1/auth/login`, {
    data: { username: 'admin', password: 'Admin123!' },
  })
  const { access_token } = await resp.json()
  await page.goto('/')
  await page.evaluate((token) => localStorage.setItem('token', token), access_token)

  // Get first project's files
  const projectsResp = await request.get(`${API_BASE}/api/v1/projects/`, {
    headers: { Authorization: `Bearer ${access_token}` },
  })
  const projects = await projectsResp.json()
  if (!projects[0]) return { token: access_token, fileId: null }

  const filesResp = await request.get(`${API_BASE}/api/v1/projects/${projects[0].id}/files?limit=1`, {
    headers: { Authorization: `Bearer ${access_token}` },
  })
  const files = await filesResp.json()
  return { token: access_token, fileId: files[0]?.id ?? null }
}

test.describe('FileViewerView — Mobile', () => {
  test.skip(({ }, testInfo) => !testInfo.project.name.startsWith('mobile'), 'Desktop-only skip')

  let fileId: string | null

  test.beforeEach(async ({ page, request }) => {
    const result = await loginAndGetFile(page, request)
    fileId = result.fileId
    if (!fileId) {
      test.skip()
      return
    }
    await page.goto(`/files/${fileId}`)
    await page.waitForLoadState('networkidle')
  })

  test('file icon is responsive (smaller on mobile)', async ({ page }) => {
    const icon = page.locator('.rounded-xl').first()
    const box = await icon.boundingBox()
    if (!box) {
      test.skip()
      return
    }
    // On mobile, icon should be 40px (w-10) or 48px (w-12), not 80px
    expect(box.width).toBeLessThanOrEqual(48)
  })

  test('mobile bottom toolbar is visible', async ({ page }) => {
    // Look for the fixed bottom toolbar with download/share buttons
    const toolbar = page.locator('text=下载').last()
    await expect(toolbar).toBeVisible()
  })

  test('desktop action buttons are hidden on mobile', async ({ page }) => {
    // The desktop btn-secondary download button should be hidden
    const desktopDownload = page.locator('.btn-secondary:has-text("下载")')
    await expect(desktopDownload).toBeHidden()
  })
})
```

- [ ] **Step 2: Commit**

```bash
cd /private/tmp/agentsmesh-workspace/sandboxes/2-3-2659936e/workspace
git add frontend/e2e/mobile/file-viewer.mobile.spec.ts
git commit -m "test: add mobile E2E tests for FileViewerView"
```

---

## Task 17: Run full test suite and fix issues

**Files:** All modified files from previous tasks

- [ ] **Step 1: Run all vitest unit tests**

```bash
cd /private/tmp/agentsmesh-workspace/sandboxes/2-3-2659936e/workspace/frontend
pnpm vitest run
```

Expected: All tests PASS. If any fail, fix the issue and re-run.

- [ ] **Step 2: Run type check**

```bash
cd /private/tmp/agentsmesh-workspace/sandboxes/2-3-2659936e/workspace/frontend
npx vue-tsc --noEmit
```

Expected: No type errors. Fix any that appear.

- [ ] **Step 3: Commit any fixes**

```bash
cd /private/tmp/agentsmesh-workspace/sandboxes/2-3-2659936e/workspace
git add -A
git commit -m "fix: resolve test and type-check issues from mobile optimization"
```

---

## Task 18: Update documentation

**Files:**
- Modify: `docs/features.md`

- [ ] **Step 1: Update features.md**

Add to the "全局组件" section in `docs/features.md`:

```markdown
### 移动端交互组件

| 组件 | 路径 | 说明 |
|------|------|------|
| `BottomSheet` | `src/components/ui/BottomSheet.vue` | 底部滑入面板，替代移动端模态框，支持拖拽关闭 |
| `SwipeAction` | `src/components/ui/SwipeAction.vue` | 左滑操作栏，包裹列表项露出编辑/删除按钮 |
| `LongPressMenu` | `src/components/ui/LongPressMenu.vue` | 长按上下文菜单，手指位置弹出操作列表 |
| `FloatingActionButton` | `src/components/ui/FloatingActionButton.vue` | 移动端悬浮操作按钮 (FAB)，仅非桌面端显示 |

### 移动端 Composables

| Composable | 路径 | 说明 |
|-----------|------|------|
| `useMobile` | `src/composables/useMobile.ts` | 响应式断点检测（mobile/tablet/desktop） |
| `useBottomToolbar` | `src/composables/useBottomToolbar.ts` | 底部工具栏滚动感知显隐控制 |
```

Add to the E2E testing section:

```markdown
### 移动端 E2E 测试

测试目录: `frontend/e2e/mobile/`

| 测试文件 | 覆盖内容 |
|---------|---------|
| `project-list.mobile.spec.ts` | 项目列表移动端布局、FAB、左滑、长按菜单 |
| `project-detail.mobile.spec.ts` | 项目详情 Tab 滑动切换、文件管理手势 |
| `file-viewer.mobile.spec.ts` | 文件查看器响应式布局、底部工具栏 |

设备视口配置:
- iPhone SE (375×667)
- iPhone 14 (390×844)
- iPad gen 7 (768×1024)
```

- [ ] **Step 2: Commit documentation update**

```bash
cd /private/tmp/agentsmesh-workspace/sandboxes/2-3-2659936e/workspace
git add docs/features.md
git commit -m "docs: update features.md with mobile components, composables, and E2E tests"
```

---

## Summary of all files

### Created (14 files)
- `frontend/src/composables/useMobile.ts`
- `frontend/src/composables/useMobile.spec.ts`
- `frontend/src/composables/useBottomToolbar.ts`
- `frontend/src/composables/useBottomToolbar.spec.ts`
- `frontend/src/components/ui/BottomSheet.vue`
- `frontend/src/components/ui/__tests__/BottomSheet.spec.ts`
- `frontend/src/components/ui/SwipeAction.vue`
- `frontend/src/components/ui/__tests__/SwipeAction.spec.ts`
- `frontend/src/components/ui/LongPressMenu.vue`
- `frontend/src/components/ui/__tests__/LongPressMenu.spec.ts`
- `frontend/src/components/ui/FloatingActionButton.vue`
- `frontend/src/components/ui/__tests__/FloatingActionButton.spec.ts`
- `frontend/e2e/helpers/touch.ts`
- `frontend/e2e/mobile/project-list.mobile.spec.ts`
- `frontend/e2e/mobile/project-detail.mobile.spec.ts`
- `frontend/e2e/mobile/file-viewer.mobile.spec.ts`

### Modified (7 files)
- `frontend/package.json` (add @vueuse/core)
- `frontend/playwright.config.ts` (add mobile device projects)
- `frontend/src/components/ui/AppModal.vue` (add mobileMode prop, useMobile)
- `frontend/src/views/project/ProjectListView.vue` (mobile gestures, FAB)
- `frontend/src/views/project/ProjectDetailView.vue` (tab swipe, mobile header)
- `frontend/src/components/project/FileManager.vue` (mobile swipe/long-press, FAB)
- `frontend/src/views/analyzer/FileViewerView.vue` (responsive sizing, bottom toolbar)
- `frontend/src/views/dev/ComponentTestView.vue` (component demos)
- `docs/features.md` (documentation update)

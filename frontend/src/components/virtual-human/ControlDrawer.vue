<script setup lang="ts">
/**
 * ControlDrawer — 底部弹出毛玻璃抽屉，包含 ControlPanel
 * Apple Glass UI 风格
 */
import ControlPanel from './ControlPanel.vue'

const props = defineProps<{ open: boolean }>()
const emit = defineEmits<{ 'update:open': [value: boolean] }>()

function close() {
  emit('update:open', false)
}
</script>

<template>
  <Teleport to="body">
    <!-- 遮罩 -->
    <Transition name="fade">
      <div
        v-if="props.open"
        class="fixed inset-0 bg-black/50 backdrop-blur-sm z-40"
        @click="close"
      />
    </Transition>
    <!-- 抽屉面板 -->
    <Transition name="slide-up">
      <div
        v-if="props.open"
        class="drawer-panel"
      >
        <!-- 拖动手柄 -->
        <div class="flex justify-center pt-2.5 pb-1 shrink-0 cursor-pointer" @click="close">
          <div class="w-9 h-1 rounded-full bg-white/25" />
        </div>
        <!-- 标题行 -->
        <div class="flex items-center justify-between px-5 pb-2 shrink-0">
          <h3 class="drawer-title">控制面板</h3>
          <button class="drawer-close-btn" @click="close">
            完成
          </button>
        </div>
        <!-- ControlPanel 内容 -->
        <div class="flex-1 overflow-auto px-4 pb-5">
          <ControlPanel />
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.drawer-panel {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  z-index: 50;
  max-height: 68vh;
  background: rgba(20, 20, 30, 0.85);
  backdrop-filter: blur(40px) saturate(1.8);
  -webkit-backdrop-filter: blur(40px) saturate(1.8);
  border-top: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 20px 20px 0 0;
  box-shadow: 0 -12px 40px rgba(0, 0, 0, 0.3),
              0 -1px 3px rgba(0, 0, 0, 0.1);
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.drawer-title {
  font-size: 15px;
  font-weight: 600;
  letter-spacing: -0.01em;
  color: rgba(255, 255, 255, 0.85);
}

.drawer-close-btn {
  font-size: 13px;
  font-weight: 500;
  color: #007AFF; /* Apple Blue */
  padding: 4px 12px;
  border-radius: 980px;
  border: none;
  background: transparent;
  cursor: pointer;
  transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
}

.drawer-close-btn:hover {
  background: rgba(0, 122, 255, 0.1);
}

/* Transitions */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.25s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.slide-up-enter-active {
  transition: transform 0.4s cubic-bezier(0.16, 1, 0.3, 1);
}
.slide-up-leave-active {
  transition: transform 0.25s cubic-bezier(0.4, 0, 1, 1);
}
.slide-up-enter-from,
.slide-up-leave-to {
  transform: translateY(100%);
}
</style>

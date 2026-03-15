<script setup lang="ts">
/**
 * WebSocket 连接状态指示器
 */
import { useVirtualHumanStore } from '@/store/virtualHuman'

const store = useVirtualHumanStore()
</script>

<template>
  <div class="flex items-center gap-2 text-xs">
    <!-- 状态圆点 -->
    <span
      :class="[
        'w-2 h-2 rounded-full',
        store.connected ? 'bg-green-400 animate-pulse' : store.connecting ? 'bg-yellow-400 animate-pulse' : 'bg-gray-400'
      ]"
    />
    <span class="text-gray-500">
      {{ store.connected ? '已连接' : store.connecting ? '连接中...' : '未连接' }}
    </span>
    <span v-if="store.error" class="text-red-400">{{ store.error }}</span>
  </div>
</template>

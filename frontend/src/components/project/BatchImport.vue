<template>
  <div class="text-center py-10 text-gray-400">
    <p class="text-sm">批量导入功能即将上线</p>
    <button class="btn-secondary btn-sm mt-4" @click="$emit('complete')">关闭</button>
  </div>
</template>

<script setup lang="ts">
defineEmits(['complete'])
</script>

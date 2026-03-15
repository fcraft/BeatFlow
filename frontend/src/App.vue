<template>
  <RouterView />
  <AppToast />
</template>

<script setup lang="ts">
import { RouterView } from 'vue-router'
import AppToast from '@/components/ui/AppToast.vue'
</script>

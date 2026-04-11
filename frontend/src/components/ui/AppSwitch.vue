<template>
  <label class="app-switch" :class="disabled && 'app-switch--disabled'">
    <input
      type="checkbox"
      :checked="modelValue"
      :disabled="disabled"
      class="sr-only"
      @change="emit('update:modelValue', ($event.target as HTMLInputElement).checked)"
    />
    <div class="app-switch__track" :class="modelValue && 'is-on'">
      <div class="app-switch__thumb" />
    </div>
    <span v-if="$slots.default || label" class="app-switch__label">
      <slot>{{ label }}</slot>
    </span>
  </label>
</template>

<script setup lang="ts">
defineProps<{
  modelValue: boolean
  label?: string
  disabled?: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
}>()
</script>

<style scoped>
.app-switch {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
  user-select: none;
}
.app-switch--disabled {
  opacity: 0.5;
  cursor: not-allowed;
  pointer-events: none;
}

.app-switch__track {
  position: relative;
  width: 40px;
  height: 24px;
  border-radius: 12px;
  background: #d1d5db;
  flex-shrink: 0;
  transition: background 0.2s ease;
}
.app-switch__track.is-on {
  background: #2563eb;
}

.app-switch__thumb {
  position: absolute;
  top: 2px;
  left: 2px;
  width: 20px;
  height: 20px;
  border-radius: 10px;
  background: white;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.15), 0 0 0 0.5px rgba(0, 0, 0, 0.04);
  transition: transform 0.2s cubic-bezier(0.16, 1, 0.3, 1);
}
.app-switch__track.is-on .app-switch__thumb {
  transform: translateX(16px);
}

.app-switch__track:hover {
  background: #bcc1ca;
}
.app-switch__track.is-on:hover {
  background: #1d4ed8;
}

.app-switch__label {
  font-size: 14px;
  line-height: 1.4;
  color: #374151;
}
</style>

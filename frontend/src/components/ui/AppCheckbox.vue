<template>
  <label class="app-check" :class="[disabled && 'app-check--disabled']">
    <input
      type="checkbox"
      :checked="modelValue"
      :disabled="disabled"
      class="sr-only"
      @change="emit('update:modelValue', ($event.target as HTMLInputElement).checked)"
    />
    <!-- Box -->
    <div class="app-check__box" :class="modelValue && 'is-checked'">
      <svg class="app-check__tick" viewBox="0 0 12 12" fill="none">
        <path d="M2.5 6L5 8.5L9.5 3.5" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" />
      </svg>
    </div>
    <!-- Label -->
    <span v-if="$slots.default || label" class="app-check__label">
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
.app-check {
  display: inline-flex;
  align-items: flex-start;
  gap: 10px;
  cursor: pointer;
  user-select: none;
}
.app-check--disabled {
  opacity: 0.5;
  cursor: not-allowed;
  pointer-events: none;
}

.app-check__box {
  width: 20px;
  height: 20px;
  border-radius: 6px;
  border: 1.5px solid rgba(0, 0, 0, 0.15);
  background: white;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: all 0.15s ease;
  margin-top: 1px;
}
.app-check__box:hover {
  border-color: rgba(0, 0, 0, 0.25);
}
.app-check__box.is-checked {
  background: #2563eb;
  border-color: #2563eb;
}
.app-check__box.is-checked:hover {
  background: #1d4ed8;
  border-color: #1d4ed8;
}

.app-check__tick {
  width: 12px;
  height: 12px;
  color: white;
  opacity: 0;
  transform: scale(0.5);
  transition: all 0.15s cubic-bezier(0.16, 1, 0.3, 1);
}
.app-check__box.is-checked .app-check__tick {
  opacity: 1;
  transform: scale(1);
}

.app-check__label {
  font-size: 14px;
  line-height: 1.4;
  color: #374151;
}
</style>

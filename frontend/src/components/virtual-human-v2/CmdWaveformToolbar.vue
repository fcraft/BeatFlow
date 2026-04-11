<script setup lang="ts">
/**
 * CmdWaveformToolbar — 波形区域内嵌工具条
 *
 * 移动端: 精简为标注+导联选择器，隐藏 PV/AP/Wiggers
 */
import { Eye, EyeOff, BarChart3 } from 'lucide-vue-next'
import { useVirtualHumanStore } from '@/store/virtualHuman'
import EcgLeadSelector from '@/components/virtual-human/EcgLeadSelector.vue'

const store = useVirtualHumanStore()

const emit = defineEmits<{
  (e: 'toggle-pv'): void
  (e: 'toggle-ap'): void
  (e: 'toggle-wiggers'): void
}>()

defineProps<{ showPv: boolean; showAp: boolean; showWiggers: boolean }>()
</script>

<template>
  <div class="flex items-center gap-1 md:gap-1.5 px-1 md:px-2 py-1 md:py-1.5 shrink-0 flex-wrap">
    <button class="h-6 px-2 md:px-2.5 text-[10px] font-semibold rounded-full border transition-all duration-200"
            :class="store.showAnnotations
              ? 'text-[#007AFF] bg-[#007AFF]/10 border-[#007AFF]/25 shadow-[0_0_8px_rgba(0,122,255,0.15)]'
              : 'text-white/35 border-white/[0.08] hover:bg-white/[0.05]'"
            style="border-radius: 980px"
            @click="store.toggleAnnotations()">
      <Eye v-if="store.showAnnotations" :size="10" class="inline mr-0.5 md:mr-1" />
      <EyeOff v-else :size="10" class="inline mr-0.5 md:mr-1" />
      <span class="cmd-desktop-only">标注</span>
    </button>
    <button class="h-6 px-2 md:px-2.5 text-[10px] font-semibold rounded-full border transition-all duration-200 cmd-desktop-only"
            :class="store.showTrendChart
              ? 'text-[#AF52DE] bg-[#AF52DE]/10 border-[#AF52DE]/25'
              : 'text-white/35 border-white/[0.08] hover:bg-white/[0.05]'"
            style="border-radius: 980px"
            @click="store.toggleTrendChart()">
      <BarChart3 :size="10" class="inline mr-1" />趋势
    </button>
    <EcgLeadSelector class="ml-0.5 md:ml-1" />

    <!-- Desktop-only physiology viz toggles -->
    <div class="flex items-center gap-1 ml-auto cmd-desktop-only">
      <button v-for="item in [
                { key: 'pv', label: 'PV', active: showPv, color: '#007AFF', event: 'toggle-pv' },
                { key: 'ap', label: 'AP', active: showAp, color: '#FF3B30', event: 'toggle-ap' },
                { key: 'wig', label: 'Wiggers', active: showWiggers, color: '#34C759', event: 'toggle-wiggers' },
              ]" :key="item.key"
              class="h-6 px-2 text-[10px] font-semibold rounded-full border transition-all duration-200"
              :class="item.active
                ? `border-[${item.color}]/25 shadow-[0_0_8px_${item.color}26]`
                : 'text-white/35 border-white/[0.08] hover:bg-white/[0.05]'"
              :style="item.active ? `color: ${item.color}; background: ${item.color}1a; border-color: ${item.color}40; border-radius: 980px` : 'border-radius: 980px'"
              @click="emit(item.event as any)">
        {{ item.label }}
      </button>
    </div>
  </div>
</template>

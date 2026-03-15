<script setup lang="ts">
/**
 * 听诊模式面板
 *
 * 包含：SVG 胸廓示意图 + 4 个听诊区域选择 + 降噪开关 + 临床提示
 * 通过 virtualHuman store 管理全局听诊状态
 */
import { computed } from 'vue'
import { Stethoscope, Volume2, ShieldCheck } from 'lucide-vue-next'
import { useVirtualHumanStore } from '@/store/virtualHuman'
import {
  AUSCULTATION_AREAS,
  AREA_ORDER,
  type AuscultationArea,
} from '@/composables/useAuscultation'

const store = useVirtualHumanStore()

const currentConfig = computed(() => AUSCULTATION_AREAS[store.auscultationArea])

function selectArea(area: AuscultationArea) {
  store.auscultationArea = area
}

/** 区域颜色映射 */
const areaColors: Record<AuscultationArea, string> = {
  aortic: '#FF3B30',
  pulmonic: '#007AFF',
  tricuspid: '#AF52DE',
  mitral: '#FF9500',
}
</script>

<template>
  <div class="glass-tab-root">
    <!-- 标题行 -->
    <div class="flex items-center justify-between">
      <div class="flex items-center gap-2">
        <Stethoscope :size="18" style="color: #007AFF;" />
        <h3 class="glass-card-label" style="font-size: 14px;">听诊模式</h3>
      </div>
      <button
        :class="['glass-pill-btn glass-pill-btn--sm', store.auscultationMode ? 'glass-pill-btn--primary' : 'glass-pill-btn--ghost']"
        @click="store.auscultationMode = !store.auscultationMode"
      >
        <Volume2 :size="13" />
        {{ store.auscultationMode ? '听诊中' : '开启听诊' }}
      </button>
    </div>

    <!-- 主内容区 -->
    <div class="grid grid-cols-2 gap-4" :style="!store.auscultationMode ? 'opacity: 0.4; pointer-events: none;' : ''">
      <!-- 左：SVG 胸廓 -->
      <div class="glass-section flex items-center justify-center" style="padding: 12px;">
        <svg viewBox="0 0 100 100" class="w-full max-w-[220px] h-auto">
          <ellipse cx="50" cy="52" rx="36" ry="42" fill="none" stroke="rgba(255,255,255,0.15)" stroke-width="1.2" />
          <line x1="50" y1="14" x2="50" y2="78" stroke="rgba(255,255,255,0.15)" stroke-width="1.5" stroke-linecap="round" />
          <path d="M 28 28 Q 50 24 72 28" fill="none" stroke="rgba(255,255,255,0.08)" stroke-width="0.8" />
          <path d="M 24 38 Q 50 33 76 38" fill="none" stroke="rgba(255,255,255,0.08)" stroke-width="0.8" />
          <path d="M 22 50 Q 50 44 78 50" fill="none" stroke="rgba(255,255,255,0.08)" stroke-width="0.8" />
          <path d="M 24 62 Q 50 56 76 62" fill="none" stroke="rgba(255,255,255,0.08)" stroke-width="0.8" />
          <path d="M 28 73 Q 50 67 72 73" fill="none" stroke="rgba(255,255,255,0.08)" stroke-width="0.8" />
          <path
            d="M 44 36 C 38 30 28 38 36 50 C 40 56 50 68 56 72 C 62 66 72 54 72 44 C 72 34 62 28 56 36 Z"
            fill="rgba(255,59,48,0.04)" stroke="rgba(255,59,48,0.1)" stroke-width="0.6"
          />
          <g
            v-for="area in AREA_ORDER"
            :key="area"
            class="cursor-pointer"
            @click="selectArea(area)"
          >
            <circle
              v-if="store.auscultationArea === area"
              :cx="AUSCULTATION_AREAS[area].svgPosition.x"
              :cy="AUSCULTATION_AREAS[area].svgPosition.y"
              r="6"
              :fill="areaColors[area]"
              fill-opacity="0.15"
              :stroke="areaColors[area]"
              stroke-width="0.5"
              class="animate-ping"
              style="animation-duration: 2s"
            />
            <circle
              :cx="AUSCULTATION_AREAS[area].svgPosition.x"
              :cy="AUSCULTATION_AREAS[area].svgPosition.y"
              :r="store.auscultationArea === area ? 4 : 3"
              :fill="store.auscultationArea === area ? areaColors[area] : 'rgba(255,255,255,0.3)'"
              :stroke="store.auscultationArea === area ? areaColors[area] : 'rgba(255,255,255,0.2)'"
              stroke-width="0.8"
              style="transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);"
            />
            <text
              :x="AUSCULTATION_AREAS[area].svgPosition.x + (area === 'aortic' ? -14 : 7)"
              :y="AUSCULTATION_AREAS[area].svgPosition.y + (area === 'mitral' ? 6 : area === 'tricuspid' ? -4 : -5)"
              :fill="store.auscultationArea === area ? areaColors[area] : 'rgba(255,255,255,0.3)'"
              font-size="3.5"
              :font-weight="store.auscultationArea === area ? 'bold' : 'normal'"
              class="select-none pointer-events-none"
            >
              {{ AUSCULTATION_AREAS[area].labelEn.charAt(0) }}
            </text>
          </g>
        </svg>
      </div>

      <!-- 右：区域详情 + 控制 -->
      <div class="flex flex-col gap-3">
        <!-- 区域选择 -->
        <div class="glass-grid glass-grid--2col">
          <button
            v-for="area in AREA_ORDER"
            :key="area"
            :class="['glass-card-btn', store.auscultationArea === area ? 'glass-card-btn--active' : '']"
            :style="store.auscultationArea === area ? `border-color: ${areaColors[area]}30; box-shadow: 0 0 0 1px ${areaColors[area]}20;` : ''"
            @click="selectArea(area)"
          >
            <div class="flex items-center gap-1.5">
              <span
                class="w-2 h-2 rounded-full shrink-0"
                :style="{ backgroundColor: store.auscultationArea === area ? areaColors[area] : 'rgba(255,255,255,0.2)' }"
              />
              <span class="glass-card-label" :style="store.auscultationArea === area ? `color: ${areaColors[area]};` : ''">
                {{ AUSCULTATION_AREAS[area].label }}
              </span>
            </div>
          </button>
        </div>

        <!-- 信息卡 -->
        <div class="glass-section flex-1">
          <div class="flex items-center gap-1.5 mb-1.5">
            <span class="w-2.5 h-2.5 rounded-full" :style="{ backgroundColor: areaColors[store.auscultationArea] }" />
            <span class="glass-card-label">{{ currentConfig.label }}</span>
            <span class="glass-card-desc ml-auto">{{ currentConfig.labelEn }}</span>
          </div>
          <p class="glass-hint mb-1.5">📍 {{ currentConfig.location }}</p>
          <p style="font-size: 11px; color: rgba(255,255,255,0.5); line-height: 1.5;">
            {{ currentConfig.clinicalTip }}
          </p>
          <hr class="glass-divider" style="margin: 8px 0;" />
          <div class="flex items-center gap-3" style="font-size: 10px; color: rgba(255,255,255,0.3);">
            <span>频段: {{ currentConfig.hpFreq }}-{{ currentConfig.lpFreq }}Hz</span>
            <span>共鸣: {{ currentConfig.resonanceFreq }}Hz +{{ currentConfig.resonanceGain }}dB</span>
          </div>
        </div>

        <!-- 降噪 -->
        <div class="glass-section flex items-center justify-between" style="padding: 10px 14px;">
          <div class="flex items-center gap-1.5">
            <ShieldCheck :size="13" style="color: #34C759;" />
            <span style="font-size: 12px; color: rgba(255,255,255,0.6);">降噪模式</span>
          </div>
          <button
            :class="['glass-toggle', store.noiseReduction ? 'glass-toggle--on' : 'glass-toggle--off']"
            @click="store.noiseReduction = !store.noiseReduction"
          >
            <span class="glass-toggle-knob" />
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
@import './glass-tab-shared.css';
</style>

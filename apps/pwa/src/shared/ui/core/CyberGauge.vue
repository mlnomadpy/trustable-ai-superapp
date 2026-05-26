<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  value: number | string
  max?: number | string
  variant?: 'primary' | 'good' | 'warn' | 'bad'
}>()

const percent = computed(() => {
  const v = Number(props.value) || 0
  const m = Number(props.max) || 100
  return Math.min(100, Math.max(0, (v / m) * 100))
})
</script>

<template>
  <div class="cyber-gauge relative w-full h-[clamp(12px,2.5vmin,20px)] bg-ink border-2 border-slate overflow-hidden">
    <!-- Fill Bar -->
    <div 
      class="h-full transition-all duration-75 origin-left segmented-bar"
      :class="[`bg-ui-${variant || 'good'}`]"
      :style="{ width: `${percent}%` }"
    ></div>
    
    <!-- Dark scanline overlay -->
    <div class="absolute inset-0 pointer-events-none opacity-30"
         style="background: repeating-linear-gradient(90deg, transparent, transparent 2px, #000 2px, #000 4px);">
    </div>
  </div>
</template>

<style scoped>
.segmented-bar {
  /* Segment cuts */
  mask-image: repeating-linear-gradient(90deg, black, black 4px, transparent 4px, transparent 6px);
  -webkit-mask-image: repeating-linear-gradient(90deg, black, black 4px, transparent 4px, transparent 6px);
}

.bg-ui-primary { background-color: var(--color-silver); }
.bg-ui-good { background-color: var(--color-ui-good); }
.bg-ui-warn { background-color: var(--color-ui-warn); }
.bg-ui-bad { background-color: var(--color-ui-bad); }
</style>

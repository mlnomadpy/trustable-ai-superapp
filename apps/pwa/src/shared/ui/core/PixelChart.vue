<script setup lang="ts">
import { computed } from 'vue'

/**
 * Pixelated line chart for telemetry and performance data.
 */
interface Props {
  data: number[]
  width?: number
  height?: number
  color?: string
  min?: number
  max?: number
  strokeWidth?: number
}

const props = withDefaults(defineProps<Props>(), {
  width: 320,
  height: 100,
  color: '#2aa198', // pitwall cyan
  strokeWidth: 2
})

const pathD = computed(() => {
  if (props.data.length < 2) return ''
  
  const minVal = props.min !== undefined ? props.min : Math.min(...props.data)
  const maxVal = props.max !== undefined ? props.max : Math.max(...props.data)
  const range = maxVal - minVal || 1
  
  const points = props.data.map((v, i) => {
    const x = (i / (props.data.length - 1)) * props.width
    const y = props.height - ((v - minVal) / range) * props.height
    return `${x.toFixed(1)},${y.toFixed(1)}`
  })
  
  return `M ${points.join(' L ')}`
})
</script>

<template>
  <div class="pixel-chart" :style="{ width: width + 'px', height: height + 'px' }" role="img" aria-label="Performance data chart">
    <svg 
      :viewBox="`0 0 ${width} ${height}`" 
      preserveAspectRatio="none"
      class="chart-svg"
      aria-hidden="true"
    >

      <path 
        :d="pathD" 
        fill="none" 
        :stroke="color" 
        :stroke-width="strokeWidth"
        stroke-linejoin="round"
        stroke-linecap="round"
      />
    </svg>
  </div>
</template>

<style scoped>
.pixel-chart {
  display: block;
  background: rgba(13, 13, 18, 0.5); /* ui-bg-deep */
  position: relative;
  overflow: hidden;
}

.chart-svg {
  width: 100%;
  height: 100%;
  image-rendering: pixelated;
}

path {
  /* Ensure the stroke stays crisp and "pixelated" looking */
  vector-effect: non-scaling-stroke;
}
</style>

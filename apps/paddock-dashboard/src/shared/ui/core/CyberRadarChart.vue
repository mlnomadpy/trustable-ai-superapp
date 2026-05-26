<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  stats: { label: string; value: number }[] // array of 5 elements, value 0-100
  color?: string // hex color
}>()

const centerX = 50
const centerY = 50
const maxRadius = 35

const points = computed(() => {
  return props.stats.map((stat, i) => {
    const angle = -Math.PI / 2 + (i * 2 * Math.PI) / props.stats.length
    const radius = (Math.max(0, Math.min(100, stat.value)) / 100) * maxRadius
    return {
      x: centerX + radius * Math.cos(angle),
      y: centerY + radius * Math.sin(angle),
      labelX: centerX + (maxRadius + 10) * Math.cos(angle),
      labelY: centerY + (maxRadius + 10) * Math.sin(angle),
      label: stat.label,
      value: stat.value
    }
  })
})

const bgPolygons = computed(() => {
  const steps = [0.25, 0.5, 0.75, 1.0]
  return steps.map(scale => {
    return Array.from({ length: props.stats.length }).map((_, i) => {
      const angle = -Math.PI / 2 + (i * 2 * Math.PI) / props.stats.length
      const r = maxRadius * scale
      return `${centerX + r * Math.cos(angle)},${centerY + r * Math.sin(angle)}`
    }).join(' ')
  })
})

const dataPolygon = computed(() => {
  return points.value.map(p => `${p.x},${p.y}`).join(' ')
})

const themeColor = computed(() => props.color || '#4ecdc4')
</script>

<template>
  <div class="cyber-radar-chart w-full h-full flex items-center justify-center relative">
    <svg viewBox="0 0 100 100" class="w-full h-full max-w-[280px] max-h-[280px] overflow-visible drop-shadow-[2px_2px_0_rgba(0,0,0,1)]">
      <!-- Background spiderweb pentagons -->
      <polygon 
        v-for="(pts, idx) in bgPolygons" 
        :key="`bg-${idx}`"
        :points="pts" 
        fill="transparent" 
        stroke="#45a29e" 
        stroke-width="0.25" 
      />
      
      <!-- Axis lines -->
      <line 
        v-for="(_, i) in points" 
        :key="`axis-${i}`"
        :x1="centerX" :y1="centerY" 
        :x2="centerX + maxRadius * Math.cos(-Math.PI / 2 + (i * 2 * Math.PI) / stats.length)" 
        :y2="centerY + maxRadius * Math.sin(-Math.PI / 2 + (i * 2 * Math.PI) / stats.length)"
        stroke="#45a29e" 
        stroke-width="0.5" 
        stroke-dasharray="1,1"
      />
      
      <!-- Data polygon -->
      <polygon 
        :points="dataPolygon" 
        :fill="`${themeColor}44`" 
        :stroke="themeColor" 
        stroke-width="1"
        class="data-poly"
      />
      
      <!-- Data points -->
      <circle 
        v-for="(p, i) in points" 
        :key="`pt-${i}`"
        :cx="p.x" :cy="p.y" 
        r="1.5" 
        :fill="themeColor"
        :stroke="themeColor"
        stroke-width="0.5"
      />
      
      <!-- Labels -->
      <text 
        v-for="(p, i) in points" 
        :key="`lbl-${i}`"
        :x="p.labelX" 
        :y="p.labelY" 
        font-family="var(--font-ui)" 
        font-size="4.5" 
        font-weight="bold"
        fill="#c5c6c7"
        text-anchor="middle"
        dominant-baseline="middle"
        class="pixel-shadow"
      >
        {{ p.label }}
      </text>
    </svg>
  </div>
</template>

<style scoped>
.data-poly {
  transition: all 0.3s steps(5);
  transform-origin: center;
}
.pixel-shadow {
  text-shadow: 0.5px 0.5px 0 #0b0c10;
}
</style>

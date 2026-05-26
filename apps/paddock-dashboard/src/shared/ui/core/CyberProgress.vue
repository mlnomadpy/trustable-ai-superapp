<script setup lang="ts">
import { computed } from 'vue'

interface Props {
  value: number
  max?: number
  variant?: 'good' | 'warn' | 'bad' | 'info'
  thickness?: 'sm' | 'md' | 'lg' | 'xl'
  animated?: boolean
  markers?: number
  /** Show a percentage or value label overlaid on the bar */
  showValue?: boolean
  /** Display an indeterminate (unknown progress) shimmer */
  indeterminate?: boolean
  /** Racing-themed diagonal stripes on the fill */
  striped?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  max: 100,
  variant: 'good',
  thickness: 'md',
  animated: true,
  markers: 3,
  showValue: false,
  indeterminate: false,
  striped: false,
})

const percentage = computed(() => {
  if (props.indeterminate) return 100
  return Math.min(100, Math.max(0, (props.value / props.max) * 100))
})
</script>

<template>
  <div 
    class="cyber-progress-container bg-charcoal border-slate border"
    :class="[`thickness-${thickness}`]"
    role="progressbar"
    :aria-valuenow="indeterminate ? undefined : value"
    :aria-valuemin="0"
    :aria-valuemax="max"
  >
    <div 
      class="cyber-progress-fill"
      :class="[
        `fill-${variant}`,
        { 
          'animate-pulse-slow': animated && percentage > 0 && !indeterminate,
          'indeterminate': indeterminate,
          'striped': striped
        }
      ]"
      :style="{ width: `${percentage}%` }"
    ></div>
    
    <!-- Markers -->
    <div v-if="markers > 0 && !indeterminate" class="marker-container" aria-hidden="true">
      <div v-for="i in markers" :key="i" class="marker"></div>
    </div>

    <!-- Value label -->
    <div v-if="showValue && !indeterminate" class="value-overlay" aria-hidden="true">
      {{ Math.round(percentage) }}%
    </div>

    <!-- Slot for custom label -->
    <div class="label-overlay">
      <slot name="label"></slot>
    </div>
  </div>
</template>

<style scoped>
.cyber-progress-container {
  position: relative;
  width: 100%;
  overflow: hidden;
  display: flex;
}

/* Thickness */
.thickness-sm { height: 4px; }
.thickness-md { height: 8px; }
.thickness-lg { height: 16px; }
.thickness-xl { height: 24px; }

/* Fill Layer */
.cyber-progress-fill {
  height: 100%;
  transition: width var(--duration-normal, 300ms) cubic-bezier(0.4, 0, 0.2, 1);
  position: relative;
}

/* Variants */
.fill-good {
  background: var(--color-ui-good);
  box-shadow: 0 0 8px rgba(78, 205, 196, 0.6);
}

.fill-warn {
  background: var(--color-ui-warn);
  box-shadow: 0 0 8px rgba(254, 202, 87, 0.6);
}

.fill-bad {
  background: var(--color-ui-bad);
  box-shadow: 0 0 8px rgba(255, 71, 87, 0.6);
}

.fill-info {
  background: var(--color-ui-info);
  box-shadow: 0 0 8px rgba(69, 183, 209, 0.6);
}

/* Striped */
.cyber-progress-fill.striped::after {
  content: '';
  position: absolute;
  inset: 0;
  background: repeating-linear-gradient(
    -45deg,
    transparent,
    transparent 4px,
    rgba(255, 255, 255, 0.1) 4px,
    rgba(255, 255, 255, 0.1) 8px
  );
  animation: stripe-scroll 0.8s linear infinite;
}

@keyframes stripe-scroll {
  0% { background-position: 0 0; }
  100% { background-position: 16px 0; }
}

/* Indeterminate */
.cyber-progress-fill.indeterminate {
  width: 40% !important;
  animation: indeterminate 1.5s ease-in-out infinite;
}

@keyframes indeterminate {
  0% { transform: translateX(-100%); }
  100% { transform: translateX(250%); }
}

/* Pulse */
.animate-pulse-slow {
  animation: progress-pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
}

@keyframes progress-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.85; }
}

/* Markers */
.marker-container {
  position: absolute;
  inset: 0;
  pointer-events: none;
  display: flex;
  justify-content: evenly;
  opacity: 0.2;
}

.marker {
  height: 100%;
  width: 1px;
  background: white;
}

/* Value overlay */
.value-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: clamp(7px, 1.5vmin, 12px);
  font-family: var(--font-nums);
  color: white;
  text-shadow: 0 0 4px rgba(0, 0, 0, 0.8);
  pointer-events: none;
  z-index: 10;
}

/* Label */
.label-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  padding: 0 var(--space-xs, 2px);
  pointer-events: none;
  z-index: 10;
}

@media (prefers-reduced-motion: reduce) {
  .animate-pulse-slow,
  .cyber-progress-fill.indeterminate,
  .cyber-progress-fill.striped::after {
    animation: none;
  }
  .cyber-progress-fill.indeterminate {
    width: 100% !important;
    transform: none;
    opacity: 0.5;
  }
}
</style>

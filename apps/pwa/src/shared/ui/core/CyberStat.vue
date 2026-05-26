<script setup lang="ts">
interface Props {
  /** The label displayed above the value */
  label: string
  /** The primary value to display */
  value: string | number
  /** Color variant for the value text */
  variant?: 'default' | 'good' | 'warn' | 'bad' | 'info'
  /** Size preset controlling font sizes */
  size?: 'sm' | 'md' | 'lg'
  /** Optional trend arrow indicator */
  trend?: 'up' | 'down' | 'flat'
  /** Use monospace font for numeric values */
  mono?: boolean
}

withDefaults(defineProps<Props>(), {
  variant: 'default',
  size: 'md',
  mono: false,
})

const trendIcon: Record<string, string> = {
  up: '▲',
  down: '▼',
  flat: '—',
}

const trendClass: Record<string, string> = {
  up: 'text-ui-good',
  down: 'text-ui-bad',
  flat: 'text-slate',
}
</script>

<template>
  <div class="cyber-stat" :class="[`size-${size}`]">
    <span class="stat-label">{{ label }}</span>
    <div class="stat-value-row">
      <span 
        class="stat-value" 
        :class="[
          `variant-${variant}`,
          mono ? 'font-nums' : ''
        ]"
      >
        {{ value }}
      </span>
      <span 
        v-if="trend" 
        class="stat-trend"
        :class="trendClass[trend]"
        :aria-label="`Trend: ${trend}`"
      >
        {{ trendIcon[trend] }}
      </span>
    </div>
    <slot></slot>
  </div>
</template>

<style scoped>
.cyber-stat {
  display: flex;
  flex-direction: column;
  gap: var(--space-xs);
}

.stat-label {
  color: var(--color-slate);
  text-transform: uppercase;
  letter-spacing: 0.15em;
  font-weight: 600;
}

.stat-value-row {
  display: flex;
  align-items: baseline;
  gap: var(--space-sm);
}

.stat-value {
  font-weight: 700;
  text-shadow: 1px 1px 0 rgba(0, 0, 0, 0.8);
}

.stat-trend {
  font-weight: 700;
}

/* Sizes */
.size-sm .stat-label { font-size: clamp(8px, 1.5vmin, 12px); }
.size-sm .stat-value { font-size: clamp(11px, 2.5vmin, 20px); }
.size-sm .stat-trend { font-size: clamp(8px, 1.5vmin, 12px); }

.size-md .stat-label { font-size: clamp(9px, 2vmin, 14px); }
.size-md .stat-value { font-size: clamp(14px, 3.5vmin, 28px); }
.size-md .stat-trend { font-size: clamp(9px, 2vmin, 14px); }

.size-lg .stat-label { font-size: clamp(10px, 2.2vmin, 16px); }
.size-lg .stat-value { font-size: clamp(18px, 4.5vmin, 36px); }
.size-lg .stat-trend { font-size: clamp(10px, 2.2vmin, 16px); }

/* Variants */
.variant-default { color: #fff; }
.variant-good { color: var(--color-ui-good); }
.variant-warn { color: var(--color-ui-warn); }
.variant-bad { color: var(--color-ui-bad); }
.variant-info { color: var(--color-ui-info); }
</style>

<script setup lang="ts">
interface Props {
  label: string
  value: string | number
  subText?: string
  subClass?: string
  /** Colored trend arrow */
  trend?: 'up' | 'down' | 'flat'
  /** Highlight the row (e.g., for personal bests) */
  highlighted?: boolean
}

withDefaults(defineProps<Props>(), {
  highlighted: false,
})

const trendIcon: Record<string, string> = {
  up: '▲',
  down: '▼',
  flat: '—',
}

const trendColor: Record<string, string> = {
  up: 'text-ui-good',
  down: 'text-ui-bad',
  flat: 'text-slate',
}
</script>

<template>
  <div 
    class="pitwall-metric-row" 
    :class="{ highlighted }"
    role="listitem"
  >
    <div class="metric-label">
      <slot name="icon"></slot>
      <span>{{ label }}</span>
    </div>
    <span class="metric-value">{{ value }}</span>
    <div class="metric-sub">
      <span 
        v-if="trend" 
        class="metric-trend"
        :class="trendColor[trend]"
        :aria-label="trend === 'up' ? 'Improved' : trend === 'down' ? 'Regressed' : 'Stable'"
      >{{ trendIcon[trend] }}</span>
      <span v-if="subText" :class="subClass">{{ subText }}</span>
    </div>
  </div>
</template>

<style scoped>
.pitwall-metric-row {
  display: grid;
  grid-template-columns: auto 1fr auto;
  align-items: center;
  gap: var(--space-sm);
  padding: var(--space-xs) 0;
  border-bottom: 1px solid color-mix(in srgb, var(--color-slate) 20%, transparent);
  font-size: clamp(11px, calc(2.3vmin * var(--app-scale)), 22px);
  transition: background-color var(--duration-fast) ease;
}

.pitwall-metric-row.highlighted {
  background: linear-gradient(90deg, rgba(78, 205, 196, 0.08) 0%, transparent 100%);
  border-bottom-color: color-mix(in srgb, var(--color-ui-good) 30%, transparent);
}


.metric-label {
  display: flex;
  align-items: center;
  gap: var(--space-xs, clamp(2px, 0.5vmin, 4px));
  color: var(--color-silver);
  white-space: nowrap;
}

.metric-value {
  text-align: center;
  font-weight: 700;
  color: #fff;
}

.metric-sub {
  text-align: right;
  display: flex;
  align-items: center;
  gap: var(--space-xs, clamp(2px, 0.5vmin, 4px));
  white-space: nowrap;
}

.metric-trend {
  font-size: 0.75em;
  font-weight: 700;
}
</style>

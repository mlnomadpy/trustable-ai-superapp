<script setup lang="ts">
interface Props {
  variant?: 'good' | 'bad' | 'warn' | 'info' | 'ghost'
  pulse?: boolean
}

withDefaults(defineProps<Props>(), {
  variant: 'info',
  pulse: false
})
</script>

<template>
  <span 
    class="cyber-badge"
    :class="[variant, { 'animate-pulse': pulse }]"
  >
    <slot></slot>
  </span>
</template>

<style scoped>
.cyber-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: clamp(4px, 1vw, 8px);
  padding: clamp(2px, 0.5vh, 6px) clamp(8px, 1.5vw, 16px);
  font-family: var(--font-ui);
  font-weight: 700;
  font-size: clamp(10px, 2.2vmin, 18px);
  text-transform: uppercase;
  letter-spacing: 1px;
  clip-path: polygon(4px 0, 100% 0, calc(100% - 4px) 100%, 0 100%);
  border: 1px solid transparent;
  transition: all 0.2s ease;
}

/* Variants */
.cyber-badge.good {
  color: var(--color-ui-good, #4ecdc4);
  background: rgba(78, 205, 196, 0.1);
  border-color: rgba(78, 205, 196, 0.4);
  text-shadow: 0 0 6px rgba(78, 205, 196, 0.6);
}

.cyber-badge.bad {
  color: var(--color-ui-bad, #ff4757);
  background: rgba(255, 71, 87, 0.1);
  border-color: rgba(255, 71, 87, 0.4);
  text-shadow: 0 0 6px rgba(255, 71, 87, 0.6);
}

.cyber-badge.warn {
  color: var(--color-ui-warn, #feca57);
  background: rgba(254, 202, 87, 0.1);
  border-color: rgba(254, 202, 87, 0.4);
  text-shadow: 0 0 6px rgba(254, 202, 87, 0.6);
}

.cyber-badge.info {
  color: var(--color-ui-info, #45b7d1);
  background: rgba(69, 183, 209, 0.1);
  border-color: rgba(69, 183, 209, 0.4);
  text-shadow: 0 0 6px rgba(69, 183, 209, 0.6);
}

.cyber-badge.ghost {
  color: #fff;
  background: transparent;
  border-color: rgba(255, 255, 255, 0.2);
}
</style>

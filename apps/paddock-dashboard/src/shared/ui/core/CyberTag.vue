<script setup lang="ts">
interface Props {
  variant?: 'slate' | 'info' | 'good' | 'warn' | 'bad'
  interactive?: boolean
}

withDefaults(defineProps<Props>(), {
  variant: 'slate',
  interactive: false
})
</script>

<template>
  <span 
    class="cyber-tag"
    :class="[`variant-${variant}`, { interactive }]"
  >
    <slot></slot>
  </span>
</template>

<style scoped>
.cyber-tag {
  display: inline-flex;
  align-items: center;
  font-family: var(--font-mono, monospace);
  font-size: 0.9em;
  padding: 2px 6px;
  border: 1px solid transparent;
  background-color: var(--color-charcoal, #1a1d28);
  white-space: nowrap;
  vertical-align: middle;
  border-radius: 2px;
}

/* Variants */
.variant-slate {
  color: var(--color-silver, #bdc3c7);
  border-color: var(--color-slate, #2c3e50);
}

.variant-info {
  color: var(--color-ui-info, #45b7d1);
  border-color: rgba(69, 183, 209, 0.5);
  background-color: rgba(69, 183, 209, 0.1);
}

.variant-good {
  color: var(--color-ui-good, #4ecdc4);
  border-color: rgba(78, 205, 196, 0.5);
  background-color: rgba(78, 205, 196, 0.1);
}

.variant-warn {
  color: var(--color-ui-warn, #feca57);
  border-color: rgba(254, 202, 87, 0.5);
  background-color: rgba(254, 202, 87, 0.1);
}

.variant-bad {
  color: var(--color-ui-bad, #ff4757);
  border-color: rgba(255, 71, 87, 0.5);
  background-color: rgba(255, 71, 87, 0.1);
}

.interactive {
  cursor: pointer;
  transition: all 0.2s ease;
}

.interactive:hover {
  filter: brightness(1.2);
  transform: translateY(-1px);
}
</style>

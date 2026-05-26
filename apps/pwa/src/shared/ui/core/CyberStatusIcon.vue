<script setup lang="ts">
/**
 * CyberStatusIcon — Reusable status indicator SVG icon.
 * Used for quest goals, task lists, checklist items, etc.
 */
withDefaults(defineProps<{
  /** Status to display */
  status: 'success' | 'pending' | 'failed' | 'locked'
  /** Size override */
  size?: string
}>(), {
  size: 'clamp(16px, 3.5vmin, 24px)',
})
</script>

<template>
  <svg 
    class="cyber-status-icon" 
    :style="{ width: size, height: size }" 
    viewBox="0 0 20 20" 
    fill="none"
    :aria-label="status"
    role="img"
  >
    <!-- Success: Green checkmark in circle -->
    <template v-if="status === 'success'">
      <circle cx="10" cy="10" r="9" fill="rgba(78,205,196,0.15)" stroke="var(--color-ui-good)" stroke-width="1.5"/>
      <polyline points="6,10.5 9,13.5 14,7" fill="none" stroke="var(--color-ui-good)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
    </template>

    <!-- Pending: Animated progress ring -->
    <template v-else-if="status === 'pending'">
      <circle cx="10" cy="10" r="9" fill="rgba(69,183,209,0.08)" stroke="var(--color-slate)" stroke-width="1"/>
      <circle cx="10" cy="10" r="9" fill="none" stroke="var(--color-ui-info)" stroke-width="1.5" stroke-dasharray="14 42" stroke-linecap="round">
        <animateTransform attributeName="transform" type="rotate" from="0 10 10" to="360 10 10" dur="3s" repeatCount="indefinite"/>
      </circle>
      <circle cx="10" cy="10" r="2" fill="var(--color-ui-info)" opacity="0.6"/>
    </template>

    <!-- Failed: Red X in circle -->
    <template v-else-if="status === 'failed'">
      <circle cx="10" cy="10" r="9" fill="rgba(255,71,87,0.1)" stroke="var(--color-ui-bad)" stroke-width="1.5"/>
      <line x1="7" y1="7" x2="13" y2="13" stroke="var(--color-ui-bad)" stroke-width="2" stroke-linecap="round"/>
      <line x1="13" y1="7" x2="7" y2="13" stroke="var(--color-ui-bad)" stroke-width="2" stroke-linecap="round"/>
    </template>

    <!-- Locked: Dashed ring with lock -->
    <template v-else>
      <circle cx="10" cy="10" r="9" fill="none" stroke="var(--color-slate)" stroke-width="1" stroke-dasharray="3 3" opacity="0.5"/>
      <rect x="7.5" y="10" width="5" height="4" rx="0.5" fill="var(--color-slate)" opacity="0.5"/>
      <path d="M8.5 10V8.5a1.5 1.5 0 0 1 3 0V10" fill="none" stroke="var(--color-slate)" stroke-width="1" opacity="0.5"/>
    </template>
  </svg>
</template>

<style scoped>
.cyber-status-icon {
  flex-shrink: 0;
  display: block;
}
</style>

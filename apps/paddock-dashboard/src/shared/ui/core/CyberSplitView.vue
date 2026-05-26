<script setup lang="ts">
interface Props {
  split?: '50-50' | '30-70' | '40-60' | '60-40' | '70-30'
  gap?: 'sm' | 'md' | 'lg'
}

withDefaults(defineProps<Props>(), {
  split: '50-50',
  gap: 'md'
})
</script>

<template>
  <div 
    class="cyber-split-view w-full h-full flex flex-col md:flex-row"
    :class="[`gap-${gap}`, `split-${split}`]"
  >
    <div class="split-pane pane-left">
      <slot name="left"></slot>
    </div>
    <div class="split-pane pane-right">
      <slot name="right"></slot>
    </div>
  </div>
</template>

<style scoped>
.cyber-split-view {
  min-height: 0; /* allows flex children to shrink */
}

.gap-sm { gap: clamp(8px, 2vmin, 16px); }
.gap-md { gap: clamp(16px, 3vmin, 24px); }
.gap-lg { gap: clamp(24px, 4vmin, 32px); }

.split-pane {
  flex-grow: 1;
  display: flex;
  flex-direction: column;
  min-height: 0; /* crucial for nested scrolling */
}

/* On mobile (default flex-col), panes just stack. On md (flex-row), we apply split ratios */
@media (min-width: 768px) {
  .split-50-50 .pane-left { flex: 1 1 50%; max-width: 50%; }
  .split-50-50 .pane-right { flex: 1 1 50%; max-width: 50%; }

  .split-30-70 .pane-left { flex: 1 1 30%; max-width: 30%; }
  .split-30-70 .pane-right { flex: 1 1 70%; max-width: 70%; }

  .split-40-60 .pane-left { flex: 1 1 40%; max-width: 40%; }
  .split-40-60 .pane-right { flex: 1 1 60%; max-width: 60%; }

  .split-60-40 .pane-left { flex: 1 1 60%; max-width: 60%; }
  .split-60-40 .pane-right { flex: 1 1 40%; max-width: 40%; }

  .split-70-30 .pane-left { flex: 1 1 70%; max-width: 70%; }
  .split-70-30 .pane-right { flex: 1 1 30%; max-width: 30%; }
}
</style>

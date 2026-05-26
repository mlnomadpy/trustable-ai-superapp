<script setup lang="ts">
interface Props {
  /** Background style */
  variant?: 'solid' | 'glass' | 'ghost'
  /** Border accent color */
  border?: 'primary' | 'secondary' | 'warn' | 'none'
  /** Enable hover/active states */
  interactive?: boolean
  /** Enable entry animation */
  animate?: boolean
  /** Internal padding preset */
  size?: 'compact' | 'default' | 'spacious'
  /** Accessible label for the panel region */
  label?: string
}

withDefaults(defineProps<Props>(), {
  variant: 'solid',
  border: 'primary',
  interactive: false,
  animate: true,
  size: 'default',
})
</script>

<template>
  <div 
    class="cyber-panel"
    :class="[
      variant, 
      `border-${border}`, 
      `size-${size}`,
      { interactive, 'arcade-hover': interactive, 'panel-animate': animate }
    ]"
    :role="label ? 'region' : undefined"
    :aria-label="label"
  >
    <!-- Optional header slot -->
    <div v-if="$slots.header" class="panel-header">
      <slot name="header"></slot>
    </div>

    <div class="panel-content">
      <slot></slot>
    </div>

    <!-- Optional footer slot -->
    <div v-if="$slots.footer" class="panel-footer">
      <slot name="footer"></slot>
    </div>
  </div>
</template>

<style scoped>
.cyber-panel {
  position: relative;
  width: 100%;
  height: 100%;
  color: inherit;
  transition: all var(--duration-fast, 150ms) ease-out;
  /* GPU-friendly clip-path for cut corners */
  clip-path: polygon(
    8px 0,
    100% 0,
    100% calc(100% - 8px),
    calc(100% - 8px) 100%,
    0 100%,
    0 8px
  );
  z-index: var(--z-content, 1);
}

/* Size presets */
.size-compact { padding: var(--space-sm, clamp(4px, 1vmin, 8px)); }
.size-default { padding: var(--space-md, clamp(8px, 2vmin, 16px)); }
.size-spacious { padding: var(--space-lg, clamp(16px, 3vmin, 24px)); }

.panel-content {
  position: relative;
  z-index: 5;
  width: 100%;
  height: 100%;
}

.panel-header {
  position: relative;
  z-index: 5;
  padding-bottom: var(--space-xs, clamp(2px, 0.5vmin, 4px));
  margin-bottom: var(--space-sm, clamp(4px, 1vmin, 8px));
  border-bottom: 1px solid var(--color-slate);
}

.panel-footer {
  position: relative;
  z-index: 5;
  padding-top: var(--space-xs, clamp(2px, 0.5vmin, 4px));
  margin-top: var(--space-sm, clamp(4px, 1vmin, 8px));
  border-top: 1px solid var(--color-slate);
}

/* Base variants */
.cyber-panel.solid {
  background: color-mix(in srgb, var(--color-ink) 95%, transparent);
}

.cyber-panel.glass {
  background: color-mix(in srgb, var(--color-ink) 85%, transparent);
  backdrop-filter: blur(4px);
}

.cyber-panel.ghost {
  background: transparent;
}

/* Border pseudo-element */
.cyber-panel::after {
  content: '';
  position: absolute;
  inset: 0;
  pointer-events: none;
  z-index: 2;
  transition: border-color var(--duration-fast, 150ms) ease;
  clip-path: polygon(
    8px 0,
    100% 0,
    100% calc(100% - 8px),
    calc(100% - 8px) 100%,
    0 100%,
    0 8px
  );
}

.cyber-panel.border-primary::after {
  border: 2px solid color-mix(in srgb, var(--color-ui-good) 50%, transparent);
  border-bottom: 4px solid color-mix(in srgb, var(--color-ui-good) 80%, transparent);
}

.cyber-panel.border-secondary::after {
  border: 2px solid color-mix(in srgb, var(--color-slate) 40%, transparent);
  border-bottom: 4px solid color-mix(in srgb, var(--color-slate) 60%, transparent);
}

.cyber-panel.border-warn::after {
  border: 2px solid color-mix(in srgb, var(--color-ui-bad) 50%, transparent);
  border-bottom: 4px solid color-mix(in srgb, var(--color-ui-bad) 80%, transparent);
}

.cyber-panel.border-none::after {
  border: none;
}

/* Scanline texture */
.cyber-panel::before {
  content: '';
  position: absolute;
  inset: 0;
  pointer-events: none;
  background: repeating-linear-gradient(
    0deg,
    transparent,
    transparent 2px,
    rgba(255, 255, 255, 0.02) 2px,
    rgba(255, 255, 255, 0.02) 4px
  );
  z-index: 1;
}

/* Interactivity */
.cyber-panel.interactive:hover {
  transform: translateY(-2px);
}

.cyber-panel.interactive.border-primary:hover::after {
  border-color: var(--color-ui-good);
  box-shadow: inset 0 0 20px rgba(78, 205, 196, 0.2);
}

.cyber-panel.interactive.border-secondary:hover::after {
  border-color: var(--color-silver);
  box-shadow: inset 0 0 20px rgba(149, 165, 166, 0.2);
}

.cyber-panel.interactive.border-warn:hover::after {
  border-color: var(--color-ui-bad);
  box-shadow: inset 0 0 20px rgba(255, 71, 87, 0.2);
}

@keyframes panel-fade-up {
  0% { opacity: 0; transform: translateY(10px); }
  100% { opacity: 1; transform: translateY(0); }
}

.cyber-panel.panel-animate {
  animation: panel-fade-up 0.4s var(--ease-smooth, cubic-bezier(0.25, 1, 0.5, 1)) both;
}
</style>

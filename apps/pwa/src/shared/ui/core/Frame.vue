<script setup lang="ts">
/**
 * 9-slice frame component for the GBA aesthetic.
 * Uses border-image with pixelated rendering.
 */
interface Props {
  variant?: 'default' | 'dialogue' | 'card' | 'inset'
  padding?: string
  /** If provided, frame becomes a focusable interactive element */
  tabindex?: number
  ariaLabel?: string
}

withDefaults(defineProps<Props>(), {
  variant: 'default'
})
</script>

<template>
  <div 
    :class="['frame', `frame-${variant}`]" 
    :style="padding ? { padding } : {}"
    :tabindex="tabindex"
    :role="tabindex !== undefined ? 'region' : undefined"
    :aria-label="ariaLabel"
  >
    <slot />
  </div>
</template>

<style scoped>
.frame {
  image-rendering: pixelated;
  border-style: solid;
  position: relative;
  /* Default padding using logical scale */
  padding: var(--space-md);
  outline: none;
}

.frame:focus-visible {
  box-shadow: var(--shadow-focus);
  z-index: 10;
}

.frame-default {
  border-width: clamp(4px, calc(1vmin * var(--app-scale)), 8px);
  border-image: url('/sprites/ui/frame-default.png') 8 fill / 16px / 0 stretch;
}


.frame-dialogue {
  border-width: clamp(6px, calc(1.5vmin * var(--app-scale)), 12px);
  border-image: url('/sprites/ui/frame-dialogue.png') 12 fill / 24px / 0 stretch;
}

.frame-card {
  border-width: clamp(4px, calc(1vmin * var(--app-scale)), 8px);
  border-image: url('/sprites/ui/frame-card.png') 8 fill / 16px / 0 stretch;
}

.frame-inset {
  border-width: clamp(2px, calc(0.5vmin * var(--app-scale)), 4px);
  border-image: url('/sprites/ui/frame-inset.png') 4 fill / 8px / 0 stretch;
}
</style>


<script setup lang="ts">
import Sprite from '@/entities/coach/Sprite.vue'

withDefaults(defineProps<{
  sheet: string
  animation?: string
  size?: 'sm' | 'md' | 'lg' | 'xl'
  variant?: 'default' | 'ghost' | 'glow'
}>(), {
  animation: 'idle',
  size: 'md',
  variant: 'default'
})
</script>

<template>
  <div 
    class="cyber-avatar relative overflow-hidden flex items-center justify-center flex-shrink-0"
    :class="[
      `size-${size}`,
      `variant-${variant}`
    ]"
  >
    <div v-if="variant === 'glow'" class="absolute inset-0 z-0 bg-ui-info opacity-20 pointer-events-none" style="background: radial-gradient(circle at center, rgba(42, 161, 152, 0.4) 0%, transparent 70%);"></div>
    <Sprite :sheet="sheet" :animation="animation" class="z-10 relative sprite-inner origin-bottom" />
  </div>
</template>

<style scoped>
.cyber-avatar {
  background: var(--color-ink);
  border: 2px solid var(--color-slate);
  box-shadow: 4px 4px 0 rgba(0,0,0,0.8);
}

.variant-ghost {
  background: transparent;
  border: none;
  box-shadow: none;
}

.size-sm {
  width: clamp(32px, 8vmin, 48px);
  height: clamp(32px, 8vmin, 48px);
}

.size-md {
  width: clamp(48px, 12vmin, 80px);
  height: clamp(48px, 12vmin, 80px);
}

.size-lg {
  width: clamp(56px, 16vmin, 100px);
  height: clamp(56px, 16vmin, 100px);
}

.size-xl {
  width: clamp(100px, 25vw, 200px);
  height: clamp(100px, 25vw, 200px);
}

.size-sm .sprite-inner { transform: scale(1); }
.size-md .sprite-inner { transform: scale(1.5); }
.size-lg .sprite-inner { transform: scale(2); }
.size-xl .sprite-inner { transform: scale(3.5); }
</style>

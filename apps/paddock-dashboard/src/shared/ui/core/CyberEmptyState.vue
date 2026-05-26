<script setup lang="ts">
interface Props {
  /** Emoji or single character icon */
  icon?: string
  /** Primary empty state message */
  title: string
  /** Supporting description text */
  description?: string
  /** Label for the CTA button */
  actionLabel?: string
}

withDefaults(defineProps<Props>(), {
  icon: '🏁',
})

const emit = defineEmits<{
  (e: 'action'): void
}>()
</script>

<template>
  <div class="cyber-empty-state" role="status">
    <div class="empty-icon" aria-hidden="true">{{ icon }}</div>
    <h3 class="empty-title">{{ title }}</h3>
    <p v-if="description" class="empty-desc">{{ description }}</p>
    <button 
      v-if="actionLabel" 
      class="empty-action"
      @click="emit('action')"
    >
      {{ actionLabel }}
    </button>
    <slot></slot>
  </div>
</template>

<style scoped>
.cyber-empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: var(--space-xl) var(--space-lg);
  gap: var(--space-sm);
  min-height: clamp(120px, 20vh, 240px);
}

.empty-icon {
  font-size: clamp(32px, 8vmin, 64px);
  line-height: 1;
  opacity: 0.6;
  filter: grayscale(0.3);
  animation: float 3s ease-in-out infinite;
}

.empty-title {
  font-family: var(--font-title);
  font-size: clamp(12px, 2.5vmin, 20px);
  color: var(--color-silver);
  letter-spacing: 0.15em;
  text-transform: uppercase;
  margin: 0;
}

.empty-desc {
  font-size: clamp(10px, 2vmin, 16px);
  color: var(--color-slate);
  max-width: 36ch;
  line-height: 1.5;
  margin: 0;
}

.empty-action {
  margin-top: var(--space-sm);
  padding: var(--space-xs) var(--space-md);
  background: transparent;
  border: 1px solid var(--color-ui-good);
  color: var(--color-ui-good);
  font-family: var(--font-title);
  font-size: clamp(10px, 2vmin, 14px);
  letter-spacing: 0.1em;
  text-transform: uppercase;
  cursor: pointer;
  transition: all var(--duration-fast) ease;
  clip-path: polygon(
    6px 0, 100% 0,
    100% calc(100% - 6px), calc(100% - 6px) 100%,
    0 100%, 0 6px
  );
}

.empty-action:hover {
  background: rgba(78, 205, 196, 0.15);
  box-shadow: 0 0 12px rgba(78, 205, 196, 0.3);
}

.empty-action:active {
  transform: translateY(1px);
}

@keyframes float {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-6px); }
}

@media (prefers-reduced-motion: reduce) {
  .empty-icon {
    animation: none;
  }
}
</style>

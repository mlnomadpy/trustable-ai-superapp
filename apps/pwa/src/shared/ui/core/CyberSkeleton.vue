<script setup lang="ts">
interface Props {
  /** Shape of the skeleton placeholder */
  variant?: 'text' | 'row' | 'chart' | 'card' | 'stat' | 'circle'
  /** Number of lines (for text variant) or repeated rows */
  lines?: number
  /** Number of repeated skeleton items */
  count?: number
  /** Enable shimmer animation */
  animated?: boolean
}

withDefaults(defineProps<Props>(), {
  variant: 'text',
  lines: 3,
  count: 1,
  animated: true,
})
</script>

<template>
  <div 
    class="cyber-skeleton-wrapper" 
    role="status"
    aria-label="Loading content"
  >
    <div v-for="n in count" :key="n" class="skeleton-item">
      <!-- Text lines -->
      <template v-if="variant === 'text'">
        <div 
          v-for="i in lines" 
          :key="i" 
          class="skeleton-line"
          :class="{ shimmer: animated }"
          :style="{ width: i === lines ? '60%' : '100%' }"
        ></div>
      </template>

      <!-- Row (list item) -->
      <template v-else-if="variant === 'row'">
        <div class="skeleton-row" :class="{ shimmer: animated }">
          <div class="skeleton-circle-sm"></div>
          <div class="skeleton-row-content">
            <div class="skeleton-line" style="width: 40%"></div>
            <div class="skeleton-line short" style="width: 70%"></div>
          </div>
        </div>
      </template>

      <!-- Chart -->
      <template v-else-if="variant === 'chart'">
        <div class="skeleton-chart" :class="{ shimmer: animated }">
          <div class="skeleton-bar" style="height: 60%"></div>
          <div class="skeleton-bar" style="height: 80%"></div>
          <div class="skeleton-bar" style="height: 40%"></div>
          <div class="skeleton-bar" style="height: 90%"></div>
          <div class="skeleton-bar" style="height: 55%"></div>
          <div class="skeleton-bar" style="height: 70%"></div>
        </div>
      </template>

      <!-- Card -->
      <template v-else-if="variant === 'card'">
        <div class="skeleton-card" :class="{ shimmer: animated }">
          <div class="skeleton-card-top"></div>
          <div class="skeleton-card-body">
            <div class="skeleton-line" style="width: 70%"></div>
            <div class="skeleton-line short" style="width: 50%"></div>
          </div>
        </div>
      </template>

      <!-- Stat -->
      <template v-else-if="variant === 'stat'">
        <div class="skeleton-stat" :class="{ shimmer: animated }">
          <div class="skeleton-line short" style="width: 50%"></div>
          <div class="skeleton-line tall" style="width: 80%"></div>
        </div>
      </template>

      <!-- Circle -->
      <template v-else-if="variant === 'circle'">
        <div class="skeleton-circle" :class="{ shimmer: animated }"></div>
      </template>
    </div>
  </div>
</template>

<style scoped>
.cyber-skeleton-wrapper {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: var(--space-md);
}

.skeleton-item {
  width: 100%;
}

/* Base shapes */
.skeleton-line {
  height: clamp(8px, 1.5vmin, 12px);
  border-radius: 2px;
  background: var(--color-charcoal);
  margin-bottom: var(--space-xs);
}

.skeleton-line.short {
  height: clamp(6px, 1.2vmin, 10px);
}

.skeleton-line.tall {
  height: clamp(16px, 3vmin, 24px);
}

.skeleton-circle-sm {
  width: clamp(20px, 4vmin, 32px);
  height: clamp(20px, 4vmin, 32px);
  border-radius: 50%;
  background: var(--color-charcoal);
  flex-shrink: 0;
}

.skeleton-circle {
  width: clamp(48px, 10vmin, 80px);
  height: clamp(48px, 10vmin, 80px);
  border-radius: 50%;
  background: var(--color-charcoal);
}

/* Composite shapes */
.skeleton-row {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  padding: var(--space-xs) 0;
  border-bottom: 1px solid rgba(69, 162, 158, 0.1);
}

.skeleton-row-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: var(--space-xs);
}

.skeleton-chart {
  display: flex;
  align-items: flex-end;
  gap: var(--space-xs);
  height: clamp(60px, 15vmin, 120px);
  padding-top: var(--space-sm);
}

.skeleton-bar {
  flex: 1;
  background: var(--color-charcoal);
  border-radius: 2px 2px 0 0;
  min-width: clamp(12px, 3vmin, 24px);
}

.skeleton-card {
  border: 1px solid var(--color-charcoal);
  overflow: hidden;
}

.skeleton-card-top {
  height: clamp(40px, 8vmin, 60px);
  background: var(--color-charcoal);
}

.skeleton-card-body {
  padding: var(--space-sm);
  display: flex;
  flex-direction: column;
  gap: var(--space-xs);
}

.skeleton-stat {
  display: flex;
  flex-direction: column;
  gap: var(--space-xs);
}

/* Shimmer animation */
@keyframes shimmer {
  0% { background-position: -200% 0; }
  100% { background-position: 200% 0; }
}

.shimmer,
.shimmer .skeleton-line,
.shimmer .skeleton-circle-sm,
.shimmer .skeleton-bar,
.shimmer .skeleton-card-top,
.shimmer.skeleton-circle {
  background: linear-gradient(
    90deg,
    var(--color-charcoal) 25%,
    rgba(69, 162, 158, 0.08) 50%,
    var(--color-charcoal) 75%
  );
  background-size: 200% 100%;
  animation: shimmer 1.5s ease-in-out infinite;
}

@media (prefers-reduced-motion: reduce) {
  .shimmer,
  .shimmer .skeleton-line,
  .shimmer .skeleton-circle-sm,
  .shimmer .skeleton-bar,
  .shimmer .skeleton-card-top,
  .shimmer.skeleton-circle {
    animation: none;
    background: var(--color-charcoal);
  }
}
</style>

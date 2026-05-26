<script setup lang="ts">
import CyberBox from './CyberBox.vue'

interface Props {
  title?: string
  subText?: string
  focused?: boolean
  locked?: boolean
  showKerb?: boolean
  variant?: 'ink' | 'charcoal' | 'glass'
}

withDefaults(defineProps<Props>(), {
  focused: false,
  locked: false,
  showKerb: false,
  variant: 'ink'
})

const emit = defineEmits<{ (e: 'click'): void; (e: 'hover'): void }>()
</script>

<template>
  <CyberBox 
    :variant="focused ? 'charcoal' : variant" 
    :border="focused ? 'good' : 'slate'"
    interactive
    :class="['cyber-tile', { locked, focused }]"
    :aria-disabled="locked || undefined"
    :role="locked ? undefined : 'button'"
    @click="$emit('click')"
    @mouseenter="$emit('hover')"
  >
    <!-- Focus Marker -->
    <div v-if="focused && !locked" class="focus-marker" aria-hidden="true">▼</div>
    
    <!-- Kerb Accent -->
    <div v-if="showKerb && focused" class="tile-kerb" aria-hidden="true"></div>

    <!-- Badge slot (top-right) -->
    <div v-if="$slots.badge" class="tile-badge">
      <slot name="badge"></slot>
    </div>
    
    <div class="tile-content w-full h-full flex flex-col justify-center">
      <slot>
        <!-- Default layout if no slot provided -->
        <div class="tile-inner">
          <!-- Icon slot -->
          <div v-if="$slots.icon" class="tile-icon" aria-hidden="true">
            <slot name="icon"></slot>
          </div>
          <div class="tile-text">
            <div class="font-bold text-body flex items-center pixel-shadow">
              <span v-if="focused" class="text-curb-red mr-1 cursor-bounce" aria-hidden="true">▶</span>
              {{ title }}
            </div>
            <div v-if="subText" class="text-body text-silver ml-3">{{ subText }}</div>
          </div>
        </div>
      </slot>
    </div>

    <!-- Lock Overlay -->
    <div v-if="locked" class="lock-overlay" aria-hidden="true">
      <span class="lock-badge">
        <!-- SVG lock icon instead of emoji for cross-platform consistency -->
        <svg class="lock-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
          <rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect>
          <path d="M7 11V7a5 5 0 0 1 10 0v4"></path>
        </svg>
        LOCKED
      </span>
    </div>
  </CyberBox>
</template>

<style scoped>
.cyber-tile {
  width: 100%;
  height: 100%;
  padding: clamp(6px, 1.5vmin, 16px);
  overflow: hidden;
  position: relative;
}

.cyber-tile.locked {
  opacity: 0.4;
  filter: saturate(0.2) brightness(0.7);
  pointer-events: none;
}

.tile-inner {
  display: flex;
  align-items: center;
  gap: var(--space-sm, clamp(4px, 1vmin, 8px));
}

.tile-icon {
  flex-shrink: 0;
  width: clamp(20px, 4vmin, 32px);
  height: clamp(20px, 4vmin, 32px);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--color-slate);
}

.tile-text {
  flex: 1;
  min-width: 0;
}

.tile-badge {
  position: absolute;
  top: clamp(4px, 1vmin, 8px);
  right: clamp(4px, 1vmin, 8px);
  z-index: 15;
}

.tile-kerb {
  position: absolute;
  bottom: 0;
  left: 0;
  width: 100%;
  height: clamp(3px, 0.6vmin, 5px);
  background: repeating-linear-gradient(
    90deg,
    #c93838 0,
    #c93838 clamp(4px, 1vmin, 8px),
    #f5f5e8 clamp(4px, 1vmin, 8px),
    #f5f5e8 clamp(8px, 2vmin, 16px)
  );
  z-index: 10;
}

.focus-marker {
  position: absolute;
  top: clamp(2px, 0.5vmin, 6px);
  left: clamp(6px, 1.5vmin, 14px);
  color: var(--color-ui-good);
  font-size: clamp(8px, 1.8vmin, 14px);
  text-shadow: 1px 1px 0 rgba(0, 0, 0, 0.8);
  animation: retro-blink 1s steps(2) infinite;
  z-index: 10;
}

.lock-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: color-mix(in srgb, var(--color-ink) 50%, transparent);
  z-index: 20;
}

.lock-badge {
  background: var(--color-charcoal);
  padding: var(--space-xs) var(--space-sm);
  font-size: clamp(9px, 2vmin, 14px);
  border: 1px solid var(--color-slate);
  display: flex;
  align-items: center;
  gap: var(--space-xs);
  color: var(--color-silver);
}

.lock-icon {
  width: clamp(12px, 2.5vmin, 18px);
  height: clamp(12px, 2.5vmin, 18px);
}

@keyframes retro-blink {
  0%, 100% { opacity: 0; }
  50% { opacity: 1; }
}
</style>

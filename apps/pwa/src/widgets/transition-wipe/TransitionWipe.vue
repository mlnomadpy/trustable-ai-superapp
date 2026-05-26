<script setup lang="ts">
import { computed } from 'vue'
import { useTransitionStore } from '@/shared/lib/transition/transitionStore'

const trans = useTransitionStore()

const overlayClass = computed(() => {
  if (!trans.inProgress || !trans.direction) return ''
  return `wipe-${trans.direction}`
})
</script>

<template>
  <Transition name="wipe-overlay">
    <div 
      v-if="trans.inProgress" 
      class="wipe-overlay"
      :class="overlayClass"
      aria-hidden="true"
    >
      <!-- Checkered wipe pattern -->
      <div class="wipe-fill"></div>
      <div class="wipe-edge"></div>
    </div>
  </Transition>
</template>

<style scoped>
.wipe-overlay {
  position: fixed;
  inset: 0;
  z-index: 999;
  pointer-events: none;
  overflow: hidden;
}

.wipe-fill {
  position: absolute;
  inset: 0;
  background: var(--color-ink);
}

.wipe-edge {
  position: absolute;
  background: repeating-linear-gradient(
    90deg,
    var(--color-curb-red, #c93838) 0,
    var(--color-curb-red, #c93838) 8px,
    var(--color-curb-white, #f5f5e8) 8px,
    var(--color-curb-white, #f5f5e8) 16px
  );
}

/* ── RIGHT wipe (default forward nav) ── */
.wipe-right .wipe-fill {
  animation: slide-in-right 300ms cubic-bezier(0.25, 1, 0.5, 1) both;
}
.wipe-right .wipe-edge {
  top: 0; bottom: 0; left: 0; width: 6px;
  animation: slide-in-right 300ms cubic-bezier(0.25, 1, 0.5, 1) both;
}

/* ── LEFT wipe (back nav) ── */
.wipe-left .wipe-fill {
  animation: slide-in-left 300ms cubic-bezier(0.25, 1, 0.5, 1) both;
}
.wipe-left .wipe-edge {
  top: 0; bottom: 0; right: 0; width: 6px;
  animation: slide-in-left 300ms cubic-bezier(0.25, 1, 0.5, 1) both;
}

/* ── UP wipe (drill-down nav) ── */
.wipe-up .wipe-fill {
  animation: slide-in-up 300ms cubic-bezier(0.25, 1, 0.5, 1) both;
}
.wipe-up .wipe-edge {
  left: 0; right: 0; bottom: 0; height: 6px;
  background: repeating-linear-gradient(
    180deg,
    var(--color-curb-red, #c93838) 0,
    var(--color-curb-red, #c93838) 8px,
    var(--color-curb-white, #f5f5e8) 8px,
    var(--color-curb-white, #f5f5e8) 16px
  );
  animation: slide-in-up 300ms cubic-bezier(0.25, 1, 0.5, 1) both;
}

/* ── DOWN wipe (surface) ── */
.wipe-down .wipe-fill {
  animation: slide-in-down 300ms cubic-bezier(0.25, 1, 0.5, 1) both;
}
.wipe-down .wipe-edge {
  left: 0; right: 0; top: 0; height: 6px;
  background: repeating-linear-gradient(
    180deg,
    var(--color-curb-red, #c93838) 0,
    var(--color-curb-red, #c93838) 8px,
    var(--color-curb-white, #f5f5e8) 8px,
    var(--color-curb-white, #f5f5e8) 16px
  );
  animation: slide-in-down 300ms cubic-bezier(0.25, 1, 0.5, 1) both;
}

/* ── FADE-NIGHT (slow cinematic for EndOfDay etc.) ── */
.wipe-fade-night .wipe-fill {
  animation: fade-in 1500ms ease both;
}
.wipe-fade-night .wipe-edge {
  display: none;
}

/* ── Keyframes ── */
@keyframes slide-in-right {
  0% { transform: translateX(100%); }
  100% { transform: translateX(0); }
}

@keyframes slide-in-left {
  0% { transform: translateX(-100%); }
  100% { transform: translateX(0); }
}

@keyframes slide-in-up {
  0% { transform: translateY(100%); }
  100% { transform: translateY(0); }
}

@keyframes slide-in-down {
  0% { transform: translateY(-100%); }
  100% { transform: translateY(0); }
}

@keyframes fade-in {
  0% { opacity: 0; }
  30% { opacity: 1; }
  100% { opacity: 1; }
}

/* Vue transition hooks for the exit */
.wipe-overlay-leave-active {
  transition: opacity 150ms ease;
}
.wipe-overlay-leave-to {
  opacity: 0;
}

@media (prefers-reduced-motion: reduce) {
  .wipe-fill, .wipe-edge {
    animation: none !important;
  }
}
</style>

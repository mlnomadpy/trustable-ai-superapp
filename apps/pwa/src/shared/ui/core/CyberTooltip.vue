<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'

interface Props {
  /** Tooltip content (plain text) */
  text: string
  /** Preferred positioning */
  position?: 'top' | 'bottom' | 'left' | 'right'
  /** Trigger method */
  trigger?: 'tap' | 'hover'
  /** Auto-hide delay in ms (0 = manual close) */
  delay?: number
}

const props = withDefaults(defineProps<Props>(), {
  position: 'top',
  trigger: 'tap',
  delay: 3000,
})

const isVisible = ref(false)
let hideTimeout: number | null = null

const show = () => {
  isVisible.value = true
  if (props.delay > 0) {
    if (hideTimeout) clearTimeout(hideTimeout)
    hideTimeout = window.setTimeout(() => {
      isVisible.value = false
    }, props.delay)
  }
}

const toggle = () => {
  if (isVisible.value) {
    isVisible.value = false
    if (hideTimeout) clearTimeout(hideTimeout)
  } else {
    show()
  }
}

const hide = () => {
  isVisible.value = false
  if (hideTimeout) clearTimeout(hideTimeout)
}

onMounted(() => {
  // Close tooltip when tapping elsewhere
  document.addEventListener('touchstart', handleOutsideTouch, { passive: true })
})

onUnmounted(() => {
  document.removeEventListener('touchstart', handleOutsideTouch)
  if (hideTimeout) clearTimeout(hideTimeout)
})

const tooltipRef = ref<HTMLDivElement | null>(null)
const handleOutsideTouch = (e: TouchEvent) => {
  if (isVisible.value && tooltipRef.value && !tooltipRef.value.contains(e.target as Node)) {
    hide()
  }
}
</script>

<template>
  <div 
    ref="tooltipRef"
    class="cyber-tooltip-wrapper"
    @click="trigger === 'tap' ? toggle() : undefined"
    @mouseenter="trigger === 'hover' ? show() : undefined"
    @mouseleave="trigger === 'hover' ? hide() : undefined"
  >
    <!-- Trigger element -->
    <slot></slot>

    <!-- Tooltip bubble -->
    <Transition name="tooltip">
      <div 
        v-if="isVisible"
        class="cyber-tooltip"
        :class="`pos-${position}`"
        role="tooltip"
      >
        <div class="tooltip-content">{{ text }}</div>
        <div class="tooltip-arrow" :class="`arrow-${position}`"></div>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.cyber-tooltip-wrapper {
  position: relative;
  display: inline-flex;
  cursor: help;
}

.cyber-tooltip {
  position: absolute;
  z-index: var(--z-toast, 40);
  pointer-events: none;
  white-space: nowrap;
}

.tooltip-content {
  background: var(--color-charcoal);
  color: var(--color-silver);
  border: 1px solid var(--color-slate);
  font-family: var(--font-ui);
  font-size: clamp(9px, 2vmin, 14px);
  padding: 4px 8px;
  line-height: 1.4;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.6);
  clip-path: polygon(4px 0, 100% 0, 100% calc(100% - 4px), calc(100% - 4px) 100%, 0 100%, 0 4px);
}

.tooltip-arrow {
  position: absolute;
  width: 6px;
  height: 6px;
  background: var(--color-charcoal);
  border: 1px solid var(--color-slate);
  transform: rotate(45deg);
}

/* Positioning */
.pos-top {
  bottom: calc(100% + 8px);
  left: 50%;
  transform: translateX(-50%);
}
.pos-top .arrow-top {
  bottom: -4px;
  left: 50%;
  margin-left: -3px;
  border-top: none;
  border-left: none;
}

.pos-bottom {
  top: calc(100% + 8px);
  left: 50%;
  transform: translateX(-50%);
}
.pos-bottom .arrow-bottom {
  top: -4px;
  left: 50%;
  margin-left: -3px;
  border-bottom: none;
  border-right: none;
}

.pos-left {
  right: calc(100% + 8px);
  top: 50%;
  transform: translateY(-50%);
}
.pos-left .arrow-left {
  right: -4px;
  top: 50%;
  margin-top: -3px;
  border-bottom: none;
  border-left: none;
}

.pos-right {
  left: calc(100% + 8px);
  top: 50%;
  transform: translateY(-50%);
}
.pos-right .arrow-right {
  left: -4px;
  top: 50%;
  margin-top: -3px;
  border-top: none;
  border-right: none;
}

/* Transition */
.tooltip-enter-active {
  transition: opacity var(--duration-fast) ease, transform var(--duration-fast) ease;
}
.tooltip-leave-active {
  transition: opacity var(--duration-fast) ease;
}

.tooltip-enter-from {
  opacity: 0;
  transform: translateX(-50%) translateY(4px);
}
.tooltip-leave-to {
  opacity: 0;
}

/* Override transform for non-top positions */
.pos-bottom.tooltip-enter-from { transform: translateX(-50%) translateY(-4px); }
.pos-left.tooltip-enter-from { transform: translateY(-50%) translateX(4px); }
.pos-right.tooltip-enter-from { transform: translateY(-50%) translateX(-4px); }
</style>

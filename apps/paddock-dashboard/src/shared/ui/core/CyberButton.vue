<script setup lang="ts">
interface Props {
  disabled?: boolean
  subText?: string
  variant?: 'primary' | 'secondary' | 'info' | 'dark' | 'danger'
  size?: 'sm' | 'md' | 'lg'
  fluid?: boolean
  active?: boolean
  complex?: boolean
  /** Shows a pulsing loading indicator and disables interaction */
  loading?: boolean
  /** Accessible label for icon-only buttons */
  ariaLabel?: string
}

const props = withDefaults(defineProps<Props>(), {
  disabled: false,
  variant: 'primary',
  size: 'md',
  fluid: false,
  active: false,
  complex: false,
  loading: false,
})

const emit = defineEmits<{ (e: 'click', evt: Event): void }>()

const onClick = (e: Event) => {
  if (!props.disabled && !props.loading) {
    emit('click', e)
  }
}
</script>

<template>
  <button 
    class="pitwall-button"
    :class="[size, variant, { fluid, active, disabled: disabled || loading, complex, loading }]"
    :disabled="disabled || loading"
    :aria-label="ariaLabel"
    :aria-busy="loading"
    :role="complex ? 'link' : 'button'"
    @click="onClick"
  >

    <!-- Background scanline effect layer -->
    <div class="bg-scanline" aria-hidden="true"></div>
    
    <div class="content-wrapper">
      <slot name="icon"></slot>
      
      <!-- Loading indicator -->
      <div v-if="loading" class="loading-indicator" aria-hidden="true">
        <span class="loading-dot"></span>
        <span class="loading-dot"></span>
        <span class="loading-dot"></span>
      </div>

      <template v-else>
        <div v-if="complex" class="complex-content">
          <slot></slot>
        </div>
        
        <div v-else class="text-content">
          <span class="main-text"><slot></slot></span>
          <span v-if="subText" class="sub-text">{{ subText }}</span>
        </div>
      </template>
      
      <slot name="icon-right"></slot>
    </div>
    
    <!-- Neon border overlay -->
    <div class="neon-border" aria-hidden="true"></div>
  </button>
</template>

<style scoped>
.pitwall-button {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: var(--color-ink);
  color: #fff;
  font-family: var(--font-title);
  cursor: pointer;
  outline: none;
  border: 2px solid var(--theme-color, var(--color-ui-good));
  transition: transform var(--duration-instant) var(--ease-snap),
              box-shadow var(--duration-instant) var(--ease-snap),
              background-color var(--duration-instant) var(--ease-snap);
  clip-path: polygon(
    clamp(6px, 1vmin, 12px) 0,
    100% 0,
    100% calc(100% - clamp(6px, 1vmin, 12px)),
    calc(100% - clamp(6px, 1vmin, 12px)) 100%,
    0 100%,
    0 clamp(6px, 1vmin, 12px)
  );
  overflow: hidden;
  z-index: var(--z-content);
  box-shadow: var(--shadow-hard);
  touch-action: manipulation;
}

.pitwall-button.fluid {
  display: flex;
  width: 100%;
}

.pitwall-button.disabled {
  opacity: 0.5;
  cursor: not-allowed;
  filter: grayscale(1);
}

.pitwall-button.loading {
  cursor: wait;
}

/* Internal Layouts */
.content-wrapper {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-sm);
  width: 100%;
  height: 100%;
  z-index: 3;
  padding: 0 var(--space-md);
}

.complex-content {
  flex: 1;
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
}

.text-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  line-height: 1.1;
}

.main-text {
  text-transform: uppercase;
  letter-spacing: 0.1em;
  text-shadow: 1px 1px 0 rgba(0,0,0,0.8);
  font-size: clamp(12px, calc(2.2vmin * var(--app-scale)), 24px);
}

.sub-text {
  font-family: var(--font-ui);
  opacity: 0.7;
  margin-top: 2px;
  letter-spacing: 0.05em;
  font-size: clamp(9px, calc(1.6vmin * var(--app-scale)), 18px);
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* Sizing */
.pitwall-button.lg {
  min-height: clamp(48px, calc(10vmin * var(--app-scale)), 80px);
  min-width: clamp(160px, calc(30vw * var(--app-scale)), 320px);
}

.pitwall-button.md {
  min-height: clamp(40px, calc(8vmin * var(--app-scale)), 64px);
  min-width: clamp(120px, calc(20vw * var(--app-scale)), 240px);
}

.pitwall-button.sm {
  min-height: clamp(32px, calc(6vmin * var(--app-scale)), 48px);
  min-width: clamp(80px, calc(15vw * var(--app-scale)), 160px);
}

/* Neon Border */
.neon-border {
  display: none; /* Disabled for strict retro look */
}

.bg-scanline {
  position: absolute;
  inset: 0;
  background: repeating-linear-gradient(
    0deg,
    transparent,
    transparent 2px,
    rgba(255,255,255,0.03) 2px,
    rgba(255,255,255,0.03) 4px
  );
  z-index: 1;
}

/* Hover and Active States */
.pitwall-button:hover:not(.disabled),
.pitwall-button.active:not(.disabled) {
  background-color: var(--theme-bg-hover, rgba(78, 205, 196, 0.2));
  transform: translate(-2px, -2px);
  box-shadow: var(--shadow-hard-hover, 6px 6px 0 rgba(0,0,0,0.8));
}

.pitwall-button:active:not(.disabled) {
  transform: translate(2px, 2px);
  box-shadow: var(--shadow-hard-active, 2px 2px 0 rgba(0,0,0,0.8));
}

.pitwall-button:focus-visible {
  outline: 2px solid var(--theme-color, var(--color-ui-good));
  outline-offset: 4px;
}

/* Variants */
.pitwall-button.primary {
  --theme-color: var(--color-ui-bad);
  --theme-bg-hover: rgba(255, 71, 87, 0.2);
}

.pitwall-button.secondary {
  --theme-color: var(--color-ui-good);
  --theme-bg-hover: rgba(78, 205, 196, 0.2);
}

.pitwall-button.info {
  --theme-color: var(--color-ui-warn);
  --theme-bg-hover: rgba(254, 202, 87, 0.2);
}

.pitwall-button.dark {
  --theme-color: var(--color-asphalt-light);
  --theme-bg-hover: rgba(44, 62, 80, 0.4);
}

.pitwall-button.danger {
  --theme-color: var(--color-ui-bad);
  --theme-bg-hover: rgba(255, 71, 87, 0.3);
  border-width: 2px;
}

@media (prefers-reduced-motion: reduce) {
  .loading-dot { animation: none; opacity: 0.6; }
}
</style>

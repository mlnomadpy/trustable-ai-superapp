<script setup lang="ts">
defineProps<{
  label: string
  checked: boolean
  focused: boolean
  subLabel?: string
}>()

const emit = defineEmits<{
  (e: 'change', checked: boolean): void
}>()
</script>

<template>
  <div 
    class="pitwall-checkbox-row flex flex-col mt-1 mb-1"

    role="checkbox"
    :aria-checked="checked"
    :aria-label="label"
    tabindex="0"
    @click="emit('change', !checked)"
    @keydown.enter.prevent="emit('change', !checked)"
    @keydown.space.prevent="emit('change', !checked)"
  >
    <div class="flex items-center">
      <span class="focus-marker" :class="focused ? 'text-ui-good opacity-100' : 'opacity-0'" aria-hidden="true">▶</span>
      
      <div 
        class="checkbox-box mr-3 border-2 transition-colors flex items-center justify-center bg-ink"
        :class="[
          checked ? 'border-ui-good' : 'border-slate',
          focused ? 'shadow-[0_0_8px_rgba(78,205,196,0.5)]' : ''
        ]"
      >
        <svg 
          v-if="checked" 
          class="check-icon text-ui-good" 
          viewBox="0 0 24 24" 
          fill="none" 
          stroke="currentColor" 
          stroke-width="3" 
          stroke-linecap="square" 
          stroke-linejoin="miter"
          aria-hidden="true"
        >
          <polyline points="20 6 9 17 4 12"></polyline>
        </svg>
      </div>

      <span class="label-text" :class="focused ? 'text-white font-bold' : 'text-silver'">{{ label }}</span>
    </div>
    <div v-if="subLabel" class="ml-11 sub-label">{{ subLabel }}</div>
  </div>
</template>

<style scoped>
.pitwall-checkbox-row {
  cursor: pointer;
  user-select: none;
  -webkit-user-select: none;
  -webkit-tap-highlight-color: transparent;
  outline: none;
}

.pitwall-checkbox-row:focus-visible {
  box-shadow: var(--shadow-focus);
}

.focus-marker {
  width: clamp(14px, calc(3vmin * var(--app-scale)), 20px);
  flex-shrink: 0;
  transition: opacity var(--duration-fast) ease;
}

.checkbox-box {
  width: clamp(16px, calc(3.5vmin * var(--app-scale)), 24px);
  height: clamp(16px, calc(3.5vmin * var(--app-scale)), 24px);
  flex-shrink: 0;
  transition: border-color var(--duration-fast) ease,
              box-shadow var(--duration-fast) ease,
              transform 0.15s var(--ease-bounce);
}

/* Snap animation on toggle */
.pitwall-checkbox-row:active .checkbox-box {
  transform: scale(0.85);
}

.check-icon {
  width: clamp(12px, calc(2.5vmin * var(--app-scale)), 18px);
  height: clamp(12px, calc(2.5vmin * var(--app-scale)), 18px);
  animation: check-snap 0.35s var(--ease-bounce) both;
  filter: drop-shadow(0 0 4px rgba(78, 205, 196, 0.6));
}

.label-text {
  font-size: clamp(11px, calc(2.2vmin * var(--app-scale)), 20px);
  transition: color var(--duration-fast) ease;
}

.sub-label {
  font-size: clamp(9px, calc(1.8vmin * var(--app-scale)), 16px);
  color: var(--color-slate);
}


@keyframes check-snap {
  0% { transform: scale(0) rotate(-15deg); opacity: 0; }
  60% { transform: scale(1.3) rotate(5deg); opacity: 1; }
  100% { transform: scale(1) rotate(0deg); opacity: 1; }
}

@media (prefers-reduced-motion: reduce) {
  .check-icon { animation: none; filter: none; }
  .checkbox-box { transition: none; }
}
</style>

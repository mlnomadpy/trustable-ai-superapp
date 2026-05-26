<script setup lang="ts">
import CyberModal from './CyberModal.vue'

interface Props {
  /** Controls dialog visibility */
  open: boolean
  /** Dialog title */
  title?: string
  /** Main confirmation message */
  message: string
  /** Confirm button label */
  confirmLabel?: string
  /** Cancel button label */
  cancelLabel?: string
  /** Visual severity */
  variant?: 'warn' | 'danger' | 'info'
}

withDefaults(defineProps<Props>(), {
  title: 'CONFIRM',
  confirmLabel: 'YES',
  cancelLabel: 'NO',
  variant: 'warn',
})

const emit = defineEmits<{
  (e: 'confirm'): void
  (e: 'cancel'): void
}>()
</script>

<template>
  <CyberModal :open="open" :title="title" size="sm" @close="emit('cancel')">
    <div class="confirm-body">
      <div 
        class="confirm-icon" 
        :class="`icon-${variant}`"
        aria-hidden="true"
      >
        <template v-if="variant === 'danger'">⚠</template>
        <template v-else-if="variant === 'warn'">❓</template>
        <template v-else>ℹ</template>
      </div>
      <p class="confirm-message">{{ message }}</p>
    </div>

    <template #footer>
      <button 
        class="confirm-btn btn-cancel"
        @click="emit('cancel')"
      >
        {{ cancelLabel }}
      </button>
      <button 
        class="confirm-btn" 
        :class="`btn-${variant}`"
        @click="emit('confirm')"
      >
        {{ confirmLabel }}
      </button>
    </template>
  </CyberModal>
</template>

<style scoped>
.confirm-body {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  gap: var(--space-md);
  padding: var(--space-md) 0;
}

.confirm-icon {
  font-size: clamp(28px, 6vmin, 48px);
  line-height: 1;
}

.icon-danger { filter: hue-rotate(-20deg); }

.confirm-message {
  font-size: clamp(11px, 2.5vmin, 18px);
  color: var(--color-silver);
  line-height: 1.5;
  max-width: 28ch;
  margin: 0;
}

.confirm-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: var(--space-xs) var(--space-lg);
  border: 2px solid var(--color-slate);
  background: transparent;
  color: var(--color-silver);
  font-family: var(--font-title);
  font-size: clamp(10px, 2.2vmin, 16px);
  letter-spacing: 0.15em;
  text-transform: uppercase;
  cursor: pointer;
  transition: all var(--duration-fast) ease;
  clip-path: polygon(6px 0, 100% 0, 100% calc(100% - 6px), calc(100% - 6px) 100%, 0 100%, 0 6px);
  min-width: clamp(60px, 12vw, 100px);
}

.btn-cancel:hover {
  border-color: var(--color-silver);
  color: white;
}

.btn-warn {
  border-color: var(--color-ui-warn);
  color: var(--color-ui-warn);
}
.btn-warn:hover {
  background: rgba(254, 202, 87, 0.15);
  box-shadow: 0 0 12px rgba(254, 202, 87, 0.3);
}

.btn-danger {
  border-color: var(--color-ui-bad);
  color: var(--color-ui-bad);
}
.btn-danger:hover {
  background: rgba(255, 71, 87, 0.15);
  box-shadow: 0 0 12px rgba(255, 71, 87, 0.3);
}

.btn-info {
  border-color: var(--color-ui-good);
  color: var(--color-ui-good);
}
.btn-info:hover {
  background: rgba(78, 205, 196, 0.15);
  box-shadow: 0 0 12px rgba(78, 205, 196, 0.3);
}

.confirm-btn:active {
  transform: translateY(1px);
}
</style>

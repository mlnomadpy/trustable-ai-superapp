<script setup lang="ts">
import { watch, nextTick, ref, onUnmounted } from 'vue'
import { useKeyboard } from '@/shared/lib/useKeyboard'
import { useAudioStore } from '@/features/audio-playback/model/audioStore'
import CyberPanel from './CyberPanel.vue'

interface Props {
  /** Controls modal visibility */
  open: boolean
  /** Optional title for the modal header */
  title?: string
  /** Whether clicking the backdrop closes the modal */
  closeOnBackdrop?: boolean
  /** Whether pressing Escape closes the modal */
  closeOnEscape?: boolean
  /** Size preset for modal width */
  size?: 'sm' | 'md' | 'lg' | 'full'
}

const props = withDefaults(defineProps<Props>(), {
  closeOnBackdrop: true,
  closeOnEscape: true,
  size: 'md',
})

const emit = defineEmits<{
  (e: 'close'): void
}>()

const audio = useAudioStore()
const modalRef = ref<HTMLDivElement | null>(null)
const isAnimating = ref(false)

// Focus trap: store the element that opened the modal so we can restore focus on close
let previouslyFocusedElement: HTMLElement | null = null

watch(() => props.open, async (isOpen) => {
  if (isOpen) {
    previouslyFocusedElement = document.activeElement as HTMLElement
    isAnimating.value = true
    await nextTick()
    modalRef.value?.focus()
  } else {
    isAnimating.value = false
    previouslyFocusedElement?.focus()
  }
})

const handleBackdropClick = () => {
  if (props.closeOnBackdrop) {
    audio.playSfx('cancel')
    emit('close')
  }
}

const handleContentClick = (e: Event) => {
  e.stopPropagation()
}

useKeyboard((e: KeyboardEvent) => {
  if (!props.open) return
  
  if ((e.key === 'Escape' || e.key === 'b') && props.closeOnEscape) {
    e.preventDefault()
    e.stopPropagation()
    audio.playSfx('cancel')
    emit('close')
  }
})

onUnmounted(() => {
  previouslyFocusedElement = null
})
</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <div 
        v-if="open"
        ref="modalRef"
        class="cyber-modal-backdrop"
        role="dialog"
        aria-modal="true"
        :aria-label="title"
        tabindex="-1"
        @click="handleBackdropClick"
        @keydown.stop
      >
        <div 
          class="cyber-modal-content" 
          :class="[`size-${size}`]"
          @click="handleContentClick"
        >
          <CyberPanel variant="solid" border="primary" :animate="false">
            <!-- Header -->
            <div v-if="title || $slots.header" class="modal-header">
              <slot name="header">
                <h2 class="modal-title">{{ title }}</h2>
              </slot>
              <button 
                class="modal-close" 
                aria-label="Close modal"
                @click="emit('close')"
              >
                ✕
              </button>
            </div>

            <!-- Body -->
            <div class="modal-body">
              <slot></slot>
            </div>

            <!-- Footer -->
            <div v-if="$slots.footer" class="modal-footer">
              <slot name="footer"></slot>
            </div>
          </CyberPanel>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.cyber-modal-backdrop {
  position: fixed;
  inset: 0;
  z-index: var(--z-modal, 30);
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.80);
  backdrop-filter: blur(4px);
  padding: var(--space-md);
}

.cyber-modal-content {
  position: relative;
  max-height: 85vh;
  display: flex;
  flex-direction: column;
}

/* Sizes */
.size-sm { width: clamp(280px, 40vw, 360px); }
.size-md { width: clamp(320px, 60vw, 520px); }
.size-lg { width: clamp(400px, 75vw, 700px); }
.size-full { width: calc(100vw - var(--space-lg) * 2); height: calc(100vh - var(--space-lg) * 2); }

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-bottom: var(--space-sm);
  margin-bottom: var(--space-sm);
  border-bottom: 1px solid var(--color-slate);
}

.modal-title {
  font-family: var(--font-title);
  font-size: clamp(12px, 2.5vmin, 20px);
  color: var(--color-silver);
  letter-spacing: 0.15em;
  text-transform: uppercase;
  margin: 0;
}

.modal-close {
  background: none;
  border: 1px solid var(--color-slate);
  color: var(--color-slate);
  width: clamp(24px, 4vmin, 32px);
  height: clamp(24px, 4vmin, 32px);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  font-size: clamp(12px, 2vmin, 18px);
  transition: all var(--duration-fast) ease;
  flex-shrink: 0;
}

.modal-close:hover {
  color: var(--color-ui-bad);
  border-color: var(--color-ui-bad);
}

.modal-body {
  overflow-y: auto;
  flex: 1;
  min-height: 0;
}

.modal-footer {
  padding-top: var(--space-sm);
  margin-top: var(--space-sm);
  border-top: 1px solid var(--color-slate);
  display: flex;
  justify-content: flex-end;
  gap: var(--space-sm);
}

/* Transition */
.modal-enter-active {
  transition: opacity var(--duration-fast) ease;
}
.modal-enter-active .cyber-modal-content {
  transition: transform var(--duration-normal) var(--ease-bounce);
}
.modal-leave-active {
  transition: opacity var(--duration-fast) ease;
}

.modal-enter-from {
  opacity: 0;
}
.modal-enter-from .cyber-modal-content {
  transform: scale(0.9) translateY(10px);
}

.modal-leave-to {
  opacity: 0;
}
</style>

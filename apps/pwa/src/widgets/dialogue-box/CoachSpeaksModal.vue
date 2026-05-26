<script setup lang="ts">
import { onMounted, ref } from 'vue'
import DialogueBox from './DialogueBox.vue'
import Frame from '@/shared/ui/core/Frame.vue'
import { useAudioStore } from '@/features/audio-playback/model/audioStore'

/**
 * High-priority coach interruption modal.
 * Used for deep paddock insights (ADK) or major milestones.
 */
interface Props {
  coachId: string
  emotion: string
  title?: string
  text: string
}

const props = defineProps<Props>()
const emit = defineEmits<{ (e: 'close'): void }>()

const audio = useAudioStore()
const visible = ref(false)

onMounted(() => {
  visible.value = true
  audio.playSfx('transition_wipe')
})

const handleDone = () => {
  visible.value = false
  setTimeout(() => emit('close'), 300)
}
</script>

<template>
  <Transition name="modal-fade">
    <div v-if="visible" class="coach-speaks-overlay pixelated">
      <div class="modal-container">
        <Frame variant="card" padding="24px" class="content-frame">
          <h2 v-if="title" class="text-title-lg text-ui-good font-title mb-4 tracking-widest text-center">
            {{ title }}
          </h2>
          
          <!-- We reuse the DialogueBox logic but styled for the modal center -->
          <DialogueBox 
            :coach-id="coachId" 
            :emotion="emotion" 
            :text="text"
            @done="handleDone"
            class="modal-dialogue"
          />
        </Frame>
      </div>
      
      <!-- Scanline overlay -->
      <div class="scanlines pointer-events-none"></div>
    </div>
  </Transition>
</template>

<style scoped>
.coach-speaks-overlay {
  position: fixed;
  inset: 0;
  z-index: 200;
  background: rgba(13, 13, 18, 0.9);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 5vmin;
  backdrop-filter: blur(8px);
}

.modal-container {
  width: 100%;
  max-width: 800px;
  position: relative;
}

.content-frame {
  min-height: 300px;
  display: flex;
  flex-direction: column;
}

/* Override DialogueBox positioning to center it in the modal */
:deep(.modal-dialogue) {
  position: relative !important;
  bottom: 0 !important;
  padding: 0 !important;
  width: 100% !important;
  transform: none !important;
}

:deep(.modal-dialogue .dialogue-layout) {
  width: 100% !important;
  gap: 24px;
}

:deep(.modal-dialogue .speech-bubble) {
  min-height: 120px;
  font-size: 1.2em;
}

.scanlines {
  position: absolute;
  inset: 0;
  background: repeating-linear-gradient(
    0deg,
    transparent,
    transparent 2px,
    rgba(255, 255, 255, 0.05) 2px,
    rgba(255, 255, 255, 0.05) 4px
  );
}

.modal-fade-enter-active,
.modal-fade-leave-active {
  transition: opacity 0.3s ease, transform 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275);
}

.modal-fade-enter-from,
.modal-fade-leave-to {
  opacity: 0;
  transform: scale(0.9) translateY(20px);
}
</style>

<script setup lang="ts">
import { ref, watch, onUnmounted } from 'vue'
import type { Cue } from '../model/cueStore'
import { useAudioStore } from '@/features/audio-playback/model/audioStore'

const props = defineProps<{
  cue: Cue | null
}>()

const audio = useAudioStore()
const displayedText = ref('')
let typeInterval: number | null = null

watch(() => props.cue, (newCue) => {
  if (newCue) {
    if (typeInterval) clearInterval(typeInterval)
    let i = 0
    displayedText.value = ''
    typeInterval = window.setInterval(() => {
      if (i < newCue.text.length) {
        displayedText.value += newCue.text.charAt(i)
        if (i % 4 === 0) audio.playSfx('dialogue_blip')
        i++
      } else {
        clearInterval(typeInterval!)
      }
    }, 30)
  } else {
    displayedText.value = ''
  }
}, { immediate: true })

onUnmounted(() => {
  if (typeInterval) clearInterval(typeInterval)
})
</script>

<template>
  <Transition name="slide-up">
    <div v-if="cue" class="cue-band-container">
      <div class="cue-band pixelated">
        <span class="cue-text">{{ displayedText }}</span>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.cue-band-container {
  position: absolute;
  bottom: calc(var(--safe-bottom) + 24px);
  left: 0;
  width: 100%;
  display: flex;
  justify-content: center;
  z-index: 150;
  pointer-events: none;
}

.cue-band {
  background: rgba(11, 12, 16, 0.95);
  border: 4px solid var(--color-ui-good);
  padding: clamp(8px, 2vmin, 16px) clamp(24px, 5vw, 48px);
  box-shadow: 
    0 10px 30px rgba(0, 0, 0, 0.8), 
    0 0 20px rgba(78, 205, 196, 0.4),
    inset 0 0 10px rgba(78, 205, 196, 0.2);
  display: flex;
  align-items: center;
  justify-content: center;
  text-align: center;
  max-width: 90%;
}

.cue-text {
  font-family: var(--font-title);
  font-size: clamp(16px, 4vmin, 32px);
  font-weight: 900;
  color: var(--color-ui-good);
  letter-spacing: 0.1em;
  text-transform: uppercase;
  text-shadow: 2px 2px 0 #000, 0 0 10px rgba(78, 205, 196, 0.6);
}

.slide-up-enter-active,
.slide-up-leave-active {
  transition: transform 0.3s var(--ease-bounce), opacity 0.3s ease;
}

.slide-up-enter-from,
.slide-up-leave-to {
  transform: translateY(100%);
  opacity: 0;
}
</style>


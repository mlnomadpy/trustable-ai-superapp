<script setup lang="ts">
import { onMounted, onUnmounted } from 'vue'
import { useKeyboard } from '@/shared/lib/useKeyboard'
import { useAudioStore } from '@/features/audio-playback/model/audioStore'
import DialogueBox from '@/widgets/dialogue-box/DialogueBox.vue'
import CyberBox from '@/shared/ui/core/CyberBox.vue'

const emit = defineEmits<{ (e: 'next'): void }>()
const audio = useAudioStore()

// Fullscreen entry now lives in the globally-mounted FullscreenToggle widget
// (top-right of every route), so the welcome tap no longer competes with it.
const advance = () => {
  audio.playSfx('cursor_select')
  emit('next')
}

useKeyboard((e: KeyboardEvent) => {
  if (e.key === 'Enter') {
    advance()
  }
})

onMounted(() => {
})

onUnmounted(() => {
})
</script>

<template>
  <div class="welcome-step" @click="advance">
    <!-- Center character label -->
    <div class="character-area">
      <CyberBox variant="ghost" border="slate" class="w-[clamp(80px,20vmin,160px)] h-[clamp(80px,20vmin,160px)] flex items-center justify-center">
        <span class="text-title text-slate font-title">T-ROD</span>
      </CyberBox>
    </div>
    
    <DialogueBox 
      coach-id="trod"
      emotion="talk"
      text="Welcome to Pitwall, kid. Let's set you up."
    />
  </div>
</template>

<style scoped>
.welcome-step {
  display: flex;
  flex-direction: column;
  height: 100%;
  justify-content: flex-end;
  position: relative;
  cursor: pointer;
}

.character-area {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: -1;
  opacity: 0.3;
}


</style>

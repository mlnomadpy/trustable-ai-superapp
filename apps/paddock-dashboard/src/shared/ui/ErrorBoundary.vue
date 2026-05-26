<script setup lang="ts">
import { onErrorCaptured, ref } from 'vue'
import { useAudioStore } from '@/features/audio-playback/model/audioStore'

const error = ref<Error | null>(null)
const audio = useAudioStore()

onErrorCaptured((err) => {
  error.value = err
  audio.playSfx('error_quiet')
  return false // prevent propagation
})

const reset = () => {
  error.value = null
  audio.playSfx('cursor_select')
}
</script>

<template>
  <slot v-if="!error" />
  <div v-else class="error-boundary flex flex-col items-center justify-center p-8 w-full h-full min-h-[200px]">
    <div class="bg-ink border-2 border-ui-bad shadow-[0_0_20px_rgba(255,71,87,0.4)] p-6 flex flex-col items-center max-w-[80%]">
      <h2 class="text-ui-warn font-title text-title-sm tracking-[0.2em] mb-4">SYSTEM ERROR</h2>
      <p class="text-silver text-body text-center mb-6">{{ error.message }}</p>
      <button 
        class="retro-btn border border-slate px-6 py-2 hover:bg-slate/20 text-white font-bold"
        @click="reset"
      >
        REBOOT MODULE
      </button>
    </div>
  </div>
</template>

<style scoped>
.error-boundary {
  animation: glitch 0.3s ease-in-out;
}

@keyframes glitch {
  0% { transform: translate(0) }
  20% { transform: translate(-2px, 2px) }
  40% { transform: translate(-2px, -2px) }
  60% { transform: translate(2px, 2px) }
  80% { transform: translate(2px, -2px) }
  100% { transform: translate(0) }
}
</style>

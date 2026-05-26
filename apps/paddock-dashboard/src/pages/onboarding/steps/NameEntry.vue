<script setup lang="ts">
import { ref } from 'vue'
import CyberKeyboard from '@/shared/ui/core/CyberKeyboard.vue'
import CyberBox from '@/shared/ui/core/CyberBox.vue'
import { useAudioStore } from '@/features/audio-playback/model/audioStore'

const props = defineProps<{
  initialName: string
}>()

const emit = defineEmits<{ (e: 'next'): void; (e: 'back'): void; (e: 'update:name', val: string): void }>()
const audio = useAudioStore()

const currentName = ref(props.initialName)
const errorMessage = ref('')

const handleChar = (char: string) => {
  errorMessage.value = ''
  if (currentName.value.length < 12) {
    currentName.value += char
    emit('update:name', currentName.value)
  }
}

const handleDel = () => {
  errorMessage.value = ''
  currentName.value = currentName.value.slice(0, -1)
  emit('update:name', currentName.value)
}

const handleEnd = () => {
  if (currentName.value.trim().length === 0) {
    errorMessage.value = 'NAME CANNOT BE EMPTY'
    audio.playSfx('cancel')
  } else {
    emit('next')
  }
}

const handleBack = () => {
  if (currentName.value.length > 0) {
    handleDel()
    audio.playSfx('cancel')
  } else {
    audio.playSfx('cancel')
    emit('back')
  }
}
</script>

<template>
  <div class="name-entry">
    <div class="entry-label text-small text-silver tracking-[0.2em]">YOUR NAME</div>
    
    <!-- Name display field -->
    <CyberBox variant="ink" border="slate" class="px-[clamp(12px,3vw,28px)] py-[clamp(6px,1.5vh,14px)] min-w-[clamp(140px,40vw,300px)] text-center">
      <span class="name-text text-title">{{ currentName }}<span class="cursor-blink">_</span></span>
    </CyberBox>
    
    <!-- Character grid -->
    <CyberKeyboard 
      @char="handleChar" 
      @del="handleDel" 
      @end="handleEnd" 
      @back="handleBack" 
      :active="true" 
    />
    
    <!-- Keyboard hint -->
    <div class="keyboard-hint text-small text-slate">
      TYPE ON KEYBOARD · OR TAP LETTERS
    </div>
    
    <div v-if="errorMessage" class="error-msg text-body text-ui-warn">{{ errorMessage }}</div>
  </div>
</template>

<style scoped>
.name-entry {
  display: flex;
  flex-direction: column;
  align-items: center;
  height: 100%;
  padding-top: clamp(8px, 2vh, 20px);
  font-family: var(--font-ui);
  gap: clamp(6px, 1.5vh, 16px);
}

.entry-label {
  margin-bottom: clamp(2px, 0.5vh, 6px);
}


.name-text {
  font-weight: bold;
  color: white;
  letter-spacing: 0.15em;
}

.cursor-blink {
  animation: blink-cursor 0.6s steps(2) infinite;
  color: var(--color-ui-good);
}

@keyframes blink-cursor {
  0% { opacity: 1; }
  50% { opacity: 0; }
}

.keyboard-hint {
  margin-top: clamp(2px, 0.5vh, 6px);
  letter-spacing: 0.1em;
}

.error-msg {
  margin-top: clamp(4px, 1vh, 10px);
  animation: shake 0.3s steps(2);
}

@keyframes shake {
  0%, 100% { transform: translateX(0); }
  25% { transform: translateX(-4px); }
  75% { transform: translateX(4px); }
}
</style>

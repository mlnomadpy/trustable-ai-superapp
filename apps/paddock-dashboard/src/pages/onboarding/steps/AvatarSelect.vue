<script setup lang="ts">
import { ref } from 'vue'
import { useKeyboard } from '@/shared/lib/useKeyboard'
import { useAudioStore } from '@/features/audio-playback/model/audioStore'
import CyberButton from '@/shared/ui/core/CyberButton.vue'
import CyberAvatar from '@/shared/ui/core/CyberAvatar.vue'

const props = defineProps<{
  initialAvatar: string
}>()

const emit = defineEmits<{ (e: 'next'): void; (e: 'back'): void; (e: 'update:avatar', val: string): void }>()
const audio = useAudioStore()

const avatars = [
  { id: 'avatar_a', label: 'TYPE A' },
  { id: 'avatar_b', label: 'TYPE B' },
  { id: 'avatar_c', label: 'TYPE C' },
  { id: 'avatar_d', label: 'TYPE D' }
]

const cursorIndex = ref(
  avatars.findIndex(a => a.id === props.initialAvatar) !== -1 
    ? avatars.findIndex(a => a.id === props.initialAvatar) 
    : 0
)

useKeyboard((e: KeyboardEvent) => {
  if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
    cursorIndex.value = (cursorIndex.value + 1) % avatars.length
    audio.playSfx('cursor_move')
    emit('update:avatar', avatars[cursorIndex.value].id)
  } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
    cursorIndex.value = (cursorIndex.value - 1 + avatars.length) % avatars.length
    audio.playSfx('cursor_move')
    emit('update:avatar', avatars[cursorIndex.value].id)
  } else if (e.key === 'Enter') {
    audio.playSfx('cursor_select')
    emit('next')
  } else if (e.key === 'Escape' || e.key === 'Backspace' || e.key === 'b') {
    audio.playSfx('cancel')
    emit('back')
  }
})

const selectAvatar = (index: number) => {
  cursorIndex.value = index
  emit('update:avatar', avatars[index].id)
  audio.playSfx('cursor_select')
  emit('next')
}
</script>

<template>
  <div class="avatar-select">
    <div class="select-label text-small text-silver tracking-[0.2em]">SELECT DRIVER PROFILE</div>
    
    <!-- Avatar Preview Area -->
    <div class="mb-[clamp(10px,2vh,20px)] flex justify-center w-full">
      <CyberAvatar :sheet="avatars[cursorIndex].id" size="xl" variant="glow" />
    </div>
    
    <!-- Selection Controls -->
    <div class="avatar-controls">
      <CyberButton
        v-for="(avatar, i) in avatars"
        :key="avatar.id"
        :active="cursorIndex === i"
        :variant="cursorIndex === i ? 'primary' : 'dark'"
        size="sm"
        @click="selectAvatar(i)"
      >
        {{ avatar.label }}
      </CyberButton>
    </div>
    
    <div class="hint-text text-small text-slate mt-4">
      ◀ ▶ SELECT · A CONFIRM
    </div>
  </div>
</template>

<style scoped>
.avatar-select {
  display: flex;
  flex-direction: column;
  align-items: center;
  height: 100%;
  padding-top: clamp(8px, 2vh, 20px);
  font-family: var(--font-ui);
  gap: clamp(8px, 2vh, 20px);
}

.select-label {
  margin-bottom: clamp(2px, 0.5vh, 6px);
}

.avatar-controls {
  display: flex;
  gap: clamp(6px, 1.5vw, 12px);
  flex-wrap: wrap;
  justify-content: center;
  max-width: 90vw;
}

</style>

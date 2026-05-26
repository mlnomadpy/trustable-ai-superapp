<script setup lang="ts">
import { ref } from 'vue'
import { useKeyboard } from '@/shared/lib/useKeyboard'
import { useAudioStore } from '@/features/audio-playback/model/audioStore'

const props = defineProps<{
  active?: boolean
}>()

const emit = defineEmits<{
  (e: 'char', char: string): void
  (e: 'del'): void
  (e: 'end'): void
  (e: 'back'): void
}>()
const audio = useAudioStore()

const chars = [
  'A','B','C','D','E','F','G',
  'H','I','J','K','L','M','N',
  'O','P','Q','R','S','T','U',
  'V','W','X','Y','Z','.',
  '_','-',' ','DEL','END'
]

const cursorX = ref(0)
const cursorY = ref(0)
const maxCols = 7
const numRows = Math.ceil(chars.length / maxCols)

const selectChar = () => {
  const idx = cursorY.value * maxCols + cursorX.value
  const char = chars[idx]
  if (!char) return
  
  audio.playSfx('cursor_select')
  
  if (char === 'DEL') {
    emit('del')
  } else if (char === 'END') {
    emit('end')
  } else {
    emit('char', char === ' ' ? ' ' : char)
  }
}

const onCharClick = (index: number) => {
  if (!props.active) return
  cursorY.value = Math.floor(index / maxCols)
  cursorX.value = index % maxCols
  selectChar()
}

useKeyboard((e: KeyboardEvent) => {
  if (!props.active && props.active !== undefined) return
  
  if (e.key === 'ArrowRight') {
    cursorX.value = (cursorX.value + 1) % maxCols
    audio.playSfx('cursor_move')
  } else if (e.key === 'ArrowLeft') {
    cursorX.value = (cursorX.value - 1 + maxCols) % maxCols
    audio.playSfx('cursor_move')
  } else if (e.key === 'ArrowDown') {
    cursorY.value = (cursorY.value + 1) % numRows
    audio.playSfx('cursor_move')
  } else if (e.key === 'ArrowUp') {
    cursorY.value = (cursorY.value - 1 + numRows) % numRows
    audio.playSfx('cursor_move')
  } else if (e.key === 'Enter') {
    selectChar()
  } else if (e.key === 'Escape') {
    emit('back')
  } else if (e.key === 'Backspace') {
    emit('del')
  } else if (e.key.length === 1 && e.key.match(/[a-zA-Z0-9.\-_ ]/)) {
    emit('char', e.key.toUpperCase())
    audio.playSfx('cursor_select')
  }
})
</script>

<template>
  <div class="cyber-keyboard">
    <div class="char-grid">
      <div 
        v-for="(char, i) in chars" 
        :key="i"
        class="char-cell"
        :class="[
          cursorY * maxCols + cursorX === i && (active === undefined || active)
            ? 'cell-focused' 
            : char === 'DEL' || char === 'END' ? 'cell-action' : 'cell-default'
        ]"
        @click="onCharClick(i)"
      >
        {{ char }}
      </div>
    </div>
  </div>
</template>

<style scoped>
.cyber-keyboard {
  display: flex;
  flex-direction: column;
  align-items: center;
  font-family: var(--font-ui);
}

.char-grid {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: clamp(3px, 0.8vmin, 8px);
  width: clamp(280px, 88vw, 560px);
}

.char-cell {
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: clamp(14px, 3.5vmin, 28px);
  min-height: clamp(32px, 7vmin, 52px);
  cursor: pointer;
  transition: all 0.1s ease;
  border: 1px solid transparent;
  user-select: none;
  -webkit-user-select: none;
  -webkit-tap-highlight-color: transparent;
}

.cell-default {
  color: var(--color-silver);
}

.cell-default:active {
  background: rgba(42, 161, 152, 0.2);
}

.cell-action {
  color: var(--color-ui-info);
  font-weight: bold;
}

.cell-action:active {
  background: rgba(74, 152, 200, 0.2);
}

.cell-focused {
  background: var(--color-ui-good);
  color: var(--color-ink);
  font-weight: bold;
  border-color: var(--color-ui-good);
  box-shadow: 0 0 8px rgba(42, 161, 152, 0.4);
}
</style>

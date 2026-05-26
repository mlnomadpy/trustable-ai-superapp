<script setup lang="ts">
import { ref, watch } from 'vue'
import { useKeyboard } from '@/shared/lib/useKeyboard'
import { useAudioStore } from '@/features/audio-playback/model/audioStore'

export interface MenuOption {
  id: string
  label: string
  desc?: string
}

const props = defineProps<{
  options: MenuOption[]
  active?: boolean
  initialOption?: string
}>()

const emit = defineEmits<{ (e: 'select', option: MenuOption): void; (e: 'back'): void; (e: 'highlight', option: MenuOption): void }>()
const audio = useAudioStore()

const cursorIndex = ref(
  props.initialOption 
    ? Math.max(0, props.options.findIndex(o => o.id === props.initialOption))
    : 0
)

watch(cursorIndex, (newIdx) => {
  emit('highlight', props.options[newIdx])
}, { immediate: true })

const selectOption = (index: number) => {
  cursorIndex.value = index
  audio.playSfx('cursor_select')
  emit('select', props.options[index])
}

useKeyboard((e: KeyboardEvent) => {
  if (!props.active && props.active !== undefined) return
  
  if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
    cursorIndex.value = (cursorIndex.value + 1) % props.options.length
    audio.playSfx('cursor_move')
  } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
    cursorIndex.value = (cursorIndex.value - 1 + props.options.length) % props.options.length
    audio.playSfx('cursor_move')
  } else if (e.key === 'Enter') {
    selectOption(cursorIndex.value)
  } else if (e.key === 'Escape' || e.key === 'Backspace' || e.key === 'b') {
    audio.playSfx('cancel')
    emit('back')
  }
})
</script>

<template>
  <div class="cyber-menu-list" role="listbox" :aria-label="'Menu'">
    <div 
      v-for="(opt, i) in options" 
      :key="i"
      class="menu-option"
      role="option"
      :aria-selected="cursorIndex === i && (active === undefined || active)"
      :class="(cursorIndex === i && (active === undefined || active)) ? 'option-focused' : 'option-default'"
      @click="selectOption(i)"
      @mouseenter="() => { if(active === undefined || active) { cursorIndex = i; audio.playSfx('cursor_move') } }"
    >
      <span v-if="cursorIndex === i && (active === undefined || active)" class="option-cursor">▶</span>
      <span v-else class="option-cursor option-invisible">&nbsp;</span>
      <span class="option-label text-body">{{ opt.label }}</span>
    </div>
  </div>
</template>

<style scoped>
.cyber-menu-list {
  display: flex;
  flex-direction: column;
  gap: clamp(4px, 1vh, 12px);
  width: 100%;
}

.menu-option {
  display: flex;
  align-items: center;
  gap: clamp(6px, 1.5vw, 14px);
  border: 2px solid var(--color-slate);
  background-color: var(--color-charcoal);
  padding: clamp(8px, 2vh, 18px) clamp(10px, 2.5vw, 24px);
  cursor: pointer;
  transition: transform 0.05s steps(2), box-shadow 0.05s steps(2), border-color 0.05s steps(2), background-color 0.05s steps(2);
  text-transform: uppercase;
  -webkit-tap-highlight-color: transparent;
  box-shadow: 2px 2px 0 rgba(0,0,0,0.8);
}

.option-focused {
  border-color: var(--color-ui-good);
  background-color: var(--color-ink);
  box-shadow: 4px 4px 0 rgba(0,0,0,0.8);
  transform: translate(-2px, -2px);
  color: white;
  font-weight: bold;
  animation: focus-glow 2s ease-in-out infinite;
}

@keyframes focus-glow {
  0%, 100% { box-shadow: 4px 4px 0 rgba(0,0,0,0.8), 0 0 4px rgba(78,205,196,0.2); }
  50% { box-shadow: 4px 4px 0 rgba(0,0,0,0.8), 0 0 16px rgba(78,205,196,0.4); }
}

.option-default {
  color: var(--color-silver);
}

.option-default:active {
  background: rgba(42, 161, 152, 0.1);
}

.option-cursor {
  color: var(--color-ui-good);
  text-shadow: 0 0 6px rgba(42, 161, 152, 0.6);
  font-size: clamp(10px, 2.5vmin, 20px);
  flex-shrink: 0;
  animation: cursor-bounce 0.25s steps(2) infinite;
}

.option-invisible { visibility: hidden; }

@keyframes cursor-bounce {
  0%, 100% { transform: translateX(0); }
  50% { transform: translateX(2px); }
}
</style>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useKeyboard } from '@/shared/lib/useKeyboard'
import { useRouter } from 'vue-router'
import { useSaveStore } from '@/entities/save/model/saveStore'
import { useAudioStore } from '@/features/audio-playback/model/audioStore'
import PageShell from '@/shared/ui/PageShell.vue'
import SlotCard from './ui/SlotCard.vue'

const router = useRouter()
const save = useSaveStore()
const audio = useAudioStore()
const cursor = ref(0)
const loading = ref(true)
const deleteProgress = ref(0)
let deleteTimer: number | null = null
// HOLD-B-DELETE needs a keyup edge that `useKeyboard` (keydown-only) does
// not surface. Track press state from the useKeyboard handler and watch
// for the matching keyup with a single, narrowly-scoped listener.
const isHoldingDelete = ref(false)

const hints = ['▲ ▼ MOVE', 'A · LOAD / NEW', 'HOLD B · DELETE']

onMounted(async () => {
  await save.hydrate()
  loading.value = false
  window.addEventListener('keyup', handleDeleteKeyup)
})

onUnmounted(() => {
  window.removeEventListener('keyup', handleDeleteKeyup)
  stopDelete()
})

useKeyboard((e: KeyboardEvent) => {
  if (e.key === 'ArrowDown') {
    cursor.value = (cursor.value + 1) % 3
    audio.playSfx('cursor_move')
  } else if (e.key === 'ArrowUp') {
    cursor.value = (cursor.value - 1 + 3) % 3
    audio.playSfx('cursor_move')
  } else if (e.key === 'Enter') {
    if (deleteProgress.value > 0) return // Ignore if deleting
    audio.playSfx('cursor_select')
    handleSelect((cursor.value + 1) as 1|2|3)
  } else if (e.key === 'Backspace' || e.key === 'b' || e.key === 'B') {
    // HOLD-B-DELETE: useKeyboard fires keydown only, so we start the timer
    // here and let the dedicated keyup listener stop it. Auto-repeat will
    // re-enter this branch but `startDelete` guards against double-start.
    if (!isHoldingDelete.value) {
      isHoldingDelete.value = true
      startDelete()
    }
  }
})

const startDelete = (index?: number) => {
  if (deleteTimer) return
  const targetIndex = index ?? cursor.value
  const slotData = save.slots[targetIndex]
  if (!slotData) return

  if (index !== undefined) {
    cursor.value = index
  }

  deleteTimer = window.setInterval(() => {
    deleteProgress.value = Math.min(100, deleteProgress.value + 5)
    if (deleteProgress.value === 100) {
      finishDelete()
    }
  }, 50)
}

const stopDelete = () => {
  if (deleteTimer) {
    window.clearInterval(deleteTimer)
    deleteTimer = null
  }
  if (deleteProgress.value < 100) {
    deleteProgress.value = 0
  }
}

const finishDelete = () => {
  stopDelete()
  audio.playSfx('cancel')
  save.slots[cursor.value] = null
  save.save()
  deleteProgress.value = 0
}

const handleDeleteKeyup = (e: KeyboardEvent) => {
  if (e.key === 'Backspace' || e.key === 'b' || e.key === 'B') {
    isHoldingDelete.value = false
    stopDelete()
  }
}

const handleSelect = (slotId: 1 | 2 | 3) => {
  save.activeSlotId = slotId
  cursor.value = slotId - 1
  const slotData = save.slots[slotId - 1]
  if (slotData) {
    router.push('/garage')
  } else {
    router.push('/onboarding/1')
  }
}
</script>

<template>
  <PageShell title="SELECT SAVE SLOT" :hints="hints" bg="neutral">
    <template #heading>
      <div class="heading-block mb-[3vh] text-center">
        <h1 class="text-title font-title text-silver tracking-[0.2em]">SELECT SAVE SLOT</h1>
        <div class="heading-rule"></div>
      </div>
    </template>
    
    <!-- Background overrides -->
    <div class="save-bg absolute inset-0 z-0 pointer-events-none"></div>
    <div class="crt-overlay pointer-events-none"></div>
    
    <div class="content flex flex-col items-center justify-center relative z-10 w-full flex-grow">
      
      <div v-if="loading" class="text-body text-slate animate-pulse">LOADING...</div>
      
      <div v-else class="slot-list w-full max-w-[92%]">
        <SlotCard 
          v-for="(slot, i) in save.slots" 
          :key="i"
          :slot-id="(i + 1) as 1|2|3"
          :slot-data="slot"
          :focused="cursor === i"
          :delete-progress="cursor === i ? deleteProgress : 0"
          @select="handleSelect((i + 1) as 1|2|3)"
          @mouseover="cursor = i"
          @pointerdown="startDelete(i)"
          @pointerup="stopDelete"
          @pointerleave="stopDelete"
          @pointercancel="stopDelete"
          class="touch-none select-none"
          @contextmenu.prevent
        />
      </div>
    </div>
  </PageShell>
</template>

<style scoped>
.save-bg {
  background: linear-gradient(
    180deg,
    var(--color-ink) 0%,
    var(--color-asphalt-deep) 50%,
    var(--color-ink) 100%
  );
}
</style>

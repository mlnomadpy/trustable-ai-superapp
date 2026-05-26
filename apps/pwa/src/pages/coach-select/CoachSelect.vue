<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useKeyboard } from '@/shared/lib/useKeyboard'
import { useRouter } from 'vue-router'
import { useSaveStore } from '@/entities/save/model/saveStore'
import { useAudioStore } from '@/features/audio-playback/model/audioStore'
import PageShell from '@/shared/ui/PageShell.vue'
import Sprite from '@/entities/coach/Sprite.vue'
import CoachFloat from '@/shared/ui/CoachFloat.vue'
import CyberButton from '@/shared/ui/core/CyberButton.vue'
import CyberProgress from '@/shared/ui/core/CyberProgress.vue'

const router = useRouter()
const save = useSaveStore()
const audio = useAudioStore()

const coaches = [
  { id: 'trod', name: 'T-ROD', levelReq: 1, quote: "Distance is king. Smooth is fast." },
  { id: 'buddy', name: 'BUDDY', levelReq: 1, quote: "Hey pal, let's just keep the car out of the wall today." },
  { id: 'drill', name: 'DRILL SGT', levelReq: 5, quote: "YOU ARE BRAKING TOO EARLY! DO YOU WANT TO WIN?" },
  { id: 'bentley', name: 'BENTLEY', levelReq: 10, quote: "The slip angle vector is sub-optimal through Turn 4." },
  { id: 'calm', name: 'CALM PRO', levelReq: 15, quote: "Breathe. Feel the grip through your hands." }
]

const cursorIndex = ref(0)
const previewQuote = ref<string | null>(null)
const previewingId = ref<string | null>(null)
const lockedMessage = ref<string | null>(null)

const activeSlot = computed(() => save.activeSlotId ? save.slots[save.activeSlotId - 1] : null)

// Coaches are always available — `levelReq` is preserved on the records
// for future ranked / story modes but does not gate the picker. (Per user
// request 2026-05-13: "I want to see all of them and be able to use all
// of them.") The locked-card styling below stays as dead UI so the gate
// can be re-enabled later by simply returning `level < levelReq` again.
const isLocked = (_index: number) => false

onMounted(() => {
  if (activeSlot.value) {
    const idx = coaches.findIndex(c => c.id === activeSlot.value!.preferredCoach)
    if (idx !== -1) cursorIndex.value = idx
  }
})

useKeyboard((e: KeyboardEvent) => {
  if (lockedMessage.value || previewQuote.value) {
    // If dialogue is playing, let it consume the event
    return
  }

  if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
    cursorIndex.value = (cursorIndex.value + 1) % coaches.length
    previewCoach(cursorIndex.value)
  } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
    cursorIndex.value = (cursorIndex.value - 1 + coaches.length) % coaches.length
    previewCoach(cursorIndex.value)
  } else if (e.key === 'Enter') {
    trySelect(coaches[cursorIndex.value])
  } else if (e.key === 'Escape' || e.key === 'Backspace' || e.key === 'b') {
    audio.playSfx('cancel')
    router.push('/garage')
  } else if (e.key === ' ') {
    audio.playSfx('cursor_select')
    router.push('/garage/coach/bios')
  }
})

const slideDir = ref('slide-right')

const previewCoach = (index: number) => {
  audio.playSfx('cursor_move')
  if (index > cursorIndex.value) slideDir.value = 'slide-left'
  else if (index < cursorIndex.value) slideDir.value = 'slide-right'

  cursorIndex.value = index
  const c = coaches[index]
  previewingId.value = c.id
  previewQuote.value = c.quote
}

const trySelect = async (c: any) => {
  if (!activeSlot.value) return

  if (activeSlot.value.preferredCoach === c.id) {
    audio.playSfx('cursor_select')
    router.push('/garage')
    return
  }
  
  audio.playSfx('cursor_select')
  audio.playVoice(activeSlot.value.preferredCoach, 'farewell_swap')
  
  activeSlot.value.preferredCoach = c.id
  save.save()
  
  setTimeout(() => {
    audio.playVoice(c.id, 'greet_morning')
    router.push('/garage')
  }, 1000)
}
</script>

<template>
  <PageShell title="COACHES" :hints="['A · SELECT', 'B · GARAGE', 'SPACE · EDIT BIOS', '◀ ▶ MOVE']" bg="neutral">
    <template #heading>
      <div class="heading-block mb-[2vmin] text-center">
        <h1 class="text-title font-title text-silver tracking-[0.3em]">COACHES</h1>
        <div class="heading-rule"></div>
      </div>
    </template>
    
    <!-- Background overrides -->
    <div class="coach-bg absolute inset-0 z-0 pointer-events-none"></div>
    
    <div class="content flex flex-col items-center relative z-10 w-full flex-grow justify-center gap-[4vh]">
      
      <!-- Coach Preview Area -->
      <div class="coach-preview-container relative w-[clamp(180px,40vw,280px)] h-[clamp(180px,40vw,280px)] flex flex-col items-center justify-center">
        <!-- Backdrop Glow -->
        <div class="sprite-backdrop absolute inset-0 rounded-full"
             :class="isLocked(cursorIndex) ? 'locked-backdrop' : (activeSlot?.preferredCoach === coaches[cursorIndex].id ? 'active-backdrop' : 'unlocked-backdrop')">
        </div>
        
        <!-- Sprite -->
        <div class="relative w-full h-full overflow-hidden">
          <Transition :name="slideDir">
            <Sprite 
              :key="coaches[cursorIndex].id"
              :sheet="coaches[cursorIndex].id" 
              :animation="isLocked(cursorIndex) ? 'idle' : 'talk'" 
              class="coach-sprite absolute bottom-0 z-10 w-full h-full" 
              :class="{ 'is-locked-sprite': isLocked(cursorIndex) }"
            />
          </Transition>
        </div>
        
        <!-- Status Overlay -->
        <div class="absolute bottom-[-10px] z-20 flex flex-col items-center w-full">
          <div v-if="isLocked(cursorIndex)" class="bg-ink text-ui-bad font-bold text-body px-4 py-2 border border-slate shadow-lg rounded">
            🔒 LV {{ coaches[cursorIndex].levelReq }}
          </div>
          <div v-else-if="activeSlot?.preferredCoach === coaches[cursorIndex].id" class="flex flex-col items-center gap-2">
            <div class="bg-ui-good/20 border border-ui-good text-ui-good text-body font-bold px-6 py-2 shadow-[0_0_15px_rgba(42,161,152,0.4)] rounded">
              ACTIVE COACH
            </div>
            <div class="text-small text-silver bg-ink/80 px-2 py-1 rounded border border-slate" @click="router.push('/garage/coach/bios')">
              SPACE TO EDIT BIOS
            </div>
          </div>
        </div>
      </div>
      
      <!-- Selection Controls -->
      <div class="coach-controls flex flex-wrap justify-center gap-[clamp(8px,1.5vw,16px)] max-w-[90vw] mt-[2vh]">
        <CyberButton 
          v-for="(c, i) in coaches" 
          :key="c.id"
          :active="cursorIndex === i"
          :variant="cursorIndex === i ? 'primary' : 'dark'"
          class="uppercase"
          :class="isLocked(i) ? 'opacity-60 grayscale' : ''"
          @click="cursorIndex = i; trySelect(c)"
          @mouseenter="cursorIndex !== i && previewCoach(i)"
        >
          <span v-if="isLocked(i)" class="mr-2 text-[1.2em]">🔒</span>
          {{ c.name }}
        </CyberButton>
      </div>
      
    </div>
    
    <template #floating>
      <CoachFloat 
        v-if="lockedMessage"
        :coach-id="'trod'"
        emotion="idle"
        :text="lockedMessage"
        @done="lockedMessage = null"
      />
      <CoachFloat 
        v-else-if="previewQuote && previewingId"
        :coach-id="previewingId"
        emotion="talk"
        :text="previewQuote"
        @done="previewQuote = null"
      />
    </template>
  </PageShell>
</template>

<style scoped>
.coach-bg {
  background: linear-gradient(
    180deg,
    var(--color-ink) 0%,
    var(--color-asphalt-deep) 50%,
    var(--color-ink) 100%
  );
}

.coach-sprite {
  transform: scale(1.3);
  transform-origin: center bottom;
  filter: drop-shadow(0 10px 15px rgba(0, 0, 0, 0.6));
  transition: all 0.3s steps(4);
}

.is-locked-sprite {
  filter: brightness(0) contrast(0) opacity(0.6) drop-shadow(0 0 0 transparent);
  transform: scale(1.3);
}

.sprite-backdrop {
  animation: pulse-glow 3s steps(4) infinite alternate;
}

.unlocked-backdrop {
  background: radial-gradient(circle at center, rgba(42, 161, 152, 0.3) 0%, transparent 70%);
}

.active-backdrop {
  background: radial-gradient(circle at center, rgba(42, 161, 152, 0.5) 0%, transparent 80%);
  animation: pulse-glow-active 2s steps(4) infinite alternate;
}

.locked-backdrop {
  background: radial-gradient(circle at center, rgba(220, 50, 47, 0.15) 0%, transparent 70%);
  animation: none;
}

@keyframes pulse-glow {
  0% { opacity: 0.6; transform: scale(0.9); }
  100% { opacity: 1; transform: scale(1.1); }
}

@keyframes pulse-glow-active {
  0% { opacity: 0.8; transform: scale(0.95); }
  100% { opacity: 1; transform: scale(1.15); }
}

.slide-left-enter-active, .slide-left-leave-active,
.slide-right-enter-active, .slide-right-leave-active {
  transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1), opacity 0.3s;
}

.slide-left-enter-from { transform: translateX(100%); opacity: 0; }
.slide-left-leave-to { transform: translateX(-100%); opacity: 0; }

.slide-right-enter-from { transform: translateX(-100%); opacity: 0; }
.slide-right-leave-to { transform: translateX(100%); opacity: 0; }
</style>

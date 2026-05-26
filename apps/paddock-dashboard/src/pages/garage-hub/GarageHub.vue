<script setup lang="ts">
import { computed, ref, onMounted, onUnmounted } from 'vue'
import { useKeyboard } from '@/shared/lib/useKeyboard'
import { useRouter } from 'vue-router'
import { useSaveStore } from '@/entities/save/model/saveStore'
import { useCoachStore } from '@/entities/coach/model/coachStore'
import { useQuestStore } from '@/entities/quest/model/questStore'
import Tile from './ui/Tile.vue'
import type { TileData } from './ui/Tile.vue'
import CoachFloat from '@/shared/ui/CoachFloat.vue'
import PageShell from '@/shared/ui/PageShell.vue'
import { useAudioStore } from '@/features/audio-playback/model/audioStore'

const router = useRouter()
const save = useSaveStore()
const audio = useAudioStore()
const coach = useCoachStore()
const quest = useQuestStore()

// Real counts from the bridge:
//   coaches → /coach/agents (AGENT_REGISTRY length)
//   quests  → /insights mapped to daily goals in questStore
// While the fetches are in flight we show "—" rather than 0.
const coachesSub = computed(() => {
  if (coach.agentsLoading) return '—'
  if (coach.agentsError) return 'DATA UNAVAILABLE'
  const n = coach.agents.length
  return `${n} AVAILABLE`
})
const questsSub = computed(() => {
  if (quest.isLoading) return '—'
  if (quest.error) return 'DATA UNAVAILABLE'
  const n = quest.daily.length
  return `${n} ACTIVE GOAL${n === 1 ? '' : 'S'}`
})

const tiles = computed<TileData[]>(() => [
  { id: 'track', title: 'TRACK', subText: 'GO RACING', route: '/briefing' },
  { id: 'pit-stall', title: 'PIT STALL', subText: 'CONNECT · TUNE', route: '/garage/pit-stall' },
  { id: 'trainer-card', title: 'TRAINER CARD', subText: 'STATS · MEDALS', route: '/garage/trainer' },
  { id: 'analysis', title: 'ANALYSIS', subText: 'LAPS · CORNERS', route: '/garage/analysis' },
  { id: 'coaches', title: 'COACHES', subText: coachesSub.value, route: '/garage/coach' },
  { id: 'leaderboard', title: 'HIGH SCORES', subText: 'GLOBAL RANKING', route: '/leaderboard' },
  { id: 'quests', title: 'QUEST LOG', subText: questsSub.value, route: '/garage/quests' },
  { id: 'setup', title: 'CAR SETUP', subText: 'AERO · BRAKES', route: '/garage/setup' }
])

const cursorIndex = ref(0)
const isGridView = ref(false)
const greetingActive = ref(true)
const greetingText = "Welcome to the Garage! Ready to hit the track?"
// Hint bar lists every key the page binds in `useKeyboard` below so the
// HintBar dev-time warning passes and users can discover every shortcut.
// B is the unified BACK key (handled by App.vue's global ESC -> router.back,
// plus a local fallback for Backspace/b that returns to the title screen).
const hints = [
  '▲ ▼ SWIPE',
  'A · ENTER',
  'S · SETTINGS',
  'C · CALIBRATE',
  'H · HARDWARE',
  'B · BACK',
]

const moveCursor = (dir: number) => {
  cursorIndex.value = (cursorIndex.value + dir + tiles.value.length) % tiles.value.length
  audio.playSfx('cursor_move')
}

useKeyboard((e: KeyboardEvent) => {
  if (e.key === 'g' || e.key === 'G') {
    isGridView.value = !isGridView.value
    audio.playSfx('cursor_select')
    return
  }
  
  if (isGridView.value) {
    if (e.key === 'ArrowRight') moveCursor(1)
    else if (e.key === 'ArrowLeft') moveCursor(-1)
    else if (e.key === 'ArrowDown') moveCursor(4)
    else if (e.key === 'ArrowUp') moveCursor(-4)
    else if (e.key === 'Enter') onSelect(tiles.value[cursorIndex.value].id)
    else if (e.key === 'Escape' || e.key === 'Backspace' || e.key === 'b') {
      audio.playSfx('cancel')
      save.activeSlotId = null
      router.push('/')
    }
    return
  }

  if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
    moveCursor(1)
  } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
    moveCursor(-1)
  } else if (e.key === 'Enter') {
    if (greetingActive.value) {
      greetingActive.value = false
      audio.playSfx('cursor_select')
      return
    }
    audio.playSfx('cursor_select')
    onSelect(tiles.value[cursorIndex.value].id)
  } else if (e.key === 'Escape' || e.key === 'Backspace' || e.key === 'b') {
    audio.playSfx('cancel')
    save.activeSlotId = null
    router.push('/')
  } else if (e.key === 'c' || e.key === 'C') {
    audio.playSfx('cursor_select')
    router.push('/calibration')
  } else if (e.key === 'h' || e.key === 'H') {
    audio.playSfx('cursor_select')
    router.push('/garage/pit-stall/hardware')
  } else if (e.key === 's' || e.key === 'S' || e.key === ' ') {
    audio.playSfx('cursor_select')
    router.push('/settings')
  }
})

const onSelect = (tileId: string) => {
  const tile = tiles.value.find(t => t.id === tileId)
  if (tile && !tile.disabled) {
    router.push(tile.route)
  }
}

// ── Touch drag navigation ──
const menuRef = ref<HTMLDivElement | null>(null)
let touchStartY = 0
let touchStartX = 0
let touchStartTime = 0

const onTouchStart = (e: TouchEvent) => {
  touchStartY = e.touches[0].clientY
  touchStartX = e.touches[0].clientX
  touchStartTime = Date.now()
}

const onTouchMove = (e: TouchEvent) => {
  const dy = e.touches[0].clientY - touchStartY
  const dx = e.touches[0].clientX - touchStartX
  if (Math.abs(dy) > 10 && Math.abs(dy) > Math.abs(dx)) {
    e.preventDefault()
  }
}

const onTouchEnd = (e: TouchEvent) => {
  const dy = e.changedTouches[0].clientY - touchStartY
  const dx = e.changedTouches[0].clientX - touchStartX
  const dt = Date.now() - touchStartTime
  const absDy = Math.abs(dy)
  const absDx = Math.abs(dx)

  if (dt > 500) return

  if (absDy > 30 && absDy > absDx) {
    if (dy < 0) moveCursor(1)
    else moveCursor(-1)
  } else if (absDx > 50 && absDx > absDy && dx > 0) {
    if (!greetingActive.value) {
      audio.playSfx('cursor_select')
      onSelect(tiles.value[cursorIndex.value].id)
    }
  }
}

onMounted(() => {
  // Kick off the real fetches for the COACHES / QUEST LOG tile subtexts.
  // Both stores cache after first call, so this is safe to call on every
  // mount.
  coach.fetchAgents()
  quest.fetchQuests()

  const el = menuRef.value
  if (el) {
    el.addEventListener('touchstart', onTouchStart, { passive: true })
    el.addEventListener('touchmove', onTouchMove, { passive: false })
    el.addEventListener('touchend', onTouchEnd, { passive: true })
  }
})

onUnmounted(() => {
  const el = menuRef.value
  if (el) {
    el.removeEventListener('touchstart', onTouchStart)
    el.removeEventListener('touchmove', onTouchMove)
    el.removeEventListener('touchend', onTouchEnd)
  }
})
</script>

<template>
  <PageShell title="GARAGE" :hints="[...hints, isGridView ? 'G · SPATIAL' : 'G · GRID']" bg="neutral" :show-heading="false">

    <div class="content flex flex-col items-center justify-center relative z-10 w-full flex-grow min-h-0 overflow-hidden">
      <div class="section-heading mb-[clamp(8px,3vmin,32px)] shrink-0">
        <span class="text-slate tracking-[0.4em] font-title uppercase" :style="{ fontSize: 'clamp(18px, 4vmin, 36px)' }">Garage</span>
      </div>
      
      <div v-if="!isGridView" ref="menuRef" class="spatial-menu-container">
        <div 
          v-for="(t, i) in tiles" 
          :key="t.id"
          :class="[
            'spatial-item',
            (i - cursorIndex + tiles.length) % tiles.length === 0 ? 'focused' :
            (i - cursorIndex + tiles.length) % tiles.length === 1 ? 'next' :
            (i - cursorIndex + tiles.length) % tiles.length === 2 ? 'next-2' :
            (cursorIndex - i + tiles.length) % tiles.length === 1 ? 'prev' :
            (cursorIndex - i + tiles.length) % tiles.length === 2 ? 'prev-2' : 'hidden-item'
          ]"
          @click="cursorIndex = i; if (!t.disabled) onSelect(t.id)"
        >
          <Tile 
            :tile="t" 
            :focused="cursorIndex === i"
            @select="onSelect(t.id)"
            @hover="cursorIndex = i"
          />
        </div>
      </div>

      <div v-else class="grid-menu-container grid grid-cols-4 gap-6 p-8">
        <div 
          v-for="(t, i) in tiles" 
          :key="t.id"
          class="grid-item transition-all duration-150"
          :class="{ 'grid-focused': cursorIndex === i }"
          @click="cursorIndex = i; onSelect(t.id)"
          @mouseover="cursorIndex = i"
        >
          <Tile :tile="t" :focused="cursorIndex === i" compact />
        </div>
      </div>
    </div>
    
    <template #floating>
      <CoachFloat 
        v-if="greetingActive"
        :coach-id="save.activeSlot?.preferredCoach ?? 'trod'"
        :text="greetingText"
        emotion="idle"
        @done="greetingActive = false" 
      />
    </template>
  </PageShell>
</template>

<style scoped>
.section-heading {
  text-align: center;
  position: relative;
  z-index: 20;
}

.section-heading::after {
  content: '';
  display: block;
  width: clamp(80px, 20vw, 200px);
  height: clamp(4px, 1vmin, 8px);
  margin: var(--space-sm) auto 0;
  background: repeating-linear-gradient(
    90deg,
    var(--color-curb-red) 0,
    var(--color-curb-red) clamp(4px, 1vmin, 8px),
    var(--color-curb-white) clamp(4px, 1vmin, 8px),
    var(--color-curb-white) clamp(8px, 2vmin, 16px)
  );
}

.spatial-menu-container {
  position: relative;
  width: 100%;
  height: 50vh;
  perspective: 1500px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  z-index: 10;
  touch-action: none;
  user-select: none;
  -webkit-user-select: none;
}

.spatial-item {
  position: absolute;
  width: clamp(280px, 50vw, 480px);
  transition: transform 0.2s var(--ease-smooth), opacity 0.2s var(--ease-smooth);
  transform-origin: center center;
  opacity: 0;
  pointer-events: none;
  cursor: pointer;
}

.spatial-item.focused {
  transform: translateZ(200px) translateY(0);
  opacity: 1;
  z-index: 10;
  pointer-events: auto;
  filter: drop-shadow(0 20px 40px rgba(0, 0, 0, 0.9));
}

.spatial-item.prev {
  transform: translateZ(0) translateY(-80px) rotateX(15deg);
  opacity: 0.5;
  z-index: 5;
  pointer-events: auto;
}

.spatial-item.prev-2 {
  transform: translateZ(-200px) translateY(-160px) rotateX(30deg);
  opacity: 0.15;
  z-index: 4;
  pointer-events: auto;
}

.spatial-item.next {
  transform: translateZ(0) translateY(80px) rotateX(-15deg);
  opacity: 0.5;
  z-index: 5;
  pointer-events: auto;
}

.spatial-item.next-2 {
  transform: translateZ(-200px) translateY(160px) rotateX(-30deg);
  opacity: 0.15;
  z-index: 4;
  pointer-events: auto;
}

.grid-menu-container {
  width: 100%;
  max-width: 1200px;
  animation: fade-in 0.3s steps(4);
}

.grid-item {
  cursor: pointer;
}

.grid-focused {
  transform: scale(1.08);
  filter: drop-shadow(0 0 15px var(--color-ui-good));
  z-index: 20;
}

@keyframes fade-in {
  from { opacity: 0; transform: scale(0.95); }
  to { opacity: 1; transform: scale(1); }
}

.hidden-item {
  opacity: 0;
}
</style>

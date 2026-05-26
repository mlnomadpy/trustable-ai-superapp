<script setup lang="ts">
import { computed, ref, onMounted, onUnmounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useSaveStore } from '@/entities/save/model/saveStore'
import { useNotificationsStore } from '@/shared/api/notificationStore'
import { useAudioStore } from '@/features/audio-playback/model/audioStore'
import { usePauseStore } from '@/shared/lib/pauseStore'
import { useKeyboard } from '@/shared/lib/useKeyboard'
import { useLoadingStore } from '@/shared/api/loadingStore'
import CyberBadge from '@/shared/ui/core/CyberBadge.vue'
import SimulatorBadge from '@/shared/ui/core/SimulatorBadge.vue'

const saveStore = useSaveStore()
const notificationStore = useNotificationsStore()
const audio = useAudioStore()
const pauseStore = usePauseStore()
const loadingStore = useLoadingStore()
const router = useRouter()

const route = useRoute()

const activeSlot = computed(() => saveStore.activeSlot)

const breadcrumbs = computed(() => {
  const path = route.path
  if (path === '/' || path === '/save' || path === '/garage') return null

  const segments: { label: string; path: string }[] = []
  
  // Always start with GARAGE as the root for authenticated pages
  if (path.startsWith('/garage') || path.startsWith('/analysis') || path.startsWith('/settings') || path.startsWith('/notifications') || path.startsWith('/leaderboard')) {
    segments.push({ label: 'GARAGE', path: '/garage' })
  }

  // Route-specific segments
  const routeMap: Record<string, { label: string; parent?: string }> = {
    '/garage/setup': { label: 'CAR SETUP' },
    '/garage/trainer': { label: 'TRAINER CARD' },
    '/garage/coach': { label: 'COACH' },
    '/garage/coach/bios': { label: 'BIOS', parent: '/garage/coach' },
    '/garage/pit-stall': { label: 'PIT STALL' },
    '/garage/pit-stall/hardware': { label: 'HARDWARE', parent: '/garage/pit-stall' },
    '/garage/quests': { label: 'QUESTS' },
    '/garage/sponsors': { label: 'SPONSORS' },
    '/garage/analysis': { label: 'ANALYSIS' },
    '/analysis/lap-times': { label: 'LAP TIMES', parent: '/garage/analysis' },
    '/analysis/compare': { label: 'COMPARE', parent: '/garage/analysis' },
    '/analysis/corners': { label: 'CORNERS', parent: '/garage/analysis' },
    '/analysis/straights': { label: 'STRAIGHTS', parent: '/garage/analysis' },
    '/analysis/track': { label: 'TRACK WALK', parent: '/garage/analysis' },
    '/analysis/atlas': { label: 'ATLAS', parent: '/garage/analysis' },
    '/analysis/evolution': { label: 'EVOLUTION', parent: '/garage/analysis' },
    '/analysis/pedals': { label: 'PEDALS', parent: '/garage/analysis' },
    '/analysis/ghosts': { label: 'GHOSTS', parent: '/garage/analysis' },
    '/analysis/sql': { label: 'SQL', parent: '/garage/analysis' },
    '/settings': { label: 'SETTINGS' },
    '/notifications': { label: 'INBOX' },
    '/leaderboard': { label: 'RANKING' },
  }

  const entry = routeMap[path]
  if (!entry) return null

  // If there's a parent, add it
  if (entry.parent) {
    const parentEntry = routeMap[entry.parent]
    if (parentEntry) segments.push({ label: parentEntry.label, path: entry.parent })
  }

  // Add current (non-tappable)
  segments.push({ label: entry.label, path: '' })

  return segments.length > 1 ? segments : null
})

const time = ref('')

const props = defineProps<{ extra?: string }>()

useKeyboard((e: KeyboardEvent) => {
  const activeTag = document.activeElement?.tagName
  if ((e.key === 'n' || e.key === 'N') && activeTag !== 'TEXTAREA' && activeTag !== 'INPUT') {
    audio.playSfx('cursor_select')
    router.push('/notifications')
  }
})

const goToNotifications = () => {
  audio.playSfx('cursor_select')
  router.push('/notifications')
}

const goToSettings = () => {
  audio.playSfx('cursor_select')
  router.push('/settings')
}

const openPause = () => {
  if (route.path !== '/') {
    audio.playSfx('transition_wipe')
    pauseStore.togglePause()
  }
}

let timer: number
onMounted(() => {
  const updateTime = () => {
    const d = new Date()
    time.value = `${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}`
  }
  updateTime()
  timer = window.setInterval(updateTime, 60000)
})

onUnmounted(() => {
  clearInterval(timer)
})
</script>

<template>
  <nav class="status-bar pixelated" role="navigation" aria-label="Status bar">
    <!-- Left: Breadcrumb trail or Driver info -->
    <div v-if="breadcrumbs" class="bar-left breadcrumb-trail">
      <template v-for="(crumb, i) in breadcrumbs" :key="i">
        <button 
          v-if="crumb.path" 
          class="crumb-btn"
          @click="audio.playSfx('cursor_select'); router.push(crumb.path)"
        >
          {{ crumb.label }}
        </button>
        <span v-else class="crumb-current">{{ crumb.label }}</span>
        <span v-if="i < breadcrumbs.length - 1" class="crumb-sep" aria-hidden="true">›</span>
      </template>
    </div>
    <button 
      v-else-if="activeSlot" 
      class="bar-left bar-btn" 
      aria-label="Open settings"
      @click="goToSettings"
    >
      <span class="driver-name">{{ activeSlot.driverName.toUpperCase() }}</span>
      <span class="bar-separator">·</span>
      <span class="driver-level">LV.{{ activeSlot.level }}</span>
    </button>
    <div class="bar-left" v-else>
      <span class="text-silver/50">NO DRIVER</span>
    </div>

    <!-- Center: Pause button OR Loading indicator -->
    <div class="bar-center">
      <div v-if="loadingStore.isLoading" class="loading-status">
        <span class="loading-label">
          [{{ loadingStore.source === 'adk' ? 'PADDOCK AI THINKING' : 
             loadingStore.source === 'duckdb' ? 'SQL ENGINE BUSY' : 'SYSTEM LOADING' }}]
        </span>
      </div>
      <button 
        v-else
        class="bar-btn" 
        aria-label="Pause menu"
        @click="openPause"
      >
        <span class="pause-icon" aria-hidden="true">▮▮</span>
      </button>
    </div>


    <!-- Right: Simulator pill + Notifications + Clock -->
    <div class="bar-right">
      <SimulatorBadge />
      <button
        class="bar-btn"
        aria-label="Notifications"
        @click="goToNotifications"
      >
        <span v-if="notificationStore.unreadCount > 0" class="notif-badge">{{ notificationStore.unreadCount }}</span>
        <svg class="bell-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"></path>
          <path d="M13.73 21a2 2 0 0 1-3.46 0"></path>
        </svg>
        <span class="clock font-nums">{{ time }}</span>
      </button>
    </div>
  </nav>
</template>

<style scoped>
.status-bar {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: calc(var(--safe-top) + 32px);
  background: linear-gradient(180deg, var(--color-ink) 0%, rgba(11, 12, 16, 0.8) 100%);
  display: flex;
  justify-content: space-between;
  align-items: flex-end; /* Align to bottom of bar, safe area handles top */
  padding: 0 calc(var(--safe-right) + var(--space-md)) 4px calc(var(--safe-left) + var(--space-md));
  font-family: var(--font-ui);
  font-size: clamp(10px, calc(2vmin * var(--app-scale)), 20px);
  z-index: var(--z-sticky);
  clip-path: none; /* Removed restrictive clip path to fill width */
  border-bottom: 2px solid var(--color-ui-good);
  box-shadow: 0 0 10px var(--color-ui-good);
}

.status-bar::after {
  display: none; /* Removed the old decorative rule since we use border-bottom */
}


/* Shared button reset for all tappable zones.
   Bar is visually 32px tall; we extend the hit area via a transparent
   pseudo-element so taps register on a full 44px target without
   visually growing the chip. */
.bar-btn {
  background: none;
  border: none;
  outline: none;
  cursor: pointer;
  color: inherit;
  font: inherit;
  padding: 0 clamp(4px, 1vw, 8px);
  display: flex;
  align-items: center;
  gap: clamp(4px, 1vw, 10px);
  z-index: 2;
  -webkit-tap-highlight-color: transparent;
  transition: opacity var(--duration-fast, 150ms) ease;
  position: relative;
  min-height: 100%;
}

.bar-btn::after {
  content: '';
  position: absolute;
  left: 0;
  right: 0;
  top: 50%;
  height: var(--touch-target-min);
  transform: translateY(-50%);
  /* Invisible — only expands hit-test region */
}

.bar-btn:active {
  opacity: 0.6;
}

.bar-left { flex: 1; }
.bar-center { flex: 0 0 auto; }
.bar-right {
  flex: 1;
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: clamp(6px, 1.2vw, 12px);
}

.driver-name {
  color: var(--color-ui-info);
  font-weight: bold;
  text-shadow: 0 0 4px rgba(69, 183, 209, 0.5);
}

.driver-level {
  color: var(--color-silver);
}

.bar-separator {
  color: var(--color-slate);
}

.pause-icon {
  color: var(--color-silver);
  font-size: clamp(8px, 2vmin, 16px);
  letter-spacing: -2px;
  opacity: 0.7;
  transition: opacity var(--duration-fast, 150ms) ease;
}

.loading-status {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
}

.loading-label {
  color: var(--color-ui-info);
  font-weight: 900;
  font-size: clamp(8px, 1.5vmin, 14px);
  letter-spacing: 0.1em;
  text-shadow: 0 0 8px var(--color-ui-info);
  animation: pulse-loading 0.8s steps(2) infinite;
}

@keyframes pulse-loading {
  0% { opacity: 0.7; transform: scale(0.98); }
  100% { opacity: 1; transform: scale(1); }
}


.bar-btn:active .pause-icon {
  opacity: 1;
  color: var(--color-ui-warn);
}

.bell-icon {
  width: clamp(14px, 3vmin, 22px);
  height: clamp(14px, 3vmin, 22px);
  color: var(--color-silver);
  opacity: 0.7;
}

.clock {
  color: var(--color-silver);
  letter-spacing: 0.1em;
  text-shadow: 0 0 4px rgba(197, 198, 199, 0.4);
}

.notif-badge {
  background: var(--color-ui-warn);
  color: var(--color-ink);
  font-size: clamp(8px, 1.8vmin, 14px);
  font-weight: bold;
  width: clamp(16px, 3.5vmin, 24px);
  height: clamp(16px, 3.5vmin, 24px);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  animation: dot-pulse 1s infinite alternate;
  box-shadow: 0 0 10px var(--color-ui-warn);
}

@keyframes dot-pulse {
  0% { opacity: 0.4; transform: scale(0.8); }
  100% { opacity: 1; transform: scale(1.2); }
}

/* Breadcrumb trail */
.breadcrumb-trail {
  display: flex;
  align-items: center;
  gap: clamp(2px, 0.5vw, 4px);
  overflow: hidden;
}

.crumb-btn {
  background: none;
  border: none;
  outline: none;
  cursor: pointer;
  color: var(--color-slate);
  font: inherit;
  font-size: 0.85em;
  padding: 0 clamp(4px, 1vw, 6px);
  white-space: nowrap;
  -webkit-tap-highlight-color: transparent;
  transition: color var(--duration-fast) ease;
  position: relative;
  display: inline-flex;
  align-items: center;
  min-height: 100%;
}

.crumb-btn::after {
  content: '';
  position: absolute;
  left: 0;
  right: 0;
  top: 50%;
  height: var(--touch-target-min);
  transform: translateY(-50%);
}

.crumb-btn:active {
  color: var(--color-ui-good);
}

.crumb-sep {
  color: var(--color-slate);
  opacity: 0.5;
  font-size: 0.9em;
}

.crumb-current {
  color: var(--color-ui-info);
  font-weight: bold;
  white-space: nowrap;
  text-shadow: 0 0 4px rgba(69, 183, 209, 0.5);
}
</style>

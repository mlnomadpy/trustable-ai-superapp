<script setup lang="ts">
/**
 * Modules tab: keeps the original Analysis-Hall tile grid so the
 * existing sub-pages (LAP TIMES HALL, CORNER MASTERY, etc.) remain
 * one click away.
 */
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useSessionStore } from '@/entities/session/model/sessionStore'
import { useSaveStore } from '@/entities/save/model/saveStore'
import { useAudioStore } from '@/features/audio-playback/model/audioStore'
import CyberTile from '@/shared/ui/core/CyberTile.vue'

const router = useRouter()
const sessionStore = useSessionStore()
const save = useSaveStore()
const audio = useAudioStore()

const sessionCount = computed(() => sessionStore.sessions.length || (save.activeSlot?.sessions?.length ?? 0))
const lapCount = computed(() => {
  const live = sessionStore.sessions.reduce((acc, s) => acc + (s.lap_count ?? 0), 0)
  if (live > 0) return live
  return save.activeSlot?.sessions?.reduce((acc, s) => acc + (s.laps?.length ?? 0), 0) ?? 0
})
const hasSessions = computed(() =>
  sessionStore.sessions.length > 0 || (save.activeSlot?.sessions?.length ?? 0) > 0,
)

// Tile subtexts intentionally describe the *kind* of analysis, not
// hardcoded counts. The previous "11 CORNERS GRADED A-F" and
// "3 STRAIGHTS" literals were invented — Sonoma's corner/straight
// counts come from /session/<sid>/corners and /straight_line_speed
// and vary per session. Drop the count subtexts rather than wiring
// per-session fetches into a navigation tile.
const tiles = computed(() => [
  { id: 'lap-times', title: 'LAP TIMES HALL', desc: `${lapCount.value} LAPS THIS SEASON`, route: '/analysis/lap-times' },
  { id: 'corners',   title: 'CORNER MASTERY', desc: 'PER-CORNER GRADES',                  route: '/analysis/corners' },
  { id: 'straights', title: 'STRAIGHTS & SPEED', desc: 'TOP SPEED · DRAG',                route: '/analysis/straights' },
  { id: 'track',     title: 'TRACK ATLAS',    desc: 'ELEVATION · MARKERS',                route: '/analysis/atlas' },
  { id: 'evolution', title: 'DRIVER EVOLUTION', desc: `${sessionCount.value} SESSIONS`,   route: '/analysis/evolution' },
  { id: 'pedals',    title: 'PEDAL PROFILE',  desc: 'THROTTLE · BRAKE',                   route: '/analysis/pedals' },
  { id: 'sql',       title: 'SQL CONSOLE',    desc: 'AD-HOC QUERIES',                     route: '/analysis/sql' },
  { id: 'ghosts',    title: 'GHOST DATA',     desc: 'COMING SOON',                        route: '/analysis/ghosts', wip: true },
  { id: 'replay',    title: 'VCR REPLAY',     desc: 'COMING SOON',                        route: '/analysis/replay', wip: true },
])

function go(tile: ReturnType<typeof tiles.value>[number]) {
  if (!hasSessions.value || tile.wip) { audio.playSfx('cancel'); return }
  audio.playSfx('cursor_select')
  router.push(tile.route)
}
</script>

<template>
  <div class="h-full grid grid-cols-3 gap-2 content-start overflow-y-auto">
    <CyberTile
      v-for="t in tiles"
      :key="t.id"
      :title="t.title"
      :subText="t.desc"
      :focused="false"
      :locked="!hasSessions || t.wip"
      :showKerb="true"
      :variant="t.wip ? 'glass' : 'ink'"
      @click="() => go(t)"
    />
  </div>
</template>

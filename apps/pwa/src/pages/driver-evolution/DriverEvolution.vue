<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAudioStore } from '@/features/audio-playback/model/audioStore'
import { useSaveStore } from '@/entities/save/model/saveStore'
import { useKeyboard } from '@/shared/lib/useKeyboard'
import { bridge } from '@/shared/api/bridge'
import { formatLapTime } from '@/shared/lib/lap'
import PageShell from '@/shared/ui/PageShell.vue'
import Frame from '@/shared/ui/core/Frame.vue'
import PixelChart from '@/shared/ui/core/PixelChart.vue'
import CoachFloat from '@/shared/ui/CoachFloat.vue'
import { useSwipeGesture } from '@/shared/lib/useSwipeGesture'

const router = useRouter()
const audio = useAudioStore()
const save = useSaveStore()

// We need a minimum of 2 sessions to show a meaningful trend
const hasEnoughSessions = ref(false)

interface SessionPoint {
  index: number
  bestLap: number
  // Median is only populated when the /driver/<id>/evolution endpoint
  // returns it (the per-session aggregate path doesn't carry median).
  // Null means "no honest source" — the median chart series simply
  // doesn't render rather than showing a synthesized `best * 1.01`.
  medianLap: number | null
  sectorPbs: Record<string, number>  // {s1: 35.1, s2: 33.7, ...}
}

const sessions = ref<SessionPoint[]>([])

// `biggestGain.deltaSec` is the per-sector time improvement in **seconds**
// (sector_pbs from the bridge are seconds). Previous versions called this
// `deltaKmh`, which was a copy-paste leftover from an earlier "+km/h"
// design — confusing because the rendered value is `−Xs`.
const heroData = ref({
  firstBest: '--:--.--',
  latestBest: '--:--.--',
  improvement: '0.0',
  sessionCount: 0,
  biggestGain: { corner: '--', deltaSec: 0 },
})

interface EvolutionRow {
  session_id: string
  started_at: string | null
  session_index: number
  best_lap_s: number
  median_lap_s: number
  lap_count: number
  sector_pbs: Record<string, number>
}
interface EvolutionResponse {
  driver_id: string
  track: string | null
  session_count: number
  evolution: EvolutionRow[]
  summary: { first_best_s: number; latest_best_s: number; improvement_s: number } | null
  note?: string
}

onMounted(async () => {
  const driverId = save.activeSlot?.driverName ?? 'driver'
  // Try the dedicated evolution endpoint first — it returns properly
  // computed median + per-sector PBs across N sessions for one driver.
  // It can 204 ("need >= 5 sessions") or 404 ("no sessions"). Both fall
  // through to the legacy /sessions aggregate so this screen still
  // renders something useful in development.
  let loadedFromEvolution = false
  try {
    const url = `/driver/${encodeURIComponent(driverId)}/evolution?track=Sonoma+Raceway`
    const res = await bridge.get<EvolutionResponse>(url)
    if (Array.isArray(res?.evolution) && res.evolution.length >= 2) {
      hasEnoughSessions.value = true
      sessions.value = res.evolution.map((r) => ({
        index: r.session_index,
        bestLap: r.best_lap_s,
        medianLap: r.median_lap_s,
        sectorPbs: r.sector_pbs ?? {},
      }))
      if (res.summary) {
        // Biggest-gain: find the sector where the PB shrank the most between
        // the first and last session in the evolution window. No hardcoded
        // T11 or made-up km/h multiplier.
        const first = res.evolution[0]?.sector_pbs ?? {}
        const last  = res.evolution[res.evolution.length - 1]?.sector_pbs ?? {}
        let bestSector: { key: string; deltaSec: number } | null = null
        for (const k of Object.keys(first)) {
          if (typeof first[k] === 'number' && typeof last[k] === 'number') {
            const d = first[k] - last[k]   // positive = got faster
            if (!bestSector || d > bestSector.deltaSec) bestSector = { key: k, deltaSec: d }
          }
        }
        heroData.value = {
          firstBest: formatLap(res.summary.first_best_s),
          latestBest: formatLap(res.summary.latest_best_s),
          improvement: res.summary.improvement_s.toFixed(1),
          sessionCount: res.evolution.length,
          biggestGain: bestSector && bestSector.deltaSec > 0
            ? { corner: bestSector.key.toUpperCase(), deltaSec: bestSector.deltaSec }
            : { corner: '', deltaSec: 0 },
        }
      }
      loadedFromEvolution = true
    }
  } catch {
    // 204/404/etc. — fall through to the sessions aggregate below.
  }

  if (!loadedFromEvolution) {
    try {
      const res = await bridge.get<{ sessions: any[]; count: number }>('/sessions?limit=100')
      const realSessions = res.sessions
        .filter((s: any) => s.best_lap_s != null)
        .reverse() // oldest first

      if (realSessions.length >= 2) {
        hasEnoughSessions.value = true
        sessions.value = realSessions.map((s: any, i: number) => ({
          index: i + 1,
          bestLap: s.best_lap_s,
          // /sessions doesn't expose median_lap_s — leave null. The
          // template skips the median series when no point has it.
          medianLap: null,
          sectorPbs: {},
        }))
        const first = realSessions[0].best_lap_s
        const latest = realSessions[realSessions.length - 1].best_lap_s
        heroData.value = {
          firstBest: formatLap(first),
          latestBest: formatLap(latest),
          improvement: (first - latest).toFixed(1),
          sessionCount: realSessions.length,
          // Sessions-aggregate path: no per-sector data, so omit biggest-gain.
          biggestGain: { corner: '', deltaSec: 0 },
        }
      }
    } catch {
      hasEnoughSessions.value = false
    }
  }

  audio.playSfx('score_total')
})

// Per-sector PB heatmap: gradient from worst→best PB across the evolution
// timeline. Returns [] when no sector PBs were returned — the template
// renders a "no historical data yet" empty state. No synthetic
// pre-launch heatmap.
const cornerPBs = computed(() => {
  const keys = new Set<string>()
  for (const s of sessions.value) Object.keys(s.sectorPbs).forEach((k) => keys.add(k))
  const sectorKeys = Array.from(keys).sort()
  if (!sectorKeys.length) return [] as { id: string; grades: number[] }[]
  return sectorKeys.map((k) => {
    const vals = sessions.value.map((s) => s.sectorPbs[k] ?? Number.POSITIVE_INFINITY)
    const finite = vals.filter((v) => Number.isFinite(v))
    if (!finite.length) return { id: k.toUpperCase(), grades: vals.map(() => 0) }
    const min = Math.min(...finite)
    const max = Math.max(...finite)
    const grades = vals.map((v) => {
      if (!Number.isFinite(v)) return 0
      if (max === min) return 4
      // Lower time = better. Normalise inverted to a 0–4 step.
      const t = (max - v) / (max - min)
      return Math.round(t * 4)
    })
    return { id: k.toUpperCase(), grades }
  })
})

const cursorIndex = ref(0)
const cur = computed(() => sessions.value[cursorIndex.value])

useKeyboard((e: KeyboardEvent) => {
  if (e.key === 'ArrowRight') {
    cursorIndex.value = Math.min(cursorIndex.value + 1, sessions.value.length - 1)
    audio.playSfx('cursor_move')
  } else if (e.key === 'ArrowLeft') {
    cursorIndex.value = Math.max(cursorIndex.value - 1, 0)
    audio.playSfx('cursor_move')
  } else if (e.key === 'Enter' || e.key === 'a') {
    // Open lap times hall for that session
    audio.playSfx('cursor_select')
  } else if (e.key === 'Escape' || e.key === 'Backspace' || e.key === 'b') {
    audio.playSfx('cancel')
    router.push('/garage/analysis')
  }
})

useSwipeGesture(null, {
  onSwipeLeft: () => {
    cursorIndex.value = Math.min(cursorIndex.value + 5, sessions.value.length - 1)
    audio.playSfx('cursor_move')
  },
  onSwipeRight: () => {
    cursorIndex.value = Math.max(cursorIndex.value - 5, 0)
    audio.playSfx('cursor_move')
  },
})

// Multi-session evolution view — 1-decimal precision matches the HUD /
// Stage Clear convention so a "best lap" looks the same here as it did
// to the driver in the car.
const formatLap = (seconds: number) => formatLapTime(seconds, 1)

const getHeatmapColor = (grade: number) => {
  switch (grade) {
    case 0: return 'bg-charcoal'
    case 1: return 'bg-[#3A4550]'
    case 2: return 'bg-slate'
    case 3: return 'bg-[#A0AAB5]'
    case 4: return 'bg-silver'
    default: return 'bg-charcoal'
  }
}
</script>

<template>
  <PageShell :hints="['A · OPEN SESSION', '◀ ▶ SCRUB', 'B · BACK']" bg="cool">
    <template #heading>
      <div class="heading-block mb-[1.5vh]">
        <h1 class="text-title font-title text-silver tracking-[0.2em]">DRIVER EVOLUTION · {{ save.activeSlot?.driverName ?? 'DRIVER' }} AT SONOMA</h1>
        <div class="heading-rule"></div>
      </div>
    </template>

      <template v-if="hasEnoughSessions">
        <Frame variant="card" padding="8px" class="mb-4">
          <div class="text-title font-bold text-white">
            FIRST {{ heroData.firstBest }} <span class="text-slate mx-1">→</span> LATEST {{ heroData.latestBest }}
          </div>
          <div class="text-body text-ui-good font-bold mt-1 drop-shadow-[1px_1px_0_#000]">
            ▼ {{ heroData.improvement }}s IMPROVEMENT OVER {{ heroData.sessionCount }} SESSIONS
          </div>
          <div v-if="heroData.biggestGain.corner" class="text-body text-silver mt-1">
            <span class="text-ui-warn">⚡</span> Best sector gain: <span class="text-white font-bold">{{ heroData.biggestGain.corner }}</span>
            <span class="text-ui-good ml-1">−{{ heroData.biggestGain.deltaSec.toFixed(2) }}s</span>
            since session #1
          </div>
        </Frame>
        
        <div class="grid grid-cols-[2fr_1fr] gap-4 flex-grow min-h-0 pb-16">
          <Frame variant="default" padding="8px" class="relative flex flex-col overflow-hidden">
            <div class="text-body text-silver mb-2 flex justify-between">
              <div>
                <span class="text-ui-good font-bold mr-2">─ BEST</span>
                <span v-if="sessions.some(s => s.medianLap != null)" class="text-slate font-bold">─ MEDIAN</span>
              </div>
              <div class="font-bold text-white" v-if="cur">SESSION #{{ cur.index }}</div>
            </div>

            <div class="flex-grow relative border-l border-b border-slate ml-8 mb-6 mt-2">
              <PixelChart
                :data="sessions.map(s => s.bestLap)"
                color="var(--color-neon-green)"
                class="absolute inset-0"
                :width="600"
                :height="200"
              />
              <!-- Median series only renders when at least one point carries
                   a real median_lap_s from /driver/<id>/evolution. -->
              <PixelChart
                v-if="sessions.some(s => s.medianLap != null)"
                :data="sessions.map(s => s.medianLap ?? s.bestLap)"
                color="var(--color-slate)"
                class="absolute inset-0 opacity-50"
                :width="600"
                :height="200"
                :stroke-width="1"
              />
              
              <div class="absolute -left-[32px] top-[-8px] text-small text-silver" v-if="sessions.length">{{ formatLap(Math.min(...sessions.map(s => s.bestLap))) }}</div>
              <div class="absolute -left-[32px] bottom-[-8px] text-small text-silver" v-if="sessions.length">{{ formatLap(Math.max(...sessions.map(s => s.bestLap))) }}</div>
              <div class="absolute -bottom-5 left-0 text-small text-silver">#1</div>
              <div class="absolute -bottom-5 right-0 text-small text-silver">#{{ sessions.length }}</div>
              
              <!-- Selected Lap Display -->
              <div class="absolute -bottom-5 left-1/2 -translate-x-1/2 text-body font-bold flex gap-2" v-if="cur">
                <span class="text-ui-good">{{ formatLap(cur.bestLap) }}</span>
              </div>
            </div>
          </Frame>
          
          <Frame variant="default" padding="8px" class="flex flex-col text-body overflow-hidden relative">
            <div class="text-silver mb-2 leading-tight font-bold">PER-CORNER<br>HEATMAP</div>
            <div v-if="cornerPBs.length === 0" class="flex-grow flex items-center justify-center text-small text-slate tracking-widest uppercase text-center px-2">
              NO HISTORICAL SECTOR DATA YET.
            </div>
            <template v-else>
              <div class="flex flex-col gap-2">
                <div class="flex justify-between text-small text-slate mb-1">
                  <span>#1</span><span>#{{ sessions.length }}</span>
                </div>
                <div v-for="c in cornerPBs" :key="c.id" class="flex gap-2 items-center">
                  <span class="w-6 text-silver font-bold">{{ c.id }}</span>
                  <div class="flex flex-grow gap-[2px]">
                    <div v-for="(g, i) in c.grades" :key="`${c.id}-lap-${i}`" class="h-4 flex-grow" :class="getHeatmapColor(g)"></div>
                  </div>
                </div>
              </div>
              <div class="absolute bottom-2 text-center w-full text-small text-slate pr-4">
                better → █
              </div>
            </template>
          </Frame>
        </div>
      </template>
      <template v-else>
        <Frame variant="default" class="flex items-center justify-center h-full">
           <p class="text-title text-silver animate-pulse">NOT ENOUGH SESSION DATA YET...</p>
        </Frame>
      </template>
      
      <template #floating>
        <CoachFloat
          v-if="heroData.biggestGain.corner"
          emotion="victory"
          :text="`${heroData.biggestGain.corner} is where you found ${heroData.biggestGain.deltaSec.toFixed(2)}s. Don't lose it.`"
        />
      </template>
  </PageShell>
</template>


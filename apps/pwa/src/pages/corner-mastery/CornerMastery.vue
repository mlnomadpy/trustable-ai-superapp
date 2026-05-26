<script setup lang="ts">
/**
 * Corner Mastery — per-corner deep-dive screen.
 *
 * Pre-2026-05-13 this page rendered:
 *   • Hardcoded `throttle: { min, q1, med, q3, max }` per corner — pure
 *     mock data. The throttle box-plot was always the same regardless of
 *     session.
 *   • Hardcoded `[20, 45, 80, 85, 70, 30, 10, 0]` brake-consistency chart.
 *   • Missing `Frame` and `PixelChart` imports — `<PixelChart>` rendered
 *     as raw HTML and silently failed.
 *
 * Now:
 *   • Throttle box-plot is real, sourced from /session/<sid>/throttle_corner_box
 *     (analytics.py — quartile stats per corner).
 *   • Brake consistency renders real per-corner peak decel from
 *     /session/<sid>/brake_acceleration (peak g_long during heavy-brake zones).
 *   • Imports fixed.
 *   • SVG turn-id resolution uses nextTick + bounded RAF (same race-tolerant
 *     pattern as TrackAtlas / TrackWalk).
 */
import { ref, computed, nextTick, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAudioStore } from '@/features/audio-playback/model/audioStore'
import { useSessionStore } from '@/entities/session/model/sessionStore'
import { useKeyboard } from '@/shared/lib/useKeyboard'
import { bridge } from '@/shared/api/bridge'
import { formatLapTime } from '@/shared/lib/lap'
import PageShell from '@/shared/ui/PageShell.vue'
import Frame from '@/shared/ui/core/Frame.vue'
import PixelChart from '@/shared/ui/core/PixelChart.vue'
import TrackMap from '@/shared/ui/core/TrackMap.vue'

const router = useRouter()
const audio = useAudioStore()
const session = useSessionStore()

interface Corner {
  id: string
  progress: number
  svgTurnId: number | undefined
  name: string
  grade: string
  entry: number | null
  apex: number | null
  exit: number | null
  brake: number | null
  glat: number | null
  time: number | null
  delta: string
  class: string
  /** Throttle box-plot from /session/<sid>/throttle_corner_box. Null until loaded. */
  throttle: { min: number; q1: number; med: number; q3: number; max: number } | null
  /** Average peak deceleration in this corner, g (negative). Null until loaded. */
  peakDecelG: number | null
  /** Average brake-zone duration, seconds. Null until loaded. */
  brakeDurationS: number | null
}

// Static layout: corner positions on the track map. Names MUST match the
// bridge convention ("Turn N" / "The Carousel") so the merge below fires.
const STATIC_CORNERS: Corner[] = [
  { id: 'T1',  progress:  8, svgTurnId: undefined, name: 'Turn 1',       grade: '--', entry: null, apex: null, exit: null, brake: null, glat: null, time: null, delta: '--', class: 'med', throttle: null, peakDecelG: null, brakeDurationS: null },
  { id: 'T2',  progress: 14, svgTurnId: undefined, name: 'Turn 2',       grade: '--', entry: null, apex: null, exit: null, brake: null, glat: null, time: null, delta: '--', class: 'med', throttle: null, peakDecelG: null, brakeDurationS: null },
  { id: 'T3',  progress: 18, svgTurnId: undefined, name: 'Turn 3',       grade: '--', entry: null, apex: null, exit: null, brake: null, glat: null, time: null, delta: '--', class: 'med', throttle: null, peakDecelG: null, brakeDurationS: null },
  { id: 'T3a', progress: 21, svgTurnId: undefined, name: 'Turn 3a',      grade: '--', entry: null, apex: null, exit: null, brake: null, glat: null, time: null, delta: '--', class: 'med', throttle: null, peakDecelG: null, brakeDurationS: null },
  { id: 'T4',  progress: 24, svgTurnId: undefined, name: 'Turn 4',       grade: '--', entry: null, apex: null, exit: null, brake: null, glat: null, time: null, delta: '--', class: 'med', throttle: null, peakDecelG: null, brakeDurationS: null },
  { id: 'T5',  progress: 30, svgTurnId: undefined, name: 'Turn 5',       grade: '--', entry: null, apex: null, exit: null, brake: null, glat: null, time: null, delta: '--', class: 'med', throttle: null, peakDecelG: null, brakeDurationS: null },
  { id: 'T6',  progress: 45, svgTurnId: undefined, name: 'The Carousel', grade: '--', entry: null, apex: null, exit: null, brake: null, glat: null, time: null, delta: '--', class: 'med', throttle: null, peakDecelG: null, brakeDurationS: null },
  { id: 'T7',  progress: 55, svgTurnId: undefined, name: 'Turn 7',       grade: '--', entry: null, apex: null, exit: null, brake: null, glat: null, time: null, delta: '--', class: 'med', throttle: null, peakDecelG: null, brakeDurationS: null },
  { id: 'T8',  progress: 65, svgTurnId: undefined, name: 'Turn 8',       grade: '--', entry: null, apex: null, exit: null, brake: null, glat: null, time: null, delta: '--', class: 'med', throttle: null, peakDecelG: null, brakeDurationS: null },
  { id: 'T8a', progress: 68, svgTurnId: undefined, name: 'Turn 8a',      grade: '--', entry: null, apex: null, exit: null, brake: null, glat: null, time: null, delta: '--', class: 'med', throttle: null, peakDecelG: null, brakeDurationS: null },
  { id: 'T9',  progress: 70, svgTurnId: undefined, name: 'Turn 9',       grade: '--', entry: null, apex: null, exit: null, brake: null, glat: null, time: null, delta: '--', class: 'med', throttle: null, peakDecelG: null, brakeDurationS: null },
  { id: 'T10', progress: 80, svgTurnId: undefined, name: 'Turn 10',      grade: '--', entry: null, apex: null, exit: null, brake: null, glat: null, time: null, delta: '--', class: 'med', throttle: null, peakDecelG: null, brakeDurationS: null },
  { id: 'T11', progress: 90, svgTurnId: undefined, name: 'Turn 11',      grade: '--', entry: null, apex: null, exit: null, brake: null, glat: null, time: null, delta: '--', class: 'med', throttle: null, peakDecelG: null, brakeDurationS: null },
]

const corners = ref<Corner[]>(STATIC_CORNERS.map(c => ({ ...c })))
const trackMapRef = ref<any>(null)
const cursorIndex = ref(0)
const cur = computed(() => corners.value[cursorIndex.value])
const sessionUsed = ref<string | null>(null)

// Explicit error UI — mirrors PreBrief.vue's `briefError`. Each fetch
// records a per-feed error message so the user knows WHICH bridge endpoint
// failed instead of silently rendering empty charts. Cleared when a fetch
// succeeds. Surface in template as a "CORNER DATA UNAVAILABLE" panel.
const pageError = ref<string | null>(null)
const feedErrors = ref<Record<string, string>>({})

const activeSessionId = computed(() => {
  const withLaps = session.sessions.filter(s => (s.lap_count ?? 0) > 0)
  return session.activeSessionId ?? withLaps[0]?.session_id ?? null
})

interface ScorecardCorner {
  corner?: string
  name?: string
  grade?: string
  entry_speed_kmh?: number
  avg_entry_kmh?: number
  apex_speed_kmh?: number
  min_speed_kmh?: number
  exit_speed_kmh?: number
  avg_exit_kmh?: number
  peak_brake_bar?: number
  peak_g_lat?: number
  max_lateral_g?: number
  time_s?: number
  delta_s?: number
}

async function fetchScorecard(sid: string) {
  try {
    const data = await bridge.get<{ scorecard?: { corners: ScorecardCorner[] } }>(
      `/session/${sid}/scorecard`,
    )
    const list = data?.scorecard?.corners ?? (data as any)?.corners ?? []
    if (!Array.isArray(list)) return
    const cardMap = new Map<string, ScorecardCorner>()
    for (const c of list) cardMap.set((c.corner ?? c.name ?? '').trim(), c)
    corners.value.forEach((corner) => {
      const card = cardMap.get(corner.name)
                ?? cardMap.get(`Turn ${corner.id.replace('T', '')}`)
                ?? cardMap.get(corner.id)
      if (!card) return
      corner.grade = card.grade ?? corner.grade
      corner.entry = card.entry_speed_kmh ?? card.avg_entry_kmh ?? corner.entry
      corner.apex  = card.apex_speed_kmh  ?? card.min_speed_kmh ?? corner.apex
      corner.exit  = card.exit_speed_kmh  ?? card.avg_exit_kmh  ?? corner.exit
      corner.brake = card.peak_brake_bar  ?? corner.brake
      corner.glat  = card.peak_g_lat ?? card.max_lateral_g ?? corner.glat
      corner.time  = card.time_s ?? corner.time
      corner.delta = card.delta_s != null
        ? `${card.delta_s >= 0 ? '+' : ''}${card.delta_s.toFixed(1)}`
        : corner.delta
      corner.class = card.grade?.startsWith('A') ? 'high'
                   : card.grade?.startsWith('F') ? 'low'
                   : 'med'
    })
  } catch (e: any) {
    feedErrors.value.scorecard = e?.message ?? String(e)
  }
}

interface ThrottleBoxRow {
  name: string
  n_passes: number
  n_samples: number
  min_pct: number | null
  q1_pct: number | null
  median_pct: number | null
  q3_pct: number | null
  max_pct: number | null
  mean_pct: number | null
}

async function fetchThrottleBox(sid: string) {
  try {
    const res = await bridge.get<{ corners: ThrottleBoxRow[] }>(
      `/session/${sid}/throttle_corner_box`,
    )
    const rows = Array.isArray(res?.corners) ? res.corners : []
    const byName = new Map<string, ThrottleBoxRow>()
    for (const r of rows) byName.set(r.name, r)
    corners.value.forEach((corner) => {
      const row = byName.get(corner.name)
                ?? byName.get(`Turn ${corner.id.replace('T', '')}`)
                ?? byName.get(corner.id)
      if (!row || row.min_pct == null || row.max_pct == null) return
      corner.throttle = {
        min: row.min_pct,
        q1:  row.q1_pct ?? row.min_pct,
        med: row.median_pct ?? row.min_pct,
        q3:  row.q3_pct ?? row.max_pct,
        max: row.max_pct,
      }
    })
  } catch (e: any) {
    feedErrors.value.throttle = e?.message ?? String(e)
  }
}

interface BrakeRow {
  corner: string
  max_decel_g: number
  duration_s: number
  n_passes: number
}

async function fetchBrakeAccel(sid: string) {
  try {
    const res = await bridge.get<{ brake_zones: BrakeRow[] }>(
      `/session/${sid}/brake_acceleration`,
    )
    const rows = Array.isArray(res?.brake_zones) ? res.brake_zones : []
    const byName = new Map<string, BrakeRow>()
    for (const r of rows) byName.set(r.corner, r)
    corners.value.forEach((corner) => {
      const row = byName.get(corner.name)
                ?? byName.get(`Turn ${corner.id.replace('T', '')}`)
                ?? byName.get(corner.id)
      if (!row) return
      corner.peakDecelG = row.max_decel_g          // negative (deceleration)
      corner.brakeDurationS = row.duration_s
    })
  } catch (e: any) {
    feedErrors.value.brake = e?.message ?? String(e)
  }
}

onMounted(async () => {
  try {
    if (session.sessions.length === 0) await session.fetchSessions()
  } catch (e: any) {
    pageError.value = `Failed to load session list: ${e?.message ?? String(e)}`
  }
  const sid = activeSessionId.value
  if (sid) {
    sessionUsed.value = sid
    await Promise.all([
      fetchScorecard(sid),
      fetchThrottleBox(sid),
      fetchBrakeAccel(sid),
    ])
    // Promote per-feed errors into a single page-level error message when
    // every feed failed (bridge offline). One failure leaves the page
    // partially populated and falls back to "—" in the cells.
    const errs = Object.values(feedErrors.value).filter(Boolean)
    if (errs.length === 3) {
      pageError.value = `All corner data feeds failed — ${errs[0]}`
    }
  }
  resolvePinPositions()
})

/** Race-tolerant SVG turn-id projection (same pattern as TrackAtlas / TrackWalk). */
async function resolvePinPositions() {
  await nextTick()
  let tries = 5
  const tryOnce = () => {
    const r = trackMapRef.value
    if (!r || !r.trackTurns || !r.getPointAtProgress) {
      if (--tries > 0) requestAnimationFrame(tryOnce)
      return
    }
    corners.value.forEach((c) => {
      const pt = r.getPointAtProgress(c.progress)
      let closest: any = null
      let minDist = Infinity
      r.trackTurns.forEach((t: any) => {
        const dist = Math.hypot(t.cx - pt.x, t.cy - pt.y)
        if (dist < minDist) { minDist = dist; closest = t }
      })
      if (closest) c.svgTurnId = closest.id
    })
  }
  tryOnce()
}

const getGradeColor = (g: string) => {
  if (g.startsWith('A')) return 'text-ui-good font-bold drop-shadow-[1px_1px_0_#000]'
  if (g.startsWith('B') || g.startsWith('C') || g.startsWith('D')) return 'text-silver'
  if (g.startsWith('F')) return 'text-ui-warn font-bold drop-shadow-[1px_1px_0_#000]'
  return 'text-silver'
}

useKeyboard((e: KeyboardEvent) => {
  if (e.key === 'ArrowRight') {
    cursorIndex.value = Math.min(cursorIndex.value + 1, corners.value.length - 1)
    const g = corners.value[cursorIndex.value].grade
    audio.playSfx(g.startsWith('A') ? 'goal_complete' : g === 'F' ? 'error_quiet' : 'cursor_move')
  } else if (e.key === 'ArrowLeft') {
    cursorIndex.value = Math.max(cursorIndex.value - 1, 0)
    const g = corners.value[cursorIndex.value].grade
    audio.playSfx(g.startsWith('A') ? 'goal_complete' : g === 'F' ? 'error_quiet' : 'cursor_move')
  } else if (e.key === 'Enter' || e.key === 'a') {
    audio.playSfx('cursor_select')
  } else if (e.key === 'Escape' || e.key === 'Backspace' || e.key === 'b') {
    audio.playSfx('cancel')
    router.push('/garage/analysis')
  }
})

/** Brake consistency series for the PixelChart — peak |decel| per corner,
 *  in tenths of a G (so the chart's 0–100 range maps to 0–10 G). When the
 *  /brake_acceleration data isn't loaded yet, returns an empty array (chart
 *  renders flat). */
const brakeSeries = computed(() =>
  corners.value
    .map(c => c.peakDecelG != null ? Math.abs(c.peakDecelG) * 10 : 0)
    .filter(v => v > 0),
)

const cornerTimeDisplay = computed(() =>
  cur.value.time != null ? formatLapTime(cur.value.time, 2).replace(/^0:/, '') : '—',
)
</script>

<template>
  <PageShell title="CORNER MASTERY" :hints="['A · DRILL DOWN', '◀ ▶ MOVE', 'B · BACK']" bg="cool">
    <template #heading>
      <div class="heading-block mb-[1vh] text-center">
        <h1 class="text-title font-title text-silver tracking-[0.2em]">CORNER MASTERY</h1>
        <div v-if="sessionUsed" class="text-small text-ui-info">
          showing best per corner from <span class="font-mono">{{ sessionUsed }}</span>
        </div>
        <div v-else class="text-small text-ui-warn">
          no session data — corners only
        </div>
      </div>
    </template>

    <div v-if="pageError" class="mx-2 mb-2 p-3 border border-ui-bad/40 bg-ui-bad/5 text-small text-ui-bad tracking-wider uppercase">
      <div class="font-bold mb-1">CORNER DATA UNAVAILABLE</div>
      <div class="text-ui-bad/80 normal-case tracking-normal">{{ pageError }}</div>
    </div>

    <div class="grid grid-cols-[1.2fr_1fr] gap-[2vw] flex-grow min-h-0">

      <!-- Left: Map & Drill -->
      <div class="flex flex-col gap-[2vh]">
        <!-- Interactive Track Minimap -->
        <Frame variant="inset" padding="0" class="h-[35vh] flex items-center justify-center bg-[#1A252C] overflow-hidden relative border-slate/30">
          <TrackMap
            ref="trackMapRef"
            class="absolute inset-[-10%] w-[120%] h-[120%] opacity-80"
            :activeTurnId="cur.svgTurnId"
            @turn-click="(id: number) => {
              const idx = corners.findIndex(c => c.svgTurnId === id)
              if (idx !== -1) { cursorIndex = idx; audio.playSfx('cursor_select') }
            }"
          />
          <div class="absolute top-2 left-2 text-small text-slate font-bold z-10 tracking-widest uppercase">
            Track Navigation
          </div>
        </Frame>

        <!-- Drill Panel -->
        <Frame
          variant="default"
          padding="16px"
          class="relative transition-colors duration-300 flex-grow"
          :class="cur.grade.startsWith('A') ? 'bg-ui-good/5 border-ui-good/50'
                : cur.grade === 'F'         ? 'bg-ui-bad/5 border-ui-bad/50'
                : 'bg-ink/40'"
        >
          <div class="flex justify-between items-end mb-4 border-b border-slate/30 pb-2">
            <span class="font-bold text-title-sm">
              <span class="text-ui-info mr-2">▶</span>{{ cur.id }} {{ cur.name.toUpperCase() }}
            </span>
            <span class="text-[clamp(32px,8vmin,56px)] leading-none font-bold" :class="getGradeColor(cur.grade)">
              {{ cur.grade }}
            </span>
          </div>

          <div class="grid grid-cols-2 gap-x-8 gap-y-2 text-small tracking-wider">
            <div class="flex justify-between border-b border-slate/10 pb-1">
              <span>ENTRY</span>
              <span class="font-bold text-white">{{ cur.entry != null ? `${cur.entry.toFixed(1)} km/h` : '—' }}</span>
            </div>
            <div class="flex justify-between border-b border-slate/10 pb-1">
              <span>PEAK BRAKE</span>
              <span class="font-bold text-white">{{ cur.brake != null ? `${cur.brake.toFixed(1)} bar` : '—' }}</span>
            </div>
            <div class="flex justify-between border-b border-slate/10 pb-1">
              <span>APEX</span>
              <span class="font-bold text-white">{{ cur.apex != null ? `${cur.apex.toFixed(1)} km/h` : '—' }}</span>
            </div>
            <div class="flex justify-between border-b border-slate/10 pb-1">
              <span>MAX gLAT</span>
              <span class="font-bold text-white">{{ cur.glat != null ? cur.glat.toFixed(2) : '—' }}</span>
            </div>
            <div class="flex justify-between border-b border-slate/10 pb-1">
              <span>EXIT</span>
              <span class="font-bold text-white">{{ cur.exit != null ? `${cur.exit.toFixed(1)} km/h` : '—' }}</span>
            </div>
            <div class="flex justify-between border-b border-slate/10 pb-1">
              <span>TIME</span>
              <span class="font-bold text-white">{{ cornerTimeDisplay }}</span>
            </div>
            <!-- New: real per-corner brake metrics from /brake_acceleration -->
            <div class="flex justify-between border-b border-slate/10 pb-1">
              <span>PEAK DECEL</span>
              <span class="font-bold text-white">
                {{ cur.peakDecelG != null ? `${Math.abs(cur.peakDecelG).toFixed(2)} G` : '—' }}
              </span>
            </div>
            <div class="flex justify-between border-b border-slate/10 pb-1">
              <span>BRAKE TIME</span>
              <span class="font-bold text-white">
                {{ cur.brakeDurationS != null ? `${cur.brakeDurationS.toFixed(2)} s` : '—' }}
              </span>
            </div>
          </div>

          <div class="absolute bottom-4 right-4 text-small font-bold uppercase tracking-widest">
            Delta
            <span :class="cur.delta.startsWith('-') ? 'text-ui-good' : cur.delta === '--' ? 'text-slate' : 'text-ui-bad'">
              {{ cur.delta }}{{ cur.delta !== '--' ? 's' : '' }}
            </span>
          </div>
        </Frame>
      </div>

      <!-- Right: Charts & Analysis -->
      <div class="flex flex-col gap-[2vh]">
        <!-- Throttle box-plot — real /throttle_corner_box data -->
        <Frame variant="default" padding="16px" class="h-[50%] flex flex-col overflow-hidden bg-ink/40">
          <div class="text-small text-slate tracking-widest uppercase mb-4 border-b border-slate/30 pb-1">
            Throttle Profile <span class="text-[10px] normal-case text-slate/60 ml-2">box: q1–q3 · whisker: min/max · bar: median</span>
          </div>
          <div class="flex flex-col gap-2 overflow-y-auto no-scrollbar flex-grow pr-2">
            <div
              v-for="c in corners"
              :key="c.id"
              class="flex items-center gap-4 transition-all py-1 px-2 rounded cursor-pointer"
              :class="cur.id === c.id ? 'bg-slate/20' : 'opacity-60'"
              @click="() => { const idx = corners.findIndex(x => x.id === c.id); if (idx !== -1) { cursorIndex = idx; audio.playSfx('cursor_select') } }"
            >
              <span class="w-8 text-small font-black text-center" :class="cur.id === c.id ? 'text-white' : 'text-slate'">{{ c.id }}</span>
              <div class="flex-grow h-3 relative border-b border-slate/30">
                <template v-if="c.throttle">
                  <div class="absolute w-[1px] h-full bg-slate/50" :style="{ left: c.throttle.min + '%' }"></div>
                  <div class="absolute w-[1px] h-full bg-slate/50" :style="{ left: c.throttle.max + '%' }"></div>
                  <div class="absolute h-[1px] bg-slate/30 top-1/2" :style="{ left: c.throttle.min + '%', width: (c.throttle.max - c.throttle.min) + '%' }"></div>
                  <div class="absolute h-full bg-charcoal-mid border border-slate/40" :style="{ left: c.throttle.q1 + '%', width: (c.throttle.q3 - c.throttle.q1) + '%' }"></div>
                  <div class="absolute w-1 h-full bg-ui-warn" :style="{ left: c.throttle.med + '%' }"></div>
                </template>
                <span v-else class="absolute inset-0 flex items-center text-[10px] text-slate/40 italic pl-2">no data</span>
              </div>
            </div>
          </div>
        </Frame>

        <!-- Brake Consistency — real per-corner peak decel from /brake_acceleration -->
        <Frame variant="default" padding="16px" class="flex-grow flex flex-col bg-ink/40">
          <div class="flex justify-between items-baseline border-b border-slate/30 pb-1 mb-2">
            <div class="text-small text-slate tracking-widest uppercase">Brake Consistency</div>
            <div v-if="brakeSeries.length" class="text-small text-silver">
              peak avg
              <span class="text-white font-bold">
                {{ (brakeSeries.reduce((a, b) => a + b, 0) / brakeSeries.length / 10).toFixed(2) }} G
              </span>
              · across {{ brakeSeries.length }} corners
            </div>
            <div v-else class="text-small text-slate italic">no brake-zone data</div>
          </div>
          <div class="flex-grow flex items-center justify-center min-h-[80px]">
            <PixelChart
              v-if="brakeSeries.length"
              :data="brakeSeries"
              color="var(--color-ui-bad)"
              :height="80"
              :width="300"
              :stroke-width="3"
            />
            <span v-else class="text-small text-slate italic">drive a session with heavy braking</span>
          </div>
          <div class="mt-2 text-small text-center italic text-slate/80">
            "Roll the brake to the apex, don't square-wave it."
          </div>
        </Frame>
      </div>

    </div>
  </PageShell>
</template>

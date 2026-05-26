<script setup lang="ts">
/**
 * Track Walk — interactive Sonoma map with per-corner detail.
 *
 * Pre-2026-05-13 this screen rendered a hardcoded `corners` array with
 * SYNTHETIC `deltas: {entry: +2, apex: +1, exit: 0, time: -0.1}` that
 * had no relationship to real telemetry. The deltas were fully invented.
 *
 * Now:
 *   • Corner positions (`progress` %) and curated coach `tip` strings are
 *     hardcoded — they're static track lore, not telemetry. (Same
 *     justification as TrackAtlas's `pointsOfInterest`.)
 *   • Grades, best entry/apex/exit speeds, corner-time, and the apex-vs-
 *     gold delta are loaded from `/session/<sid>/corners` (bp_track.session_corners).
 *   • Entry/exit/time deltas are honest `null` because the bridge only
 *     exposes a gold delta for *apex* today. CornerScorecard renders "—"
 *     for null deltas instead of fake arrows.
 *   • SVG turn-id resolution uses `nextTick` + bounded `requestAnimationFrame`
 *     instead of `setTimeout(100)` (the same race-tolerant pattern we
 *     applied to TrackAtlas).
 *   • Empty state when no session has data: pin colours all neutral,
 *     deltas all "—", coach speaks an honest "no data yet" line.
 */
import { computed, nextTick, onMounted, ref } from 'vue'
import { useKeyboard } from '@/shared/lib/useKeyboard'
import { useRouter } from 'vue-router'
import { useSaveStore } from '@/entities/save/model/saveStore'
import { useAudioStore } from '@/features/audio-playback/model/audioStore'
import { useSessionStore } from '@/entities/session/model/sessionStore'
import { useNotificationsStore } from '@/shared/api/notificationStore'
import { bridge } from '@/shared/api/bridge'
import PageShell from '@/shared/ui/PageShell.vue'
import CoachFloat from '@/shared/ui/CoachFloat.vue'
import TrackMap from '@/shared/ui/core/TrackMap.vue'
import CornerScorecard from '@/shared/ui/core/CornerScorecard.vue'
import { buildTrackWalkCornerPins, buildTurnIdToCornerIndex, pickTrackWalkSessionId } from './trackWalkModel'

const router = useRouter()
const save = useSaveStore()
const audio = useAudioStore()
const sessionStore = useSessionStore()
const notifications = useNotificationsStore()

interface CornerView {
  id: string
  /** 0–100 along the lap; used to position the pin on TrackMap. */
  progress: number
  /** Display name (matches `/session/<sid>/corners` `name` field). */
  name: string
  /** Coach narrative — static curated lore from sonoma.json + T-Rod. */
  tip: string
  /** "A"–"F" / "ungraded" / "--" when no session data yet. */
  grade: string
  entry: number | null
  apex: number | null
  exit: number | null
  time: number | null
  statsSource: 'session' | 'none'
  /**
   * Honest deltas: only `apex` populated when the bridge returns
   * `gold_delta_kmh`. The other three stay null until the bridge
   * exposes per-leg gold data.
   */
  deltas: { entry: number | null; apex: number | null; exit: number | null; time: number | null }
  svgTurnId?: number
}

// Static layout + lore — always rendered, even with no session data.
// `name` MUST match the bridge's corner-name format ("Turn 1" / "T1" /
// "The Carousel") for the merge in onMounted to fire. The bridge derives
// these names from `data/tracks/sonoma.json:corners[].name` — so the
// canonical form here is "Turn N" (the sonoma JSON convention), and
// "The Carousel" for T6.
const STATIC_CORNERS: CornerView[] = [
  { id: 'T1',  progress:  8, name: 'Turn 1',       tip: 'Keep it pinned, eyes up the hill.',                                grade: '--', entry: null, apex: null, exit: null, time: null, statsSource: 'none', deltas: { entry: null, apex: null, exit: null, time: null } },
  { id: 'T2',  progress: 14, name: 'Turn 2',       tip: 'Brake at the bridge, late apex — rolls off camber on exit.',      grade: '--', entry: null, apex: null, exit: null, time: null, statsSource: 'none', deltas: { entry: null, apex: null, exit: null, time: null } },
  { id: 'T3',  progress: 18, name: 'Turn 3',       tip: 'Crest the hill, do not lift. T3 is a give-away — sacrifice for T3a/T4.', grade: '--', entry: null, apex: null, exit: null, time: null, statsSource: 'none', deltas: { entry: null, apex: null, exit: null, time: null } },
  { id: 'T4',  progress: 24, name: 'Turn 4',       tip: 'Downhill braking — rear gets light. Trail brake gently.',         grade: '--', entry: null, apex: null, exit: null, time: null, statsSource: 'none', deltas: { entry: null, apex: null, exit: null, time: null } },
  { id: 'T5',  progress: 30, name: 'Turn 5',       tip: 'Throwaway corner — preserve T6 entry, do not rush the throttle.', grade: '--', entry: null, apex: null, exit: null, time: null, statsSource: 'none', deltas: { entry: null, apex: null, exit: null, time: null } },
  { id: 'T6',  progress: 45, name: 'The Carousel', tip: 'Long constant radius. Distance is king — cut the inside, do not open up.', grade: '--', entry: null, apex: null, exit: null, time: null, statsSource: 'none', deltas: { entry: null, apex: null, exit: null, time: null } },
  { id: 'T7',  progress: 55, name: 'Turn 7',       tip: 'Single apex, treat as double — cut entry, rotate, hit second apex.', grade: '--', entry: null, apex: null, exit: null, time: null, statsSource: 'none', deltas: { entry: null, apex: null, exit: null, time: null } },
  { id: 'T8',  progress: 65, name: 'Turn 8',       tip: 'Esses begin. Rhythm is everything — link the inputs.',            grade: '--', entry: null, apex: null, exit: null, time: null, statsSource: 'none', deltas: { entry: null, apex: null, exit: null, time: null } },
  { id: 'T9',  progress: 70, name: 'Turn 9',       tip: 'Open up nine — straight shot to ten.',                            grade: '--', entry: null, apex: null, exit: null, time: null, statsSource: 'none', deltas: { entry: null, apex: null, exit: null, time: null } },
  { id: 'T10', progress: 80, name: 'Turn 10',      tip: 'Fastest corner. Most drivers brake when they only need a lift.',  grade: '--', entry: null, apex: null, exit: null, time: null, statsSource: 'none', deltas: { entry: null, apex: null, exit: null, time: null } },
  { id: 'T11', progress: 90, name: 'Turn 11',      tip: 'No painted brake board — the bump is the reference. Wait for the car to settle.', grade: '--', entry: null, apex: null, exit: null, time: null, statsSource: 'none', deltas: { entry: null, apex: null, exit: null, time: null } },
]

const corners = ref<CornerView[]>(STATIC_CORNERS.map(c => ({ ...c, deltas: { ...c.deltas } })))
const trackMapRef = ref<any>(null)
const cursorIndex = ref(0)
const state = ref<'idle' | 'corner-detail' | 'no-data' | 'marker-detail'>('idle')
const sessionUsed = ref<string | null>(null)

// Explicit error UI for bridge fetches. Pre-2026-05-24 the three /track/*
// + /session/<sid>/corners catches silently fell through to state='no-data',
// which conflated "session has no laps yet" with "bridge is offline".
// `pageError` surfaces the underlying bridge error in a "TRACK DATA
// UNAVAILABLE" panel (PreBrief.vue pattern) so the user can distinguish.
const pageError = ref<string | null>(null)

const selectedCorner = computed(() => corners.value[cursorIndex.value])
const hasSessionMetrics = computed(() => corners.value.some((corner) => corner.statsSource === 'session'))

// ── Phase 1: Marker pins layer ─────────────────────────────────────────────

interface MarkerRow {
  id: string
  label: string
  /** Free-form kind, e.g. apex_ref / brake_ref / visual / reference. */
  kind: string
  corner: string | null
  distance: number | null
  at_offset_m_from_entry?: number | null
  lat?: number
  lon?: number
  note?: string
  source?: string
}

const markers = ref<MarkerRow[]>([])
const TRACK_LENGTH_M = 4258  // sonoma; matches bridge sonoma.TRACK_LENGTH_M

interface MarkerPin extends MarkerRow {
  x: number
  y: number
}
const markerPins = ref<MarkerPin[]>([])
const selectedMarker = ref<MarkerPin | null>(null)
const cornerPins = ref<Array<{ id: string; x: number; y: number }>>([])
const turnIdToCornerIndex = ref<Record<number, number>>({})

const KIND_COLOR: Record<string, string> = {
  brake_ref: 'fill-ui-warn',    // amber — slow-down landmark
  apex_ref:  'fill-ui-good',    // green — turn-in / apex landmark
  turn_in_ref: 'fill-ui-info',  // cyan — initial steering reference
  reference: 'fill-ui-info',    // blue  — generic reference
  visual:    'fill-silver',     // grey  — visual-only landmark
}

function markerKindLabel(kind: string): string {
  return kind.replaceAll('_', ' ')
}

function markerKindSummary(kind: string): string {
  if (kind === 'brake_ref') return 'Brake reference'
  if (kind === 'apex_ref') return 'Apex reference'
  if (kind === 'turn_in_ref') return 'Turn-in reference'
  if (kind === 'visual') return 'Visual reference'
  return 'Track reference'
}

function markerKindDescription(kind: string): string {
  if (kind === 'brake_ref') {
    return 'Use this landmark to anchor the braking point before turn-in.'
  }
  if (kind === 'apex_ref') {
    return 'Use this landmark to lock your eyes on the apex and repeat the line.'
  }
  if (kind === 'turn_in_ref') {
    return 'Use this landmark as the cue to begin steering input into the corner.'
  }
  if (kind === 'visual') {
    return 'Use this landmark to stay oriented and keep your vision farther ahead.'
  }
  return 'Reference point surfaced from the backend track guide.'
}

function markerOffsetLabel(offset: number | null | undefined): string | null {
  if (offset == null) return null
  if (offset === 0) return 'at corner entry'
  if (offset > 0) return `+${offset.toFixed(0)} m after entry`
  return `${offset.toFixed(0)} m before entry`
}

// ── Phase 3: Layers menu ───────────────────────────────────────────────────

// Layer prefs persist across reloads via localStorage (single key, shared
// across all save slots — these are a workflow preference, not save state).
// Falls back to sensible defaults if the stored value is malformed.
const LAYER_PREFS_KEY = 'pitwall.trackwalk.layers.v1'

interface LayerPrefs {
  corners: boolean   // always rendered by TrackMap itself; kept for forward-compat
  markers: boolean
  dangerZones: boolean
  hustle: boolean    // per-50m commit-rate (>= 95% throttle) overlay
}

function loadLayerPrefs(): LayerPrefs {
  const fallback: LayerPrefs = { corners: true, markers: true, dangerZones: false, hustle: false }
  try {
    const raw = localStorage.getItem(LAYER_PREFS_KEY)
    if (!raw) return fallback
    const parsed = JSON.parse(raw)
    return {
      corners:     typeof parsed.corners     === 'boolean' ? parsed.corners     : fallback.corners,
      markers:     typeof parsed.markers     === 'boolean' ? parsed.markers     : fallback.markers,
      dangerZones: typeof parsed.dangerZones === 'boolean' ? parsed.dangerZones : fallback.dangerZones,
      hustle:      typeof parsed.hustle      === 'boolean' ? parsed.hustle      : fallback.hustle,
    }
  } catch {
    return fallback
  }
}

const layers = ref<LayerPrefs>(loadLayerPrefs())

interface DangerZone {
  id: string
  start_m: number
  end_m: number
  description: string
  severity: 'high' | 'medium' | 'low' | string
}
const dangerZones = ref<DangerZone[]>([])

interface DangerArc { id: string; start: { x: number; y: number }; end: { x: number; y: number }; severity: string; description: string }
const dangerArcs = ref<DangerArc[]>([])

// Hustle map — per-50m segment, % frames at >= 95% throttle. Painted on
// the track to visualise where the driver actually committed. Sourced from
// /session/<sid>/hustle_map (analytics.hustle_map). Loaded lazily on first
// toggle; null while the layer hasn't been turned on yet (no point hitting
// the bridge for data the user hasn't asked for).
interface HustleSegment { start_m: number; end_m: number; hustle_pct: number }
interface HustleArc { start: { x: number; y: number }; end: { x: number; y: number }; pct: number }
const hustleSegments = ref<HustleSegment[]>([])
const hustleArcs = ref<HustleArc[]>([])
const hustleLoaded = ref(false)

function toggleLayer(key: keyof LayerPrefs) {
  layers.value[key] = !layers.value[key]
  audio.playSfx('cursor_select')
  try {
    localStorage.setItem(LAYER_PREFS_KEY, JSON.stringify(layers.value))
  } catch { /* storage quota / private mode — silently keep in-memory state */ }
  // Lazy-load layers that need a bridge fetch.
  if (key === 'hustle' && layers.value.hustle && !hustleLoaded.value) {
    loadHustle()
  }
}

async function loadHustle() {
  const sid = sessionUsed.value
  if (!sid) return
  try {
    const res = await bridge.get<{ hustle_map: HustleSegment[] }>(`/session/${sid}/hustle_map`)
    hustleSegments.value = Array.isArray(res?.hustle_map) ? res.hustle_map : []
    projectHustleArcs()
  } catch {
    hustleSegments.value = []
  } finally {
    hustleLoaded.value = true
  }
}

function projectHustleArcs() {
  const r = trackMapRef.value
  if (!r || !r.getPointAtProgress || !hustleSegments.value.length) {
    hustleArcs.value = []
    return
  }
  hustleArcs.value = hustleSegments.value.map(s => ({
    start: r.getPointAtProgress((s.start_m / TRACK_LENGTH_M) * 100),
    end:   r.getPointAtProgress((s.end_m   / TRACK_LENGTH_M) * 100),
    pct:   s.hustle_pct,
  }))
}

/** Map hustle % → tailwind stroke class. >=80% green, 50-80% amber,
 *  <50% red. Empty segments (count=0 from the bridge) render as 0%. */
function hustleColor(pct: number): string {
  if (pct >= 80) return 'stroke-ui-good'
  if (pct >= 50) return 'stroke-amber'
  if (pct > 0)   return 'stroke-ui-bad'
  return 'stroke-slate'
}

interface BridgeCornerRow {
  name: string
  n_passes: number
  grade: string                                  // "A".."F" | "ungraded"
  gold_delta_kmh:       number | null            // apex speed vs gold
  gold_delta_entry_kmh: number | null            // entry speed vs gold
  gold_delta_exit_kmh:  number | null            // exit speed vs gold
  gold_delta_time_s:    number | null            // corner time vs gold (positive = slower)
  best_pass: {
    entry_speed_kmh: number
    apex_speed_kmh: number
    exit_speed_kmh: number
    corner_time_s: number
    peak_brake_bar: number
  } | null
  averages: { apex_speed_kmh: number; corner_time_s: number } | null
}

onMounted(async () => {
  if (sessionStore.sessions.length === 0) {
    await sessionStore.fetchSessions()
  }

  // Pick the most recent session that actually has laps. Falls back to the
  // active session if it's the only one. No magic 'demo-session' fallback.
  const sid = pickTrackWalkSessionId(sessionStore.activeSessionId, sessionStore.sessions)

  if (sid) {
    sessionUsed.value = sid
    try {
      const res = await bridge.get<{ corners: BridgeCornerRow[]; lap_count: number }>(
        `/session/${sid}/corners`,
      )
      const rows = Array.isArray(res?.corners) ? res.corners : []
      const byName = new Map<string, BridgeCornerRow>()
      for (const r of rows) byName.set(r.name, r)

      let merged = 0
      for (const c of corners.value) {
        // Match by display name first, fall back to "T<n>" / "Turn <n>" variants.
        const r = byName.get(c.name)
              ?? byName.get(c.id)
              ?? byName.get(c.id.replace('T', 'Turn '))
        if (!r) continue
        merged++
        c.grade = r.grade && r.grade !== 'ungraded' ? r.grade : '--'
        if (r.best_pass) {
          c.entry = r.best_pass.entry_speed_kmh
          c.apex  = r.best_pass.apex_speed_kmh
          c.exit  = r.best_pass.exit_speed_kmh
          c.time  = r.best_pass.corner_time_s
          c.statsSource = 'session'
        }
        // Per-leg gold deltas now all real — bridge populates entry / apex /
        // exit / time from sonoma_gold.json. Nulls only when the gold record
        // is missing the field (won't happen for the 11 Sonoma corners).
        c.deltas.entry = r.gold_delta_entry_kmh
        c.deltas.apex  = r.gold_delta_kmh
        c.deltas.exit  = r.gold_delta_exit_kmh
        c.deltas.time  = r.gold_delta_time_s
      }
      if (merged === 0 && rows.length === 0) {
        state.value = 'no-data'
      }
    } catch (e: any) {
      // Bridge offline / session not analysed — surface the real error so the
      // user knows whether it's a missing endpoint or a true no-data condition.
      pageError.value = `Corners feed failed: ${e?.message ?? String(e)}`
      state.value = 'no-data'
    }
  } else {
    state.value = 'no-data'
  }

  // Phase 1: load markers (named landmarks like "the bridge", "the K-wall bend")
  try {
    const mres = await bridge.get<{ markers: MarkerRow[] }>('/track/markers')
    markers.value = Array.isArray(mres?.markers) ? mres.markers : []
  } catch (e: any) {
    // Markers are optional; only surface the error if no other feed already did.
    if (!pageError.value) {
      pageError.value = `Markers feed failed: ${e?.message ?? String(e)}`
    }
  }

  // Phase 3: load danger zones (off by default; user can toggle)
  try {
    const dres = await bridge.get<{ danger_zones: DangerZone[] }>('/track/danger_zones')
    dangerZones.value = Array.isArray(dres?.danger_zones) ? dres.danger_zones : []
  } catch (e: any) {
    if (!pageError.value) {
      pageError.value = `Danger zones feed failed: ${e?.message ?? String(e)}`
    }
  }

  resolvePinPositions()
})

/** Resolve interactive overlays once the SVG is mounted. */
async function resolvePinPositions() {
  await nextTick()
  let tries = 5
  const tryOnce = () => {
    const r = trackMapRef.value
    if (!r || !r.trackTurns || !r.getPointAtProgress) {
      if (--tries > 0) requestAnimationFrame(tryOnce)
      return
    }
    const resolvedCornerPins = buildTrackWalkCornerPins(corners.value, r.trackTurns)
    cornerPins.value = resolvedCornerPins.map(({ id, x, y }) => ({ id, x, y }))
    turnIdToCornerIndex.value = buildTurnIdToCornerIndex(corners.value)

    corners.value.forEach((corner, index) => {
      const pin = resolvedCornerPins[index]
      if (pin?.turnId != null) {
        corner.svgTurnId = pin.turnId
      }
    })

    // Phase 1: project each marker's `distance` along the track path to an
    // SVG (x, y). Markers without a distance are skipped (we don't have lat/
    // lon → SVG projection here; track-path-relative distance is the source).
    markerPins.value = markers.value
      .filter(m => m.distance != null)
      .map(m => {
        const progress = (m.distance! / TRACK_LENGTH_M) * 100
        const pt = r.getPointAtProgress(Math.max(0, Math.min(100, progress)))
        return { ...m, x: pt.x, y: pt.y }
      })

    // Phase 3: precompute danger-zone arc endpoints on the track path so we
    // can render coloured spans without the TrackMap component needing to
    // know about them.
    dangerArcs.value = dangerZones.value.map(z => ({
      id: z.id,
      start: r.getPointAtProgress((z.start_m / TRACK_LENGTH_M) * 100),
      end:   r.getPointAtProgress((z.end_m / TRACK_LENGTH_M) * 100),
      severity: z.severity,
      description: z.description,
    }))

    // If the hustle layer was already on from a previous session (persisted
    // in localStorage), kick off the lazy load now that the SVG is mounted.
    if (layers.value.hustle && !hustleLoaded.value) {
      loadHustle()
    } else if (hustleSegments.value.length) {
      projectHustleArcs()
    }
  }
  tryOnce()
}

function openCorner(index: number) {
  cursorIndex.value = index
  selectedMarker.value = null
  state.value = 'corner-detail'
  audio.playSfx('cursor_select')
}

function openCornerByTurnId(turnId: number) {
  const index = turnIdToCornerIndex.value[turnId]
  if (index == null || !corners.value[index]) return
  openCorner(index)
}

useKeyboard((e: KeyboardEvent) => {
  if (state.value === 'corner-detail') {
    if (e.key === 'Escape' || e.key === 'Backspace' || e.key === 'b') {
      audio.playSfx('cancel')
      state.value = 'idle'
    } else if (e.key === 'a' || e.key === 'Enter') {
      audio.playSfx('goal_complete')
      notifications.add({
        kind: 'track-unlock',
        title: `GOAL ADDED: ${selectedCorner.value.name}`,
        subText: 'Focus added to next session',
        timestamp: new Date().toISOString(),
      })
      state.value = 'idle'
    }
    return
  }

  if (state.value === 'marker-detail') {
    if (e.key === 'Escape' || e.key === 'Backspace' || e.key === 'b' || e.key === 'a' || e.key === 'Enter') {
      audio.playSfx('cancel')
      state.value = 'idle'
      selectedMarker.value = null
    }
    return
  }

  // Phase 3: layer toggles via keyboard. M = markers, D = danger zones, H = hustle.
  if (e.key === 'm' || e.key === 'M') { toggleLayer('markers'); return }
  if (e.key === 'd' || e.key === 'D') { toggleLayer('dangerZones'); return }
  if (e.key === 'h' || e.key === 'H') { toggleLayer('hustle'); return }

  if (e.key === 'ArrowRight') {
    cursorIndex.value = (cursorIndex.value + 1) % corners.value.length
    audio.playSfx('cursor_move')
  } else if (e.key === 'ArrowLeft') {
    cursorIndex.value = (cursorIndex.value - 1 + corners.value.length) % corners.value.length
    audio.playSfx('cursor_move')
  } else if (e.key === 'Enter' || e.key === 'a') {
    audio.playSfx('cursor_select')
    state.value = 'corner-detail'
  } else if (e.key === 'Escape' || e.key === 'Backspace' || e.key === 'b') {
    audio.playSfx('cancel')
    router.back()
  }
})

const idleCoachLine = computed(() => {
  if (state.value === 'no-data') {
    return `No completed backend lap has touched ${selectedCorner.value.name} yet — start and finish a real session and these corners come alive.`
  }
  if (!hasSessionMetrics.value) {
    return 'Tap any corner to walk through it. Grades and per-corner speeds populate after your first completed real session.'
  }
  return 'Tap any corner. Red grades mean you are losing time — those are tomorrow\'s focus.'
})
</script>

<template>
  <PageShell
    :title="`TRACK WALK · SONOMA${hasSessionMetrics ? '' : ' · NO DATA'}`"
    :hints="
      state === 'corner-detail'  ? ['A · ADD AS GOAL', 'B · BACK'] :
      state === 'marker-detail'  ? ['A / B · CLOSE'] :
      ['A · ENTER CORNER', 'M / D / H · LAYERS', '◀ ▶ NEXT', 'B · BACK']
    "
    bg="neutral"
  >
    <template #heading>
      <div class="heading-block mb-[clamp(4px,1vh,12px)] text-center px-2">
        <h1 class="font-title text-silver tracking-[0.2em] leading-tight break-words" :style="{ fontSize: 'clamp(16px, 3.4vmin, 28px)' }">
          TRACK WALK · SONOMA
        </h1>
        <div v-if="hasSessionMetrics" class="text-small text-ui-info break-words">
          showing best per corner from <span class="font-mono">{{ sessionUsed }}</span>
        </div>
        <div v-else class="text-small text-ui-warn break-words">
          no completed backend laps yet — corners and coach tips only
        </div>
      </div>
    </template>

    <!-- Layers toggle row (Phase 3) -->
    <div class="mx-2 mb-1 flex gap-[clamp(4px,1vmin,10px)] items-center text-small flex-wrap shrink-0">
      <span class="text-slate tracking-widest uppercase shrink-0">Layers:</span>
      <button
        type="button"
        class="px-3 border font-mono uppercase tracking-wider min-h-[36px] inline-flex items-center"
        :class="layers.markers
          ? 'border-ui-good text-ui-good bg-charcoal'
          : 'border-slate text-slate'"
        @click="toggleLayer('markers')"
        title="M · toggle named markers (the bridge, the K-wall bend, …)"
      >
        M · Markers
        <span class="text-[10px] ml-1 opacity-60">{{ markerPins.length }}</span>
      </button>
      <button
        type="button"
        class="px-3 border font-mono uppercase tracking-wider min-h-[36px] inline-flex items-center"
        :class="layers.dangerZones
          ? 'border-ui-bad text-ui-bad bg-charcoal'
          : 'border-slate text-slate'"
        @click="toggleLayer('dangerZones')"
        title="D · toggle danger zones (high-risk run-offs and downhills)"
      >
        D · Danger
        <span class="text-[10px] ml-1 opacity-60">{{ dangerArcs.length }}</span>
      </button>
      <button
        type="button"
        class="px-3 border font-mono uppercase tracking-wider min-h-[36px] inline-flex items-center disabled:opacity-40"
        :class="layers.hustle
          ? 'border-ui-good text-ui-good bg-charcoal'
          : 'border-slate text-slate'"
        @click="toggleLayer('hustle')"
        :disabled="!sessionUsed"
        :title="sessionUsed
          ? 'H · toggle hustle map (per-50 m commit rate at >= 95% throttle)'
          : 'No session — hustle map needs telemetry'"
      >
        H · Hustle
        <span v-if="hustleArcs.length" class="text-[10px] ml-1 opacity-60">{{ hustleArcs.length }}</span>
        <span v-else class="text-[10px] ml-1 opacity-40">—</span>
      </button>
      <span class="ml-auto text-slate text-[10px] italic hidden landscape:inline">
        Corner pins always on. M / D / H keys also toggle layers.
      </span>
    </div>

    <div v-if="pageError" class="mx-2 mb-1 p-2 border border-ui-bad/40 bg-ui-bad/5 text-small text-ui-bad tracking-wider uppercase shrink-0">
      <div class="font-bold mb-0.5">TRACK DATA UNAVAILABLE</div>
      <div class="text-ui-bad/80 normal-case tracking-normal break-words">{{ pageError }}</div>
    </div>

    <!-- Map area -->
    <div class="relative flex-1 min-h-0 mx-2 border border-slate bg-charcoal/20 overflow-hidden">
      <TrackMap
        ref="trackMapRef"
        class="text-slate/75"
        :activeTurnId="selectedCorner.svgTurnId"
        @turn-click="openCornerByTurnId"
      >
        <g>
          <circle
            v-for="(pin, index) in cornerPins"
            :key="`corner-hit-${pin.id}`"
            :cx="pin.x"
            :cy="pin.y"
            r="72"
            fill="transparent"
            pointer-events="all"
            class="cursor-pointer"
            role="button"
            tabindex="0"
            :aria-label="`Open ${corners[index]?.name ?? pin.id}`"
            @click="openCorner(index)"
          />
        </g>

        <!-- Hustle map: per-50 m commit-rate overlay. Rendered first so the
             danger zones + markers + turn pins layer cleanly on top. Color:
             green ≥ 80%, amber 50–80%, red 0–50%, slate when no data. -->
        <g v-if="layers.hustle" class="pointer-events-none">
          <line
            v-for="(seg, i) in hustleArcs"
            :key="`h-${i}`"
            :x1="seg.start.x" :y1="seg.start.y"
            :x2="seg.end.x"   :y2="seg.end.y"
            :class="hustleColor(seg.pct)"
            stroke-width="14"
            stroke-linecap="round"
            opacity="0.55"
          >
            <title>{{ seg.pct.toFixed(0) }}% commit · {{ Math.round(hustleSegments[i]?.start_m ?? 0) }}–{{ Math.round(hustleSegments[i]?.end_m ?? 0) }} m</title>
          </line>
        </g>

        <!-- Phase 3: danger-zone arc highlights — rendered BEHIND markers
             and turn pins (which TrackMap draws after the slot). Each zone
             is a chord between start_m and end_m projected onto the SVG. -->
        <g v-if="layers.dangerZones" class="pointer-events-none">
          <line
            v-for="z in dangerArcs"
            :key="`dz-${z.id}`"
            :x1="z.start.x" :y1="z.start.y"
            :x2="z.end.x"   :y2="z.end.y"
            :class="z.severity === 'high'   ? 'stroke-ui-bad'
                  : z.severity === 'medium' ? 'stroke-ui-warn'
                  : 'stroke-silver'"
            stroke-width="20"
            stroke-linecap="round"
            opacity="0.35"
          />
        </g>

        <!-- Phase 1: marker pins. Coloured by `kind`; clickable to surface
             the marker's name + lore. -->
        <g v-if="layers.markers">
          <g
            v-for="m in markerPins"
            :key="m.id"
            class="cursor-pointer transition-transform"
            :style="{ transform: selectedMarker?.id === m.id ? 'scale(1.6)' : 'scale(1)',
                      transformOrigin: 'center', transformBox: 'fill-box' }"
            @click="selectedMarker = m; state = 'marker-detail'; audio.playSfx('cursor_select')"
            role="button"
            :aria-label="`Marker ${m.label}`"
          >
            <circle
              :cx="m.x" :cy="m.y" r="18"
              :class="KIND_COLOR[m.kind] || 'fill-silver'"
              stroke="#0f172a"
              stroke-width="4"
            />
            <circle :cx="m.x" :cy="m.y" r="6" class="fill-ink" />
          </g>
        </g>
      </TrackMap>
    </div>

    <!-- Corner detail modal -->
    <Transition name="fade">
      <div v-if="state === 'corner-detail'" class="absolute inset-0 bg-ink/80 z-20 backdrop-blur-sm" @click="state = 'idle'"></div>
    </Transition>
    <Transition name="slide-up">
      <CornerScorecard
        v-if="state === 'corner-detail'"
        :corner="selectedCorner"
        :coach-id="save.activeSlot?.preferredCoach ?? 'TROD'"
      />
    </Transition>

    <!-- Marker detail card (Phase 1) — small bottom panel with the lore -->
    <Transition name="fade">
      <div v-if="state === 'marker-detail' && selectedMarker"
           class="absolute inset-0 bg-ink/70 z-20 backdrop-blur-sm"
           @click="state = 'idle'; selectedMarker = null">
      </div>
    </Transition>
    <Transition name="slide-up">
      <div
        v-if="state === 'marker-detail' && selectedMarker"
        class="absolute left-2 right-2 bottom-[6vh] z-30 p-3 border bg-ink/95 backdrop-blur-sm pointer-events-auto"
        :class="selectedMarker.kind === 'brake_ref' ? 'border-ui-warn'
              : selectedMarker.kind === 'apex_ref'  ? 'border-ui-good'
              : 'border-slate'"
      >
        <div class="flex justify-between items-baseline border-b border-slate pb-1 mb-2">
          <span class="text-white font-bold text-[clamp(13px,2.8vw,20px)]">
            "{{ selectedMarker.label }}"
          </span>
          <span class="text-small text-slate tracking-widest uppercase">
            {{ markerKindLabel(selectedMarker.kind) }}
            <span v-if="selectedMarker.corner" class="text-ui-info ml-2">· {{ selectedMarker.corner }}</span>
          </span>
        </div>
        <div class="text-body text-silver">
          <div class="text-ui-info font-bold tracking-wider uppercase mb-2">
            {{ markerKindSummary(selectedMarker.kind) }}
          </div>
          <div class="mb-2">
            {{ markerKindDescription(selectedMarker.kind) }}
          </div>
          <div v-if="selectedMarker.note" class="mb-2 border border-slate/40 bg-charcoal/50 px-2 py-1 text-ui-warn italic">
            {{ selectedMarker.note }}
          </div>
          <div class="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-small">
            <span class="text-slate uppercase tracking-wider">Corner</span>
            <span>{{ selectedMarker.corner ?? '—' }}</span>
            <span class="text-slate uppercase tracking-wider">Distance</span>
            <span>{{ selectedMarker.distance != null ? `${selectedMarker.distance.toFixed(0)} m` : '—' }}</span>
            <span class="text-slate uppercase tracking-wider">Offset</span>
            <span>{{ markerOffsetLabel(selectedMarker.at_offset_m_from_entry) ?? '—' }}</span>
            <span class="text-slate uppercase tracking-wider">Source</span>
            <span>{{ selectedMarker.source ? selectedMarker.source.toUpperCase() : '—' }}</span>
            <span class="text-slate uppercase tracking-wider">GPS</span>
            <span>
              {{ selectedMarker.lat != null && selectedMarker.lon != null
                ? `${selectedMarker.lat.toFixed(6)}, ${selectedMarker.lon.toFixed(6)}`
                : '—' }}
            </span>
          </div>
          <div class="text-[10px] text-slate/70 mt-2 italic">
            Marker id: {{ selectedMarker.id }}
          </div>
        </div>
        <div class="text-[10px] text-slate/60 text-right mt-2 italic">A / B / Esc — close</div>
      </div>
    </Transition>

    <template #floating>
      <CoachFloat
        v-if="state === 'idle' || state === 'no-data'"
        :emotion="state === 'no-data' ? 'encouraging' : 'relaxed'"
        :text="idleCoachLine"
      />
    </template>
  </PageShell>
</template>

<style scoped>
.slide-up-enter-active,
.slide-up-leave-active {
  transition: transform 0.2s cubic-bezier(0.175, 0.885, 0.32, 1.275);
}
.slide-up-enter-from,
.slide-up-leave-to {
  transform: translateY(100%);
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>

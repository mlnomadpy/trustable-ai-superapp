<script setup lang="ts">
import { ref, computed, nextTick, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAudioStore } from '@/features/audio-playback/model/audioStore'
import { useKeyboard } from '@/shared/lib/useKeyboard'
import { bridge } from '@/shared/api/bridge'
import PageShell from '@/shared/ui/PageShell.vue'
import CyberPanel from '@/shared/ui/core/CyberPanel.vue'
import CyberSplitView from '@/shared/ui/core/CyberSplitView.vue'
import CoachFloat from '@/shared/ui/CoachFloat.vue'
import TrackMap from '@/shared/ui/core/TrackMap.vue'

const router = useRouter()
const audio = useAudioStore()

// Toggles
const showElevation = ref(true)
const showMarkers = ref(true)
const showDanger = ref(true)

const cursorIndex = ref(0)

// ── Real bridge data (no mock POIs) ─────────────────────────────────────────
// `/track/markers` → { markers: [{ kind, corner, ... }] }
// `/track/danger_zones` → { danger_zones: [{ id, start_m, end_m, description, severity }] }
// `/track/<id>/elevation` → { samples: [{ distance_m, elevation_m }], ... }
// `/track/weather` → { phase, surface_state, coaching_note }
//
// Track id is `sonoma` — matches the file at data/tracks/sonoma.json and
// what the /sessions response uses for `track` (the user-facing name is
// "Sonoma Raceway", the bridge endpoints take the slug).
const TRACK_ID = 'sonoma'

interface TrackMarker {
  kind?: string
  corner?: string | number
  name?: string
  note?: string
  description?: string
  distance_m?: number
  [k: string]: unknown
}
interface DangerZone {
  id: string | number
  start_m: number
  end_m: number
  description: string
  severity: string | number
}
interface ElevationSample { distance_m: number; elevation_m: number }
interface ElevationResponse {
  track_length_m?: number | null
  min_elevation_m?: number | null
  max_elevation_m?: number | null
  samples: ElevationSample[]
}
interface WeatherResponse {
  hour_local: number
  phase: string
  surface_state: string
  coaching_note: string
}

const markers = ref<TrackMarker[]>([])
const markersError = ref<string | null>(null)
const dangerZones = ref<DangerZone[]>([])
const dangerError = ref<string | null>(null)
const elevation = ref<ElevationResponse | null>(null)
const elevationError = ref<string | null>(null)
const weather = ref<WeatherResponse | null>(null)
const weatherError = ref<string | null>(null)

// Merged POI list: real markers + real danger zones, normalised to a
// shared shape the UI can iterate over. progress is the distance as a
// percent of track length (0–100) so the existing TrackMap helpers still
// map them onto the SVG centerline.
interface POI {
  id: string
  progress: number          // 0–100 along centerline
  svgTurnId: number | undefined
  type: 'marker' | 'danger'
  name: string
  text: string
}

const pointsOfInterest = computed<POI[]>(() => {
  const out: POI[] = []
  const trackLen = elevation.value?.track_length_m ?? null

  if (showMarkers.value) {
    markers.value.forEach((m, i) => {
      const distM = typeof m.distance_m === 'number' ? m.distance_m : null
      const pct = (distM != null && trackLen && trackLen > 0)
        ? Math.max(0, Math.min(100, (distM / trackLen) * 100))
        : null
      // Without a distance we can't position it — skip rather than fake.
      if (pct == null) return
      const corner = m.corner != null ? `T${m.corner}` : (m.name ?? `MK${i + 1}`)
      out.push({
        id: `mk-${i}-${corner}`,
        progress: pct,
        svgTurnId: undefined,
        type: 'marker',
        name: String(m.name ?? corner),
        text: String(m.note ?? m.description ?? '—'),
      })
    })
  }

  if (showDanger.value) {
    dangerZones.value.forEach((d) => {
      const mid = (d.start_m + d.end_m) / 2
      const pct = trackLen && trackLen > 0
        ? Math.max(0, Math.min(100, (mid / trackLen) * 100))
        : null
      if (pct == null) return
      out.push({
        id: `dz-${d.id}`,
        progress: pct,
        svgTurnId: undefined,
        type: 'danger',
        name: String(d.description ?? `Danger ${d.id}`),
        text: `Severity ${d.severity}. ${d.description}`,
      })
    })
  }

  return out
})

const trackMapRef = ref<any>(null)

async function resolvePoiTurnIds() {
  await nextTick()
  let tries = 5
  const tryOnce = () => {
    const r = trackMapRef.value
    if (!r || !r.trackTurns || !r.getPointAtProgress) {
      if (--tries > 0) requestAnimationFrame(tryOnce)
      return
    }
    pointsOfInterest.value.forEach(p => {
      const pt = r.getPointAtProgress(p.progress)
      let closest: any = null
      let minDist = Infinity
      r.trackTurns.forEach((t: any) => {
        const dist = Math.hypot(t.cx - pt.x, t.cy - pt.y)
        if (dist < minDist) { minDist = dist; closest = t }
      })
      if (closest) p.svgTurnId = closest.id
    })
  }
  tryOnce()
}

onMounted(async () => {
  // Fire all four fetches in parallel; each one keeps an honest error
  // state so the panel can render "DATA UNAVAILABLE" per source.
  const [mRes, dRes, eRes, wRes] = await Promise.allSettled([
    bridge.get<{ markers: TrackMarker[] }>('/track/markers'),
    bridge.get<{ danger_zones: DangerZone[] }>('/track/danger_zones'),
    bridge.get<ElevationResponse>(`/track/${TRACK_ID}/elevation`),
    bridge.get<WeatherResponse>('/track/weather'),
  ])
  if (mRes.status === 'fulfilled') markers.value = Array.isArray(mRes.value?.markers) ? mRes.value.markers : []
  else markersError.value = (mRes.reason && (mRes.reason.message ?? String(mRes.reason))) || 'error'
  if (dRes.status === 'fulfilled') dangerZones.value = Array.isArray(dRes.value?.danger_zones) ? dRes.value.danger_zones : []
  else dangerError.value = (dRes.reason && (dRes.reason.message ?? String(dRes.reason))) || 'error'
  if (eRes.status === 'fulfilled') elevation.value = eRes.value
  else elevationError.value = (eRes.reason && (eRes.reason.message ?? String(eRes.reason))) || 'error'
  if (wRes.status === 'fulfilled') weather.value = wRes.value
  else weatherError.value = (wRes.reason && (wRes.reason.message ?? String(wRes.reason))) || 'error'

  resolvePoiTurnIds()
})

const cur = computed(() => pointsOfInterest.value[cursorIndex.value] ?? null)

const dangerTurnIds = computed(() => {
  return showDanger.value
    ? pointsOfInterest.value.filter(p => p.type === 'danger' && p.svgTurnId !== undefined).map(p => p.svgTurnId!)
    : []
})

const selectMarker = (id: string) => {
  const idx = pointsOfInterest.value.findIndex(p => p.id === id)
  if (idx !== -1) {
    cursorIndex.value = idx
    audio.playSfx(pointsOfInterest.value[idx].type === 'danger' ? 'error_quiet' : 'cursor_select')
  }
}

useKeyboard((e: KeyboardEvent) => {
  const visible = pointsOfInterest.value
  if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
    if (!visible.length) return
    cursorIndex.value = (cursorIndex.value + 1) % visible.length
    audio.playSfx(cur.value?.type === 'danger' ? 'error_quiet' : 'cursor_move')
  } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
    if (!visible.length) return
    cursorIndex.value = (cursorIndex.value - 1 + visible.length) % visible.length
    audio.playSfx(cur.value?.type === 'danger' ? 'error_quiet' : 'cursor_move')
  } else if (e.key === '1') {
    showElevation.value = !showElevation.value
    audio.playSfx('cursor_select')
  } else if (e.key === '2') {
    showMarkers.value = !showMarkers.value
    cursorIndex.value = 0
    audio.playSfx('cursor_select')
  } else if (e.key === '3') {
    showDanger.value = !showDanger.value
    cursorIndex.value = 0
    audio.playSfx('cursor_select')
  } else if (e.key === 'Escape' || e.key === 'Backspace' || e.key === 'b') {
    audio.playSfx('cancel')
    router.push('/garage/analysis')
  }
})

// ── Elevation polyline from real samples ────────────────────────────────────
// Build an SVG path that fits the 0–100 viewBox. y is inverted (lower SVG y
// = higher elevation). When the samples list is empty we render an
// honest empty state rather than the previous 11-point hand-drawn shape.
const elevationPath = computed<string | null>(() => {
  const samples = elevation.value?.samples ?? []
  if (samples.length < 2) return null
  const maxD = samples[samples.length - 1].distance_m || 1
  const elevs = samples.map(s => s.elevation_m)
  const lo = Math.min(...elevs)
  const hi = Math.max(...elevs)
  const range = hi - lo || 1
  const pts = samples.map(s => {
    const x = (s.distance_m / maxD) * 100
    const y = 90 - ((s.elevation_m - lo) / range) * 70    // 20–90 band
    return `${x.toFixed(2)} ${y.toFixed(2)}`
  })
  return `M ${pts.join(' L ')}`
})

const elevationFillPath = computed<string | null>(() => {
  const p = elevationPath.value
  if (!p) return null
  return `${p} L 100 100 L 0 100 Z`
})

const weatherLabel = computed(() => {
  if (weatherError.value) return 'WEATHER · DATA UNAVAILABLE'
  if (!weather.value) return 'WEATHER · loading…'
  return `WEATHER · ${weather.value.phase.toUpperCase()} · ${weather.value.surface_state.toUpperCase()}`
})
</script>

<template>
  <PageShell title="TRACK ATLAS · SONOMA RACEWAY" :hints="['1/2/3 · TOGGLE', '◀ ▶ MOVE', 'B · BACK']" bg="cool">
    <!-- Toggles & Weather -->
    <div class="flex justify-between items-center text-body mx-2">
      <div class="flex gap-4">
        <div class="flex items-center gap-1 cursor-pointer" :class="showElevation ? 'text-ui-good' : 'text-slate'" @click="showElevation = !showElevation; audio.playSfx('cursor_select')">
          <span>[{{ showElevation ? 'x' : ' ' }}]</span> <span class="uppercase">Elevation</span>
        </div>
        <div class="flex items-center gap-1 cursor-pointer" :class="showMarkers ? 'text-ui-good' : 'text-slate'" @click="showMarkers = !showMarkers; cursorIndex = 0; audio.playSfx('cursor_select')">
          <span>[{{ showMarkers ? 'x' : ' ' }}]</span> <span class="uppercase">Markers</span>
        </div>
        <div class="flex items-center gap-1 cursor-pointer" :class="showDanger ? 'text-ui-warn' : 'text-slate'" @click="showDanger = !showDanger; cursorIndex = 0; audio.playSfx('cursor_select')">
          <span>[{{ showDanger ? 'x' : ' ' }}]</span> <span class="uppercase">Danger Zones</span>
        </div>
      </div>
      <div class="text-silver" :class="weatherError ? 'text-ui-bad' : ''">
        {{ weatherLabel }}
      </div>
    </div>

    <CyberSplitView split="60-40" gap="sm" class="flex-grow min-h-0">

      <template #left>
        <!-- Track Map Area -->
        <CyberPanel class="h-full relative flex items-center justify-center bg-[#1A252C] overflow-hidden p-2">
          <TrackMap ref="trackMapRef"
                    :strokeClass="showElevation ? 'stroke-[url(#elevationGradient)] stroke-[20]' : 'stroke-[#A0AAB5] stroke-[20]'"
                    :activeTurnId="cur?.svgTurnId"
                    :dangerTurns="dangerTurnIds"
                    @turn-click="(id: number) => { const marker = pointsOfInterest.find(p => p.svgTurnId === id); if (marker) selectMarker(marker.id); }"
          >
            <defs v-if="showElevation">
              <linearGradient id="elevationGradient" x1="0%" y1="100%" x2="0%" y2="0%">
                <stop offset="0%" stop-color="#3B82F6" />
                <stop offset="50%" stop-color="#F59E0B" />
                <stop offset="100%" stop-color="#EF4444" />
              </linearGradient>
            </defs>
          </TrackMap>

          <div class="absolute bottom-2 left-2 text-body text-silver">
            <span v-if="markersError && dangerError" class="text-ui-bad">DATA UNAVAILABLE</span>
            <span v-else-if="cur">
              <span class="text-ui-info font-bold">▶ Selected:</span>
              <span :class="cur.type === 'danger' ? 'text-ui-warn' : 'text-white'">"{{ cur.name }}" ({{ cur.id }})</span>
            </span>
            <span v-else class="text-slate">— NO POI DATA —</span>
          </div>
        </CyberPanel>
      </template>

      <template #right>
        <!-- Elevation Chart Side Panel -->
        <CyberPanel class="h-full flex flex-col text-body p-2 overflow-hidden relative">
          <div class="text-silver mb-1">ELEVATION PROFILE</div>

          <template v-if="showElevation">
            <div v-if="elevationError" class="flex-grow flex items-center justify-center text-small text-ui-bad text-center px-2 tracking-widest uppercase">
              DATA UNAVAILABLE
            </div>
            <div v-else-if="!elevationPath" class="flex-grow flex items-center justify-center text-small text-slate text-center px-2 tracking-widest uppercase">
              — no elevation samples —
            </div>
            <div v-else class="flex-grow relative flex items-end border-l border-b border-slate pb-1 pl-1 mt-2">
              <svg viewBox="0 0 100 100" class="w-full h-full preserve-aspect-ratio-none">
                <line x1="0" y1="25" x2="100" y2="25" stroke="#4A5568" stroke-width="0.5" stroke-dasharray="2,2" opacity="0.5"/>
                <line x1="0" y1="50" x2="100" y2="50" stroke="#4A5568" stroke-width="0.5" stroke-dasharray="2,2" opacity="0.5"/>
                <line x1="0" y1="75" x2="100" y2="75" stroke="#4A5568" stroke-width="0.5" stroke-dasharray="2,2" opacity="0.5"/>

                <path :d="elevationPath" fill="none" stroke="#5EED71" stroke-width="1.5" stroke-linejoin="bevel"/>
                <path v-if="elevationFillPath" :d="elevationFillPath" fill="#5EED71" opacity="0.1"/>
              </svg>

              <div class="absolute bottom-0 left-1 text-small text-slate">start</div>
              <div class="absolute bottom-0 right-1 text-small text-slate">finish</div>
              <div v-if="elevation?.max_elevation_m != null" class="absolute top-0 left-1 text-small text-slate">{{ elevation.max_elevation_m.toFixed(0) }}m</div>
              <div v-if="elevation?.min_elevation_m != null" class="absolute bottom-3 left-1 text-small text-slate">{{ elevation.min_elevation_m.toFixed(0) }}m</div>
            </div>
          </template>
          <div v-else class="flex-grow flex items-center justify-center text-slate text-center">
            ELEVATION<br>HIDDEN
          </div>
        </CyberPanel>
      </template>

    </CyberSplitView>

    <template #floating>
      <CoachFloat
        v-if="cur"
        :emotion="cur.type === 'danger' ? 'talk' : 'idle'"
        :text="cur.text"
        :key="cur.id"
      />
    </template>
  </PageShell>
</template>

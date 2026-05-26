<script setup lang="ts">
/**
 * HudTrackMap — Sonoma minimap driven by live telemetry.
 *
 * Sources, in order of preference:
 *   1. Real GPS — `lat` / `lon` from the SSE telemetry frame, snapped to
 *      the nearest point on the Sonoma real-GPS centerline
 *      (`/data/tracks/sonoma_real_gps.json`). Used when the GPS fix is
 *      sane: |lat| < 89, |lon| < 180, lon < 200 (the dataset uses 214.7
 *      as a sentinel for "no fix"), and (lat, lon) != (0, 0).
 *   2. Distance fallback — `distance_m` mapped along the centerline
 *      relative to a session-start anchor, modulo `track_length_m`. This
 *      is the same algorithm the offline viewer uses
 *      (docs/telemetry-viewer.html, lines 1127-1170). Triggered when GPS
 *      is sentinel-bound or absent. UI shows "GPS · INFERRED" (yellow).
 *
 * The car marker is rendered via the existing TrackMap SVG by mapping
 * the chosen centerline-distance to a 0-100 `carProgress` along the
 * artistic path. That keeps the visual track correct while the marker
 * follows real motion.
 */
import { ref, computed, onMounted, watch } from 'vue'
import TrackMap from '@/shared/ui/core/TrackMap.vue'

interface CenterlinePoint { distance: number; lat: number; lon: number }
interface SonomaCenterline {
  track_length_m: number
  real_centerline: CenterlinePoint[]
}

const props = defineProps<{
  track: string
  posM: number
  lat?: number | null
  lon?: number | null
}>()

const centerline = ref<CenterlinePoint[] | null>(null)
const trackLengthM = ref<number>(4258)
const startAnchorM = ref<number | null>(null)

// Load centerline once. The file lives in /public, so it's served as a
// static asset by Vite both in dev and prod.
onMounted(async () => {
  try {
    const res = await fetch('/data/tracks/sonoma_real_gps.json')
    if (!res.ok) return
    const data = (await res.json()) as SonomaCenterline
    if (Array.isArray(data?.real_centerline) && data.real_centerline.length > 1) {
      centerline.value = data.real_centerline
      trackLengthM.value = data.track_length_m || 4258
    }
  } catch (e) {
    console.warn('[HudTrackMap] failed to load centerline', e)
  }
})

const gpsValid = computed(() => {
  const la = props.lat
  const lo = props.lon
  if (la == null || lo == null) return false
  if (!Number.isFinite(la) || !Number.isFinite(lo)) return false
  if (Math.abs(la) >= 89) return false
  if (Math.abs(lo) >= 180) return false
  // Dataset sentinel: lon ~= 214.7 means "no fix". The Math.abs >= 180
  // check above already rejects that, but the explicit upper bound here
  // documents intent for any future dataset cleanups.
  if (lo >= 200) return false
  if (la === 0 && lo === 0) return false
  return true
})

// Anchor the distance fallback to the first frame we see with a non-null
// distance, so partial sessions still align with the centerline (matches
// the offline viewer's `d0` behaviour).
watch(
  () => props.posM,
  (d) => {
    if (startAnchorM.value == null && Number.isFinite(d) && d > 0) {
      startAnchorM.value = d
    }
  },
  { immediate: true },
)

// Find nearest centerline point to a (lat, lon) using a cheap planar
// metric — fine for the ~4 km Sonoma circuit.
function nearestCenterlineDist(la: number, lo: number): number | null {
  const cl = centerline.value
  if (!cl || cl.length === 0) return null
  let best = 0
  let bestD = Infinity
  for (let i = 0; i < cl.length; i++) {
    const p = cl[i]
    const dla = p.lat - la
    const dlo = p.lon - lo
    const sq = dla * dla + dlo * dlo
    if (sq < bestD) {
      bestD = sq
      best = i
    }
  }
  return cl[best].distance
}

/**
 * Centerline distance (m) for the current frame, in [0, track_length_m).
 * Returns null when neither GPS nor distance is usable yet.
 */
const centerlineDistanceM = computed<number | null>(() => {
  // Path 1: real GPS snap.
  if (gpsValid.value && centerline.value) {
    const la = props.lat as number
    const lo = props.lon as number
    const d = nearestCenterlineDist(la, lo)
    if (d != null) return d
  }
  // Path 2: distance fallback, modulo track length, anchored at first
  // observed distance so partial sessions align with the start line.
  if (Number.isFinite(props.posM) && props.posM > 0 && startAnchorM.value != null) {
    const len = trackLengthM.value
    const raw = props.posM - startAnchorM.value
    return ((raw % len) + len) % len
  }
  return null
})

const carProgressPct = computed<number | null>(() => {
  const d = centerlineDistanceM.value
  if (d == null) return null
  return Math.min(100, Math.max(0, (d / trackLengthM.value) * 100))
})

const gpsMode = computed<'LIVE' | 'INFERRED' | 'NONE'>(() => {
  if (centerlineDistanceM.value == null) return 'NONE'
  return gpsValid.value && centerline.value ? 'LIVE' : 'INFERRED'
})

const positionLabel = computed(() => {
  const d = centerlineDistanceM.value
  if (d == null) return '—'
  return `${Math.floor(d)}m`
})
</script>

<template>
  <div class="track-map">
    <div class="map-frame">
      <span class="map-label text-small text-silver/60">{{ track.toUpperCase() }} MAP</span>

      <div class="absolute inset-2">
        <TrackMap :car-progress="carProgressPct" stroke-class="text-slate opacity-40" />
      </div>

      <!-- Position indicator -->
      <div class="pos-indicator text-body text-ui-info font-nums">
        <span v-if="carProgressPct == null" class="text-slate/60">NO POSITION</span>
        <span v-else>▶ {{ positionLabel }}</span>
      </div>

      <!-- GPS source pill -->
      <div class="gps-pill" :class="`gps-${gpsMode.toLowerCase()}`">
        GPS · {{ gpsMode === 'NONE' ? '—' : gpsMode }}
      </div>
    </div>
  </div>
</template>

<style scoped>
.track-map {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}

.map-frame {
  width: clamp(140px, 35vw, 280px);
  height: clamp(100px, 25vh, 200px);
  border: 1px solid var(--color-slate);
  background: linear-gradient(180deg, rgba(42, 47, 66, 0.4) 0%, rgba(31, 34, 48, 0.6) 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  overflow: hidden;
}

.map-label {
  position: absolute;
  top: clamp(4px, 1vmin, 10px);
  left: clamp(6px, 1.5vmin, 12px);
  letter-spacing: 0.1em;
  z-index: 10;
}

.pos-indicator {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  text-shadow: 0 0 6px rgba(74, 152, 200, 0.6);
  animation: pos-pulse 2s ease-in-out infinite;
}

.gps-pill {
  position: absolute;
  bottom: clamp(4px, 1vmin, 10px);
  left: clamp(6px, 1.5vmin, 12px);
  z-index: 10;
  font-family: var(--font-ui);
  font-size: clamp(9px, 1.4vmin, 11px);
  font-weight: 700;
  letter-spacing: 0.1em;
  padding: 2px 6px;
  border: 1px solid currentColor;
  border-radius: 2px;
  text-transform: uppercase;
  line-height: 1;
}

.gps-live {
  color: var(--color-ui-good);
  background: color-mix(in srgb, var(--color-ui-good) 12%, transparent);
}

.gps-inferred {
  color: var(--color-ui-warn);
  background: color-mix(in srgb, var(--color-ui-warn) 12%, transparent);
}

.gps-none {
  color: var(--color-slate);
  background: rgba(0, 0, 0, 0.4);
}

@keyframes pos-pulse {
  0%, 100% { opacity: 0.7; }
  50% { opacity: 1; }
}
</style>

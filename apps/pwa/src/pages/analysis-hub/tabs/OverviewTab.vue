<script setup lang="ts">
/**
 * Overview tab: 11-cell summary grid on the left, Leaflet Sonoma map
 * on the right. Mirrors `renderSummary` + `renderTrackMap` from
 * docs/telemetry-viewer.html. Map is lazy-imported so Leaflet doesn't
 * bloat the initial bundle, and rebuilt whenever the lap selection
 * changes.
 */
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import CyberPanel from '@/shared/ui/core/CyberPanel.vue'
import { useAnalysisStore } from '@/entities/analysis/model/analysisStore'
import { useDuckDBStore } from '@/shared/lib/duckdb/duckdbStore'
import { asNum } from '@/shared/lib/telemetry/queries'

interface SummaryStats {
  durS: number
  wideN: number
  tallN: number
  distinct: number
  totalSignals: number
  distance: number
  peakSpeedMph: number
  peakRpm: number
  peakG: number
  wideRateHz: number
  signalRate: number
}

const analysis = useAnalysisStore()
const duck = useDuckDBStore()

const summary = ref<SummaryStats | null>(null)
const summaryError = ref<string | null>(null)
const summaryLoading = ref(false)

async function loadSummary() {
  const sid = analysis.sessionId
  if (!sid) { summary.value = null; return }
  summaryLoading.value = true
  summaryError.value = null
  try {
    const lf = analysis.lapFilterSql('timestamp')
    const lfT = analysis.lapFilterSql('t')
    const sidParams = [sid, ...lf.params]
    const sidTParams = [sid, ...lfT.params]
    const wideN = asNum(await duck.scalar(
      'SELECT COUNT(*) FROM telemetry WHERE session_id = ?' + lf.sql, sidParams,
    )) ?? 0
    const tallN = asNum(await duck.scalar(
      'SELECT COUNT(*) FROM telemetry_signals WHERE session_id = ?' + lfT.sql, sidTParams,
    )) ?? 0
    const tlo = asNum(await duck.scalar(
      'SELECT MIN(timestamp) FROM telemetry WHERE session_id = ?' + lf.sql, sidParams,
    ))
    const thi = asNum(await duck.scalar(
      'SELECT MAX(timestamp) FROM telemetry WHERE session_id = ?' + lf.sql, sidParams,
    ))
    const durS = (tlo != null && thi != null) ? (thi - tlo) : 0
    const tallTLo = asNum(await duck.scalar(
      'SELECT MIN(t) FROM telemetry_signals WHERE session_id = ?' + lfT.sql, sidTParams,
    ))
    const tallTHi = asNum(await duck.scalar(
      'SELECT MAX(t) FROM telemetry_signals WHERE session_id = ?' + lfT.sql, sidTParams,
    ))
    const tallDur = (tallTLo != null && tallTHi != null) ? (tallTHi - tallTLo) : 0
    const totalSignals = asNum(await duck.scalar('SELECT COUNT(*) FROM signal_registry')) ?? 0
    const distinct = asNum(await duck.scalar(
      'SELECT COUNT(DISTINCT signal_id) FROM telemetry_signals WHERE session_id = ?' + lfT.sql,
      sidTParams,
    )) ?? 0
    const distance = asNum(await duck.scalar(
      'SELECT MAX(distance_m) - MIN(distance_m) FROM telemetry WHERE session_id = ?' + lf.sql,
      sidParams,
    )) ?? 0
    const peakSpeedMph = asNum(await duck.scalar(
      'SELECT MAX(speed_ms)*2.2369362920544 FROM telemetry WHERE session_id = ?' + lf.sql,
      sidParams,
    )) ?? 0
    const peakRpm = asNum(await duck.scalar(
      'SELECT MAX(rpm) FROM telemetry WHERE session_id = ?' + lf.sql, sidParams,
    )) ?? 0
    const peakG = asNum(await duck.scalar(
      'SELECT MAX(combo_g) FROM telemetry WHERE session_id = ?' + lf.sql, sidParams,
    )) ?? 0
    summary.value = {
      durS, wideN, tallN, distinct, totalSignals, distance,
      peakSpeedMph, peakRpm, peakG,
      wideRateHz: durS > 0 ? wideN / durS : 0,
      signalRate: tallDur > 0 ? tallN / tallDur : 0,
    }
  } catch (e) {
    summaryError.value = e instanceof Error ? e.message : String(e)
    summary.value = null
  } finally {
    summaryLoading.value = false
  }
}

function fmtDur(s: number): string {
  if (!s) return '—'
  if (s < 60) return s.toFixed(1) + ' s'
  if (s < 3600) return Math.floor(s / 60) + 'm ' + Math.floor(s % 60) + 's'
  return Math.floor(s / 3600) + 'h ' + Math.floor((s % 3600) / 60) + 'm'
}

const scope = computed(() => analysis.selectedLap?.name ?? 'Full session')

// ── Map ──────────────────────────────────────────────────────────────────
const mapEl = ref<HTMLDivElement | null>(null)
const mapNote = ref<string>('')
const mapError = ref<string | null>(null)
// Leaflet types are loaded as values lazily; we keep `unknown`-typed
// refs so we can call .remove() safely on unmount.
let mapInstance: { remove: () => void; invalidateSize: () => void } | null = null

interface SonomaTrack {
  track_length_m?: number
  real_centerline?: Array<{ distance: number; lat: number; lon: number }>
  corners?: Array<{ number: string | number; name: string; nicknames?: string[]; apex?: { lat: number; lon: number } }>
}

async function loadSonomaTrack(): Promise<SonomaTrack | null> {
  // Try real GPS first, fall back to anonymised.
  for (const p of ['/data/tracks/sonoma_real_gps.json', '/data/tracks/sonoma.json']) {
    try {
      const res = await fetch(p)
      if (res.ok) return await res.json() as SonomaTrack
    } catch { /* try next */ }
  }
  return null
}

async function buildMap() {
  if (!mapEl.value) return
  destroyMap()
  mapError.value = null
  const sid = analysis.sessionId
  if (!sid) return
  try {
    const [{ default: L }] = await Promise.all([
      import('leaflet'),
      import('leaflet/dist/leaflet.css'),
    ])
    const track = await loadSonomaTrack()

    let center: [number, number] = [38.1607, -122.4549]
    if (track?.real_centerline?.length) {
      center = [track.real_centerline[0].lat, track.real_centerline[0].lon]
    }
    const map = L.map(mapEl.value, { zoomSnap: 0.25, attributionControl: true })
      .setView(center, 16)
    mapInstance = map as unknown as typeof mapInstance
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution: '&copy; OpenStreetMap contributors',
    }).addTo(map)

    let centerline: [number, number][] | null = null
    if (track?.real_centerline?.length) {
      centerline = track.real_centerline.map((p) => [p.lat, p.lon] as [number, number])
      L.polyline(centerline, { color: '#7cc5ff', weight: 3, opacity: 0.85 }).addTo(map)
      map.fitBounds(L.latLngBounds(centerline), { padding: [30, 30] })
      if (track.corners) {
        for (const c of track.corners) {
          if (c.apex?.lat) {
            L.marker([c.apex.lat, c.apex.lon], {
              icon: L.divIcon({ className: 'corner-marker', html: String(c.number), iconSize: [20, 20] }),
            }).bindTooltip(`${c.name}${c.nicknames?.[0] ? ' · ' + c.nicknames[0] : ''}`).addTo(map)
          }
        }
      }
    }

    // Raw GPS path (filter sentinels — lon 214.7 is a known stale value)
    const lf = analysis.lapFilterSql('timestamp')
    const realGps = await duck.rows<{ lat: unknown; lon: unknown }>(
      `SELECT lat, lon FROM telemetry
        WHERE session_id = ? AND lat > -89 AND lat < 89
          AND lon BETWEEN -180 AND 180
          AND lat <> 0 AND lon <> 0 AND lon < 200` + lf.sql + `
        ORDER BY timestamp`,
      [sid, ...lf.params],
    )
    if (realGps.length > 30) {
      const path: [number, number][] = realGps
        .map((r) => [asNum(r.lat) ?? 0, asNum(r.lon) ?? 0] as [number, number])
      L.polyline(path, { color: '#f0c674', weight: 2, opacity: 0.85 }).addTo(map)
    }

    // Virtual path: distance_m -> centerline
    let virtCount = 0
    if (centerline && track?.real_centerline?.length) {
      const distRows = await duck.rows<{ timestamp: unknown; distance_m: unknown }>(
        `SELECT timestamp, distance_m FROM telemetry
          WHERE session_id = ? AND distance_m IS NOT NULL` + lf.sql + `
          ORDER BY timestamp`,
        [sid, ...lf.params],
      )
      if (distRows.length > 30) {
        const trackLen = track.track_length_m ?? 4258
        const cl = track.real_centerline
        const dists = cl.map((p) => p.distance)
        const d0 = asNum(distRows[0].distance_m) ?? 0
        const virt: [number, number][] = []
        for (const r of distRows) {
          const dm = asNum(r.distance_m) ?? 0
          const dAlong = (((dm - d0) % trackLen) + trackLen) % trackLen
          let lo = 0, hi = cl.length - 1
          while (lo < hi - 1) {
            const mid = (lo + hi) >> 1
            if (dists[mid] <= dAlong) lo = mid
            else hi = mid
          }
          const a = cl[lo], b = cl[hi]
          const span = (b.distance - a.distance) || 1
          const t = (dAlong - a.distance) / span
          virt.push([a.lat + (b.lat - a.lat) * t, a.lon + (b.lon - a.lon) * t])
        }
        const stride = Math.max(1, Math.floor(virt.length / 4000))
        const pts: [number, number][] = []
        for (let i = 0; i < virt.length; i += stride) pts.push(virt[i])
        L.polyline(pts, { color: '#7ee787', weight: 2, opacity: 0.85, dashArray: '3 3' }).addTo(map)
        virtCount = virt.length
        if (analysis.selectedLap && pts.length) {
          L.circleMarker(pts[0], { radius: 7, color: '#7ee787', fillColor: '#7ee787', fillOpacity: 0.8, weight: 1 })
            .bindTooltip(`${analysis.selectedLap.name} start`).addTo(map)
          L.circleMarker(pts[pts.length - 1], { radius: 7, color: '#f47174', fillColor: '#f47174', fillOpacity: 0.8, weight: 1 })
            .bindTooltip(`${analysis.selectedLap.name} end`).addTo(map)
        }
      }
    }
    if (realGps.length > 30 && virtCount > 0) {
      mapNote.value = `${realGps.length.toLocaleString()} GPS samples + ${virtCount.toLocaleString()} virtual position points`
    } else if (virtCount > 0) {
      mapNote.value = `GPS sentinel-bound · virtual path from ${virtCount.toLocaleString()} distance samples`
    } else if (realGps.length > 30) {
      mapNote.value = `${realGps.length.toLocaleString()} GPS samples`
    } else {
      mapNote.value = 'no movement data'
    }

    // The panel mounts hidden behind a tab — defer one frame so the
    // container has its final box, then ask Leaflet to recompute.
    await nextTick()
    setTimeout(() => mapInstance?.invalidateSize(), 100)
  } catch (e) {
    mapError.value = e instanceof Error ? e.message : String(e)
  }
}

function destroyMap() {
  if (mapInstance) {
    try { mapInstance.remove() } catch { /* ignore */ }
    mapInstance = null
  }
}

onMounted(async () => {
  await loadSummary()
  await buildMap()
})
onUnmounted(destroyMap)

watch(
  () => [analysis.sessionId, analysis.selectedLapIndex, analysis.filterOutliers],
  async () => {
    await loadSummary()
    await buildMap()
  },
)
</script>

<template>
  <div v-if="!analysis.sessionId" class="h-full flex items-center justify-center">
    <CyberPanel class="text-center" :animate="false">
      <div class="text-ui-warn text-body">NO SESSION SELECTED</div>
      <div class="text-slate text-small mt-2">Pick a session from the toolbar to load telemetry.</div>
    </CyberPanel>
  </div>
  <div v-else class="h-full grid grid-cols-[1.1fr_1fr] gap-3 min-h-0">
    <!-- Summary -->
    <CyberPanel class="overflow-auto min-h-0">
      <div class="text-silver tracking-[0.2em] mb-2 text-small">SESSION · {{ scope.toUpperCase() }}</div>
      <div v-if="summaryError" class="text-ui-bad text-small">DATA UNAVAILABLE — {{ summaryError }}</div>
      <div v-else-if="summaryLoading && !summary" class="text-slate text-small">Loading…</div>
      <div v-else-if="summary" class="grid grid-cols-3 gap-2">
        <div class="stat-cell"><div class="stat-v truncate" :title="analysis.sessionId ?? ''">{{ analysis.sessionId }}</div><div class="stat-l">SESSION ID</div></div>
        <div class="stat-cell"><div class="stat-v">{{ fmtDur(summary.durS) }}</div><div class="stat-l">DURATION</div></div>
        <div class="stat-cell"><div class="stat-v">{{ summary.wideN.toLocaleString() }}</div><div class="stat-l">WIDE ROWS</div></div>
        <div class="stat-cell"><div class="stat-v">{{ summary.tallN.toLocaleString() }}</div><div class="stat-l">SIGNAL SAMPLES</div></div>
        <div class="stat-cell"><div class="stat-v">{{ summary.distinct }} <span class="stat-sub">/ {{ summary.totalSignals }}</span></div><div class="stat-l">SIGNALS SEEN</div></div>
        <div class="stat-cell"><div class="stat-v">{{ summary.wideRateHz.toFixed(1) }} <span class="stat-sub">Hz</span></div><div class="stat-l">WIDE RATE</div></div>
        <div class="stat-cell"><div class="stat-v">{{ summary.signalRate.toFixed(0) }} <span class="stat-sub">/s</span></div><div class="stat-l">SIGNAL RATE</div></div>
        <div class="stat-cell"><div class="stat-v">{{ (summary.distance / 1000).toFixed(2) }} <span class="stat-sub">km</span></div><div class="stat-l">DISTANCE</div></div>
        <div class="stat-cell"><div class="stat-v">{{ summary.peakSpeedMph.toFixed(1) }} <span class="stat-sub">mph</span></div><div class="stat-l">PEAK SPEED</div></div>
        <div class="stat-cell"><div class="stat-v">{{ summary.peakRpm.toFixed(0) }}</div><div class="stat-l">PEAK RPM</div></div>
        <div class="stat-cell"><div class="stat-v">{{ summary.peakG.toFixed(2) }} <span class="stat-sub">g</span></div><div class="stat-l">PEAK COMBO G</div></div>
      </div>
      <div v-else class="text-slate text-small">NO TELEMETRY ROWS IN THIS SESSION</div>
    </CyberPanel>
    <!-- Map -->
    <CyberPanel class="flex flex-col min-h-0">
      <div class="text-silver tracking-[0.2em] mb-2 text-small">TRACK · SONOMA RACEWAY</div>
      <div v-if="mapError" class="text-ui-bad text-small mb-2">MAP UNAVAILABLE — {{ mapError }}</div>
      <div ref="mapEl" class="flex-1 min-h-0 rounded bg-[#0a0a10]" />
      <div class="flex gap-3 text-[10px] text-slate mt-2 flex-wrap">
        <span><span class="swatch" style="background:#7cc5ff" />centerline</span>
        <span><span class="swatch" style="background:#f0c674" />raw GPS</span>
        <span><span class="swatch" style="background:#7ee787" />virtual path</span>
        <span class="ml-auto">{{ mapNote }}</span>
      </div>
    </CyberPanel>
  </div>
</template>

<style scoped>
.stat-cell {
  background: rgba(29,29,39,.8);
  border: 1px solid rgba(255,255,255,.04);
  border-radius: 4px;
  padding: 8px 10px;
  min-height: 44px;
}
.stat-v {
  font-size: clamp(14px, 1.6vmin, 18px);
  color: #7cc5ff;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}
.stat-sub {
  font-size: 11px;
  color: #9aa0b4;
}
.stat-l {
  font-size: 10px;
  color: #9aa0b4;
  letter-spacing: 0.05em;
  margin-top: 2px;
  text-transform: uppercase;
}
.swatch {
  display: inline-block;
  width: 16px;
  height: 3px;
  vertical-align: middle;
  margin-right: 4px;
}
/* Corner markers used inside the leaflet map (global since Leaflet
 * appends to document.body). */
:global(.corner-marker) {
  background: #15151c;
  color: #e9e9f0;
  border: 1px solid #7cc5ff;
  border-radius: 10px;
  width: 20px; height: 20px;
  text-align: center;
  font-size: 10px;
  line-height: 18px;
  font-weight: 600;
}
:global(.leaflet-container) {
  background: #0a0a10;
}
:global(.leaflet-control-attribution) {
  background: rgba(13,13,18,.6) !important;
  color: #9aa0b4 !important;
  font-size: 10px !important;
}
</style>

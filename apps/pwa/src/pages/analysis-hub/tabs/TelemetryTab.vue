<script setup lang="ts">
/**
 * Telemetry tab: three twin-axis line charts (Speed+RPM, Driver
 * inputs, G-forces). Pulls the wide canonical table once and
 * decimates to ~4000 points to keep Chart.js responsive.
 *
 * Re-queries whenever the active lap or outlier toggle change.
 */
import { computed, onMounted, ref, watch } from 'vue'
import type { ChartData, ChartOptions } from 'chart.js'
import CyberPanel from '@/shared/ui/core/CyberPanel.vue'
import CyberLineChart from '@/shared/ui/charts/CyberLineChart.vue'
import { useAnalysisStore } from '@/entities/analysis/model/analysisStore'
import { useDuckDBStore } from '@/shared/lib/duckdb/duckdbStore'
import { asNum, decimate, tallT0 } from '@/shared/lib/telemetry/queries'
import { clipOutliers } from '@/shared/lib/telemetry/outliers'

interface WideRow {
  timestamp: number
  speed_ms: number | null
  rpm: number | null
  brake_bar: number | null
  throttle_pct: number | null
  g_lat: number | null
  g_long: number | null
  combo_g: number | null
  steering_deg: number | null
}

const analysis = useAnalysisStore()
const duck = useDuckDBStore()

const rows = ref<WideRow[]>([])
const gVertByT = ref<Array<number | null>>([])
const loading = ref(false)
const err = ref<string | null>(null)

async function load() {
  const sid = analysis.sessionId
  if (!sid) { rows.value = []; gVertByT.value = []; return }
  loading.value = true
  err.value = null
  try {
    const lf = analysis.lapFilterSql('timestamp')
    const raw = await duck.rows(
      `SELECT timestamp, speed_ms, rpm, brake_bar, throttle_pct,
              g_lat, g_long, combo_g, steering_deg
         FROM telemetry
        WHERE session_id = ?` + lf.sql + `
        ORDER BY timestamp`,
      [sid, ...lf.params],
    )
    const target = 4000
    const stride = Math.max(1, Math.floor(raw.length / target))
    const out: WideRow[] = []
    for (let i = 0; i < raw.length; i += stride) {
      const r = raw[i]
      out.push({
        timestamp: asNum(r.timestamp) ?? 0,
        speed_ms: asNum(r.speed_ms),
        rpm: asNum(r.rpm),
        brake_bar: asNum(r.brake_bar),
        throttle_pct: asNum(r.throttle_pct),
        g_lat: asNum(r.g_lat),
        g_long: asNum(r.g_long),
        combo_g: asNum(r.combo_g),
        steering_deg: asNum(r.steering_deg),
      })
    }
    rows.value = out

    // g_vert lives only in the tall store — merge by nearest sample.
    const lfT = analysis.lapFilterSql('ts.t')
    const t0 = await tallT0()
    const gv = await duck.rows<{ t: unknown; value: unknown }>(
      `SELECT ts.t, ts.value FROM telemetry_signals ts
         JOIN signal_registry sr USING(signal_id)
        WHERE sr.name = 'g_vert' AND ts.session_id = ?` + lfT.sql + `
        ORDER BY ts.t`,
      [sid, ...lfT.params],
    )
    if (gv.length && out.length) {
      // Hold-merge against the wide timestamps.
      const samples = gv.map((s) => ({ t: asNum(s.t) ?? 0, v: asNum(s.value) }))
      const merged: Array<number | null> = new Array(out.length).fill(null)
      let j = 0
      for (let i = 0; i < out.length; i++) {
        const at = out[i].timestamp - t0 + t0 // wide stays in absolute t
        while (j < samples.length && samples[j].t <= at) j++
        merged[i] = j === 0 ? null : samples[j - 1].v
      }
      gVertByT.value = merged
    } else {
      gVertByT.value = []
    }
  } catch (e) {
    err.value = e instanceof Error ? e.message : String(e)
    rows.value = []
  } finally {
    loading.value = false
  }
}

onMounted(load)
watch(
  () => [analysis.sessionId, analysis.selectedLapIndex, analysis.filterOutliers],
  load,
)

// ── Chart data builders ──────────────────────────────────────────────────
const t0w = computed(() => rows.value[0]?.timestamp ?? 0)
const labels = computed(() => rows.value.map((r) => r.timestamp - t0w.value))

function clip<T extends number | null>(name: string, arr: T[]) {
  return clipOutliers(name, arr, analysis.filterOutliers) as T[]
}

const speedRpmData = computed<ChartData<'line'>>(() => ({
  labels: labels.value,
  datasets: [
    {
      label: 'speed (mph)',
      data: clip('speed_mph', rows.value.map((r) => r.speed_ms == null ? null : r.speed_ms * 2.2369362920544)),
      borderColor: '#7cc5ff', backgroundColor: 'rgba(124,197,255,.1)',
      borderWidth: 1.5, pointRadius: 0, yAxisID: 'y',
    },
    {
      label: 'rpm',
      data: clip('rpm', rows.value.map((r) => r.rpm)),
      borderColor: '#f0c674', borderWidth: 1.5, pointRadius: 0, yAxisID: 'y2',
    },
  ],
}))

const speedRpmOpts: ChartOptions<'line'> = {
  scales: {
    x: { type: 'linear', title: { display: true, text: 'time (s)' } },
    y: { position: 'left', title: { display: true, text: 'mph' } },
    y2: { position: 'right', title: { display: true, text: 'rpm' }, grid: { drawOnChartArea: false } },
  },
}

const driverData = computed<ChartData<'line'>>(() => ({
  labels: labels.value,
  datasets: [
    {
      label: 'throttle %',
      data: clip('throttle_pct', rows.value.map((r) => r.throttle_pct)),
      borderColor: '#7ee787', borderWidth: 1.5, pointRadius: 0,
    },
    {
      label: 'brake (bar × 10)',
      data: clip('brake_bar', rows.value.map((r) => r.brake_bar)).map((v) => v == null ? null : v * 10),
      borderColor: '#f47174', borderWidth: 1.5, pointRadius: 0,
    },
    {
      label: 'steering (°)',
      data: clip('steering_deg', rows.value.map((r) => r.steering_deg)),
      borderColor: '#c8a2ff', borderWidth: 1.5, pointRadius: 0,
    },
  ],
}))

const driverOpts: ChartOptions<'line'> = {
  scales: {
    x: { type: 'linear', title: { display: true, text: 'time (s)' } },
    y: {},
  },
}

const gForceData = computed<ChartData<'line'>>(() => {
  const ds: ChartData<'line'>['datasets'] = [
    {
      label: 'g_lat',
      data: clip('g_lat', rows.value.map((r) => r.g_lat)),
      borderColor: '#7cc5ff', borderWidth: 1.5, pointRadius: 0,
    },
    {
      label: 'g_long',
      data: clip('g_long', rows.value.map((r) => r.g_long)),
      borderColor: '#f0c674', borderWidth: 1.5, pointRadius: 0,
    },
  ]
  if (gVertByT.value.length) {
    ds.push({
      label: 'g_vert',
      data: clip('g_vert', gVertByT.value),
      borderColor: '#7ee787', borderWidth: 1.5, pointRadius: 0,
    })
  }
  ds.push({
    label: 'combo_g',
    data: clip('combo_g', rows.value.map((r) => r.combo_g)),
    borderColor: '#f47174', borderWidth: 1, borderDash: [4, 3], pointRadius: 0,
  })
  return { labels: labels.value, datasets: ds }
})

const gForceOpts: ChartOptions<'line'> = {
  scales: {
    x: { type: 'linear', title: { display: true, text: 'time (s)' } },
    y: { title: { display: true, text: 'g' } },
  },
}

// silence unused-import lint when decimate isn't used inline
void decimate
</script>

<template>
  <div v-if="!analysis.sessionId" class="h-full flex items-center justify-center">
    <CyberPanel class="text-center" :animate="false">
      <div class="text-ui-warn text-body">NO SESSION SELECTED</div>
    </CyberPanel>
  </div>
  <div v-else-if="err" class="h-full flex items-center justify-center">
    <CyberPanel class="text-center" :animate="false">
      <div class="text-ui-bad text-body">DATA UNAVAILABLE</div>
      <div class="text-slate text-small mt-2">{{ err }}</div>
    </CyberPanel>
  </div>
  <div v-else-if="!loading && !rows.length" class="h-full flex items-center justify-center">
    <CyberPanel class="text-center" :animate="false">
      <div class="text-slate text-body">NO TELEMETRY ROWS IN THIS LAP</div>
    </CyberPanel>
  </div>
  <div v-else class="h-full grid grid-rows-3 gap-2 min-h-0">
    <CyberPanel class="flex flex-col min-h-0">
      <div class="text-silver tracking-[0.2em] text-small mb-1">SPEED &amp; RPM</div>
      <div class="flex-1 min-h-0"><CyberLineChart :data="speedRpmData" :options="speedRpmOpts" zoom aria-label="Speed and RPM" /></div>
    </CyberPanel>
    <CyberPanel class="flex flex-col min-h-0">
      <div class="text-silver tracking-[0.2em] text-small mb-1">DRIVER INPUTS</div>
      <div class="flex-1 min-h-0"><CyberLineChart :data="driverData" :options="driverOpts" zoom aria-label="Driver inputs" /></div>
    </CyberPanel>
    <CyberPanel class="flex flex-col min-h-0">
      <div class="text-silver tracking-[0.2em] text-small mb-1">G-FORCES</div>
      <div class="flex-1 min-h-0"><CyberLineChart :data="gForceData" :options="gForceOpts" zoom aria-label="G forces" /></div>
    </CyberPanel>
  </div>
</template>

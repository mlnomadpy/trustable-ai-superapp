<script setup lang="ts">
/**
 * Signals tab: full port of `renderPicker` from the HTML viewer.
 *   - left pane: search box, preset buttons, grouped signal list with checkboxes
 *   - right pane: twin-axis overlay chart with zoom
 *
 * Signals are auto-grouped by `units` so the chart never carries more
 * than two y-axes (third+ unit groups fall back onto the dominant axis).
 */
import { computed, onMounted, reactive, ref, watch } from 'vue'
import type { ChartData, ChartOptions } from 'chart.js'
import CyberPanel from '@/shared/ui/core/CyberPanel.vue'
import CyberLineChart from '@/shared/ui/charts/CyberLineChart.vue'
import { useAnalysisStore } from '@/entities/analysis/model/analysisStore'
import { useDuckDBStore } from '@/shared/lib/duckdb/duckdbStore'
import { asNum, fetchSignalSeries, tallT0 } from '@/shared/lib/telemetry/queries'
import { clipOutliers, type PointXY } from '@/shared/lib/telemetry/outliers'

interface SignalMeta {
  name: string
  units: string
  group: string
  n: number
}

const COLORS = ['#7cc5ff', '#f0c674', '#7ee787', '#f47174', '#c8a2ff', '#ffd86b', '#9aa0b4', '#76d3c4', '#ff9ab6', '#a3b0ff']

const PRESET_MAP: Record<string, string[]> = {
  speed_rpm: ['speed_ms', 'rpm'],
  driver: ['throttle_pct', 'brake_bar', 'steering_deg'],
  g: ['g_lat', 'g_long', 'g_vert'],
  imu: ['inline_accel_g', 'lateral_accel_g', 'vertical_accel_g', 'roll_rate_degs', 'pitch_rate_degs', 'yaw_rate_degs'],
  oil: ['oil_press_psi', 'oil_filter_temp_f', 'engine_oil_temp_f'],
  clear: [],
}

const analysis = useAnalysisStore()
const duck = useDuckDBStore()

const signals = ref<SignalMeta[]>([])
const selected = reactive<Set<string>>(new Set())
const search = ref('')
const seriesCache = reactive<Map<string, PointXY[]>>(new Map())
const err = ref<string | null>(null)
const loading = ref(false)

async function loadCatalog() {
  const sid = analysis.sessionId
  if (!sid) return
  loading.value = true
  err.value = null
  try {
    const rows = await duck.rows<{ name: unknown; units: unknown; group: unknown; n: unknown }>(
      `SELECT sr.name, sr.units, sr."group", COUNT(*) AS n
         FROM telemetry_signals ts
         JOIN signal_registry sr USING(signal_id)
        WHERE ts.session_id = ?
        GROUP BY sr.signal_id, sr.name, sr.units, sr."group"
        ORDER BY sr."group" NULLS LAST, sr.name`,
      [sid],
    )
    signals.value = rows.map((r) => ({
      name: String(r.name ?? ''),
      units: r.units == null ? '' : String(r.units),
      group: r.group == null ? '(other)' : String(r.group),
      n: asNum(r.n) ?? 0,
    }))
    // Default selection: speed_ms + rpm if both exist
    if (!selected.size) {
      for (const s of signals.value) {
        if (s.name === 'speed_ms' || s.name === 'rpm') selected.add(s.name)
      }
    }
  } catch (e) {
    err.value = e instanceof Error ? e.message : String(e)
  } finally {
    loading.value = false
  }
}

async function refreshSelectedSeries() {
  const sid = analysis.sessionId
  if (!sid) return
  const t0 = await tallT0()
  const names = Array.from(selected)
  // Always re-pull (lap or filter may have changed)
  seriesCache.clear()
  await Promise.all(names.map(async (n) => {
    const s = await fetchSignalSeries(sid, n, t0, 3000)
    seriesCache.set(n, s)
  }))
}

onMounted(async () => {
  await loadCatalog()
  await refreshSelectedSeries()
})

watch(() => [analysis.sessionId, analysis.selectedLapIndex, analysis.filterOutliers],
  async () => {
    await loadCatalog()
    await refreshSelectedSeries()
  },
)

const grouped = computed(() => {
  const needle = search.value.trim().toLowerCase()
  const m = new Map<string, SignalMeta[]>()
  for (const s of signals.value) {
    if (needle && !`${s.name} ${s.units} ${s.group}`.toLowerCase().includes(needle)) continue
    const arr = m.get(s.group) ?? []
    arr.push(s)
    m.set(s.group, arr)
  }
  return Array.from(m.entries())
})

async function toggle(name: string, on: boolean) {
  if (on) selected.add(name); else selected.delete(name)
  await refreshSelectedSeries()
}

async function applyPreset(p: keyof typeof PRESET_MAP) {
  const want = new Set(PRESET_MAP[p])
  selected.clear()
  for (const n of want) {
    // Only add if the catalog actually has it for this session.
    if (signals.value.some((s) => s.name === n)) selected.add(n)
  }
  await refreshSelectedSeries()
}

async function clearAll() {
  selected.clear()
  await refreshSelectedSeries()
}

const chartData = computed<ChartData<'line'>>(() => {
  const picks = signals.value.filter((s) => selected.has(s.name))
  if (!picks.length) return { datasets: [] }
  // Group picks by unit; first two unit groups get y / y2 axes.
  const unitGroups = new Map<string, SignalMeta[]>()
  for (const p of picks) {
    const k = p.units || '—'
    const arr = unitGroups.get(k) ?? []
    arr.push(p)
    unitGroups.set(k, arr)
  }
  const unitKeys = Array.from(unitGroups.keys())
  const yIds: Record<string, string> = { [unitKeys[0]]: 'y' }
  if (unitKeys[1]) yIds[unitKeys[1]] = 'y2'

  const datasets: ChartData<'line'>['datasets'] = picks.map((p, idx) => ({
    label: p.name + (p.units ? ` (${p.units})` : ''),
    data: clipOutliers(p.name, seriesCache.get(p.name) ?? [], analysis.filterOutliers) as PointXY[],
    borderColor: COLORS[idx % COLORS.length],
    borderWidth: 1.2,
    pointRadius: 0,
    parsing: false,
    yAxisID: yIds[p.units || '—'] ?? 'y',
  }))
  return { datasets }
})

const chartOpts = computed<ChartOptions<'line'>>(() => {
  const picks = signals.value.filter((s) => selected.has(s.name))
  const unitKeys = Array.from(new Set(picks.map((p) => p.units || '—')))
  const scales: Record<string, unknown> = {
    x: { type: 'linear', title: { display: true, text: 'time (s)' } },
    y: { position: 'left', title: { display: true, text: unitKeys[0] ?? '' } },
  }
  if (unitKeys[1]) {
    scales.y2 = { position: 'right', title: { display: true, text: unitKeys[1] }, grid: { drawOnChartArea: false } }
  }
  return { parsing: false, scales }
})
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
  <div v-else class="h-full grid grid-cols-[280px_1fr] gap-2 min-h-0">
    <!-- Picker -->
    <CyberPanel class="flex flex-col min-h-0">
      <div class="text-silver tracking-[0.2em] text-small mb-2">SIGNALS</div>
      <input
        v-model="search"
        type="search"
        placeholder="filter signals…"
        class="bg-charcoal text-silver border border-slate/40 rounded px-2 py-1 text-small mb-2"
        aria-label="filter signals"
      />
      <div class="flex flex-wrap gap-1 mb-2">
        <button class="preset-btn" @click="applyPreset('speed_rpm')">speed+rpm</button>
        <button class="preset-btn" @click="applyPreset('driver')">driver</button>
        <button class="preset-btn" @click="applyPreset('g')">g</button>
        <button class="preset-btn" @click="applyPreset('imu')">imu</button>
        <button class="preset-btn" @click="applyPreset('oil')">oil</button>
        <button class="preset-btn" @click="clearAll">clear</button>
      </div>
      <div class="text-[10px] text-slate mb-1">{{ selected.size }} selected · {{ signals.length }} available</div>
      <div class="sig-list flex-1 min-h-0 overflow-y-auto">
        <div v-if="!signals.length && !loading" class="text-slate text-small p-2">NO SIGNALS IN THIS SESSION</div>
        <template v-for="[group, list] in grouped" :key="group">
          <div class="group-head">{{ group }} · {{ list.length }}</div>
          <label
            v-for="s in list"
            :key="s.name"
            class="sig-row"
            :class="{ 'sig-checked': selected.has(s.name) }"
          >
            <input
              type="checkbox"
              :checked="selected.has(s.name)"
              @change="(e) => toggle(s.name, (e.target as HTMLInputElement).checked)"
            />
            <span class="sig-name">{{ s.name }}</span>
            <span class="sig-meta">{{ s.units || '' }} · {{ s.n.toLocaleString() }}</span>
          </label>
        </template>
      </div>
    </CyberPanel>
    <!-- Chart -->
    <CyberPanel class="flex flex-col min-h-0">
      <div class="text-silver tracking-[0.2em] text-small mb-1">MULTI-SIGNAL OVERLAY</div>
      <div v-if="!selected.size" class="text-slate text-small p-4">Pick signals from the list to build a chart.</div>
      <div v-else class="flex-1 min-h-0">
        <CyberLineChart :data="chartData" :options="chartOpts" zoom aria-label="Multi signal overlay" />
      </div>
    </CyberPanel>
  </div>
</template>

<style scoped>
.preset-btn {
  background: var(--color-charcoal);
  color: var(--color-silver);
  border: 1px solid rgba(255,255,255,.06);
  font-size: 10px;
  padding: 4px 8px;
  border-radius: 3px;
  cursor: pointer;
  min-height: 44px;
  min-width: 44px;
}
.preset-btn:hover { color: #7cc5ff; border-color: #7cc5ff; }
.sig-list {
  background: rgba(13,13,18,.6);
  border: 1px solid rgba(255,255,255,.04);
  border-radius: 4px;
  padding: 4px;
}
.group-head {
  color: #9aa0b4;
  font-size: 9px;
  text-transform: uppercase;
  padding: 6px 6px 2px;
  letter-spacing: 0.08em;
}
.sig-row {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 6px;
  font-size: 11px;
  border-radius: 3px;
  cursor: pointer;
  color: var(--color-silver);
  min-height: 28px;
}
.sig-row:hover { background: rgba(255,255,255,.04); }
.sig-checked { background: rgba(124,197,255,.12); color: #7cc5ff; }
.sig-name { flex: 1; }
.sig-meta { color: #9aa0b4; font-size: 10px; }
</style>

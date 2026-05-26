<script setup lang="ts">
/**
 * Systems tab: TPMS 2x2 corner grid (latest sample) plus the
 * stock-comparison overlay charts (engine temps, pressures, wheel
 * speeds, GPS-vs-wheel speed). Each comparison renders its own panel
 * only when at least one of its signals has samples in this session.
 */
import { computed, onMounted, reactive, ref, watch } from 'vue'
import type { ChartData, ChartOptions } from 'chart.js'
import CyberPanel from '@/shared/ui/core/CyberPanel.vue'
import CyberLineChart from '@/shared/ui/charts/CyberLineChart.vue'
import { useAnalysisStore } from '@/entities/analysis/model/analysisStore'
import {
  asNum, fetchSignalSeries, latestSignalValue, tallT0,
} from '@/shared/lib/telemetry/queries'
import { clipOutliers, type PointXY } from '@/shared/lib/telemetry/outliers'

interface Preset {
  title: string
  signals: string[]
  unit: string
}

const PRESETS: Preset[] = [
  { title: 'Engine temperatures', signals: ['water_temp_f', 'engine_oil_temp_f', 'oil_filter_temp_f', 'ambient_temp_f', 'logger_temp_f'], unit: '°F' },
  { title: 'Engine pressures', signals: ['oil_press_psi', 'water_press_psi', 'fuel_press_psi', 'brake_press_psi'], unit: 'psi' },
  { title: 'TPMS pressures', signals: ['tpms_press_fl_psi', 'tpms_press_fr_psi', 'tpms_press_rl_psi', 'tpms_press_rr_psi', 'tpms_press_avg_psi'], unit: 'psi' },
  { title: 'TPMS temperatures', signals: ['tpms_temp_fl_f', 'tpms_temp_fr_f', 'tpms_temp_rl_f', 'tpms_temp_rr_f', 'tpms_temp_avg_f'], unit: '°F' },
  { title: 'Wheel speeds', signals: ['wheel_speed_fl_mph', 'wheel_speed_fr_mph', 'wheel_speed_rl_mph', 'wheel_speed_rr_mph', 'wheel_speed_avg_mph'], unit: 'mph' },
  { title: 'GPS · speed sources', signals: ['gps_speed_mph', 'wheel_speed_avg_mph'], unit: 'mph' },
]
const PALETTE = ['#7cc5ff', '#f0c674', '#7ee787', '#f47174', '#c8a2ff', '#9aa0b4', '#ffd86b']

const analysis = useAnalysisStore()

const tpms = reactive<Record<string, number | null>>({})
const seriesByPreset = reactive<Record<string, Record<string, PointXY[]>>>({})
const loading = ref(false)
const err = ref<string | null>(null)

async function load() {
  const sid = analysis.sessionId
  if (!sid) return
  loading.value = true
  err.value = null
  try {
    // TPMS latest values (per corner, four metrics each)
    const corners = ['fl', 'fr', 'rl', 'rr']
    const keys: string[] = []
    for (const c of corners) {
      for (const k of [`tpms_press_${c}_psi`, `tpms_temp_${c}_f`, `tpms_volt_${c}_mv`, `tpms_alm_${c}`]) {
        keys.push(k)
      }
    }
    await Promise.all(keys.map(async (k) => {
      tpms[k] = await latestSignalValue(sid, k)
    }))

    // Comparison series
    const t0 = await tallT0()
    for (const pre of PRESETS) {
      const m: Record<string, PointXY[]> = {}
      await Promise.all(pre.signals.map(async (s) => {
        const arr = await fetchSignalSeries(sid, s, t0, 3000)
        m[s] = arr
      }))
      seriesByPreset[pre.title] = m
    }
  } catch (e) {
    err.value = e instanceof Error ? e.message : String(e)
  } finally {
    loading.value = false
  }
}

onMounted(load)
watch(() => [analysis.sessionId, analysis.selectedLapIndex, analysis.filterOutliers], load)

const hasTpms = computed(() => Object.values(tpms).some((v) => v != null))

const presetCharts = computed(() => {
  const out: Array<{ title: string; unit: string; data: ChartData<'line'>; opts: ChartOptions<'line'> }> = []
  for (const pre of PRESETS) {
    const m = seriesByPreset[pre.title] ?? {}
    const datasets: ChartData<'line'>['datasets'] = []
    pre.signals.forEach((s, idx) => {
      const arr = m[s]
      if (!arr || !arr.length) return
      const isAvg = s.endsWith('_avg_psi') || s.endsWith('_avg_f') || s.endsWith('_avg_mph')
      datasets.push({
        label: s,
        data: clipOutliers(s, arr, analysis.filterOutliers) as PointXY[],
        borderColor: PALETTE[idx % PALETTE.length],
        borderWidth: isAvg ? 2 : 1,
        borderDash: isAvg ? [6, 3] : [],
        pointRadius: 0,
        parsing: false,
      })
    })
    if (!datasets.length) continue
    out.push({
      title: pre.title,
      unit: pre.unit,
      data: { datasets },
      opts: {
        parsing: false,
        scales: {
          x: { type: 'linear', title: { display: true, text: 'time (s)' } },
          y: { title: { display: true, text: pre.unit } },
        },
      },
    })
  }
  return out
})

const cornerView = (c: 'fl' | 'fr' | 'rl' | 'rr') => ({
  name: ({ fl: 'FRONT L', fr: 'FRONT R', rl: 'REAR L', rr: 'REAR R' } as const)[c],
  psi: tpms[`tpms_press_${c}_psi`] ?? null,
  tf:  tpms[`tpms_temp_${c}_f`] ?? null,
  vmv: tpms[`tpms_volt_${c}_mv`] ?? null,
  alm: tpms[`tpms_alm_${c}`] ?? null,
})
const corners = computed(() => (['fl', 'fr', 'rl', 'rr'] as const).map(cornerView))

void asNum
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
  <div v-else class="h-full grid grid-cols-[minmax(300px,1fr)_2fr] gap-2 min-h-0 overflow-hidden">
    <!-- TPMS column -->
    <CyberPanel class="flex flex-col min-h-0">
      <div class="text-silver tracking-[0.2em] text-small mb-2">TPMS · LATEST PER CORNER</div>
      <div v-if="!hasTpms" class="text-slate text-small">NO TPMS SAMPLES IN THIS SESSION</div>
      <div v-else class="grid grid-cols-2 gap-2 flex-1 min-h-0">
        <div v-for="c in corners" :key="c.name" class="corner-cell">
          <div class="label">{{ c.name }}</div>
          <div class="p">{{ c.psi != null ? c.psi.toFixed(1) : '—' }} <span class="unit">psi</span></div>
          <div class="t">{{ c.tf != null ? c.tf.toFixed(1) + ' °F' : '—' }}</div>
          <div class="v">batt {{ c.vmv != null ? c.vmv + ' mV' : '—' }} · alm 0x{{ (c.alm ?? 0).toString(16).padStart(4, '0') }}</div>
        </div>
      </div>
    </CyberPanel>
    <!-- Comparison panels (scrolls if more than fit) -->
    <div class="flex flex-col gap-2 overflow-y-auto min-h-0 pr-1">
      <CyberPanel
        v-for="pc in presetCharts"
        :key="pc.title"
        class="flex flex-col"
        style="height: 220px; min-height: 220px;"
      >
        <div class="text-silver tracking-[0.2em] text-small mb-1">{{ pc.title.toUpperCase() }}</div>
        <div class="flex-1 min-h-0"><CyberLineChart :data="pc.data" :options="pc.opts" zoom :aria-label="pc.title" /></div>
      </CyberPanel>
      <CyberPanel v-if="!presetCharts.length" class="text-center" :animate="false">
        <div class="text-slate text-small">NO STOCK COMPARISON SIGNALS IN THIS SESSION</div>
      </CyberPanel>
    </div>
  </div>
</template>

<style scoped>
.corner-cell {
  background: rgba(29,29,39,.8);
  border: 1px solid rgba(255,255,255,.04);
  border-radius: 4px;
  padding: 10px;
  text-align: center;
  min-height: 80px;
  display: flex;
  flex-direction: column;
  justify-content: center;
}
.label { font-size: 10px; color: #9aa0b4; letter-spacing: 0.08em; }
.p { font-size: clamp(16px, 2.4vmin, 24px); font-weight: 600; color: #7cc5ff; margin: 4px 0; font-variant-numeric: tabular-nums; }
.unit { font-size: 10px; color: #9aa0b4; font-weight: 400; }
.t { font-size: 12px; color: #9aa0b4; }
.v { font-size: 10px; color: #9aa0b4; margin-top: 2px; }
</style>

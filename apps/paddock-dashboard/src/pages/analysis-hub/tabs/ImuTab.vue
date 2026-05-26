<script setup lang="ts">
/**
 * IMU tab: two stacked charts — accelerometers and gyroscopes — both
 * pulled from the 50 Hz tall store.
 */
import { computed, onMounted, ref, watch } from 'vue'
import type { ChartData, ChartOptions } from 'chart.js'
import CyberPanel from '@/shared/ui/core/CyberPanel.vue'
import CyberLineChart from '@/shared/ui/charts/CyberLineChart.vue'
import { useAnalysisStore } from '@/entities/analysis/model/analysisStore'
import { fetchSignalSeries, tallT0 } from '@/shared/lib/telemetry/queries'
import { clipOutliers, type PointXY } from '@/shared/lib/telemetry/outliers'

const ACCEL = ['inline_accel_g', 'lateral_accel_g', 'vertical_accel_g'] as const
const GYRO  = ['roll_rate_degs', 'pitch_rate_degs', 'yaw_rate_degs'] as const
const COLORS = ['#7cc5ff', '#f0c674', '#7ee787']

const analysis = useAnalysisStore()
const accelSeries = ref<Record<string, PointXY[]>>({})
const gyroSeries  = ref<Record<string, PointXY[]>>({})
const err = ref<string | null>(null)
const loading = ref(false)

async function load() {
  const sid = analysis.sessionId
  if (!sid) return
  loading.value = true
  err.value = null
  try {
    const t0 = await tallT0()
    const all = [...ACCEL, ...GYRO]
    const results = await Promise.all(all.map((n) => fetchSignalSeries(sid, n, t0, 3000)))
    const aMap: Record<string, PointXY[]> = {}
    const gMap: Record<string, PointXY[]> = {}
    ACCEL.forEach((n, i) => { aMap[n] = results[i] })
    GYRO.forEach((n, i) => { gMap[n] = results[ACCEL.length + i] })
    accelSeries.value = aMap
    gyroSeries.value = gMap
  } catch (e) {
    err.value = e instanceof Error ? e.message : String(e)
  } finally {
    loading.value = false
  }
}

onMounted(load)
watch(() => [analysis.sessionId, analysis.selectedLapIndex, analysis.filterOutliers], load)

const accelData = computed<ChartData<'line'>>(() => ({
  datasets: ACCEL.map((n, i) => ({
    label: n,
    data: clipOutliers(n, accelSeries.value[n] ?? [], analysis.filterOutliers) as PointXY[],
    borderColor: COLORS[i],
    borderWidth: 1,
    pointRadius: 0,
    parsing: false,
  })),
}))

const gyroData = computed<ChartData<'line'>>(() => ({
  datasets: GYRO.map((n, i) => ({
    label: n,
    data: clipOutliers(n, gyroSeries.value[n] ?? [], analysis.filterOutliers) as PointXY[],
    borderColor: COLORS[i],
    borderWidth: 1,
    pointRadius: 0,
    parsing: false,
  })),
}))

const accelOpts: ChartOptions<'line'> = {
  parsing: false,
  scales: {
    x: { type: 'linear', title: { display: true, text: 'time (s)' } },
    y: { title: { display: true, text: 'g' } },
  },
}
const gyroOpts: ChartOptions<'line'> = {
  parsing: false,
  scales: {
    x: { type: 'linear', title: { display: true, text: 'time (s)' } },
    y: { title: { display: true, text: '°/s' } },
  },
}

const hasAccel = computed(() => Object.values(accelSeries.value).some((a) => a.length))
const hasGyro = computed(() => Object.values(gyroSeries.value).some((a) => a.length))
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
  <div v-else class="h-full grid grid-rows-2 gap-2 min-h-0">
    <CyberPanel class="flex flex-col min-h-0">
      <div class="text-silver tracking-[0.2em] text-small mb-1">IMU · ACCELEROMETERS (50 Hz)</div>
      <div v-if="!hasAccel && !loading" class="text-slate text-small">NO ACCELEROMETER SAMPLES IN THIS SESSION</div>
      <div v-else class="flex-1 min-h-0"><CyberLineChart :data="accelData" :options="accelOpts" zoom aria-label="IMU accelerometers" /></div>
    </CyberPanel>
    <CyberPanel class="flex flex-col min-h-0">
      <div class="text-silver tracking-[0.2em] text-small mb-1">IMU · GYROSCOPES (50 Hz)</div>
      <div v-if="!hasGyro && !loading" class="text-slate text-small">NO GYROSCOPE SAMPLES IN THIS SESSION</div>
      <div v-else class="flex-1 min-h-0"><CyberLineChart :data="gyroData" :options="gyroOpts" zoom aria-label="IMU gyroscopes" /></div>
    </CyberPanel>
  </div>
</template>

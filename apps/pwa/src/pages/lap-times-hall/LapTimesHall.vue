<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAudioStore } from '@/features/audio-playback/model/audioStore'
import { useKeyboard } from '@/shared/lib/useKeyboard'
import PageShell from '@/shared/ui/PageShell.vue'
import Frame from '@/shared/ui/core/Frame.vue'
import CyberSplitView from '@/shared/ui/core/CyberSplitView.vue'
import ErrorBoundary from '@/shared/ui/ErrorBoundary.vue'
import CyberSkeleton from '@/shared/ui/core/CyberSkeleton.vue'
import { useLapTimeStore } from '@/entities/lap-time/model/lapTimeStore'
import { useAnalysisStore } from '@/entities/analysis/model/analysisStore'
import { formatLapTime } from '@/shared/lib/lap'

const router = useRouter()
const route = useRoute()
const audio = useAudioStore()
const store = useLapTimeStore()
const analysis = useAnalysisStore()

onMounted(() => {
  store.fetchLapTimes()
  // Best-effort: server-computed ideal lap + distribution. Both endpoints
  // can 404 when the session lacks enough laps; UI degrades to honest
  // empty values ("—") in that case — no synthesis.
  store.fetchIdealLap()
  store.fetchDistribution()
})

// Subtitle = real active session id, not a hardcoded date. Prefer the
// analysis store (set by the user's selected session), then the route
// param, then a neutral placeholder.
const subtitle = computed(() => {
  const sid = analysis.sessionId ?? (route.params.sid as string | undefined) ?? null
  return sid ? `session ${sid} ◀ ▶` : 'no active session'
})

// Distribution: real server values only — no fake fallback ranges.
const distStats = computed(() => {
  const d = store.distribution
  if (!d) return null
  return {
    min: d.min_s,
    q1: d.q1_s,
    median: d.median_s,
    q3: d.q3_s,
    max: d.max_s,
    outliers: d.outliers.map(o => o.lap_time_s),
    stddev: `${d.stddev_s.toFixed(1)}s`,
  }
})

const distRange = computed(() => {
  const d = store.distribution
  if (!d) return null
  const pad = Math.max(0.5, (d.max_s - d.min_s) * 0.1)
  return { lo: d.min_s - pad, hi: d.max_s + pad }
})

const cursorIndex = ref(0)
const visibleRows = 5
const scrollOffset = computed(() => {
  if (cursorIndex.value < 2) return 0
  if (cursorIndex.value > store.laps.length - 3) return Math.max(0, store.laps.length - visibleRows)
  return cursorIndex.value - 2
})

let pbPlayed = false

useKeyboard((e: KeyboardEvent) => {
  if (store.isLoading || store.laps.length === 0) return

  if (e.key === 'ArrowDown') {
    cursorIndex.value = Math.min(cursorIndex.value + 1, store.laps.length - 1)
    const lap = store.laps[cursorIndex.value]
    if (lap?.is_best && !pbPlayed) {
      audio.playSfx('pb_unlock')
      pbPlayed = true
    } else {
      audio.playSfx('cursor_move')
    }
  } else if (e.key === 'ArrowUp') {
    cursorIndex.value = Math.max(cursorIndex.value - 1, 0)
    const lap = store.laps[cursorIndex.value]
    if (lap?.is_best && !pbPlayed) {
      audio.playSfx('pb_unlock')
      pbPlayed = true
    } else {
      audio.playSfx('cursor_move')
    }
  } else if (e.key === 'Enter' || e.key === 'a') {
    audio.playSfx('cursor_select')
  } else if (e.key === 'c' || e.key === 'C') {
    audio.playSfx('cursor_select')
    router.push('/analysis/compare')
  } else if (e.key === 'Escape' || e.key === 'Backspace' || e.key === 'b') {
    audio.playSfx('cancel')
    router.push('/garage/analysis')
  }
})

// Headline computed values — sourced from the real LapTime shape returned
// by /session/<sid>/lap_time_table (numbers, not pre-formatted strings).
const bestLap = computed(() => formatLapTime(store.bestLapS, 3))

// Ideal lap: server-computed sum-of-best-sectors. If the endpoint 404s
// (not enough sector data yet), show "—" — no client-side synthesis.
const idealLap = computed(() => {
  if (store.ideal) return formatLapTime(store.ideal.ideal_lap_s, 3)
  return formatLapTime(null, 3)
})

const gain = computed(() => {
  if (store.ideal) {
    // Backend reports `gain_potential_s` = best_actual - ideal. Negative
    // when the driver is *at* ideal (rare).
    const g = store.ideal.gain_potential_s
    return `${g >= 0 ? '-' : '+'}${Math.abs(g).toFixed(3)}s`
  }
  return '--'
})

// Per-lap delta against best lap — uses the server-supplied
// `delta_to_best_s` (number, seconds, signed).
const formatDelta = (deltaS: number | null | undefined): string => {
  if (deltaS == null || !Number.isFinite(deltaS)) return '--'
  if (Math.abs(deltaS) < 1e-3) return '0.000'
  const sign = deltaS > 0 ? '+' : '-'
  return `${sign}${Math.abs(deltaS).toFixed(3)}`
}

// Box-plot scale uses the dynamic range from the distribution endpoint.
const distScale = (val: number) => {
  const r = distRange.value
  if (!r) return '0%'
  const { lo, hi } = r
  if (hi <= lo) return '0%'
  const pct = (val - lo) / (hi - lo)
  return `${Math.min(100, Math.max(0, pct * 100))}%`
}
</script>

<template>
  <PageShell title="LAP TIMES HALL" :subtitle="subtitle" :hints="['A · REPLAY', 'C · COMPARE', '◀ ▶ SESSION', 'B · BACK']" bg="cool">
    <!-- Headline -->
    <Frame variant="card" padding="8px" class="flex justify-around items-center mb-4">
      <div class="flex flex-col items-center">
        <span class="text-small text-slate tracking-widest">BEST LAP</span>
        <span class="text-title font-bold text-ui-good drop-shadow-[1px_1px_0_#000]">{{ bestLap }}</span>
      </div>
      <div class="flex flex-col items-center">
        <span class="text-small text-slate tracking-widest">IDEAL LAP</span>
        <span class="text-title font-bold text-white">{{ idealLap }}</span>
      </div>
      <div class="flex flex-col items-center">
        <span class="text-small text-slate tracking-widest">GAIN</span>
        <span class="text-title font-bold text-ui-good drop-shadow-[1px_1px_0_#000]">{{ gain }}</span>
      </div>
    </Frame>

    <CyberSplitView split="60-40" gap="md" class="flex-grow min-h-0">
      <template #left>
        <!-- Lap Table -->
        <Frame variant="default" padding="8px" class="h-full flex flex-col text-body overflow-hidden">
          <ErrorBoundary>
            <div v-if="store.isLoading" class="flex-grow flex flex-col items-center justify-center p-4">
              <CyberSkeleton variant="row" :count="5" />
            </div>

            <div v-else-if="store.laps.length === 0" class="flex-grow flex items-center justify-center text-small text-slate tracking-widest uppercase">
              — NO LAPS FOR THIS SESSION —
            </div>

            <div v-else class="flex flex-col h-full overflow-hidden">
              <div class="flex text-small text-slate border-b border-slate px-2 pb-1 mb-2 tracking-widest uppercase">
                <span class="flex-1 text-center">#</span>
                <span class="flex-[3] text-center">TOTAL</span>
                <span class="flex-[2] text-center">S1</span>
                <span class="flex-[2] text-center">S2</span>
                <span class="flex-[2] text-center">S3</span>
                <span class="flex-[2] text-center">Δ BEST</span>
              </div>
              <div class="flex-grow relative overflow-hidden">
                <div
                  class="absolute top-0 left-0 right-0 flex flex-col transition-transform duration-100"
                  :style="{ transform: `translateY(-${scrollOffset * 24}px)` }"
                >
                  <div
                    v-for="(lap, i) in store.laps" :key="lap.lap_number"
                    class="flex items-center px-2 h-6 transition-colors relative cursor-pointer"
                    :class="[
                      cursorIndex === i ? 'bg-charcoal text-white' : 'text-silver',
                      lap.is_best ? 'text-ui-good' : ''
                    ]"
                    @click="cursorIndex = i; audio.playSfx('cursor_move')"
                  >
                    <span class="flex-1 text-center relative font-bold">
                      <span v-if="cursorIndex === i" class="absolute -left-2 text-ui-warn">▶</span>
                      {{ lap.lap_number }}
                    </span>
                    <span class="flex-[3] text-center font-bold">{{ formatLapTime(lap.lap_time_s, 3) }}</span>
                    <span class="flex-[2] text-center">{{ lap.sectors?.[0] ? lap.sectors[0].time_s.toFixed(3) : '—' }}</span>
                    <span class="flex-[2] text-center">{{ lap.sectors?.[1] ? lap.sectors[1].time_s.toFixed(3) : '—' }}</span>
                    <span class="flex-[2] text-center">{{ lap.sectors?.[2] ? lap.sectors[2].time_s.toFixed(3) : '—' }}</span>
                    <span class="flex-[2] text-center font-bold" :class="lap.delta_to_best_s != null && lap.delta_to_best_s < 0 ? 'text-ui-good' : lap.delta_to_best_s != null && lap.delta_to_best_s > 0 ? 'text-ui-bad' : ''">{{ formatDelta(lap.delta_to_best_s) }}</span>
                    <span v-if="lap.is_best" class="absolute right-2 text-ui-good drop-shadow-[1px_1px_0_#000]">★</span>
                  </div>
                </div>
              </div>
            </div>
          </ErrorBoundary>
        </Frame>
      </template>

      <template #right>
        <!-- Distribution Box-Plot & Coach -->
        <div class="h-full flex flex-col gap-4">
          <Frame variant="default" padding="12px" class="flex flex-col text-body relative min-h-[120px]">
            <div class="text-small text-slate tracking-widest mb-4">DISTRIBUTION</div>

            <div v-if="!distStats" class="flex-grow flex items-center justify-center text-small text-slate tracking-widest uppercase">
              DATA UNAVAILABLE
            </div>

            <template v-else>
              <div class="relative w-full h-8 mt-2">
                <!-- Whisker line -->
                <div class="absolute h-[1px] bg-slate top-4"
                     :style="{ left: distScale(distStats.min), right: `calc(100% - ${distScale(distStats.max)})` }"></div>
                <!-- Whisker caps -->
                <div class="absolute w-[2px] h-4 bg-slate top-2" :style="{ left: distScale(distStats.min) }"></div>
                <div class="absolute w-[2px] h-4 bg-slate top-2" :style="{ left: distScale(distStats.max) }"></div>

                <!-- Box (IQR) -->
                <div class="absolute h-6 border-2 border-silver bg-ink top-1"
                     :style="{
                       left: distScale(distStats.q1),
                       width: `calc(${distScale(distStats.q3)} - ${distScale(distStats.q1)})`
                     }"></div>
                <!-- Median line -->
                <div class="absolute w-1 h-6 bg-ui-warn top-1" :style="{ left: distScale(distStats.median) }"></div>

                <!-- Outliers -->
                <div v-for="out in distStats.outliers" :key="out"
                     class="absolute w-2 h-2 rounded-full border-2 border-slate top-3 -ml-1"
                     :style="{ left: distScale(out) }"></div>

                <!-- Cursor Marker -->
                <div class="absolute text-ui-good font-bold text-title-sm top-8 -ml-2 drop-shadow-[1px_1px_0_#000]"
                     v-if="store.laps.length > 0 && store.laps[cursorIndex]?.lap_time_s"
                     :style="{ left: distScale(store.laps[cursorIndex].lap_time_s) }">
                  ▲
                </div>
              </div>

              <div class="mt-auto pt-4 text-small text-slate flex justify-between tracking-widest">
                <span>
                  MEDIAN {{ Math.floor(distStats.median / 60) }}:{{ (distStats.median % 60).toFixed(1) }}
                </span>
                <span>σ={{ distStats.stddev }}</span>
              </div>
            </template>
          </Frame>

          <!--
            No per-lap commentary endpoint exists yet. Honest placeholder
            instead of the previous canned strings.
          -->
          <div class="flex-grow flex flex-col justify-end">
            <div class="text-small text-slate tracking-widest uppercase px-3 py-2 border-t border-slate/30">
              — NO PER-LAP COMMENTARY —
            </div>
          </div>
        </div>
      </template>
    </CyberSplitView>
  </PageShell>
</template>

<script setup lang="ts">
/**
 * CornerScorecard — per-corner detail card surfaced from TrackWalk and
 * CornerMastery. Renders speeds + grade + coach tip with HONEST delta
 * indicators: only `apex` has a real delta source on the bridge today
 * (`/session/<sid>/corners` returns `gold_delta_kmh` for apex). Entry,
 * exit, and time deltas are nullable — when missing we render "—" with
 * a neutral grey, never a misleading ▲/▼.
 */
import CyberGlassPanel from './CyberGlassPanel.vue'

interface CornerDeltas {
  /** Apex-speed delta vs gold standard, km/h. Positive = faster than gold. */
  apex: number | null
  /** Entry-speed delta vs gold. Currently always null — bridge does not expose. */
  entry: number | null
  /** Exit-speed delta vs gold. Currently always null — bridge does not expose. */
  exit: number | null
  /** Corner-time delta in seconds. Currently always null — bridge does not expose. */
  time: number | null
}

interface Corner {
  id: string
  name: string
  tip: string
  /** "A" / "B" / ... / "F" / "ungraded" / "--" when no session data yet. */
  grade: string
  /** Best entry speed in km/h, or null when no session data. */
  entry?: number | null
  apex?: number | null
  exit?: number | null
  time?: number | null
  deltas: CornerDeltas
  statsSource?: 'session' | 'none'
}

defineProps<{
  corner: Corner
  coachId: string
}>()

const getGradeColor = (grade: string) => {
  if (grade.startsWith('A') || grade.startsWith('B')) return 'text-ui-good drop-shadow-[1px_1px_0_#000]'
  if (grade.startsWith('C')) return 'text-ui-warn'
  if (grade === 'D' || grade === 'F') return 'text-ui-bad font-bold drop-shadow-[1px_1px_0_#000]'
  return 'text-silver'
}

/**
 * Map a delta number → arrow + colour class. `null` (no comparison
 * available) renders "—" in grey. For speeds: positive (faster) is good;
 * for `time` the sign convention is inverted (positive = slower, bad).
 */
function deltaDisplay(d: number | null, kind: 'speed' | 'time' = 'speed'): { text: string; cls: string } {
  if (d == null) return { text: '—', cls: 'text-slate/50' }
  if (Math.abs(d) < 0.05) return { text: '0', cls: 'text-silver' }
  const better = kind === 'speed' ? d > 0 : d < 0
  const arrow = d > 0 ? '▲' : '▼'
  return {
    text: `${arrow}${Math.abs(d).toFixed(kind === 'time' ? 2 : 1)}`,
    cls: better ? 'text-ui-good' : 'text-ui-bad',
  }
}

function statsHeading(corner: Corner): string {
  if (corner.statsSource === 'session') return `YOUR BEST AT ${corner.id}`
  return `NO RECORDED LAP AT ${corner.id}`
}
</script>

<template>
  <div class="absolute inset-x-2 bottom-[6vh] top-[6vh] z-30 flex flex-col pointer-events-none">
    <CyberGlassPanel class="flex-grow flex flex-col shadow-2xl p-2 border-slate pointer-events-auto">
      <div class="flex justify-between border-b border-slate pb-1 mb-2 items-center">
        <span class="text-white font-bold text-[clamp(14px,3vw,24px)]">{{ corner.id }} · "{{ corner.name }}"</span>
        <span class="text-title font-bold" :class="getGradeColor(corner.grade)">Grade: {{ corner.grade }}</span>
      </div>

      <div class="flex flex-col gap-2 flex-grow text-body">
        <CyberGlassPanel class="p-2 border-slate">
          <span class="text-slate text-small font-bold tracking-wider">COACH SAYS</span>
          <div class="mt-1 flex gap-2">
            <span class="text-ui-good font-bold text-body shrink-0">{{ coachId.toUpperCase() }}:</span>
            <div class="text-silver italic">
              "{{ corner.tip }}"
            </div>
          </div>
        </CyberGlassPanel>

        <div class="text-slate mb-1 mt-2 tracking-wider text-small font-bold">{{ statsHeading(corner) }}</div>
        <CyberGlassPanel class="flex flex-col gap-2 p-3 border-slate">
          <!-- ENTRY -->
          <div class="flex justify-between items-center">
            <span class="w-[clamp(40px,10vw,60px)] text-silver text-small">ENTRY</span>
            <span class="font-bold text-[clamp(14px,3vw,20px)]">
              {{ corner.entry != null ? `${corner.entry.toFixed(1)} km/h` : '—' }}
            </span>
            <span class="w-[clamp(28px,6vw,52px)] text-right font-bold text-small"
                  :class="deltaDisplay(corner.deltas.entry, 'speed').cls">
              {{ deltaDisplay(corner.deltas.entry, 'speed').text }}
            </span>
          </div>
          <!-- APEX (the one with a real gold delta) -->
          <div class="flex justify-between items-center">
            <span class="w-[clamp(40px,10vw,60px)] text-silver text-small">APEX</span>
            <span class="font-bold text-[clamp(14px,3vw,20px)]">
              {{ corner.apex != null ? `${corner.apex.toFixed(1)} km/h` : '—' }}
            </span>
            <span class="w-[clamp(28px,6vw,52px)] text-right font-bold text-small"
                  :class="deltaDisplay(corner.deltas.apex, 'speed').cls">
              {{ deltaDisplay(corner.deltas.apex, 'speed').text }}
            </span>
          </div>
          <!-- EXIT -->
          <div class="flex justify-between items-center">
            <span class="w-[clamp(40px,10vw,60px)] text-silver text-small">EXIT</span>
            <span class="font-bold text-[clamp(14px,3vw,20px)]">
              {{ corner.exit != null ? `${corner.exit.toFixed(1)} km/h` : '—' }}
            </span>
            <span class="w-[clamp(28px,6vw,52px)] text-right font-bold text-small"
                  :class="deltaDisplay(corner.deltas.exit, 'speed').cls">
              {{ deltaDisplay(corner.deltas.exit, 'speed').text }}
            </span>
          </div>
          <div class="w-full h-[1px] bg-slate/30 my-1"></div>
          <!-- TIME -->
          <div class="flex justify-between items-center text-white">
            <span class="w-[clamp(40px,10vw,60px)] text-silver text-small">TIME</span>
            <span class="font-bold text-[clamp(14px,3vw,20px)]">
              {{ corner.time != null ? `${corner.time.toFixed(2)} s` : '—' }}
            </span>
            <span class="w-[clamp(28px,6vw,52px)] text-right font-bold text-small"
                  :class="deltaDisplay(corner.deltas.time, 'time').cls">
              {{ deltaDisplay(corner.deltas.time, 'time').text }}
            </span>
          </div>
          <!-- Footnote: all four deltas are vs the gold-standard lap. -->
          <div v-if="corner.deltas.apex != null || corner.deltas.entry != null || corner.deltas.exit != null || corner.deltas.time != null" class="text-[10px] text-slate/60 mt-1 italic">
            All deltas vs gold-standard lap (sonoma_gold.json). Speed: ▲ faster, ▼ slower. Time: ▼ faster.
          </div>
          <div v-else class="text-[10px] text-slate/60 mt-1 italic">
            No completed backend lap has populated this corner yet. Start and finish a real session to unlock speeds, timing, and grades.
          </div>
        </CyberGlassPanel>
      </div>
    </CyberGlassPanel>
  </div>
</template>

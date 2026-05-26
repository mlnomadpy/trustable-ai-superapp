<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useKeyboard } from '@/shared/lib/useKeyboard'
import { useRouter } from 'vue-router'
import { useAudioStore } from '@/features/audio-playback/model/audioStore'
import { useSaveStore } from '@/entities/save/model/saveStore'
import { useSessionStore } from '@/entities/session/model/sessionStore'
import { useLapTimeStore } from '@/entities/lap-time/model/lapTimeStore'
import { useCoachStore } from '@/entities/coach/model/coachStore'
import { useSequence } from '@/shared/lib/useSequence'
import { formatLapTime } from '@/shared/lib/lap'
import { bridge } from '@/shared/api/bridge'
import PageShell from '@/shared/ui/PageShell.vue'
import Frame from '@/shared/ui/core/Frame.vue'
import CoachFloat from '@/shared/ui/CoachFloat.vue'
import CyberMetricRow from '@/shared/ui/core/CyberMetricRow.vue'

const router = useRouter()
const audio = useAudioStore()
const save = useSaveStore()
const session = useSessionStore()
const lapTime = useLapTimeStore()
const coach = useCoachStore()

// Real score / grade from /session/<sid>/scorecard. weighted_total_pct
// (0–100) is what the backend grades on, and session_grade is the
// authoritative S/A/B/C/D letter. No client-side synthesis from
// lapCount * 500 + sigma + throttle — that was inventing numbers.
interface ScorecardResponse {
  session_id: string
  session_grade: string
  weighted_total_pct: number
  summary?: string
  best_lap_s?: number | null
  n_laps?: number
}
const scorecard = ref<ScorecardResponse | null>(null)
const scorecardError = ref<string | null>(null)

const displayedScore = ref(0)
const { phase, addStep, addCustomInterval, skip } = useSequence(99)

// Stage Clear sits between the live HUD and the analytics screens — we
// use the HUD-style single-decimal precision so the numbers match what
// the driver just saw on the HUD, not the longer 3-decimal analytics format.
const bestLapFormatted = computed(() => formatLapTime(lapTime.bestLapS, 1))

const idealLapSeconds = computed<number | null>(() => {
  if (lapTime.laps.length < 2) return null
  const sectorCount = lapTime.laps[0]?.sectors?.length ?? 0
  if (sectorCount === 0) return lapTime.bestLapS
  let idealTotal = 0
  for (let s = 0; s < sectorCount; s++) {
    const bestSector = Math.min(...lapTime.laps.map(l => l.sectors?.[s]?.time_s ?? Infinity))
    if (bestSector === Infinity) return null
    idealTotal += bestSector
  }
  return idealTotal
})

const idealLapFormatted = computed(() => formatLapTime(idealLapSeconds.value, 1))

const idealGain = computed(() => {
  const ideal = idealLapSeconds.value
  if (!lapTime.bestLapS || ideal == null) return '--'
  const diff = lapTime.bestLapS - ideal
  return diff > 0 ? `${diff.toFixed(1)}s gain` : 'at ideal'
})

const consistencyInfo = computed(() => {
  const times = lapTime.laps.map(l => l.lap_time_s).filter(t => t > 0)
  if (times.length < 2) return { stars: '★☆☆☆☆', sigma: '?' }
  const mean = times.reduce((a, b) => a + b, 0) / times.length
  const variance = times.reduce((a, t) => a + (t - mean) ** 2, 0) / times.length
  const sigma = Math.sqrt(variance)
  const rating = sigma < 0.5 ? 5 : sigma < 1 ? 4 : sigma < 2 ? 3 : sigma < 4 ? 2 : 1
  const stars = '★'.repeat(rating) + '☆'.repeat(5 - rating)
  return { stars, sigma: `σ=${sigma.toFixed(1)}s` }
})

const pedalStats = ref<{ throttle_pct: number; brake_pct: number; coast_pct: number } | null>(null)

interface Highlight {
  title: string
  category: string
  severity: 'high' | 'medium' | 'positive' | 'engineering' | string
  lap: number
  distance_m: number
  timestamp_s: number
  video_in_s: number
  video_out_s: number
  narrative_seed: string
}
const highlights = ref<Highlight[]>([])

// Highlights endpoint returns the post-debrief "best moments" reel. We
// surface the top 3 — preferring positive ones — to celebrate the session
// before the driver leaves the screen. Falls back silently if /debrief
// wasn't run for this session (404 from /session/<sid>/highlights).
const topHighlights = computed<Highlight[]>(() => {
  const ranked = [...highlights.value].sort((a, b) => {
    const rank: Record<string, number> = { positive: 0, high: 1, medium: 2, engineering: 3 }
    return (rank[a.severity] ?? 9) - (rank[b.severity] ?? 9)
  })
  return ranked.slice(0, 3)
})

function highlightAccentClass(h: Highlight): string {
  if (h.severity === 'positive') return 'border-ui-good text-ui-good'
  if (h.severity === 'high') return 'border-ui-bad text-ui-bad'
  if (h.severity === 'medium') return 'border-ui-warn text-ui-warn'
  return 'border-slate text-silver'
}

// "What nearly went wrong" — backed by /session/<sid>/incidents (the
// flight-recorder output). Each row is a single over-limit moment with
// distance, speed, combo G, and a human reason. Top 3 shown by combo G.
interface Incident {
  timestamp: number
  distance_m: number
  speed_kmh: number
  combo_g: number
  reason: string
  frame_idx: number
}
const incidents = ref<Incident[]>([])
const topIncidents = computed<Incident[]>(() =>
  [...incidents.value].sort((a, b) => b.combo_g - a.combo_g).slice(0, 3),
)

const metrics = computed(() => {
  const bestPb = session.detail?.best_lap_s
  const pbDelta = bestPb && lapTime.bestLapS
    ? `${(lapTime.bestLapS - bestPb) < 0 ? '' : '+'}${(lapTime.bestLapS - bestPb).toFixed(1)}s`
    : '--'
  const pbClass = bestPb && lapTime.bestLapS && lapTime.bestLapS <= bestPb
    ? 'text-ui-good' : 'text-silver'

  return [
    { label: 'BEST LAP', val: bestLapFormatted.value, sub: `${pbDelta} PB`, subClass: pbClass },
    { label: 'IDEAL LAP', val: idealLapFormatted.value, sub: idealGain.value, subClass: 'text-silver' },
    { label: 'CONSISTENCY', val: consistencyInfo.value.stars, sub: consistencyInfo.value.sigma, subClass: 'text-silver' },
    { label: 'THROTTLE', val: pedalStats.value ? `${pedalStats.value.throttle_pct.toFixed(0)}%` : '--%', sub: 'on-throttle', subClass: 'text-ui-good' },
    { label: 'COAST TIME', val: pedalStats.value ? `${pedalStats.value.coast_pct.toFixed(0)}%` : '--%', sub: pedalStats.value && pedalStats.value.coast_pct < 15 ? 'GOOD' : 'work on it', subClass: pedalStats.value && pedalStats.value.coast_pct < 15 ? 'text-ui-good' : 'text-ui-bad' },
  ]
})

// Score = weighted_total_pct from the bridge scorecard (0–100 range, so
// we keep it as an int percentage rather than a synthetic four-digit
// figure). When the scorecard is missing we render null and the UI
// shows "SCORE UNAVAILABLE" instead of a fake number.
const finalScore = computed<number | null>(() => {
  if (!scorecard.value) return null
  const pct = scorecard.value.weighted_total_pct
  if (typeof pct !== 'number' || !Number.isFinite(pct)) return null
  return Math.round(pct)
})

const grade = computed<string | null>(() => scorecard.value?.session_grade ?? null)
const scoreAvailable = computed(() => finalScore.value != null && grade.value != null)

const goals = computed(() => {
  const g: { desc: string; res: string; ok: boolean }[] = []
  const count = lapTime.laps.length
  g.push({ desc: `COMPLETE ${count >= 5 ? 5 : count + 1}+ LAPS`, res: `got ${count}`, ok: count >= 5 })
  const best = lapTime.bestLapS
  if (best) {
    const target = Math.ceil(best / 10) * 10 
    g.push({ desc: `BREAK ${Math.floor(target / 60)}:${String(target % 60).padStart(2, '0')}`, res: `got ${bestLapFormatted.value}`, ok: best < target })
  }
  if (pedalStats.value) {
    g.push({ desc: 'COAST UNDER 15%', res: `${pedalStats.value.coast_pct.toFixed(0)}%`, ok: pedalStats.value.coast_pct < 15 })
  }
  return g
})

// No per-session "medals earned" endpoint exists on the bridge. Until one
// ships we leave this empty rather than synthesizing — the medals strip
// below is gated on `medals.length > 0` so it simply does not render.
const medals = computed<string[]>(() => [])

useKeyboard((e: KeyboardEvent) => {
  if (e.key === 'a' || e.key === 'Enter') {
    if (phase.value < 13) {
      skip(() => { displayedScore.value = finalScore.value ?? 0 })
    } else {
      audio.playSfx('cursor_select')
      router.push('/garage')
    }
  } else if (e.key === 'b' || e.key === 'Escape' || e.key === 'Backspace') {
    if (phase.value < 13) {
      skip(() => { displayedScore.value = finalScore.value ?? 0 })
    } else {
      audio.playSfx('cancel')
      router.push('/garage')
    }
  }
})

onMounted(async () => {
  audio.playMusic('garage_loop')
  const sid = session.activeSessionId ?? session.sessions[0]?.session_id
  if (sid) {
    await lapTime.fetchLapTimes(sid)
    // Real scorecard from the bridge — drives the SCORE + GRADE tiles.
    try {
      scorecard.value = await bridge.get<ScorecardResponse>(`/session/${sid}/scorecard`)
    } catch (e: any) {
      scorecardError.value = e?.message ?? String(e)
    }
    // Real coach line from /coach/debrief — replaces the previous hardcoded
    // "Outstanding performance" string. Driver id is optional on the
    // request; bridge picks it up from the session.
    coach.fetchDebrief({
      sessionId: sid,
      driverId: save.activeSlot?.driverName,
    })
    try {
      const pedal = await bridge.get<any>(`/session/${sid}/pedal_behavior`)
      if (pedal?.states) {
        pedalStats.value = {
          throttle_pct: pedal.states.throttle_only?.pct ?? 0,
          brake_pct: pedal.states.brake_only?.pct ?? 0,
          coast_pct: pedal.states.coast?.pct ?? 0,
        }
      }
    } catch { }
    // Best-moments reel — populated by /coach/debrief upstream. 404 means
    // the debrief hasn't run yet for this session; we degrade gracefully.
    try {
      const hl = await bridge.get<{ highlights: Highlight[] }>(`/session/${sid}/highlights`)
      highlights.value = Array.isArray(hl?.highlights) ? hl.highlights : []
    } catch { /* highlights are best-effort; ignore */ }

    // Incidents — over-limit / off-line moments from the flight recorder.
    // Same upstream dependency as highlights (analysis bundle), same 404
    // behaviour. Populates the "what nearly went wrong" panel.
    try {
      const inc = await bridge.get<{ incidents: Incident[] }>(`/session/${sid}/incidents`)
      incidents.value = Array.isArray(inc?.incidents) ? inc.incidents : []
    } catch { /* incidents best-effort; ignore */ }
  }

  addStep({ phase: 1, timeMs: 200 })
  addStep({ phase: 2, timeMs: 600 })
  addStep({
    phase: 2, 
    timeMs: 800,
    callback: () => {
      // If no real scorecard arrived, skip the score-counter animation
      // entirely. The template renders "SCORE UNAVAILABLE" in that case.
      const target = finalScore.value
      if (target == null) return
      let current = 0
      const steps = 24
      const stepAmt = target / steps
      let stepCount = 0
      addCustomInterval(1200 / steps, () => {
        current += stepAmt
        displayedScore.value = Math.min(Math.round(current), target)
        audio.playSfx('score_tick')
        stepCount++
        if (stepCount >= steps) {
          displayedScore.value = target
          audio.playSfx('level_up')
          return true
        }
        return false
      })
    }
  })

  addStep({ phase: 3, timeMs: 2200 })
  addStep({ phase: 4, timeMs: 2300 })
  addStep({ phase: 5, timeMs: 2400 })
  addStep({ phase: 6, timeMs: 2500 })
  addStep({ phase: 7, timeMs: 2600 })
  addStep({ phase: 8, timeMs: 2700, sfx: 'goal_complete' })
  addStep({ phase: 9, timeMs: 3200, sfx: 'cursor_select' })
  addStep({ phase: 10, timeMs: 4700 })
  addStep({ phase: 11, timeMs: 4900 })
  addStep({ phase: 13, timeMs: 7000 })
})
</script>

<template>
  <PageShell 
    :hints="phase >= 13 || phase === 99 ? ['A · CONTINUE', 'B · HOME', '◆ SHARE'] : []" 
    bg="warm" bgVariant="stars" 
    :show-heading="false"
    :hide-status="true"
  >
    <div class="stage-bg absolute inset-0 z-0 pointer-events-none"></div>
    
    <div class="content h-full flex flex-col relative z-10 w-full" @click="phase < 13 ? skip(() => { displayedScore = finalScore ?? 0 }) : (audio.playSfx('cursor_select'), router.push('/garage'))">
      
      <div 
        class="text-center transition-transform duration-300 mt-[2vh] mb-[2vh]"
        :class="phase >= 1 ? 'translate-y-0' : '-translate-y-16'"
      >
        <span class="banner-tag uppercase tracking-[0.4em] font-title">
          Stage Clear !
        </span>
      </div>
      
      <div class="grid grid-cols-[1fr_auto_1fr] gap-[4vw] px-[4vw] items-center min-h-0">
        <!-- Left: Metrics -->
        <div class="flex flex-col gap-[2vh]">
          <div class="text-small text-slate tracking-widest uppercase border-b border-slate/30 pb-1">Performance</div>
          <Frame variant="default" padding="12px" class="flex flex-col gap-[1vh]">
            <div v-for="(m, i) in metrics" :key="m.label" 
                 class="transition-opacity duration-200"
                 :class="(phase >= 3 + i || phase === 99) ? 'opacity-100' : 'opacity-0'">
              <CyberMetricRow 
                :label="m.label" 
                :value="m.val" 
                :sub-text="m.sub" 
                :sub-class="m.subClass" 
              />
            </div>
          </Frame>
        </div>

        <!-- Center: Score & Grade — real values from /session/<sid>/scorecard -->
        <div v-if="phase >= 2 || phase === 99" class="flex flex-col items-center justify-center min-w-[25vw] relative">
          <div class="text-small text-slate tracking-widest mb-2 uppercase">Session Score</div>
          <template v-if="scoreAvailable">
            <div class="text-[clamp(40px,10vmin,80px)] text-ui-warn tracking-widest font-title leading-none mb-4">
              {{ displayedScore }}<span class="text-title-sm text-slate ml-1">%</span>
            </div>
            <div v-if="phase >= 8 || phase === 99" class="grade-badge animate-stamp">
              {{ grade }}
            </div>
          </template>
          <template v-else>
            <div class="text-body text-ui-bad tracking-widest uppercase text-center max-w-[28ch]">
              SCORE UNAVAILABLE
              <div v-if="scorecardError" class="text-tiny text-slate normal-case tracking-normal mt-2">
                {{ scorecardError }}
              </div>
              <div v-else class="text-tiny text-slate normal-case tracking-normal mt-2">
                /session/&lt;sid&gt;/scorecard returned no data — session may not be analysed yet.
              </div>
            </div>
          </template>
        </div>

        <!-- Right: Goals & Medals -->
        <div class="flex flex-col gap-[4vh]">
           <div v-if="phase >= 8 || phase === 99" class="flex flex-col gap-2">
              <div class="text-small text-slate tracking-widest uppercase border-b border-slate/30 pb-1">Goals</div>
              <Frame variant="default" padding="12px" class="flex flex-col gap-2">
                <div v-for="g in goals" :key="g.desc" class="flex items-center gap-3 text-small">
                  <span class="font-bold" :class="g.ok ? 'text-ui-good' : 'text-ui-bad'">{{ g.ok ? '✓' : '✗' }}</span>
                  <span class="flex-grow tracking-wider" :class="g.ok ? 'text-white' : 'text-slate'">{{ g.desc }}</span>
                </div>
              </Frame>
           </div>

           <div v-if="(phase >= 9 || phase === 99) && medals.length > 0" class="flex flex-col gap-2">
              <div class="text-small text-ui-warn tracking-widest uppercase border-b border-ui-warn/30 pb-1">★ Medals</div>
              <div class="flex flex-wrap gap-2">
                <div v-for="m in medals" :key="m" class="bg-ui-warn/10 border border-ui-warn px-2 py-1 text-[10px] text-white tracking-widest">
                  {{ m.toUpperCase() }}
                </div>
              </div>
           </div>
        </div>
      </div>

      <!-- BEST MOMENTS strip — backed by /session/<sid>/highlights -->
      <div
        v-if="(phase >= 10 || phase === 99) && topHighlights.length > 0"
        class="mx-[4vw] mt-[2vh] mb-[1vh] flex flex-col gap-2"
      >
        <div class="text-small text-slate tracking-widest uppercase border-b border-slate/30 pb-1">
          Best Moments
        </div>
        <div class="grid grid-cols-1 md:grid-cols-3 gap-2">
          <Frame
            v-for="(h, i) in topHighlights"
            :key="`${h.lap}-${h.distance_m}-${i}`"
            variant="default"
            padding="10px"
            class="flex flex-col gap-1 border-l-2"
            :class="highlightAccentClass(h)"
          >
            <div class="text-small tracking-widest uppercase opacity-80">
              {{ h.category }} · lap {{ h.lap }}
            </div>
            <div class="text-silver text-[clamp(11px,2.2vmin,15px)] leading-tight font-bold">
              {{ h.title }}
            </div>
            <div class="text-[10px] text-slate italic line-clamp-2">
              {{ h.narrative_seed }}
            </div>
          </Frame>
        </div>
      </div>

      <!-- INCIDENTS strip — backed by /session/<sid>/incidents (flight recorder) -->
      <div
        v-if="(phase >= 11 || phase === 99) && topIncidents.length > 0"
        class="mx-[4vw] mt-[2vh] mb-[1vh] flex flex-col gap-2"
      >
        <div class="text-small text-ui-bad tracking-widest uppercase border-b border-ui-bad/30 pb-1 flex items-center gap-2">
          Incidents <span class="text-slate text-[10px]">· what nearly went wrong</span>
        </div>
        <div class="grid grid-cols-1 md:grid-cols-3 gap-2">
          <Frame
            v-for="(inc, i) in topIncidents"
            :key="`inc-${inc.frame_idx}-${i}`"
            variant="default"
            padding="10px"
            class="flex flex-col gap-1 border-l-2 border-ui-bad text-ui-bad"
          >
            <div class="text-small tracking-widest uppercase opacity-80">
              {{ inc.combo_g.toFixed(2) }} G · {{ inc.speed_kmh.toFixed(0) }} km/h
            </div>
            <div class="text-silver text-[clamp(11px,2.2vmin,15px)] leading-tight font-bold">
              {{ inc.reason }}
            </div>
            <div class="text-[10px] text-slate italic">
              at {{ inc.distance_m.toFixed(0) }} m
            </div>
          </Frame>
        </div>
      </div>

      <!-- Clean-session indicator — only when bundle was analysed AND no incidents -->
      <div
        v-else-if="(phase >= 11 || phase === 99) && incidents.length === 0 && highlights.length > 0"
        class="mx-[4vw] mt-[1vh] text-small text-ui-good tracking-widest uppercase text-center"
      >
        🏁 Clean session — no over-limit incidents recorded.
      </div>

    </div>

    <div v-if="phase >= 13 || phase === 99" class="absolute bottom-[10vh] left-0 right-0 text-center z-20 cursor-pointer" @click="audio.playSfx('cursor_select'); router.push('/garage')">
      <span class="text-ui-good font-bold text-title-sm tracking-[0.4em] animate-pulse border-2 border-ui-good px-10 py-3 bg-ink/90 shadow-[0_0_20px_rgba(42,161,152,0.4)]">
        Tap to Continue ▶
      </span>
    </div>
    
    <template #floating>
      <div 
        class="absolute bottom-[4vh] left-[4vw] right-[4vw] transition-transform duration-500 pointer-events-none"
        :class="(phase >= 10 || phase === 99) ? 'translate-y-0' : 'translate-y-48'"
      >
        <CoachFloat
          v-if="(phase >= 11 || phase === 99) && coach.debrief?.narrative"
          :coach-id="save.activeSlot?.preferredCoach ?? 'trod'"
          :emotion="coach.debrief?.emotion ?? 'idle'"
          :text="coach.debrief.narrative ?? ''"
        />
      </div>
    </template>
  </PageShell>
</template>


<style scoped>
.stage-bg {
  background: linear-gradient(
    180deg,
    rgba(42, 161, 152, 0.06) 0%,
    var(--color-ink) 30%,
    var(--color-asphalt-deep) 100%
  );
}

.banner-tag {
  display: inline-block;
  background: var(--color-ui-good);
  color: var(--color-ink);
  font-weight: bold;
  font-size: clamp(16px, 4vmin, 32px);
  padding: 8px 48px;
  box-shadow:
    0 0 20px rgba(42, 161, 152, 0.4),
    inset 0 -2px 0 rgba(0,0,0,0.2);
}

.grade-badge {
  font-size: 64px;
  color: var(--color-ui-good);
  text-shadow: 2px 2px 0 #000, 0 0 15px var(--color-ui-good);
  border: 4px solid var(--color-ui-good);
  border-radius: 50%;
  width: 96px;
  height: 96px;
  display: flex;
  align-items: center;
  justify-content: center;
  transform: rotate(15deg);
  background: rgba(42, 161, 152, 0.1);
}

.animate-stamp {
  animation: stamp 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275) forwards;
}

@keyframes stamp {
  0% { transform: scale(4) rotate(0deg); opacity: 0; }
  100% { transform: scale(1) rotate(15deg); opacity: 1; }
}
</style>


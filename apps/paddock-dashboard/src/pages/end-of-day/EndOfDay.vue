<script setup lang="ts">
/**
 * END OF DAY — tabbed layout for Pixel 10 landscape.
 *
 * Four tabs (1–4):
 *   1. SUMMARY    — tally cards from /sessions + /session/<sid>/scorecard + /session/<sid>/stats
 *   2. LAPS       — /session/<sid>/lap_time_table + /session/<sid>/laps
 *   3. HIGHLIGHTS — /session/<sid>/highlights + /session/<sid>/incidents
 *   4. DEBRIEF    — coach.debrief narrative + focus (POST /coach/debrief result)
 *
 * Each tab fails-loud with an honest "DATA UNAVAILABLE" panel when the
 * underlying endpoint returns nothing — never a templated fallback.
 *
 * Esc/B navigates to home (preserves the existing end-of-day flow that
 * wiped the active save and routed to '/').
 */
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useKeyboard } from '@/shared/lib/useKeyboard'
import { useRouter } from 'vue-router'
import { useSaveStore } from '@/entities/save/model/saveStore'
import { useAudioStore } from '@/features/audio-playback/model/audioStore'
import { useCoachStore } from '@/entities/coach/model/coachStore'
import { useSessionStore } from '@/entities/session/model/sessionStore'
import { useLapTimeStore } from '@/entities/lap-time/model/lapTimeStore'
import { bridge } from '@/shared/api/bridge'
import { formatLapTime } from '@/shared/lib/lap'
import PageShell from '@/shared/ui/PageShell.vue'
import CyberTabs from '@/shared/ui/core/CyberTabs.vue'
import CyberPanel from '@/shared/ui/core/CyberPanel.vue'
import Frame from '@/shared/ui/core/Frame.vue'
import DialogueBox from '@/widgets/dialogue-box/DialogueBox.vue'

const router = useRouter()
const save = useSaveStore()
const audio = useAudioStore()
const coach = useCoachStore()
const sessionStore = useSessionStore()
const lapTime = useLapTimeStore()

const TAB_LABELS = ['SUMMARY', 'LAPS', 'HIGHLIGHTS', 'DEBRIEF'] as const
const activeTab = ref(0)

let navTimeout: number | null = null

// ── SUMMARY tab state ────────────────────────────────────────────────────────
interface TallyCard { label: string; value: string }
const tally = ref<TallyCard[]>([])
const tallyError = ref<string | null>(null)

interface StatsBundle {
  top_speed_kmh?: number
  max_g_lat?: number
  max_g_combo?: number
  peak_brake_bar?: number
  longest_full_throttle_s?: number
  [key: string]: any
}
const stats = ref<StatsBundle | null>(null)
const statsError = ref<string | null>(null)

interface ScorecardCorner {
  corner?: string
  name?: string
  grade?: string
}
const scorecardCorners = ref<ScorecardCorner[]>([])
const scorecardError = ref<string | null>(null)

// ── LAPS tab state ───────────────────────────────────────────────────────────
const lapsError = ref<string | null>(null)
const lapTimeTableError = ref<string | null>(null)
interface LapWindow {
  name: string
  t_start: number
  t_end: number
  duration_s: number
  distance_m: number
  method: string
}
const lapWindows = ref<LapWindow[]>([])

// ── HIGHLIGHTS tab state ─────────────────────────────────────────────────────
interface Highlight {
  title: string
  category: string
  severity: 'high' | 'medium' | 'positive' | 'engineering' | string
  lap?: number
  distance_m?: number
  narrative_seed?: string
}
interface Incident {
  timestamp?: number
  distance_m?: number
  speed_kmh?: number
  combo_g?: number
  reason?: string
  frame_idx?: number
}
const highlights = ref<Highlight[]>([])
const incidents = ref<Incident[]>([])
const highlightsError = ref<string | null>(null)
const incidentsError = ref<string | null>(null)

// ── DEBRIEF tab state ────────────────────────────────────────────────────────
const debriefError = ref<string | null>(null)
const debriefText = computed(() => coach.debrief?.narrative?.trim() ?? '')
const debriefEmotion = computed(() => coach.debrief?.emotion ?? 'idle')
const debriefFocus = computed<string[]>(() => coach.debrief?.focus ?? [])

// ── Loading orchestration ────────────────────────────────────────────────────
async function loadTally() {
  try {
    await sessionStore.fetchSessions()
    const sessions = sessionStore.sessions
    const totalLaps = sessions.reduce((sum, s) => sum + (s.lap_count || 0), 0)
    const bestLap = sessions
      .map(s => s.best_lap_s)
      .filter((t): t is number => t != null)
    const bestLapFormatted = formatLapTime(
      bestLap.length ? Math.min(...bestLap) : null,
      1,
    )
    tally.value = [
      { label: 'SESSIONS', value: String(sessions.length) },
      { label: 'TOTAL LAPS', value: String(totalLaps) },
      { label: 'BEST LAP', value: bestLapFormatted },
      { label: 'LEVEL', value: `LV ${save.activeSlot?.level ?? '?'}` },
    ]
  } catch (e: any) {
    tallyError.value = e?.message ?? String(e)
    tally.value = []
  }
}

async function loadStats(sid: string) {
  try {
    const res = await bridge.get<any>(`/session/${sid}/stats`)
    // Bundle endpoints return the section as-is or { stats: {...} }; accept both.
    stats.value = (res?.stats ?? res) as StatsBundle
  } catch (e: any) {
    statsError.value = e?.message ?? String(e)
    stats.value = null
  }
}

async function loadScorecard(sid: string) {
  try {
    const res = await bridge.get<any>(`/session/${sid}/scorecard`)
    const list = res?.scorecard?.corners ?? res?.corners ?? []
    scorecardCorners.value = Array.isArray(list) ? list : []
  } catch (e: any) {
    scorecardError.value = e?.message ?? String(e)
    scorecardCorners.value = []
  }
}

async function loadLapWindows(sid: string) {
  try {
    const res = await bridge.get<{ laps: LapWindow[] }>(`/session/${sid}/laps`)
    lapWindows.value = Array.isArray(res?.laps) ? res.laps : []
  } catch (e: any) {
    lapsError.value = e?.message ?? String(e)
    lapWindows.value = []
  }
}

async function loadLapTimeTable(sid: string) {
  await lapTime.fetchLapTimes(sid)
  if (lapTime.error) {
    lapTimeTableError.value = lapTime.error
  }
}

async function loadHighlights(sid: string) {
  try {
    const res = await bridge.get<{ highlights: Highlight[] }>(`/session/${sid}/highlights`)
    highlights.value = Array.isArray(res?.highlights) ? res.highlights : []
  } catch (e: any) {
    highlightsError.value = e?.message ?? String(e)
    highlights.value = []
  }
}

async function loadIncidents(sid: string) {
  try {
    const res = await bridge.get<{ incidents: Incident[] }>(`/session/${sid}/incidents`)
    incidents.value = Array.isArray(res?.incidents) ? res.incidents : []
  } catch (e: any) {
    incidentsError.value = e?.message ?? String(e)
    incidents.value = []
  }
}

async function loadDebrief(sid: string) {
  try {
    await coach.fetchDebrief({
      sessionId: sid,
      driverId: save.activeSlot?.driverName,
    })
    if (!coach.debrief?.narrative?.trim()) {
      debriefError.value = coach.debriefError
        ?? 'Debrief unavailable — coach returned no narrative.'
    }
  } catch (e: any) {
    debriefError.value = e?.message ?? String(e)
  }
}

onMounted(async () => {
  await loadTally()

  const sid = sessionStore.activeSessionId
  if (!sid) {
    statsError.value = 'No active session — nothing to summarize.'
    scorecardError.value = 'No active session.'
    lapsError.value = 'No active session.'
    lapTimeTableError.value = 'No active session.'
    highlightsError.value = 'No active session.'
    incidentsError.value = 'No active session.'
    debriefError.value = 'No active session — nothing to debrief.'
    return
  }

  // Fan out — every endpoint is independent.
  await Promise.all([
    loadStats(sid),
    loadScorecard(sid),
    loadLapWindows(sid),
    loadLapTimeTable(sid),
    loadHighlights(sid),
    loadIncidents(sid),
    loadDebrief(sid),
  ])
})

onUnmounted(() => {
  if (navTimeout) clearTimeout(navTimeout)
})

function goHome() {
  audio.playSfx('cancel')
  save.activeSlotId = null
  router.push('/')
}

useKeyboard((e: KeyboardEvent) => {
  // Tab switching — always available.
  if (e.key === '1') { audio.playSfx('cursor_move'); activeTab.value = 0; return }
  if (e.key === '2') { audio.playSfx('cursor_move'); activeTab.value = 1; return }
  if (e.key === '3') { audio.playSfx('cursor_move'); activeTab.value = 2; return }
  if (e.key === '4') { audio.playSfx('cursor_move'); activeTab.value = 3; return }

  if (e.key === 'Escape' || e.key === 'Backspace' || e.key === 'b') {
    goHome()
  } else if (e.key === 'Enter' || e.key === 'a') {
    // On DEBRIEF tab Enter advances to home (mirrors the old behaviour
    // after the dialogue box played out).
    if (activeTab.value === 3) goHome()
  }
})

// ── Tier styling helpers ─────────────────────────────────────────────────────
function highlightAccent(h: Highlight): string {
  if (h.severity === 'positive') return 'border-ui-good text-ui-good'
  if (h.severity === 'high') return 'border-ui-bad text-ui-bad'
  if (h.severity === 'medium') return 'border-ui-warn text-ui-warn'
  return 'border-slate text-silver'
}

function gradeColor(g?: string): string {
  if (!g) return 'text-slate'
  if (g.startsWith('A')) return 'text-ui-good'
  if (g.startsWith('B')) return 'text-ui-info'
  if (g.startsWith('C')) return 'text-ui-warn'
  return 'text-ui-bad'
}

const statRows = computed(() => {
  const s = stats.value
  if (!s) return []
  const rows: { label: string; value: string }[] = []
  if (typeof s.top_speed_kmh === 'number') rows.push({ label: 'TOP SPEED', value: `${s.top_speed_kmh.toFixed(1)} km/h` })
  if (typeof s.max_g_lat === 'number') rows.push({ label: 'MAX G-LAT', value: `${s.max_g_lat.toFixed(2)} g` })
  if (typeof s.max_g_combo === 'number') rows.push({ label: 'MAX G-COMBO', value: `${s.max_g_combo.toFixed(2)} g` })
  if (typeof s.peak_brake_bar === 'number') rows.push({ label: 'PEAK BRAKE', value: `${s.peak_brake_bar.toFixed(1)} bar` })
  if (typeof s.longest_full_throttle_s === 'number') rows.push({ label: 'LONGEST WOT', value: `${s.longest_full_throttle_s.toFixed(1)} s` })
  return rows
})
</script>

<template>
  <PageShell
    title="END OF DAY"
    :hints="['1·SUMMARY', '2·LAPS', '3·HIGHLIGHTS', '4·DEBRIEF', 'B · HOME']"
    bg="cool"
    :show-heading="false"
  >
    <div class="eod-root flex flex-col h-full w-full gap-[1vmin]">

      <!-- Tab bar -->
      <CyberTabs
        v-model="activeTab"
        :tabs="TAB_LABELS"
        class="mx-2 shrink-0"
      />

      <div class="flex-1 min-h-0 mx-2 overflow-hidden">

        <!-- TAB 1 · SUMMARY -->
        <CyberPanel v-show="activeTab === 0" class="h-full flex flex-col gap-[1.5vmin] p-[2vmin] overflow-y-auto">
          <div class="text-small text-slate tracking-widest uppercase border-b border-slate/50 pb-1 shrink-0">
            TODAY · SESSION TALLY
          </div>

          <div v-if="tallyError" class="p-3 border border-ui-bad/40 bg-ui-bad/5 text-small text-ui-bad tracking-wider uppercase">
            <div class="font-bold mb-1">DATA UNAVAILABLE — bridge endpoint missing</div>
            <div class="text-ui-bad/80 normal-case tracking-normal">{{ tallyError }}</div>
          </div>
          <div v-else class="grid grid-cols-2 gap-3">
            <Frame v-for="t in tally" :key="t.label" variant="default" padding="12px" class="flex flex-col">
              <span class="text-small text-slate tracking-widest uppercase">{{ t.label }}</span>
              <span class="text-title-sm font-bold text-white mt-1">{{ t.value }}</span>
            </Frame>
          </div>

          <div class="text-small text-slate tracking-widest uppercase border-b border-slate/50 pb-1 mt-[1vmin] shrink-0">
            SESSION STATS · /session/&lt;sid&gt;/stats
          </div>
          <div v-if="statsError" class="p-3 border border-ui-bad/40 bg-ui-bad/5 text-small text-ui-bad tracking-wider uppercase">
            <div class="font-bold mb-1">DATA UNAVAILABLE — bridge endpoint missing</div>
            <div class="text-ui-bad/80 normal-case tracking-normal">{{ statsError }}</div>
          </div>
          <div v-else-if="!statRows.length" class="text-small text-slate tracking-widest uppercase py-2">
            — NO STATS RETURNED —
          </div>
          <div v-else class="flex flex-col gap-1">
            <div v-for="r in statRows" :key="r.label" class="flex justify-between text-body">
              <span class="text-slate tracking-widest">{{ r.label }}</span>
              <span class="font-bold text-white">{{ r.value }}</span>
            </div>
          </div>

          <div class="text-small text-slate tracking-widest uppercase border-b border-slate/50 pb-1 mt-[1vmin] shrink-0">
            CORNER GRADES · /session/&lt;sid&gt;/scorecard
          </div>
          <div v-if="scorecardError" class="p-3 border border-ui-bad/40 bg-ui-bad/5 text-small text-ui-bad tracking-wider uppercase">
            <div class="font-bold mb-1">DATA UNAVAILABLE — bridge endpoint missing</div>
            <div class="text-ui-bad/80 normal-case tracking-normal">{{ scorecardError }}</div>
          </div>
          <div v-else-if="!scorecardCorners.length" class="text-small text-slate tracking-widest uppercase py-2">
            — NO SCORECARD RETURNED —
          </div>
          <div v-else class="flex flex-wrap gap-2">
            <div
              v-for="c in scorecardCorners"
              :key="c.corner ?? c.name"
              class="border px-2 py-1 text-small tracking-widest font-mono"
              :class="gradeColor(c.grade)"
            >
              {{ c.corner ?? c.name ?? '?' }} · {{ c.grade ?? '?' }}
            </div>
          </div>
        </CyberPanel>

        <!-- TAB 2 · LAPS -->
        <CyberPanel v-show="activeTab === 1" class="h-full flex flex-col gap-[1.5vmin] p-[2vmin] overflow-y-auto">
          <div class="text-small text-slate tracking-widest uppercase border-b border-slate/50 pb-1 shrink-0">
            LAP TIME TABLE · /session/&lt;sid&gt;/lap_time_table
          </div>

          <div v-if="lapTimeTableError" class="p-3 border border-ui-bad/40 bg-ui-bad/5 text-small text-ui-bad tracking-wider uppercase">
            <div class="font-bold mb-1">DATA UNAVAILABLE — bridge endpoint missing</div>
            <div class="text-ui-bad/80 normal-case tracking-normal">{{ lapTimeTableError }}</div>
          </div>
          <div v-else-if="!lapTime.laps.length" class="text-small text-slate tracking-widest uppercase py-2">
            — NO LAPS RECORDED —
          </div>
          <Frame v-else variant="default" padding="12px" class="flex flex-col gap-1">
            <div class="grid grid-cols-[3rem_1fr_1fr_4rem] text-small text-slate tracking-widest uppercase border-b border-slate/40 pb-1 mb-1">
              <span>LAP</span>
              <span>TIME</span>
              <span>Δ BEST</span>
              <span class="text-right">PB</span>
            </div>
            <div
              v-for="l in lapTime.laps"
              :key="l.lap_number"
              class="grid grid-cols-[3rem_1fr_1fr_4rem] text-body items-center"
            >
              <span class="font-mono text-slate">#{{ l.lap_number }}</span>
              <span class="font-mono text-white font-bold">{{ formatLapTime(l.lap_time_s, 3) }}</span>
              <span class="font-mono" :class="l.delta_to_best_s === 0 ? 'text-ui-good' : 'text-silver'">
                {{ l.delta_to_best_s === 0 ? 'BEST' : `+${l.delta_to_best_s.toFixed(3)}s` }}
              </span>
              <span class="text-right">
                <span v-if="l.is_best" class="text-ui-good font-bold text-small">★</span>
              </span>
            </div>
          </Frame>

          <div class="text-small text-slate tracking-widest uppercase border-b border-slate/50 pb-1 mt-[1vmin] shrink-0">
            LAP WINDOWS · /session/&lt;sid&gt;/laps
          </div>
          <div v-if="lapsError" class="p-3 border border-ui-bad/40 bg-ui-bad/5 text-small text-ui-bad tracking-wider uppercase">
            <div class="font-bold mb-1">DATA UNAVAILABLE — bridge endpoint missing</div>
            <div class="text-ui-bad/80 normal-case tracking-normal">{{ lapsError }}</div>
          </div>
          <div v-else-if="!lapWindows.length" class="text-small text-slate tracking-widest uppercase py-2">
            — NO LAP WINDOWS RETURNED —
          </div>
          <div v-else class="flex flex-col gap-1 text-small font-mono">
            <div v-for="w in lapWindows" :key="`${w.t_start}-${w.name}`" class="flex justify-between">
              <span class="text-silver">{{ w.name }}</span>
              <span class="text-slate">{{ w.duration_s.toFixed(2) }}s · {{ (w.distance_m / 1000).toFixed(2) }}km · {{ w.method }}</span>
            </div>
          </div>
        </CyberPanel>

        <!-- TAB 3 · HIGHLIGHTS -->
        <CyberPanel v-show="activeTab === 2" class="h-full flex flex-col gap-[1.5vmin] p-[2vmin] overflow-y-auto">
          <div class="text-small text-slate tracking-widest uppercase border-b border-slate/50 pb-1 shrink-0">
            BEST MOMENTS · /session/&lt;sid&gt;/highlights
          </div>

          <div v-if="highlightsError" class="p-3 border border-ui-bad/40 bg-ui-bad/5 text-small text-ui-bad tracking-wider uppercase">
            <div class="font-bold mb-1">DATA UNAVAILABLE — bridge endpoint missing</div>
            <div class="text-ui-bad/80 normal-case tracking-normal">{{ highlightsError }}</div>
          </div>
          <div v-else-if="!highlights.length" class="text-small text-slate tracking-widest uppercase py-2">
            — NO HIGHLIGHTS RETURNED (debrief not run for this session) —
          </div>
          <div v-else class="grid grid-cols-1 md:grid-cols-2 gap-2">
            <div
              v-for="h in highlights"
              :key="`${h.title}-${h.lap}-${h.distance_m}`"
              class="border p-2"
              :class="highlightAccent(h)"
            >
              <div class="text-small tracking-widest font-bold uppercase">{{ h.title }}</div>
              <div class="text-small text-slate font-mono mt-1">
                lap {{ h.lap ?? '?' }} · {{ (h.distance_m ?? 0).toFixed(0) }}m · {{ h.category }}
              </div>
              <div v-if="h.narrative_seed" class="text-small text-silver italic mt-1">"{{ h.narrative_seed }}"</div>
            </div>
          </div>

          <div class="text-small text-slate tracking-widest uppercase border-b border-slate/50 pb-1 mt-[1vmin] shrink-0">
            INCIDENTS · /session/&lt;sid&gt;/incidents
          </div>
          <div v-if="incidentsError" class="p-3 border border-ui-bad/40 bg-ui-bad/5 text-small text-ui-bad tracking-wider uppercase">
            <div class="font-bold mb-1">DATA UNAVAILABLE — bridge endpoint missing</div>
            <div class="text-ui-bad/80 normal-case tracking-normal">{{ incidentsError }}</div>
          </div>
          <div v-else-if="!incidents.length" class="text-small text-slate tracking-widest uppercase py-2">
            — NO INCIDENTS RECORDED —
          </div>
          <Frame v-else variant="default" padding="12px" class="flex flex-col gap-1">
            <div
              v-for="(inc, i) in incidents"
              :key="`${inc.timestamp}-${i}`"
              class="grid grid-cols-[5rem_1fr_5rem_5rem] text-small font-mono items-center"
            >
              <span class="text-slate">{{ (inc.distance_m ?? 0).toFixed(0) }}m</span>
              <span class="text-silver truncate">{{ inc.reason ?? '?' }}</span>
              <span class="text-ui-warn">{{ (inc.combo_g ?? 0).toFixed(2) }}g</span>
              <span class="text-right text-slate">{{ (inc.speed_kmh ?? 0).toFixed(0) }} km/h</span>
            </div>
          </Frame>
        </CyberPanel>

        <!-- TAB 4 · DEBRIEF -->
        <CyberPanel v-show="activeTab === 3" class="h-full flex flex-col gap-[1.5vmin] p-[2vmin] overflow-y-auto">
          <div class="text-small text-slate tracking-widest uppercase border-b border-slate/50 pb-1 shrink-0">
            COACH DEBRIEF · /coach/debrief
          </div>

          <div v-if="coach.debriefLoading" class="text-slate text-body animate-pulse text-center py-4">
            LOADING DEBRIEF…
          </div>
          <div v-else-if="debriefError" class="p-3 border border-ui-bad/40 bg-ui-bad/5 text-small text-ui-bad tracking-wider uppercase">
            <div class="font-bold mb-1">DEBRIEF UNAVAILABLE</div>
            <div class="text-ui-bad/80 normal-case tracking-normal">{{ debriefError }}</div>
            <div class="mt-2">
              <button class="underline text-small" @click="goHome">[ continue ]</button>
            </div>
          </div>
          <DialogueBox
            v-else-if="debriefText"
            :coach-id="save.activeSlot?.preferredCoach ?? 'trod'"
            :emotion="debriefEmotion"
            :text="debriefText"
            @done="goHome"
          />
          <div v-else class="text-small text-slate tracking-widest uppercase text-center py-4">
            — WAITING FOR DEBRIEF —
          </div>

          <div v-if="debriefFocus.length" class="mt-[1vmin]">
            <div class="text-small text-slate tracking-widest uppercase border-b border-slate/50 pb-1 mb-2">
              NEXT FOCUS
            </div>
            <ul class="flex flex-col gap-1">
              <li v-for="f in debriefFocus" :key="f" class="text-body text-white tracking-wide">
                <span class="text-ui-good mr-2">▶</span>{{ f }}
              </li>
            </ul>
          </div>
        </CyberPanel>

      </div>
    </div>
  </PageShell>
</template>

<style scoped>
.eod-root {
  min-height: 0;
}
</style>

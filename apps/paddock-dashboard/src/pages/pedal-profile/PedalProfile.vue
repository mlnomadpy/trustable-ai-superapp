<script setup lang="ts">
/**
 * Pedal-state distribution for the active session, sourced from
 * `/session/<sid>/pedal_behavior`. The bridge accepts `throttle_th` and
 * `brake_th` query params and re-classifies every telemetry frame
 * server-side — so the sliders here are an actual filter on real data,
 * not a synthetic skew of a hardcoded base distribution.
 *
 * Per-corner pedal patterns were previously rendered from a hardcoded
 * 6-cell array per corner ('T','T','C','B','B','B'). No bridge endpoint
 * exposes that yet; the right panel now shows real per-corner *grades*
 * from the scorecard, which is what we have.
 */
import { onMounted, onUnmounted, ref, watch, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAudioStore } from '@/features/audio-playback/model/audioStore'
import { useSessionStore } from '@/entities/session/model/sessionStore'
import { useKeyboard } from '@/shared/lib/useKeyboard'
import { bridge } from '@/shared/api/bridge'
import PageShell from '@/shared/ui/PageShell.vue'
import CyberPanel from '@/shared/ui/core/CyberPanel.vue'
import CyberSplitView from '@/shared/ui/core/CyberSplitView.vue'
import CoachFloat from '@/shared/ui/CoachFloat.vue'

const router = useRouter()
const audio = useAudioStore()
const session = useSessionStore()

interface PedalState { frames: number; pct: number; time_s: number }
interface PedalResponse {
  session_id: string
  frame_count: number
  thresholds: { throttle_pct: number; brake_bar: number }
  frame_dt_s: number
  states: {
    throttle_only: PedalState
    brake_only:    PedalState
    trail_brake:   PedalState
    coast:         PedalState
  }
}

interface CornerGrade {
  corner: string
  grade: string | null
}

/**
 * EoB ("end-of-braking") summary — Bentley's "nothing time" metric. The
 * shorter the dead-pedal interval between brake-off and throttle-on, the
 * better the driver. Endpoint returns session average + worst corner +
 * per-corner averages.
 */
interface EobSummary {
  average_nothing_time_s: number
  worst_corner: string | null
  per_corner_avg_s: Record<string, number>
}
const eob = ref<EobSummary | null>(null)

/**
 * Friction circle — classic G-G plot. Bridge returns:
 *   • histogram_pct: 10 utilisation bins (0–10% … 90–100%)
 *   • over_limit_pct: % frames exceeding 100% utilisation
 *   • samples: ~1500 stride-sampled (gLat, gLong) points for scatter
 * Bentley anchor: "drivers who never reach the peak band aren't using the car."
 */
interface FrictionResp {
  max_combo_g_observed: number
  histogram_pct: number[]
  over_limit_pct: number
  samples: { gLat: number; gLong: number }[]
}
const friction = ref<FrictionResp | null>(null)

const thrTh = ref(5)         // %
const brkTh = ref(1.0)       // bar
const activeSlider = ref<'throttle' | 'brake'>('throttle')

const data = ref<PedalResponse | null>(null)
const corners = ref<CornerGrade[]>([])
const loading = ref(false)
const errorMsg = ref<string | null>(null)
let refetchTimer: number | null = null

const sid = computed(() => session.activeSessionId ?? session.sessions[0]?.session_id ?? '')

async function refetch() {
  if (!sid.value) {
    errorMsg.value = 'No active session'
    return
  }
  loading.value = true
  errorMsg.value = null
  try {
    const res = await bridge.get<PedalResponse>(
      `/session/${sid.value}/pedal_behavior?throttle_th=${thrTh.value}&brake_th=${brkTh.value}`,
    )
    data.value = res
  } catch (e: any) {
    errorMsg.value = e?.message ?? String(e)
    data.value = null
  } finally {
    loading.value = false
  }
}

async function loadCorners() {
  if (!sid.value) return
  try {
    const res = await bridge.get<{ scorecard: { corners: CornerGrade[] } }>(
      `/session/${sid.value}/scorecard`,
    )
    corners.value = res?.scorecard?.corners ?? []
  } catch { /* corners are best-effort */ }
}

async function loadEob() {
  if (!sid.value) return
  try {
    const res = await bridge.get<{ eob: EobSummary }>(`/session/${sid.value}/eob`)
    eob.value = res?.eob && Object.keys(res.eob).length ? res.eob : null
  } catch { /* eob best-effort; null UI handled below */ }
}

async function loadFriction() {
  if (!sid.value) return
  try {
    const res = await bridge.get<FrictionResp>(`/session/${sid.value}/friction_circle`)
    friction.value = res && Array.isArray(res.samples) ? res : null
  } catch { /* friction best-effort */ }
}

/** Per-corner dead-pedal time lookup for the corner-grade strip. */
function nothingTimeFor(cornerName: string): number | null {
  return eob.value?.per_corner_avg_s?.[cornerName] ?? null
}

onMounted(async () => {
  refetch()
  loadCorners()
  loadEob()
  loadFriction()
})

/**
 * Project a (gLat, gLong) sample into an SVG-friendly viewBox. The G-G
 * scatter is rendered in a 200×200 viewBox; we scale by the observed peak
 * G with a small inset so the outermost samples don't sit flush against
 * the boundary. Returns NaN-free coords.
 */
function ggProject(s: { gLat: number; gLong: number }): { x: number; y: number } {
  const peak = Math.max(0.5, friction.value?.max_combo_g_observed ?? 1.5)
  const scale = 90 / peak           // 90 = half-axis (viewBox 200, centre 100)
  const x = 100 + s.gLat  * scale
  const y = 100 - s.gLong * scale  // SVG y grows downward; throttle (positive g_long) up
  return { x, y }
}

// Debounce slider changes so we don't re-hit the bridge on every keypress.
watch([thrTh, brkTh], () => {
  if (refetchTimer) window.clearTimeout(refetchTimer)
  refetchTimer = window.setTimeout(refetch, 200) as unknown as number
})

const distribution = computed(() => {
  const s = data.value?.states
  return {
    throttle: s?.throttle_only?.pct ?? 0,
    brake:    s?.brake_only?.pct ?? 0,
    trail:    s?.trail_brake?.pct ?? 0,
    coast:    s?.coast?.pct ?? 0,
  }
})

const getCoachLine = () => {
  if (!data.value) return ''
  const { throttle: th, brake: br, trail: tr, coast: c } = distribution.value
  void br
  if (c > 20) return `You're coasting ${c.toFixed(1)}% of the time. Pick a pedal — trail-brake the entry instead of lifting early.`
  if (tr < 5)  return `Trail-brake under 5%. Front tires aren't being loaded — you'll understeer the apex.`
  if (tr > 15) return `Real trail-brake technique — that's where the lap time hides. Hold this.`
  if (th > 60) return `Committed on power. Good.`
  if (th < 40) return `Tentative on power. The exits are where you build straight-line speed.`
  return `Solid pedal overlap. Keep the same shape next stint.`
}

const getEmotion = () => {
  if (!data.value) return 'idle'
  const { throttle: th, trail: tr, coast: c } = distribution.value
  if (c > 20 || tr < 5 || th < 40) return 'talk'
  if (tr > 15 || th > 60) return 'victory'
  return 'idle'
}

useKeyboard((e: KeyboardEvent) => {
  if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
    activeSlider.value = activeSlider.value === 'throttle' ? 'brake' : 'throttle'
    audio.playSfx('cursor_move')
  } else if (e.key === 'ArrowRight') {
    if (activeSlider.value === 'throttle') {
      thrTh.value = Math.min(100, thrTh.value + 1)
    } else {
      brkTh.value = Number((Math.min(100, brkTh.value + 0.5)).toFixed(1))
    }
    audio.playSfx('cursor_move')
  } else if (e.key === 'ArrowLeft') {
    if (activeSlider.value === 'throttle') {
      thrTh.value = Math.max(0, thrTh.value - 1)
    } else {
      brkTh.value = Number((Math.max(0.5, brkTh.value - 0.5)).toFixed(1))
    }
    audio.playSfx('cursor_move')
  } else if (e.key === 'Escape' || e.key === 'Backspace' || e.key === 'b') {
    audio.playSfx('cancel')
    router.push('/garage/analysis')
  }
})

onUnmounted(() => {
  if (refetchTimer) {
    window.clearTimeout(refetchTimer)
    refetchTimer = null
  }
})

const gradeColor: Record<string, string> = {
  'A+': 'bg-ui-good', 'A': 'bg-ui-good',
  'B':  'bg-ui-info',
  'C':  'bg-amber',
  'D':  'bg-ui-warn',
  'F':  'bg-ui-bad',
}
</script>

<template>
  <PageShell title="PEDAL PROFILE" :hints="['▲ ▼ SELECT SLIDER', '◀ ▶ ADJUST', 'B · BACK']" bg="cool">
    <!-- Session Distribution -->
    <CyberPanel class="p-2 relative">
      <div class="flex justify-between items-center mb-2">
        <div class="text-body text-silver font-bold uppercase">Session Distribution</div>
        <div class="text-small text-slate">
          <span v-if="loading">loading…</span>
          <span v-else-if="errorMsg" class="text-ui-bad">{{ errorMsg }}</span>
          <span v-else-if="data">{{ data.frame_count.toLocaleString() }} frames · {{ data.frame_dt_s }} s/frame</span>
        </div>
      </div>

      <!-- Stacked Bar -->
      <div class="w-full h-4 flex mt-2 border border-slate">
        <div class="h-full bg-ui-good" :style="{ width: `${distribution.throttle}%` }"></div>
        <div class="h-full bg-ui-warn" :style="{ width: `${distribution.brake}%` }"></div>
        <div class="h-full bg-amber" :style="{ width: `${distribution.trail}%` }"></div>
        <div class="h-full bg-charcoal" :style="{ width: `${distribution.coast}%` }"></div>
      </div>

      <div class="flex justify-between text-body mt-2 font-bold">
        <span class="text-ui-good">THROTTLE {{ distribution.throttle.toFixed(1) }}%</span>
        <span class="text-ui-warn">BRAKE {{ distribution.brake.toFixed(1) }}%</span>
        <span class="text-amber">TRAIL {{ distribution.trail.toFixed(1) }}%</span>
        <span class="text-silver">COAST {{ distribution.coast.toFixed(1) }}%</span>
      </div>

      <!-- End-of-braking summary (Bentley "nothing time"). Real data from /eob. -->
      <div v-if="eob" class="flex justify-between items-baseline mt-2 pt-2 border-t border-slate/40 text-small">
        <span class="text-slate tracking-widest uppercase">End-of-braking</span>
        <span class="text-silver">
          avg dead-pedal
          <span class="text-white font-bold">{{ eob.average_nothing_time_s.toFixed(2) }} s</span>
          <span v-if="eob.worst_corner" class="text-ui-warn ml-2">
            · worst at {{ eob.worst_corner }}
          </span>
        </span>
      </div>
    </CyberPanel>

    <CyberSplitView split="60-40" gap="sm" class="flex-grow min-h-0 mt-2">
      <template #left>
        <!-- Per-corner grade strip (real data; replaces the old hardcoded pedal pattern) -->
        <CyberPanel class="h-full flex flex-col text-body overflow-hidden p-2">
          <div class="flex justify-between mb-2">
            <div class="text-silver font-bold uppercase">Per-Corner Grade</div>
            <div class="text-small text-slate">from scorecard</div>
          </div>

          <div v-if="!corners.length" class="text-small text-slate italic">
            Run a debrief on this session to populate corner grades.
          </div>

          <div class="flex flex-col gap-1 overflow-y-auto pr-2">
            <div v-for="c in corners" :key="c.corner" class="flex gap-2 items-center text-small">
              <span class="w-[clamp(48px,10vw,80px)] text-silver">{{ c.corner }}</span>
              <div
                class="h-3 flex-grow"
                :class="(c.grade && gradeColor[c.grade]) || 'bg-charcoal'"
              ></div>
              <!-- Per-corner dead-pedal time from /eob (Bentley nothing-time). -->
              <span
                class="w-[clamp(40px,8vw,60px)] text-right font-mono text-[10px]"
                :class="(nothingTimeFor(c.corner) ?? 0) > 0.5 ? 'text-ui-warn' : 'text-slate/50'"
                :title="nothingTimeFor(c.corner) != null ? `${nothingTimeFor(c.corner)?.toFixed(2)} s dead-pedal` : 'no data'"
              >
                {{ nothingTimeFor(c.corner) != null ? `${nothingTimeFor(c.corner)?.toFixed(2)}s` : '—' }}
              </span>
              <span class="w-6 text-right font-bold text-silver">{{ c.grade ?? '—' }}</span>
            </div>
          </div>

          <div class="mt-auto flex justify-around text-small text-slate pt-2 border-t border-charcoal">
            <span class="flex items-center gap-1"><span class="w-2 h-2 bg-ui-good inline-block"></span> A</span>
            <span class="flex items-center gap-1"><span class="w-2 h-2 bg-ui-info inline-block"></span> B</span>
            <span class="flex items-center gap-1"><span class="w-2 h-2 bg-amber inline-block"></span> C</span>
            <span class="flex items-center gap-1"><span class="w-2 h-2 bg-ui-warn inline-block"></span> D</span>
            <span class="flex items-center gap-1"><span class="w-2 h-2 bg-ui-bad inline-block"></span> F</span>
          </div>
        </CyberPanel>
      </template>

      <template #right>
        <!-- Threshold sliders — debounced re-fetch against the bridge -->
        <CyberPanel class="h-full flex flex-col text-body p-2 overflow-hidden relative">
          <div class="text-silver mb-2 font-bold uppercase">Thresholds</div>

          <div class="flex flex-col gap-4">
            <div class="flex flex-col gap-1 cursor-pointer" :class="activeSlider === 'throttle' ? 'text-white' : 'text-slate'" @click="activeSlider = 'throttle'; audio.playSfx('cursor_move')">
              <div class="flex justify-between items-end relative">
                <span class="flex items-center relative">
                  <span v-if="activeSlider === 'throttle'" class="text-ui-good mr-1 absolute -left-3 text-body">▶</span>
                  THROTTLE %
                </span>
                <span class="font-bold bg-charcoal px-1">{{ thrTh }}</span>
              </div>
              <div class="w-full h-2 bg-charcoal relative mt-1 border border-slate cursor-pointer"
                   @click.stop="(e: MouseEvent) => { activeSlider = 'throttle'; const rect = (e.currentTarget as HTMLElement).getBoundingClientRect(); thrTh = Math.round(((e.clientX - rect.left) / rect.width) * 100); audio.playSfx('cursor_move') }">
                <div class="absolute h-full bg-ui-good" :style="{ width: `${thrTh}%` }"></div>
                <div class="absolute bottom-full -mb-[1px] -ml-[5px] w-0 h-0 border-l-[5px] border-l-transparent border-r-[5px] border-r-transparent border-t-[6px] border-t-white" :style="{ left: `${thrTh}%` }"></div>
              </div>
            </div>

            <div class="flex flex-col gap-1 cursor-pointer" :class="activeSlider === 'brake' ? 'text-white' : 'text-slate'" @click="activeSlider = 'brake'; audio.playSfx('cursor_move')">
              <div class="flex justify-between items-end relative">
                <span class="flex items-center relative">
                  <span v-if="activeSlider === 'brake'" class="text-ui-good mr-1 absolute -left-3 text-body">▶</span>
                  BRAKE bar
                </span>
                <span class="font-bold bg-charcoal px-1">{{ brkTh.toFixed(1) }}</span>
              </div>
              <div class="w-full h-2 bg-charcoal relative mt-1 border border-slate cursor-pointer"
                   @click.stop="(e: MouseEvent) => { activeSlider = 'brake'; const rect = (e.currentTarget as HTMLElement).getBoundingClientRect(); brkTh = Number((((e.clientX - rect.left) / rect.width) * 20).toFixed(1)); audio.playSfx('cursor_move') }">
                <div class="absolute h-full bg-ui-warn" :style="{ width: `${brkTh * 5}%` }"></div>
                <div class="absolute bottom-full -mb-[1px] -ml-[5px] w-0 h-0 border-l-[5px] border-l-transparent border-r-[5px] border-r-transparent border-t-[6px] border-t-white" :style="{ left: `${brkTh * 5}%` }"></div>
              </div>
            </div>
          </div>

          <div class="mt-auto text-small text-slate text-center leading-tight pt-2 border-t border-charcoal">
            Use ◀ ▶ to adjust.<br>Bridge re-classifies every frame at the new threshold.
          </div>
        </CyberPanel>
      </template>
    </CyberSplitView>

    <!-- Friction circle (G-G scatter + utilisation histogram) -->
    <CyberPanel class="mt-2 p-2">
      <div class="flex justify-between items-baseline mb-2 border-b border-slate pb-1">
        <div class="text-body text-silver font-bold uppercase">Friction Circle</div>
        <div class="text-small text-slate">
          <span v-if="!friction" class="italic">no data — drive a flying lap</span>
          <span v-else>
            peak combo G <span class="text-white font-bold">{{ friction.max_combo_g_observed.toFixed(2) }}</span>
            · over-limit
            <span :class="friction.over_limit_pct > 1 ? 'text-ui-warn font-bold' : 'text-silver'">
              {{ friction.over_limit_pct.toFixed(2) }}%
            </span>
            · {{ friction.samples.length.toLocaleString() }} samples
          </span>
        </div>
      </div>

      <div v-if="friction" class="grid grid-cols-1 md:grid-cols-[260px_1fr] gap-3">
        <!-- G-G scatter -->
        <div>
          <svg viewBox="0 0 200 200" class="w-full max-h-[40vh] aspect-square border border-slate">
            <!-- Grid: concentric utilisation rings at 25 / 50 / 75 / 100% -->
            <circle cx="100" cy="100" :r="22.5" class="fill-none stroke-slate/30" />
            <circle cx="100" cy="100" :r="45" class="fill-none stroke-slate/30" />
            <circle cx="100" cy="100" :r="67.5" class="fill-none stroke-slate/30" />
            <circle cx="100" cy="100" :r="90" class="fill-none stroke-ui-bad/40" stroke-dasharray="2 2" />
            <!-- Axes -->
            <line x1="10" y1="100" x2="190" y2="100" class="stroke-slate/40" stroke-width="0.5" />
            <line x1="100" y1="10" x2="100" y2="190" class="stroke-slate/40" stroke-width="0.5" />
            <!-- Sample dots -->
            <circle
              v-for="(s, i) in friction.samples"
              :key="`gg-${i}-${s.gLat.toFixed(3)}-${s.gLong.toFixed(3)}`"
              :cx="ggProject(s).x"
              :cy="ggProject(s).y"
              r="0.8"
              class="fill-ui-good"
              opacity="0.55"
            />
            <!-- Axis labels -->
            <text x="195" y="103" class="fill-slate text-[6px] font-mono">+gLat</text>
            <text x="3"   y="103" class="fill-slate text-[6px] font-mono">−gLat</text>
            <text x="102" y="13"  class="fill-slate text-[6px] font-mono">accel</text>
            <text x="102" y="195" class="fill-slate text-[6px] font-mono">brake</text>
          </svg>
          <div class="text-[10px] text-slate text-center mt-1 italic">
            Inner rings 25 / 50 / 75 % utilisation · dashed = limit
          </div>
        </div>

        <!-- Utilisation histogram -->
        <div class="flex flex-col">
          <div class="text-small text-slate mb-2 tracking-widest uppercase">Utilisation Histogram</div>
          <div class="flex-grow flex items-end gap-1 border-b border-slate/40 pb-1 min-h-[120px]">
            <div
              v-for="(pct, i) in friction.histogram_pct"
              :key="`bin-${i * 10}`"
              class="flex-1 relative"
              :title="`${i*10}–${(i+1)*10}% utilisation: ${pct}% of frames`"
            >
              <div
                class="w-full transition-all"
                :class="i < 3 ? 'bg-slate/60'
                      : i < 6 ? 'bg-ui-info/70'
                      : i < 8 ? 'bg-amber/80'
                      : 'bg-ui-good'"
                :style="{ height: `${Math.min(100, pct * 4)}%` }"
              ></div>
              <div class="text-[8px] text-center text-slate mt-1">{{ i*10 }}</div>
            </div>
          </div>
          <div class="text-[10px] text-slate mt-2 italic leading-tight">
            % of session frames in each grip-utilisation band. Bentley archetype: drivers who never reach the right-hand bins aren't using the car. The session above sits at
            <span class="text-white font-bold">
              {{ friction.histogram_pct.slice(7).reduce((a,b) => a+b, 0).toFixed(0) }}%
            </span>
            in the peak band (70%+).
          </div>
        </div>
      </div>

      <div v-else class="text-small text-slate italic p-3 text-center">
        Drive a flying lap to populate the friction-circle scatter.
      </div>
    </CyberPanel>

    <template #floating>
      <CoachFloat
        v-if="data"
        :emotion="getEmotion()"
        :text="getCoachLine()"
        :key="getCoachLine()"
      />
    </template>
  </PageShell>
</template>

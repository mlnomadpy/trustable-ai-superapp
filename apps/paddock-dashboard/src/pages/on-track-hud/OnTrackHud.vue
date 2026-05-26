<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useKeyboard } from '@/shared/lib/useKeyboard'
import { useRouter } from 'vue-router'
import { useCueStore } from '@/features/coach-interaction/model/cueStore'
import { useAudioStore } from '@/features/audio-playback/model/audioStore'
import { useSessionStore } from '@/entities/session/model/sessionStore'
import { useTelemetryStore } from '@/entities/session/model/telemetryStore'
import { useLapDerivation } from '@/entities/session/model/useLapDerivation'
import { useBridgeStore } from '@/shared/api/bridgeStore'
import { bridge } from '@/shared/api/bridge'
import { useLapTimeStore } from '@/entities/lap-time/model/lapTimeStore'
import { formatLapTime } from '@/shared/lib/lap'
import GripBar from '@/widgets/hud/GripBar.vue'
import HudTrackMap from '@/widgets/hud/HudTrackMap.vue'
import HudCornerTile from '@/widgets/hud/HudCornerTile.vue'
import CueBand from '@/features/coach-interaction/ui/CueBand.vue'
import CyberButton from '@/shared/ui/core/CyberButton.vue'
import CyberConfirmDialog from '@/shared/ui/core/CyberConfirmDialog.vue'
import CyberModal from '@/shared/ui/core/CyberModal.vue'
import SessionStartPicker from '@/widgets/session-start/SessionStartPicker.vue'
import CoachVoiceButton from '@/widgets/coach-voice-button/CoachVoiceButton.vue'
import AgentTraceDrawer from './AgentTraceDrawer.vue'

const router = useRouter()
const audio = useAudioStore()
const cueStore = useCueStore()
const session = useSessionStore()
const telemetry = useTelemetryStore()
const bridgeStore = useBridgeStore()
const lapTime = useLapTimeStore()

const paused = ref(false)
const confirmingCancel = ref(false)
const cancellingSession = ref(false)

// Ref to the voice FAB so the `M` keybinding can trigger the same handler
// the touch surface uses. Driver-facing: tapping at speed is hostile, a
// physical/Bluetooth keyboard or steering-wheel macro is preferable.
const coachVoiceRef = ref<{ trigger: () => void; abort: () => void } | null>(null)

// ── Agent-trace drawer ────────────────────────────────────────────────────
// Slide-out panel on the right that shows which ADK coaching agents have
// fired this session, latency, success/failure. Toggled by `T` so it
// doesn't fight the cockpit at-speed. Polling lives inside the drawer
// component (only while open — battery-aware on Pixel 10).
const showAgentTrace = ref(false)
function toggleAgentTrace() {
  showAgentTrace.value = !showAgentTrace.value
  audio.playSfx(showAgentTrace.value ? 'cursor_select' : 'cursor_move')
}
function closeAgentTrace() {
  showAgentTrace.value = false
  audio.playSfx('cursor_move')
}

// ── Data-source check ───────────────────────────────────────────────────────
// The HUD is only useful if frames are actually streaming. On mount we
// poll /session/replay/status; if no frame has arrived after the grace
// window AND nothing is feeding the bridge (no replay, no live CAN),
// surface a "WAITING FOR DATA" overlay with a one-click START REPLAY
// affordance instead of pretending the cockpit is live.
interface ReplayStatus {
  running: boolean
  source_session_id?: string | null
  speed?: number
  loop?: boolean
}
const replayStatus = ref<ReplayStatus>({ running: false })

// The active session id can flip after mount when the user starts a replay
// from the WAITING-FOR-DATA overlay. Priority: explicit
// session.activeSessionId > active replay source > /health active_session_id.
// Including the replay source means the SSE subscribes within the replay-
// status poll cadence (~2s) instead of waiting for the slower /health poll
// (~5s) — closes the bug where REPLAY ACTIVE pill showed but telemetry
// frames never arrived because `sid` was still null.
const sid = computed(() =>
  session.activeSessionId
  ?? replayStatus.value.source_session_id
  ?? bridgeStore.health?.active_session_id
  ?? null,
)
const replayStatusError = ref<string | null>(null)
const mountedAt = ref<number>(Date.now())
const showReplayPicker = ref(false)
let replayPollTimer: number | null = null
const REPLAY_POLL_MS = 2_000
// Bumped from 2s -> 3s so the WAITING overlay doesn't flash on the
// quick handoff between /session/replay/start succeeding and the first
// SSE event arriving (typical ~300-1500ms on Pixel 10 over adb).
const NO_DATA_GRACE_MS = 3_000
// If no frame arrives within this window we log loudly so the user can
// see the failure mode in DevTools instead of staring at "WAITING".
const NO_DATA_WARN_MS = 5_000
const noDataWarned = ref(false)

async function pollReplayStatus() {
  try {
    replayStatus.value = await bridge.get<ReplayStatus>('/session/replay/status')
    replayStatusError.value = null
  } catch (e) {
    replayStatusError.value = String(e)
  }
}

const canConnected = computed(() => Boolean(bridgeStore.health?.can?.connected))
const hasFrame = computed(() => telemetry.firstFrameAt != null)

const nowMs = ref<number>(Date.now())
let nowTimer: number | null = null

const showWaitingOverlay = computed(() => {
  if (hasFrame.value) return false
  if (showReplayPicker.value) return false
  // Don't flash the overlay during the very first moments — give the SSE
  // a chance to deliver a frame first.
  if (nowMs.value - mountedAt.value < NO_DATA_GRACE_MS) return false
  if (replayStatus.value.running) return false
  if (canConnected.value) return false
  return true
})

const showReplayPill = computed(() => replayStatus.value.running)

function openReplayPicker() {
  showReplayPicker.value = true
  audio.playSfx('cursor_select')
}
function closeReplayPicker() {
  showReplayPicker.value = false
  audio.playSfx('cursor_move')
  // Refresh status immediately on close in case the user started a replay.
  void pollReplayStatus()
}

const distanceM = computed(() => telemetry.frame?.distance ?? 0)
const frictionPct = computed(() => {
  const g = telemetry.frame?.combo_g ?? 0
  return Math.min(100, Math.max(0, (g / 1.2) * 100))
})
const overPct = computed(() => frictionPct.value > 80 ? (frictionPct.value - 80) * 5 : 0)

// ── Live lap derivation ────────────────────────────────────────────────────
// The bridge SSE doesn't emit `lap_number` — only cumulative `distance`.
// We derive the active lap client-side using the track length returned
// by /session/<sid>/laps. The composable anchors on the first frame so
// it works regardless of when the HUD mounts vs replay start.
interface LapsResp {
  laps: Array<{ name: string; t_start: number; t_end: number; distance_m: number }>
  track_length_m?: number | null
}
const trackLengthM = ref<number | null>(null)
const { lapNumber: derivedLap, lapProgressPct, reset: resetLapDerivation } =
  useLapDerivation(telemetry, trackLengthM)

async function fetchTrackLength(thisSid: string) {
  try {
    const res = await bridge.get<LapsResp>(`/session/${thisSid}/laps`)
    trackLengthM.value = res.track_length_m ?? null
  } catch (e) {
    console.warn('[hud] fetchTrackLength failed:', e)
    trackLengthM.value = null
  }
}

// Telemetry-frame counter + age, used by the debug overlay so a
// silent SSE failure becomes visible without leaving the page.
const framesReceived = ref(0)
const lastFrameAt = ref<number | null>(null)
const lastFrameAgeMs = computed(() => {
  if (lastFrameAt.value == null) return null
  return Math.max(0, nowMs.value - lastFrameAt.value)
})

// ── Debug overlay (Shift+D) ────────────────────────────────────────────────
const showDebug = ref(false)

// Live best lap from the lap-time store. HUD uses single-decimal precision
// for at-speed readability; analytics screens use 3 decimals (per
// `shared/lib/lap.ts`).
const bestLapDisplay = computed(() => formatLapTime(lapTime.bestLapS, 1))

// ── Cockpit data gate ──────────────────────────────────────────────────────
// Until a frame actually arrives we hide the speed / grip / friction tiles
// rather than render a wall of "—". The minimap renders independently
// because it owns its own empty state.
const showCockpitData = computed(() => telemetry.firstFrameAt != null)

// Speed in MPH, integer for at-speed readability. Returns '—' when no
// frame has arrived yet (paired with `showCockpitData`).
const speedMph = computed(() => {
  const s = telemetry.frame?.speed
  if (s == null) return '—'
  return Math.round(s * 2.237).toString()
})

// Grip tone follows the at-speed safety rule: green normal, warn nearing
// the limit, bad over. Mirrors what the GripBar already paints.
const gripTone = computed<'good' | 'warn' | 'bad'>(() => {
  const p = frictionPct.value
  if (p >= 90) return 'bad'
  if (p >= 75) return 'warn'
  return 'good'
})

// Lap display string — derived value with fallback chain, kept here so
// the template stays declarative.
const lapDisplay = computed(() => {
  const fromFrame = telemetry.frame?.lap_number
  if (fromFrame != null) return String(fromFrame).padStart(2, '0')
  if (derivedLap.value != null) return String(derivedLap.value).padStart(2, '0')
  return '—'
})

const lapTotalDisplay = computed(() =>
  lapTime.laps.length > 0 ? `/${lapTime.laps.length}` : '',
)

const distKmDisplay = computed(() => {
  if (!showCockpitData.value) return '—'
  return (distanceM.value / 1000).toFixed(2)
})

let simInterval: number

onMounted(async () => {
  try {
    if (document.documentElement.requestFullscreen) {
      await document.documentElement.requestFullscreen()
    }
  } catch (e) {
    console.warn('Fullscreen rejected', e)
  }

  if (sid.value) {
    cueStore.open(sid.value)
    telemetry.open(sid.value)
    // Pull lap times so the HUD's best-lap tile shows real data instead of
    // a hardcoded placeholder. The store keeps state for the lifetime of
    // the session — Stage Clear / Lap Times Hall reuse it.
    lapTime.fetchLapTimes(sid.value)
    // Track length powers the client-side lap_number derivation. Without
    // it we keep showing "—" rather than inventing a fake lap 1.
    void fetchTrackLength(sid.value)
  }

  // Make sure /health is being polled (the bridge store is normally
  // started at app bootstrap, but the HUD is the one screen that *must*
  // see live can.connected status — kick it if it isn't already).
  if (!bridgeStore.isPolling) bridgeStore.startPolling()

  // Initial replay-status check + a 2s loop so the overlay reacts
  // promptly when the operator starts/stops a replay externally.
  mountedAt.value = Date.now()
  void pollReplayStatus()
  replayPollTimer = window.setInterval(pollReplayStatus, REPLAY_POLL_MS)

  // 250ms wall-clock tick — only needed so the grace-window computed
  // re-evaluates after NO_DATA_GRACE_MS. Cheap; killed on unmount.
  nowTimer = window.setInterval(() => { nowMs.value = Date.now() }, 250)

  simInterval = window.setInterval(() => {
    if (paused.value) return
    if (!cueStore.activeCue && cueStore.queue.length > 0) {
      cueStore.activeCue = cueStore.queue.shift()!
      setTimeout(() => { cueStore.activeCue = null }, 3000)
    }
  }, 100)
})

// Re-open the SSE / lap fetch whenever the active session id flips.
// Triggered by:
//   • Replay picker starting a session post-mount
//   • Live CAN connecting after mount
//   • The user navigating to /hud before sessionStore.startSession finished
watch(sid, (newSid, oldSid) => {
  if (newSid === oldSid) return
  if (oldSid) {
    cueStore.close()
    telemetry.close()
  }
  // Re-anchor lap derivation on sid flip — different session means a
  // different cumulative distance origin.
  resetLapDerivation()
  framesReceived.value = 0
  lastFrameAt.value = null
  noDataWarned.value = false
  trackLengthM.value = null
  if (newSid) {
    cueStore.open(newSid)
    telemetry.open(newSid)
    lapTime.fetchLapTimes(newSid)
    void fetchTrackLength(newSid)
  }
}, { immediate: false })

// Replay restart: the SSE may stay open but firstFrameAt resets when
// telemetry.open() is re-called OR when the bridge sends a fresh frame
// after a quiet window. We treat firstFrameAt flipping null -> number
// as "new run begins" and re-anchor the derivation.
watch(() => telemetry.firstFrameAt, (next, prev) => {
  if (next != null && prev == null) {
    resetLapDerivation()
    framesReceived.value = 0
    noDataWarned.value = false
  }
})

// Frame counter + age. We tap telemetry.frame.timestamp because it
// changes on every SSE event; firstFrameAt only changes once.
watch(() => telemetry.frame?.timestamp, (ts) => {
  if (ts == null) return
  framesReceived.value += 1
  lastFrameAt.value = Date.now()
})

// Warn loudly in DevTools if no frame arrives after NO_DATA_WARN_MS.
watch(nowMs, (n) => {
  if (noDataWarned.value) return
  if (telemetry.frame != null) return
  if (replayStatus.value.running !== true && !canConnected.value) return
  if (n - mountedAt.value < NO_DATA_WARN_MS) return
  noDataWarned.value = true
  // eslint-disable-next-line no-console
  console.error(
    `[hud] No SSE telemetry frame received after ${NO_DATA_WARN_MS}ms ` +
    `despite replay.running=${replayStatus.value.running} can=${canConnected.value} sid=${sid.value}`,
  )
})

onUnmounted(() => {
  cueStore.close()
  telemetry.close()
  clearInterval(simInterval)
  if (replayPollTimer != null) { clearInterval(replayPollTimer); replayPollTimer = null }
  if (nowTimer != null) { clearInterval(nowTimer); nowTimer = null }
  if (document.fullscreenElement) {
    document.exitFullscreen?.()
  }
})

const resumeSession = () => {
  confirmingCancel.value = false
  paused.value = false
  audio.playSfx('cursor_select')
}

const togglePause = () => {
  confirmingCancel.value = false
  paused.value = !paused.value
  audio.playSfx(paused.value ? 'cursor_move' : 'cancel')
}

const promptCancelSession = () => {
  if (cancellingSession.value) return
  confirmingCancel.value = true
  audio.playSfx('error_quiet')
}

const closeCancelPrompt = () => {
  confirmingCancel.value = false
  audio.playSfx('cursor_move')
}

const cancelSession = async () => {
  if (cancellingSession.value) return

  confirmingCancel.value = false
  cancellingSession.value = true
  audio.playSfx('cancel')

  try {
    await session.endSession()
    paused.value = false
    await router.push('/garage')
  } finally {
    cancellingSession.value = false
  }
}

useKeyboard((e: KeyboardEvent) => {
  if (cancellingSession.value) return

  if (confirmingCancel.value) {
    if (e.key === 'Enter' || e.key === 'y' || e.key === 'Y') {
      void cancelSession()
    } else if (e.key === 'Escape' || e.key === 'Backspace' || e.key === 'b' || e.key === 'n' || e.key === 'N') {
      closeCancelPrompt()
    }
    return
  }

  // Unified key contract (App.vue handles ESC -> router.back() globally).
  // The HUD's local pause overlay is bound to P; B/Backspace remain as
  // ergonomic aliases for resuming/dismissing the pause state without
  // leaving the page.
  if (e.key === 'p' || e.key === 'P') {
    togglePause()
  } else if (e.key === 't' || e.key === 'T') {
    toggleAgentTrace()
  } else if ((e.key === 'Backspace' || e.key === 'b' || e.key === 'B') && paused.value) {
    resumeSession()
  } else if ((e.key === 'Enter' || e.key === 'a' || e.key === 'A') && paused.value) {
    resumeSession()
  } else if ((e.key === 'c' || e.key === 'C') && (paused.value || telemetry.frame)) {
    promptCancelSession()
  } else if ((e.key === 'm' || e.key === 'M') && !paused.value) {
    // Talk-to-coach hotkey. Skipped during pause so the mic doesn't fight
    // the pause overlay's own key handling.
    coachVoiceRef.value?.trigger()
  } else if (e.shiftKey && (e.key === 'D' || e.key === 'd')) {
    // Diagnostic overlay — frame count, last frame age, sid. Invaluable
    // when chasing "why is the HUD frozen" bugs without leaving the page.
    showDebug.value = !showDebug.value
    audio.playSfx('cursor_move')
  }
})
</script>

<template>
  <div class="viewport hud-root">

    <!-- ── TOP STRIP ──────────────────────────────────────────────────
         Single thin row at the top of the cockpit. REPLAY pill on the
         left (only when active), stream/key hint on the right. No
         frames, no nested padding — just a row. -->
    <header class="hud-top-strip" aria-hidden="false">
      <div class="hud-top-left">
        <div
          v-if="showReplayPill"
          class="replay-chip"
          role="status"
          aria-live="polite"
        >
          <span class="replay-dot" aria-hidden="true"></span>
          <span>REPLAY</span>
          <span v-if="replayStatus.source_session_id" class="replay-sid">{{ replayStatus.source_session_id }}</span>
        </div>
      </div>
      <div class="hud-top-right">
        <span
          class="stream-chip"
          :class="telemetry.frame ? 'stream-live' : 'stream-lost'"
          role="img"
          :aria-label="telemetry.frame ? 'Telemetry stream live' : 'Telemetry stream lost'"
        >
          <span class="stream-dot" :class="telemetry.frame ? 'active' : 'inactive'"></span>
          <span>{{ telemetry.frame ? 'LIVE' : 'LOST' }}</span>
        </span>
        <span class="key-hint" aria-hidden="true">
          ESC · P · T · ⇧D
        </span>
      </div>
    </header>

    <!-- ── CORNER TILES (top-left, top-right) ────────────────────────
         Minimalist label-over-numeric tiles. Hidden until a frame
         arrives so the user never stares at "—". -->
    <div v-if="showCockpitData" class="hud-tile hud-tile-tl">
      <HudCornerTile
        label="Lap"
        :value="lapDisplay"
        :unit="lapTotalDisplay || undefined"
        tone="silver"
        align="left"
      >
        <template #below>
          <div
            v-if="lapProgressPct != null"
            class="lap-progress"
            role="progressbar"
            :aria-valuenow="Math.round(lapProgressPct)"
            aria-valuemin="0"
            aria-valuemax="100"
            :aria-label="`Lap progress ${Math.round(lapProgressPct)} percent`"
          >
            <div class="lap-progress-fill" :style="{ width: lapProgressPct + '%' }"></div>
          </div>
        </template>
      </HudCornerTile>
    </div>

    <div v-if="showCockpitData" class="hud-tile hud-tile-tr">
      <HudCornerTile
        label="Best"
        :value="bestLapDisplay"
        :tone="lapTime.bestLapS != null ? 'good' : 'muted'"
        align="right"
      />
    </div>

    <!-- ── CENTRE: BIG SPEED ─────────────────────────────────────────
         The dominant element. Number + unit, nothing else. -->
    <div v-if="showCockpitData" class="hud-speed">
      <span class="hud-speed-num">{{ speedMph }}</span>
      <span class="hud-speed-unit">MPH</span>
    </div>

    <!-- ── CENTRE BOTTOM: GRIP STRIP ─────────────────────────────────
         A compact horizontal grip / slip readout under the speed.
         Replaces the giant vertical grip towers. -->
    <div v-if="showCockpitData" class="hud-grip-row">
      <GripBar :pct="frictionPct" :is-over="false" label="GRIP" class="hud-grip-bar-compact" />
      <GripBar :pct="overPct" :is-over="true" label="SLIP" class="hud-grip-bar-compact" />
    </div>

    <!-- ── BOTTOM STRIP: friction · dist · minimap · trace ──────────
         Single horizontal row at the bottom of the cockpit. All status
         data lives here as tiny chips so nothing competes with the
         centre speed. Voice FAB is fixed bottom-right by its own
         component, the minimap sits as a small left widget. -->
    <footer class="hud-bottom-strip">
      <div class="hud-bottom-left">
        <HudTrackMap
          track="sonoma"
          :pos-m="distanceM"
          :lat="telemetry.frame?.lat ?? null"
          :lon="telemetry.frame?.lon ?? null"
          class="hud-minimap"
        />
      </div>

      <div v-if="showCockpitData" class="hud-bottom-center">
        <HudCornerTile
          label="Friction"
          :value="frictionPct.toFixed(0)"
          unit="%"
          :tone="gripTone"
        />
        <span class="hud-bottom-sep" aria-hidden="true"></span>
        <HudCornerTile
          label="Dist"
          :value="distKmDisplay"
          unit="km"
          tone="silver"
        />
      </div>

      <div class="hud-bottom-right">
        <button
          type="button"
          class="hud-icon-btn"
          :class="showAgentTrace ? 'is-open' : ''"
          :aria-label="showAgentTrace ? 'Close agent trace' : 'Open agent trace'"
          :aria-expanded="showAgentTrace"
          @click="toggleAgentTrace"
        >
          <span aria-hidden="true">⟁</span>
          <span class="hud-icon-btn-label">TRACE</span>
        </button>
      </div>
    </footer>

    <!-- ── Slide-out drawer + cues + voice FAB (unchanged behaviour) ── -->
    <AgentTraceDrawer
      :open="showAgentTrace"
      :session-id="sid"
      @close="closeAgentTrace"
    />

    <CueBand :cue="cueStore.activeCue" />

    <!-- Voice coach FAB. Bottom-RIGHT fixed — bottom-left is now the
         home of the minimap in the new minimalist layout, and the FAB
         is the only persistent primary affordance on the page. Hidden
         while a blocking overlay is up so it doesn't collide with the
         WAITING-FOR-DATA or PAUSE modal. Hotkey: M. -->
    <CoachVoiceButton
      v-if="!showWaitingOverlay && !paused"
      ref="coachVoiceRef"
      mode="toggle"
      position="fixed-br"
    />
    
    <!-- HIGH CONTRAST PAUSE MODAL -->
    <div v-if="paused" class="pause-overlay">
      <h2 class="text-[clamp(40px,10vmin,80px)] text-ui-warn font-title mb-12 animate-pulse tracking-[0.4em] font-black">PAUSED</h2>
      <p class="pause-copy">
        Resume the live run, or cancel this session and head back to the garage.
      </p>
      <div class="pause-actions">
        <CyberButton @click="promptCancelSession" :loading="cancellingSession" variant="danger" size="lg" fluid>
          CANCEL SESSION
        </CyberButton>
        <CyberButton @click="resumeSession" :disabled="cancellingSession" variant="secondary" size="lg" fluid>
          RESUME SESSION
        </CyberButton>
      </div>
    </div>

    <CyberConfirmDialog
      :open="confirmingCancel"
      title="CANCEL SESSION"
      message="End the current live session and return to the garage?"
      confirmLabel="CANCEL"
      cancelLabel="KEEP RUNNING"
      variant="danger"
      @confirm="cancelSession"
      @cancel="closeCancelPrompt"
    />

    <!-- WAITING FOR DATA overlay — surfaces when the SSE produced no
         frames after the grace window AND nothing is feeding the bridge
         (no replay, no CAN). One click starts a replay; CAN is hardware
         so we just explain. Dismisses automatically the moment a frame
         arrives or a replay starts. -->
    <div v-if="showWaitingOverlay" class="waiting-overlay" role="alertdialog" aria-labelledby="hud-waiting-title">
      <div class="waiting-card">
        <h2 id="hud-waiting-title" class="waiting-title">WAITING FOR DATA</h2>
        <p class="waiting-copy">
          No telemetry frames are arriving on the SSE stream. Start a
          replay from a recorded session, or connect the CANable to your
          car so the bridge can ingest live frames.
        </p>
        <div v-if="replayStatusError" class="waiting-error">
          Bridge status check failed: {{ replayStatusError }}
        </div>
        <div class="waiting-actions">
          <CyberButton variant="primary" size="lg" fluid @click="openReplayPicker">
            START REPLAY
          </CyberButton>
          <CyberButton variant="secondary" size="lg" fluid disabled>
            CONNECT CAN (HARDWARE)
          </CyberButton>
        </div>
        <p class="waiting-hint">
          CAN: <span :class="canConnected ? 'text-ui-good' : 'text-ui-bad'">
            {{ canConnected ? 'CONNECTED' : 'DISCONNECTED' }}
          </span>
          · REPLAY: <span :class="replayStatus.running ? 'text-ui-good' : 'text-slate'">
            {{ replayStatus.running ? 'RUNNING' : 'IDLE' }}
          </span>
        </p>
      </div>
    </div>

    <!-- DATA DEBUG overlay — Shift+D. Cheap, read-only, gives operators
         the three numbers that matter when chasing "why no telemetry":
         the latest frame timestamp, total frame count since mount, and
         age of the last frame in ms. -->
    <div v-if="showDebug" class="data-debug" aria-live="polite">
      <div class="data-debug-row"><span>sid</span><b>{{ sid ?? '—' }}</b></div>
      <div class="data-debug-row"><span>frames</span><b>{{ framesReceived }}</b></div>
      <div class="data-debug-row">
        <span>ts</span>
        <b>{{ telemetry.frame?.timestamp != null ? telemetry.frame.timestamp.toFixed(3) : '—' }}</b>
      </div>
      <div class="data-debug-row">
        <span>age</span>
        <b :class="(lastFrameAgeMs ?? 0) > 1500 ? 'text-ui-bad' : 'text-ui-good'">
          {{ lastFrameAgeMs != null ? `${lastFrameAgeMs}ms` : '—' }}
        </b>
      </div>
      <div class="data-debug-row"><span>dist</span><b>{{ distanceM.toFixed(1) }}m</b></div>
      <div class="data-debug-row"><span>trkL</span><b>{{ trackLengthM != null ? `${trackLengthM}m` : '—' }}</b></div>
      <div class="data-debug-row"><span>lap</span><b>{{ derivedLap ?? '—' }} ({{ lapProgressPct != null ? Math.round(lapProgressPct) : '—' }}%)</b></div>
      <div class="data-debug-row"><span>replay</span><b>{{ replayStatus.running ? 'RUN' : 'IDLE' }}</b></div>
      <div class="data-debug-row"><span>can</span><b>{{ canConnected ? 'UP' : 'DN' }}</b></div>
    </div>

    <!-- Replay picker — re-uses the existing widget. Once a replay starts
         the bridge sets state.active_session_id to the source id, which
         the SSE already follows; the overlay dismisses on first frame. -->
    <CyberModal
      :open="showReplayPicker"
      title="START REPLAY"
      size="lg"
      @close="closeReplayPicker"
    >
      <SessionStartPicker />
    </CyberModal>
  </div>
</template>

<style scoped>
/* ── HUD root ───────────────────────────────────────────────────────
   Single unit (`--hud-gap`) drives every gap, padding, and inset in
   the cockpit. Change the clamp once, the whole layout breathes
   together. */
.hud-root {
  --hud-gap: clamp(8px, 1.5vmin, 16px);
  position: relative;
  width: 100%;
  height: 100%;
  background: #050508;
  color: var(--color-silver);
  font-family: var(--font-ui);
  overflow: hidden;
  padding: calc(max(var(--safe-top),    var(--hud-gap)))
           calc(max(var(--safe-right),  var(--hud-gap)))
           calc(max(var(--safe-bottom), var(--hud-gap)))
           calc(max(var(--safe-left),   var(--hud-gap)));
}

/* ── Top strip ──────────────────────────────────────────────────── */
.hud-top-strip {
  position: absolute;
  top: calc(max(var(--safe-top), var(--hud-gap)));
  left: calc(max(var(--safe-left), var(--hud-gap)));
  right: calc(max(var(--safe-right), var(--hud-gap)));
  z-index: 40;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--hud-gap);
  min-height: 28px;
  pointer-events: none;
}

.hud-top-left,
.hud-top-right {
  display: inline-flex;
  align-items: center;
  gap: var(--hud-gap);
  pointer-events: auto;
}

.stream-chip {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 4px 10px;
  border: 1px solid color-mix(in srgb, var(--color-slate) 35%, transparent);
  border-radius: 4px;
  font-family: var(--font-ui);
  font-weight: 800;
  font-size: clamp(10px, 1.6vmin, 13px);
  letter-spacing: 0.22em;
  text-transform: uppercase;
  min-height: 28px;
}

.stream-live { color: var(--color-ui-good); }
.stream-lost {
  color: var(--color-ui-bad);
  animation: pulse-pip 1.4s ease-in-out infinite;
}

.stream-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  display: inline-block;
}
.stream-dot.active {
  background: var(--color-ui-good);
  box-shadow: 0 0 8px var(--color-ui-good);
}
.stream-dot.inactive {
  background: var(--color-ui-bad);
}

.key-hint {
  font-family: var(--font-mono);
  font-size: clamp(10px, 1.4vmin, 12px);
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: color-mix(in srgb, var(--color-slate) 70%, transparent);
  white-space: nowrap;
}

/* Replay chip in top-left — the only non-silver/green element up top
   to flag "you're not looking at live data". */
.replay-chip {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 4px 10px;
  border: 1px solid color-mix(in srgb, var(--color-ui-warn) 60%, transparent);
  background: color-mix(in srgb, var(--color-ui-warn) 14%, transparent);
  color: var(--color-ui-warn);
  font-family: var(--font-ui);
  font-weight: 800;
  font-size: clamp(10px, 1.6vmin, 13px);
  letter-spacing: 0.22em;
  text-transform: uppercase;
  border-radius: 4px;
  min-height: 28px;
  max-width: min(48vw, 420px);
}

.replay-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--color-ui-warn);
  box-shadow: 0 0 8px var(--color-ui-warn);
  animation: pulse-pip 2s ease-in-out infinite;
}

.replay-sid {
  font-family: var(--font-mono);
  color: var(--color-silver);
  letter-spacing: 0.04em;
  text-transform: none;
  opacity: 0.85;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 28ch;
}

/* ── Corner tiles ───────────────────────────────────────────────── */
.hud-tile {
  position: absolute;
  z-index: 20;
}

.hud-tile-tl {
  top: calc(max(var(--safe-top), var(--hud-gap)) + 36px);
  left: calc(max(var(--safe-left), var(--hud-gap)));
  min-width: clamp(120px, 18vmin, 200px);
}

.hud-tile-tr {
  top: calc(max(var(--safe-top), var(--hud-gap)) + 36px);
  right: calc(max(var(--safe-right), var(--hud-gap)));
  min-width: clamp(120px, 18vmin, 200px);
}

.lap-progress {
  margin-top: 6px;
  height: 3px;
  width: 100%;
  background: color-mix(in srgb, var(--color-slate) 22%, transparent);
  border-radius: 2px;
  overflow: hidden;
}

.lap-progress-fill {
  height: 100%;
  background: var(--color-ui-good);
  transition: width var(--duration-fast) linear;
}

/* ── Centre speed ───────────────────────────────────────────────── */
.hud-speed {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  pointer-events: none;
  /* Reserve room above / below for the strips and grip row. */
  padding-block: clamp(80px, 14vh, 160px);
}

.hud-speed-num {
  font-family: var(--font-nums);
  font-weight: 900;
  font-size: clamp(140px, 32vmin, 360px);
  line-height: 0.9;
  letter-spacing: -0.04em;
  color: #fff;
  text-shadow: 0 0 60px rgba(255,255,255,0.08);
}

.hud-speed-unit {
  margin-top: clamp(4px, 0.8vmin, 12px);
  font-family: var(--font-ui);
  font-weight: 800;
  font-size: clamp(14px, 2.4vmin, 24px);
  letter-spacing: 0.5em;
  color: color-mix(in srgb, var(--color-slate) 80%, transparent);
  text-transform: uppercase;
}

/* ── Compact grip row, anchored just below the speed numeral ─────── */
.hud-grip-row {
  position: absolute;
  left: 50%;
  bottom: clamp(96px, 14vh, 160px);
  transform: translateX(-50%);
  display: flex;
  align-items: flex-end;
  justify-content: center;
  gap: clamp(16px, 3vmin, 32px);
  z-index: 15;
  pointer-events: none;
}

:deep(.hud-grip-bar-compact .grip-bar-container) {
  gap: clamp(6px, 1vmin, 10px);
}

:deep(.hud-grip-bar-compact .grip-bar) {
  width: clamp(14px, 2vmin, 22px);
  height: clamp(60px, 9vh, 110px);
}

:deep(.hud-grip-bar-compact .grip-label) {
  font-size: clamp(9px, 1.4vmin, 12px);
  letter-spacing: 0.18em;
}

/* ── Bottom strip ──────────────────────────────────────────────── */
.hud-bottom-strip {
  position: absolute;
  left: calc(max(var(--safe-left), var(--hud-gap)));
  right: calc(max(var(--safe-right), var(--hud-gap)));
  bottom: calc(max(var(--safe-bottom), var(--hud-gap)));
  z-index: 30;
  display: grid;
  grid-template-columns: auto 1fr auto;
  align-items: end;
  gap: var(--hud-gap);
}

.hud-bottom-left {
  display: flex;
  align-items: flex-end;
}

.hud-bottom-center {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: clamp(20px, 4vmin, 48px);
}

.hud-bottom-sep {
  width: 1px;
  height: clamp(28px, 5vmin, 48px);
  background: color-mix(in srgb, var(--color-slate) 30%, transparent);
}

.hud-bottom-right {
  display: inline-flex;
  align-items: flex-end;
  justify-content: flex-end;
  /* Reserve clearance for the 64px voice FAB which lives in this
     corner. The TRACE button sits above the FAB. */
  padding-bottom: calc(64px + var(--hud-gap));
}

.hud-minimap {
  width: clamp(80px, 14vmin, 120px);
  height: clamp(80px, 14vmin, 120px);
  opacity: 0.85;
  filter: drop-shadow(0 0 12px rgba(0,0,0,0.6));
}

.hud-icon-btn {
  min-width: 56px;
  min-height: 44px;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 0 12px;
  border: 1px solid color-mix(in srgb, var(--color-slate) 40%, transparent);
  background: rgba(5, 5, 8, 0.6);
  color: var(--color-silver);
  font-family: var(--font-ui);
  font-weight: 800;
  letter-spacing: 0.2em;
  font-size: clamp(11px, 1.8vmin, 13px);
  text-transform: uppercase;
  border-radius: 4px;
  cursor: pointer;
  transition: transform var(--duration-fast) ease,
              border-color var(--duration-fast) ease,
              color var(--duration-fast) ease;
}

.hud-icon-btn:hover,
.hud-icon-btn:focus-visible {
  transform: translateY(-1px);
  border-color: color-mix(in srgb, var(--color-ui-good) 60%, transparent);
  color: var(--color-ui-good);
}

.hud-icon-btn.is-open {
  border-color: color-mix(in srgb, var(--color-ui-good) 80%, transparent);
  color: var(--color-ui-good);
  box-shadow: 0 0 12px color-mix(in srgb, var(--color-ui-good) 30%, transparent);
}

.hud-icon-btn-label {
  letter-spacing: 0.22em;
}

@keyframes pulse-pip {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.6; transform: scale(0.8); }
}

.pause-overlay {
  position: absolute;
  inset: 0;
  background: rgba(5, 5, 8, 0.98);
  z-index: 200;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  backdrop-filter: blur(20px);
}

.pause-copy {
  max-width: 28ch;
  margin: 0 0 clamp(20px, 4vh, 32px);
  text-align: center;
  color: var(--color-slate);
  font-size: clamp(14px, 2.8vmin, 22px);
  line-height: 1.4;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.pause-actions {
  display: grid;
  gap: clamp(12px, 2vh, 20px);
  width: min(92vw, 460px);
}

@media (min-width: 640px) {
  .pause-actions {
    grid-template-columns: 1fr 1fr;
  }
}

/* WAITING-FOR-DATA overlay — full-bleed, blocks the HUD until a frame
   arrives or the user starts a replay. */
.waiting-overlay {
  position: absolute;
  inset: 0;
  z-index: 250;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(5, 5, 8, 0.94);
  backdrop-filter: blur(16px);
  padding: clamp(16px, 4vmin, 32px);
}

.waiting-card {
  width: min(92vw, 640px);
  border: 1px solid color-mix(in srgb, var(--color-ui-warn) 50%, transparent);
  background: var(--color-ink);
  padding: clamp(20px, 4vmin, 36px);
  display: flex;
  flex-direction: column;
  gap: clamp(12px, 2vh, 20px);
}

.waiting-title {
  color: var(--color-ui-warn);
  font-family: var(--font-title);
  font-weight: 900;
  font-size: clamp(28px, 6vmin, 48px);
  letter-spacing: 0.3em;
  margin: 0;
  text-align: center;
  animation: pulse-pip 2.2s ease-in-out infinite;
}

.waiting-copy {
  color: var(--color-silver);
  font-size: clamp(13px, 2.4vmin, 18px);
  line-height: 1.5;
  text-align: center;
  margin: 0;
}

.waiting-error {
  color: var(--color-ui-bad);
  font-family: var(--font-mono);
  font-size: clamp(11px, 1.8vmin, 13px);
  text-align: center;
}

.waiting-actions {
  display: grid;
  gap: clamp(10px, 1.6vh, 16px);
}

@media (min-width: 640px) {
  .waiting-actions {
    grid-template-columns: 1fr 1fr;
  }
}

.waiting-hint {
  color: var(--color-slate);
  font-family: var(--font-mono);
  font-size: clamp(10px, 1.6vmin, 12px);
  text-align: center;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  margin: 0;
}

/* Data debug overlay — sits just under the ESC corner hint, mono font,
   small, always above the HUD but below the pause / waiting modals. */
.data-debug {
  position: absolute;
  top: calc(max(var(--safe-top), var(--space-sm)) + 96px);
  right: calc(max(var(--safe-right), var(--space-sm)));
  z-index: 60;
  display: grid;
  grid-template-columns: auto auto;
  gap: 2px 12px;
  padding: 8px 12px;
  border: 1px solid color-mix(in srgb, var(--color-slate) 50%, transparent);
  background: rgba(5, 5, 8, 0.85);
  color: var(--color-silver);
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.04em;
  pointer-events: none;
  min-width: 200px;
}

.data-debug-row {
  display: contents;
}

.data-debug-row > span {
  color: var(--color-slate);
  text-transform: uppercase;
  letter-spacing: 0.12em;
}

.data-debug-row > b {
  font-weight: 700;
  text-align: right;
}
</style>

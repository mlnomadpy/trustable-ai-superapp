<script setup lang="ts">
/**
 * SessionStartPicker — pick a recorded session and start a replay.
 *
 * Calls the bridge's replay endpoints (bp_replay.py shipped in PR #36):
 *   POST /session/replay/start  {source_session_id, speed, loop}
 *   POST /session/replay/stop
 *   GET  /session/replay/status
 *
 * Once a replay is running the bridge sets state.active_session_id to the
 * source id, so PitStall.vue's telemetryStore.open(h.active_session_id) picks
 * the live SSE up with no further wiring.
 *
 * Polling cadence:
 *   • /sessions on mount + every 30 s (rarely changes)
 *   • /session/replay/status every 2 s while mounted
 */
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { bridge } from '@/shared/api/bridge'
import type { SessionSummary } from '@/shared/types/bridge'
import Frame from '@/shared/ui/core/Frame.vue'
import CyberButton from '@/shared/ui/core/CyberButton.vue'

interface ReplayStatus {
  running: boolean
  source_session_id?: string | null
  speed?: number
  loop?: boolean
  frame_idx?: number
  total_frames?: number
  elapsed_s?: number
  est_remaining_s?: number
}

const router = useRouter()

const sessions = ref<SessionSummary[]>([])
const sessionsLoading = ref(true)
const sessionsError = ref<string | null>(null)
const bridgeReachable = ref(true)

const selectedSessionId = ref<string>('')
const speed = ref<number>(1)
const loop = ref<boolean>(false)

const status = ref<ReplayStatus>({ running: false })
const statusError = ref<string | null>(null)

const startBusy = ref(false)
const stopBusy = ref(false)
const toast = ref<string | null>(null)
let toastTimer: number | null = null

const SPEED_OPTIONS = [0.5, 1, 2, 5, 10]
const PIT_STALL_ROUTE = '/garage/pit-stall'
const PREFERRED_DEFAULT = 'track-sonoma-2026-05-23-1'

const sortedSessions = computed(() =>
  [...sessions.value].sort((a, b) => {
    const ta = a.started_at ? Date.parse(a.started_at) : 0
    const tb = b.started_at ? Date.parse(b.started_at) : 0
    return tb - ta
  })
)

const selectedSummary = computed(() =>
  sessions.value.find(s => s.session_id === selectedSessionId.value) ?? null
)

const progressPct = computed(() => {
  const total = status.value.total_frames || 0
  const idx = status.value.frame_idx || 0
  if (total <= 0) return 0
  return Math.min(100, Math.max(0, (idx / total) * 100))
})

function showToast(msg: string) {
  toast.value = msg
  if (toastTimer) clearTimeout(toastTimer)
  toastTimer = window.setTimeout(() => { toast.value = null }, 4000)
}

async function fetchSessions() {
  try {
    const res = await bridge.get<{ sessions: SessionSummary[] }>('/sessions?limit=50')
    sessions.value = Array.isArray(res?.sessions) ? res.sessions : []
    sessionsError.value = null
    bridgeReachable.value = true

    // Default-select preferred session if present, else newest.
    if (!selectedSessionId.value || !sessions.value.some(s => s.session_id === selectedSessionId.value)) {
      const preferred = sessions.value.find(s => s.session_id === PREFERRED_DEFAULT)
      if (preferred) {
        selectedSessionId.value = preferred.session_id
      } else if (sortedSessions.value.length > 0) {
        selectedSessionId.value = sortedSessions.value[0].session_id
      }
    }
  } catch (e) {
    const msg = String(e)
    sessionsError.value = msg
    if (msg.includes('503') || msg.toLowerCase().includes('failed to fetch') || msg.toLowerCase().includes('networkerror')) {
      bridgeReachable.value = false
    }
  } finally {
    sessionsLoading.value = false
  }
}

async function pollStatus() {
  try {
    status.value = await bridge.get<ReplayStatus>('/session/replay/status')
    statusError.value = null
    bridgeReachable.value = true
  } catch (e) {
    statusError.value = String(e)
    // Don't flip bridgeReachable on transient status errors — the /sessions
    // call is the source of truth for "bridge alive".
  }
}

async function onStart() {
  if (!selectedSessionId.value) return
  startBusy.value = true
  try {
    await bridge.post('/session/replay/start', {
      source_session_id: selectedSessionId.value,
      speed: speed.value,
      loop: loop.value,
    })
    // Optimistically refresh status, then route to Pit Stall.
    await pollStatus()
    router.push(PIT_STALL_ROUTE)
  } catch (e) {
    const msg = String(e)
    if (msg.includes('409')) {
      showToast('Replay already running — stop first.')
      await pollStatus()
    } else if (msg.includes('404')) {
      showToast('Selected session has no telemetry rows.')
    } else if (msg.includes('503')) {
      showToast('Bridge has no database — cannot replay.')
    } else {
      showToast(`Could not start replay: ${msg}`)
    }
  } finally {
    startBusy.value = false
  }
}

async function onStop() {
  stopBusy.value = true
  try {
    await bridge.post('/session/replay/stop', {})
    await pollStatus()
  } catch (e) {
    showToast(`Could not stop replay: ${e}`)
  } finally {
    stopBusy.value = false
  }
}

let sessionsTimer: number | null = null
let statusTimer: number | null = null

onMounted(() => {
  fetchSessions()
  pollStatus()
  sessionsTimer = window.setInterval(fetchSessions, 30_000)
  statusTimer = window.setInterval(pollStatus, 2_000)
})

onUnmounted(() => {
  if (sessionsTimer) clearInterval(sessionsTimer)
  if (statusTimer) clearInterval(statusTimer)
  if (toastTimer) clearTimeout(toastTimer)
})

function formatStarted(iso: string | null): string {
  if (!iso) return '—'
  // Compact ISO display; avoid Intl heavy formatter to keep bundle small.
  return iso.replace('T', ' ').replace(/\..*$/, '').slice(0, 16)
}
</script>

<template>
  <Frame variant="default" padding="16px" class="w-full bg-ink/40">
    <h2 class="text-small text-ui-info tracking-[0.2em] font-black uppercase border-b border-slate/30 pb-2 mb-3">
      SIMULATED SESSION
    </h2>

    <!-- Bridge unreachable -->
    <div v-if="!bridgeReachable && !sessionsLoading" class="text-ui-warn text-small p-2 font-mono">
      Bridge not reachable — start it first (127.0.0.1:8765).
    </div>

    <!-- Loading -->
    <div v-else-if="sessionsLoading" class="text-slate text-small animate-pulse p-2">
      Loading sessions…
    </div>

    <!-- Empty list -->
    <div v-else-if="sessions.length === 0" class="text-slate text-small p-2">
      No recorded sessions yet. Import a VBO or run a real session first.
    </div>

    <!-- Main picker -->
    <div v-else class="flex flex-col gap-[clamp(8px,1.5vmin,14px)] w-full min-w-0">
      <label class="flex flex-col gap-1 text-small min-w-0">
        <span class="text-slate uppercase tracking-widest text-[10px]">Source session</span>
        <select
          v-model="selectedSessionId"
          class="bg-charcoal border border-slate text-white px-2 font-mono text-small min-h-[44px] w-full min-w-0 max-w-full"
          :disabled="status.running"
        >
          <option
            v-for="s in sortedSessions"
            :key="s.session_id"
            :value="s.session_id"
          >
            {{ s.session_id }} · {{ s.driver || '—' }} · {{ s.track || '—' }} · {{ formatStarted(s.started_at) }}
          </option>
        </select>
      </label>

      <div v-if="selectedSummary" class="text-[10px] text-slate/80 font-mono pl-1 break-words">
        car: {{ selectedSummary.car || '—' }} · laps: {{ selectedSummary.lap_count ?? 0 }}
        <span v-if="selectedSummary.best_lap_s != null"> · best: {{ selectedSummary.best_lap_s.toFixed(3) }}s</span>
      </div>

      <div class="flex gap-[clamp(8px,1.5vmin,14px)] items-end flex-wrap">
        <label class="flex flex-col gap-1 text-small">
          <span class="text-slate uppercase tracking-widest text-[10px]">Speed</span>
          <select
            v-model.number="speed"
            class="bg-charcoal border border-slate text-white px-2 font-mono text-small min-h-[44px] min-w-[88px]"
            :disabled="status.running"
          >
            <option v-for="opt in SPEED_OPTIONS" :key="opt" :value="opt">{{ opt }}×</option>
          </select>
        </label>

        <label class="flex items-center gap-2 text-small text-silver cursor-pointer min-h-[44px] px-2">
          <input
            v-model="loop"
            type="checkbox"
            class="accent-ui-good w-[20px] h-[20px]"
            :disabled="status.running"
          />
          <span class="uppercase tracking-widest text-[10px]">Loop</span>
        </label>
      </div>

      <!-- Running state -->
      <div v-if="status.running" class="flex flex-col gap-2 mt-2 min-w-0">
        <div class="text-ui-good text-small font-mono break-words">
          <span class="animate-pulse">● REPLAY</span>
          <span class="ml-2">{{ status.source_session_id || '—' }}</span>
        </div>
        <div class="text-small text-silver font-mono break-words">
          {{ status.frame_idx ?? 0 }} / {{ status.total_frames ?? 0 }} ·
          {{ (status.speed ?? 1).toFixed(1) }}× ·
          {{ (status.elapsed_s ?? 0).toFixed(0) }}s
          <span v-if="status.est_remaining_s != null">
            · ETA {{ status.est_remaining_s.toFixed(0) }}s
          </span>
        </div>
        <div class="h-1 bg-charcoal border border-slate/40 overflow-hidden">
          <div class="h-full bg-ui-good transition-all" :style="{ width: progressPct + '%' }"></div>
        </div>
        <div class="flex gap-2 mt-1">
          <CyberButton
            variant="danger"
            size="md"
            :loading="stopBusy"
            @click="onStop"
          >
            STOP SESSION
          </CyberButton>
          <CyberButton
            variant="secondary"
            size="md"
            @click="router.push(PIT_STALL_ROUTE)"
          >
            OPEN PIT STALL
          </CyberButton>
        </div>
      </div>

      <!-- Idle state -->
      <div v-else class="flex gap-2 mt-1">
        <CyberButton
          variant="primary"
          size="lg"
          fluid
          :disabled="!selectedSessionId"
          :loading="startBusy"
          @click="onStart"
        >
          START SIMULATED SESSION
        </CyberButton>
      </div>
    </div>

    <!-- Toast -->
    <div
      v-if="toast"
      class="mt-3 text-small text-ui-warn font-mono border border-ui-warn/40 bg-ink/80 px-2 py-1 break-words"
      role="alert"
    >
      {{ toast }}
    </div>
  </Frame>
</template>

<style scoped>
select {
  appearance: none;
}
</style>

<script setup lang="ts">
/**
 * HARDWARE DETAIL — tabbed layout for Pixel 10 landscape.
 *
 * Four tabs:
 *   1. BRIDGE  — engine + version + active session, sourced from /health.
 *   2. CAN     — connection state, fps, frames, DBC, signal catalogue,
 *                unknown IDs. The existing signal-browser table (with its
 *                drill-in modal + live LAST column) lives here.
 *   3. LLM     — LocalLLM transport, model, recent friction (latency /
 *                fallback / error rates) from /diagnostics/llm_friction.
 *   4. STORAGE — db backend + persisted session count from /sessions; the
 *                bridge does not expose disk-size info so that line is
 *                rendered "DATA UNAVAILABLE — bridge endpoint missing".
 *
 * Polling cadence:
 *   • /health           — every 5 s via shared bridgeStore.
 *   • /diagnostics/can  — 2 s while page is mounted (any tab).
 *   • /diagnostics/llm_friction — 10 s (single timer; not per tab switch).
 *   • /sessions         — once on mount + every 30 s.
 *   • SSE telemetry     — opened ONCE per page (in onMounted); persists
 *                         across tab switches because tabs use v-show, not
 *                         v-if. Closed in onUnmounted only.
 *
 * Keyboard: 1-4 selects tabs; B/Esc/Backspace = back; A/Enter drills into
 * the focused signal row (CAN tab only); arrows move the signal cursor.
 */
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useKeyboard } from '@/shared/lib/useKeyboard'
import { useRouter } from 'vue-router'
import { useAudioStore } from '@/features/audio-playback/model/audioStore'
import { bridge } from '@/shared/api/bridge'
import { useBridgeStore } from '@/shared/api/bridgeStore'
import { useTelemetryStore } from '@/entities/session/model/telemetryStore'

import PageShell from '@/shared/ui/PageShell.vue'
import CyberTabs from '@/shared/ui/core/CyberTabs.vue'
import CyberPanel from '@/shared/ui/core/CyberPanel.vue'
import CyberBox from '@/shared/ui/core/CyberBox.vue'

const router = useRouter()
const audio = useAudioStore()
const bridgeStore = useBridgeStore()
const telemetry = useTelemetryStore()

// ── Tabs ────────────────────────────────────────────────────────────────────
const TAB_LABELS = ['BRIDGE', 'CAN', 'LLM', 'STORAGE'] as const
const activeTab = ref(0)

// ── Signal catalogue (CAN tab) ──────────────────────────────────────────────
interface SignalCapability {
  id: number
  name: string
  unit: string
  hz: number
  group: string
  dbc: string
  /** From /signals/registry — e.g. "stateful", "variable", "rate". */
  semantics: string
  /** From /signals/registry — e.g. "static_obd2", "can_dbc", "derived". */
  discovery: string
  last: number | string
  baseValue: number
  variance: number
}

const signals = ref<SignalCapability[]>([])
// Unknown CAN IDs reported by the bridge — populated from /signals/registry
// when the ingest pipeline starts capturing frames whose IDs aren't in the
// DBC. Empty list = clean (everything decoded) OR no ingest active.
const unknownIds = ref<{ id: string; hz: number }[]>([])

const searchQuery = ref('')
const expandedGroups = ref<Record<string, boolean>>({})
const drilling = ref<SignalCapability | null>(null)
const cursorIndex = ref(0)

// Sort and group signals
const groupedSignals = computed(() => {
  const filtered = signals.value.filter(s =>
    s.name.toLowerCase().includes(searchQuery.value.toLowerCase()) ||
    s.dbc.toLowerCase().includes(searchQuery.value.toLowerCase())
  )

  const groups: Record<string, SignalCapability[]> = {}
  filtered.forEach(s => {
    if (!groups[s.group]) groups[s.group] = []
    groups[s.group].push(s)
  })

  return Object.keys(groups).sort().map(k => ({
    name: k,
    signals: groups[k].sort((a, b) => a.name.localeCompare(b.name)),
  }))
})

// Flatten for keyboard nav
const flatVisibleSignals = computed(() => {
  const list: SignalCapability[] = []
  groupedSignals.value.forEach(g => {
    if (expandedGroups.value[g.name] !== false) {
      list.push(...g.signals)
    }
  })
  return list
})

const totalSignals = computed(() => flatVisibleSignals.value.length)

watch(searchQuery, () => {
  cursorIndex.value = 0
})

const toggleGroup = (groupName: string) => {
  expandedGroups.value[groupName] = expandedGroups.value[groupName] === false
  cursorIndex.value = 0
}

// ── Diagnostics polling (CAN, LLM) ──────────────────────────────────────────
interface CanDiagnostics {
  connected?: boolean
  interface?: string | null
  channel?: string | null
  bitrate?: number | null
  frames_total?: number
  frames_unknown?: number
  frames_per_second?: number
  last_frame_age_s?: number | null
  car_config_path?: string | null
  dbc_path?: string | string[] | null
  signal_registry_count?: number
}

const canDiag = ref<CanDiagnostics | null>(null)
const canDiagMissing = ref(false)

interface LlmFrictionRoleAgg {
  role: string
  count: number
  p50_latency_ms: number | null
  fallback_rate: number
}
interface LlmFrictionResponse {
  count: number
  backend?: string
  p50_latency_ms: number | null
  p95_latency_ms: number | null
  error_rate: number
  fallback_rate: number
  truncation_rate: number
  by_role: LlmFrictionRoleAgg[]
  rows: Array<{
    id: number
    role: string
    backend: string
    latency_ms: number
    fell_back: boolean
    error: string
    ts: string
  }>
}

const llmFriction = ref<LlmFrictionResponse | null>(null)
const llmFrictionMissing = ref(false)
const llmFrictionError = ref<string | null>(null)

// ── Storage tab ─────────────────────────────────────────────────────────────
const sessionsCount = ref<number | null>(null)
const sessionsError = ref<string | null>(null)

const pollCanDiagnostics = async () => {
  try {
    canDiag.value = await bridge.get<CanDiagnostics>('/diagnostics/can')
    canDiagMissing.value = false
  } catch (e) {
    const msg = String(e)
    if (msg.includes('404') || msg.toLowerCase().includes('not found')) {
      canDiagMissing.value = true
    }
  }
}

const pollLlmFriction = async () => {
  try {
    llmFriction.value = await bridge.get<LlmFrictionResponse>('/diagnostics/llm_friction?limit=20&since_minutes=60')
    llmFrictionMissing.value = false
    llmFrictionError.value = null
  } catch (e) {
    const msg = String(e)
    llmFrictionError.value = msg
    if (msg.includes('404') || msg.toLowerCase().includes('not found')) {
      llmFrictionMissing.value = true
    }
  }
}

const pollSessions = async () => {
  try {
    const res = await bridge.get<{ sessions: unknown[]; count?: number }>('/sessions?limit=1')
    sessionsCount.value = typeof res.count === 'number'
      ? res.count
      : Array.isArray(res.sessions) ? res.sessions.length : 0
    sessionsError.value = null
  } catch (e) {
    sessionsError.value = String(e)
  }
}

// ── Live LAST column wiring (CAN tab) ───────────────────────────────────────
// Same alias map as before — the bridge SSE uses short legacy names for
// some of the wide-frame canonicals.
const FRAME_FIELD_ALIASES: Record<string, string> = {
  speed_ms:     'speed',
  brake_bar:    'brake_pressure',
  throttle_pct: 'throttle',
  steering_deg: 'steering',
  distance_m:   'distance',
}

const extractSignal = (
  frame: Record<string, unknown> | null | undefined,
  name: string,
): number | undefined => {
  if (!frame) return undefined
  const key = name.toLowerCase()
  if (key in frame) {
    const v = frame[key]
    return typeof v === 'number' ? v : undefined
  }
  const aliased = FRAME_FIELD_ALIASES[key]
  if (aliased && aliased in frame) {
    const v = frame[aliased]
    return typeof v === 'number' ? v : undefined
  }
  return undefined
}

const updateLiveValues = () => {
  const frame = telemetry.frame as unknown as Record<string, unknown> | null
  signals.value.forEach(s => {
    const v = extractSignal(frame, s.name)
    s.last = (typeof v === 'number' && Number.isFinite(v)) ? v.toFixed(2) : '—'
  })
}

// ── Keyboard ───────────────────────────────────────────────────────────────
useKeyboard((e: KeyboardEvent) => {
  // Drill-in modal swallows keys.
  if (drilling.value) {
    if (e.key === 'Escape' || e.key === 'Backspace' || e.key === 'b') {
      audio.playSfx('cancel')
      drilling.value = null
    }
    return
  }

  // Tab switching always available — Pixel 10 number row.
  if (e.key === '1') { audio.playSfx('cursor_move'); activeTab.value = 0; return }
  if (e.key === '2') { audio.playSfx('cursor_move'); activeTab.value = 1; return }
  if (e.key === '3') { audio.playSfx('cursor_move'); activeTab.value = 2; return }
  if (e.key === '4') { audio.playSfx('cursor_move'); activeTab.value = 3; return }

  // Search input takes priority — don't steal arrows from it.
  if (document.activeElement?.tagName === 'INPUT') {
    if (e.key === 'Escape') {
      (document.activeElement as HTMLElement).blur()
    }
    return
  }

  // Global back.
  if (e.key === 'Escape' || e.key === 'Backspace' || e.key === 'b') {
    audio.playSfx('cancel')
    router.back()
    return
  }

  // Signal nav only meaningful on CAN tab.
  if (activeTab.value !== 1) return

  if (e.key === 'ArrowDown') {
    if (cursorIndex.value < totalSignals.value - 1) {
      cursorIndex.value++
      audio.playSfx('cursor_move')
    }
  } else if (e.key === 'ArrowUp') {
    if (cursorIndex.value > 0) {
      cursorIndex.value--
      audio.playSfx('cursor_move')
    }
  } else if (e.key === 'Enter' || e.key === 'a') {
    if (flatVisibleSignals.value[cursorIndex.value]) {
      audio.playSfx('cursor_select')
      drilling.value = flatVisibleSignals.value[cursorIndex.value]
    }
  }
})

// ── Lifecycle ───────────────────────────────────────────────────────────────
let liveTimer: number | null = null
let canDiagTimer: number | null = null
let llmFrictionTimer: number | null = null
let sessionsTimer: number | null = null

onMounted(async () => {
  // Health is the source of truth for the BRIDGE tab — start polling.
  bridgeStore.startPolling()

  // Catalogue: /signals/registry returns per-signal metadata.
  try {
    const data = await bridge.get<{
      signals: Array<{ signal_id?: number; name: string; units?: string; expected_hz?: number; group?: string; semantics?: string; discovery?: string }>
      unknown_can_ids?: Array<{ id?: string; can_id?: string; hz?: number }>
    }>('/signals/registry')
    signals.value = data.signals.map((s, i) => ({
      id: s.signal_id ?? i,
      name: s.name,
      unit: s.units ?? 'n/a',
      hz: s.expected_hz ?? 10.0,
      group: s.group ?? 'misc',
      // `discovery` doubles as the DBC-source label in the table view
      // because the registry doesn't expose a separate dbc-file field.
      dbc: s.discovery ?? 'unknown',
      semantics: s.semantics ?? '—',
      discovery: s.discovery ?? '—',
      last: '—',
      baseValue: 0,
      variance: 0,
    }))
    if (Array.isArray(data.unknown_can_ids)) {
      unknownIds.value = data.unknown_can_ids.map(u => ({
        id: u.id ?? u.can_id ?? '?',
        hz: u.hz ?? 0,
      }))
    }
  } catch (_) {
    // Bridge offline — leave catalogue empty so the empty-state renders.
  }

  // SSE opens ONCE per page — not per tab switch. Tabs are v-show, so the
  // store retains the connection while you're on BRIDGE/LLM/STORAGE.
  telemetry.open('hardware-detail')

  liveTimer = window.setInterval(updateLiveValues, 200)            // 5 Hz LAST col
  canDiagTimer = window.setInterval(pollCanDiagnostics, 2_000)
  llmFrictionTimer = window.setInterval(pollLlmFriction, 10_000)
  sessionsTimer = window.setInterval(pollSessions, 30_000)

  // First fetch right away (don't wait for the first interval tick).
  pollCanDiagnostics()
  pollLlmFriction()
  pollSessions()
})

onUnmounted(() => {
  if (liveTimer) window.clearInterval(liveTimer)
  if (canDiagTimer) window.clearInterval(canDiagTimer)
  if (llmFrictionTimer) window.clearInterval(llmFrictionTimer)
  if (sessionsTimer) window.clearInterval(sessionsTimer)
  if (histTimer) window.clearInterval(histTimer)
  liveTimer = null
  canDiagTimer = null
  llmFrictionTimer = null
  sessionsTimer = null
  histTimer = null
  telemetry.close()
})

// ── Drill-in sparkline (CAN tab modal) ──────────────────────────────────────
const histBars = [' ', '▂', '▃', '▄', '▅', '▆', '▇', '█']
const drillHist = ref('')
const drillBuffer = ref<number[]>([])
let histTimer: number | null = null

const sampleDrill = () => {
  const sig = drilling.value
  if (!sig) return
  const frame = telemetry.frame as unknown as Record<string, unknown> | null
  const v = extractSignal(frame, sig.name)
  if (typeof v === 'number' && Number.isFinite(v)) {
    drillBuffer.value.push(v)
    if (drillBuffer.value.length > 30) drillBuffer.value.shift()
  }
  if (!drillBuffer.value.length) {
    drillHist.value = '—'.repeat(30)
    return
  }
  const lo = Math.min(...drillBuffer.value)
  const hi = Math.max(...drillBuffer.value)
  const range = Math.max(1e-6, hi - lo)
  drillHist.value = drillBuffer.value
    .map(v2 => histBars[Math.min(histBars.length - 1, Math.floor(((v2 - lo) / range) * (histBars.length - 1)))])
    .join('')
}

watch(drilling, (n) => {
  drillBuffer.value = []
  drillHist.value = ''
  if (n) {
    sampleDrill()
    histTimer = window.setInterval(sampleDrill, 200)
  } else if (histTimer) {
    window.clearInterval(histTimer)
    histTimer = null
  }
})

// ── Derived view-state ──────────────────────────────────────────────────────
const health = computed(() => bridgeStore.health)
const bridgeOk = computed(() => bridgeStore.health !== null && !bridgeStore.healthError)

const basename = (p?: string | string[] | null): string => {
  if (!p) return '—'
  if (Array.isArray(p)) {
    if (p.length === 0) return '—'
    const names = p.map(s => basename(s))
    return names.length === 1 ? names[0] : `${names[0]} (+${names.length - 1} more)`
  }
  const idx = Math.max(p.lastIndexOf('/'), p.lastIndexOf('\\'))
  return idx >= 0 ? p.slice(idx + 1) : p
}

const llmRecentErrors = computed(() => {
  if (!llmFriction.value?.rows) return []
  return llmFriction.value.rows.filter(r => r.error || r.fell_back).slice(0, 5)
})
</script>

<template>
  <PageShell
    title="HARDWARE DETAIL"
    :actions="[
      { label: 'DRILL', key: 'a', keyLabel: 'A' },
      { label: 'BACK', key: 'Escape', keyLabel: 'B', variant: 'warn' }
    ]"
    bg="neutral"
    :show-heading="false"
  >
    <div class="hardware-root flex flex-col h-full w-full gap-[1vmin]">

      <!-- Tab bar -->
      <CyberTabs
        v-model="activeTab"
        :tabs="TAB_LABELS"
        class="mx-2 shrink-0"
      />

      <!-- Tab content fills remaining height -->
      <div class="flex-1 min-h-0 mx-2 overflow-hidden">

        <!-- ── BRIDGE ─────────────────────────────────────────────────── -->
        <CyberPanel v-show="activeTab === 0" class="h-full flex flex-col gap-[1.5vmin] p-[2vmin] overflow-y-auto">
          <div class="text-small text-slate tracking-widest uppercase border-b border-slate/50 pb-1 shrink-0">
            BRIDGE STATUS
          </div>

          <div v-if="!bridgeOk && !health" class="p-3 border border-ui-bad/40 bg-ui-bad/5 text-small text-ui-bad tracking-wider uppercase">
            <div class="font-bold mb-1">BRIDGE UNREACHABLE</div>
            <div class="text-ui-bad/80 normal-case tracking-normal">
              {{ bridgeStore.healthError || 'No response from 127.0.0.1:8765 — daemon offline?' }}
            </div>
          </div>

          <div v-else-if="health" class="grid grid-cols-2 gap-x-6 gap-y-2 text-body font-mono">
            <div class="flex flex-col"><span class="text-slate text-small uppercase tracking-widest">Status</span><span class="text-ui-good font-bold">{{ health.status }}</span></div>
            <div class="flex flex-col"><span class="text-slate text-small uppercase tracking-widest">Version</span><span class="text-silver">{{ health.version }}</span></div>
            <div class="flex flex-col"><span class="text-slate text-small uppercase tracking-widest">Engine</span><span class="text-silver">{{ health.engine || '—' }}</span></div>
            <div class="flex flex-col"><span class="text-slate text-small uppercase tracking-widest">DB Backend</span><span class="text-silver">{{ health.duckdb ? 'duckdb / sqlite' : 'none' }}</span></div>
            <div class="flex flex-col"><span class="text-slate text-small uppercase tracking-widest">Active Session</span><span class="text-silver truncate">{{ health.active_session_id || '—' }}</span></div>
            <div class="flex flex-col"><span class="text-slate text-small uppercase tracking-widest">Coach</span><span class="text-silver">{{ health.coach || '—' }}</span></div>
            <div class="flex flex-col"><span class="text-slate text-small uppercase tracking-widest">Driver Level</span><span class="text-silver">{{ health.driver_level || '—' }}</span></div>
            <div class="flex flex-col"><span class="text-slate text-small uppercase tracking-widest">Simulator</span><span class="text-silver">{{ health.simulator?.running ? 'running' : 'idle' }}</span></div>
          </div>

          <div v-else class="text-slate text-small tracking-widest uppercase animate-pulse">
            connecting to bridge…
          </div>
        </CyberPanel>

        <!-- ── CAN ─────────────────────────────────────────────────────── -->
        <CyberPanel v-show="activeTab === 1" class="h-full flex flex-col gap-[1.5vmin] p-[2vmin]">
          <!-- CAN diagnostics summary -->
          <div v-if="canDiagMissing" class="p-2 border border-ui-warn/40 bg-ui-warn/5 text-small text-ui-warn tracking-wider uppercase shrink-0">
            DATA UNAVAILABLE — /diagnostics/can endpoint missing on this bridge build.
          </div>
          <div v-else-if="canDiag" class="grid grid-cols-4 gap-x-4 gap-y-1 text-small font-mono shrink-0 border-b border-slate/30 pb-2">
            <div><span class="text-slate uppercase tracking-widest">State</span> <span :class="canDiag.connected ? 'text-ui-good' : 'text-ui-bad'" class="font-bold">{{ canDiag.connected ? 'CONNECTED' : 'OFFLINE' }}</span></div>
            <div><span class="text-slate uppercase tracking-widest">FPS</span> <span class="text-white">{{ Math.round(canDiag.frames_per_second || 0) }}</span></div>
            <div><span class="text-slate uppercase tracking-widest">Total</span> <span class="text-white">{{ (canDiag.frames_total || 0).toLocaleString() }}</span></div>
            <div><span class="text-slate uppercase tracking-widest">Unknown</span> <span class="text-white">{{ canDiag.frames_unknown || 0 }}</span></div>
            <div class="col-span-2"><span class="text-slate uppercase tracking-widest">DBC</span> <span class="text-white truncate">{{ basename(canDiag.dbc_path) }}</span></div>
            <div class="col-span-2"><span class="text-slate uppercase tracking-widest">Car</span> <span class="text-white truncate">{{ basename(canDiag.car_config_path) }}</span></div>
          </div>
          <div v-else class="text-slate text-small tracking-widest uppercase animate-pulse shrink-0">querying /diagnostics/can…</div>

          <!-- Signals + Unknown IDs side-by-side -->
          <div class="flex gap-2 flex-1 min-h-0">
            <CyberBox variant="ink" border="slate" class="flex-1 flex flex-col text-body overflow-hidden p-2">
              <div class="flex justify-between items-center mb-2 gap-4 shrink-0">
                <div class="text-silver font-bold uppercase shrink-0">Signals</div>
                <input
                  v-model="searchQuery"
                  type="search"
                  inputmode="search"
                  autocomplete="off"
                  autocorrect="off"
                  autocapitalize="off"
                  spellcheck="false"
                  placeholder="SEARCH SIGNALS..."
                  class="bg-ink border border-slate text-silver px-2 py-1 w-full max-w-xs focus:outline-none focus:border-ui-good"
                />
              </div>

              <div class="overflow-y-auto flex-grow pr-2 scroll-smooth min-h-0">
                <table class="w-full text-left font-mono">
                  <thead>
                    <tr class="text-slate border-b border-charcoal">
                      <th class="pb-1 w-4"></th>
                      <th class="pb-1">NAME</th>
                      <th class="pb-1 text-right">UNIT</th>
                      <th class="pb-1 text-right">Hz</th>
                      <th class="pb-1 text-right">LAST</th>
                      <th class="pb-1">DBC</th>
                    </tr>
                  </thead>
                  <tbody v-for="g in groupedSignals" :key="g.name">
                    <tr class="bg-charcoal text-ui-info cursor-pointer hover:bg-slate/20" @click="toggleGroup(g.name)">
                      <td colspan="6" class="py-1 px-2 font-bold uppercase border-y border-ink">
                        <span class="mr-2">{{ expandedGroups[g.name] !== false ? '▼' : '▶' }}</span>
                        {{ g.name }} ({{ g.signals.length }})
                      </td>
                    </tr>
                    <template v-if="expandedGroups[g.name] !== false">
                      <tr v-for="s in g.signals" :key="s.id"
                          @click="drilling = s; cursorIndex = flatVisibleSignals.findIndex(fs => fs.id === s.id)"
                          class="cursor-pointer hover:bg-slate/20"
                          :class="flatVisibleSignals[cursorIndex]?.id === s.id ? 'bg-charcoal text-white' : 'text-silver'">
                        <td class="text-ui-good">{{ flatVisibleSignals[cursorIndex]?.id === s.id ? '▶' : '' }}</td>
                        <td class="font-bold truncate max-w-[clamp(60px,15vw,120px)]">{{ s.name }}</td>
                        <td class="text-right text-slate">{{ s.unit }}</td>
                        <td class="text-right">{{ s.hz.toFixed(1) }}</td>
                        <td class="text-right font-bold w-[40px]">{{ s.last }}</td>
                        <td class="truncate max-w-[clamp(48px,12vw,80px)]">{{ s.dbc }}</td>
                      </tr>
                    </template>
                  </tbody>
                </table>
                <div v-if="groupedSignals.length === 0" class="text-slate text-center mt-4 italic">
                  No signals match your search.
                </div>
              </div>
            </CyberBox>

            <CyberBox variant="ink" border="slate" class="flex flex-col text-body p-2 w-[clamp(80px,20vw,160px)] shrink-0 overflow-hidden">
              <div class="text-silver font-bold uppercase mb-2 border-b border-charcoal pb-1 shrink-0">Unknown CAN IDs</div>
              <div class="flex flex-col gap-1 font-mono overflow-y-auto">
                <div v-for="u in unknownIds" :key="u.id" class="flex flex-col text-slate">
                  <div class="flex justify-between text-white">
                    <span>{{ u.id }}</span>
                    <span>{{ u.hz }} Hz</span>
                  </div>
                  <span class="text-small">(no DBC entry)</span>
                </div>
                <div v-if="unknownIds.length === 0" class="text-slate/60 text-small italic">
                  (none — all frames decoded)
                </div>
              </div>
            </CyberBox>
          </div>
        </CyberPanel>

        <!-- ── LLM ─────────────────────────────────────────────────────── -->
        <CyberPanel v-show="activeTab === 2" class="h-full flex flex-col gap-[1.5vmin] p-[2vmin] overflow-y-auto">
          <div class="text-small text-slate tracking-widest uppercase border-b border-slate/50 pb-1 shrink-0">
            LOCALLLM STATUS
          </div>

          <div v-if="health?.litert" class="grid grid-cols-2 gap-x-6 gap-y-2 text-body font-mono shrink-0">
            <div class="flex flex-col"><span class="text-slate text-small uppercase tracking-widest">Loaded</span><span :class="health.litert.up ? 'text-ui-good' : 'text-ui-bad'" class="font-bold">{{ health.litert.up ? 'UP' : 'DOWN' }}</span></div>
            <div class="flex flex-col"><span class="text-slate text-small uppercase tracking-widest">Transport</span><span class="text-silver">{{ health.litert.transport || '—' }}</span></div>
            <div class="flex flex-col col-span-2"><span class="text-slate text-small uppercase tracking-widest">HTTP URL</span><span class="text-silver truncate">{{ health.litert.http_url || '—' }}</span></div>
            <div class="flex flex-col col-span-2"><span class="text-slate text-small uppercase tracking-widest">Model</span><span class="text-silver truncate">{{ health.litert.http_model || '—' }}</span></div>
          </div>
          <div v-else class="text-slate text-small tracking-widest uppercase shrink-0">
            waiting for /health…
          </div>

          <div class="text-small text-slate tracking-widest uppercase border-b border-slate/50 pb-1 shrink-0 mt-[1vmin]">
            FRICTION (LAST 60 MIN)
          </div>

          <div v-if="llmFrictionMissing" class="p-2 border border-ui-warn/40 bg-ui-warn/5 text-small text-ui-warn tracking-wider uppercase">
            DATA UNAVAILABLE — /diagnostics/llm_friction endpoint missing on this bridge build.
          </div>
          <div v-else-if="llmFriction" class="flex flex-col gap-[1vmin]">
            <div class="grid grid-cols-5 gap-2 text-small font-mono">
              <div class="flex flex-col"><span class="text-slate uppercase tracking-widest text-[10px]">Calls</span><span class="text-white">{{ llmFriction.count }}</span></div>
              <div class="flex flex-col"><span class="text-slate uppercase tracking-widest text-[10px]">p50 ms</span><span class="text-white">{{ llmFriction.p50_latency_ms != null ? llmFriction.p50_latency_ms.toFixed(0) : '—' }}</span></div>
              <div class="flex flex-col"><span class="text-slate uppercase tracking-widest text-[10px]">p95 ms</span><span class="text-white">{{ llmFriction.p95_latency_ms != null ? llmFriction.p95_latency_ms.toFixed(0) : '—' }}</span></div>
              <div class="flex flex-col"><span class="text-slate uppercase tracking-widest text-[10px]">Fallback</span><span :class="llmFriction.fallback_rate > 0.1 ? 'text-ui-warn' : 'text-white'">{{ (llmFriction.fallback_rate * 100).toFixed(0) }}%</span></div>
              <div class="flex flex-col"><span class="text-slate uppercase tracking-widest text-[10px]">Errors</span><span :class="llmFriction.error_rate > 0 ? 'text-ui-bad' : 'text-white'">{{ (llmFriction.error_rate * 100).toFixed(0) }}%</span></div>
            </div>

            <div v-if="llmRecentErrors.length > 0" class="border-t border-slate/30 pt-[1vmin]">
              <div class="text-small text-slate uppercase tracking-widest mb-1">Recent failures</div>
              <div class="flex flex-col gap-1 font-mono text-small max-h-[20vh] overflow-y-auto">
                <div v-for="r in llmRecentErrors" :key="r.id" class="flex gap-2 text-ui-warn">
                  <span class="text-slate w-[140px] truncate">{{ r.ts }}</span>
                  <span class="text-slate w-[80px] truncate">{{ r.role }}</span>
                  <span class="text-slate w-[60px] truncate">{{ r.backend }}</span>
                  <span class="truncate flex-1">{{ r.error || (r.fell_back ? '(fell back)' : '') }}</span>
                </div>
              </div>
            </div>
            <div v-else class="text-small text-slate italic">no failures in window</div>
          </div>
          <div v-else-if="llmFrictionError" class="text-small text-ui-warn font-mono">
            {{ llmFrictionError }}
          </div>
          <div v-else class="text-slate text-small tracking-widest uppercase animate-pulse">
            querying /diagnostics/llm_friction…
          </div>
        </CyberPanel>

        <!-- ── STORAGE ────────────────────────────────────────────────── -->
        <CyberPanel v-show="activeTab === 3" class="h-full flex flex-col gap-[1.5vmin] p-[2vmin] overflow-y-auto">
          <div class="text-small text-slate tracking-widest uppercase border-b border-slate/50 pb-1 shrink-0">
            STORAGE
          </div>

          <div class="grid grid-cols-2 gap-x-6 gap-y-2 text-body font-mono shrink-0">
            <div class="flex flex-col">
              <span class="text-slate text-small uppercase tracking-widest">DB Backend</span>
              <span class="text-silver">{{ health?.duckdb ? 'duckdb / sqlite' : 'none' }}</span>
            </div>
            <div class="flex flex-col">
              <span class="text-slate text-small uppercase tracking-widest">Recorded Sessions</span>
              <span v-if="sessionsError" class="text-ui-bad text-small">{{ sessionsError }}</span>
              <span v-else-if="sessionsCount === null" class="text-slate animate-pulse">…</span>
              <span v-else class="text-silver">{{ sessionsCount }}</span>
            </div>
          </div>

          <div class="p-2 border border-ui-warn/40 bg-ui-warn/5 text-small text-ui-warn tracking-wider uppercase">
            DATA UNAVAILABLE — bridge does not expose db file size or parquet cache info via /health. Add a /diagnostics/storage endpoint to populate this section.
          </div>
        </CyberPanel>

      </div>
    </div>

    <!-- Drill-In Modal (shared across tabs but only reachable from CAN tab) -->
    <div v-if="drilling" class="absolute inset-0 bg-black/80 z-50 flex items-center justify-center font-ui text-body text-silver" @click="drilling = null">
      <CyberBox variant="ink" border="slate" class="w-[clamp(280px,85vw,500px)] shadow-xl flex flex-col p-4 relative pixelated" @click.stop>
        <div class="text-body font-bold text-white uppercase border-b border-slate pb-1 mb-2">
          SIGNAL · {{ drilling.name }}
        </div>

        <div class="flex gap-4">
          <table class="w-1/2 text-left">
            <tr><td class="text-slate font-bold pb-1 w-[clamp(48px,12vw,80px)]">UNITS</td><td class="text-white pb-1">{{ drilling.unit }}</td></tr>
            <tr><td class="text-slate font-bold pb-1">SEMANTICS</td><td class="text-white pb-1">{{ drilling.semantics }}</td></tr>
            <tr><td class="text-slate font-bold pb-1">GROUP</td><td class="text-white pb-1">{{ drilling.group }}</td></tr>
            <tr><td class="text-slate font-bold pb-1">EXPECTED</td><td class="text-white pb-1">{{ drilling.hz }} Hz</td></tr>
            <tr><td class="text-slate font-bold pb-1">DISCOVERY</td><td class="text-white pb-1">{{ drilling.discovery }}</td></tr>
            <tr><td class="text-slate font-bold">DBC</td><td class="text-white">{{ drilling.dbc }}</td></tr>
          </table>

          <CyberBox variant="charcoal" border="none" class="w-1/2 flex flex-col border border-charcoal p-2">
            <div class="text-slate font-bold mb-1">LAST 30 SAMPLES (live)</div>
            <div class="font-mono text-ui-good text-title leading-none mb-2 overflow-hidden whitespace-nowrap">{{ drillHist }}</div>
            <div class="flex justify-between text-small">
              <span class="text-slate">MIN <span class="text-white font-bold">{{ drillBuffer.length ? Math.min(...drillBuffer).toFixed(1) : '—' }}</span></span>
              <span class="text-slate">AVG <span class="text-white font-bold">{{ drillBuffer.length ? (drillBuffer.reduce((a,b)=>a+b,0)/drillBuffer.length).toFixed(1) : '—' }}</span></span>
              <span class="text-slate">MAX <span class="text-white font-bold">{{ drillBuffer.length ? Math.max(...drillBuffer).toFixed(1) : '—' }}</span></span>
            </div>
          </CyberBox>
        </div>

        <div class="mt-4 text-small text-slate text-center pt-2 border-t border-charcoal hover:text-white cursor-pointer" @click="drilling = null">B / CLICK · CLOSE</div>
      </CyberBox>
    </div>
  </PageShell>
</template>

<style scoped>
.hardware-root {
  min-height: 0;
}
</style>

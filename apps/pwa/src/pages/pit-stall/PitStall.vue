<script setup lang="ts">
/**
 * PIT STALL — tabbed layout for Pixel 10 landscape.
 *
 * Three tabs:
 *   1. CONNECTIONS — bridge / USB-CAN / DBC / car status rows + boot log
 *                    terminal. Sourced from /health + /diagnostics/can.
 *   2. LIVE        — live telemetry car state from SSE telemetry stream,
 *                    plus the OPEN LIVE PIT WALL CTA.
 *   3. REPLAY      — SessionStartPicker: lists /sessions, drives
 *                    /session/replay/{start,stop,status}.
 *
 * Keyboard: 1-3 selects tabs; L/Enter opens the live pit wall (preserved
 * from PR-C); R reboots diagnostics; B/Esc/Backspace = back.
 *
 * SSE contract (PR-C): the telemetry stream is subscribed via the
 * page-level `watch(bridgeStore.health?.active_session_id)` below — NOT
 * inside any tab. Tabs use v-show, so the SSE connection is established
 * once on mount and persists across tab switches. `telemetry.open()` is
 * idempotent (close-then-open), so the `watch` triggering on sid change
 * is safe.
 */
import { ref, computed, onUnmounted, onMounted, watch } from 'vue'
import { useKeyboard } from '@/shared/lib/useKeyboard'
import { useRouter } from 'vue-router'
import { useAudioStore } from '@/features/audio-playback/model/audioStore'
import PageShell from '@/shared/ui/PageShell.vue'
import CyberTabs from '@/shared/ui/core/CyberTabs.vue'
import CyberButton from '@/shared/ui/core/CyberButton.vue'
import ConnRow from './ui/ConnRow.vue'
import LiveCarState from './ui/LiveCarState.vue'
import SessionStartPicker from '@/widgets/session-start/SessionStartPicker.vue'
import { useBridgeStore } from '@/shared/api/bridgeStore'
import { useTelemetryStore } from '@/entities/session/model/telemetryStore'
import { bridge } from '@/shared/api/bridge'

const router = useRouter()
const audio = useAudioStore()
const bridgeStore = useBridgeStore()
const telemetry = useTelemetryStore()

// ── Tabs ────────────────────────────────────────────────────────────────────
const TAB_LABELS = ['CONNECTIONS', 'LIVE', 'REPLAY'] as const
const activeTab = ref(0)

// ─────────────────────────────────────────────────────────────────────────────
// Real-data state — every row derives from /health + /diagnostics/can.
// No setTimeout-faked progress; no hardcoded bitrates, signal counts, or
// boot messages. If an endpoint is missing (old bridge), the row falls
// back to a degraded label rather than crashing.
// ─────────────────────────────────────────────────────────────────────────────

interface CanDiagnostics {
  loaded?: boolean
  connected?: boolean
  interface?: string | null
  channel?: string | null
  bitrate?: number | null
  frames_total?: number
  frames_unknown?: number
  frames_per_second?: number
  last_frame_age_s?: number | null
  usb_devices?: Array<{ device: string; vid?: string; pid?: string; model?: string; kind?: string; is_known?: boolean }>
  // `dbc_path` is emitted as a string OR a list of paths (multi-DBC overlays).
  car_config_path?: string | null
  dbc_path?: string | string[] | null
  signal_registry_count?: number
}

const canDiag = ref<CanDiagnostics | null>(null)
const canDiagError = ref<string | null>(null)
const canDiagMissing = ref(false)   // true when bridge replies 404 (old bridge)

const bootLogs = ref<{ msg: string; type: string }[]>([])
const seenLogKeys = ref<Set<string>>(new Set())

const addLog = (key: string, msg: string, type = 'info') => {
  // De-dupe across polls — we only want a log line the first time a
  // milestone fires (bridge online, can connected, dbc loaded, ignition).
  if (seenLogKeys.value.has(key)) return
  seenLogKeys.value.add(key)
  bootLogs.value.push({ msg, type })
  const el = document.getElementById('boot-logs-container')
  if (el) {
    setTimeout(() => { el.scrollTop = el.scrollHeight }, 50)
  }
}

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

// ── Row state machines ──────────────────────────────────────────────────────

const bridgeState = computed<'checking' | 'ok' | 'error' | 'pending'>(() => {
  if (bridgeStore.healthError) return 'error'
  if (bridgeStore.health) return 'ok'
  return 'checking'
})

const bridgeDetails = computed<string[]>(() => {
  const h = bridgeStore.health
  if (!h) {
    if (bridgeStore.healthError) return ['127.0.0.1:8765', 'no response — daemon offline?']
    return ['127.0.0.1:8765', 'connecting…']
  }
  const lite = h.litert
  const llm = lite?.up
    ? `LiteRT @ ${lite.http_url || '?'} (${lite.http_model || 'unknown model'})`
    : 'no LLM'
  return [
    `127.0.0.1:8765 — engine: ${h.engine || 'unknown'}`,
    llm,
  ]
})

const usbCanState = computed<'checking' | 'ok' | 'error' | 'pending'>(() => {
  if (bridgeState.value !== 'ok') return 'pending'
  if (canDiagMissing.value) return 'error'
  if (!canDiag.value) return 'checking'
  const c = canDiag.value
  if (c.connected && (c.frames_per_second || 0) > 0) return 'ok'
  if ((c.usb_devices?.length || 0) > 0) return 'pending'
  return 'error'
})

const usbCanDetails = computed<string[]>(() => {
  if (canDiagMissing.value) return ['(unknown — bridge endpoint missing)']
  const c = canDiag.value
  if (!c) return ['querying /diagnostics/can…']
  const device = c.channel || c.interface || 'no device'
  const bps = typeof c.bitrate === 'number' ? `${Math.round(c.bitrate / 1000)}k bps` : 'rate unknown'
  const fps = typeof c.frames_per_second === 'number' ? `${Math.round(c.frames_per_second)} fps` : '0 fps'
  const lines = [`device: ${device}`, `rate: ${bps}`, `fps: ${fps}`]
  const devs = c.usb_devices || []
  if (!c.connected && devs.length > 0) {
    lines.push(`detected: ${devs.map(d => d.model || d.device).join(', ')}`)
  } else if (!c.connected && devs.length === 0) {
    lines.push('no USB-CAN adapter detected')
  }
  return lines
})

const dbcState = computed<'checking' | 'ok' | 'error' | 'pending'>(() => {
  if (bridgeState.value !== 'ok') return 'pending'
  if (canDiagMissing.value) return 'error'
  if (!canDiag.value) return 'checking'
  return (canDiag.value.signal_registry_count || 0) > 0 ? 'ok' : 'error'
})

const dbcDetails = computed<string[]>(() => {
  if (canDiagMissing.value) return ['(unknown — bridge endpoint missing)']
  const c = canDiag.value
  if (!c) return ['querying signal registry…']
  return [
    `car: ${basename(c.car_config_path)}`,
    `dbc: ${basename(c.dbc_path)}`,
    `${c.signal_registry_count || 0} signals registered`,
  ]
})

const carState = computed<'checking' | 'ok' | 'error' | 'pending'>(() => {
  const h = bridgeStore.health
  if (bridgeState.value !== 'ok' || !h?.can) return 'pending'
  const total = h.can.frames_total || 0
  const age = h.can.last_frame_age_s
  if (total <= 0) return 'error'
  if (typeof age === 'number' && age < 5) return 'ok'
  return 'pending'
})

const carDetails = computed<string[]>(() => {
  const h = bridgeStore.health
  if (!h) return ['—']
  const track = (h as { track?: string | null }).track || 'no track'
  const sid = h.active_session_id || '—'
  return [track, `session: ${sid}`]
})

// ── Accessible state phrasing ───────────────────────────────────────────────
// The status dots/check-glyphs in each ConnRow are color-only — screen
// readers get nothing useful from "✓" or a green pixel. These computed
// strings are rendered in visually-hidden `<span class="sr-only">` nodes
// alongside each row so assistive tech announces the same signal the
// sighted user sees in the dot.
const stateWord = (s: 'checking' | 'ok' | 'error' | 'pending'): string => {
  switch (s) {
    case 'ok':       return 'online'
    case 'error':    return 'offline'
    case 'pending':  return 'pending'
    case 'checking': return 'checking'
  }
}

const bridgeA11yLabel = computed(() =>
  `Bridge ${stateWord(bridgeState.value)} — ${bridgeDetails.value.join(', ')}`,
)
const usbCanA11yLabel = computed(() =>
  `USB-CAN ${stateWord(usbCanState.value)} — ${usbCanDetails.value.join(', ')}`,
)
const dbcA11yLabel = computed(() =>
  `DBC ${stateWord(dbcState.value)} — ${dbcDetails.value.join(', ')}`,
)
const carA11yLabel = computed(() =>
  `Car ${stateWord(carState.value)} — ${carDetails.value.join(', ')}`,
)

// ── Live values: SSE telemetry frame + diagnostics.frames_per_second ────────

const liveState = computed(() => {
  const f = telemetry.frame as unknown as Record<string, unknown> | null
  const pickNum = (k: string): number | undefined => {
    const v = f ? f[k] : undefined
    return typeof v === 'number' && Number.isFinite(v) ? v : undefined
  }
  const fmt = (v: number | undefined, digits = 0): string =>
    v === undefined ? '—' : v.toFixed(digits)

  const rpm = pickNum('rpm')
  const speedMs = pickNum('speed')
  const speedKmh = speedMs !== undefined ? speedMs * 3.6 : undefined
  const throttle = pickNum('throttle')
  const brake = pickNum('brake_pressure')
  const steer = pickNum('steering')
  const gLat = pickNum('g_lat')
  const gLong = pickNum('g_long')
  const gCombo = pickNum('combo_g')

  // Wide-frame v3.0 channels — emitted on SSE when the bridge enriches
  // the payload. If absent we render '—' (no fake constants).
  const oil = pickNum('engine_oil_temp_c') ?? pickNum('oil_temp_c')
  const oilF = pickNum('engine_oil_temp_f') ?? pickNum('oil_temp_f')
  const coolant = pickNum('water_temp_c') ?? pickNum('coolant_temp_c')
  const coolantF = pickNum('water_temp_f') ?? pickNum('coolant_temp_f')
  const fuelPct = pickNum('fuel_level_pct')
  const fuelGal = pickNum('fuel_level_gal') ?? pickNum('fuel_level_l')

  // Derive a coarse gear from speed when no gear signal is on the frame.
  const gearSig = pickNum('gear_position') ?? pickNum('gear')
  const gear = gearSig !== undefined
    ? Math.round(gearSig).toString()
    : speedKmh === undefined
      ? '-'
      : speedKmh < 10 ? '1' : speedKmh < 60 ? '2' : speedKmh < 100 ? '3' : speedKmh < 140 ? '4' : '5'

  return {
    rpm: fmt(rpm, 0),
    gear,
    speed: fmt(speedKmh, 0),
    oil: oil !== undefined ? fmt(oil, 0) : (oilF !== undefined ? fmt((oilF - 32) * 5 / 9, 0) : '—'),
    coolant: coolant !== undefined ? fmt(coolant, 0) : (coolantF !== undefined ? fmt((coolantF - 32) * 5 / 9, 0) : '—'),
    fuel: fuelPct !== undefined ? fmt(fuelPct, 0) : (fuelGal !== undefined ? fmt(fuelGal, 1) : '—'),
    throttle: fmt(throttle, 0),
    brake: fmt(brake, 0),
    steer: fmt(steer, 1),
    glat: fmt(gLat, 1),
    glong: fmt(gLong, 1),
    gcombo: fmt(gCombo, 1),
  }
})

// ── Polling ─────────────────────────────────────────────────────────────────

let canDiagInterval: number | null = null

const pollCanDiagnostics = async () => {
  if (!bridgeStore.health) return    // wait until bridge handshake completes
  try {
    canDiag.value = await bridge.get<CanDiagnostics>('/diagnostics/can')
    canDiagError.value = null
    canDiagMissing.value = false
  } catch (e) {
    const msg = String(e)
    canDiagError.value = msg
    // Bridge replied but route doesn't exist → old bridge, degrade gracefully.
    if (msg.includes('404') || msg.toLowerCase().includes('not found')) {
      canDiagMissing.value = true
    }
  }
}

// ── Boot-log narrative: derived purely from real state transitions ──────────

watch([bridgeState, () => bridgeStore.health], () => {
  const h = bridgeStore.health
  if (bridgeState.value === 'ok' && h) {
    const model = h.litert?.http_model || (h.litert?.up ? 'unknown' : 'no LLM')
    addLog('bridge', `BRIDGE CONNECTED — engine: ${h.engine || 'unknown'}, AI: ${model}`, 'good')
    audio.playSfx('goal_complete')
  } else if (bridgeState.value === 'error') {
    addLog('bridge_err', 'BRIDGE CONNECTION FAILED. Is the daemon running?', 'bad')
    audio.playSfx('cancel')
  }
})

watch(canDiag, (c) => {
  if (!c) return
  if (canDiagMissing.value) return
  if (usbCanState.value === 'ok' && c.bitrate) {
    addLog(
      'usbcan',
      `USB-CAN STREAM — ${c.interface || '?'}/${c.channel || '?'} @ ${Math.round((c.bitrate || 0) / 1000)} kbps, ${Math.round(c.frames_per_second || 0)} fps`,
      'good',
    )
    audio.playSfx('goal_complete')
  }
  if (dbcState.value === 'ok') {
    addLog(
      'dbc',
      `DBC LOADED — ${c.signal_registry_count || 0} signals registered, ${c.frames_unknown || 0} unknown frame IDs seen`,
      'good',
    )
    audio.playSfx('goal_complete')
  }
})

watch(carState, (s) => {
  const h = bridgeStore.health
  if (s === 'ok' && h?.can) {
    const total = (h.can.frames_total || 0).toLocaleString()
    const fps = Math.round(h.can.fps || 0)
    const age = (h.can.last_frame_age_s || 0).toFixed(1)
    addLog(
      'ignition',
      `Frames flowing: ${total} total, ${fps} fps, last seen ${age}s ago`,
      'good',
    )
    addLog('streaming', 'LINK STABLE. STREAMING TELEMETRY.', 'good')
    audio.playSfx('level_up')
    // Open SSE on the active session — no implicit simulation. If the
    // bridge hasn't published an active_session_id yet, do nothing; the
    // page-level watcher on `bridgeStore.health?.active_session_id`
    // below will open the stream as soon as one appears.
    if (h.active_session_id) telemetry.open(h.active_session_id)
  } else if (s === 'error') {
    addLog('no_ignition', 'no ignition / engine off (0 frames)', 'warn')
  }
})

// Replay-aware SSE gate (PR-C): session replay bypasses the CAN reader so
// `can.connected` stays false and `carState` never reaches 'ok'. Open the
// telemetry stream whenever the bridge advertises an active session
// regardless of CAN state. `telemetry.open()` calls `close()` first so
// this is idempotent with the carState-driven open above.
//
// CRITICAL: this watcher lives at the PAGE level, not inside a tab. It
// fires once per active_session_id change — NOT once per tab switch —
// because tabs are v-show, not v-if. Do not move into a tab template or
// the SSE will re-subscribe every time the user touches the tab bar.
watch(
  () => bridgeStore.health?.active_session_id,
  (sid) => {
    if (sid) telemetry.open(sid)
  },
  { immediate: true },
)

const reboot = () => {
  // Reset boot-log narrative so the user sees a fresh sequence.
  bootLogs.value = []
  seenLogKeys.value = new Set()
  addLog('init', 'INITIATING DIAGNOSTICS…', 'warn')
  addLog('connecting', 'Connecting to bridge at 127.0.0.1:8765', 'info')
  // Force a fresh health poll + immediate diagnostics fetch.
  bridgeStore.pollHealth().then(() => pollCanDiagnostics())
  audio.playSfx('cursor_select')
}

onMounted(() => {
  addLog('init', 'INITIATING DIAGNOSTICS…', 'warn')
  addLog('connecting', 'Connecting to bridge at 127.0.0.1:8765', 'info')
  bridgeStore.startPolling()
  // Kick off diagnostics polling at 2 Hz — first attempt fires immediately
  // once the bridge handshake lands.
  pollCanDiagnostics()
  canDiagInterval = window.setInterval(pollCanDiagnostics, 2000)
})

onUnmounted(() => {
  if (canDiagInterval) clearInterval(canDiagInterval)
  telemetry.close()
})

const openLiveWall = () => {
  audio.playSfx('cursor_select')
  router.push('/pit-stall/live')
}

useKeyboard((e: KeyboardEvent) => {
  // Tab switching always available — Pixel 10 number row.
  if (e.key === '1') { audio.playSfx('cursor_move'); activeTab.value = 0; return }
  if (e.key === '2') { audio.playSfx('cursor_move'); activeTab.value = 1; return }
  if (e.key === '3') { audio.playSfx('cursor_move'); activeTab.value = 2; return }

  if (e.key === 'Escape' || e.key === 'Backspace' || e.key === 'b') {
    audio.playSfx('cancel')
    router.push('/garage')
  } else if (e.key === 'r' || e.key === 'R') {
    reboot()
  } else if (e.key === 'Enter' || e.key === 'l' || e.key === 'L') {
    // Live wall is always reachable — replay sessions don't satisfy
    // carState === 'ok' but still produce telemetry worth viewing.
    openLiveWall()
  }
})
</script>

<template>
  <PageShell
    title="PIT STALL"
    :actions="[
      { label: 'LIVE WALL', key: 'l', keyLabel: 'L', variant: 'primary' },
      { label: 'REBOOT', key: 'r', keyLabel: 'R' },
      { label: 'BACK', key: 'Escape', keyLabel: 'B', variant: 'warn' }
    ]"
    bg="neutral"
    :show-heading="false"
  >
    <div class="pitstall-root flex flex-col h-full min-h-0 w-full gap-[clamp(6px,1vmin,12px)]">

      <!-- Tab bar -->
      <CyberTabs
        v-model="activeTab"
        :tabs="TAB_LABELS"
        class="shrink-0"
      />

      <!-- Tab content fills remaining height -->
      <div class="flex-1 min-h-0 overflow-hidden">

        <!-- ── CONNECTIONS ─────────────────────────────────────────────── -->
        <!--
          Landscape (Pixel 10, 2424×1080): two columns — connection chain
          on the left, terminal log on the right. The 1fr / 1fr grid keeps
          both halves bounded so neither overflows the viewport height.
        -->
        <section
          v-show="activeTab === 0"
          class="h-full min-h-0 grid grid-cols-1 landscape:grid-cols-[3fr_2fr] gap-[clamp(6px,1.2vmin,14px)] overflow-hidden"
          aria-label="Connection diagnostics"
        >
          <!-- Connection chain column -->
          <div class="flex flex-col min-h-0 bg-ink/40 border-2 border-slate/30">
            <header class="flex justify-between items-center shrink-0 px-[clamp(8px,1.5vmin,16px)] py-[clamp(6px,1vmin,12px)] border-b border-slate/20 bg-ink/60">
              <span class="text-small text-slate tracking-[0.2em] font-black uppercase">Connection Chain</span>
              <CyberButton size="sm" variant="secondary" @click="reboot">REBOOT</CyberButton>
            </header>

            <div
              class="flex-1 min-h-0 overflow-y-auto no-scrollbar flex flex-col gap-[clamp(6px,1.2vmin,14px)] p-[clamp(8px,1.5vmin,16px)]"
              role="list"
            >
              <div role="listitem" :aria-label="bridgeA11yLabel">
                <ConnRow title="BRIDGE" :state="bridgeState" status-text="ONLINE" :details="bridgeDetails" />
                <span class="sr-only" aria-live="polite">{{ bridgeA11yLabel }}</span>
              </div>
              <div role="listitem" :aria-label="usbCanA11yLabel">
                <ConnRow title="USB-CAN" :state="usbCanState" status-text="STREAM" :details="usbCanDetails" />
                <span class="sr-only" aria-live="polite">{{ usbCanA11yLabel }}</span>
              </div>
              <div role="listitem" :aria-label="dbcA11yLabel">
                <ConnRow title="DBC" :state="dbcState" status-text="LOADED" :details="dbcDetails" />
                <span class="sr-only" aria-live="polite">{{ dbcA11yLabel }}</span>
              </div>
              <div role="listitem" :aria-label="carA11yLabel">
                <ConnRow title="CAR" :state="carState" status-text="READY" :details="carDetails" />
                <span class="sr-only" aria-live="polite">{{ carA11yLabel }}</span>
              </div>
            </div>
          </div>

          <!-- Terminal column -->
          <div class="flex flex-col min-h-0 bg-ink/80 border-2 border-slate/30">
            <header class="shrink-0 px-[clamp(8px,1.5vmin,16px)] py-[clamp(6px,1vmin,12px)] border-b border-slate/20 bg-ink/60">
              <span class="text-ui-info text-small font-black tracking-widest uppercase opacity-80">Terminal Output</span>
            </header>
            <div
              id="boot-logs-container"
              class="flex-1 min-h-0 overflow-y-auto no-scrollbar font-nums text-small leading-tight whitespace-pre-line p-[clamp(8px,1.5vmin,16px)]"
            >
              <div
                v-for="(log, i) in bootLogs"
                :key="i"
                :class="log.type === 'good' ? 'text-ui-good' : log.type === 'bad' ? 'text-ui-bad' : log.type === 'warn' ? 'text-ui-warn' : 'text-silver/60'"
              >
                > {{ log.msg }}
              </div>
              <div v-if="!bootLogs.length" class="text-slate/50 italic">— awaiting diagnostics —</div>
            </div>
          </div>
        </section>

        <!-- ── LIVE ────────────────────────────────────────────────────── -->
        <!--
          Landscape: telemetry detail on the left, status + primary CTA on
          the right (constrained max-w so the button doesn't stretch the
          full 2424px). Both columns are independently scrollable but
          bounded by parent min-h-0.
        -->
        <section
          v-show="activeTab === 1"
          class="h-full min-h-0 grid grid-cols-1 landscape:grid-cols-[2fr_1fr] gap-[clamp(6px,1.2vmin,14px)] overflow-hidden"
          aria-label="Live telemetry"
        >
          <div class="flex flex-col min-h-0 bg-ink/40 border-2 border-slate/30">
            <header class="flex justify-between items-center shrink-0 px-[clamp(8px,1.5vmin,16px)] py-[clamp(6px,1vmin,12px)] border-b border-slate/20 bg-ink/60">
              <span class="text-small text-slate tracking-[0.2em] font-black uppercase">Telemetry Monitor</span>
              <span v-if="carState === 'ok'" class="text-ui-good animate-pulse text-small font-bold">● LIVE</span>
              <span v-else class="text-slate text-small">○ {{ stateWord(carState).toUpperCase() }}</span>
            </header>
            <div class="flex-1 min-h-0 overflow-y-auto no-scrollbar p-[clamp(8px,1.5vmin,16px)]">
              <LiveCarState :state="liveState" />
            </div>
          </div>

          <div class="flex flex-col min-h-0 bg-ink/40 border-2 border-slate/30">
            <header class="shrink-0 px-[clamp(8px,1.5vmin,16px)] py-[clamp(6px,1vmin,12px)] border-b border-slate/20 bg-ink/60">
              <span class="text-small text-slate tracking-[0.2em] font-black uppercase">Live Pit Wall</span>
            </header>
            <div class="flex-1 min-h-0 overflow-y-auto no-scrollbar flex flex-col gap-[clamp(8px,1.5vmin,16px)] p-[clamp(8px,1.5vmin,16px)]">
              <p class="text-small text-silver/80 leading-relaxed">
                Open the full-screen pit wall to mirror live telemetry, coach
                cues, and lap counters at race-day legibility. Works during
                replay too — the wall reflects whatever the bridge is
                streaming.
              </p>
              <!--
                Always enabled — replay sessions don't satisfy carState === 'ok'
                (no CAN frames) but still emit telemetry worth viewing on the
                live wall. The button is the primary affordance to reach
                /pit-stall/live; without it the route is URL-only.
              -->
              <CyberButton fluid variant="primary" size="lg" @click="openLiveWall">
                OPEN LIVE PIT WALL [L]
              </CyberButton>
              <div class="text-[10px] text-slate/70 tracking-widest uppercase">
                Active session: <span class="text-silver">{{ bridgeStore.health?.active_session_id || '—' }}</span>
              </div>
            </div>
          </div>
        </section>

        <!-- ── REPLAY ──────────────────────────────────────────────────── -->
        <!--
          SessionStartPicker is a vertical form; on landscape we cap its
          width and pair it with a help column rather than stretching it
          across 2424px. min-h-0 + overflow-y-auto keeps long session
          lists scrollable without breaking the page envelope.
        -->
        <section
          v-show="activeTab === 2"
          class="h-full min-h-0 grid grid-cols-1 landscape:grid-cols-[minmax(0,640px)_1fr] gap-[clamp(8px,1.5vmin,18px)] overflow-hidden"
          aria-label="Session replay"
        >
          <div class="min-h-0 overflow-y-auto no-scrollbar">
            <!--
              SessionStartPicker owns its own /sessions polling, replay
              status polling, and start/stop calls against
              /session/replay/*. When it triggers a replay the bridge
              updates state.active_session_id, which fans out through
              bridgeStore.health into the SSE watcher above — no extra
              wiring here.
            -->
            <SessionStartPicker />
          </div>

          <aside class="hidden landscape:flex flex-col min-h-0 bg-ink/40 border-2 border-slate/30 p-[clamp(10px,2vmin,20px)] gap-[clamp(6px,1.2vmin,14px)] overflow-y-auto no-scrollbar">
            <h3 class="text-small text-ui-info tracking-[0.2em] font-black uppercase border-b border-slate/30 pb-[clamp(4px,0.8vmin,8px)]">
              How replay works
            </h3>
            <p class="text-small text-silver/80 leading-relaxed">
              Pick a recorded session and press <span class="text-ui-good">START</span>. The bridge will
              re-stream its telemetry as if it were live — every coach,
              gauge, and pit-wall view in the app reacts to it the same
              way they would to a real car.
            </p>
            <p class="text-small text-silver/80 leading-relaxed">
              Switch to the <span class="text-ui-good">LIVE</span> tab to watch the resulting telemetry,
              or open the <span class="text-ui-good">Live Pit Wall</span> for a full-screen view.
            </p>
            <p class="text-small text-slate/70 leading-relaxed mt-auto">
              Replay bypasses the CAN reader, so the connection chain on
              the <span class="text-ui-good">CONNECTIONS</span> tab will still show CAR as pending —
              that is expected.
            </p>
          </aside>
        </section>

      </div>
    </div>
  </PageShell>
</template>

<style scoped>
.pitstall-root {
  min-height: 0;
}
</style>

<script setup lang="ts">
/**
 * AgentTraceDrawer — slide-out panel on the right of the On-Track HUD that
 * surfaces *which* ADK coaching agents have fired during the active session,
 * what tools they invoked, latency, and success/failure.
 *
 * - Polls /coach/traces every 1.5s ONLY while open (battery-aware on Pixel 10).
 * - Fetches /coach/agents once so the user can see what COULD run, not just
 *   what HAS run.
 * - Honest empty state when `available:false` — no fake rows, ever.
 */
import { computed, onMounted, onBeforeUnmount, ref, watch } from 'vue'
import CyberPanel from '@/shared/ui/core/CyberPanel.vue'
import { useAgentTraceStore } from '@/entities/coach/model/agentTraceStore'

interface Props {
  open: boolean
  sessionId?: string | null
}

const props = defineProps<Props>()
const emit = defineEmits<{ (e: 'close'): void }>()

const store = useAgentTraceStore()
const POLL_MS = 1500
let pollTimer: number | null = null
const showAgentRoster = ref(false)

const sidShort = computed(() => {
  const s = props.sessionId ?? ''
  if (!s) return '—'
  if (s.length <= 16) return s
  return `${s.slice(0, 8)}…${s.slice(-6)}`
})

function startPolling() {
  if (pollTimer != null) return
  // Kick an immediate fetch so the drawer doesn't show "—" for 1.5s on open.
  void store.pollTraces({ sessionId: props.sessionId ?? undefined })
  pollTimer = window.setInterval(() => {
    void store.pollTraces({ sessionId: props.sessionId ?? undefined })
  }, POLL_MS)
}

function stopPolling() {
  if (pollTimer != null) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

onMounted(() => {
  // Always fetch the agent roster on mount — the user can see what's
  // *registered* even before any agent fires.
  void store.fetchAgents()
  if (props.open) startPolling()
})

onBeforeUnmount(() => {
  stopPolling()
})

watch(() => props.open, (isOpen) => {
  if (isOpen) startPolling()
  else stopPolling()
})

function rowClass(t: { event_type: string; success: boolean }): string {
  if (!t.success) return 'trace-row trace-bad'
  switch (t.event_type) {
    case 'tool':  return 'trace-row trace-good'
    case 'route': return 'trace-row trace-warn'
    case 'agent': return 'trace-row trace-info'
    default:      return 'trace-row trace-info'
  }
}

function eventIcon(t: { event_type: string; success: boolean }): string {
  if (!t.success) return '✗'
  switch (t.event_type) {
    case 'tool':  return '⚙'
    case 'route': return '→'
    case 'agent': return '●'
    default:      return '·'
  }
}

function formatLatency(ms: number | null): string {
  if (ms == null || !Number.isFinite(ms)) return '—'
  if (ms < 1) return '<1ms'
  if (ms >= 1000) return `${(ms / 1000).toFixed(2)}s`
  return `${ms.toFixed(0)}ms`
}

function formatTs(iso: string): string {
  // ISO → HH:MM:SS.mmm in local TZ. Defensive against weird server formats.
  try {
    const d = new Date(iso)
    if (Number.isNaN(d.getTime())) return iso
    const hh = String(d.getHours()).padStart(2, '0')
    const mm = String(d.getMinutes()).padStart(2, '0')
    const ss = String(d.getSeconds()).padStart(2, '0')
    const ms = String(d.getMilliseconds()).padStart(3, '0')
    return `${hh}:${mm}:${ss}.${ms}`
  } catch {
    return iso
  }
}

function toggleRoster() {
  showAgentRoster.value = !showAgentRoster.value
}

function close() {
  emit('close')
}
</script>

<template>
  <Transition name="slide-drawer">
    <aside
      v-if="open"
      class="trace-drawer"
      role="complementary"
      aria-labelledby="trace-drawer-title"
    >
      <CyberPanel variant="solid" border="primary" class="drawer-panel">
        <header class="drawer-head">
          <div class="head-titles">
            <h2 id="trace-drawer-title" class="drawer-title">
              AGENT TRACE
              <span class="title-sid">· {{ sidShort }}</span>
            </h2>
            <div class="head-meta">
              <span class="event-count">{{ store.eventCount }} events</span>
              <span v-if="store.loading" class="poll-pip" aria-hidden="true"></span>
            </div>
          </div>
          <button
            type="button"
            class="drawer-close"
            aria-label="Close agent trace drawer"
            @click="close"
          >
            ✕
          </button>
        </header>

        <!-- Unavailable banner — honest about why the panel is empty. -->
        <div
          v-if="!store.available"
          class="trace-empty trace-unavailable"
          role="status"
        >
          AGENT TRACE UNAVAILABLE
          <div class="trace-empty-sub">{{ store.reason || 'ADK not loaded' }}</div>
        </div>

        <!-- Empty-but-available state. -->
        <div
          v-else-if="store.eventCount === 0"
          class="trace-empty"
          role="status"
        >
          NO AGENT ACTIVITY YET
          <div class="trace-empty-sub">
            Coach pipelines write here as soon as they run.
          </div>
        </div>

        <!-- Live trace list — newest at top. -->
        <ol v-else class="trace-list" aria-label="Agent trace events, newest first">
          <li
            v-for="t in store.traces"
            :key="`${t.trace_id}-${t.agent_name}-${t.ts}`"
            :class="rowClass(t)"
          >
            <div class="row-line-1">
              <span class="row-icon" aria-hidden="true">{{ eventIcon(t) }}</span>
              <span class="row-agent">{{ t.agent_name || '?' }}</span>
              <span class="row-latency">{{ formatLatency(t.latency_ms) }}</span>
              <span class="row-status" :aria-label="t.success ? 'success' : 'failure'">
                {{ t.success ? '✓' : '✗' }}
              </span>
            </div>
            <div class="row-line-2">
              <span class="row-type">{{ t.event_type }}</span>
              <span v-if="t.detail" class="row-detail">{{ t.detail }}</span>
              <span class="row-ts">{{ formatTs(t.ts) }}</span>
            </div>
          </li>
        </ol>

        <footer class="drawer-foot">
          <button
            type="button"
            class="roster-pill"
            :aria-expanded="showAgentRoster"
            @click="toggleRoster"
          >
            AVAILABLE AGENTS · {{ store.agents.length }}
            <span class="roster-chevron" aria-hidden="true">
              {{ showAgentRoster ? '▾' : '▸' }}
            </span>
          </button>
          <div v-if="showAgentRoster" class="roster-body">
            <div
              v-if="store.agents.length === 0"
              class="roster-empty"
            >
              No agents registered.
            </div>
            <ul v-else class="roster-list">
              <li
                v-for="a in store.agents"
                :key="a.name"
                class="roster-item"
                :class="store.firedAgentNames.includes(a.name) ? 'roster-fired' : ''"
              >
                <span class="roster-name">{{ a.name }}</span>
                <span v-if="a.role" class="roster-role">{{ a.role }}</span>
              </li>
            </ul>
          </div>
        </footer>
      </CyberPanel>
    </aside>
  </Transition>
</template>

<style scoped>
.trace-drawer {
  position: absolute;
  top: 0;
  right: 0;
  bottom: 0;
  width: min(92vw, 480px);
  z-index: 180;
  display: flex;
  flex-direction: column;
  padding: calc(max(var(--safe-top), var(--space-sm)))
           calc(max(var(--safe-right), var(--space-sm)))
           calc(max(var(--safe-bottom), var(--space-sm)))
           var(--space-sm);
  pointer-events: auto;
}

.drawer-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: rgba(8, 8, 14, 0.96);
  backdrop-filter: blur(12px);
}

.drawer-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px;
  padding: 12px 14px 8px;
  border-bottom: 1px solid color-mix(in srgb, var(--color-slate) 30%, transparent);
}

.head-titles {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.drawer-title {
  margin: 0;
  font-family: var(--font-title);
  font-weight: 800;
  letter-spacing: 0.18em;
  color: var(--color-ui-good);
  font-size: clamp(13px, 2.2vmin, 16px);
  text-transform: uppercase;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.title-sid {
  color: var(--color-silver);
  font-family: var(--font-mono);
  font-size: 0.85em;
  letter-spacing: 0.05em;
}

.head-meta {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: var(--color-slate);
  font-family: var(--font-mono);
  font-size: clamp(10px, 1.8vmin, 12px);
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.event-count {
  color: var(--color-silver);
}

.poll-pip {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--color-ui-info);
  box-shadow: 0 0 8px var(--color-ui-info);
  animation: trace-pulse 1.4s ease-in-out infinite;
}

@keyframes trace-pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.45; transform: scale(0.75); }
}

.drawer-close {
  width: 44px;
  height: 44px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid color-mix(in srgb, var(--color-slate) 40%, transparent);
  background: transparent;
  color: var(--color-silver);
  font-family: var(--font-ui);
  font-size: 18px;
  font-weight: 700;
  cursor: pointer;
  border-radius: 4px;
  transition: background-color var(--duration-fast) ease, transform var(--duration-fast) ease;
}

.drawer-close:hover,
.drawer-close:focus-visible {
  background: rgba(255, 255, 255, 0.06);
  transform: translateY(-1px);
}

.trace-empty {
  flex: 1 1 auto;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 32px 16px;
  color: var(--color-slate);
  font-family: var(--font-title);
  font-weight: 800;
  letter-spacing: 0.16em;
  text-align: center;
  font-size: clamp(12px, 2vmin, 15px);
  text-transform: uppercase;
}

.trace-unavailable {
  color: var(--color-ui-warn);
}

.trace-empty-sub {
  color: var(--color-slate);
  font-family: var(--font-mono);
  font-weight: 400;
  letter-spacing: 0.04em;
  text-transform: none;
  font-size: clamp(11px, 1.6vmin, 13px);
  max-width: 32ch;
  line-height: 1.4;
}

.trace-list {
  flex: 1 1 auto;
  list-style: none;
  margin: 0;
  padding: 6px 8px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 4px;
  scrollbar-width: thin;
  scrollbar-color: var(--color-slate) transparent;
}

.trace-row {
  border-left: 3px solid transparent;
  padding: 6px 8px;
  background: rgba(255, 255, 255, 0.02);
  border-radius: 2px;
  min-height: 44px;
}

.trace-row.trace-info  { border-left-color: var(--color-ui-info); }
.trace-row.trace-good  { border-left-color: var(--color-ui-good); }
.trace-row.trace-warn  { border-left-color: var(--color-ui-warn); }
.trace-row.trace-bad   { border-left-color: var(--color-ui-bad); background: rgba(255, 71, 87, 0.06); }

.row-line-1 {
  display: grid;
  grid-template-columns: 18px 1fr auto auto;
  align-items: baseline;
  gap: 8px;
  font-family: var(--font-mono);
  font-size: clamp(12px, 1.9vmin, 14px);
  color: var(--color-silver);
}

.row-icon {
  text-align: center;
  font-weight: 700;
}

.trace-info .row-icon  { color: var(--color-ui-info); }
.trace-good .row-icon  { color: var(--color-ui-good); }
.trace-warn .row-icon  { color: var(--color-ui-warn); }
.trace-bad  .row-icon  { color: var(--color-ui-bad); }

.row-agent {
  font-weight: 700;
  color: var(--color-white);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.row-latency {
  color: var(--color-slate);
  font-variant-numeric: tabular-nums;
}

.row-status {
  font-weight: 700;
}

.trace-bad .row-status { color: var(--color-ui-bad); }
.trace-row:not(.trace-bad) .row-status { color: var(--color-ui-good); }

.row-line-2 {
  display: flex;
  align-items: baseline;
  gap: 8px;
  margin-top: 2px;
  font-family: var(--font-mono);
  font-size: clamp(10px, 1.6vmin, 12px);
  color: var(--color-slate);
}

.row-type {
  text-transform: uppercase;
  letter-spacing: 0.06em;
}

.trace-info .row-type { color: var(--color-ui-info); }
.trace-good .row-type { color: var(--color-ui-good); }
.trace-warn .row-type { color: var(--color-ui-warn); }
.trace-bad  .row-type { color: var(--color-ui-bad); }

.row-detail {
  flex: 1 1 auto;
  color: var(--color-silver);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  min-width: 0;
}

.row-ts {
  color: var(--color-slate);
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

.drawer-foot {
  border-top: 1px solid color-mix(in srgb, var(--color-slate) 30%, transparent);
  padding: 8px 10px 10px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.roster-pill {
  display: inline-flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  min-height: 44px;
  padding: 0 12px;
  border: 1px solid color-mix(in srgb, var(--color-ui-info) 45%, transparent);
  background: color-mix(in srgb, var(--color-ui-info) 12%, transparent);
  color: var(--color-ui-info);
  font-family: var(--font-title);
  font-weight: 700;
  letter-spacing: 0.14em;
  font-size: clamp(11px, 1.8vmin, 13px);
  text-transform: uppercase;
  border-radius: 4px;
  cursor: pointer;
  transition: background-color var(--duration-fast) ease;
}

.roster-pill:hover,
.roster-pill:focus-visible {
  background: color-mix(in srgb, var(--color-ui-info) 22%, transparent);
}

.roster-chevron {
  font-size: 12px;
  color: var(--color-silver);
}

.roster-body {
  max-height: 30vh;
  overflow-y: auto;
}

.roster-empty {
  padding: 8px;
  font-family: var(--font-mono);
  color: var(--color-slate);
  font-size: 12px;
}

.roster-list {
  list-style: none;
  margin: 0;
  padding: 4px 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.roster-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  min-height: 32px;
  padding: 6px 8px;
  font-family: var(--font-mono);
  font-size: clamp(11px, 1.6vmin, 13px);
  color: var(--color-slate);
  border-radius: 2px;
  border-left: 2px solid color-mix(in srgb, var(--color-slate) 25%, transparent);
}

.roster-item.roster-fired {
  color: var(--color-silver);
  border-left-color: var(--color-ui-good);
  background: rgba(0, 255, 153, 0.04);
}

.roster-name { font-weight: 600; }
.roster-role { opacity: 0.7; }

/* Slide-in transition from the right edge. */
.slide-drawer-enter-from,
.slide-drawer-leave-to {
  transform: translateX(100%);
  opacity: 0;
}

.slide-drawer-enter-active,
.slide-drawer-leave-active {
  transition: transform 220ms cubic-bezier(0.2, 0.8, 0.2, 1), opacity 180ms ease;
}
</style>

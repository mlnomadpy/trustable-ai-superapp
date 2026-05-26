<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useBridgeStore } from '@/shared/api/bridgeStore'
import { bridge } from '@/shared/api/bridge'

/**
 * Slim diagnostic pill bar that exposes three live signals:
 *   • Bridge  — is /health reachable?
 *   • CAN     — is the bus producing frames?
 *   • LLM     — is local llm transport up AND producing non-empty completions?
 *
 * Polls /health implicitly (via the existing bridgeStore, every 5 s) and
 * /diagnostics/llm_friction directly on a 15 s cadence with exponential
 * back-off on failure (capped at 60 s) so a missing endpoint does not
 * spam the network. Dismissible per-session via the × button.
 */

interface FrictionRow {
  timestamp?: number
  prompt_chars?: number
  completion_chars?: number
  error?: string | null
  model?: string | null
  latency_ms?: number
}

interface FrictionResponse {
  records?: FrictionRow[]
}

const bridgeStore = useBridgeStore()

const dismissed = ref(false)
const nowMs = ref(Date.now())

// LLM friction polling state
const lastFriction = ref<FrictionRow | null>(null)
const frictionError = ref<string | null>(null)
const frictionFetched = ref(false)
let frictionTimer: number | null = null
let freshnessTimer: number | null = null
let frictionBackoffMs = 15_000 // base cadence
const FRICTION_BASE_MS = 15_000
const FRICTION_MAX_BACKOFF_MS = 60_000
const BRIDGE_STALE_MS = 12_500

const pollFriction = async () => {
  try {
    const data = await bridge.get<FrictionResponse>('/diagnostics/llm_friction')
    const recs = data?.records ?? []
    lastFriction.value = recs.length > 0 ? recs[recs.length - 1] : null
    frictionError.value = null
    frictionFetched.value = true
    frictionBackoffMs = FRICTION_BASE_MS // reset on success
  } catch (e) {
    frictionError.value = String(e)
    // Exponential back-off: 15s → 30s → 60s (capped)
    frictionBackoffMs = Math.min(frictionBackoffMs * 2, FRICTION_MAX_BACKOFF_MS)
  } finally {
    if (frictionTimer !== null) {
      // Already scheduled by interval; nothing to do.
    }
  }
}

const scheduleFriction = () => {
  if (frictionTimer !== null) {
    window.clearTimeout(frictionTimer)
  }
  frictionTimer = window.setTimeout(async () => {
    await pollFriction()
    scheduleFriction()
  }, frictionBackoffMs)
}

// ---------- Pill state derivations ----------

type Tone = 'good' | 'warn' | 'bad' | 'unknown'
interface Pill { tone: Tone; label: string; title?: string }

const truncate = (s: string, n = 80) => (s.length > n ? s.slice(0, n - 1) + '…' : s)
const bridgeAgeMs = computed(() => (
  bridgeStore.healthFetchedAt > 0 ? Math.max(0, nowMs.value - bridgeStore.healthFetchedAt) : 0
))
const isBridgeStale = computed(() => (
  !bridgeStore.healthError &&
  bridgeStore.healthFetchedAt > 0 &&
  bridgeAgeMs.value > BRIDGE_STALE_MS
))
const staleAgeLabel = computed(() => `${Math.round(bridgeAgeMs.value / 1000)}s`)

const bridgePill = computed<Pill>(() => {
  // bridgeStore polls /health every 5s; consecutiveFailures gates state.
  if (!bridgeStore.health && !bridgeStore.healthError) {
    return { tone: 'unknown', label: 'bridge ?' }
  }
  if (bridgeStore.healthError || bridgeStore.consecutiveFailures > 0) {
    return {
      tone: 'bad',
      label: `bridge ${truncate(bridgeStore.healthError ?? 'down', 60)}`,
      title: bridgeStore.healthError ?? 'down'
    }
  }
  if (isBridgeStale.value) {
    return {
      tone: 'warn',
      label: `bridge stale ${staleAgeLabel.value}`,
      title: `No fresh /health response for ${staleAgeLabel.value}`,
    }
  }
  const h = bridgeStore.health
  if (h && (h.status === 'ok' || h.status === 'OK')) {
    return { tone: 'good', label: 'bridge ok' }
  }
  return { tone: 'warn', label: `bridge ${h?.status ?? '?'}` }
})

const canPill = computed<Pill>(() => {
  if (bridgeStore.healthError || isBridgeStale.value) {
    return { tone: 'unknown', label: 'can ?' }
  }
  const can = bridgeStore.health?.can
  if (!bridgeStore.health) return { tone: 'unknown', label: 'can ?' }
  if (!can) return { tone: 'warn', label: 'can n/a' }
  const total = can.frames_total ?? 0
  if (!can.connected) {
    if (total === 0) return { tone: 'bad', label: 'can no device' }
    const age = can.last_frame_age_s
    const ageStr = typeof age === 'number' ? `${age.toFixed(1)}s ago` : 'recently'
    return { tone: 'warn', label: `can idle (last frame ${ageStr})` }
  }
  const fps = can.fps != null ? can.fps.toFixed(0) : '?'
  return { tone: 'good', label: `can ${fps} fps · ${total} frames` }
})

const llmPill = computed<Pill>(() => {
  if (bridgeStore.healthError || isBridgeStale.value) {
    return { tone: 'unknown', label: 'llm ?' }
  }
  const litert = bridgeStore.health?.litert
  if (!bridgeStore.health) return { tone: 'unknown', label: 'llm ?' }
  if (!litert) return { tone: 'warn', label: 'llm n/a' }
  if (!litert.up) {
    const fricErr = lastFriction.value?.error
    const reason = fricErr ? truncate(fricErr, 80) : 'transport down'
    return { tone: 'bad', label: `llm ${reason}`, title: fricErr ?? 'transport down' }
  }
  // Transport up — look at last completion
  const last = lastFriction.value
  if (!frictionFetched.value) {
    return { tone: 'good', label: `llm ${litert.http_model ?? 'up'}` }
  }
  if (!last) {
    return { tone: 'good', label: `llm ${litert.http_model ?? 'up'}` }
  }
  if (last.error) {
    return { tone: 'bad', label: `llm ${truncate(last.error, 80)}`, title: last.error }
  }
  if ((last.completion_chars ?? 0) <= 0) {
    return { tone: 'warn', label: 'llm templated fallback' }
  }
  return { tone: 'good', label: `llm ${litert.http_model ?? 'up'}` }
})

const pills = computed(() => [bridgePill.value, canPill.value, llmPill.value])

const dismiss = () => { dismissed.value = true }

onMounted(() => {
  // bridgeStore polling is already started from App.vue onMounted; do not
  // double-start it here. Just kick off our own friction loop.
  freshnessTimer = window.setInterval(() => {
    nowMs.value = Date.now()
  }, 1000)
  void pollFriction()
  scheduleFriction()
})

onUnmounted(() => {
  if (frictionTimer !== null) {
    window.clearTimeout(frictionTimer)
    frictionTimer = null
  }
  if (freshnessTimer !== null) {
    window.clearInterval(freshnessTimer)
    freshnessTimer = null
  }
})
</script>

<template>
  <div v-if="!dismissed" class="diag-bar" role="status" aria-label="Diagnostic status">
    <div class="pills">
      <span
        v-for="(p, i) in pills"
        :key="i"
        class="pill"
        :class="`tone-${p.tone}`"
        :title="p.title ?? p.label"
      >
        <span class="dot" aria-hidden="true"></span>
        <span class="pill-label">{{ p.label }}</span>
      </span>
    </div>
    <button class="dismiss" type="button" aria-label="Dismiss diagnostic bar" @click="dismiss">×</button>
  </div>
</template>

<style scoped>
.diag-bar {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  height: 28px;
  padding: 0 44px 0 8px; /* leave room for the fullscreen button on the right */
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
  background: rgba(13, 13, 18, 0.82);
  border-bottom: 1px solid rgba(124, 197, 255, 0.18);
  color: #c5c6c7;
  font-family: var(--font-ui, system-ui, sans-serif);
  font-size: 11px;
  line-height: 1;
  z-index: 9998; /* just under fullscreen toggle (9999) */
  backdrop-filter: blur(6px);
  -webkit-backdrop-filter: blur(6px);
  user-select: none;
}

.pills {
  display: flex;
  align-items: center;
  gap: 6px;
  overflow: hidden;
  flex: 1;
  min-width: 0;
}

.pill {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 3px 8px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.08);
  max-width: 50%;
  white-space: nowrap;
  overflow: hidden;
}

.pill-label {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #888;
  flex-shrink: 0;
}

.tone-good .dot { background: #4ade80; box-shadow: 0 0 6px rgba(74, 222, 128, 0.6); }
.tone-warn .dot { background: #fbbf24; box-shadow: 0 0 6px rgba(251, 191, 36, 0.6); }
.tone-bad  .dot { background: #f87171; box-shadow: 0 0 6px rgba(248, 113, 113, 0.6); }
.tone-unknown .dot { background: #6b7280; }

.tone-good { color: #d1fae5; }
.tone-warn { color: #fde68a; }
.tone-bad  { color: #fecaca; }
.tone-unknown { color: #9ca3af; }

.dismiss {
  background: transparent;
  border: none;
  color: rgba(197, 198, 199, 0.6);
  font-size: 18px;
  line-height: 1;
  width: 24px;
  height: 24px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  padding: 0;
  border-radius: 4px;
  -webkit-tap-highlight-color: transparent;
  flex-shrink: 0;
}

.dismiss:hover { color: #fff; background: rgba(255, 255, 255, 0.08); }
.dismiss:active { transform: scale(0.92); }
</style>

<script setup lang="ts">
/**
 * CoachVoiceButton — primary voice CTA for the coach loop.
 *
 * Composes `useVoiceConversation`: mic captures speech → final transcript is
 * submitted via coachStore.askStream → reply is auto-spoken via TTS. The
 * composable owns the actual SpeechRecognition / SpeechSynthesis plumbing;
 * this widget is purely the FAB + transient transcript bubble around it.
 *
 * Two interaction modes:
 *   • mode="toggle" (default): tap once to start listening, tap again to send.
 *     Best for the HUD where the driver shouldn't be holding a button.
 *   • mode="push":             pointerdown to listen, pointerup to send.
 *     Best for stationary screens where push-to-talk feels more natural.
 *
 * The button advertises four states (IDLE / LISTENING / THINKING / SPEAKING)
 * with distinct colours + icons so a driver can read it at a glance. If the
 * browser lacks SpeechRecognition the button renders DISABLED — never fakes
 * recognition, per the no-mocks rule.
 *
 * The widget force-enables auto-speak on mount so the reply is always read
 * out — the entire point of clicking the mic is hands-free conversation.
 * The user can still mute via voice.stop() (exposed by the composable).
 */
import { computed, onMounted } from 'vue'
import { useVoiceConversation } from '@/entities/coach/model/useVoiceConversation'
import { useCoachStore } from '@/entities/coach/model/coachStore'

const props = withDefaults(defineProps<{
  /** 'toggle' = tap to start / tap to send. 'push' = hold to talk. */
  mode?: 'toggle' | 'push'
  /** Visual position. 'inline' lets the parent place it manually. */
  position?: 'fixed-br' | 'fixed-bl' | 'inline'
  /** Override the recognizer language. Defaults to en-US. */
  lang?: string
  /** ARIA / tooltip override. */
  label?: string
}>(), {
  mode: 'toggle',
  position: 'fixed-br',
  lang: 'en-US',
})

const coach = useCoachStore()
const v = useVoiceConversation({ lang: props.lang })

// Always speak coach replies when the user invoked this surface — they
// clicked a microphone, so they want their answer read aloud. We don't
// touch the persisted setting (which the Ask-Coach text UI honours).
onMounted(() => {
  if (!v.autoSpeak.value && v.supported.value.speak) {
    // Don't persist — just enable for this session.
    v.autoSpeak.value = true
  }
})

// ── Visual state ─────────────────────────────────────────────────────────

type UiState = 'disabled' | 'idle' | 'listening' | 'thinking' | 'speaking'

const uiState = computed<UiState>(() => {
  if (!v.supported.value.listen) return 'disabled'
  if (v.isListening.value) return 'listening'
  if (coach.isAsking || coach.isStreaming) return 'thinking'
  if (v.isSpeaking.value) return 'speaking'
  return 'idle'
})

const ariaLabel = computed(() => {
  if (props.label) return props.label
  switch (uiState.value) {
    case 'disabled':  return 'Voice input unavailable in this browser'
    case 'listening': return 'Listening… tap to send or release'
    case 'thinking':  return 'Coach is thinking…'
    case 'speaking':  return 'Coach is speaking — tap to stop'
    case 'idle':      return props.mode === 'push'
      ? 'Hold to talk to coach'
      : 'Tap to talk to coach'
  }
  return 'Talk to coach'
})

// Show a short transcript bubble while listening so the driver gets
// feedback that the recognizer is picking up their words.
const showTranscriptBubble = computed(() =>
  v.isListening.value || v.interimTranscript.value.length > 0,
)

// ── Interaction handlers ─────────────────────────────────────────────────

function handleToggleClick() {
  if (uiState.value === 'disabled') return
  // If the coach is currently speaking, a tap = "stop talking and start
  // listening" — a natural barge-in gesture.
  if (uiState.value === 'speaking') {
    v.stopSpeaking()
    v.pushToTalkStart()
    return
  }
  // If thinking, ignore — wait for the reply.
  if (uiState.value === 'thinking') return

  if (v.isListening.value) {
    void v.pushToTalkStop()
  } else {
    v.pushToTalkStart()
  }
}

function handlePushDown(e: PointerEvent) {
  if (props.mode !== 'push') return
  if (uiState.value === 'disabled') return
  e.preventDefault()
  if (uiState.value === 'speaking') v.stopSpeaking()
  v.pushToTalkStart()
}

function handlePushUp(e: PointerEvent) {
  if (props.mode !== 'push') return
  if (!v.isListening.value) return
  e.preventDefault()
  void v.pushToTalkStop()
}

function handlePushCancel() {
  if (props.mode !== 'push') return
  if (!v.isListening.value) return
  v.abort()
}

// Exposed so a parent (e.g. OnTrackHud) can wire a keyboard shortcut to
// the same handler without reaching into the composable directly.
defineExpose({
  trigger: handleToggleClick,
  abort: () => v.abort(),
})
</script>

<template>
  <div
    class="cvb-host"
    :class="[
      `cvb-host--${position}`,
      `cvb-host--state-${uiState}`,
    ]"
  >
    <!-- Live interim transcript bubble (only while LISTENING) -->
    <div
      v-if="showTranscriptBubble"
      class="cvb-transcript"
      role="status"
      aria-live="polite"
    >
      <span aria-hidden="true" class="cvb-transcript__cursor">▌</span>
      <span class="cvb-transcript__text">
        {{ v.interimTranscript.value || 'listening…' }}
      </span>
    </div>

    <!-- Error pill (mic permission denied, etc.) -->
    <div
      v-else-if="v.lastError.value"
      class="cvb-error"
      role="alert"
      :title="v.lastError.value"
    >
      voice: {{ v.lastError.value }}
    </div>

    <!-- Streaming preview while THINKING (first tokens of reply) -->
    <div
      v-else-if="uiState === 'thinking' && coach.streamingText"
      class="cvb-transcript cvb-transcript--reply"
      role="status"
      aria-live="polite"
    >
      <span class="cvb-transcript__text">{{ coach.streamingText.slice(-120) }}</span>
    </div>

    <button
      type="button"
      class="cvb-fab"
      :class="`cvb-fab--${uiState}`"
      :aria-label="ariaLabel"
      :title="ariaLabel"
      :disabled="uiState === 'disabled'"
      @click="mode === 'toggle' ? handleToggleClick() : null"
      @pointerdown="handlePushDown"
      @pointerup="handlePushUp"
      @pointerleave="handlePushCancel"
      @pointercancel="handlePushCancel"
    >
      <!-- Icon swap per state. Inline SVG so we don't pull in a sprite. -->
      <svg
        v-if="uiState === 'idle'"
        class="cvb-icon" viewBox="0 0 24 24" fill="none"
        stroke="currentColor" stroke-width="2.2" stroke-linecap="round"
        stroke-linejoin="round" aria-hidden="true"
      >
        <path d="M12 2a3 3 0 0 0-3 3v6a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3z" />
        <path d="M19 11a7 7 0 0 1-14 0" />
        <line x1="12" y1="18" x2="12" y2="22" />
        <line x1="8" y1="22" x2="16" y2="22" />
      </svg>
      <svg
        v-else-if="uiState === 'listening'"
        class="cvb-icon" viewBox="0 0 24 24" fill="none"
        stroke="currentColor" stroke-width="2.2" stroke-linecap="round"
        stroke-linejoin="round" aria-hidden="true"
      >
        <rect x="9" y="3" width="6" height="11" rx="3" fill="currentColor" />
        <path d="M5 11a7 7 0 0 0 14 0" />
        <line x1="12" y1="18" x2="12" y2="22" />
        <line x1="8" y1="22" x2="16" y2="22" />
      </svg>
      <svg
        v-else-if="uiState === 'thinking'"
        class="cvb-icon cvb-icon--spin" viewBox="0 0 24 24" fill="none"
        stroke="currentColor" stroke-width="2.4" stroke-linecap="round"
        aria-hidden="true"
      >
        <path d="M12 3a9 9 0 0 1 9 9" />
        <path d="M21 12a9 9 0 1 1-9-9" opacity="0.25" />
      </svg>
      <svg
        v-else-if="uiState === 'speaking'"
        class="cvb-icon" viewBox="0 0 24 24" fill="none"
        stroke="currentColor" stroke-width="2.2" stroke-linecap="round"
        stroke-linejoin="round" aria-hidden="true"
      >
        <polygon points="4 9 8 9 13 5 13 19 8 15 4 15 4 9" fill="currentColor" />
        <path d="M16 8a5 5 0 0 1 0 8" />
        <path d="M19 5a9 9 0 0 1 0 14" />
      </svg>
      <svg
        v-else
        class="cvb-icon" viewBox="0 0 24 24" fill="none"
        stroke="currentColor" stroke-width="2.2" stroke-linecap="round"
        stroke-linejoin="round" aria-hidden="true"
      >
        <line x1="3" y1="3" x2="21" y2="21" />
        <path d="M9 5a3 3 0 0 1 6 0v6" />
        <path d="M9 11v0a3 3 0 0 0 4.24 2.74" />
        <path d="M19 11a7 7 0 0 1-11.5 5.4" />
        <line x1="8" y1="22" x2="16" y2="22" />
        <line x1="12" y1="18" x2="12" y2="22" />
      </svg>
    </button>
  </div>
</template>

<style scoped>
/* ── Host positioning ──────────────────────────────────────────────────── */
.cvb-host {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 8px;
  pointer-events: none; /* children opt back in */
}
.cvb-host--fixed-br {
  position: fixed;
  /* Sit above the bottom-edge safe area but clear of any HintBar. */
  right: calc(max(var(--safe-right), var(--space-md)));
  bottom: calc(max(var(--safe-bottom), var(--space-md)) + 12px);
  z-index: 180; /* above panels, below modals (200+) */
}
.cvb-host--fixed-bl {
  position: fixed;
  left: calc(max(var(--safe-left), var(--space-md)));
  bottom: calc(max(var(--safe-bottom), var(--space-md)) + 12px);
  z-index: 180;
  align-items: flex-start;
}
.cvb-host--inline {
  position: relative;
  display: inline-flex;
}

/* ── Transcript bubble ─────────────────────────────────────────────────── */
.cvb-transcript {
  pointer-events: none;
  max-width: clamp(160px, 38vw, 320px);
  padding: 4px 10px;
  background: color-mix(in srgb, var(--color-ink) 88%, transparent);
  border: 1px solid color-mix(in srgb, var(--color-ui-info) 55%, transparent);
  color: var(--color-silver);
  font-family: var(--font-mono);
  font-size: clamp(10px, 1.6vmin, 13px);
  letter-spacing: 0.02em;
  line-height: 1.4;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.cvb-transcript--reply {
  border-color: color-mix(in srgb, var(--color-ui-good) 55%, transparent);
}
.cvb-transcript__cursor {
  color: var(--color-ui-info);
  margin-right: 4px;
  animation: cvb-blink 1s steps(2) infinite;
}
.cvb-error {
  pointer-events: none;
  max-width: clamp(160px, 38vw, 320px);
  padding: 4px 10px;
  background: color-mix(in srgb, var(--color-ink) 88%, transparent);
  border: 1px solid color-mix(in srgb, var(--color-ui-bad) 60%, transparent);
  color: var(--color-ui-bad);
  font-family: var(--font-mono);
  font-size: clamp(10px, 1.6vmin, 12px);
  letter-spacing: 0.02em;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* ── The FAB itself ────────────────────────────────────────────────────── */
.cvb-fab {
  pointer-events: auto;
  width: 64px;
  height: 64px;
  min-width: 64px;
  min-height: 64px;
  border-radius: 50%;
  border: 2px solid var(--color-slate);
  background: color-mix(in srgb, var(--color-ink) 90%, transparent);
  color: var(--color-silver);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  user-select: none;
  -webkit-tap-highlight-color: transparent;
  touch-action: manipulation;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.45);
  transition:
    border-color 140ms ease,
    color 140ms ease,
    background-color 140ms ease,
    transform 120ms ease,
    box-shadow 180ms ease;
}
.cvb-fab:active { transform: translateY(1px) scale(0.98); }
.cvb-fab:focus-visible {
  outline: 2px solid var(--color-ui-info);
  outline-offset: 3px;
}

/* State variants */
.cvb-fab--idle {
  border-color: var(--color-slate);
  color: var(--color-silver);
}
.cvb-fab--idle:hover {
  border-color: var(--color-ui-info);
  color: var(--color-ui-info);
}
.cvb-fab--listening {
  border-color: var(--color-ui-good);
  color: var(--color-ui-good);
  background: color-mix(in srgb, var(--color-ui-good) 14%, var(--color-ink));
  box-shadow: 0 0 0 0 color-mix(in srgb, var(--color-ui-good) 50%, transparent);
  animation: cvb-pulse-good 1.2s ease-out infinite;
}
.cvb-fab--thinking {
  border-color: var(--color-ui-warn, var(--color-ui-info));
  color: var(--color-ui-warn, var(--color-ui-info));
  background: color-mix(in srgb, var(--color-ink) 92%, transparent);
  cursor: progress;
}
.cvb-fab--speaking {
  border-color: var(--color-ui-info);
  color: var(--color-ui-info);
  background: color-mix(in srgb, var(--color-ui-info) 14%, var(--color-ink));
  box-shadow: 0 0 0 0 color-mix(in srgb, var(--color-ui-info) 50%, transparent);
  animation: cvb-pulse-info 1.4s ease-out infinite;
}
.cvb-fab--disabled {
  border-color: color-mix(in srgb, var(--color-slate) 40%, transparent);
  color: color-mix(in srgb, var(--color-slate) 60%, transparent);
  background: transparent;
  cursor: not-allowed;
  box-shadow: none;
}

/* Icon sizing + spin */
.cvb-icon {
  width: 28px;
  height: 28px;
}
.cvb-icon--spin {
  animation: cvb-spin 1.1s linear infinite;
}

/* Animations */
@keyframes cvb-blink {
  0%, 100% { opacity: 0.35; }
  50% { opacity: 1; }
}
@keyframes cvb-pulse-good {
  0%   { box-shadow: 0 0 0 0   color-mix(in srgb, var(--color-ui-good) 55%, transparent); }
  70%  { box-shadow: 0 0 0 16px color-mix(in srgb, var(--color-ui-good)  0%, transparent); }
  100% { box-shadow: 0 0 0 0   color-mix(in srgb, var(--color-ui-good)  0%, transparent); }
}
@keyframes cvb-pulse-info {
  0%   { box-shadow: 0 0 0 0   color-mix(in srgb, var(--color-ui-info) 55%, transparent); }
  70%  { box-shadow: 0 0 0 16px color-mix(in srgb, var(--color-ui-info)  0%, transparent); }
  100% { box-shadow: 0 0 0 0   color-mix(in srgb, var(--color-ui-info)  0%, transparent); }
}
@keyframes cvb-spin {
  to { transform: rotate(360deg); }
}

@media (prefers-reduced-motion: reduce) {
  .cvb-fab--listening,
  .cvb-fab--speaking { animation: none; }
  .cvb-icon--spin { animation-duration: 2.5s; }
  .cvb-transcript__cursor { animation: none; opacity: 0.8; }
}
</style>

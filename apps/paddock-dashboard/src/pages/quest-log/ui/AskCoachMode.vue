<script setup lang="ts">
/**
 * Ask Coach Mode — Q&A entry point with intent override + history.
 *
 * Three stacked panels:
 *   • Top:    question input + intent-picker chip row (from /coach/agents).
 *   • Middle: current conversation thread (in-memory; lives until session end).
 *   • Bottom: persisted history (last N coach_brief / coach_debrief records
 *             from /conversations/driver/{driver_id}).
 *
 * Per ADR-022 every request goes through the bridge — never directly to
 * LocalLLM on :8099. ADK paddock latency is 2–15 s; show the loading state
 * via the existing useLoadingStore hook in coachStore.
 *
 * Per the 2026-05-12 routing audit, the `intent` chip is the documented
 * escape hatch when the regex classifier in adk_agents.py misroutes a
 * natural-language query. Selecting an intent forces the orchestrator to
 * use the matching specialist agent.
 */
import { computed, onMounted, ref } from 'vue'
import { useCoachStore } from '@/entities/coach/model/coachStore'
import { useSaveStore } from '@/entities/save/model/saveStore'
import { useSessionStore } from '@/entities/session/model/sessionStore'
import { useVoiceConversation } from '@/entities/coach/model/useVoiceConversation'
import CyberPanel from '@/shared/ui/core/CyberPanel.vue'
import CyberButton from '@/shared/ui/core/CyberButton.vue'

const props = defineProps<{ active: boolean }>()

const coach = useCoachStore()
const save = useSaveStore()
const session = useSessionStore()

const question = ref('')
const selectedIntent = ref<string | null>(null)
const useStreaming = ref(true)

// Voice: push-to-talk mic + auto-speak of coach replies.
// Composable handles permission prompt, SpeechRecognition/Synthesis
// feature detection, and the auto-speak watcher.
const v = useVoiceConversation()

const driverId = computed(() => save.activeSlot?.driverName ?? 'driver')
const sessionId = computed(() => session.activeSessionId ?? '')

const canSubmit = computed(() =>
  question.value.trim().length > 0 && !coach.isAsking && !coach.isStreaming,
)

onMounted(() => {
  coach.fetchAgents()
  coach.fetchHistory(driverId.value)
})

async function submit() {
  if (!canSubmit.value) return
  const q = question.value.trim()
  question.value = ''
  const opts = {
    driverId: driverId.value,
    sessionId: sessionId.value,
    intent: selectedIntent.value ?? undefined,
  }
  if (useStreaming.value) {
    await coach.askStream(q, opts)
  } else {
    await coach.ask(q, opts)
  }
}

/**
 * Explicit agent-name → bridge intent map.
 *
 * Audit fix 2026-05-13: the previous naive camelCase→snake_case conversion
 * produced wrong intent names for 11 of 17 agents (CornerCoachAgent →
 * `corner_coach` instead of `corner`, SessionPlannerAgent → `session_planner`
 * instead of `session_plan`, etc.). The intent values here MUST match the
 * keys in `_VALID_INTENTS` in `src/pitwall/features/coaching/adk_agents.py`.
 *
 * Two agents (HighlightFinderAgent, PedagogyAgent) are pipeline-only —
 * they only run inside the debrief / brief pipelines and aren't reachable
 * via /coach/ask intent override. Mapped to `null` so the picker hides
 * them.
 */
const AGENT_INTENT_MAP: Record<string, string | null> = {
  TelemetryAgent:         'telemetry',
  LapComparisonAgent:     'lap_comparison',
  CornerCoachAgent:       'corner',
  ProgressTrackerAgent:   'progress',
  SetupAdvisorAgent:      'setup',
  MindsetCoachAgent:      'mindset',
  GoldLapAgent:           'gold_lap',
  WeatherAdaptationAgent: 'weather',
  SessionPlannerAgent:    'session_plan',
  IncidentReviewAgent:    'incident',
  RacePaceAgent:          'race_pace',
  GoalSettingAgent:       'goal',
  MentalMapAgent:         'mental_map',
  VoiceScriptAgent:       'voice_script',
  AgentMetaAgent:         'agent_meta',
  // Pipeline-only — hide from picker.
  HighlightFinderAgent:   null,
  PedagogyAgent:          null,
}

function intentForAgent(agentName: string): string | null {
  if (agentName in AGENT_INTENT_MAP) return AGENT_INTENT_MAP[agentName]
  // Forward-compat: any new agent registered server-side falls back to the
  // previous snake-case heuristic so we don't crash. The picker will still
  // route via the regex classifier in that case (orchestrator falls back
  // when intent isn't in _VALID_INTENTS).
  return agentName
    .replace(/Agent$/, '')
    .replace(/Pipeline$/, '')
    .replace(/([a-z])([A-Z])/g, '$1_$2')
    .toLowerCase()
}

function pickIntent(agentName: string) {
  const intent = intentForAgent(agentName)
  if (!intent) return  // pipeline-only agent — silently no-op
  selectedIntent.value = selectedIntent.value === intent ? null : intent
}

/** Agents the picker should show — excludes pipeline-only agents that
 *  aren't reachable via /coach/ask intent override. */
const pickableAgents = computed(() =>
  coach.agents.filter(a => intentForAgent(a.name) !== null),
)

function exampleClick(text: string) {
  question.value = text
}
</script>

<template>
  <div v-if="active" class="ask-coach-mode flex flex-col gap-3 h-full">
    <!-- Input + intent picker -->
    <CyberPanel variant="solid" border="primary" class="flex-shrink-0 p-3">
      <h2 class="section-label mb-2 text-ui-good">ASK THE COACH</h2>

      <textarea
        v-model="question"
        rows="3"
        placeholder="Why was lap 4 faster than lap 2? — or pick an intent below."
        class="w-full bg-ink border border-slate p-2 text-silver font-mono text-[clamp(11px,2vmin,14px)]"
        :disabled="coach.isAsking || coach.isStreaming"
        @keydown.enter.meta="submit"
      />

      <!-- Intent picker chips: routing escape hatch (audit 2026-05-12) -->
      <div v-if="pickableAgents.length" class="mt-2">
        <div class="text-small text-slate mb-1 tracking-widest">INTENT (OPTIONAL)</div>
        <div class="flex flex-wrap gap-1">
          <button
            v-for="a in pickableAgents"
            :key="a.name"
            type="button"
            class="intent-chip px-2 py-1 text-small border font-mono"
            :class="selectedIntent === intentForAgent(a.name)
              ? 'border-ui-good text-ui-good bg-charcoal'
              : 'border-slate text-silver hover:border-ui-info'"
            :title="a.role"
            @click="pickIntent(a.name)"
          >
            {{ a.name.replace(/Agent$/, '').replace(/Pipeline$/, '') }}
          </button>
        </div>
        <div v-if="selectedIntent" class="text-xs text-ui-info mt-1 italic">
          Override active — orchestrator will skip regex routing and dispatch
          straight to the <span class="text-ui-good">{{ selectedIntent }}</span> agent.
        </div>
      </div>

      <div v-else-if="coach.agentsLoading" class="text-small text-slate mt-2">
        Loading agent registry...
      </div>
      <div v-else-if="coach.agentsError" class="text-small text-ui-bad mt-2">
        Agent registry unavailable: {{ coach.agentsError }}
      </div>

      <!-- Submit row -->
      <div class="flex items-center gap-2 mt-3 flex-wrap">
        <label class="text-small text-slate flex items-center gap-1">
          <input v-model="useStreaming" type="checkbox" /> stream
        </label>

        <!-- Auto-speak toggle: only shown if TTS is available -->
        <label
          v-if="v.supported.value.speak"
          class="text-small text-slate flex items-center gap-1"
          :title="v.autoSpeak.value
            ? 'Coach replies will be spoken aloud'
            : 'Coach replies are text-only'"
        >
          <input
            type="checkbox"
            :checked="v.autoSpeak.value"
            @change="v.toggleAutoSpeak()"
          />
          speak
        </label>

        <CyberButton size="sm" :disabled="!canSubmit" @click="submit">
          ASK
        </CyberButton>

        <!-- Push-to-talk mic. Hidden if SpeechRecognition isn't available
             (Firefox desktop, etc.) — text input still works fine there. -->
        <button
          v-if="v.supported.value.listen"
          type="button"
          class="mic-btn"
          :class="{ 'mic-btn--listening': v.isListening.value }"
          :title="v.isListening.value
            ? 'Release to send'
            : 'Press and hold to talk'"
          @pointerdown.prevent="v.pushToTalkStart()"
          @pointerup.prevent="v.pushToTalkStop()"
          @pointerleave.prevent="v.isListening.value && v.pushToTalkStop()"
          @pointercancel.prevent="v.abort()"
        >
          <span aria-hidden="true">🎙</span>
          {{ v.isListening.value ? 'LISTENING' : 'HOLD TO TALK' }}
        </button>

        <!-- Stop button while coach is speaking aloud -->
        <button
          v-if="v.isSpeaking.value"
          type="button"
          class="intent-chip px-2 py-1 text-small border border-ui-warn text-ui-warn"
          title="Stop the coach from speaking"
          @click="v.stopSpeaking()"
        >
          ◾ STOP SPEAKING
        </button>

        <span v-if="coach.isAsking || coach.isStreaming" class="text-small text-ui-info">
          paddock thinking...
        </span>
      </div>

      <!-- Live interim transcript while the user is holding the mic. -->
      <div
        v-if="v.isListening.value || v.interimTranscript.value"
        class="text-small text-ui-info mt-2 italic font-mono"
      >
        <span aria-hidden="true">▌</span>
        {{ v.interimTranscript.value || 'listening…' }}
      </div>

      <div
        v-if="v.lastError.value"
        class="text-small text-ui-bad mt-2"
        :title="v.lastError.value"
      >
        Voice error: {{ v.lastError.value }}
      </div>
    </CyberPanel>

    <!-- Current conversation -->
    <CyberPanel variant="glass" border="secondary" class="flex-1 overflow-y-auto p-3 min-h-0">
      <div class="flex items-end justify-between border-b border-slate pb-1 mb-2">
        <h2 class="section-label m-0">CURRENT THREAD</h2>
        <span class="text-small text-slate">{{ coach.conversation.length }} turns</span>
      </div>

      <div v-if="!coach.conversation.length && !coach.streamingText" class="text-small text-slate italic">
        No active conversation. Ask the coach a question above.
      </div>

      <div v-for="(t, i) in coach.conversation" :key="t.recorded_at ?? `turn-${i}-${t.role}-${t.text.slice(0, 32)}`" class="mb-3">
        <div class="text-small font-bold mb-1"
             :class="t.role === 'user' ? 'text-ui-info' : 'text-ui-good'">
          {{ t.role === 'user' ? 'YOU' : 'COACH' }}
          <span v-if="t.emotion" class="text-slate font-normal ml-2">({{ t.emotion }})</span>
        </div>
        <div class="text-silver whitespace-pre-wrap font-mono text-[clamp(11px,2vmin,13px)]">
          {{ t.text }}
        </div>
      </div>

      <div v-if="coach.isStreaming && coach.streamingText" class="mb-3">
        <div class="text-small font-bold text-ui-good mb-1">COACH (live)</div>
        <div class="text-silver whitespace-pre-wrap font-mono text-[clamp(11px,2vmin,13px)]">
          {{ coach.streamingText }}<span class="animate-pulse">▍</span>
        </div>
      </div>

      <!-- Example question hints from the registry -->
      <div v-if="!coach.conversation.length && coach.agents.length" class="mt-4">
        <div class="text-small text-slate tracking-widest mb-1">TRY ASKING:</div>
        <ul class="text-small text-silver space-y-1">
          <li
            v-for="ex in coach.agents.flatMap(a => a.example_questions ?? []).slice(0, 6)"
            :key="ex"
            class="cursor-pointer hover:text-ui-info"
            @click="exampleClick(ex)"
          >
            · {{ ex }}
          </li>
        </ul>
      </div>
    </CyberPanel>

    <!-- Persisted history -->
    <CyberPanel variant="glass" border="secondary" class="flex-shrink-0 max-h-[28%] overflow-y-auto p-3">
      <div class="flex items-end justify-between border-b border-slate pb-1 mb-2">
        <h2 class="section-label m-0">RECENT BRIEFS &amp; DEBRIEFS</h2>
        <span class="text-small text-slate">{{ coach.historyTurns.length }} records · driver {{ driverId }}</span>
      </div>

      <div v-if="coach.historyLoading" class="text-small text-slate">Loading...</div>
      <div v-else-if="coach.historyError" class="text-small text-ui-bad">
        {{ coach.historyError }}
      </div>
      <div v-else-if="!coach.historyTurns.length" class="text-small text-slate italic">
        No persisted conversations yet.
      </div>

      <div v-for="h in coach.historyTurns" :key="`${h.session_id}-${h.recorded_at}`" class="mb-2">
        <div class="text-small text-slate font-mono">
          [{{ h.recorded_at ?? '?' }}] {{ h.role }}
          <span v-if="h.emotion" class="text-ui-info">· {{ h.emotion }}</span>
        </div>
        <div class="text-small text-silver font-mono truncate">{{ h.text }}</div>
      </div>
    </CyberPanel>
  </div>
</template>

<style scoped>
.section-label {
  font-family: var(--font-title);
  font-size: clamp(10px, 2.5vmin, 18px);
  color: var(--color-silver);
  letter-spacing: 0.12em;
}

/* Push-to-talk button. Mirrors CyberButton's small-size look but adds a
   pulsing red ring while the mic is hot so the driver can tell at a
   glance whether the recognizer is capturing. */
.mic-btn {
  background: transparent;
  border: 1px solid var(--color-slate);
  color: var(--color-silver);
  font-family: var(--font-ui);
  font-size: clamp(10px, 1.7vmin, 13px);
  letter-spacing: 0.1em;
  padding: 4px 10px;
  min-height: var(--touch-target-min);
  cursor: pointer;
  user-select: none;
  -webkit-tap-highlight-color: transparent;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  touch-action: manipulation;
  transition: border-color 120ms ease, color 120ms ease;
}

.intent-chip {
  min-height: var(--touch-target-min);
  display: inline-flex;
  align-items: center;
}
.mic-btn:hover { border-color: var(--color-ui-info); color: var(--color-ui-info); }
.mic-btn:active { transform: translateY(1px); }
.mic-btn--listening {
  border-color: var(--color-ui-bad, #e85a5a);
  color: var(--color-ui-bad, #e85a5a);
  background: rgba(232, 90, 90, 0.06);
  box-shadow: 0 0 8px rgba(232, 90, 90, 0.45);
  animation: mic-pulse 1.1s steps(2) infinite;
}
@keyframes mic-pulse {
  0%   { opacity: 0.7; }
  100% { opacity: 1; }
}
</style>

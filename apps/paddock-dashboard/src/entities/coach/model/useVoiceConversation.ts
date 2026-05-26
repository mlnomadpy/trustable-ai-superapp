/**
 * useVoiceConversation — drives a back-and-forth voice dialog with the
 * coach. Combines the Web Speech API wrappers in `shared/lib/voice.ts`
 * with the existing `useCoachStore` Q&A pipeline.
 *
 * Behaviour:
 *   • pushToTalkStart() → mic opens, interim transcript flows into
 *     `interimTranscript`. Caller typically wires this to the
 *     pointerdown / touchstart event of a mic button.
 *   • pushToTalkStop() → mic closes, the final transcript is submitted
 *     via coachStore.askStream(); if it's empty (user released without
 *     speaking) the call is skipped.
 *   • autoSpeak (toggle, persisted in localStorage): when true, the
 *     composable watches coachStore.conversation; every new coach turn
 *     is spoken aloud via TTS as soon as it finalizes. The streaming
 *     interim text is NOT spoken to avoid stuttering — the final-once
 *     pattern matches how voice assistants feel.
 *   • abort() — stop any in-flight mic + TTS at once. Bind this to the
 *     screen-edge swipe or the "stop talking" button.
 *
 * The composable doesn't own the coachStore — it observes it. Multiple
 * pages can mount it simultaneously without fighting over state.
 */

import { computed, onUnmounted, ref, watch } from 'vue'
import { useCoachStore } from '@/entities/coach/model/coachStore'
import { useSessionStore } from '@/entities/session/model/sessionStore'
import { useSaveStore } from '@/entities/save/model/saveStore'
import { voice, type ListenHandle } from '@/shared/lib/voice'

const AUTOSPEAK_STORAGE_KEY = 'pitwall.voice.autoSpeak'

function _readAutoSpeak(): boolean {
  if (typeof localStorage === 'undefined') return false
  try { return localStorage.getItem(AUTOSPEAK_STORAGE_KEY) === '1' }
  catch { return false }
}
function _writeAutoSpeak(v: boolean): void {
  if (typeof localStorage === 'undefined') return
  try { localStorage.setItem(AUTOSPEAK_STORAGE_KEY, v ? '1' : '0') }
  catch { /* ignore quota errors etc. */ }
}

export interface UseVoiceConversationOptions {
  /** Override the recognizer language; defaults to 'en-US'. */
  lang?: string
  /** If true, skip the auto-speak feature entirely (e.g. on a page where
   *  TTS would interfere with another audio surface). */
  disableAutoSpeak?: boolean
}

export function useVoiceConversation(opts: UseVoiceConversationOptions = {}) {
  const coach   = useCoachStore()
  const session = useSessionStore()
  const save    = useSaveStore()

  const isListening      = ref(false)
  const interimTranscript = ref('')
  const finalTranscript   = ref('')
  const lastError         = ref<string | null>(null)
  const isSpeaking        = ref(false)
  const autoSpeak         = ref(_readAutoSpeak() && !opts.disableAutoSpeak)

  let _handle: ListenHandle | null = null

  const supported = computed(() => ({
    listen: voice.canListen,
    speak:  voice.canSpeak,
  }))

  const driverId = computed(() => save.activeSlot?.driverName ?? 'driver')
  const sessionId = computed(() => session.activeSessionId ?? '')

  // ── Push-to-talk ──────────────────────────────────────────────────────

  function pushToTalkStart() {
    if (isListening.value || !supported.value.listen) return
    lastError.value         = null
    interimTranscript.value = ''
    finalTranscript.value   = ''
    isListening.value       = true

    _handle = voice.listen({
      lang: opts.lang ?? 'en-US',
      continuous: true,                          // user controls release
      onInterim: t => { interimTranscript.value = t },
    })
    _handle.finished
      .then(text => { finalTranscript.value = text })
      .catch(err => { lastError.value = err?.message ?? String(err) })
      .finally(() => {
        isListening.value       = false
        interimTranscript.value = ''
        _handle = null
      })
  }

  async function pushToTalkStop() {
    if (!_handle) return
    _handle.stop()
    // Wait for the recognizer to settle; finalTranscript ref is updated
    // in the .then() above. Tiny delay so the watcher sees the value.
    await new Promise<void>(r => setTimeout(r, 30))
    const text = finalTranscript.value.trim()
    if (!text) return
    // Hand off to the existing coach Q&A pipeline (streaming).
    await coach.askStream(text, {
      driverId: driverId.value,
      sessionId: sessionId.value,
    })
  }

  // ── Auto-speak: TTS coach replies as they finalize ────────────────────

  // Track which conversation indexes we've already spoken so we don't
  // re-speak old turns when the user toggles autoSpeak on mid-session.
  const _spokenIndexes = new Set<number>()

  watch(
    () => coach.conversation.length,
    async (newLen) => {
      if (!autoSpeak.value || !supported.value.speak) return
      if (newLen === 0) return
      const idx = newLen - 1
      const turn = coach.conversation[idx]
      // coachStore pushes coach replies with role 'assistant'; accept the
      // legacy 'coach' label too so this composable works against any
      // ConversationTurn shape (e.g. /conversations/driver/{id} history).
      if (!turn || !['assistant', 'coach'].includes(turn.role as string)) return
      if (_spokenIndexes.has(idx)) return
      _spokenIndexes.add(idx)
      isSpeaking.value = true
      try {
        await voice.speak(turn.text)
      } catch {
        // TTS errors are non-fatal; user can read the text on screen.
      } finally {
        isSpeaking.value = false
      }
    },
  )

  function setAutoSpeak(v: boolean) {
    autoSpeak.value = v
    _writeAutoSpeak(v)
    if (!v) voice.stop()  // shut up immediately
  }

  function toggleAutoSpeak() { setAutoSpeak(!autoSpeak.value) }

  function stopSpeaking() {
    voice.stop()
    isSpeaking.value = false
  }

  function abort() {
    if (_handle) { _handle.stop(); _handle = null }
    isListening.value       = false
    interimTranscript.value = ''
    stopSpeaking()
  }

  onUnmounted(abort)

  return {
    // reactive state
    isListening, interimTranscript, finalTranscript, lastError,
    isSpeaking, autoSpeak, supported,
    // actions
    pushToTalkStart, pushToTalkStop,
    setAutoSpeak, toggleAutoSpeak,
    stopSpeaking, abort,
  }
}

/**
 * Web Speech API wrappers — TTS (speak) + STT (listen).
 *
 * Browsers expose two related APIs:
 *   - SpeechSynthesis     — text → audio out the speakers (TTS). Universally
 *                           supported on modern browsers + Android WebView.
 *   - SpeechRecognition   — mic → text (STT). Webkit-prefixed on Safari +
 *                           older Chromium; modern Chromium on Android uses
 *                           on-device Gemini Nano for offline recognition.
 *
 * Both gracefully degrade: if the runtime doesn't expose the API, the
 * corresponding `can*` flag is false and calls are no-ops returning sensible
 * defaults. UI code can hide controls accordingly.
 */

// ── SpeechRecognition global typing ──────────────────────────────────────
// The DOM lib's SpeechRecognition type isn't universally available, and the
// webkit prefix needs special handling. We define a minimal interface here.
interface MinimalSpeechRecognition extends EventTarget {
  lang: string
  continuous: boolean
  interimResults: boolean
  maxAlternatives: number
  start(): void
  stop(): void
  abort(): void
  onresult: ((this: any, ev: any) => any) | null
  onerror: ((this: any, ev: any) => any) | null
  onstart: ((this: any, ev: any) => any) | null
  onend: ((this: any, ev: any) => any) | null
}

type SpeechRecognitionCtor = new () => MinimalSpeechRecognition

function _getRecognitionCtor(): SpeechRecognitionCtor | null {
  if (typeof window === 'undefined') return null
  const w = window as any
  return (w.SpeechRecognition || w.webkitSpeechRecognition || null) as SpeechRecognitionCtor | null
}

// ── Voice cache ──────────────────────────────────────────────────────────
// `speechSynthesis.getVoices()` returns [] on first call in Chrome; the voice
// list arrives asynchronously and fires a `voiceschanged` event. Cache it on
// that event so callers don't have to re-pick on every speak().

let _voiceCache: SpeechSynthesisVoice[] = []
let _voiceCacheReady = false

if (typeof window !== 'undefined' && window.speechSynthesis) {
  const refresh = () => {
    const list = window.speechSynthesis.getVoices()
    if (list.length) {
      _voiceCache = list
      _voiceCacheReady = true
    }
  }
  refresh()
  window.speechSynthesis.addEventListener('voiceschanged', refresh)
}

function pickCoachingVoice(): SpeechSynthesisVoice | undefined {
  // Preference order, top → bottom:
  //   1. English UK male (matches the "coaching" voice character we want)
  //   2. Any English UK voice
  //   3. Any English US voice
  //   4. Anything English
  //   5. Default (let browser pick)
  if (!_voiceCache.length) return undefined
  const en_gb_male = _voiceCache.find(v =>
    v.lang === 'en-GB' && /male|david|daniel|bruce/i.test(v.name))
  if (en_gb_male) return en_gb_male
  const en_gb = _voiceCache.find(v => v.lang === 'en-GB')
  if (en_gb) return en_gb
  const en_us = _voiceCache.find(v => v.lang === 'en-US')
  if (en_us) return en_us
  return _voiceCache.find(v => v.lang.startsWith('en'))
}

// ── Public API ───────────────────────────────────────────────────────────

export interface ListenOptions {
  /** BCP-47 language tag for the recognizer. Defaults to 'en-US'. */
  lang?: string
  /** If true, recognizer keeps running until stop() is called (continuous
   *  dictation). If false (default), stops after the first natural pause. */
  continuous?: boolean
  /** Callback fired every time the recognizer emits a partial (non-final)
   *  result. Use to show a live transcript bubble. */
  onInterim?: (interim: string) => void
}

export interface SpeakOptions {
  rate?: number    // 0.1-10, default 1.0
  pitch?: number   // 0-2, default 1.0
  volume?: number  // 0-1, default 1.0
  /** Optional override; falls back to pickCoachingVoice(). */
  voice?: SpeechSynthesisVoice
}

export interface ListenHandle {
  /** Resolves with the final transcript when recognition ends naturally.
   *  Rejects with Error on permission denial, no-speech-detected, etc. */
  finished: Promise<string>
  /** Cancel recognition immediately. The promise resolves with whatever
   *  was captured so far (possibly empty). */
  stop(): void
}

export const voice = {
  /**
   * Whether the runtime exposes a SpeechSynthesis implementation. UI should
   * hide TTS controls if false.
   */
  get canSpeak(): boolean {
    return typeof window !== 'undefined' && !!window.speechSynthesis
  },

  /**
   * Whether the runtime exposes a SpeechRecognition implementation. UI
   * should hide mic controls if false (e.g. Firefox desktop).
   */
  get canListen(): boolean {
    return !!_getRecognitionCtor()
  },

  /** Are the cached voices ready? Mostly for diagnostic display. */
  get voicesReady(): boolean {
    return _voiceCacheReady
  },

  /**
   * Speak `text`. Returns a Promise that resolves when the utterance ends
   * (or rejects on error). Any in-flight speech is cancelled first so the
   * coach never "stacks" two replies.
   */
  speak(text: string, opts: SpeakOptions = {}): Promise<void> {
    if (!this.canSpeak || !text) return Promise.resolve()
    const synth = window.speechSynthesis
    synth.cancel()
    return new Promise((resolve, reject) => {
      const u = new SpeechSynthesisUtterance(text)
      u.rate   = opts.rate   ?? 1.0
      u.pitch  = opts.pitch  ?? 1.0
      u.volume = opts.volume ?? 1.0
      u.voice  = opts.voice  ?? pickCoachingVoice() ?? null
      u.onend   = () => resolve()
      u.onerror = (e: SpeechSynthesisErrorEvent) => {
        // 'canceled' / 'interrupted' fire when we manually cancel — not a
        // failure for our purposes, the caller usually wanted that.
        if (e.error === 'canceled' || e.error === 'interrupted') resolve()
        else reject(new Error(`speech-synthesis error: ${e.error}`))
      }
      synth.speak(u)
    })
  },

  /** Cancel any in-flight TTS. */
  stop(): void {
    if (this.canSpeak) window.speechSynthesis.cancel()
  },

  /** True while the synthesizer is currently speaking. */
  get isSpeaking(): boolean {
    return this.canSpeak && window.speechSynthesis.speaking
  },

  /**
   * Start the speech recognizer. Returns a handle whose `.finished` promise
   * resolves with the captured transcript when recognition ends naturally,
   * or when the caller invokes `.stop()`.
   *
   * Errors that propagate (rejection):
   *   - 'no-speech-recognition' if the API is unavailable
   *   - 'not-allowed' if the user denies mic permission
   *   - 'audio-capture' if no input device is available
   *
   * The mic permission prompt fires on the first call per origin.
   */
  listen(opts: ListenOptions = {}): ListenHandle {
    const Ctor = _getRecognitionCtor()
    if (!Ctor) {
      return {
        stop() {},
        finished: Promise.reject(new Error('no-speech-recognition')),
      }
    }
    const rec = new Ctor()
    rec.lang = opts.lang ?? 'en-US'
    rec.continuous = !!opts.continuous
    rec.interimResults = !!opts.onInterim
    rec.maxAlternatives = 1

    let finalText = ''
    let stopped = false

    const finished = new Promise<string>((resolve, reject) => {
      rec.onresult = (e: any) => {
        let interim = ''
        for (let i = e.resultIndex; i < e.results.length; i++) {
          const r = e.results[i]
          if (r.isFinal) finalText += r[0].transcript
          else interim += r[0].transcript
        }
        if (interim && opts.onInterim) opts.onInterim(interim)
      }
      rec.onerror = (e: any) => {
        // 'aborted' fires when we manually stop — not an error.
        if (e.error === 'aborted') resolve(finalText.trim())
        else reject(new Error(`speech-recognition error: ${e.error}`))
      }
      rec.onend = () => {
        if (!stopped) resolve(finalText.trim())
      }
      try {
        rec.start()
      } catch (err) {
        reject(err instanceof Error ? err : new Error(String(err)))
      }
    })

    return {
      finished,
      stop() {
        stopped = true
        try { rec.stop() } catch { /* ignore */ }
      },
    }
  },
}

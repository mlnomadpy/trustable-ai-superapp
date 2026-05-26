# 06 — Audio design

Every sound the player will hear, why it's there, where it lives, how
it's produced. Audio is half the "feels like an old game" pitch — get
this wrong and the pixel art doesn't carry it alone.

## Four audio layers

| Layer | Volume | Mix priority | Source |
|---|---|---|---|
| **Music** | 15% master, ducks to 5% during dialogue | low | Chiptune loops, generative or pre-baked |
| **SFX** | 30% master | medium | jsfxr-generated, ~20 distinct samples |
| **Tactical tones** | 60% master, **ducks to 12%** while TTS plays | medium-high | Web Audio oscillator, pitch ↔ delta from sonic_model |
| **Voice (TTS)** | 100% master | high | Pre-rendered MP3 per coach phrase + Web Speech fallback |

All four pipe through [Howler.js](https://howlerjs.com/) with one
shared mixer (the tactical-tone oscillator wired into the Howler graph
via a `MediaElementAudioSourceNode`). Mute toggles per layer in
`screens/13-settings.md`.

### Why a separate tactical-tone layer

The sonic-model emits a continuous pitch where the pitch IS the
delta — speed delta, brake-pressure delta, longitudinal-G delta — so
the driver hears how far they are from the gold-lap reference without
listening to words. This is the reflexive sub-50 ms feedback layer
(per [ADR-017](../adr/017-three-tier-coach-architecture.md)).

It cannot share the SFX bus: SFX are < 1 s one-shots, tactical tones
are continuous and never stop. It cannot share the voice bus either,
because voice (TTS) is *the thing we duck around*. It needs its own
gain node so we can ramp it down by ~14 dB whenever a coach phrase is
speaking and back up when the phrase ends — without affecting any
other layer.

## SFX library

20 distinct samples. Each is a one-shot, < 1 s, generated via
[jsfxr](https://sfxr.me/) with the seeds + parameter files committed
in `pitwall-web/public/sfx/`. Reproducible from seeds — the JSON in
`pitwall-web/scripts/sfx-bake.ts` regenerates the .mp3s.

| ID | Use | Length | Character |
|---|---|---|---|
| `boot_chime` | Title screen entry | 1.2 s | Three-note rising arpeggio (C-E-G) |
| `cursor_move` | Menu D-pad nav | 30 ms | Tiny click |
| `cursor_select` | A button confirm | 200 ms | Two-note ding |
| `cancel` | B button cancel | 150 ms | Soft thud |
| `dialogue_blip` | Per char during teletype | 20 ms | Very soft tick (max once per 30 ms) |
| `transition_wipe` | Screen change | 150 ms | Whoosh |
| `lap_complete` | Lap finish | 800 ms | 4-note fanfare |
| `pb_unlock` | New personal best | 1.5 s | 6-note ascending fanfare with chord |
| `medal_award` | New medal awarded | 600 ms | Slot-machine "ding-ding-ding" |
| `coach_thinking` | Pre-brief generating | loop, 800 ms | 4-tone loop |
| `over_grip` | HUD: friction circle exceeded | 250 ms | Buzzer (matches `01-visual-language.md` ui-bad) |
| `coast_warning` | HUD: coasting too long on a straight | 400 ms | Slow descending tone |
| `corner_apex` | HUD: hit apex marker | 100 ms | Quick chirp |
| `score_tick` | Per metric reveal on score screen | 50 ms | Click |
| `score_total` | Total score reveal | 1.0 s | Big positive chord |
| `error_quiet` | Bridge offline / network drop | 600 ms | 2-note descending soft sad tone |
| `goal_complete` | Session goal achieved | 500 ms | Heroic 3-note motif |
| `goal_miss` | Session goal missed | 350 ms | 2-note flat tone |
| `level_up` | Driver level increase | 1.8 s | Big rising chime + fanfare |
| `night_chime` | End-of-day fade-to-night | 2.0 s | Soft 5-note descending lullaby |

## Music

8-bar chiptune loops. Each scene has an associated track. Looping is
gapless via Howler's `sprite` mode.

| Track | Use | Tempo | Key |
|---|---|---|---|
| `title_loop` | Title screen idle | 92 BPM | C major |
| `garage_loop` | Garage hub | 80 BPM | A minor |
| `worldmap_loop` | World map | 85 BPM | G major |
| `prebrief_loop` | Pre-brief (low-key, atmospheric) | 70 BPM | D minor |
| `drive_loop` | On-track HUD (energetic) | 130 BPM | E minor |
| `cooldown_loop` | Cool-down lap | 95 BPM | A major |
| `score_fanfare` | Stage clear (one-shot, 12 s) | 100 BPM | F major |
| `eod_loop` | End of day (slow, melancholic) | 60 BPM | C minor |

Generation paths (pick one):

1. **Hand-composed** with [Bosca Ceoil](https://terrycavanagh.itch.io/bosca-ceoil)
   or [Famistudio](https://famistudio.org) — most authentic; slow.
2. **Suno / Udio** prompted with "8-bit chiptune racing arcade,
   GBA-era, 92 BPM, C major, looping 16-bar arrangement, NES square
   waves + triangle bass" — fast; license clearance required for
   commercial use.
3. **CC0 sample packs** like Eric Skiff's *Resistor Anthems* or Kevin
   MacLeod's chiptune set — fastest; less specific to the brand.

For May 23 demo, **option 3** is the realistic call. Post-Sonoma,
revisit.

## Voice (TTS)

Per [`03-character-bible.md`](03-character-bible.md), each coach has
~50 canonical phrases pre-rendered to MP3 + a Web Speech API fallback
for any phrase the LLM generates ad-hoc.

### Pre-rendered set

```
pitwall-web/public/audio/coaches/
├── trod/
│   ├── greet_morning.mp3            (~2 s)
│   ├── greet_afternoon.mp3
│   ├── greet_evening.mp3
│   ├── greet_long_absence.mp3
│   ├── concept_trail_brake.mp3
│   ├── concept_late_apex.mp3
│   ├── … 50 total per coach …
│   └── farewell_eod.mp3
├── bentley/  (50 files)
├── drill/    (50 files)
├── calm/     (50 files)
└── buddy/    (50 files)
```

= 250 clips × ~120 KB each ≈ **30 MB** total. Service worker caches the
*active* coach's clips on coach-select; downloads the rest in the
background.

### Web Speech fallback

When the LLM (LitertCoach) generates a fresh phrase that isn't
pre-rendered, the PWA uses Web Speech API:

```ts
function speak(text: string, voiceConfig: { rate: number, pitch: number }) {
  const u = new SpeechSynthesisUtterance(text)
  u.rate = voiceConfig.rate
  u.pitch = voiceConfig.pitch
  u.voice = pickVoice(coachId)         // best-match Web Speech voice
  speechSynthesis.speak(u)
}
```

Quality is variable by browser/OS. On the Pixel + Chrome, the default
en-US voice is acceptable. On macOS Chrome, less so. **Pre-rendered is
preferred** for any phrase that fires more than once.

### Voice generation pipeline

A bake script (run once or whenever phrases change):

```bash
node scripts/voice-bake.ts \
  --coach trod \
  --phrases data/voices/trod-phrases.json \
  --tts gemini-2.5-flash-tts \
  --voice "experienced-instructor-male-american-50s" \
  --out pitwall-web/public/audio/coaches/trod/
```

Phrases JSON shape:

```jsonc
// pitwall-web/data/voices/trod-phrases.json
[
  { "id": "greet_morning",     "text": "Welcome back, kid. Today we drive." },
  { "id": "concept_trail_brake", "text": "Roll the brake to the apex." },
  { "id": "corner_t11",        "text": "Wait for the bump, trail to the third tire stack." },
  { "id": "encourage_clean",   "text": "Now THAT was distance." },
  { "id": "disappoint_overdrive", "text": "Slow down. Same line." },
  /* ... 50 entries ... */
]
```

Output filenames are deterministic from `id` so service-worker cache
keys are stable across rebuilds.

## Audio system architecture

```ts
// pitwall-web/src/lib/audio.ts
import { Howl } from 'howler'
import { ref } from 'vue'

// One reactive flag is the source of truth for ducking. The tactical-tone
// oscillator and any future ducked layer watch it and ramp their gain.
// Setting it true while it is already true extends the duck window
// (multiple back-to-back voice cues won't drop the duck mid-phrase).
export const ttsDucked = ref(false)
let _duckUntil = 0          // monotonic ms — when the active duck window ends

export const audio = {
  music:    new Map<string, Howl>(),
  sfx:      new Map<string, Howl>(),
  voice:    new Map<string, Howl>(),
  tactical: null as null | TacticalToneOscillator,    // see sonic-model bus

  playMusic(track: string) {
    /* fade out current track over 500 ms, fade in new */
  },
  playSfx(id: SfxId) { /* one-shot */ },
  playVoice(coachId: CoachId, phraseId: string, hintMs = 0) {
    const key = `${coachId}/${phraseId}`
    let h = this.voice.get(key)
    if (!h) {
      h = new Howl({ src: [`/audio/coaches/${key}.mp3`] })
      this.voice.set(key, h)
    }
    // Two ducks for the price of one: music drops to 5%, tactical to 12%.
    audio.duckMusic(true)
    audio.duckTactical(true, hintMs || (h.duration() * 1000) || 1500)
    h.once('end', () => {
      audio.duckMusic(false)
      // Tactical un-ducks via timer — see duckTactical — so a
      // long phrase that finishes early doesn't yank tones up
      // before the user has parsed the cue.
    })
    h.play()
  },
  speakAdHoc(text: string, voiceConfig: VoiceConfig, hintMs = 0) {
    // Web Speech path — used when the LLM emits a phrase outside the
    // pre-rendered set. Ducker hint comes from the bridge's
    // `expected_tts_ms` on the /cues/stream payload (~150 ms/word, floor 800).
    const u = new SpeechSynthesisUtterance(text)
    u.rate = voiceConfig.rate
    u.pitch = voiceConfig.pitch
    u.voice = pickVoice(voiceConfig.coachId)
    audio.duckMusic(true)
    audio.duckTactical(true, hintMs || estimateMs(text))
    u.onend = () => audio.duckMusic(false)
    speechSynthesis.speak(u)
  },
  duckMusic(ducked: boolean) { /* fade music to 5% / 100% */ },
  duckTactical(ducked: boolean, holdMs = 0) {
    // Engages the duck IMMEDIATELY (8 ms ramp — fast enough that the
    // driver doesn't hear the hand-off, slow enough that we don't
    // get a click). Releases on a timer so back-to-back cues stack
    // their hold windows instead of fighting each other.
    if (ducked) {
      _duckUntil = Math.max(_duckUntil, performance.now() + holdMs)
      ttsDucked.value = true
      audio.tactical?.gain.gainNode.gain.linearRampToValueAtTime(
        0.12, audio.tactical.ctx.currentTime + 0.008,
      )
      setTimeout(audio._maybeUnduck, holdMs + 16)
    }
  },
  _maybeUnduck() {
    if (performance.now() >= _duckUntil - 8) {
      ttsDucked.value = false
      audio.tactical?.gain.gainNode.gain.linearRampToValueAtTime(
        0.60, audio.tactical.ctx.currentTime + 0.080,
      )
    }
  },
}
```

The PWA's `/cues/stream` subscriber feeds `expected_tts_ms` from each
event into `playVoice`/`speakAdHoc` so the duck window matches the
phrase length exactly — no guessing, no hand-tuning.

## Audio rules

These match the visual rules in `01-visual-language.md`:

1. **Every confirm has a chime.** No silent A-button presses.
2. **Every cancel has a thud.** No silent B-button presses.
3. **Music ducks during dialogue.** 100% → 5% over 200 ms; restore
   when teletype finishes.
4. **Tactical tones duck during TTS.** 60% → 12% over 8 ms (fast hand-off,
   no click) when a coach phrase starts; restore over 80 ms (slow ramp so
   the driver stays oriented after the cue lands). Window length comes from
   the bridge's `expected_tts_ms` cue field — back-to-back cues *extend*
   the duck instead of fighting each other. **This is the cognitive-overload
   fix from ADR-018.** Without it, the driver hears continuous brake-delta
   pitch UNDER a verbal pace note at full volume — provably bad at 130 mph.
5. **TTS never overlaps TTS.** A new voice cue interrupts the previous
   one (`Howl.stop()` then play). The arbiter at the bridge already cools
   down to one cue per 3 s (ADR-002), so this is a backstop.
6. **No SFX during the on-track HUD's high-attention windows** —
   between corner-entry and corner-exit, only safety SFX (`over_grip`,
   `coast_warning`) play. Cursor / dialogue SFX are suppressed.
7. **`prefers-reduced-motion: reduce`** also reduces audio: music
   volume drops to 0, SFX to 50%. Coach voice unchanged (it's the
   point of the coach). Tactical-tone gain drops to 30% (still
   present — it's a safety layer).
8. **No SFX delay > 30 ms.** Pre-loaded Howls; never lazy-load on
   button press.

## Mute / volume UX

In `screens/13-settings.md`, three sliders:

```
MASTER     ████████████████░░░░    80%
MUSIC      ██████████░░░░░░░░░░    50%
SFX        ████████████████████    100%
COACH VOICE ████████████████████   100%
```

Plus quick toggles:
- 🔕 mute all (visible in status bar)
- 🎙️ mute coach voice (some drivers prefer the silence-is-coaching
  baseline)

Settings persist in the active save slot (per `04-state-architecture.md`),
so a household sharing a phone keeps per-driver preferences.

## Related

- [`01-visual-language.md`](01-visual-language.md) — the audio ↔ visual
  pairs table
- [`03-character-bible.md`](03-character-bible.md) — voice character
  for each coach
- [`screens/08-on-track-hud.md`](screens/08-on-track-hud.md) — HUD
  audio rules
- [ADR-017 — Three-tier coach architecture](../adr/017-three-tier-coach-architecture.md)
  — pre-rendered phrases are exactly the in-drive coach path

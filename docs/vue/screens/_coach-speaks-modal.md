# _ — Coach Speaks Modal (pattern)

The reusable overlay every LLM-driven moment uses. **Not a screen** in
the routing sense — it overlays whatever screen is active. Underscore
prefix in the filename keeps it sorted to the top of `screens/` and
signals "pattern, not destination."

Used by:
- [`07-pre-brief.md`](07-pre-brief.md) — pre-session briefing
- [`10-stage-clear.md`](10-stage-clear.md) — post-session debrief
- [`15-pit-stall-setup.md`](15-pit-stall-setup.md) — connection-issue commentary
- [`05-coach-select.md`](05-coach-select.md) — new coach intro line
- [`24-achievement-toast.md`](24-achievement-toast.md) — coach reaction to a medal
- [`28-coach-codex.md`](28-coach-codex.md) — phrase context dialogue

## Purpose

Verb: **Listen.** When the LLM produces text or a canonical phrase
fires, the player sees + hears the coach deliver it. Same component,
same animation grammar, every time.

## Wireframe (overlay)

Sits over the current screen at z-index 50, dimming the rest 70 %.
Always anchored to the bottom 1/3 of the viewport (so it doesn't
obscure the screen's primary tile grid).

```
┌────────────────────────────────────────────────────────────┐
│              (parent screen visible at 30% opacity)        │
│                                                            │
│                                                            │
│                                                            │
│                                                            │
│                                                            │
├────────────────────────────────────────────────────────────┤
│  ┌──────┐  ┌──────────────────────────────────────────┐    │
│  │      │  │ Settle in. We're at Sonoma, peak grip   │    │
│  │      │  │ today, so we're going to be tight.      │    │
│  │ T-ROD│  │ Remember, distance is king, especially  │    │
│  │  +   │  │ on these sweeps.█                        │    │
│  │  3   │  │                                          │    │
│  │frames│  │                                ▼ tap to  │    │
│  └──────┘  │                                  advance │    │
│            └──────────────────────────────────────────┘    │
└────────────────────────────────────────────────────────────┘
```

The portrait sprite is 96 × 96 logical pixels. Text frame is 9-slice
`frame-dialogue` with the bottom-left pointer triangle pointing at
the portrait.

## States

The modal has four states orchestrating LLM latency + emotion:

| State | Trigger | Behaviour |
|---|---|---|
| `summoning` | `coachSpeak({...})` called | Modal slides up from bottom (200 ms outBack); music ducks to 5%; portrait shows `thinking` emotion (clipboard_writing or holding_gauge) |
| `awaiting` | LLM call dispatched, no response yet | Portrait stays in `thinking`; no text; no SFX; subtle "Z Z Z" particles or pulsing dots |
| `talking` | LLM response received OR canonical phrase ready | Portrait switches to `<emotion>` frame from response; text begins teletyping at 30 char/sec; `dialogue_blip` SFX per char (max one per 30 ms); voice TTS clip plays in parallel if pre-rendered |
| `idle` | Teletype done | Portrait holds `<emotion>` frame in 2-frame breathing loop; ▼ "tap to advance" hint pulses |
| `dismissing` | A or tap | Modal slides down (150 ms inOutCubic); music un-ducks |

## Sprite usage

| Sprite | Where | Animation |
|---|---|---|
| Coach portrait (per `coachId`) | Bottom-left, 96×96 | Per state — see table above |
| `frame-dialogue` 9-slice | Wraps text area | Static |
| `frame-card` 9-slice | Wraps portrait | Static |
| `dialog_pointer_triangle` | Between portrait and text | Static (part of frame-dialogue's nine-slice) |
| `cursor_advance` (▼) | Bottom-right of text | 2-frame pulse at 1 Hz, only in `idle` state |
| `thinking_z_particles` 3-frame | Above portrait, only in `awaiting` | Floats up, fades; 1 Hz |

The portrait's internal sprite frame depends on **emotion** from
[`10-coach-emotions.md`](../10-coach-emotions.md):

```ts
const emotion = props.emotion ?? 'neutral'   // neutral | thinking | analyzing | encouraging | …

// In template:
<Sprite
  :sheet="props.coachId"
  :animation="props.state === 'awaiting' ? 'thinking' : emotion"
  :variant="props.state === 'talking' ? 'talk' : 'idle'"
/>
```

When `state === 'talking'` the sprite swaps to the `talk` variant of
the chosen emotion (mouth open/closed at 6 Hz). When `state === 'idle'`
it stays in the chosen emotion's breathing loop.

## Vue component

```vue
<!-- pitwall-web/src/components/CoachSpeaksModal.vue -->
<template>
  <Teleport to="body">
    <Transition :name="modalTransition">
      <div v-if="visible" class="modal-overlay">
        <Frame frame-type="card" class="portrait-frame">
          <Sprite
            :sheet="coachId"
            :animation="spriteAnim"
            :variant="spriteVariant"
          />
          <Particles v-if="state === 'awaiting'" name="thinking_z" />
        </Frame>

        <Frame frame-type="dialogue" class="text-frame">
          <p
            class="font-ui text-body"
            :data-text="fullText"
          >
            {{ visibleText }}<span class="caret" v-if="caretVisible">█</span>
          </p>
          <Sprite
            v-if="state === 'idle'"
            sheet="ui"
            animation="cursor_advance"
            class="advance-hint"
          />
        </Frame>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, ref, watch, onMounted } from 'vue'
import { useTeletype } from '@/lib/teletype'
import { audio } from '@/lib/audio'
import { CoachId, Emotion } from '@/types/coach'

const props = defineProps<{
  coachId:   CoachId
  text:      string                // final text to teletype
  emotion?:  Emotion               // from Gemma response or phrase tag
  voiceId?:  string                // pre-rendered MP3 phrase id
  state:     'summoning' | 'awaiting' | 'talking' | 'idle' | 'dismissing'
  visible:   boolean
}>()
const emit = defineEmits<{ advance: []; dismissed: [] }>()

const visibleText = ref('')
const caretVisible = ref(true)
const modalTransition = 'slide-up-pixel'

const spriteAnim = computed(() =>
  props.state === 'awaiting' ? 'thinking' : (props.emotion ?? 'neutral')
)
const spriteVariant = computed(() =>
  props.state === 'talking' ? 'talk' : 'idle'
)

watch(() => [props.state, props.text], ([state, text]) => {
  if (state === 'talking' && text) {
    audio.duckMusic(true)
    if (props.voiceId) audio.playVoice(props.coachId, props.voiceId)
    useTeletype(text as string, {
      onChar: (txt) => {
        visibleText.value = txt
        // throttled per `06-audio-design.md` rules
        audio.playSfx('dialogue_blip')
      },
      onDone: () => {
        emit('advance')      // parent transitions to 'idle'
      },
    })
  }
  if (state === 'idle') {
    audio.duckMusic(false)
  }
  if (state === 'dismissing') {
    setTimeout(() => emit('dismissed'), 150)
  }
})
</script>
```

## Composable usage

```ts
// pitwall-web/src/lib/useCoachSpeaks.ts
import { useDialogueStore } from '@/stores/dialogue'

export function useCoachSpeaks() {
  const dialogue = useDialogueStore()

  return {
    /** Show "thinking" portrait, fire async work, transition to talking
     *  on resolve. */
    async speak<T>(opts: {
      coachId:  string
      thinking?: () => Promise<{ text: string; emotion: string; voiceId?: string } | T>
      text?:    string
      emotion?: string
      voiceId?: string
    }) {
      // 1. Show modal in `summoning` → `awaiting`
      dialogue.show({ coachId: opts.coachId, state: 'awaiting' })
      // 2. Resolve text + emotion
      let payload
      if (opts.thinking) {
        payload = await opts.thinking()
      } else {
        payload = { text: opts.text!, emotion: opts.emotion, voiceId: opts.voiceId }
      }
      // 3. Switch to talking, set text + emotion
      dialogue.setText(payload.text, payload.emotion, payload.voiceId)
      // 4. Wait for user to advance (or auto-advance after teletype)
      await dialogue.waitForAdvance()
      // 5. Dismiss
      dialogue.dismiss()
    }
  }
}

// Used in pre-brief:
const { speak } = useCoachSpeaks()
await speak({
  coachId: save.preferredCoach,
  thinking: async () => {
    const r = await fetch('/api/coach/brief?driver=...').then(r => r.json())
    return { text: r.narrative_md, emotion: r.emotion }
  }
})
```

## Endpoints consumed

The modal itself doesn't consume endpoints; its caller does. Typical
patterns:

| Caller | Endpoint | Emotion source |
|---|---|---|
| Pre-brief | `POST /coach/brief` | response.emotion |
| Stage clear | `POST /coach/debrief` | response.emotion |
| Live cue (badge, not modal) | SSE `/cues/stream` | cue.emotion |
| Phrase preview (codex) | None — local | static phrase library tag |
| Coach intro on swap | None — pre-rendered MP3 | filename → static tag |

## Audio cues

| Event | Sound |
|---|---|
| Modal slides up | `transition_wipe` (short) |
| Each character teletyped | `dialogue_blip` (rate-limited to 1 per 30 ms) |
| Voice TTS clip starts | pre-rendered MP3 from `/audio/coaches/<id>/<voiceId>.mp3` |
| Modal dismissed | `cancel` |

## Input map

While modal is open (any state):

| Input | Action |
|---|---|
| A / Tap on text frame | If `talking`: fast-forward teletype to end. If `idle`: dismiss. |
| B / Esc | If `awaiting`: cancel the LLM call (only allowed for non-blocking calls). If `talking` or `idle`: dismiss. |
| All other inputs | No-op (modal is modal) |

## Edge cases

- **LLM call exceeds 15 s** — stay in `awaiting` indefinitely; show
  a "..." pulsing indicator. User can press B to cancel.
- **LLM returns empty text** — modal flashes once and auto-dismisses
  to avoid the player staring at an empty box.
- **Coach voice MP3 isn't cached AND offline** — fall back to Web
  Speech API per `06-audio-design.md`. Teletype still drives the
  visual; voice is auxiliary.
- **Modal already open when `speak()` is called again** — queue the
  new payload; play after current dismisses. No stacking.
- **Player navigates away during modal** — state preserved in
  `useDialogueStore`; on return, modal is still open. (Important for
  the on-track HUD entering paddock mid-dialogue.)

## Performance budget

- Modal mount → first frame visible: < 50 ms
- LLM `awaiting` state: 0–15 s tolerated (4 s typical for Gemma 4 E2B
  on-device)
- Teletype throughput: 30 chars/sec; max latency from text-ready to
  first-char-visible: 100 ms
- Total memory footprint of modal: < 300 KB (sprite frames + text)

## Related

- [`10-coach-emotions.md`](../10-coach-emotions.md) — emotion taxonomy
  consumed via `props.emotion`
- [`06-audio-design.md`](../06-audio-design.md) — `dialogue_blip` rate
  rules + voice MP3 playback
- [`08-animation-spec.md`](../08-animation-spec.md) — slide-up timing
  + teletype throughput
- [`07-pre-brief.md`](07-pre-brief.md) — primary consumer
- [`10-stage-clear.md`](10-stage-clear.md) — primary consumer

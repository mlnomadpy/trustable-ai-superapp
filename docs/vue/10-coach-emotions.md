# 10 — Coach emotions (Gemma-controlled)

The coach isn't always neutral. When Gemma generates coaching text,
it also emits an **emotion tag** that drives which sprite animation
the avatar plays. Same coach, different face — and the "different
face" is *whatever the LLM decided was appropriate for what it just
said*.

This doc defines the 12-emotion taxonomy, the Gemma prompt contract,
the response shape, and per-screen mapping.

## The 12 emotions

Each emotion maps to a specific T-Rod sprite frame (or short loop)
from the user's reference sheet. Other coaches mirror the same
emotion set with their own sprites — same `id`, same meaning,
different art per character.

| ID | Mood | Used when | T-Rod frame source (row × col on reference sheet) |
|---|---|---|---|
| `neutral` | Default | Idle, waiting, generic dialogue | `idle_0/1` (row 1, cols 1-2) |
| `thinking` | Coach is processing | LLM is generating; coach is "looking at the data" | `clipboard_writing` (row 7, col 12) |
| `analyzing` | Coach is examining specifics | Mid-debrief commentary on a specific lap or corner | `tablet_review` / `clipboard_review` (row 8, cols 12-13) |
| `encouraging` | Positive but measured | "Solid lap." "Good improvement." | `thumbs_up` (row 8, col 1) |
| `proud` | Genuinely proud | New PB, all goals hit, multiple medals earned | `medal_proud` (row 11, cols 6-9) |
| `excited` | Hyped, celebrating | Major milestone — first sub-1:48, level up, 100th session | `victory_arms_up` (row 11, cols 1-3) |
| `serious` | Direct, no fluff | Safety reminder, danger zone warning | `arms_crossed` (row 5, col 5) |
| `concerned` | Worried about driver | Coasting too much, missing apex repeatedly | `kneel_serious` (row 9, col 12) |
| `disappointed` | Patient but sad | Goal missed, lap got slower, bad technique | `kneel_satisfied` → frown variant (row 11, col 13) |
| `intense` | High focus | Pre-stage briefing on a hard corner; mid-arbiter P3 | `fight_stance` (row 10, cols 4-7) or `point_emphatic` |
| `relaxed` | Wind-down | Cool-down lap, end-of-day, post-celebration | `coffee_mug` (row 13, col 1) |
| `tired` | Long day | End-of-day farewell after 5+ sessions | `bed_lie` / `sleep_z` (row 13, cols 2-4) |

Three additional rules:

1. **Defaults are forgiving.** If Gemma emits an unknown emotion (e.g.
   `confused`, `worried`, etc.), the PWA falls back to `neutral`.
2. **In-drive uses canonical phrases**, not Gemma. Per
   [ADR-017](../adr/017-three-tier-coach-architecture.md), the in-drive
   path is canned phrases. Each canned phrase is *also* tagged with an
   emotion at design time, so the in-drive HUD's small coach badge
   plays an animation too.
3. **`thinking` is reserved for the loading state.** It plays *while*
   the LLM is generating; once the response arrives the emotion
   switches to whatever Gemma chose.

## Gemma prompt contract

Every system prompt that uses the LLM coach (in
`src/pitwall/features/coaching/prompts.py`, re-exported via the
`coach_engine` shim) must instruct the model to emit an emotion tag. Format:

```
At the START of your reply, emit one tag in the form
[EMOTION: <name>]
where <name> is exactly one of:
  neutral, thinking, analyzing, encouraging, proud, excited,
  serious, concerned, disappointed, intense, relaxed, tired
Then a single newline, then your normal coaching response.
Do not emit the tag anywhere else in the reply.
```

Example output Gemma should produce:

```
[EMOTION: encouraging]
Now THAT was distance. Same line again.
```

```
[EMOTION: disappointed]
T7 again. You're braking 15 m early. Ride it deeper.
```

```
[EMOTION: proud]
First sub-1:48. Stack up another one — break the next plateau.
```

The system prompt update lives in
`src/pitwall/features/coaching/prompts.py:build_system_prompt`. The change is
small (~5 lines added per mode) and additive — older clients that
don't know about `[EMOTION: ...]` keep working because the tag is
just text they can ignore.

## Bridge response shape

Brief and debrief responses gain an `emotion` field:

```jsonc
// POST /coach/brief response
{
  "narrative_md": "Settle in. Peak grip today …",
  "focus":        ["the bump", "the K-wall bend", "T7 entry"],
  "emotion":      "intense",        // NEW
  "coach_id":     "trod"
}

// POST /coach/debrief response
{
  "narrative_md": "Good session. Best 1:46.8 …",
  "focus_next":   ["T11 exit", "T7 brake reference"],
  "emotion":      "encouraging",     // NEW
  "score":        86,
  "coach_id":     "trod"
}
```

Live SSE cues from `/cues/stream` already carry an emotion since
in-drive phrases are canonical, not LLM-generated:

```jsonc
// GET /cues/stream — SSE event
{
  "ts":         1714316103.42,
  "phrase_id":  "concept_trail_brake",
  "text":       "Roll the brake to the apex.",
  "priority":   2,
  "emotion":    "intense"
}
```

The PWA reads `cue.emotion` and plays the matching coach animation
on the on-track HUD's mini-coach-badge.

## Coach-engine implementation

In `src/pitwall/features/coaching/engine_base.py` (the dataclass + emotion
extractor) and `src/pitwall/features/coaching/litert_coach.py` (the
brief/debrief callers). Both are re-exported from the legacy
`src/pitwall/features/coaching/coach_engine.py` shim — `extract_emotion`
is now public (was `_extract_emotion`).

```python
@dataclass
class CoachingMessage:
    text:     str
    priority: int
    layer:    str = "coach"
    reason:   str = ""
    emotion:  str = "neutral"   # NEW field; defaults to neutral

def _split_brief_narrative_and_focus(text: str) -> tuple[str, list[str], str]:
    """Now returns (narrative, focus, emotion)."""
    emotion = "neutral"
    m = re.match(r"\s*\[EMOTION:\s*(\w+)\s*\]\s*\n?", text)
    if m:
        emotion = m.group(1).lower()
        text = text[m.end():]
    if emotion not in VALID_EMOTIONS:
        emotion = "neutral"
    # ... existing focus-extraction logic ...
    return narrative, focus, emotion

VALID_EMOTIONS = {
    "neutral", "thinking", "analyzing", "encouraging", "proud",
    "excited", "serious", "concerned", "disappointed", "intense",
    "relaxed", "tired",
}
```

Tests added in `tests/test_coach_engine_litert.py`:

- `test_brief_includes_emotion_tag` — brief() returns a third tuple
  element that's a valid emotion
- `test_debrief_includes_emotion_tag` — same for debrief
- `test_emotion_extractor_handles_garbage` — unknown emotion → neutral

## Per-screen mapping

Where each emotion shows up in the PWA:

### Pre-Brief screen (`07-pre-brief.md`)
- `loading` state → `thinking` animation while `/coach/brief` is in flight
- After brief loads → emotion from response (likely `intense` or
  `serious`, since briefings set tone)

### On-Track HUD (`08-on-track-hud.md`)
- Small 32×32 coach badge top-right cycles emotion based on the
  latest cue's `emotion` field
- Badge animation maps emotion → frame just like the full-size
  portrait, scaled down

### Cool-Down (`09-cool-down.md`)
- Coach reaction sprite picked from per-corner `corner_score` cues —
  emotion field drives which face shows when each corner reveals

### Stage Clear (`10-stage-clear.md`)
- Emotion comes from `/coach/debrief` response, displayed when coach
  delivers final verdict at t=4700ms in the orchestrated sequence

### Coach Speaks Modal (`screens/_coach-speaks-modal.md`)
- The reusable component every LLM-talks moment uses; reads emotion
  from props

### Pit Stall Setup (`15-pit-stall-setup.md`)
- Coach idles `holding_gauge` (`analyzing`) by default
- If any connection ✗ → switches to `concerned`
- All ✓ → `encouraging` for ~3 s then back to `analyzing`

### Garage Hub (`03-garage-hub.md`)
- Coach NPC walks around; emotion is whatever the daily greeting's
  pre-rendered TTS clip is tagged with (we tag the canonical phrase
  library at design time)

### Trainer Card (`04-trainer-card.md`)
- Coach in corner plays `proud` if driver level just increased,
  else `relaxed`

### End of Day (`14-end-of-day.md`)
- Always `tired`, transitioning to `relaxed` (coffee), then sprite
  hides as the screen fades to night

## Pre-tagged canonical phrase library

Every entry in
`src/pitwall/features/track/sonoma.py:TROD_VOICE` and the per-coach pre-rendered
TTS phrase library (`pitwall-web/data/voices/<coach>-phrases.json`)
carries an emotion tag:

```jsonc
[
  { "id": "greet_morning",
    "text": "Welcome back, kid. Today we drive.",
    "emotion": "neutral" },
  { "id": "concept_trail_brake",
    "text": "Roll the brake to the apex.",
    "emotion": "intense" },
  { "id": "encourage_clean",
    "text": "Now THAT was distance.",
    "emotion": "encouraging" },
  { "id": "celebrate_pb",
    "text": "First sub-1:48. Stack another.",
    "emotion": "proud" },
  { "id": "disappoint_overdrive",
    "text": "Slow down. Same line.",
    "emotion": "disappointed" },
  /* ... 50 entries per coach ... */
]
```

The bridge's in-drive arbiter emits these tags into the SSE stream
without any LLM call — `phrase_id` → `emotion` is a static lookup.

## Sprite spec changes

The 14-frame minimum animation set per coach (defined in
`02-sprite-sheet-spec.md`) extends to **24 frames** to cover all 12
emotions (each emotion gets a 2-frame breathing loop):

| Animation | Frames | Source pattern |
|---|---|---|
| `idle` (= neutral) | 2 | breathing |
| `thinking` | 2 | head tilted, hand on chin or clipboard |
| `analyzing` | 2 | looking at tablet / instrument |
| `encouraging` | 2 | smile + thumbs-up |
| `proud` | 2 | chest puffed, arms wide |
| `excited` | 2 | arms raised + open mouth |
| `serious` | 2 | arms crossed, level gaze |
| `concerned` | 2 | head down, hand on hip |
| `disappointed` | 2 | head shake, frown |
| `intense` | 2 | pointing, brow furrowed |
| `relaxed` | 2 | coffee in hand, easy stance |
| `tired` | 2 | yawning / rubbing eyes |

All 12 emotions also need a `talk` variant (mouth open/closed) for
when text is teletyping. So the full sheet is **24 base + 12 talk =
36 frames per coach**. T-Rod has all 36 from the user's reference
sheet; the other 4 coaches generate via the prompts in
[`assets/reference-sheet-source.md`](assets/reference-sheet-source.md).

## Vue consumption

```vue
<!-- Sprite usage with emotion -->
<Sprite
  sheet="trod"
  :animation="emotion"
  :variant="talking ? 'talk' : 'idle'"
/>
```

The `Sprite.vue` component composes `<sheet>_<emotion>_<variant>_<frame>`
to find the right cell. Falls back to `idle` if a frame isn't present.

## Pressure tests

| Scenario | Expected behaviour |
|---|---|
| Gemma omits the `[EMOTION: ...]` tag | Default to `neutral` |
| Gemma emits an unknown emotion | Default to `neutral`, log warning |
| Gemma emits the tag mid-text instead of at start | Strip the tag, use it; remaining text is the response |
| Multiple `[EMOTION: ...]` tags in one response | Use the first; strip all |
| Coach sprite missing the emotion frame | `Sprite.vue` falls back to `idle` |
| Emotion tag in a canonical phrase doesn't match valid set | Log + use `neutral` (caught in tests) |

## Decision log

- **Why a 12-emotion set, not 5 or 30?** 5 (the "5 personas × 4
  emotions" earlier) felt too coarse for in-drive nuance. 30+ was
  the user's reference sheet's full inventory, which would overwhelm
  Gemma to choose between. 12 is the comfortable middle — every
  emotion has a clear coaching context.
- **Why have Gemma choose, not a deterministic rule?** Because Gemma
  generates the *text*, and the emotion that fits the text is
  context-sensitive. A fixed rule like "if `delta_to_pb > 0.5s` ⟹
  encouraging" misses the times when the coach should be
  *disappointed despite an improvement* (e.g., the player got faster
  but did it unsafely).
- **Why not have Gemma generate the animation directly?** Because
  Gemma can't render sprites, and a free-form animation choice would
  break the sprite-sheet contract. A 12-item enum is the right
  abstraction for the LLM.

## Related

- [`03-character-bible.md`](03-character-bible.md) — voice and persona
  per coach (extended by this doc)
- [`02-sprite-sheet-spec.md`](02-sprite-sheet-spec.md) — sprite frame
  taxonomy (extended to 36 frames per coach)
- [`assets/reference-sheet-source.md`](assets/reference-sheet-source.md)
  — nano-banana prompts for emotion frames
- [`screens/_coach-speaks-modal.md`](screens/_coach-speaks-modal.md)
  — the canonical "LLM is talking" overlay
- [ADR-017 — Three-tier coach architecture](../adr/017-three-tier-coach-architecture.md)
  — pre-rendered phrases also carry emotion tags

# 05 — Coach Select

The roster screen. Five coaches as cards; the player picks who's
talking to them this session.

## Purpose

Verb: **Recruit.** Pick the voice in your ear. Each coach is the same
engine underneath ([ADR-017](../../adr/017-three-tier-coach-architecture.md))
with different system prompts and pre-rendered voice clips.

## Wireframe

```
┌────────────────────────────────────────────────────────────┐
│ TAHA · LV.12 · ⚙ T-ROD                          15:32 PT   │
│ ─────────────────────────────────────────────────────────  │
│ COACHES                                                    │
│                                                            │
│  ┌──────┐  ┌──────┐  ┌──────┐                              │
│  │      │  │      │  │      │                              │
│  │ T-ROD│  │BUDDY │  │ DRILL │                             │
│  │ ▼    │  │      │  │ LV 5  │  ← locked grey               │
│  │ 96×96│  │ 96×96│  │ 96×96│                              │
│  └──────┘  └──────┘  └──────┘                              │
│   ACTIVE    UNLOCKED   LOCKED                              │
│                                                            │
│      ┌──────┐  ┌──────┐                                    │
│      │      │  │      │                                    │
│      │BENTLEY│  │ CALM │                                   │
│      │ LV 10│  │ LV 15│                                    │
│      │ 96×96│  │ 96×96│                                    │
│      └──────┘  └──────┘                                    │
│       LOCKED   LOCKED                                      │
│                                                            │
│ ╔══════════════════════════════════════════════════════╗   │
│ ║ ▼ "Distance is king."                                ║   │
│ ║                          —— T-Rod                    ║   │
│ ╚══════════════════════════════════════════════════════╝   │
│                                                            │
│  A · SELECT     B · GARAGE     ◀ ▶ MOVE                    │
└────────────────────────────────────────────────────────────┘
```

## States

| State | Behaviour |
|---|---|
| `idle` | Cursor on currently-selected coach; selected coach pulses 2 Hz |
| `previewing` | Cursor moved to a different coach; that coach plays a sample teletyped quote |
| `locked-bump` | A on a locked coach: brief shake + `cancel` SFX + dialogue: *"Reach level X to recruit."* |
| `swapping` | A on an unlocked coach: previous coach speaks farewell, transition, new coach speaks greeting |

## Sprite usage

| Sprite | Where | Animation |
|---|---|---|
| Each coach 96×96 portrait | Card | `idle` 2-frame; selected coach also runs `talk` while quote teletypes |
| `frame-card` | Each card | 9-slice; locked variant (greyed) for unselectable |
| `frame-dialogue` | Bottom quote | 9-slice with speech-bubble pointer |
| Cursor | On focused card | Bouncing |

## Unlock gates

| Coach | Unlock | Default |
|---|---|---|
| T-Rod | always | yes (default coach) |
| Buddy | always | no |
| Drill Sergeant | driver level 5 | no |
| Bentley | driver level 10 | no |
| Calm Pro | driver level 15 | no |

Levels per `04-state-architecture.md` `floor(sessions / 5) + 1`.

## Vue component

```vue
<!-- pitwall-web/src/views/CoachSelect.vue -->
<template>
  <div class="viewport">
    <StatusBar />
    <h1 class="font-title text-title">COACHES</h1>

    <div class="coach-grid">
      <CoachCard v-for="c in coaches" :key="c.id"
                 :coach="c"
                 :focused="cursor === c.id"
                 :selected="save.preferredCoach === c.id"
                 :locked="!save.unlockedCoaches.includes(c.id)"
                 @select="trySelect(c)" />
    </div>

    <DialogueBox v-if="previewQuote"
                 :coach-id="cursor"
                 emotion="talk"
                 :text="previewQuote" />

    <HintBar :hints="['A · SELECT', 'B · GARAGE', '◀ ▶ MOVE']" />
  </div>
</template>

<script setup lang="ts">
async function trySelect(c: CoachDef) {
  if (!save.unlockedCoaches.includes(c.id)) {
    audio.playSfx('cancel')
    showLockedDialogue(c)
    return
  }
  audio.playSfx('cursor_select')
  // Play prior coach farewell, then swap, then new coach greeting
  await audio.playVoice(save.preferredCoach, 'farewell_swap')
  save.preferredCoach = c.id
  await save.persist()
  await audio.playVoice(c.id, pickGreeting())
}
</script>
```

## Endpoints consumed

| Endpoint | When |
|---|---|
| `GET /coach/concepts` | On mount; cached at app level — confirms which Bentley concepts each coach can fire (cosmetic flavour text per card) |

Voice clips are local pre-rendered MP3s from
`/audio/coaches/<coach-id>/greet_*.mp3` per
[`06-audio-design.md`](../06-audio-design.md). No live LLM call here —
this is a paddock screen, but voice is pre-rendered so swapping is
instant.

## Audio cues

| Event | Sound |
|---|---|
| Cursor move (preview) | `cursor_move` + start the previewed coach's `talk` animation |
| A on unlocked coach | `cursor_select` then sequenced: prior `farewell_swap` MP3 → 200 ms wipe → new `greet_*` MP3 |
| A on locked coach | `cancel` + locked-coach speech-bubble |
| Mount | `garage_loop` continues (no music swap) |

## Input map

| Input | Action |
|---|---|
| ◀ ▶ ▲ ▼ | Move cursor between cards |
| A | Try to select |
| B | Back to garage hub |
| Start | No-op |

## Edge cases

- **All coaches locked except defaults** — only T-Rod and Buddy
  selectable; the other three show silhouettes + level requirement
- **Coach affinity** (per [`03-character-bible.md`](../03-character-bible.md))
  — affinity-level badge shown under each unlocked card; max level 5
  unlocks the personalised "kid → driver name" flourish
- **Voice clip missing** (network-fetched mid-session) — fall back to
  Web Speech API with the coach's voice profile
- **Bridge offline** — screen still works; `/coach/concepts` is cached

## Related

- [`02-onboarding.md`](02-onboarding.md) — same UI as step 4 of onboarding
- [`03-character-bible.md`](../03-character-bible.md) — full cast bible
- [`06-audio-design.md`](../06-audio-design.md) — voice generation pipeline
- [ADR-017 — Three-tier coach](../../adr/017-three-tier-coach-architecture.md)

# 28 — Coach Codex

Pokédex-style listing of every canonical coaching phrase the driver
has heard. Sub-tab of `12-quest-log.md` (no separate route — accessed
via tab-switch within Quest Log).

## Purpose

Verb: **Collect.** Show what the player has unlocked from the coach's
phrase library. Re-experience phrases on demand.

## Wireframe

```
┌────────────────────────────────────────────────────────────┐
│ TAHA · LV.12 · ⚙ T-ROD                          15:32 PT   │
│ ─────────────────────────────────────────────────────────  │
│ COACH CODEX                                                │
│                                                            │
│ ┌────┐                                                     │
│ │T-RD│                                                     │
│ │SEL │  ┌────┐  ┌────┐  ┌────┐  ┌────┐                     │
│ └────┘  │BNTLY│  │DRILL│  │CALM │  │BUDDY│                  │
│         └────┘  └────┘  └────┘  └────┘                     │
│                                                            │
│ T-ROD · 47 / 50 PHRASES HEARD ····················  94 %  │
│                                                            │
│ ╔══════════════════════════════════════════════════════╗   │
│ ║ ✓ 🅴 distance_is_king         "Distance is king"      ║   │
│ ║ ✓ 🅴 closer_tire_stacks       "Be closer to tires"   ║   │
│ ║ ✓ 🅴 100_percent              "Just go 100"           ║   │
│ ║ ✓ 🅸 trail_brake              "Roll the brake to apex"║   │
│ ║ ✓ 🅼 single_apex              "Treat as double"       ║   │
│ ║ ✓ 🅴 trust_curb               "Trust the curb"        ║   │
│ ║ ▒ ?? open_up_nine             ──────                 ║   │
│ ║ ✓ 🅸 cool_down                "Same line, slower"    ║   │
│ ║ ✓ 🅸 brake_to_apex            "Roll the brake"        ║   │
│ ║ ▒ ?? cut_distance             ──────                 ║   │
│ ║ …                                                    ║   │
│ ╚══════════════════════════════════════════════════════╝   │
│                                                            │
│ A · PLAY     B · BACK     ◀ ▶ COACH    ◆ FILTER           │
└────────────────────────────────────────────────────────────┘
```

The leading icon next to each phrase is the **emotion glyph** from
`../10-coach-emotions.md`: 🅴 = encouraging, 🅸 = intense,
🅼 = analyzing, etc. Pre-tagged in the canonical library.

## States

| State | Behaviour |
|---|---|
| `idle` | Cursor on first heard phrase; coach idle in corner with `relaxed` emotion |
| `playing` | A on a heard phrase opens `_coach-speaks-modal.md` with that exact phrase + emotion + voice clip |
| `filtered` | ◆ filters by emotion, group, or "unheard only" |

## Sprite usage

| Sprite | Where | Animation |
|---|---|---|
| Coach portrait (per tab) | Top-left tab | Static `idle` for selected, silhouette for others |
| `cursor_arrow` | On focused phrase | Bouncing |
| Coach idle in corner | Right side | Emotion = `relaxed` (relaxed in the codex; this is downtime) |
| Emotion glyphs | Per phrase | Static, 16×16 |

## Vue component

```vue
<!-- Sub-component of QuestLog.vue or own view -->
<template>
  <CoachTabs :coaches="coaches" v-model="selected" />
  <ProgressBar :pct="(heardCount/totalCount)*100" />
  <PhraseList :phrases="phrases" :focus="cursor"
              @select="play" />
  <CoachSpeaksModal v-if="playing" v-bind="playing"
                    @dismissed="playing = null" />
  <HintBar :hints="hints" />
</template>
```

The phrase library lives in
`pitwall-web/data/voices/<coach>-phrases.json` per the
`../06-audio-design.md` spec; this screen reads it client-side and
overlays the player's heard-status from the save slot.

## Endpoints consumed

| Endpoint | Use |
|---|---|
| `GET /coach/concepts` | Cached; the 9 Bentley concepts the phrases reference |

Otherwise pure local state.

## Audio cues

| Event | Sound |
|---|---|
| Coach tab switch | `cursor_select` |
| Phrase row cursor | `cursor_move` |
| A on heard phrase | Plays the phrase's pre-rendered MP3 + opens speaks modal |
| A on unheard phrase | `cancel` (you have to earn it first) |

## Input map

| Input | Action |
|---|---|
| ▲ ▼ | Cursor through phrases |
| ◀ ▶ | Switch coach tabs |
| A | Play focused phrase (if heard) |
| B | Back to Quest Log |
| Start | Pause menu |
| ◆ | Filter dropdown (emotion / group / heard-only) |

## Edge cases

- **First entry, zero phrases heard** — empty state with coach idle
  and a hint: *"Drive a session to start collecting."*
- **All 50 heard for a coach** — confetti burst + special title
  badge "MASTER OF T-ROD'S VOICE"
- **Player switches active coach mid-session** — codex tab persists
  the previously-active selection across visits, doesn't auto-jump

## Related

- [`12-quest-log.md`](12-quest-log.md) — parent (this is a tab inside)
- [`../03-character-bible.md`](../03-character-bible.md) — coach voices
- [`../06-audio-design.md`](../06-audio-design.md) — phrase library
- [`../10-coach-emotions.md`](../10-coach-emotions.md) — emotion glyphs
- [`_coach-speaks-modal.md`](_coach-speaks-modal.md) — used to play phrases

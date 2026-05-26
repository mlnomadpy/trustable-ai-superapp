# 03 — Garage Hub

The Pokémon-town-square of the app. Every other screen is reached
from here. The chosen coach idles in the background; the player picks
where to go next.

## Purpose

Verb: **Choose where to go.** Six hub tiles + status bar surface every
top-level action.

## Wireframe

```
┌────────────────────────────────────────────────────────────┐
│ TAHA · LV.12 · ⚙ T-ROD                          15:32 PT   │
│ ─────────────────────────────────────────────────────────  │
│                                                            │
│  ╔══════════════════╗  ╔══════════════════════╗            │
│  ║   ▶ TRACK         ║  ║   PIT STALL          ║            │
│  ║                   ║  ║                      ║            │
│  ║   GO RACING       ║  ║   CONNECT · TUNE     ║            │
│  ╚══════════════════╝  ╚══════════════════════╝            │
│                                                            │
│  ╔══════════════════╗  ╔══════════════════════╗            │
│  ║   TRAINER CARD    ║  ║   ANALYSIS           ║            │
│  ║   ★★★★★★★★★         ║  ║   LAPS · CORNERS    ║            │
│  ║   STATS · MEDALS  ║  ║   STRAIGHTS · TRACK   ║            │
│  ╚══════════════════╝  ╚══════════════════════╝            │
│                                                            │
│  ╔══════════════════╗  ╔══════════════════════╗            │
│  ║   COACHES         ║  ║   QUEST LOG          ║            │
│  ║   ┌──┐┌──┐         ║  ║   3 ACTIVE GOALS     ║            │
│  ║   └──┘└──┘ + 3    ║  ║   12 / 40 MEDALS     ║            │
│  ╚══════════════════╝  ╚══════════════════════╝            │
│                                                            │
│ ░░░ Coach T-ROD walks across this band ░░░░░░░░░░          │
│                                                            │
│ A · ENTER     B · TITLE     ◆ MENU                         │
└────────────────────────────────────────────────────────────┘
```

## States

| State | Behaviour |
|---|---|
| `idle` | Cursor on TRACK by default; coach NPCs idle/walk in the bottom band |
| `coach-greeting` | First entry of the session: dialogue box appears with rotating greeting; A dismisses |
| `notification` | Achievement / queued debrief ready: small ✉ icon pulses in status bar |

## Tiles

| Tile | Route | Visible always? | Sub-text |
|---|---|---|---|
| TRACK | `/world` | Yes | "GO RACING" |
| PIT STALL | `/garage/pit-stall` | Yes | "CONNECT · TUNE" |
| TRAINER CARD | `/garage/trainer` | Yes | "STATS · MEDALS" |
| ANALYSIS | `/garage/analysis` | Yes after first session | "LAPS · CORNERS" |
| COACHES | `/garage/coach` | Yes | "+3" if unlocked coaches > 1 |
| QUEST LOG | `/garage/quests` | Yes | "N ACTIVE GOALS" |

The ANALYSIS tile shows on the home screen but greys out until the
driver has at least one completed session in DuckDB.

## Sprite usage

| Sprite | Where | Animation |
|---|---|---|
| `bg_garage_interior` | Background | Static |
| Coach (e.g., `trod`) | Bottom band | `walk_l` cycle, walks every ~30 s |
| `crew_walk_generic` | Bottom band | Walks the opposite direction |
| `tires_static` | Decoration | Static |
| `lamp_idle` | Top of background | 0.5 Hz flicker |
| Cursor | On hovered tile | Bouncing |

## Vue component

```vue
<!-- pitwall-web/src/views/GarageHub.vue -->
<template>
  <div class="viewport">
    <StatusBar />
    <Sprite name="bg_garage_interior" class="absolute inset-0 -z-10"/>

    <div class="grid grid-cols-2 gap-4 p-4">
      <Tile v-for="t in tiles" :key="t.id"
            :tile="t" :focused="cursor === t.id"
            @select="onSelect(t.id)" />
    </div>

    <NpcBand>
      <Sprite name="trod" :animation="trodAnim" :style="{ left: trodX + 'px' }" />
      <Sprite name="crew_walk_generic" :animation="crewAnim" :style="{ left: crewX + 'px' }" />
    </NpcBand>

    <DialogueBox v-if="greetingActive"
                 :coach-id="save.activeSlot!.preferredCoach"
                 :text="greetingText"
                 emotion="idle"
                 @done="greetingActive = false" />

    <HintBar :hints="['A · ENTER', 'B · TITLE', '◆ MENU']" />
  </div>
</template>
```

## Endpoints consumed

| Endpoint | Use |
|---|---|
| `GET /health` | Polled every 5 s (in `useBridgeStore`); offline indicator if it fails |
| `GET /coach/concepts` | Cached; populates the COACHES tile sub-text |
| `GET /sessions?driver=<name>` | Lap-count badge on TRACK tile (post-MVP) |

## Audio cues

| Event | Sound |
|---|---|
| Mount | `garage_loop` music starts |
| Cursor move | `cursor_move` |
| Tile A | `cursor_select` → wipe to destination |
| Coach greeting starts | pre-rendered MP3 of one of the greetings (per `03-character-bible.md`) |
| New achievement waiting | `goal_complete` (one-shot, plays once) |

## Input map

| Input | Action |
|---|---|
| ▲ ▼ ◀ ▶ | Move cursor |
| A | Enter the focused tile |
| B | Back to title (with confirmation: "QUIT TO TITLE?") |
| Start (◆) | Quick menu |

## Edge cases

- **First entry after onboarding** — coach plays the long welcome
  greeting (`greet_first_session`)
- **First entry of a new day** — coach plays `greet_morning` /
  `greet_afternoon` / `greet_evening` based on local time
- **Bridge offline** — TRACK tile greys out (can't start a new session
  without telemetry); ANALYSIS still works from cached Parquet
- **Notification icon** — only shows when there's a real notification
  to surface (queued debrief done, new medal earned)

## Related

- [`05-coach-select.md`](05-coach-select.md) — COACHES tile
- [`04-trainer-card.md`](04-trainer-card.md) — TRAINER CARD tile
- [`06-world-map.md`](06-world-map.md) — TRACK tile
- [`12-quest-log.md`](12-quest-log.md) — QUEST LOG tile
- [`13-settings.md`](13-settings.md) — Start menu opens this
- [`15-pit-stall-setup.md`](15-pit-stall-setup.md) — PIT STALL tile
- [`16-analysis-hub.md`](16-analysis-hub.md) — ANALYSIS tile

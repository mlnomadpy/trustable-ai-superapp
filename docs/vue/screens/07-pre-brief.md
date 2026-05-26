# 07 — Pre-Brief

The setup conversation. Coach speaks; driver picks 1–3 goals for the
session; pre-flight check sits on top so any hardware problem is
visible before the car moves.

## Purpose

Verb: **Set intentions.** Carry forward goals into the HUD as
attention anchors and into Stage Clear as scored objectives.

## Wireframe

```
┌────────────────────────────────────────────────────────────┐
│ TAHA · LV.12 · ⚙ T-ROD                          15:32 PT   │
│ ─────────────────────────────────────────────────────────  │
│ PRE-SESSION BRIEFING · SONOMA RACEWAY                      │
│                                                            │
│ ╔═ PRE-FLIGHT ═══════════════════════════════════════════╗ │
│ ║ ✓ BRIDGE   ✓ USB-CAN  ✓ DBC   ✓ CALIBRATION            ║ │
│ ╚═══════════════════════════════════════════════════════╝ │
│                                                            │
│ ┌──────────┐  ┌────────────────────────┐                  │
│ │          │  │  "Settle in. Peak grip │                  │
│ │  T-ROD   │  │   today, so we're going│                  │
│ │  talking │  │   to be tight. T7 is   │                  │
│ │   anim   │  │   costing you 0.4s vs  │                  │
│ │          │  │   last week."          │                  │
│ └──────────┘  └────────────────────────┘                  │
│                                                            │
│ PICK YOUR GOALS  (1–3)                                     │
│ ─────────────────────────────────────────────────────────  │
│  ☑ ▶ APEX SPEED AT T7         +3 km/h target              │
│  ☑   BREAK 1:48               PB delta                    │
│  ☐   TRAIL BRAKE EVERY ENTRY                              │
│  ☐   SECTOR 2 SUB-37s                                     │
│                                                            │
│ WEATHER  ░ peak grip · 13:00                               │
│ TRACK    ░ DRY · 21°C                                      │
│                                                            │
│  A · TOGGLE / CONFIRM    B · BACK     ◆ EDIT GOALS         │
└────────────────────────────────────────────────────────────┘
```

## States

| State | Trigger | Behaviour |
|---|---|---|
| `loading` | Mount | Fetch `/coach/brief`; coach `clipboard_writing` while waiting; pre-flight populates async |
| `briefing` | Brief loaded | Coach `talk` animation + teletype the dialogue |
| `goals` | Briefing dismissed | Goal list interactive; cursor on first goal |
| `confirming` | A on CONFIRM | Persist goals to session; wipe-down to HUD |
| `pre-flight-fail` | Any pre-flight ✗ | Block CONFIRM; show inline reason; offer "GO TO PIT STALL" tile |

## Goal kinds

Three shapes, per `pitwall-web-design.md` § "Session Goals":

| Kind | Source | Example |
|---|---|---|
| `corner_focus` | Driver profile flags weakest corners; `evolution.biggest_corner_loss` | "APEX SPEED AT T7   +3 km/h target" |
| `lap_time` | Best lap PB in profile | "BREAK 1:48 (PB 1:48.2)" |
| `technique` | Bentley concepts under-fired in last session | "TRAIL BRAKE EVERY ENTRY" |

## Sprite usage

| Sprite | Where | Animation |
|---|---|---|
| Coach (selected, default T-Rod) | Left of dialogue box | `talk` while teletyping; `idle` after |
| `frame-default` | Pre-flight panel | 9-slice |
| `frame-dialogue` | Coach quote | 9-slice with pointer |
| `frame-card` | Goals list | 9-slice |
| `check_v` / `x_v` | Pre-flight indicators | Static |

## Vue component

```vue
<!-- pitwall-web/src/views/PreBrief.vue -->
<template>
  <div class="viewport">
    <StatusBar />
    <h1 class="font-title text-title">PRE-SESSION BRIEFING · SONOMA RACEWAY</h1>

    <PreFlightStrip :state="preflightState" />

    <DialogueBox :coach-id="save.preferredCoach"
                 emotion="talk"
                 :text="briefText"
                 @done="phase = 'goals'" />

    <GoalList v-if="phase === 'goals'"
              :suggestions="goalSuggestions"
              v-model:selected="selectedGoals" />

    <WeatherStrip :weather="weather" :surface="surface" />

    <HintBar :hints="hints" />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
async function fetchBrief() {
  const params = new URLSearchParams({
    driver: save.driverName,
    hour_local: String(new Date().getHours()),
    goal: 'personal best lap',
  }).toString()
  const r = await fetch(`/api/coach/brief?${params}`)
  const data = await r.json()
  briefText.value = data.narrative
  goalSuggestions.value = data.focus_corners.map(c => ({
    kind: 'corner_focus', description: `APEX SPEED AT ${c}`, ...
  }))
}
async function confirm() {
  await session.startSession({ goals: selectedGoals.value })
  router.push({ name: 'drive', params: { trackId: 'sonoma' } })
}
</script>
```

## Endpoints consumed

| Endpoint | When |
|---|---|
| `GET /coach/brief?driver=&hour_local=&focus=&goal=` | On mount; coach narrative + focus list |
| `GET /track/weather?hour_local=` | On mount; bottom strip |
| `GET /health` | Pre-flight bridge ✓ |
| `GET /signals/registry?include_can_state=true` | Pre-flight USB-CAN ✓ |
| `POST /session/start` | On CONFIRM (creates the session_id) |

## Audio cues

| Event | Sound |
|---|---|
| Mount | swap to `prebrief_loop` (lower-key) |
| Brief loaded | pre-rendered TTS for the brief, OR `coach_thinking` while LLM generates |
| Goal toggle | `cursor_select` |
| Goal added (3rd) | `goal_complete` (mini-affirmation) |
| Pre-flight fails | `error_quiet` (one-shot) |
| CONFIRM | `cursor_select` (heavier) → wipe-down to HUD |

## Input map

| Input | Action |
|---|---|
| ▲ ▼ | Move cursor between goals |
| A | Toggle current goal (or CONFIRM if cursor on confirm tile) |
| B | Back to world map |
| Start (◆) | Open custom-goal editor |

## Edge cases

- **Coach brief endpoint fails** — fall back to templated brief (per
  LitertCoach `_templated_pre_brief`); coach voice clips for *"Settle
  in"* still play
- **Pre-flight ✗** (e.g., USB-CAN unplugged) — pre-flight strip turns
  amber; CONFIRM disabled; coach line: *"Plug it in first, kid"*; "GO
  TO PIT STALL" mini-tile appears
- **No goal suggestions** (new driver, no profile) — show generic
  goals: "Complete 3 clean laps", "Stay smooth", etc.
- **Player picks 0 goals + CONFIRM** — coach raises an eyebrow:
  *"No goals? Fine, free-drive."* Allowed. Stage Clear scores 0 of 0.
- **Bridge offline mid-pre-brief** — block CONFIRM with "BRIDGE OFFLINE";
  player can navigate back

## Walk-the-track button

Below the goal list, a "**▶ WALK THE TRACK**" button opens
[`37-track-walk.md`](37-track-walk.md) — the interactive Sonoma layout
where the player can tap any corner for coach commentary + their
historical performance, add corners to session goals from there, and
read marker lore. Returning from track-walk drops the player back on
this pre-brief screen with any added goals already in the list.

## Related

- [`06-world-map.md`](06-world-map.md) — entry point
- [`37-track-walk.md`](37-track-walk.md) — interactive track exploration
  + per-corner coaching
- [`08-on-track-hud.md`](08-on-track-hud.md) — destination
- [`15-pit-stall-setup.md`](15-pit-stall-setup.md) — fallback on pre-flight ✗
- [`10-stage-clear.md`](10-stage-clear.md) — where the goals are scored
- [`36-goals-library.md`](36-goals-library.md) — custom goal editor
- [Bridge `/coach/brief`](../../api.md)

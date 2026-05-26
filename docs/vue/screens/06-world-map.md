# 06 — World Map

The Pokémon-region-map of Pitwall. Pixel-art California coast with
track pins. Sonoma's the only one open today; the rest are silhouettes
with carrots.

## Purpose

Verb: **Travel.** Pick where to drive. Sets up post-Sonoma multi-track
expansion as a visible roadmap.

## Wireframe

```
┌────────────────────────────────────────────────────────────┐
│ TAHA · LV.12 · ⚙ T-ROD                          15:32 PT   │
│ ─────────────────────────────────────────────────────────  │
│ WORLD MAP                                                  │
│                                                            │
│       ░░░░░░░░  PACIFIC  ░░░░░░░░░░░░                      │
│      ░░░  ◉ SONOMA  1:46.8  ░░                             │
│       ░░░    └──RACEWAY──┐  ░░░                            │
│      ░░░    ★ ★ ★ ★ ★      │ ░░░                            │
│     ░░░                    │░░░                            │
│    ░░░    ◯ LAGUNA SECA   │░░                              │
│   ░░░     LOCKED — 50      │░                              │
│  ░░░       SESSIONS                                        │
│ ░░░                                                        │
│ ░░░    ◯ THUNDERHILL  LOCKED — 25 MEDALS                  │
│                                                            │
│ ░░░    ◯ BUTTONWILLOW  LOCKED — LV. 20                    │
│                                                            │
│ ░░░░░░░░  CALIFORNIA  ░░░░░░░░░░░░░░░░░                    │
│                                                            │
│ ╔══════════════════════════════════════════════════════╗   │
│ ║ SONOMA · 4.06km · 11 corners · ★★★★★                  ║   │
│ ║ "Half the lap is in the corners."                    ║   │
│ ║ WEATHER: peak grip · DRY · 21°C                      ║   │
│ ║ NEXT SESSION: open                                   ║   │
│ ╚══════════════════════════════════════════════════════╝   │
│                                                            │
│  A · ENTER     B · GARAGE     ◀ ▶ MOVE                     │
└────────────────────────────────────────────────────────────┘
```

## States

| State | Behaviour |
|---|---|
| `loading` | Mount; fetch weather + markers + danger zones |
| `idle` | Sonoma pin pulses (2 Hz); cursor on Sonoma; bottom card filled |
| `cursor-moving` | Cursor crosses the map between pins; tiny dust-puff sprite at last position |
| `locked-bump` | A on a locked track: shake + `cancel` SFX |

## Sprite usage

| Sprite | Where | Animation |
|---|---|---|
| `bg_california_map` | Background | Static; subtle wave animation on the ocean (0.5 Hz) |
| `track_pin_unlocked` | Sonoma | 2-frame pulse |
| `track_pin_locked` | Other tracks | Silhouette, 1-frame |
| `dust_puff` 4-frame | Trailing cursor movement | Plays once per move |
| `frame-card` | Bottom info card | 9-slice |
| Cursor | Hidden — pins are the cursor target |

## Track unlock criteria

| Track | Unlock |
|---|---|
| Sonoma Raceway | always |
| Laguna Seca | "Drive 50 sessions at Sonoma" |
| Thunderhill | "Earn 25 medals" |
| Buttonwillow | "Reach Driver Level 20" |

These are aspirational — no real geometry / DBC / pedagogy for the
locked three. They exist to set the post-Sonoma roadmap visibly.

## Vue component

```vue
<!-- pitwall-web/src/views/WorldMap.vue -->
<template>
  <div class="viewport">
    <StatusBar />
    <h1 class="font-title text-title">WORLD MAP</h1>

    <Sprite name="bg_california_map" class="absolute inset-0 -z-10" />

    <TrackPin v-for="t in tracks" :key="t.id"
              :track="t"
              :focused="cursor === t.id"
              :unlocked="save.unlockedTracks.includes(t.id)"
              :style="t.position"
              @hover="cursor = t.id"
              @select="enter(t)" />

    <Frame frame-type="card" class="track-info-card">
      <h3>{{ activeTrack.name.toUpperCase() }} · {{ activeTrack.length_km }}km · {{ activeTrack.corners }} corners · {{ '★'.repeat(activeTrack.difficulty) }}</h3>
      <p>"{{ activeTrack.tagline }}"</p>
      <p>WEATHER: {{ weather.phase }} · {{ weather.surface_state }} · {{ weather.temp_c }}°C</p>
      <p>NEXT SESSION: {{ unlocked ? 'open' : `LOCKED — ${activeTrack.unlockText}` }}</p>
    </Frame>

    <HintBar :hints="['A · ENTER', 'B · GARAGE', '◀ ▶ MOVE']" />
  </div>
</template>
```

## Endpoints consumed

| Endpoint | When |
|---|---|
| `GET /track/markers` | On mount; populates pin positions for unlocked tracks |
| `GET /track/danger_zones` | On mount; informational badge on the active card |
| `GET /track/weather?hour_local=<h>` | On mount + every 5 min while on screen |

Locked-track placeholders are hard-coded — no bridge call needed
because they're not playable.

## Audio cues

| Event | Sound |
|---|---|
| Mount | swap to `worldmap_loop` |
| Cursor moves to a different pin | `cursor_move` + `dust_puff` particle |
| A on Sonoma | `cursor_select` → wipe to `/track/sonoma` (pre-brief) |
| A on locked track | `cancel` |
| Weather phase changes | quiet pre-rendered phrase from coach: *"Surface is heating up."* |

## Input map

| Input | Action |
|---|---|
| ◀ ▶ ▲ ▼ | Move cursor between pins (snap to nearest) |
| A | Enter selected track |
| B | Back to garage hub |

## Edge cases

- **Bridge offline** — weather card shows last-cached values; pin still
  works; player can still enter Sonoma but pre-brief will catch the
  offline state
- **All tracks locked** (impossible in v1 since Sonoma is always open;
  documented for completeness) — coach line: *"Drive Sonoma first, kid"*
- **Hour boundaries change weather phase mid-session** — bottom card
  updates with a small flash; no toast (player is mid-decision)
- **Pin spacing** — pins are placed in fixed map coordinates, not
  randomised; navigation order is geographic (Sonoma N → Laguna →
  Thunderhill → Buttonwillow S)

## Related

- [`03-garage-hub.md`](03-garage-hub.md) — entry point
- [`07-pre-brief.md`](07-pre-brief.md) — destination after A on Sonoma
- [`20-track-atlas.md`](20-track-atlas.md) — same data, more depth
- Bridge: [`/track/markers`](../../api.md), [`/track/weather`](../../api.md)

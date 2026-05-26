# 04 — Trainer Card

The Pokémon-trainer-card moment. Driver portrait + name + level + skill
radar + medals. The face the player shows the world.

## Purpose

Verb: **Reflect.** "Who am I as a driver?" Surfaces who you are, what
you've done, where you're growing.

## Wireframe

```
┌────────────────────────────────────────────────────────────┐
│ TAHA · LV.12 · ⚙ T-ROD                          15:32 PT   │
│ ─────────────────────────────────────────────────────────  │
│                                                            │
│ ╔═ TRAINER CARD ═════════════════════════════════════════╗ │
│ ║ ┌──────────┐                                          ║ │
│ ║ │ AVATAR   │   TAHA                                   ║ │
│ ║ │  64 × 64 │   LV. 12 · INTERMEDIATE                  ║ │
│ ║ │   idle   │   47  TRACK SESSIONS                     ║ │
│ ║ └──────────┘   ★ BEST 1:46.8                         ║ │
│ ║                ▼ -5.2s vs 1 YEAR AGO                  ║ │
│ ║                                                       ║ │
│ ║ CAR    ░░ BMW M3 (E46)                                ║ │
│ ║ COACH  ░░ T-ROD · INTERMEDIATE                        ║ │
│ ║ TRACK  ░░ SONOMA RACEWAY                              ║ │
│ ╚═══════════════════════════════════════════════════════╝ │
│                                                            │
│ SKILL RADAR                       ★ MEDALS  14 / 40        │
│  BRAKING       ████████░░  B+      ★ ★ ★ ░ ░               │
│  TRAIL BRAKE   ██████████  A       ★ ★ ★ ★ ★               │
│  CORNER SPEED  ███████░░░  B       ★ ★ ★ ░ ░               │
│  THROTTLE      ████████░░  B+      ★ ★ ★ ★ ░               │
│  CONSISTENCY   ██████████  A       ★ ★ ★ ★ ★               │
│  LINE          ███████░░░  B       ★ ★ ★ ░ ░               │
│                                                            │
│  A · MEDALS    ◆ EVOLUTION    B · GARAGE                   │
└────────────────────────────────────────────────────────────┘
```

## States

| State | Trigger | Behaviour |
|---|---|---|
| `loading` | Mount | `GET /driver/<id>/profile` + `evolution`; skeleton bars; coach `clipboard_writing` |
| `idle` | Profile loaded | Static card; coach `idle` in corner |
| `medals-grid` | A pressed | Slide to medal grid sub-view (5×8 = 40 slots) |
| `evolution-chart` | ◆ Start pressed | Slide to multi-line evolution chart |
| `medal-detail` | A on a medal | Dialogue box with criteria + acquisition date |

## Sprite usage

| Sprite | Where | Animation |
|---|---|---|
| Driver avatar (per save slot) | Top-left card portrait | `idle` 2-frame breathing |
| Coach (T-Rod default) | Bottom-right corner | `idle` |
| `frame-card` | Card outer frame | 9-slice |
| `medal_*` | Medal grid (`02-sprite-sheet-spec.md`) | Static; locked = silhouette |
| `radar_axis` | 6-axis radar diagram (post-MVP visual; bars are MVP) | Static |

## Vue component

```vue
<!-- pitwall-web/src/views/TrainerCard.vue -->
<template>
  <div class="viewport">
    <StatusBar />
    <h1 class="font-title text-title">TRAINER CARD</h1>

    <Frame frame-type="card">
      <Sprite :name="`avatars`" :animation="`avatar_${avatar}_idle`" />
      <div class="card-meta">
        <h2>{{ save.driverName }}</h2>
        <p>LV. {{ save.level }} · {{ save.skillLevel.toUpperCase() }}</p>
        <p>{{ totalSessions }} TRACK SESSIONS</p>
        <p>★ BEST {{ formatLap(profile?.best_lap_s) }}</p>
        <p v-if="evolution?.summary">▼ {{ deltaVsYearAgo }}s vs 1 YEAR AGO</p>
      </div>
    </Frame>

    <SkillRadar :profile="profile" v-if="view === 'idle'" />
    <MedalGrid :medals="save.medals" v-else-if="view === 'medals'" @open="openMedal" />
    <EvolutionChart :data="evolution" v-else-if="view === 'evolution'" />

    <Sprite name="trod" animation="idle" class="absolute bottom-12 right-4" />

    <DialogueBox v-if="activeMedal"
                 :coach-id="save.preferredCoach"
                 emotion="thumbsup"
                 :text="activeMedal.acquisitionText"
                 @done="activeMedal = null" />

    <HintBar :hints="hints" />
  </div>
</template>
```

## Endpoints consumed

| Endpoint | When |
|---|---|
| `GET /driver/<id>/profile` | On mount; cached for the session |
| `GET /driver/<id>/evolution?track=sonoma` | On mount; 204 (< 5 sessions) is fine — chart shows "needs more sessions" |

The skill-radar values come from `driver_profile.compute_profile`'s
output (six dimensions: braking, trail_brake, corner_speed, throttle,
consistency, line). Each is a 0-100 score; mapped to a letter grade
A+/A/B+/B/C+/C/D/F per the bands defined in `driver_profile.py`.

## Audio cues

| Event | Sound |
|---|---|
| Mount | `garage_loop` continues |
| View switch (A or ◆) | `cursor_select` |
| Open a medal | `cursor_select` (stronger) + `medal_award` |
| Locked medal selected | `cancel` |

## Input map

| Input | Action |
|---|---|
| ▲ ▼ ◀ ▶ | Navigate radar (idle) or medal grid |
| A | Open medal grid → open medal detail |
| ◆ Start | Switch to evolution-chart sub-view |
| B | Back to garage hub (or back from sub-view) |

## Edge cases

- **Profile endpoint 404** (driver has no events yet) — show base card
  with all-zero radar; medal grid empty; coach line: *"First session
  yet, kid."*
- **Evolution returns 204** (< 5 sessions) — sub-view shows
  placeholder *"NEEDS 5 SESSIONS"* + coach line directs to TRACK
- **Medal newly earned this session** — pulses (1 Hz, scale 1.0 →
  1.05) until first A on it
- **Avatar slot 8 (locked)** — only shows on the picker; if somehow
  selected, fallback to slot 1
- **`prefers-reduced-motion`** — sprite breathing pauses; pulse stops

## Related

- [`03-garage-hub.md`](03-garage-hub.md) — entry point
- [`12-quest-log.md`](12-quest-log.md) — same medals list, different view
- [`21-driver-evolution.md`](21-driver-evolution.md) — full evolution chart
- [`03-character-bible.md`](../03-character-bible.md) — avatar slots
- [`04-state-architecture.md`](../04-state-architecture.md) — save schema
- [Bridge `/driver/<id>/evolution`](../../api.md#get-driveridevolutiontracksonoma)

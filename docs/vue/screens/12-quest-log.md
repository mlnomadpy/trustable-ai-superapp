# 12 — Quest Log

The "what am I working on" screen. Active session goals + medal grid.
Pokémon-Pokédex aesthetic — locked = silhouettes, unlocked = full
sprite + acquisition story.

## Purpose

Verb: **Plan.** Track active goals, browse the 40-medal taxonomy, see
what unlocks next.

## Wireframe

```
┌────────────────────────────────────────────────────────────┐
│ TAHA · LV.12 · ⚙ T-ROD                          15:32 PT   │
│ ─────────────────────────────────────────────────────────  │
│ QUEST LOG                                                  │
│                                                            │
│ ╔═ ACTIVE GOALS (THIS SESSION) ══════════════════════════╗ │
│ ║   ◐ APEX SPEED AT T7   82 → 84 km/h (target +3)         ║ │
│ ║   ✓ BREAK 1:48          1:46.8 ✓                        ║ │
│ ║   ✗ TRAIL EVERY ENTRY   4 of 11                         ║ │
│ ╚═══════════════════════════════════════════════════════╝ │
│                                                            │
│ ┌─ TAB ─────────────────────────────────────────────────┐ │
│ │ ▶ ALL  · BRONZE · SILVER · GOLD · PLATINUM · RAINBOW   │ │
│ └───────────────────────────────────────────────────────┘ │
│                                                            │
│ ╔═ MEDALS  14 / 40 ══════════════════════════════════════╗ │
│ ║                                                       ║ │
│ ║  ★  ★  ★  ★  ★  ?  ?  ?                                ║ │
│ ║  ★  ★  ★  ★  ★  ?  ?  ?                                ║ │
│ ║  ★  ★  ?  ★  ?  ?  ?  ?                                ║ │
│ ║  ?  ?  ?  ?  ?  ?  ?  ?                                ║ │
│ ║  ?  ?  ?  ?  ?  ?  ?  ?                                ║ │
│ ║                                                       ║ │
│ ║  ▶ Trail Brake Apprentice · 2026-04-23                 ║ │
│ ╚═══════════════════════════════════════════════════════╝ │
│                                                            │
│  A · DETAIL    ◀ ▶ TAB    B · GARAGE                       │
└────────────────────────────────────────────────────────────┘
```

## States

| State | Behaviour |
|---|---|
| `idle` | Active goals at top; medal grid below; cursor on first unlocked medal |
| `tab-switching` | Cursor wraps within active tier |
| `medal-detail` | A pressed: dialogue box describing acquisition criteria + earned-on date + session_id link |
| `goal-detail` | A on a goal: dialogue box with full progress + source-data link to analysis |

## Sprite usage

| Sprite | Where | Animation |
|---|---|---|
| `medal_*` (5 tiers) | Grid cells | 1 frame each; locked = silhouette outline only |
| `frame-card` | Active goals + medal grid | 9-slice |
| Cursor | On focused medal / goal | Bouncing |

## Medal taxonomy

40 total; grouped by tier:

| Tier | Count | Examples |
|---|---|---|
| Bronze | 5 | First Lap · First Sub-2:00 · First Trail Brake · etc. |
| Silver | 15 | Sub-1:50 · Trail Brake Apprentice · 5 Clean Laps · 50 Sessions · etc. |
| Gold | 15 | Sub-1:48 · Trail Brake Master · 100 Sessions · 11-Corner Mastery · etc. |
| Platinum | 4 | Sonoma Veteran · T-Rod's Approval · Bentley Student · Drill's Recruit |
| Rainbow | 1 | "All Four Coaches Approved" — only earnable by hitting Tier 5 affinity with all four unlockable coaches |

Full list in `pitwall-web-design.md` §"Medals."

## Vue component

```vue
<!-- pitwall-web/src/views/QuestLog.vue -->
<template>
  <div class="viewport">
    <StatusBar />
    <h1 class="font-title text-title">QUEST LOG</h1>

    <Frame frame-type="card">
      <h2 class="font-title text-small">ACTIVE GOALS</h2>
      <ActiveGoal v-for="g in session.goals" :key="g.id"
                  :goal="g"
                  :focused="focus.kind === 'goal' && focus.id === g.id" />
    </Frame>

    <TabPicker v-model="tab" :tabs="['ALL', 'BRONZE', 'SILVER', 'GOLD', 'PLATINUM', 'RAINBOW']" />

    <Frame frame-type="card">
      <h2 class="font-title text-small">MEDALS  {{ unlocked }} / 40</h2>
      <MedalGrid :medals="medalsForTab" :focus-id="focus.kind === 'medal' ? focus.id : null" />
      <p class="text-body">▶ {{ focusedMedal?.name ?? '—' }} · {{ focusedMedal?.awardedAt ?? '' }}</p>
    </Frame>

    <DialogueBox v-if="detail"
                 :coach-id="save.preferredCoach"
                 emotion="thumbsup"
                 :text="detail.acquisitionText"
                 @done="detail = null" />

    <HintBar :hints="['A · DETAIL', '◀ ▶ TAB', 'B · GARAGE']" />
  </div>
</template>
```

## Endpoints consumed

None directly. Reads from local save slot. The medal definitions are a
static JSON file (`/data/medals.json`); award timestamps come from the
save slot.

When viewing a medal earned in a specific session, A→A could open
`16-analysis-hub.md` for that session — but that's a post-MVP polish.

## Audio cues

| Event | Sound |
|---|---|
| Mount | `garage_loop` continues |
| Cursor move | `cursor_move` |
| Tab switch | `cursor_select` |
| A on unlocked medal | `cursor_select` (stronger) |
| A on locked medal | `cancel` |
| Active goal hits 100 % during session | (handled by HUD/Stage Clear, not here) |

## Input map

| Input | Action |
|---|---|
| ▲ ▼ ◀ ▶ | Move cursor (across goals AND medal grid; ▲ at top of medals jumps to goals) |
| A | Open detail |
| ◀ ▶ on tab strip | Switch tier filter |
| B | Back to garage hub |
| Start | Quick menu |

## Edge cases

- **No active goals** (player CONFIRMed pre-brief with 0 goals) — top
  panel shows: "NO GOALS THIS SESSION · FREE DRIVE"
- **Player at 0 medals** — grid all silhouettes; bottom hint: "EARN
  MEDALS BY DRIVING"
- **Rainbow medal hovered before earning the prerequisite Platinums** —
  acquisition text reveals the gating criteria so the player knows what
  to chase
- **Medal awarded mid-session** — when player returns to QUEST LOG,
  newly-unlocked medal pulses for one minute (then static)

## Related

- [`03-garage-hub.md`](03-garage-hub.md) — entry point
- [`07-pre-brief.md`](07-pre-brief.md) — where active goals are set
- [`10-stage-clear.md`](10-stage-clear.md) — where goals are scored
- [`04-trainer-card.md`](04-trainer-card.md) — alt medal view
- [`pitwall-web-design.md` § Medals](../../pitwall-web-design.md)

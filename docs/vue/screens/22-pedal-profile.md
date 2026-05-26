# 22 — Pedal Profile

The "diagnose your feet" screen. Per-session distribution across the
four canonical pedal states (throttle-only, brake-only, trail-brake,
coast). Per-corner mini-charts showing pattern by location.

## Purpose

Verb: **Diagnose your feet.** Find the silent killers — coasting too
much, never trail-braking, hesitation at corner entry.

## Wireframe

```
┌────────────────────────────────────────────────────────────┐
│ TAHA · LV.12 · ⚙ T-ROD                          15:32 PT   │
│ ─────────────────────────────────────────────────────────  │
│ PEDAL PROFILE · session 2026-04-29-1503                    │
│                                                            │
│ ╔═ SESSION DISTRIBUTION ══════════════════════════════════╗│
│ ║  ████████████████████████████░░░░░░░░░░░░░░░░░░          ║│
│ ║  THROTTLE 54.7%  BRAKE 15.0%  TRAIL 10.2%  COAST 20.1%   ║│
│ ║  thresholds: throttle > 5%, brake > 1.0 bar              ║│
│ ╚═══════════════════════════════════════════════════════╝ │
│                                                            │
│ ─── PER-CORNER PEDAL STATE ───                             │
│ T1   ▓▓▓▓░░░░  T7   ▓▓░░▒▒▒▒                              │
│ T2   ▓▓▓▓▓▓░░  T8   ▓▓▓▓░░░░                              │
│ T3   ▓▓░░▒▒▒▒  T9   ▓▓▓▓▓▓░░                              │
│ T4   ▓▓░░▒▒▒▒  T10  ▓▓▓▓▓▓▓░                              │
│ T5   ▓▓▓░░░░░  T11  ▓▓░░▒▒▒▒                              │
│ T6   ▓▓▓▓░░░░    legend: ▓ throttle ░ coast ▒ trail        │
│                                                            │
│ ─── THRESHOLDS ───                                         │
│  THROTTLE %  ◀  5  ▶                                       │
│  BRAKE bar   ◀ 1.0 ▶                                       │
│                                                            │
│  ◐ T-ROD: "20% coast — try trail-braking deeper into       │
│            T3a and T7. That's where the time is."          │
│                                                            │
│  ◀ ▶ THRESHOLD     B · BACK                                │
└────────────────────────────────────────────────────────────┘
```

## States

| State | Trigger | Behaviour |
|---|---|---|
| `loading` | Mount | Fetch `pedal_behavior` |
| `idle` | Loaded | Stacked bar + per-corner mini-charts; coach commentary auto-derived from band |
| `editing-threshold` | A on threshold slider | Live re-fetch with new params on debounced 300 ms |

## Coach commentary heuristics

Generated client-side from the data:

| Pattern | Coach line |
|---|---|
| Coast > 20 % | *"You're coasting one-fifth of the time. Trail-brake to corner entry instead of lifting early."* |
| Trail < 5 % | *"Less than 5 % trail-brake. Front tires aren't loaded — you're sliding."* |
| Trail 8–15 % | *"Solid trail-brake percentage for an intermediate."* |
| Trail > 15 % | *"That's pro-level trail. Don't lose it."* |
| Throttle > 60 % | *"You're committed. Good."* |
| Throttle < 40 % | *"Tentative on power. Find the exits."* |

## Sprite usage

| Sprite | Where | Animation |
|---|---|---|
| `frame-card` | Distribution + per-corner panels | 9-slice |
| `pedal_state_block_*` | Stacked bar + per-corner mini-charts | 1-frame each, 4 states colour-coded |
| `slider_track` / `slider_handle` | Threshold sliders | Static |
| Coach (selected) | Bottom-left | `idle` or `clipboard_check_*` (T-Rod row 7 frames) |

## Vue component

```vue
<!-- pitwall-web/src/views/PedalProfile.vue -->
<template>
  <div class="viewport">
    <StatusBar />
    <h1 class="font-title text-title">PEDAL PROFILE · {{ sidShort }}</h1>

    <Frame frame-type="card" class="distribution">
      <StackedBar :states="data.states"
                  :total="data.frame_count" />
      <p class="text-small">
        thresholds: throttle &gt; {{ data.thresholds.throttle_pct }}%,
        brake &gt; {{ data.thresholds.brake_bar }} bar
      </p>
    </Frame>

    <PerCornerPedalGrid :corners="cornerData" />

    <ThresholdSliders v-model:throttle="thrTh"
                      v-model:brake="brkTh"
                      @change="reload" />

    <DialogueBox v-if="coachLine"
                 :coach-id="save.preferredCoach"
                 :emotion="bandEmotion"
                 :text="coachLine" />

    <HintBar :hints="['◀ ▶ THRESHOLD', 'B · BACK']" />
  </div>
</template>

<script setup lang="ts">
async function reload() {
  const params = new URLSearchParams({
    throttle_th: String(thrTh.value),
    brake_th:    String(brkTh.value),
  })
  data.value = await fetch(
    `/api/session/${sid}/pedal_behavior?${params}`
  ).then(r => r.json())
}
</script>
```

## Endpoints consumed

| Endpoint | Use |
|---|---|
| `GET /session/<sid>/pedal_behavior?throttle_th=&brake_th=` | Single endpoint; thresholds drive per-state classification |

The per-corner mini-chart isn't directly returned — it's computed
client-side via DuckDB-Wasm against the cached Parquet for the
session, querying `telemetry` rows grouped by corner-distance bucket.

## Audio cues

| Event | Sound |
|---|---|
| Mount | `garage_loop` continues |
| Threshold slider tick | `cursor_move` |
| Reload completes after threshold change | brief sparkle (subtle) |
| Coach line: high-coast warning | `error_quiet` (one-shot) |

## Input map

| Input | Action |
|---|---|
| ▲ ▼ | Move focus between the two sliders |
| ◀ ▶ | Adjust focused slider (debounced reload) |
| A | (no-op; sliders are click-and-drag style with arrow nudges) |
| B | Back to analysis hub |

## Edge cases

- **Endpoint returns 0 frames** — distribution shows N/A; coach: *"No
  pedal data — drive a lap."*
- **All states < 1 %** (impossible — always some throttle) — likely
  data corruption; show ⚠ banner
- **Threshold values that classify all frames as "coast"** (player
  cranks throttle threshold to 99 %) — coach humour: *"Set realistic
  thresholds, kid."*
- **Per-corner mini-chart needs DuckDB-Wasm** — load lazily; while
  loading, mini-charts show "..." placeholder. Stacked bar always
  available.
- **Bridge offline** — fall back to cached Parquet via DuckDB-Wasm;
  cannot adjust thresholds without bridge (DuckDB recomputes locally —
  this works offline once the Parquet is cached!)

## Related

- [`16-analysis-hub.md`](16-analysis-hub.md) — entry point
- [`18-corner-mastery.md`](18-corner-mastery.md) — sibling
- [Bridge `/pedal_behavior`](../../api.md#get-sessionsidpedal_behavior)
- [`docs/api.md`](../../api.md) — pedal classifier states defined here

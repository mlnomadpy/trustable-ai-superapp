# 30 — SQL Console (Fullscreen)

Power-user surface. Monaco editor + DuckDB-Wasm + result table for
ad-hoc analytics over cached session Parquets. Reached from
`16-analysis-hub.md`'s ◆ Start.

## Purpose

Verb: **Hack.** Run arbitrary SQL against the cached telemetry.
Power users want answers their dashboard doesn't expose.

## Wireframe

```
┌────────────────────────────────────────────────────────────┐
│ TAHA · LV.12 · ⚙ T-ROD · ░ DUCKDB ON         15:32 PT       │
│ ─────────────────────────────────────────────────────────  │
│ SQL CONSOLE                                                │
│                                                            │
│ ┌──────────────────────────────────────────────────────┐    │
│ │ -- Where did I lose time at T7 best vs second-best   │    │
│ │ SELECT distance_m, speed_best * 3.6 AS speed_best,    │    │
│ │        speed_2nd * 3.6 AS speed_2nd,                   │    │
│ │        (speed_2nd - speed_best) * 3.6 AS delta_kmh    │    │
│ │ FROM compare_laps('sonoma-001', 7, 5)                 │    │
│ │ WHERE distance_m BETWEEN 1620 AND 1820                │    │
│ │ ORDER BY delta_kmh DESC LIMIT 10;█                    │    │
│ └──────────────────────────────────────────────────────┘    │
│                                                            │
│  ▶ RUN     ☆ SAVE     📂 LOAD     🗑 CLEAR                  │
│                                                            │
│ RESULT  10 rows · 0.4 s                                    │
│ ┌──────────────────────────────────────────────────────┐    │
│ │ distance_m │ speed_best │ speed_2nd │ delta_kmh       │    │
│ │ 1720       │ 92.1       │ 99.4      │ +7.3            │    │
│ │ 1715       │ 91.8       │ 98.2      │ +6.4            │    │
│ │ …                                                    │    │
│ └──────────────────────────────────────────────────────┘    │
│                                                            │
│  ┌──────┐                                                  │
│  │T-ROD │  (idle in corner, emotion = analyzing)           │
│  │analyz│                                                  │
│  └──────┘                                                  │
│                                                            │
│ A · RUN     B · BACK     ◆ EXAMPLES                        │
└────────────────────────────────────────────────────────────┘
```

## States

| State | Trigger | Behaviour |
|---|---|---|
| `editor-focused` | Mount | Cursor in Monaco; DuckDB-Wasm warming up if not already |
| `running` | RUN button or A | Query executes; coach `analyzing` |
| `result` | Query done | Result table populates; row count + duration shown |
| `error` | Query syntax error or runtime | Red highlight on Monaco line + error in result panel |
| `saving` | SAVE pressed | Prompt for query name; persist to save slot |
| `loading-saved` | LOAD pressed | List of saved queries; cursor picks one |

## Sprite usage

| Sprite | Where | Animation |
|---|---|---|
| Coach (`save.preferredCoach`) | Bottom-right, 48×48 | Emotion = `intense` (editor focused) → `analyzing` (running) → `encouraging` (result OK) → `concerned` (error) |
| `frame-default` | Editor + result panels | Static |
| `loading_dots` | While running | 6-frame spin |

## Vue component

```vue
<!-- pitwall-web/src/views/SqlConsoleFullscreen.vue -->
<template>
  <div class="viewport">
    <StatusBar :extra="`░ DUCKDB ${duck.ready ? 'ON' : 'BOOTING…'}`" />
    <h1 class="font-title text-title">SQL CONSOLE</h1>

    <MonacoEditor v-model="query" language="sql" :options="editorOpts" />

    <Toolbar>
      <Button @click="run" :loading="running">▶ RUN</Button>
      <Button @click="save">☆ SAVE</Button>
      <Button @click="load">📂 LOAD</Button>
      <Button @click="clear">🗑 CLEAR</Button>
    </Toolbar>

    <ResultPanel v-if="result" :result="result" />
    <ErrorPanel v-if="error"  :error="error" />

    <Sprite :sheet="save.preferredCoach" :animation="emotion" :variant="'idle'" />
    <HintBar :hints="hints" />
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useDuckDBStore } from '@/stores/duckdb'
import { useSavedQueries } from '@/lib/saved-queries'
const duck = useDuckDBStore()
const query  = ref(EXAMPLE_QUERIES[0].sql)
const result = ref<any | null>(null)
const error  = ref<string | null>(null)
const running = ref(false)

const emotion = computed(() => {
  if (running.value) return 'analyzing'
  if (error.value) return 'concerned'
  if (result.value) return 'encouraging'
  return 'intense'
})

async function run() {
  running.value = true; error.value = null
  try {
    result.value = await duck.query(query.value)
  } catch (e) {
    error.value = String(e); result.value = null
  } finally {
    running.value = false
  }
}
</script>
```

## Pre-loaded example queries

| Title | Use case |
|---|---|
| Last session lap times | one row per lap with sector splits |
| Where I lost time at T7 | speed-trace diff between best + 2nd-best |
| Top 5 laps across the season | best 5 laps by lap time |
| Trail-brake quality across corners | brake>5 bar AND |g_lat|>0.4 |
| Coast time per straight | time spent off-throttle on each named straight |
| Personal best evolution | best lap per session over time |

These ship as static defaults; user can SAVE additional queries per
save slot.

## Endpoints consumed

| Endpoint | Use |
|---|---|
| `GET /session/<sid>/export.parquet?table=telemetry` | Hydrates DuckDB-Wasm with the selected session's parquet |
| `GET /session/<sid>/export.parquet?table=telemetry_signals` | Tall-store parquet for ADR-015 signals |

After hydration: pure DuckDB-Wasm. No bridge calls per query.

## Audio cues

| Event | Sound |
|---|---|
| RUN | `cursor_select` |
| Query OK | `goal_complete` |
| Query error | `error_quiet` |
| SAVE | `cursor_select` |
| LOAD | `cursor_select` |

## Input map

| Input | Action |
|---|---|
| (Monaco focused) typing | Edit query |
| Cmd/Ctrl+Enter | Run |
| Esc | Blur Monaco |
| A (when blurred) | Run |
| B | Back to Analysis Hub |
| Start | Pause menu |
| ◆ | Open EXAMPLES dropdown |

## Edge cases

- **DuckDB-Wasm fails to load** — show error + fallback message; suggest
  using individual analytics screens (17-22) which call bridge directly
- **Query runs > 5 s** — show running indicator; user can abort via
  another RUN press (kills + restarts) or B
- **Query result > 10 000 rows** — paginate (1000 per page); export
  to CSV button surfaces in result toolbar
- **Saved queries quota** — capped at 20 per save slot; oldest evicted
  on overflow

## Related

- [`16-analysis-hub.md`](16-analysis-hub.md) — parent
- [`../04-state-architecture.md`](../04-state-architecture.md) — DuckDB-Wasm + OPFS
- [`../09-tech-stack.md`](../09-tech-stack.md) — Monaco editor lazy-loaded

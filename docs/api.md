# API — Pitwall HTTP Bridge

The Flask bridge is the single HTTP surface for the Vue PWA, the CAN
ingest pipeline, and any external client. It binds to `127.0.0.1:8765`
and is composed of blueprints under `src/pitwall/features/`.

Counts at the time of writing (grep `@bp.route`): **~70 routes** across
the eleven blueprints below.

Backend storage is **DuckDB on x86 laptops** and **SQLite on aarch64
Termux** (the duckdb wheel doesn't build for android). Both backends
expose the same `db_conn()` and `state.has_duckdb` API; the parquet
export path branches via `db_backend()`.

```
client (PWA / curl / Termux) ──► Flask :8765
                                    ├─ bp_core         (/health, /analyze)
                                    ├─ bp_cars         (/cars)
                                    ├─ bp_leaderboard  (/leaderboard)
                                    ├─ bp_diagnostics  (/diagnostics/…)
                                    ├─ session.bp_session   (CRUD + parquet + /session/<sid>/laps)
                                    ├─ session.bp_analysis  (lap-time, sectors, pedal…)
                                    ├─ session.bp_replay    (/session/replay/{start,stop,status})
                                    ├─ coaching.bp_coaching (brief/debrief/ask/traces/agents)
                                    ├─ telemetry.bp_signals (ADR-015 tall sink)
                                    ├─ track.bp_track       (markers, weather, elevation, evolution)
                                    └─ realtime.bp_realtime (SSE bus, spectator tokens)
```

CLI knobs and CAN flags live in `python -m pitwall --help`. The key ones:

| Flag                   | Default                          | Purpose                                       |
| ---------------------- | -------------------------------- | --------------------------------------------- |
| `--port`               | `8765`                           | bind port                                     |
| `--track`              | `data/tracks/sonoma.json`        | active track                                  |
| `--can-channel`        | unset                            | `/dev/ttyACM0` for live SLCAN                 |
| `--can-interface`      | `virtual`                        | `slcan` for the CANable on phone              |
| `--can-bitrate`        | `500000`                         | use `1000000` for the AiM MXP SmartyCam port  |
| `--can-car-config`     | unset                            | `data/cars/<id>.yaml`                         |
| `--can-dbc`            | `data/dbc/pitwall.dbc`           | DBC pack(s)                                   |
| `--simulate`           | off                              | built-in AiM-MXP synthetic generator          |
| `--simulate-speed`     | `1.0`                            | replay speed multiplier                       |
| `--simulate-lap-seconds` | `60`                           | one synthetic lap length                      |

---

## Diagnostics & meta

### `GET /health`

Liveness probe with engine + coach + CAN status.

```jsonc
{
  "status": "ok",
  "version": "2.1",
  "engine": "sonic_model",
  "coach": "litert" | "rule" | null,
  "track": "Sonoma Raceway",
  "duckdb": true,                  // also true for the SQLite-on-Termux backend
  "active_session_id": "…",
  "can": { "connected": true, "fps": 102.4, "frames_total": 18742 },
  "timestamp": "2026-05-26T17:00:00Z"
}
```

### `GET /diagnostics/llm_friction`

Recent LLM-friction rows from DuckDB (latency, fallback reasons).

### `GET /diagnostics/can`

CAN reader state: interface, channel, bitrate, frames/sec, last error.

---

## Cars

### `GET /cars`

List of every YAML in `data/cars/`. The currently-loaded config (per
`--can-car-config`) is flagged `loaded: true`. Per car, returns identity,
dash-logger spec, CAN bus, and a flattened channel inventory.

```jsonc
{
  "cars": [{
    "id": "bmw_e46_m3",
    "loaded": true,
    "make": "BMW", "model": "M3", "chassis": "E46", "year": 2003,
    "engine": "S54B32 (MSS54HP DME)",
    "dash_logger": { "make": "AiM", "model": "MXP",
                     "protocol": "AIM MXP SmartyCam Enhanced CAN Protocol v3.0",
                     "total_frames": 20, "total_channels": 66 },
    "can_bus": { "name": "SmartyCam output", "bitrate_bps": 1000000,
                 "frame_format": "MIXED", "id_width": 11 },
    "frame_count": 20, "channel_count": 66,
    "channels": [ { "name": "rpm", "frame_id": "0x420", "rate_hz": 50, "role": "engine" }, ... ]
  }],
  "loaded_id": "bmw_e46_m3",
  "cars_dir": "/.../data/cars"
}
```

**Status codes:** `200` always; `404` if the directory is missing.

---

## Sessions — CRUD

### `POST /session/start`

Open a session row. Auto-generates `session_id = <track-slug>-<UTC>` if
none is supplied.

```jsonc
// req
{ "driver": "Taha", "driver_level": "intermediate",
  "track": "Sonoma Raceway", "car": "BMW M3 (E46)", "note": "…" }

// 200
{ "started": true, "session_id": "sonoma-raceway-20260526-170015" }
```

### `POST /session/<sid>/end`

Stamp `ended_at = now()`. Idempotent.

### `GET /sessions?limit=50&active_only=false`

List newest-first; each row carries derived `lap_count` and `best_lap_s`.

### `GET /session/<sid>`

Full detail: session row + laps + last 50 coaching notes. `404` if unknown.

### `POST /session/reset`

Clear in-memory burst caches (doesn't touch DuckDB).

### `POST /session/import`

Parse a VBO from disk, create a `sessions` row, persist all frames into
`telemetry`. `409` if the session id already has rows.

```jsonc
// req
{ "vbo_path": "/abs/path.vbo", "driver": "Taha",
  "driver_level": "intermediate", "session_id": "optional" }

// 200
{ "session_id": "…", "n_frames": 8273, "duration_s": 1387.2,
  "distance_m": 95234.1, "vbo_source": "lap.vbo",
  "capabilities_count": 42 }
```

---

## Sessions — ingest

### `POST /session/<sid>/frames`

Append a batch of telemetry frames (wide canonicals).

### `POST /session/<sid>/frame`

Append one frame; returns the assigned `frame_idx`.

### `POST /session/<sid>/video_frames`

Append video frame metadata (for the post-session sync view).

### `POST /session/<sid>/signals`

ADR-015 tall sink: append `(signal_name, t, value)` tuples. Auto-registers
unknown signal names into `signal_registry`.

---

## Sessions — laps & exports

### `GET /session/<sid>/laps`

Lap envelope used by the PWA's Analysis-Hall lap-filter dropdown. Three
strategies tried in order: GPS return-to-start, distance-based slicing,
speed-stint fallback. First entry is always `{name: "Full session",
method: "all"}`.

```jsonc
{
  "laps": [
    { "name": "Full session", "t_start": 0, "t_end": 1387.2,
      "duration_s": 1387.2, "distance_m": 95234.1, "method": "all" },
    { "name": "Lap 1", "t_start": 0.2, "t_end": 110.5,
      "duration_s": 110.3, "distance_m": 4258, "method": "gps" }
  ],
  "track_length_m": 4258
}
```

**Status codes:** `200`, `404` (no rows for the session), `503` (no DB).

### `GET /session/<sid>/export.parquet?table=<name>`

Stream a parquet for DuckDB-wasm hydration in the PWA. Works on **both**
backends — the SQLite path streams pyarrow `RecordBatch`es of 50k rows.

Valid `table` values:

| `table`              | Contents                                                      |
| -------------------- | ------------------------------------------------------------- |
| `telemetry`          | wide canonicals (default)                                     |
| `telemetry_signals`  | ADR-015 tall sink; **includes `session_id` column**           |
| `signal_registry`    | signal catalog; stamped with the requested `session_id`       |
| `capabilities`       | per-session per-signal sample rate + useful-flag              |

Response headers: `Content-Type: application/octet-stream`,
`X-Pitwall-Session`, `X-Pitwall-Table`, `X-Pitwall-Rows`.

**Status codes:** `200`, `400` (bad table), `404` (no rows), `503` (no DB).

---

## Sessions — replay

Re-publishes a previously-recorded SQLite/DuckDB session to the live
`telemetry_bus`. The PWA can't tell the difference between live CAN and
replay — same SSE frame shape.

### `POST /session/replay/start`

```jsonc
// req
{ "source_session_id": "sonoma-…", "speed": 1.0, "loop": false }

// 200
{ "replay_id": "sonoma-…", "source_session_id": "sonoma-…",
  "total_frames": 8273, "est_duration_s": 1387.2,
  "speed": 1.0, "loop": false }
```

**Status codes:** `200`, `400` (missing id), `404` (source has no
telemetry), `409` (a replay is already running), `503`.

Side effect: if a live CAN reader is running, it's stopped first so the
two publishers don't fight over the same `session_id`.

### `POST /session/replay/stop`

```jsonc
{ "stopped": true, "frames_emitted": 4180 }
```

### `GET /session/replay/status`

```jsonc
// running
{ "running": true, "source_session_id": "…", "speed": 1.0,
  "loop": false, "frame_idx": 4180, "total_frames": 8273,
  "elapsed_s": 41.8, "est_remaining_s": 41.4, "frames_emitted": 4180 }

// idle
{ "running": false }
```

---

## Sessions — analytics

All under `/session/<sid>/…`, all `GET`. `404` when the session has no
telemetry. `400` when it has < 1 complete lap. See the math derivations
inline in `src/pitwall/features/session/bp_analysis.py`.

| Path                          | Returns                                                |
| ----------------------------- | ------------------------------------------------------ |
| `/scorecard`                  | A–F grade per corner                                   |
| `/highlights`                 | top 8 moments                                          |
| `/stats`                      | session aggregates                                     |
| `/friction_circle`            | gLat × gLong scatter                                   |
| `/hustle_map`                 | per-segment 100% throttle fraction                     |
| `/eob`                        | end-of-braking summary                                 |
| `/incidents`                  | flagged events                                         |
| `/map`                        | track + lap GPS overlay                                |
| `/sync`                       | telemetry × video at ±50 ms                            |
| `/clips`                      | video clip cuts                                        |
| `/lap_time_table`             | per-lap + S1/S2/S3 splits with best flags              |
| `/lap_time_distribution`      | Tukey box-plot stats                                   |
| `/ideal_lap`                  | Σ best sectors                                         |
| `/sector_times`               | thin S1/S2/S3 view                                     |
| `/pedal_behavior`             | 4-state (`throttle_only`, `brake_only`, `trail_brake`, `coast`) distribution; tunable via `?throttle_th=&brake_th=` |
| `/throttle_corner_box`        | per-corner throttle box-plot                           |
| `/corner_classification`      | low/med/high speed bands (`?low_max=&med_max=`)        |
| `/straight_line_speed`        | top speed per named straight                           |
| `/brake_acceleration`         | decel + exit-accel per corner                          |

---

## Coach

### `POST /analyze`

Hot-path burst coaching. Takes a telemetry summary, returns text + audio
cues + a rally-style pace note. Writes to `coaching_notes` when
`session_id` is present.

```jsonc
{
  "coaching": "Trail brake — hold pressure. …",
  "pace_note": "128, the Carousel, brake at just after the slight crest, downhill",
  "coach_source": "rule" | "litert" | "",
  "cues": [ … ],
  "burst_id": 7,
  "source": "sonic_model"
}
```

### `GET /coach/brief`

Pre-session narrative from LocalLLM (or templated fallback when LocalLLM
is unreachable).

### `POST /coach/debrief`

Post-session debrief; returns markdown narrative + emotion tag + the
contributing telemetry/highlights/pedagogy fragments.

### `GET /coach/concepts`

The 9 Bentley pedagogical concepts the coach can fire, with `description`
and `fires_when`.

### `POST /coach/ask`

Multi-turn driver Q&A via ADK. Requires `google-adk` installed —
otherwise `503 {"error": "ADK not available"}`. The optional `intent`
field bypasses the regex router (see `bp_coaching.py` for valid values).

```jsonc
// req
{ "driver_id": "taha", "session_id": "…",
  "question": "Why was lap 4 faster than lap 2?",
  "intent": "lap_comparison" }   // optional

// 200
{ "answer": "…", "emotion": "neutral",
  "qa_key": "taha:<sid>", "turn": 1 }
```

### `POST /coach/ask/stream`

SSE variant; tokens stream as `data: {"delta": "…"}\n\n` lines and a
final `{"done": true, "answer": "…", "emotion": "…"}`.

### `POST /coach/ask/end`

Flush the in-memory Q&A history into the `conversations` table.

### `GET /coach/agents`

ADK agent registry. **Always returns 200**; when ADK is missing the
shape is `{available: false, reason, agents: []}` so the PWA can render
an honest empty state.

### `GET /coach/traces?session_id=&limit=&since_ts=`

Poll recent `agent_traces` rows for the HUD's Agent-Trace drawer.
`limit` defaults to 200, capped at 1000. `since_ts` enables incremental
polling. **Always 200**; honest `{available: false, reason, traces: []}`
when ADK or DuckDB is missing.

### `POST /score`

Gemini-graded session score; `503` when `GEMINI_API_KEY` is unset.

### `GET /insights`

Aggregate ML/coaching insights across sessions.

### `GET /conversations/<sid>` · `GET /conversations/driver/<driver_id>`

Flushed Q&A history.

---

## Track

### `GET /track/markers`, `GET /track/danger_zones`, `GET /track/weather`

Read straight from the active track JSON. `/track/weather` is
parameterised on `?hour_local=` to pick a weather phase.

### `GET /track/<id>/elevation`

Elevation profile along the centerline of `data/tracks/<id>.json`,
sampled at `?step_m=` (default 10 m). `404` if the track JSON is missing;
`422` if it has no `reference_line`.

### `GET /markers?corner=&kind=`

Filterable view over the track's marker list.

### `GET /driver/<id>/evolution?track=sonoma`

Multi-session driver evolution time-series + summary deltas + biggest-
corner-gain heuristic. `204` if < 5 sessions for the requested track.

### `GET /session/<sid>/corners`

Per-corner aggregates: best pass + averages over all passes + optional
A–F grade + gold-standard delta (when `data/reference/sonoma_gold.json`
is loadable).

### `GET /driver/<id>/profile`

Event-sourced profile from `compute_profile()`.

### `GET /laps?session_id=&limit=20` · `POST /lap`

Read or write a lap row.

---

## Realtime

### `GET /cues/stream`

SSE of live coaching cues. Heartbeats every 15 s.

### `GET /telemetry/stream`

SSE of decoded telemetry frames published by either the CAN reader or
the replay thread (same shape).

### `GET /notifications`

SSE notification inbox (async messages, queued briefings).

### `POST /spectator/token` · `DELETE /spectator/token/<token>`

Mint and revoke time-limited tokens for remote pit-wall viewers.

---

## Signals (ADR-015 sink)

### `GET /signals/registry`

Full signal catalog — 54 seeded entries from `data/registry/obd2_pids.json`
plus any signals discovered at runtime.

### `GET /session/<sid>/capabilities`

Per-session signal inventory: which signals showed up, their mean Hz,
their useful-flag, and the coaches-enabled subset.

### `POST /session/<sid>/capabilities/recompute`

Trigger a recomputation (call after a bulk ingest).

### `GET /session/<sid>/signals`

Synchroniser: resample a list of signals onto a common axis. Query
params: `names`, `axis` (`time` | `distance`), `rate_hz`, `interp`
(`linear` | `previous`), `t_from`, `t_to`.

---

## Leaderboard

### `GET /leaderboard?track=&limit=`

Best lap per `(driver, car, track)` across all sessions. No fake rows —
returns `{entries: [], count: 0}` if nothing has been recorded yet.
Limit capped at 500. `503` when no DB backend is loaded.

```jsonc
{
  "entries": [
    { "rank": 1, "initials": "TB", "car": "BMW M3 (E46)",
      "track": "Sonoma Raceway", "time": "1:45.318" }
  ],
  "count": 1
}
```

---

## Backwards compatibility

- `/analyze` response is additive — `pace_note`, `coach_source` are new.
- `/coach/agents` and `/coach/traces` now always return 200; clients
  should branch on the `available` flag rather than HTTP status. This is
  the honest-empty-state pattern adopted across the bridge.
- `/session/<sid>/export.parquet` is identical on DuckDB and SQLite
  backends; the parquet path was rewritten for SQLite on Termux via
  pyarrow streaming.

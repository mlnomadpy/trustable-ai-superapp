# System Architecture

As-shipped, May 2026. Three tiers, all running on a single rooted Pixel 10
in cabin (or on a laptop for development). No cloud round-trips in the
coaching loop.

```
┌─────────────────────── Pixel 10 (Termux) ────────────────────────────┐
│                                                                       │
│  AiM MXP dash logger ─► CANable 2.0 (SLCAN 1 Mbit/s) ─► /dev/ttyACM0  │
│                                                  │                    │
│                                                  ▼                    │
│  ┌────────────────────────────────────────────────────────────────┐   │
│  │  Python bridge (Flask, src/pitwall/)                            │   │
│  │     can_reader  →  telemetry_bus  →  SSE  →  PWA                │   │
│  │     can_reader  →  SQLite (or DuckDB)  →  parquet  →  PWA       │   │
│  │     bp_replay   →  reads SQLite recording  →  telemetry_bus     │   │
│  │     bp_coaching →  LocalLLM (OpenAI-compat)  →  brief/debrief   │   │
│  └────────────────────────────────────────────────────────────────┘   │
│                                                                       │
│  ┌──────────────────────┐         ┌──────────────────────┐            │
│  │ LocalLLM APK         │◄────────┤ bridge (litert_coach)│            │
│  │ :8080 /v1/chat/…     │         │   POST /v1/chat/…    │            │
│  │ Gemma 4 E2B (LiteRT) │         └──────────────────────┘            │
│  └──────────────────────┘                                             │
│                                                                       │
│  ┌──────────────────────────────────────────────────────────────┐    │
│  │ PWA (Vue 3 + Pinia + DuckDB-wasm + Leaflet + Chart.js)       │    │
│  │   Chrome on the same phone, or any laptop via adb reverse    │    │
│  └──────────────────────────────────────────────────────────────┘    │
└───────────────────────────────────────────────────────────────────────┘
```

ADK paddock agents (`/coach/ask`, `/coach/agents`, `/coach/traces`) are
**opt-in** and currently **not installed on the phone**. Manylinux wheels
of `google-adk` don't match Termux's android wheel tag, and DNS in the
`adb su` exec context is too unreliable for `pip install`. The endpoints
honestly return `{available: false}` until that gap closes. On a laptop
with `pip install google-adk` they wire up automatically via
`state.has_adk`.

## Tier 1 — Bridge (Python)

`src/pitwall/` is a single Flask app composed of eleven blueprints
registered in `src/pitwall/__init__.py`. Each blueprint owns one domain:

| Blueprint                                     | Routes                                              |
| --------------------------------------------- | --------------------------------------------------- |
| `features/bp_core.py`                         | `/health`, `/analyze`                               |
| `features/bp_cars.py`                         | `/cars`                                             |
| `features/bp_leaderboard.py`                  | `/leaderboard`                                      |
| `features/bp_diagnostics.py`                  | `/diagnostics/*`                                    |
| `features/session/bp_session.py`              | session CRUD, ingest, parquet export, `/laps`       |
| `features/session/bp_analysis.py`             | lap-time table, sectors, pedal stats, …             |
| `features/session/bp_replay.py`               | `/session/replay/{start,stop,status}`               |
| `features/coaching/bp_coaching.py`            | brief / debrief / ask / traces / agents             |
| `features/telemetry/bp_signals.py`            | ADR-015 tall sink + capabilities                    |
| `features/track/bp_track.py`                  | markers, weather, elevation, evolution              |
| `features/realtime/bp_realtime.py`            | SSE bus + spectator tokens                          |

### Storage: SQLite on Termux, DuckDB on laptops

The DuckDB Python wheel doesn't build for aarch64 Termux. The bridge
detects this at boot and falls back to SQLite (the rest of the code
keeps using `db_conn()` / `state.has_duckdb`, which both backends
satisfy). Specific accommodations:

- **DDL** is SQLite-compatible: integer autoincrement sequences instead
  of `nextval()`, `TEXT` instead of `VARCHAR`, no `DEFAULT now()`.
- **Parquet export** branches on `db_backend()`: DuckDB uses native
  `COPY (…) TO 'file' (FORMAT PARQUET)`; SQLite streams rows through
  pyarrow in 50k-row `RecordBatch`es so the 3M-row tall sink doesn't
  materialise as a Python list.
- `pyarrow` is installed via Termux `pkg` (not pip) and exposed to the
  venv via a `termux_system.pth` shim. Same for `numpy`. See
  `deploy/phone/10-termux-packages.sh` and `30-python-deps.sh`.

### Telemetry path: live CAN, replay, and simulator

Three publishers, one bus, same SSE shape downstream:

1. **Live CAN.** `features/telemetry/can_reader.py` opens the CANable
   over SLCAN at 1 Mbit/s, decodes AiM MXP SmartyCam v3.0 frames via
   `data/cars/bmw_e46_m3.yaml` + `data/dbc/pitwall.dbc`, and flushes
   wide canonicals into `telemetry` every 100 ms. Tall (signal-name)
   samples land in `telemetry_signals` via the ADR-015 sink.
2. **Replay** (`bp_replay.py`). Reads a recorded session's `telemetry`
   and `telemetry_signals` tables, walks them in timestamp order, and
   republishes to `telemetry_bus` at `?speed=N` cadence (optionally
   looping). Used when there's no live CAN plugged in. Stops any
   running CAN reader on start so the two don't race.
3. **Simulator** (`--simulate`). In-process AiM MXP synthetic generator
   with configurable `--simulate-speed` and `--simulate-lap-seconds`.
   Mutually exclusive with live CAN.

### Coach path

- **Hot path** (`/analyze`): `sonic_model` + `RuleCoach` canonical
  phrases. No LLM. Sub-50 ms.
- **Warm path** (`/coach/brief`, `/coach/debrief`): `litert_coach.py`
  calls LocalLLM's OpenAI-compatible endpoint at
  `http://localhost:8080/v1/chat/completions`. The `_templated_pre_brief`
  templated fallback was removed in the no-fake-fallbacks sweep — when
  LocalLLM is unreachable, the response is honest.
- **Paddock** (`/coach/ask`): 18 ADK agents — only when `google-adk` is
  importable. Returns `available: false` on the phone today.

## Tier 2 — PWA (Vue)

`src/pwa/` is a Vue 3 + Pinia PWA built with Vite 8. 27 pages under
`src/pages/`, plus widgets, entities (Pinia stores), and shared lib.
Built `dist/` is served by the bridge for the phone deployment.

Notable pieces of this sprint:

- **Analysis Hall** (`pages/analysis-hub/AnalysisHub.vue`) — tabbed
  workbench with six tabs (Overview / Telemetry / Systems / IMU /
  Signals / Modules). Each tab lazy-loads its chart bundle. Data flow:
  bridge → parquet → DuckDB-wasm in OPFS → SQL → Chart.js + Leaflet.
- **DuckDB-wasm** worker is bundled same-origin (no jsdelivr CDN, no
  CORS prompt at boot).
- **On-Track HUD** (`pages/on-track-hud/`) — cockpit-minimal redesign.
  - `useLapDerivation` composable derives `lap_number` client-side from
    cumulative `distance / track_length_m` (the bridge SSE doesn't emit
    `lap_number`).
  - `AgentTraceDrawer.vue` (toggled by `T`) polls `/coach/traces`.
  - `CoachVoiceButton` FAB (toggled by `M`) wires Web Speech API STT +
    `speechSynthesis` TTS to a conversational loop.
  - WAITING-FOR-DATA overlay if no SSE frame within a 3 s grace window.
- **Eight pages newly tabbed** for Pixel 10 landscape: Settings,
  CarSetup, Calibration, HardwareDetail, PitStall, QuestLog, EndOfDay,
  PreBrief, LivePitWall.
- **InstallPrompt + FullscreenToggle** — sticky banner from
  `beforeinstallprompt`, fullscreen persisted via the
  `fullscreen-toggle` widget.
- **PWA icons** — `public/icons/icon-{192,512}.png`,
  `icon-maskable-{192,512}.png`, `apple-touch-icon-180.png`. Manifest
  config is in `vite.config.ts`.

### No-fake-fallback sweep

Templated mock data was purged in this sprint. The user-visible effect:
empty stores and offline banners look "empty" instead of "fake-full".

- `entities/quest/model/medalStore.ts` — honest empty state.
- `entities/session/model/telemetryStore.ts` — `startSimulation()`
  (Math.sin/cos fake frames) removed.
- `pages/garage-hub/CarSetup.vue` — wired to real `/cars`.
- `pages/track-atlas/TrackAtlas.vue` — wired to real
  `/track/markers`, `/track/danger_zones`, `/track/elevation`,
  `/track/weather`.
- `pages/lap-times-hall/LapTimesHall.vue` — type-drift fixed.

## Tier 3 — LocalLLM (sibling APK)

Pitwall doesn't ship an LLM. It expects [LocalLLM](https://github.com/mlnomadpy/localllm)
(or any OpenAI-compatible server) to be running on `http://localhost:8080/v1`.
The bridge talks to it via `litert_coach.py` for brief/debrief and via
ADK's `LiteLlm` wrapper for paddock Q&A (when ADK is installed).

Environment knobs (read by `litert_coach.py` and the ADK wiring):

| Var                          | Default                       |
| ---------------------------- | ----------------------------- |
| `PITWALL_ADK_OPENAI_URL`     | `http://localhost:8080/v1`    |
| `PITWALL_ADK_OPENAI_MODEL`   | `gemma-4-e2b`                 |
| `PITWALL_ADK_OPENAI_API_KEY` | `local`                       |

## Deployment ladder (rooted Pixel 10)

`deploy/phone/` is a numbered shell-script ladder (00 → 99) plus
`_common.sh` (shared helpers) and `status.sh` (probe). Each step is
idempotent and prints a clear `OK` / `FAIL` marker. See
`deploy/phone/README.md` for the per-step contract.

Mode selection in `70-start-bridge.sh`:

- `SIM=1` → built-in synthetic AiM MXP generator
- `NO_CAN=1` → start in replay-only mode
- otherwise → auto-detect `/dev/ttyACM*` for live CAN

## What this architecture is not

- **Not** cloud-attached. No hosted LLM is ever called. The driver gets
  the same coaching with the cell radio off.
- **Not** a Garmin Catalyst clone. There is a real-time loop, not just
  post-session review.
- **Not** dependent on DuckDB. SQLite-on-Termux is a first-class backend.
- **Not** dependent on ADK. The paddock Q&A is an extra tier; everything
  else works without it.

See [`docs/api.md`](api.md) for the endpoint contract and
[`docs/hardware.md`](hardware.md) for the in-car wiring.

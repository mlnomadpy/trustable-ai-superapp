# Changelog

All notable changes to Pitwall. The architecture decisions live in
[`docs/adr/`](docs/adr/index.md); this file is the chronological log
of what shipped when.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versions are dates because the project is pre-release.

## [Unreleased]

### Planned

- `pitwall-web` Vue PWA scaffold + first paddock screens — see
  [`docs/pitwall-web-design.md`](docs/pitwall-web-design.md)
- Video × telemetry sync (deferred from 2026-04-29 work) —
  `--video` flag on `tools/can_simulator.py` + byte-range MP4 serving
  on the bridge
- Live `/cues/stream` SSE endpoint for the PWA on-track HUD
- DBC packs for additional cars (Subaru GR86 next)
- May 23, 2026 — Sonoma Raceway field test

## [2026-04-29]

### Added — CAN-USB pivot ([ADR-016](docs/adr/016-can-bus-ingest-and-frontend-pivot.md))

- `data/dbc/pitwall.dbc` — synthetic CAN database, 9 messages, 29 signals
  covering the 11 wide-table canonicals + key ADR-015 sink seeds
- `tools/can_reader.py` — `python-can` consumer that decodes via
  `cantools` and sinks into both wide table + tall sink. Threadable
  + standalone CLI.
- `tools/can_simulator.py` — VBO replay or synthetic-laps producer
  emitting CAN frames over a `python-can` Bus. Configurable speed
  multiplier; optional sink-signal injection (oil temp curve, 1 Hz
  TPMS, etc.)
- `tests/test_can_pipeline.py` — 6 round-trip tests on
  `interface='virtual'`. No kernel modules, no permissions.
- Bridge `--can-channel` family of flags: `--can-interface`,
  `--can-channel`, `--can-bitrate`, `--can-dbc`, `--can-session-id`,
  `--can-flush-ms`. Reader thread spawns at startup; clean shutdown.

### Added — Termux foreground service

- `deploy/termux/` — drop-in install package: `runit` service
  scripts, Termux:Boot hook, svlogd log rotation, full `INSTALL.md`
  with Doze-survival verification.

### Added — Universal Telemetry Sink phases ([ADR-015](docs/adr/015-universal-telemetry-sink.md))

- Phase 1 — `signal_registry`, `telemetry_signals`, `session_capabilities`
  tables; 54-entry seed at `data/registry/obd2_pids.json`;
  `GET /signals/registry` endpoint
- Phase 2 — `POST /session/<sid>/signals` batch ingest with
  auto-discovery of novel signal names; `_compute_capabilities`
- Phase 3 — `GET /session/<sid>/capabilities` envelope;
  `GET /session/<sid>/signals` synchroniser with ASOF + lerp
  interpolation; axis switching (gps / lap_distance / signal name);
  rate_hz uniform-grid resampling
- Phase 4 — `@coach_rule(requires=, min_rates=)` decorator in
  `coach_engine.py`; `evaluate_coach_gating()` populating
  `coaches_available` / `coaches_disabled` in the capabilities
  envelope. Five built-in rules registered.

### Added — Phase 6 analysis endpoints

11 endpoints, all backed by code + tests:

- `GET /session/<sid>/lap_time_table`
- `GET /session/<sid>/lap_time_distribution`
- `GET /session/<sid>/ideal_lap`
- `GET /session/<sid>/sector_times`
- `GET /session/<sid>/pedal_behavior`
- `GET /session/<sid>/throttle_corner_box`
- `GET /session/<sid>/corner_classification`
- `GET /session/<sid>/straight_line_speed`
- `GET /session/<sid>/brake_acceleration`
- `GET /track/<id>/elevation`
- `GET /driver/<id>/evolution`

Plus the supporting `_detect_laps()` (cumulative-distance + GPS-perpendicular
fallback) and `_lap_sectors()` helpers.

### Added — Session lifecycle endpoints

- `POST /session/start`
- `POST /session/<sid>/end`
- `GET /sessions?limit=&active_only=`
- `GET /session/<sid>` (full detail with laps + notes)

### Added — Roadmap endpoints

- `POST /session/<sid>/frame` — single-frame append
- `GET /session/<sid>/corners` — per-corner aggregates with optional
  gold-standard delta + A–F grade
- `POST /score` — Gemini-graded session score (0–100 + one-sentence why)
- `GET /markers?corner=&kind=` — filterable marker view
- `GET /coach/concepts` — 9 Bentley pedagogical concepts

### Added — Documentation

- [ADR-015](docs/adr/015-universal-telemetry-sink.md) accepted (was Proposed)
- [ADR-016](docs/adr/016-can-bus-ingest-and-frontend-pivot.md) accepted
- [`docs/pitwall-web-design.md`](docs/pitwall-web-design.md) — full GBA-style
  UX design spec for the upcoming Vue PWA
- [`docs/ux.md`](docs/ux.md) expanded from 153 → 505 lines with design
  principles, user journey, accessibility, failure modes, hardware setup,
  trust UX
- `pymdownx.arithmatex` + MathJax wired in `mkdocs.yml`; math now renders

### Added — Tooling

- `tools/smoke_test_endpoints.py` — end-to-end test against a real
  Sonoma VBO (8273 frames, 6.83 cumulative laps); 51 assertions

### Fixed

- `laps.id` was `NOT NULL` with no default in the bridge schema —
  `POST /lap` would have crashed in production. Added
  `DEFAULT nextval('laps_id_seq')`.
- Lap detection on real Racelogic cumulative-distance VBOs was
  finding zero laps (only worked for synthetic per-lap data).
  Added cumulative-distance strategy as primary; GPS-perpendicular
  crossing as fallback with 50 m radial tolerance and out-lap/in-lap
  discard.

### Stats

- Bridge routes: 30 → **50**
- Tests: 213 → **289 passed, 0 skipped**
- Smoke assertions: **51 passed, 0 failed** against real VBO
- ADRs: 14 → **16**, both new ones Accepted

## [2026-04-28]

### Added

- Initial Python HTTP bridge (`tools/pitwall_bridge.py`) — Flask app
  on `127.0.0.1:8765` wrapping `sonic_model.compute_cues`. Initial
  endpoints: `/health`, `/analyze`, `/laps`, `/lap`.
- DuckDB persistence at `tools/pitwall_sessions.duckdb`.
- Coach engine adapter ([ADR-012](docs/adr/012-coach-engine-adapter.md))
  with `RuleCoach` + `LitertCoach` (Gemma 4 E2B via MediaPipe Genai).
- Frontend / backend boundary recorded
  ([ADR-013](docs/adr/013-frontend-backend-boundary.md)) — backend
  owns LLM logic + system prompts.
- Sonoma-as-the-product ([ADR-014](docs/adr/014-sonoma-as-the-product.md))
  — three-mode coaching + analysis pipeline + visualisation bundles, all
  Sonoma-hardcoded.
- Phase 6 endpoint specs documented in `docs/api.md` (implementation
  followed 2026-04-29).

## [2026-04 and earlier]

ADRs 001–011 — see [`docs/adr/index.md`](docs/adr/index.md):

- 001 — Confidence-annotated telemetry frame
- 002 — Split-brain architecture with message arbiter
- 003 — Gemma 4 as edge LLM
- 004 — Antigravity store-and-forward pipeline
- 005 — Pedagogical vector retrieval (Ross Bentley curriculum)
- 006 — Sensor fusion for Racelogic + OBDLink
- 007 — Event-sourced driver profile
- 008 — Pedagogical vector regression testing
- 009 — Graceful degradation protocol
- 010 — HTTP bridge as warm-path tier 1
- 011 — Named-marker schema for Sonoma corner references

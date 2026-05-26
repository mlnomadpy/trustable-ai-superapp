# Pitwall Server Improvement Plan

**Author:** Taha Bouhsine
**Date:** 2026-05-15
**Companion:** `docs/reports/server-audit-termux.md` (findings)
**Branch:** `aim-mxp-yaml-pipeline`

Translates the audit findings into an executable, phased roadmap.
Each phase is a self-contained unit of work with a goal, a list of
deliverables with effort estimates, an exit criterion that can be
tested, and an explicit answer to "what breaks if we skip this phase
and try to ship?"

The sequencing favours **derisking the next demo / track day first**,
then operability, then scale, then security. Phases 1–3 should land
**before any unsupervised on-car run**; phases 4–6 can ship
incrementally afterwards.

---

## Phase 0 — Already shipped on this branch

Context for what follows. None of this needs work; listed so we don't
redo it.

| Item | Where | Notes |
|---|---|---|
| YAML-driven per-car pipeline | `data/cars/bmw_e46_m3.yaml`, `formula.py`, `car_config.py` | 22 signal pipelines, 2 cross-derived, 1 method, AST-allowlisted expressions |
| Shared formula library | `data/formulas/standard.yaml` | 29 formulas, zero-Python additions for new conversions |
| AiM MXP synthetic simulator | `src/simulator/aim_mxp_simulator.py` + `--simulate` flag | Headless dev/test without a real car |
| DB corruption recovery | `db.py::reset_live_session` | Rotates `.corrupted-<ts>` aside, recreates fresh schema, re-seeds registry |
| Lazy capabilities | `bp_signals.py::session_capabilities_get` | `/session/<sid>/capabilities` works for `_live` without explicit recompute |
| Hardware spec docs | `docs/reports/aim-mxp-can-validation.tex/.pdf`, `data/cars/bmw_e46_m3.yaml` | 29/29 channel math validated against live bus |
| DuckDB out of git | `.gitignore`, `data/pitwall_sessions.duckdb` untracked | Each clone starts with a fresh DB |

---

## Phase 1 — Stop the bridge being its own worst enemy

**Goal:** Make `python -m pitwall` survive an unclean shutdown without
poisoning state, deadlocking, or dropping in-flight HTTP requests.

**Why first:** Every other improvement assumes the bridge can boot
reliably. We just spent an hour rotating a corrupted DB during
testing; that should not happen twice.

**Total budget:** 2 hours.

### Items

| # | Title | Cost | File |
|---|---|---|---|
| 1.1 | SIGTERM + SIGINT handler → `can_reader.stop()` → `simulator.stop()` → DuckDB `CHECKPOINT;` → `sys.exit(0)` | 30 min | `src/pitwall/__main__.py` |
| 1.2 | Mirror the same body in an `atexit` handler (belt + suspenders) | 5 min | `src/pitwall/__main__.py` |
| 1.3 | `state.db_lock = threading.Lock()` → `threading.RLock()`; same for `burst_lock`, `bundles_lock` (`qa_lock` was removed entirely in PR #30) | 5 min | `src/pitwall/state.py` — **shipped: locks are now `RLock()` at lines 57/66/70** |
| 1.4 | Swap Flask dev server for **waitress**: `waitress.serve(app, host="127.0.0.1", port=port, threads=8, channel_timeout=30)` | 1 h | `src/pitwall/__main__.py:168` + `pyproject.toml` deps |
| 1.5 | Add `--dev` flag that keeps the Flask dev server path for local debugging | 10 min | `src/pitwall/__main__.py` |
| 1.6 | Release Termux wake-lock on graceful stop via `subprocess.run(["termux-wake-unlock"], check=False)` | 5 min | shutdown handler from 1.1 |

### Exit criteria

- `kill -TERM <pid>` followed by a fresh start produces **zero** `FATAL:
  Failed to delete all rows from index` errors, with no `.corrupted-*`
  file generated.
- Starting + stopping `--simulate` 10 times in a row leaves the DB
  size stable (no zombie WAL entries).
- The bridge boot log no longer prints `WARNING: This is a development
  server.`

### Risk if skipped

Already realised today: one rough kill produces an invalidated DB. The
recovery path in `db.py` masks the symptom but loses all prior
session data when it fires.

---

## Phase 2 — Make a stock Pixel actually able to read CAN

**Goal:** Replace the documentation lie that `/dev/ttyACM0` exists on
non-rooted Termux with a code path that genuinely works.

**Why before phase 3:** Until this lands, no real-car deployment is
possible; everything else is academic. `--simulate` is the only
working path today on a stock Pixel.

**Total budget:** 1 working day.

### Items

| # | Title | Cost | File |
|---|---|---|---|
| 2.1 | Add `--can-fd <int>` argument to `CanReader` + `__main__` that accepts a pre-opened USB file descriptor | 1 h | `src/pitwall/features/telemetry/can_reader.py`, `src/pitwall/__main__.py` |
| 2.2 | Wrap python-can's `slcan` interface so it can use the FD (python-can's `SerialBus` accepts a `serial.Serial` constructed from the FD via `fdopen`) | 2 h | new helper in `can_reader.py` |
| 2.3 | Write a Termux:Boot shim script that runs `termux-usb -e <handoff.sh> <vendor:product>` and `exec python -m pitwall --can-fd "$1"` | 1 h | `deploy/termux/boot/start-pitwall-with-can` |
| 2.4 | Update `deploy/termux/INSTALL.md`: explicit "USB host on non-rooted Android" section + the three paths (termux-usb FD handoff, root + udev, separate Android app forwarding) with the FD handoff marked recommended | 1 h | docs |
| 2.5 | Add `--no-car-config` + `--simulate` to INSTALL.md as the "no-car smoke-test" path so new operators have a working bridge from minute zero | 30 min | docs |
| 2.6 | Open-on-disconnect retry: outer loop in `_reader_loop` with 1s → 2s → 5s → 10s exponential backoff; reset `_latest` cache on reconnect; surface in `state()` for the PWA | 1 h | `can_reader.py:355-369` |
| 2.7 | `frames_dropped` counter exposed via `state()` (incremented when python-can's RX buffer overflows) | 30 min | `can_reader.py` |

### Exit criteria

- A fresh Pixel 10 with Termux + Termux:API + the CANable plugged in
  goes from `git clone` to "bridge ingesting real CAN frames" in
  **under 10 minutes**, following only INSTALL.md.
- Unplugging the CANable for 5 s and plugging it back in resumes
  ingest within 5 s without bridge restart, and the
  `/signals/registry?include_can_state=true` snapshot reflects the
  re-connection.

### Risk if skipped

No prod track day. We've already validated the upstream chain (CAN
bus on the Mac), but the Pixel-side ingest path **does not exist**.

---

## Phase 3 — Operability for an unattended bridge

**Goal:** When the bridge runs unattended in the car for hours, we
can answer "is anything wrong?" from logs alone, and the bridge
recovers from common transient failures without manual intervention.

**Total budget:** 1 working day.

### Items

| # | Title | Cost | File |
|---|---|---|---|
| 3.1 | Structured logging: top-of-`main()` `logging.basicConfig` with `%(asctime)s %(levelname)s %(name)s %(message)s`; replace `print(...)` calls throughout `__main__.py` and blueprints; add `--log-level` CLI | 1 h | `__main__.py`, all `bp_*.py` |
| 3.2 | Cap `/session/<sid>/signals` window: reject if `rate_hz × (t_to − t_from) > 10_000` with HTTP 413 and a "narrow your window" message; default to last 60s if neither bound given | 15 min | `bp_signals.py:111-123` |
| 3.3 | Periodic RSS log line every 60s; flag if growth > 10 MB/min | 30 min | `__main__.py` background task |
| 3.4 | LocalLLM fast health probe: `HEAD /v1/models` with 2s timeout before every `/coach/brief` call; on failure return rules-only response immediately, log warn, expose `state.litert_up` in `/health` | 1 h | `src/pitwall/features/coaching/litert_coach.py` (was in monolithic `coach_engine.py` pre PR #30) |
| 3.5 | Watchdog thread that detects a stuck reader: if `frames_per_second == 0` AND `last_frame_age_s > 30` AND `loaded == True`, log error and restart the reader | 1 h | `__main__.py` |
| 3.6 | `_latest` and `_tall_id_cache` bounded to 1000 entries each (LRU via `collections.OrderedDict`) | 15 min | `can_reader.py` |
| 3.7 | `/health` extended with `can.fps`, `can.connected`, `litert.up`, `simulator.running`, `wide_rows.last_5min`, `tall_rows.last_5min` — a single curl tells the operator everything | 30 min | `__init__.py` or `bp_diagnostics.py` |

### Exit criteria

- A 4-hour idle simulator run produces a clean log with no errors,
  bounded RSS, and a `/health` snapshot the on-call can read in 5
  seconds.
- Killing LocalLLM mid-session causes coach responses to fall back to
  rules instantly (no 30s stalls); `/health` flips `litert.up=false`.
- Unplugging the CANable mid-session triggers the watchdog within
  35 s and reconnect succeeds (combines with item 2.6).

### Risk if skipped

We won't know the bridge has degraded until the driver complains.

---

## Phase 4 — Scale & disk hygiene

**Goal:** Bridge survives a full season of track days on a single
device without manual cleanup.

**Total budget:** 2 working days.

### Items

| # | Title | Cost | File |
|---|---|---|---|
| 4.1 | Session archive: POST `/session/<sid>/end` exports session rows to `archive/<sid>.duckdb`, DELETEs them from live DB, `VACUUM`s | 3 h | `db.py`, new blueprint endpoint |
| 4.2 | Automatic archive on session-end (lap detector EOL, or 30 min of zero frames) | 2 h | `db.py`, `bp_session.py` |
| 4.3 | Daily `VACUUM` at 03:00 local time via a small scheduler thread (only when `frames_per_second < 1`, so we never block live ingest) | 1 h | `__main__.py` |
| 4.4 | Per-thread DuckDB read connection via `threading.local`; one shared writer connection owned by the CAN reader thread; HTTP endpoints get read-only connections | 3 h | `db.py:32` |
| 4.5 | Migrate the few HTTP endpoints that do `INSERT`/`DELETE` (notes, capabilities recompute) to queue work to the writer via a small queue, returning 202 Accepted | 2 h | `bp_*.py` writers |

### Exit criteria

- After 50 simulated sessions, the live `pitwall_sessions.duckdb` is
  under 100 MB; older sessions live in `archive/`.
- `/session/<sid>/signals` 5 Hz polling load test: 100 RPS for 5
  minutes against the bridge with the simulator running stays under
  150 ms p99 latency.

### Risk if skipped

Slow degradation: disk fills, queries slow down, eventually the
phone's Doze killer or filesystem corruption finishes the job.

---

## Phase 5 — Security hardening

**Goal:** Bridge is safe even if other untrusted apps run on the same
phone, and if the phone itself is lost.

**Total budget:** 1 working day.

### Items

| # | Title | Cost | File |
|---|---|---|---|
| 5.1 | Bearer token auth: `PITWALL_TOKEN` env var; if set, all requests must include `X-Pitwall-Token`; `/health` exempt | 1 h | `__init__.py` (Flask `before_request`) |
| 5.2 | Rate limit `/coach/*` and `/session/*/signals` at e.g. 20 RPS per source | 1 h | `__init__.py` (small token-bucket middleware) |
| 5.3 | Verify Android disk encryption is on at install time (`getprop ro.crypto.state`) and log a warning to INSTALL if it's `unencrypted` | 30 min | install script |
| 5.4 | Cap request body size (1 MB) and `Content-Type` allow-list (`application/json` only on POSTs) | 15 min | `__init__.py` |
| 5.5 | Audit CORS: drop `CORS(app)` (allow-all) → `CORS(app, origins=["http://localhost:*"])` so the bind-to-127.0.0.1 promise extends to the browser layer | 15 min | `__init__.py:49` |
| 5.6 | Document the threat model + the assumptions we make (single-user device, no remote exposure, Android FDE) | 30 min | new `docs/security.md` |

### Exit criteria

- A second app on the phone calling `/coach/brief` without the token
  receives 401.
- Loading 1000 requests/second against `/coach/ask` produces 429s,
  not OOM.

### Risk if skipped

Today the surface is benign (single-user device), but the first time
we ship a partner app or expose `adb forward` to a workstation, the
attack surface opens.

---

## Phase 6 — Hot-path & latency tuning

**Goal:** Sustain the real AiM MXP rate (350 fps peak) on the Pixel
without dropping frames or smearing coaching latency.

**Total budget:** 2 working days (mostly profiling + small fixes).

### Items

| # | Title | Cost | File |
|---|---|---|---|
| 6.1 | `cProfile` capture of `_consume` over a 60-s 350 fps simulator run; flag anything > 100 µs/frame | 2 h | profiling |
| 6.2 | Cross-derived dedupe: skip evaluating a `derived:` entry if all `bind:` inputs have identical values to last call | 1 h | `car_config.py` |
| 6.3 | Lazy-load ADK agents: keep only the active "intent" agent in RAM; spawn others on demand | 4 h | `src/pitwall/features/coaching/adk_agents.py` |
| 6.4 | Batch tall-store inserts across multiple frames (50 ms window) instead of per-frame `executemany` | 2 h | `can_reader.py` |
| 6.5 | Move DuckDB writes into a dedicated thread fed by a `queue.Queue` from the reader; reader never blocks on the DB lock | 4 h | `can_reader.py` |
| 6.6 | Re-measure all numbers after each change; commit a `docs/reports/perf-baseline.md` with the before/after | 1 h | docs |

### Exit criteria

- At 350 fps synthetic load, `frames_dropped == 0` over 10 minutes.
- Coach round-trip latency (CAN frame → cue arriving in PWA) under
  100 ms p95.

### Risk if skipped

Bridge keeps up at idle / pit-lane rates (the conditions we've
tested), but might miss frames at hot-lap fast-IMU rates on Pixel CPU
under thermal throttle.

---

## Cross-phase: testing & CI

Items applicable across phases; should run in CI continuously.

| # | Title | Phase |
|---|---|---|
| C.1 | Rebuild the broken `tests/features/telemetry/test_can_pipeline.py` against the current AiM MXP DBC; today it expects messages that don't exist | 1 |
| C.2 | Smoke test: `pytest -k simulate` boots the bridge with `--simulate`, hits `/health`, queries `/session/_live/capabilities`, validates pipeline-derived signals are present | 1 |
| C.3 | Add a "kill-mid-write" test: `--simulate` for 5 s, `SIGKILL -9`, restart, assert no `.corrupted-*` file | 4 |
| C.4 | Long-run nightly: 4-hour `--simulate`, assert RSS bounded, no errors in log | 3 |
| C.5 | CAN reconnect test: start `--simulate`, swap virtual channels mid-run, assert reconnect | 2 |

---

## Sequencing summary

```
NOW ──► Phase 1 (2h)  ─► Phase 2 (1d)  ─► Phase 3 (1d)  ─► [first track day]
                                                              │
                                                              ▼
                          Phase 4 (2d) ─► Phase 5 (1d) ─► Phase 6 (2d)
```

**Phase 1 unblocks everything** — required hygiene; ≤2 h.
**Phase 2 unblocks the first track day** — required to read CAN on a stock Pixel.
**Phase 3 makes the first track day not panicky** — operability + observability.
**Phases 4–6 are the "long-term ownership" investment**: ship them incrementally as track-day learnings come in.

**Total to "ready for first track day": ~2.25 working days.**

The audit findings doc (`server-audit-termux.md`) is the authoritative
source for the *what* and *why* of each item. This doc is the
authoritative source for the *order* and *acceptance*.

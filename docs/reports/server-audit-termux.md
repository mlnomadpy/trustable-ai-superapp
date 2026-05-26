# Pitwall Python Server — Production / Termux Deployment Audit

**Date:** 2026-05-15
**Reviewer:** Taha Bouhsine
**Scope:** `src/pitwall/` Flask bridge + CAN ingest path + DB layer, with a deployment lens on Termux on a Pixel 10.
**Branch:** `aim-mxp-yaml-pipeline` (commit `ec3b93a`)

> **Post-audit update (PR #30):** Several findings below have moved or shipped.
> - Finding #3 (non-reentrant `db_lock`): shipped — `state.db_lock`, `burst_lock`, `bundles_lock` are now `threading.RLock()`. `qa_lock` was removed entirely (callers no longer share it).
> - The path `coach_engine.py:936-944` referenced in finding #13 now lives in `src/pitwall/features/coaching/litert_coach.py` (the monolith was split into 6 focused modules; `coach_engine.py` is now a re-export shim).
> - `state.py` no longer holds function-pointer attributes (`state.compute_cues`, `state.load_track`, `state.run_adk`, etc.) or `state.has_genai` / `state.qa_histories` — callers import the relevant function directly.
> - DDL is now run once at boot via `db.init_schema_once()`; `db_conn()` is the context-manager entry point.

This audit catalogs concrete improvements grouped by severity. Each finding cites the relevant file:line and gives a recommended action sized to the work.

---

## Executive summary

Pitwall is structurally sound for a single-driver, single-car edge deployment: localhost bind, optional deps cleanly gated, batched CAN writes, YAML-driven per-car pipeline, automatic DB corruption recovery (just landed in `ec3b93a`).

The main risks for running on Termux long-term are five concrete things, in priority order:

1. **No graceful shutdown** — SIGTERM kills the bridge mid-write; we already hit this once and it required a `.corrupted-<ts>` rotation. The recovery code makes it survivable but the underlying behavior is destructive.
2. **Flask dev server in production** — single-process, no graceful drain, no slow-request protection.
3. **`state.db_lock` is non-reentrant + 42 acquire sites** — one nested acquire deadlocks the bridge silently.
4. **No DB rotation / vacuum** — DuckDB file grows unbounded across track days; eventually corrupts under disk pressure.
5. **USB-CAN on non-rooted Termux** — `/dev/ttyACM0` does not auto-bind without root or `termux-usb`; the deploy doc reads as if it just works, but it doesn't.

None of these block today's `--simulate` path. All of them will be felt at the first real-car track day with the phone running for >2 hours.

---

## P0 — Critical (must address before first prod track day)

### 1. No SIGTERM handler; DuckDB never checkpoints on exit

**Where:** `src/pitwall/__main__.py:168` — `app.run(...)` returns on Ctrl-C, but nothing calls `state.can_reader.stop()`, no `CHECKPOINT`, no DB close.

**Risk:** Every clean shutdown is a hard kill from DuckDB's perspective. We saw the consequence first-hand: `FATAL: Failed to delete all rows from index` on the next boot, requiring the corruption-recovery path to rotate the file. **The recovery code masks the symptom; it does not fix the root cause.**

**Cost:** ~30 min.

**Action:**
- Register SIGTERM + SIGINT handlers at the top of `main()` that:
  1. Call `state.can_reader.stop(timeout=2.0)` if set
  2. Call `state.simulator.stop(timeout=2.0)` if set
  3. Open a DB connection, `CHECKPOINT;` to flush WAL, close.
  4. `sys.exit(0)`
- Add an `atexit` handler with the same body as a belt-and-suspenders.

### 2. Flask dev server in production

**Where:** `src/pitwall/__main__.py:168` — `app.run(host="127.0.0.1", port=port, debug=False, threaded=True)`.

The startup log even prints `WARNING: This is a development server. Do not use it in a production deployment.` We currently ignore that.

**Risk:**
- No request timeout cap — a long-running `/session/<sid>/signals` query can hold a worker thread indefinitely.
- No max-concurrent-requests — DuckDB's `state.db_lock` already serializes writes, but the reader threads queue up and burn memory.
- No graceful drain on stop — `app.run()` just stops accepting; in-flight requests are dropped.
- No HTTP/1.1 keep-alive tuning, no slow-loris mitigation.

**Cost:** ~1 h to switch to waitress (pure-python, single binary, Termux-friendly) or gunicorn.

**Action:**
- `pkg install python-waitress` on Termux (or `pip install waitress` — wheel available aarch64).
- Replace `app.run(...)` in `__main__.py` with `waitress.serve(app, host="127.0.0.1", port=port, threads=8, channel_timeout=30, cleanup_interval=10)`.
- Keep the Flask dev server only as a dev fallback when `PITWALL_DEV=1`.

### 3. Non-reentrant `state.db_lock` taken in 42 places

**Where:** `src/pitwall/state.py:44` — `self.db_lock = threading.Lock()` (not `RLock`). 42 `with state.db_lock:` sites across `db.py`, blueprints, can_reader.

**Risk:** Any call path where a lock-holder triggers code that also `with state.db_lock:` deadlocks the entire bridge — no error, no log, just everything blocked on that thread. Adding such a call is one accidental refactor away. Today, the only protections are convention and grep.

**Cost:** ~10 min.

**Action:**
- Change `threading.Lock()` → `threading.RLock()` for `db_lock` (and `burst_lock`, `bundles_lock`, `qa_lock` for consistency).
- RLock has identical semantics for the common case but tolerates nested acquires from the same thread.
- Add a comment: *"Use RLock so nested acquires from one thread don't deadlock — this code base has 42 acquire sites and we cannot prove non-nesting by inspection."*

---

## P1 — Important (next sprint)

### 4. No DB rotation / vacuum policy

**Where:** `src/pitwall/db.py` — no scheduled vacuum, no archive rotation. The `_live` session gets wiped on each boot (`reset_live_session()`), but real sessions accumulate forever.

**Risk:**
- 30 fps × 60 signals × 1 hour ≈ 6.5M tall-store rows per hour. After 50 track days, `pitwall_sessions.duckdb` is multi-GB.
- DuckDB doesn't auto-vacuum; size grows even after DELETE. Phone storage is finite.
- Larger files = longer crash-recovery + larger blast radius on the `FatalException` corruption case we just fixed.

**Cost:** ~2 h.

**Action:**
- Add a "session archive" path: at session end (lap detector EOL or explicit POST `/session/<sid>/end`), export the session's rows to a separate `archive/<sid>.duckdb` file, then DELETE them from the live DB.
- Wire a `VACUUM` call after each archive to actually shrink the file.
- Document target retention (e.g., last 30 days live; older archived).

### 5. No CAN reconnect logic

**Where:** `src/pitwall/features/telemetry/can_reader.py:355-369` — `_reader_loop` exits cleanly on `CanOperationError` and never re-tries.

**Risk:** USB unplugged / re-plugged → reader thread dies → bridge looks healthy but ingests nothing until restart. On a track day this is a session-killer (loose OBD-II adapter is common).

**Cost:** ~1 h.

**Action:**
- Wrap the open + read loop in an outer retry loop with backoff (e.g., 1 s, 2 s, 5 s, capped at 10 s).
- On reconnect, reset `self._latest` (stale cache from before the disconnect) and update the `state()` snapshot so the Pit Stall UI shows "RECONNECTED".
- Log every disconnect/reconnect with a timestamp.

### 6. Open-per-request DB connections (no pool)

**Where:** `src/pitwall/db.py:32` — `get_db()` opens a fresh DuckDB connection on every call. The HTTP `/session/<sid>/signals` endpoint opens, reads thousands of rows, closes — every call.

**Risk:** DuckDB connection setup is cheap (~5 ms) but not free. At the Pit Stall UI's 5 Hz polling, that's 25 ms/sec of pure setup overhead, on a phone CPU. Add a Vue PWA polling multiple endpoints, and we're at 100+ ms/sec on connect/close alone.

**Cost:** ~2 h.

**Action:**
- Add a tiny connection pool (one writer connection held by `state`, plus a per-thread read connection via `threading.local`). DuckDB supports multiple read connections to the same file.
- Or: thread-local single connection, opened lazily on first use, closed in a Flask `teardown_appcontext`.
- Either is a 30-line change.

### 7. No bound on `/session/<sid>/signals` queries

**Where:** `src/pitwall/features/telemetry/bp_signals.py:111-123` — auto-fills `t_from`/`t_to` from full session bounds if missing. A long-running session at 70 fps × 60 signals × 1 hour returns ~15 M rows in a single response.

**Risk:** OOM on the phone. Caller (UI) hangs for minutes.

**Cost:** 15 min.

**Action:**
- Cap `rate_hz × (t_to - t_from)` to e.g. 10000 points server-side; if exceeded, return 413 with a clear "narrow your window" message.
- Add a default `t_to - t_from <= 60 s` if neither is set and `rate_hz` is unspecified.

### 8. No structured logging; everything goes to stdout

**Where:** `src/pitwall/__main__.py:155-159` — `print(...)` for boot messages; can_reader uses `logging` but other modules don't.

**Risk:** On Termux, the stdout goes to `~/.pitwall-logs/current` (svlogd). Mixing print + logging makes filtering and rotation messy. No log levels, no structured fields for grep-by-session.

**Cost:** ~1 h.

**Action:**
- Initialize logging at the top of `main()` with a `%(asctime)s %(levelname)s %(name)s %(message)s` format.
- Replace `print(...)` calls with `log.info(...)`. Keep the unicode badges (`✓`, `⚠`) — they read fine in logs.
- Add a `--log-level` arg (default INFO; DEBUG for triage).

### 9. CAN reader `_latest` cache grows unboundedly

**Where:** `src/pitwall/features/telemetry/can_reader.py:182` — `self._latest: dict[str, float] = {}`; the YAML pipeline writes every emitted signal name into it; never pruned.

**Risk:** Minor leak — on a real bus with 100 distinct signal names, the cache is ~10 KB and stable. But on an MXP with config drift or a misbehaving adapter that sends novel IDs, the cache grows. Worth a guard.

**Cost:** 10 min.

**Action:**
- Cap to e.g. 1000 entries; on overflow, drop the oldest by insertion order (`collections.OrderedDict.popitem(last=False)`).

---

## P2 — Termux-specific concerns

### 10. USB-CAN on non-rooted Termux: `/dev/ttyACM0` does not exist

**Where:** `deploy/termux/INSTALL.md:79` recommends `PITWALL_CAN_CHANNEL=/dev/ttyACM0`. But on non-rooted Android, Termux **cannot see** `/dev/ttyACM*` — the kernel CDC-ACM driver isn't auto-bound, and Termux's app UID has no permission to enumerate `/dev/bus/usb/`. I confirmed this earlier in this branch: `ls /dev/tty*` returns nothing inside Termux on the connected Pixel 10.

**What actually works:**
1. **`termux-usb` flow** — `pkg install termux-api`, run `termux-usb -l` to list devices, `termux-usb -e <python-script> <vendor:product>` to hand a USB file descriptor to a Python process. python-can would then need adaptation to read from that FD (or use libusb-via-pyusb on top).
2. **Rooted Pixel** — `chmod 666 /dev/ttyACM0` works once `udev` rules or a setuid helper grant access. Pixel 10 stock is not rooted.
3. **Android Java side ownership** — `usb-serial-for-android` from a separate Android app, forwarding decoded frames over a Unix socket or HTTP to the Python bridge. (The prior in-repo `android-app/pitwall-bridge-ktor/` proof-of-concept was removed in PR #32; any future revival of this path would start from scratch.)

**Risk:** As written, the INSTALL.md will not work on a stock Pixel. A first-time deploy fails silently — bridge boots, CAN reader can't open the device, the user is left chasing a `/dev/ttyACM0` ghost.

**Cost:** Path 1 is the realistic one; ~1 day to adapt `can_reader.py` to accept a pre-opened FD via `--can-fd <int>`, plus a Termux:Boot shim that handles the `termux-usb` permission flow and passes the FD in.

**Action:**
- Add a "Termux USB host limitations" section to `INSTALL.md` with the three options above and call out option 1 as the recommended path for stock devices.
- Implement `--can-fd` support in `can_reader.py` (python-can's `slcan` interface accepts file descriptors via `SerialBus`; needs a small shim).
- Until then, document `--simulate` as the only working "no car" path on stock Termux.

### 11. DuckDB compile-from-source on Termux is brutal

**Observation from this branch:** During the install on the connected Pixel, `uv pip install duckdb` triggered a CMake bootstrap-from-source because no prebuilt wheel exists for the Termux aarch64 manylinux variant. The compile would have taken 30-60 minutes on the Pixel 10.

**Risk:** Every fresh Termux install / venv rebuild eats an hour. First-time setup feels broken; reinstall after a crash is painful.

**Cost:** ~2 h research + maybe ~3 h packaging.

**Action options (pick one):**
- **Pin to an older DuckDB version** that does have a Termux-compatible wheel (some have surfaced on Termux's user-repos community).
- **Bundle a prebuilt `.whl`** in `deploy/termux/wheels/` and install via `pip install --no-index --find-links deploy/termux/wheels duckdb`. Maintainable but version-locked.
- **Drop DuckDB on Termux**, use SQLite for that target — DuckDB's analytical features aren't critical for the live ingest path; the sync endpoint queries could be SQLite. Bigger refactor.
- **Document the bake-in** — accept the install cost, but display a progress bar so the user doesn't think it hung.

### 12. Wake-lock release on graceful stop

**Where:** `deploy/termux/INSTALL.md:253` mentions `termux-wake-unlock` in the uninstall path but nowhere in the normal-stop path.

**Risk:** A `sv down pitwall-bridge` stops the process but doesn't release the wake lock; phone CPU stays awake unnecessarily until Termux is killed.

**Cost:** 5 min.

**Action:**
- In the SIGTERM handler from finding #1, call `subprocess.run(["termux-wake-unlock"], check=False)` before exiting.
- Document this in INSTALL.md.

### 13. LocalLLM is an external APK with its own lifecycle

**Where:** `coach_engine.py:936-944` — pitwall HTTP-hops to `http://localhost:8099/v1` with a 30-s timeout, falls back to in-process LiteRT if the URL is empty.

**Risk:** LocalLLM is a separate process (a different APK). It can be killed by Android's memory pressure independently. When it dies:
- `/coach/brief` and `/coach/debrief` start 500'ing or stalling 30 s each.
- `/coach/ask` (ADK orchestrator) suffers 45-s timeouts per agent run (`adk_agents.py:905`).
- Driver hears nothing for 30+ s during what should be a coaching moment.

**Cost:** ~1 h.

**Action:**
- Add a fast health probe (`HEAD /v1/models` with 2-s timeout) before every LLM request. If down, return a degraded rules-only response immediately instead of waiting on the long timeout.
- Track `state.litert_up: bool` and surface it in `/health` so the PWA can warn the driver.
- Optionally: a watchdog thread that re-launches LocalLLM via `am start` if it stays down for >60 s (requires `termux-am`).

### 14. Memory pressure: bridge + LocalLLM + ADK + sonic_model

**Observation:** Boot log shows `✓ ADK coach_orchestrator loaded — 17 agents`, plus `sonic_model`, `LiteRT-LM E4B`. Plus DuckDB's column stores. Plus the simulator thread when `--simulate`. The Pixel 10 has 12 GB RAM but Android keeps roughly half for OS + foreground apps.

**Risk:** On a long session with continuous coaching, memory creeps. Android's low-memory killer eventually nukes Termux when foreground apps demand RAM. The bridge dies mid-session.

**Cost:** Profiling needed (~half day). Mitigations are then specific.

**Action:**
- Add a periodic RSS log (every 60 s, `psutil.Process().memory_info().rss`). Watch it for 1-hour idle runs to baseline growth.
- The `_tall_id_cache` in `can_reader.py` is unbounded; same story as `_latest` (finding #9). Cap it.
- Consider lazy-loading the 17 ADK agents — only the active "intent" agent needs to be in RAM. Today all 17 are constructed at startup.

---

## P3 — Future / nice-to-have

### 15. No auth on the bridge HTTP endpoints

Anyone with localhost access (any app on the phone) can hit `/coach/brief`, `/session/_live/signals`, or DELETE-ish endpoints if any exist. Today this is *fine* because it's a single-user device. If a partner app is ever added, or if the bridge is `adb forward`-ed to a shared Mac on the user's behalf, the surface is unprotected.

**Action:** Add a `PITWALL_TOKEN` env var that the bridge requires on every request as a `X-Pitwall-Token` header. Default-empty disables. Document in INSTALL.md.

### 16. No encryption-at-rest

The DuckDB file is plaintext. Telemetry is not PII per se, but GPS traces + lap times + driver behavior is identifiable. On a stolen phone, the data is readable.

**Action:** DuckDB doesn't natively encrypt; would need full-disk encryption (Android default) to be sufficient. Verify the Pixel's disk encryption is on. Document this in the security section.

### 17. Single-writer pattern for DB

Today: CAN reader, HTTP endpoints, and capability recompute all write to the same DB through `db_lock`. Reads contend with writes. A single-writer pattern (only CAN reader writes; HTTP endpoints are read-only or post-via-queue) would let us use DuckDB's multi-reader-single-writer mode efficiently.

**Action:** Big refactor. Defer until #6's connection pool is in place; then revisit.

### 18. CAN reader's `_consume` is single-threaded by design but pipeline could be heavy

For each frame: cantools decode → 22 SignalProcessor pipelines → up to ~10 emissions per frame → cross-signal derives → method handlers → tall-store insert (executemany). At 350 fps (real AiM MXP), this is the hot path. If it ever gets slow, frames queue up in `python-can`'s receive buffer and we drop telemetry.

**Action:**
- Add a `frames_dropped` counter exposed via `state()`.
- Benchmark `_consume` with `cProfile` on a 1-min capture; flag if any single step is >100 µs/frame.
- The cross-signal derived block fires on every frame even when its inputs haven't changed. Cheap dedupe (skip if `latest` values for all inputs are identical to last call) could save 50% of derive evaluations.

---

## What's already solid (don't break)

- **Localhost-only bind** (`__main__.py:168`) — no accidental remote exposure.
- **All heavy deps gated behind try/except + feature flags** (`state.py:100-193`) — bridge boots even if `torch` or `google-adk` are absent.
- **DB corruption recovery just landed** (`db.py:383-481`) — rotate-and-rebuild keeps the bridge bootable through prior crashes.
- **Capabilities lazy compute just landed** (`bp_signals.py:14-54`) — `_live` session is usable immediately.
- **YAML-driven per-car pipeline** (`data/cars/*.yaml` + `car_config.py` + `formula.py`) — new car = new YAML, no Python edits.
- **Synthetic simulator** (`src/simulator/aim_mxp_simulator.py`) — full ingest path exercisable without a real car, single `--simulate` flag.
- **Wake-lock + Termux:Boot + svlogd plan** in `deploy/termux/INSTALL.md` — the supervision story is documented even where the implementation needs follow-up.

---

## Prioritized action list

| # | Title | Severity | Cost | Order |
|---|---|---|---|---|
| 1 | SIGTERM + CHECKPOINT | P0 | 30 min | **1st** |
| 3 | RLock for db_lock | P0 | 10 min | **2nd** |
| 2 | Switch to waitress | P0 | 1 h | **3rd** |
| 10 | USB-CAN via `termux-usb` | P2 | 1 d | **4th** (blocks real-car) |
| 5 | CAN reconnect loop | P1 | 1 h | 5th |
| 7 | Cap signals-endpoint window | P1 | 15 min | 6th |
| 13 | LocalLLM fast health probe | P2 | 1 h | 7th |
| 4 | DB rotation / vacuum | P1 | 2 h | 8th |
| 6 | Connection pool | P1 | 2 h | 9th |
| 11 | DuckDB Termux wheel | P2 | 2-5 h | 10th |
| 8 | Structured logging | P1 | 1 h | 11th |
| 14 | Memory profiling | P2 | 0.5 d | 12th |
| 12 | Wake-lock release on stop | P2 | 5 min | bundle with #1 |
| 9 | `_latest` cache bound | P1 | 10 min | bundle with #5 |
| 15-18 | Auth, encryption, single-writer, hot-path optimization | P3 | varies | post-MVP |

The top three (#1, #3, #2) are all ≤1 h and remove the failure modes most likely to bite during the first prod track day. The fourth (#10) is what makes the first real-car run actually possible on a stock Pixel.

---

## Note on git state

Three commits sit locally on `aim-mxp-yaml-pipeline`, waiting for network:

```
ec3b93a  fix(bridge): recover from DuckDB index corruption; lazy capabilities
520c9ed  feat(simulator): AiM MXP synthetic simulator + --simulate flag
04f65fb  feat(can): YAML-driven per-car pipeline for sign / units / derivations
```

This audit is committed alongside them as `docs/reports/server-audit-termux.md`.

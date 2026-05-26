# Pitwall Backend Audit — 2026-04-28

> **Historical snapshot.** File paths below reflect the layout as of 2026-04-28. Since then PR #30 reorganised `src/pitwall/features/coaching/` (split `coach_engine.py` into 6 modules behind a back-compat shim) and promoted helpers from the now-deleted `helpers.py` into `features/session/laps.py`, `features/session/frames.py`, `features/coaching/cue_renderer.py`, and `features/track/track_json.py`. See `internal_architecture.md` for the current module map.
> Note: pitwall_bridge.py was deleted in a prior commit; bridge entry is now src/pitwall/__main__.py.

Audit of all Python code shipped in this work cycle (`src/pitwall/features/`, `tools/`). Catalogs:

- **Bugs** — incorrect behaviour observed or trivially provable.
- **Weak spots** — code that works but has known fragility (data dependence, edge cases).
- **Architectural risks** — decisions that may need revisiting based on field-test feedback.

Each item is tagged **[FIX]** if it gets patched in this turn or **[DEFER]** if it's a known limitation we're shipping with.

---

## src/pitwall/features/sonoma.py

- ✅ Constants module is straightforward; `LAP_TIME_LEVERAGE` weights validated to sum to 1.0 at import time.
- **[FIX]** `WeatherPhase.start_hour=18, end_hour=18` is missed at hour 18+ — `weather_phase_for_hour(20)` should return `late_session`. The current loop with `<` end_hour misses the boundary. Patch the loop to use `<=` or extend the last phase.
- **[FIX]** No test asserts `LAP_TIME_LEVERAGE` covers exactly the 11 entries of `CORNER_ORDER`. Drift between the two would silently miscompute weighted scores.

## src/pitwall/features/track_loader.py

- ✅ `MarkerDef` dataclass + `find_nearest_marker` + `find_marker_for_next_corner` work correctly on the canonical sonoma.json.
- **[FIX]** `find_nearest_marker` with `kind=None` and `corner=None` and a marker exactly at `track_dist` returns None because the gap-check is `0 < gap < lookahead`. A marker exactly at the car's position should be the answer; current code skips it. Change to `0 <= gap < lookahead` and let the cooldown logic deduplicate.
- **[DEFER]** `cross_track_error` does point-to-point haversine to the nearest reference_line vertex, not perpendicular distance to the polyline segment. Approximate but introduces ~1 m error near corners with sparse reference points. Acceptable for current use; noted for future.

## src/pitwall/features/vbo_parser.py

- ✅ Now extracts the `avitime` field for video sync. `TelemetryFrame.avitime` defaults to 0 when absent.
- **[DEFER]** Per-frame `import math` inside the parsing loop — minor inefficiency, doesn't justify a refactor.
- **[DEFER]** No unit conversion check on `avitime` — assumes milliseconds (correct for Racelogic VBO format but brittle if a different vendor's file is used).

## src/pitwall/features/gold_standard.py

- **[KNOWN — DEFER]** Lap detection still imperfect with the dataset's distance counter. The fastest detected single lap is usually a partial slice rather than a full lap when the file contains many runs. Per-corner aggregation (the more important output) is robust; the headline `lap_time_s` is the weak number.
- ✅ The "best pass per corner" picker now scores by `(min_speed_kmh, exit_speed_kmh)` with a slowed-at-apex sanity filter, not `corner_time_s` alone — fixes the earlier "blew through the corner at 170 km/h" bug.
- **[FIX]** `_aggregate_corner_pass_abs` returns 0 for `brake_point_m` and `brake_release_m` when the driver never brakes for that corner. Should return None or `nan` so the grader can distinguish "no data" from "brake at entry". Patch the dataclass + grader to handle None.

## src/pitwall/features/corner_grader.py

- ✅ Weighted A-F formula matches `feedback-system.md:118-140` spec.
- ✅ Time-loss decomposition has 8 cause categories with capped attribution to prevent over-counting.
- **[FIX]** `_trod_voice_for` returns "Nice — keep that line." for any corner with empty attribution, including high-leverage corners where it should suggest something more nuanced. Add a corner-specific positive voice line for graded-A passes.
- **[DEFER]** Time-loss attribution coefficients (e.g. `0.025 * apex_delta` for low_apex_speed) are heuristic, not calibrated. Calibration requires multiple gold-vs-driver lap pairings — Phase 4 work.

## src/pitwall/features/analytics.py

- ⚠ **[FIX] Critical bug in `smoothness_per_corner`**: the `_track_corners_cache` helper is a stub that returns inert tuples `(name, 0, track_len)` for every corner. As a result, the function reports the SAME corner span (the entire track) for every corner — meaning all "in-corner" frames are everything, the std-devs are computed over the whole lap, not per-corner. The output is a dict keyed by corner name but the values are session-wide, not corner-specific. **Patch needed**: refactor `smoothness_per_corner` to take the `track` object (already loaded by the caller) and use real corner entry/exit distances.
- ✅ `friction_circle`, `hustle_map`, `consistency`, `eob_summary`, `slip_angle_band`, `change_in_speed_events`, `trail_brake_events`, `flight_recorder`, `limit_oscillation`, `plateau_detector` are all correct against synthetic inputs.
- **[FIX]** `friction_circle` `samples` field caps at 1500 entries with no downsampling — a 8000-frame lap's first 1500 frames don't represent the whole session well. Use stride sampling (`frames[::n]` so all parts of the lap are represented).

## src/pitwall/features/highlight_finder.py

- ✅ All 7 Sonoma-specific categories detect from synthetic frames as expected.
- **[FIX]** "Perfect trail brake at T4" detector: the condition `0.5 <= (apex/peak) <= 0.20` is malformed — `0.5 <= x <= 0.20` is always False. Should be `0.05 <= ... <= 0.20`. The detector currently never fires.
- **[DEFER]** Severity ordering puts "engineering" lowest (correct) but "positive" sits between "medium" and "engineering". For the post-session debrief we may want positives before engineering events. Acceptable default.

## src/pitwall/features/driver_profile.py

- ✅ Schema is append-only, idempotent. `compute_profile` correctly identifies weakest_recent_corner and biggest_improvement.
- **[FIX]** `compute_profile` `biggest_improvement` compares `hs[0] - hs[1]` after ordering DESC by `recorded_at`. If the most-recent score is the *worst*, it returns a negative delta (regression, not improvement). Filter to `delta > 0` before picking the biggest.

## src/pitwall/features/session_analyzer.py

- ✅ `_segment_into_laps` correctly assigns lap indices via cumulative-distance progression.
- **[FIX]** Templated narrative writes `Δ: +-63.00 s` when the best lap is *shorter* than the gold (negative delta). The format string `+{delta:.2f}` produces `+-63.00` instead of `-63.00`. Use `{delta:+.2f}` consistently OR special-case the sign.
- **[FIX]** When `_no_gold_bundle` triggers, `consistency` and `eob_summary` are empty dicts but `friction` and `slip_band` still get computed — inconsistent behaviour. Either compute all-of-them or none-of-them.

## src/pitwall/features/coach_engine.py

- ✅ `RuleCoach`, `LitertCoach`, `CoachContext`, `CoachArbiter`, all three system-prompt builders work correctly with synthetic inputs.
- ✅ `LitertCoach` falls back to `RuleCoach` when MediaPipe is missing — verified by smoke test.
- ✅ `make_coach("auto")` priority `litert > rule` works.
- **[DEFER]** No way to inject a custom system prompt at runtime. `build_system_prompt` is pure (deterministic) but doesn't accept overrides for testing variant prompts. Could be added without breaking the contract.

## src/pitwall/__main__.py

- ✅ 26 endpoints, all importable cleanly. Schema initialises on first use.
- **[FIX]** `_section()` returns a `Response` with implicit 200 when bundle is missing. Should return `(jsonify(...), 404)` consistently — already done in `session_detail` and `session_clips`, missing in `_section` itself. Fix returns to be `(response, status)` tuples.
- **[FIX]** `_load_session_frames` is called inside the request handler with the DB lock held briefly, then releases. If multiple debriefs hit the same session simultaneously the analyser runs twice. Add an in-memory lock per session_id around `_session_bundles` writes.
- **[DEFER]** The `/coach/brief` driver_id="" (empty string) case computes profile against an empty driver — which returns no profile data, which is fine, but also writes empty events on the post-debrief side if `persist_to_profile=True` and `driver_id=""`. Should skip persistence when no driver_id.
- **[FIX]** `session_sync` SQL parameter bindings are constructed in two passes (`params` then `params2`) — the first list is unused; cleanup.

## tools/enrich_sonoma_track.py

- ✅ Idempotent. Writes `.bak`. Syncs to all 4 duplicate copies.
- **[FIX]** `_sample_reference_line` returns `(0.0, 0.0)` if the reference_line is empty — better to return `None` so callers can detect missing data instead of pinning the marker at the equator.

## tools/extract_gold_lap.py

- ✅ Default paths work. Output JSON is round-trippable.
- **[DEFER]** `--vbo` defaults to a hardcoded forza path. Acceptable — this is a dev tool, not a production deploy.

## tools/best_sonoma_lap.py

- ✅ S/F-line projection + sign-change detection works (22 sessions found vs 0 with the old radius-only detector).
- **[KNOWN — DEFER]** Best lap times are ~2:28 vs the filename's claim of 1:47.5. The dataset's anonymised GPS may scale the track differently. Can't fix without ground-truth lap data; the relative ranking is still correct.

## tools/import_sonoma_real_gps.py

- ✅ Stitches OSM Overpass results into a closed loop (88 m closure gap, ~1% scale match against anonymised).
- **[FIX]** `map_fractional` is invoked twice per marker (once for lat, once for lon). Cache the call.
- **[DEFER]** No retry/timeout handling for the Overpass request. Acceptable for a one-shot tool.

## tools/extract_marker_thumbnails.py

- ✅ Produces correct cut points (verified: 16 markers, average 0.3 m frame gap). Falls back to dry-run when ffmpeg is missing.
- **[DEFER]** `find_frame_at_distance` does a full O(n) scan for each marker — 16 × 8000 frames = 128K comparisons, milliseconds. Not worth pre-indexing.

## tools/validate_litert.py

- ✅ Self-contained, lazy imports, runs without MediaPipe installed (it'll FAIL at step 1 cleanly).
- **[DEFER]** No way to test this from a non-Pixel environment without mocking MediaPipe — that's by design.

---

## Summary of fixes landing this turn

| File | Fix |
|---|---|
| `sonoma.py` | `weather_phase_for_hour` boundary at hour 18 |
| `track_loader.py` | `find_nearest_marker` includes gap=0 |
| `gold_standard.py` | brake_point_m / brake_release_m use None when no brake event |
| `corner_grader.py` | per-corner positive voice line for graded-A passes |
| `analytics.py` | **`smoothness_per_corner` rewritten** to use real track corners |
| `analytics.py` | `friction_circle` stride-samples instead of head-of-lap |
| `highlight_finder.py` | T4 trail-brake condition fix (`0.05 <= … <= 0.20`) |
| `driver_profile.py` | `biggest_improvement` filters to positive deltas |
| `session_analyzer.py` | sign formatting in templated narrative |
| `pitwall_bridge.py` | `_section()` returns 404 with status code |
| `pitwall_bridge.py` | `session_sync` parameter cleanup |
| `enrich_sonoma_track.py` | `_sample_reference_line` returns `None` on empty |
| `import_sonoma_real_gps.py` | cache `map_fractional` call |

Everything else is **[DEFER]** — known but acceptable.

---

## Test plan

Test files in a new `tests/` directory at the repo root, runnable with `pytest tests/`. Each module gets a focused unit-test file plus an integration test that exercises the full session → debrief flow. See `tests/conftest.py` for shared fixtures.

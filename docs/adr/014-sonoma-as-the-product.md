# ADR-014: Sonoma is the Product

**Status:** Accepted
**Date:** 2026-04-28

## Context

The Pitwall sprint exists to ship a coaching system at **Sonoma Raceway on May 23, 2026**. Yet the codebase still treats Sonoma as one of N possible tracks: `track_loader` is generic, `coach_engine._TRACK_LORE` is a dict keyed by track name, three track JSONs sit in `data/tracks/`, and every consumer accepts a `--track` flag.

This abstraction earns nothing for the field test and costs us in three places:

1. **System prompts** are weaker because Sonoma-specific knowledge is parameterised rather than asserted. The LLM has to guess whether "the bridge" is a brake reference at *this* track.
2. **Visualisation** can't ship a real Sonoma map. The track JSON's GPS is anonymised (`23.49°N`); a Sonoma-only design lets us hardcode the real GPS layer (`38.16°N, -122.45°W`).
3. **Scoring** treats every corner equally. Sonoma's lap time is dominated by T10 (fastest), T11 (exits onto the main straight), and T6 (long sweeper). Generic equal-weight A-F grading buries this.

Two architectural decisions on 2026-04-28 already pointed this way:
- [ADR-012](012-coach-engine-adapter.md) committed to **on-device only** (LiteRT-LM via MediaPipe Genai) — no track-agnostic cloud.
- [ADR-013](013-frontend-backend-boundary.md) committed to **backend owns LLM logic + system prompts** — the frontend stops being a place where track context could leak in.

ADR-014 finishes the job: Sonoma is the product.

## Decision

**Sonoma is hardcoded as the canonical track of the app.** Track abstractions remain in the *function signatures* (loaders, grader, marker lookup) so future track support is possible if the project ever expands, but every default, every prompt, every UI assumes Sonoma. Other tracks in the dataset (`track2.json`, `track8.json`) move to `data/tracks/training_data/` — they were ML training material, not deployment targets.

Three bodies of work land under this ADR:

1. **Sonoma data layer** — real GPS, derived marker coordinates, hardcoded constants.
2. **Three-mode coaching** — pre-brief, during-drive, post-session — each with a Sonoma-specific system prompt.
3. **Visualisation bundles** — pure JSON the frontend renders for map, scorecard, highlights, replay.

---

## Sonoma data layer

### Canonical artifacts

| File | Purpose |
|---|---|
| `data/tracks/sonoma.json` | Track geometry + 16 markers + per-corner Bentley/T-Rod tips. Already authored from `sonoma_track_intelligence.md`. |
| `data/tracks/sonoma_real_gps.json` | Real Sonoma GPS centerline + marker lat/lon. **NEW** — derived from OSM + the synthetic-VBO real coords. |
| `data/reference/sonoma_gold.json` | Frozen Gold Standard lap profile per corner: entry/apex/exit speed, brake point, peak bar, trail-brake metric. **NEW** — extracted from the dataset's fastest verified Sonoma lap. |
| `data/reference/sonoma_aj_trace.parquet` | Full per-frame telemetry of the Gold Standard lap. **NEW** — for delta-overlay rendering. |
| `data/tracks/training_data/track2.json`, `track8.json` | Moved out of the active path. Kept for ML training reference. |

### `src/pitwall/features/sonoma.py` (NEW)

> Updated 2026-05 (PR #30): module relocated to `src/pitwall/features/track/sonoma.py` as part of the feature-sliced reorganisation.

A module of hardcoded Sonoma constants — not data-driven, not parameterised. The things we *know* about this track:

```python
TRACK_NAME = "Sonoma Raceway"
TRACK_LENGTH_M = 4258
ELEVATION_RANGE_M = 49
SF_LAT, SF_LON = 38.16152, -122.45472   # Real finish line

# Sectors with names, not just "Sector 1"
SECTORS = [
    Sector("Front", 0, 1294,    "Start/finish through the esses, into the Carousel"),
    Sector("Back", 1294, 2752,  "Carousel exit through T9, into T10 brake zone"),
    Sector("Final", 2752, 4258, "T10 exit through T11 onto front straight"),
]

# Per-corner risk + lap-time leverage weights — drive the corner-grade
# formula and the highlight-finder severity. Calibrated from the dataset.
LAP_TIME_LEVERAGE = {
    "Turn 1": 0.06, "Turn 2": 0.08, "Turn 3": 0.07, "Turn 4": 0.09,
    "Turn 5": 0.04, "Turn 6": 0.13, "Turn 7": 0.09, "Turn 8": 0.06,
    "Turn 9": 0.07, "Turn 10": 0.16, "Turn 11": 0.15,
}

# Known dangerous moments — feed safety overrides + post-session highlights
DANGER_ZONES = [
    DangerZone("T6_runoff",  1294, 1418, "Carousel run-off — wall close"),
    DangerZone("T9_downhill", 1820, 2108, "Long downhill into the Carousel exit"),
    DangerZone("T11_dive",   4080, 4256, "Calamity Corner — passing battleground"),
]

# Sonoma weather pattern — surface temperature, fog burn-off, grip evolution
WEATHER_PHASES = [
    WeatherPhase("morning_fog",  start_hour=6,  end_hour=10, surface="cool damp"),
    WeatherPhase("warm_up",      start_hour=10, end_hour=12, surface="rising grip"),
    WeatherPhase("peak_grip",    start_hour=12, end_hour=15, surface="optimal"),
    WeatherPhase("late_session", start_hour=15, end_hour=18, surface="tire degradation"),
]

# Hardware notes specific to running at Sonoma in the BMW M3
RIG_NOTES = {
    "bluetooth_dropouts": ["back of the Carousel (T6 exit, hill blocks LOS)"],
    "data_lull":          "T2 → T3 climb is RPM-flat at 4500-5000",
    "video_sync_marker":  "downhill at T6 has the largest IMU spike — use as A/V sync",
}
```

Every consumer reads from `sonoma.py` directly. No string lookup, no parameterisation, no fallback path.

---

## Three-mode coaching

`coach_engine.py` gains a `CoachMode` enum and three composers. Same `LitertCoach` runtime, different prompts and outputs. All three modes assume Sonoma — system prompts hardcode the track context rather than composing it from a dict.

### Mode 1 — `PRE_BRIEF`

**When:** driver opens the Flutter app in the paddock before a session.
**Endpoint:** `POST /coach/brief`
**Inputs:**
- `driver_id` (looks up event-sourced profile from DuckDB)
- `today_iso` (drives weather phase selection)
- `markers_selected: list[str]` (the "pick 3" UX from earlier discussion — three corner IDs the driver wants to focus)
- `goal: str` ("personal best lap" / "consistency" / "learn T11" — free-form)

**System prompt (Sonoma-hardcoded, ~800 chars):**
> You are a pro race coach giving a pre-session brief at Sonoma Raceway. The driver is in a BMW M3, intermediate level. The track is 4.06 km, 49 m elevation, 11 corners. Today is `{day_phase}` — `{surface_state}`. The driver has chosen three focus corners: `{markers_selected}`. Their event-sourced profile shows `{weakest_corner}` graded D in the last 3 sessions and `{best_corner}` improved by `{delta}` km/h since last visit. Respond with a 4-paragraph brief: 1) one-line greeting + weather/grip note, 2) what to focus on per chosen corner with named landmarks ("brake at the bridge", "be closer to the tire stacks"), 3) one safety reminder for today's dangerous spot, 4) one canonical T-Rod phrase to keep in mind. Total ~150 words. End with the literal token `<FOCUS>` followed by a JSON list of 3 actionable focus items, e.g. `["brake later at T4 (back up by one marker)", ...]`.

**Output:** `{narrative_md, focus: list[str], system_prompt_used: str}`

### Mode 2 — `DURING_DRIVE`

Already shipped. `RuleCoach` + `LitertCoach` produce one-line pace notes per burst via `/analyze`. Sonoma lore is hardcoded in `coach_engine._TRACK_LORE["Sonoma Raceway"]` (will move to `sonoma.py:SYSTEM_PROMPT_LORE` constant under this ADR for consistency).

### Mode 3 — `POST_SESSION`

**When:** session ends (driver returns to paddock, or explicit "End Session" tap).
**Endpoint:** `POST /coach/debrief` with `session_id`
**Inputs assembled server-side:**
- All laps for `session_id` from DuckDB.
- All `coaching_notes` (what was actually voiced).
- Per-corner aggregates (entry/apex/exit speeds, brake metrics, trail-brake intensity).
- Delta to Gold Standard at every corner.
- Comparison to driver's prior 3 sessions at Sonoma (event-sourced profile).
- Highlight moments from `highlight_finder.py` (see below).

**System prompt (Sonoma-hardcoded, ~1200 chars):**
> You are a pro race engineer giving a post-session debrief at Sonoma Raceway. The driver completed `{n_laps}` laps in `{total_time}`. Best lap: `{best_lap}` (gold standard at Sonoma is `{gold_lap}`). The session-summary block below contains corner-by-corner grades A–F, deltas to gold, and the top-5 highlight moments computed by the analyser. Use the canonical T-Rod voice ("Distance is king", "Just go 100", "Wait, you're not at the apex yet"). Respond with: 1) one-paragraph headline assessment, 2) one paragraph per highlight moment (lap N, corner, what happened, what to do next time), 3) one paragraph identifying the single biggest lap-time-leverage opportunity (likely T10 or T11 given Sonoma's geometry), 4) three focus items for next session, formatted as a JSON list after the literal token `<NEXT_FOCUS>`. Reference named Sonoma landmarks throughout — "the bridge", "the bump", "Calamity Corner", "the third tire stack". Total ~300 words.

**Output:** `{narrative_md, scorecard, highlights, map_overlay, video_cuts, next_focus, system_prompt_used}` — the full visualisation bundle.

---

## Analysis pipeline (Python, in `src/pitwall/features/`)

Three new modules, all Sonoma-specific:

### `corner_grader.py` (~80 lines)
Implements the A-F formula from `feedback-system.md:118-140`, **weighted by Sonoma `LAP_TIME_LEVERAGE`** so T10/T11 dominate the session grade. Reads frames + Gold Standard, writes a `corner_grades` table.

```python
def grade_corner_pass(actual: CornerPass, gold: GoldCornerPass) -> Grade:
    # Existing weighted-gap formula × sonoma.LAP_TIME_LEVERAGE[corner_name]
    ...

def grade_session(session_id: str) -> SessionScorecard:
    # All passes, all corners, write to corner_grades table
    ...
```

### `highlight_finder.py` (~150 lines)
Computes top-N "moments" per session. Sonoma-specific categories:

| Category | Detection | Severity |
|---|---|---|
| `t6_carousel_oversteer`         | combo G > 1.6 + yaw_rate > expected at T6 | high |
| `t11_bump_late_brake`           | brake event > 5m past `T11_bump.distance` | high |
| `t10_lift_when_brake_needed`    | brake > 30 bar at T10 entry (gold standard says lift) | medium |
| `t9_pinch_into_t10`             | exit_speed at T9 < gold by >3 km/h | medium |
| `coast_in_T2_climb`             | throttle <10% during T2 → T3 RPM-flat zone | medium |
| `perfect_trail_brake_T4`        | brake taper matches gold within 5%, gLat within 0.05G | positive |
| `improved_corner_vs_last_session` | grade improvement of 1 letter or more | positive |
| `bluetooth_dropout_back_carousel` | telemetry gap >100ms in known LOS-blocked zone | engineering |

Returns `[{category, lap, distance_m, severity, telemetry_window, narrative_seed}]`. Output feeds the LLM prompt and the frontend's video-cut list.

### `session_analyzer.py` (~120 lines)
Orchestrator. Reads everything for a `session_id`, runs grader + highlight finder, calls `LitertCoach` with mode=POST_SESSION, returns the bundle. The bundle shape is the contract with the frontend (next section).

---

## Visualisation data bundles (frontend contract)

Per ADR-013 the frontend renders only — every screen consumes a JSON bundle the backend has fully prepared.

### `GET /session/<sid>/scorecard`
```json
{
  "session_id": "sonoma-20260523-team2",
  "n_laps": 8,
  "best_lap_s": 105.2,
  "gold_lap_s": 102.4,
  "session_grade": "B",
  "weighted_total_pct": 88.4,
  "corners": [
    {
      "name": "Turn 10", "grade": "C", "weight": 0.16,
      "entry_delta_kmh": -2.1, "apex_delta_kmh": -3.4, "exit_delta_kmh": -1.8,
      "brake_point_delta_m": +8.0, "trail_brake_quality": 0.61,
      "best_pass_lap": 5, "worst_pass_lap": 2,
      "named_landmarks_hit": ["the Toyota sign letters"],
      "trod_voice": "Lift, don't brake."
    },
    ...
  ]
}
```

### `GET /session/<sid>/highlights`
Ranked list, each with everything the frontend needs to render a card + clip:
```json
[
  {
    "title": "T11 brake — 5m past the bump (lap 3)",
    "category": "t11_bump_late_brake",
    "severity": "high",
    "lap": 3, "distance_m": 4085,
    "video_in_s": 312.4, "video_out_s": 318.9,
    "narrative_md": "Lap 3, Turn 11 — you started braking 5 m past the bump. ...",
    "telemetry_window": [/* per-frame slice for the chart overlay */]
  },
  ...
]
```

### `GET /session/<sid>/map`
Pure GeoJSON the frontend overlays on a Mapbox/Maplibre layer — uses `data/tracks/sonoma_real_gps.json`:
```json
{
  "lap_polylines": {"5": "<geojson>", "best": "<geojson>", "gold": "<geojson>"},
  "per_corner_color": {"Turn 1": "#4caf50", "Turn 10": "#f44336", ...},
  "marker_pins": [{"id": "T11_bump", "label": "the bump", "lat": ..., "lon": ...}, ...],
  "danger_zones": [{"id": "T6_runoff", "polygon_geojson": "..."}, ...]
}
```

### `GET /session/<sid>/clips`
ffmpeg-ready cut points the Flutter side requests one at a time:
```json
[
  {"id": "h1", "in_s": 312.4, "out_s": 318.9, "title": "T11 late brake"},
  ...
]
```

### `GET /coach/brief?driver=&date=&focus=T4,T7,T11`
Pre-session bundle:
```json
{
  "narrative_md": "Morning fog still burning off — first lap will be cool damp surface...",
  "focus": ["brake later at T4 — back up by one marker", "single-apex T7 cutting the inside", "T11 — be closer to the tire stacks, distance is king"],
  "weather_phase": "morning_fog",
  "weakest_recent_corner": "Turn 10",
  "best_recent_improvement": {"corner": "Turn 6", "delta_kmh": +2.4},
  "danger_zones_today": ["T6 runoff cool/damp — extra caution lap 1"]
}
```

---

## Driver profile (event-sourced)

New DuckDB table — append-only — that powers pre-brief and "improved vs last session":

```sql
CREATE TABLE driver_events (
    id           INTEGER PRIMARY KEY DEFAULT nextval('driver_events_id_seq'),
    driver_id    VARCHAR,
    session_id   VARCHAR,
    corner       VARCHAR,
    event_kind   VARCHAR,    -- 'grade', 'best_apex_speed', 'mistake', 'improvement'
    value_num    DOUBLE,
    value_str    VARCHAR,
    recorded_at  TIMESTAMP DEFAULT now()
);
```

Post-session writes events; pre-brief reads them. Profile is computed, not stored — so adding new event kinds doesn't require migrations.

---

## What this ADR rules out

- **Generic track UI.** No track picker on the home screen. Sonoma is the home screen.
- **Track-agnostic coaching prompts.** Every system prompt asserts Sonoma context, named landmarks, and known danger zones.
- **Equal-weight corner grading.** T10/T11 dominate per `LAP_TIME_LEVERAGE`.
- **Cloud LLM tier.** Already ruled out by ADR-012 — restated for completeness.
- **Loading other track JSONs at runtime.** They move to `data/tracks/training_data/` and are read only by the ML training pipeline.

---

## Migration list

| Item | Action |
|---|---|
| `data/tracks/track2.json`, `track8.json` | Move to `data/tracks/training_data/` |
| `coach_engine._TRACK_LORE` (dict) | Replace with `from src.simulator.sonoma import SYSTEM_PROMPT_LORE` |
| `--track` CLI flag in `pitwall_app.py` and bridge | Default to Sonoma; flag becomes optional override for ML reproducibility |
| `track_loader.find_nearest_corner` etc. | API unchanged; every caller passes the canonical Sonoma path |
| New `src/pitwall/features/sonoma.py` | Hardcoded constants module |
| New `src/pitwall/features/{corner_grader,highlight_finder,session_analyzer}.py` | Analysis pipeline modules |
| New endpoints: `/coach/brief`, `/coach/debrief`, `/session/<id>/{scorecard,highlights,map,clips}`, `/driver/<id>/profile` | Add to `src/pitwall/__main__.py` |
| New `data/tracks/sonoma_real_gps.json` | Author from OSM centerline + marker distance + reference_line trace |
| New `data/reference/sonoma_gold.json` + `sonoma_aj_trace.parquet` | Extract from dataset's fastest Sonoma lap |
| Frontend (`flutter/lib/screens/`) | Consumes the JSON bundles above; does not implement scoring/highlighting/grading. Per ADR-013. |

---

## Phasing for May 23 field test

| Phase | Deadline | Slice |
|---|---|---|
| **1 — must-ship** | May 10 | `sonoma.py` constants, `corner_grader`, post-session narrative + scorecard endpoint, real-GPS centerline. Driver gets a debrief screen. |
| **2 — should-ship** | May 18 | `highlight_finder`, video-cut endpoint, map-overlay endpoint with GPS marker pins. Frontend can render a highlights reel. |
| **3 — nice-to-have** | May 22 | Pre-brief endpoint + driver-event store. First useful brief is for *session 2* on field-test day. |
| **Phase 4 (post-sprint)** | June | Longitudinal trend tracking, "T-Rod auto-clip" voice replay, adaptive coaching difficulty. |

Phase 1 is 4 days of work, Phase 2 is another 4-5, Phase 3 is 2-3. Total ~10-12 days of focused engineering — fits comfortably in the 25 days remaining.

---

## Consequences

**Positive**
- System prompts are sharp: every prompt asserts Sonoma context as fact, not parameter.
- Visualisation gets free real-GPS rendering — marker pins, danger zones, gold-lap polyline.
- Scoring weights match what actually wins lap time at Sonoma.
- Code paths are straighter — fewer `if track == "Sonoma"` branches because Sonoma is the only branch.
- The frontend has one set of JSON shapes to render, not parameterised renderers.

**Negative**
- Future track support requires explicit re-generalisation. Acceptable: not a current goal.
- `sonoma.py` constants drift if the track resurfaces or a corner is renumbered. Mitigation: a tiny test that reads `sonoma.json` and asserts corner counts/lengths agree.

## Feature catalog

What follows is the full menu of coaching modes, analyses, visualizations, and engagement features the Sonoma-targeted system can offer. Each entry lists the **data dependency** (what telemetry / track data / model the feature needs) and the **build cost** (S = small, ≤1 day; M = medium, 2-3 days; L = large, 4+ days). Items marked **[shipped]** already exist in the codebase; **[Phase N]** maps to the phasing table above.

### Coaching modes — when the driver gets a voice

| # | Mode | Trigger | Data | Cost | Phase |
|---|---|---|---|---|---|
| 1 | **Pre-brief** | App open, before session | Driver profile, gold standard, focus markers, weather phase | M | 3 |
| 2 | **During-drive pace notes** | Every burst (7.5 s) | Frame + next corner + matched Bentley/T-Rod concept | — | shipped |
| 3 | **Post-session debrief** | "End Session" tap | Full session DuckDB, gold delta, highlights | M | 1 |
| 4 | **Out-lap warm-up coaching** | First lap of stint, cold tires | Phase classifier + tire-temp inference (RPM/brake-temp surrogate) | S | 2 |
| 5 | **In-lap / cool-down enforcement** | Last lap before pit-in | Same as during-drive but with a "same line, slower" voice (T-Rod) | S | 2 |
| 6 | **Mid-session pit reset** | Stop > 30 s in pit lane | Mini-debrief of the stint just completed + 1-line focus for next stint | S | 3 |
| 7 | **Incident debrief** | Over-limit / off-track / spin detected | Last 30 s telemetry, frame-by-frame replay with annotation | M | 2 |
| 8 | **Race-craft mode** | Other car detected within ~10m via GPS-other (not currently fed) | Defending lines, T11 dive-bomb awareness | L | 4 |
| 9 | **Mock interviewer** | After debrief in paddock | Gemma-driven Q&A: "What did you think of T11?" → driver self-reflects | M | 4 |

### Analysis types — what the backend computes per session

These all live in `src/pitwall/features/` as analyser modules; outputs land in DuckDB and feed both the post-session narrative and the visualization bundles.

| # | Analysis | What it measures | Data | Cost | Phase |
|---|---|---|---|---|---|
| 1 | **Corner A-F grader** | Weighted gap to gold per corner, weighted by Sonoma `LAP_TIME_LEVERAGE` | Corner passes + gold standard | S | 1 |
| 2 | **Time-loss decomposition** | Where the lap-time delta to gold actually came from: late brake (Δm), early lift (Δs), coasting (Δs), missed apex (Δkmh), exit understeer (Δkmh) | Per-corner trace + gold trace | M | 1 |
| 3 | **Highlight-moment finder** | Top-N "interesting" events per session — Sonoma-specific categories (T6 carousel oversteer, T11 bump late brake, T10 lift-when-brake-needed, perfect T4 trail brake) | Frames + phase classifier | M | 2 |
| 4 | **End-of-Braking (EoB) timing** | "Nothing time" between brake-off and throttle-on per corner; Bentley PDF p39 — best drivers reference EoB, not BoB | Brake + throttle traces | S | 1 |
| 5 | **Trail-brake score** | Detect explicit trail-brake events, score the release-rate vs gold's smoothness curve | Brake + gLat traces | S | 1 |
| 6 | **Friction-circle utilisation** | Per-corner percentage of grip envelope used; histogram of `combo_g / max_combo_g` | gLat, gLong | S | 2 |
| 7 | **Smoothness metric** | `std(steering_dot)` and `std(brake_dot)` per corner; correlates with lap time per Bentley "smooth is fast" | Steering + brake derivatives | S | 2 |
| 8 | **Hustle map** | Per-segment fraction of time at 100% throttle; flags places where "just go 100" applied (T-Rod) | Throttle | S | 2 |
| 9 | **Track-out usage** | How much of the track width the driver actually used (cross-track error in metres at apex/exit); Bentley: 1 ft off edge already shrinks the radius noticeably | GPS + reference line | M | 2 |
| 10 | **Steering-corrections counter** | Discrete steering reversals per corner; indicator of corrective driving | Steering | S | 2 |
| 11 | **Slip-angle band classifier** | Drives the driver's friction-utilisation distribution into one of 4 Bentley bands (under-driving / peak / over-driving / wear) | gLat, gLong, history | M | 3 |
| 12 | **Limit-oscillation classifier** | Bentley p42 archetypes #1 (never reaches limit), #2 (oscillates), #3 (settles); computed from cross-session corner-grade variance | DuckDB `corner_grades` | S | 3 |
| 13 | **Plateau detector** | Bentley p26 stepped-learning regions in lap-time time series; surfaces "you're on a plateau, that's normal" | DuckDB `laps` longitudinal | S | 3 |
| 14 | **Change-in-Speed problem detector** | Bentley p38 — driver entering corner below limit and adding throttle to find it (`throttle_dot > 0 AND |gLat| > 0.5G AND speed < gold_entry`) | Throttle, gLat | S | 2 |
| 15 | **Consistency analyser** | Std-dev of lap times + per-corner times; identifies "the one corner that varies most" → pre-brief input | DuckDB `corner_grades` | S | 2 |
| 16 | **Tire-wear pace degradation** | Pace drop across the stint vs first lap; surfaces "lap 7 is when your apex speeds dropped 2 km/h" | Per-lap aggregates | S | 3 |
| 17 | **Driver-style fingerprint trend** | How the existing K-Means archetype label shifts across sessions (aggressive → smoother) | `style_fingerprint.pkl` | S | 4 |
| 18 | **Black-box flight recorder** | Auto-saved last 30 s of telemetry on over-limit / off-track / spin | Combo G threshold, distance-from-reference threshold | S | 2 |

### Visualisation bundles — what the frontend gets to render

Per [ADR-013](013-frontend-backend-boundary.md), the frontend is a renderer. Every panel below is fed by a JSON endpoint the backend pre-computes.

| # | Panel | Endpoint | Phase |
|---|---|---|---|
| 1 | **Sonoma map overlay** with marker pins, danger zones, lap polylines | `GET /session/<id>/map` | 2 |
| 2 | **Per-corner A-F scorecard** | `GET /session/<id>/scorecard` | 1 |
| 3 | **Highlights reel** with auto-clipped video | `GET /session/<id>/highlights` + `GET /session/<id>/clips` | 2 |
| 4 | **Time-loss heatmap** — track segment colored by Δs to gold | included in `/map` | 2 |
| 5 | **Speed-trace overlay** — current / best-self / gold over distance | `GET /session/<id>/trace?metric=speed` | 2 |
| 6 | **Brake-trace zoom** — peak-then-taper visualisation per corner | `GET /session/<id>/trace?metric=brake&corner=T11` | 2 |
| 7 | **Friction-circle scatter** — gLat × gLong, one dot per frame | `GET /session/<id>/friction_circle?corner=T6` | 3 |
| 8 | **Hustle map** — track painted by throttle %  | included in `/map` | 2 |
| 9 | **Stat cards** — top speed, max G, max brake bar, longest 100% throttle stretch | `GET /session/<id>/stats` | 1 |
| 10 | **Consistency dot-plot** — lap times across session | included in `/scorecard` | 2 |
| 11 | **Improvement chart** — per-corner grade trends across sessions | `GET /driver/<id>/trends` | 3 |
| 12 | **Lap-delta widget** — running Δs to best/gold during a live lap | included in `/analyze` (already returns telemetry) | 2 |
| 13 | **Replay-with-ghost** — current lap visualised next to a position-synced gold-lap car | `GET /session/<id>/ghost?lap=N` | 3 |
| 14 | **Bentley/T-Rod page citation** — when a concept fires, frontend renders the source page from the PDF / transcript | `GET /coach/concepts/<id>/citation` | 3 |
| 15 | **Pre-brief card** — paragraph + 3 focus items + weather note | `GET /coach/brief?driver=...` | 3 |
| 16 | **Pit-board view** — terse, glanceable, designed for the dashboard mount | derived from `/scorecard` and the live `/analyze` stream | 4 |

### Engagement / longitudinal features

| # | Feature | Notes | Cost | Phase |
|---|---|---|---|---|
| 1 | **Pick-3 focus markers** | Driver selects 3 corners from the Sonoma map; all coaching weights toward those for the session | S | 2 |
| 2 | **Personal-record alerts** | "New best apex speed at T6" — fires in-paddock, not on track | S | 2 |
| 3 | **Streak tracker** | "T11 graded B+ in 4 consecutive sessions" | S | 3 |
| 4 | **Pod leaderboard** | Per-pod best lap + per-corner leaders; reads from cross-driver DuckDB | M | 3 |
| 5 | **Daily drill** | Backend chooses one corner per session based on event-sourced profile; coach mutes everything else | S | 3 |
| 6 | **Auto-narrated session video** | Stitch dashcam clips at highlight cut points + TTS narrative; produces a shareable mp4 | L | 4 |
| 7 | **External video import** | Upload someone else's coaching video, sync to telemetry by IMU-spike at T6 (per `RIG_NOTES.video_sync_marker`) | M | 4 |
| 8 | **Multi-driver session compare** | Same car, different drivers in the same session; side-by-side scorecard | M | 4 |
| 9 | **Coach handoff** | Human coach overrides AI for specific corners; surfaces in the post-debrief | S | 4 |
| 10 | **Voice query** | "Coach, am I close to the limit at T10?" — needs ASR (out of scope for May 23) | L | 4 |

### Cross-cutting: data we can derive but don't yet expose

These are quick wins — the data is already in DuckDB; the analyser just needs to run.

- **`max_combo_g_per_corner`** — diagnostic for grip headroom.
- **`coast_seconds_per_lap`** — Bentley's #1 wasted-time metric; already in driving-phase distribution but not surfaced per-driver.
- **`brake_press_consistency`** — std-dev of peak brake pressure per corner across the session.
- **`gear_choice_evidence`** — RPM vs speed traces show implicit gear; flag when gear differs from gold (e.g. "you used 4th in T2; gold uses 3rd").
- **`steering_lock_event`** — `|steering_dot|` spikes flag corrective steering, useful for understeer / oversteer post-mortem.
- **`throttle_application_rate`** — `dThrottle/dt` at corner exit; T-Rod called this out specifically as a focus area.

---

## Related

- [ADR-005 — Pedagogical Vector Retrieval](005-pedagogical-vectors.md) — the curriculum applies to any track; the *materialised* vectors live per-track.
- [ADR-007 — Event-Sourced Driver Profile](007-event-sourced-profile.md) — pre-brief and "improvement vs last session" both read from the event store specified there.
- [ADR-010 — HTTP Bridge as Warm-Path Tier 1](010-http-bridge-warm-path.md) — every new endpoint lands here.
- [ADR-011 — Named-Marker Schema](011-named-marker-schema.md) — markers gain GPS coordinates derived from `sonoma_real_gps.json`.
- [ADR-012 — Coach Engine Adapter](012-coach-engine-adapter.md) — `LitertCoach` is the engine for all three modes.
- [ADR-013 — Frontend Visualises, Backend Reasons](013-frontend-backend-boundary.md) — every JSON bundle in this ADR is shaped for that contract.
- [Sonoma Track Intelligence](../sonoma_track_intelligence.md), [T-Rod Sonoma Session](../trod_sonoma_session.md), [Track Markers](../markers.md) — source material for the hardcoded Sonoma knowledge.

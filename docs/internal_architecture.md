# Internal Architecture

This is the **as-shipped** view of the Python backend (post 2026-04-28). [`architecture.md`](architecture.md) is the original sprint-design diagram (split-brain hot/warm path conceptually); this doc shows what the code actually does today, with mermaid diagrams generated against the live codebase.

---

## High-level system

The Python backend is the source of truth. The Vue PWA at `src/pwa/` is the production renderer (per [ADR-016](adr/016-can-bus-ingest-and-frontend-pivot.md); the v1 Flutter + Kotlin app referenced in [ADR-013](adr/013-frontend-backend-boundary.md) was removed in PR #32). All LLM logic, system prompts, and analytics live in `src/pitwall/features/`. The bridge (`src/pitwall/__main__.py`) exposes them over HTTP.

```mermaid
flowchart LR
  subgraph SENSORS["📡 Sensors (on-car)"]
    RL[Racelogic Mini<br/>10 Hz GPS+IMU<br/>VBO format]
    OBD[USB-CAN Adapter<br/>CAN brake/throttle/RPM]
    CAM[Pixel dashcam<br/>MP4 chunks]
  end

  subgraph BRIDGE["🌉 src/pitwall/ — 56 endpoints"]
    direction TB
    INGEST["/session/&lt;id&gt;/frames<br/>/session/&lt;id&gt;/video_frames<br/>/analyze (burst)"]
    QUERY["/session/&lt;id&gt;/scorecard<br/>/highlights /map /sync<br/>/coach/brief /debrief"]
    META["/track/markers<br/>/track/danger_zones<br/>/track/weather"]
  end

  subgraph BACKEND["🐍 src/pitwall/features/ — analytics + coach"]
    direction TB
    SONOMA[(sonoma.py<br/>hardcoded constants)]
    GRADER[corner_grader.py<br/>A-F + time-loss]
    ANALYTICS[analytics.py<br/>13 analysers]
    HIGHLIGHTER[highlight_finder.py<br/>7 Sonoma categories]
    ANALYZER[session_analyzer.py<br/>orchestrator]
    COACH[coaching/<br/>rule_coach + litert_coach +<br/>arbiter + prompts]
    GOLD[(gold_standard.py<br/>per-corner reference)]
    PROFILE[(driver_profile.py<br/>event-sourced)]
  end

  subgraph STORE["💾 DuckDB (single-process source of truth)"]
    direction TB
    T_SESSIONS[(sessions)]
    T_LAPS[(laps)]
    T_FRAMES[(telemetry)]
    T_VIDEO[(video_frames)]
    T_NOTES[(coaching_notes)]
    T_EVENTS[(driver_events)]
  end

  subgraph FRONTEND["🌐 Vue PWA (src/pwa/) — renderer only"]
    HUD[on-track HUD]
    PADDOCK[paddock review]
    MAP[Mapbox/Maplibre overlay]
  end

  subgraph DATA["📂 data/"]
    TRACK_JSON[/sonoma.json<br/>+ markers + tips/]
    REAL_GPS[/sonoma_real_gps.json<br/>OSM-derived/]
    GOLD_REF[/sonoma_gold.json<br/>+ trace.json/]
    THUMBS[/markers/sonoma/*.jpg/]
  end

  RL --> INGEST
  OBD --> INGEST
  CAM --> INGEST
  INGEST --> T_FRAMES & T_VIDEO & T_NOTES & T_LAPS
  INGEST --> COACH
  COACH --> SONOMA
  COACH --> ANALYZER
  ANALYZER --> GRADER & ANALYTICS & HIGHLIGHTER & GOLD & PROFILE
  ANALYZER --> COACH
  GRADER --> SONOMA
  HIGHLIGHTER --> SONOMA
  PROFILE <--> T_EVENTS
  GOLD <-- reads --> GOLD_REF
  SONOMA <-- reads --> TRACK_JSON
  QUERY --> ANALYZER
  QUERY --> META
  META --> SONOMA
  QUERY --> FRONTEND
  MAP <-- real GPS --> REAL_GPS
  MAP <-- markers + thumbs --> THUMBS

  classDef store fill:#1a3a52,stroke:#4a6e8a,color:#e0e0e0
  classDef code fill:#2e5d3a,stroke:#5a8a6e,color:#e0e0e0
  classDef sensor fill:#5d4a1a,stroke:#8a6e3a,color:#e0e0e0
  classDef ui fill:#5d1a3a,stroke:#8a3a5e,color:#e0e0e0
  classDef data fill:#3a3a3a,stroke:#6e6e6e,color:#e0e0e0
  class T_SESSIONS,T_LAPS,T_FRAMES,T_VIDEO,T_NOTES,T_EVENTS,SONOMA,GOLD,PROFILE store
  class GRADER,ANALYTICS,HIGHLIGHTER,ANALYZER,COACH,INGEST,QUERY,META code
  class RL,OBD,CAM sensor
  class HUD,PADDOCK,MAP ui
  class TRACK_JSON,REAL_GPS,GOLD_REF,THUMBS data
```

---

## Module dependency graph (`src/pitwall/features/`)

The `coaching/` slice was split into focused modules in PR #30. `coach_engine` is now a back-compat re-export shim — old imports (`from pitwall.features.coaching.coach_engine import …`) keep working.

```mermaid
graph TD
  sonoma[track/sonoma.py<br/>constants + lore]
  vbo[session/vbo_parser.py<br/>VBO → frames]
  track[track/track_loader.py<br/>JSON → TrackMap]
  trackjson[track/track_json.py<br/>raw JSON loader + corner bounds]
  gold[track/gold_standard.py<br/>per-corner reference]
  grader[session/corner_grader.py<br/>A-F + time-loss]
  analytics[session/analytics.py<br/>smoothness / friction / etc.]
  hl[session/highlight_finder.py<br/>moments]
  profile[session/driver_profile.py<br/>events]
  laps[session/laps.py<br/>detect_laps + sectors + new_session_id]
  frames[session/frames.py<br/>frames↔rows + load_session_frames]
  analyzer[session/session_analyzer.py<br/>orchestrator]
  enginebase[coaching/engine_base.py<br/>CoachContext / CoachEngine / friction sink]
  prompts[coaching/prompts.py<br/>system + user prompt builders]
  pedagogy[coaching/pedagogy.py<br/>Bentley concept matcher + rule registry]
  rule[coaching/rule_coach.py<br/>templated zero-dep coach]
  litert[coaching/litert_coach.py<br/>HTTP + in-process LiteRT-LM]
  arbiter[coaching/arbiter.py<br/>P1/P2/P3 cooldown gate]
  cuerender[coaching/cue_renderer.py<br/>sonic cues → coaching string]
  sonic[coaching/sonic_model.py<br/>rule-driven cues]

  vbo --> gold
  track --> gold
  vbo --> analyzer
  track --> analyzer
  frames --> analyzer
  laps --> analyzer
  sonoma --> grader
  gold --> grader
  grader --> analyzer
  sonoma --> analytics
  grader --> analytics
  analytics --> analyzer
  sonoma --> hl
  grader --> hl
  gold --> hl
  hl --> analyzer
  profile --> analyzer
  analyzer --> rule
  analyzer --> litert
  enginebase --> rule
  enginebase --> litert
  prompts --> litert
  prompts --> rule
  pedagogy --> rule
  pedagogy --> litert
  arbiter --> rule
  arbiter --> litert
  cuerender --> sonic
  sonoma -.imported via.-> rule
  trackjson --> grader

  classDef hot fill:#5d2a1a,stroke:#8a4e3a,color:#e0e0e0
  classDef warm fill:#1a4a5d,stroke:#3a6e8a,color:#e0e0e0
  classDef data fill:#1a3a52,stroke:#4a6e8a,color:#e0e0e0
  class rule,litert,grader,hl,analytics,arbiter warm
  class sonic,sonoma,cuerender hot
  class profile,gold,track,trackjson,vbo,laps,frames data
```

Removed in PR #30 (dead code): `audio_engine.py`, `lstm_predictor.py`, `lstm_predictor_v3.py`, `sequence_predictor.py`, `sonic_model_v2.py`, `track_map.py`, and the top-level `helpers.py`. The promoted home of every helper:

| Old | New |
|---|---|
| `helpers.py:_detect_laps` | `features/session/laps.py:detect_laps` |
| `helpers.py:_lap_sectors` | `features/session/laps.py:lap_sectors` |
| `helpers.py:_new_session_id` | `features/session/laps.py:new_session_id` |
| `helpers.py:_quantile` | `features/session/laps.py:quantile` |
| `helpers.py:_frames_to_rows` / `_rows_to_frames` | `features/session/frames.py:frames_to_rows` / `rows_to_frames` |
| `helpers.py:_load_session_frames` | `features/session/frames.py:load_session_frames` |
| `helpers.py:_cues_to_coaching` / `_sonic_coaching` / `_rule_coaching` / `_estimate_tts_ms` | `features/coaching/cue_renderer.py:cues_to_coaching` / `sonic_coaching` / `rule_coaching` / `estimate_tts_ms` |
| `helpers.py:_load_track_json` / `_corner_bounds_from_track` | `features/track/track_json.py:load_track_json` / `corner_bounds_from_track` |

---

## DuckDB schema

```mermaid
erDiagram
  SESSIONS ||--o{ LAPS : "has many"
  SESSIONS ||--o{ TELEMETRY : "has many"
  SESSIONS ||--o{ VIDEO_FRAMES : "has many"
  SESSIONS ||--o{ COACHING_NOTES : "has many"
  SESSIONS {
    string session_id PK
    string driver
    string driver_level
    string track
    string car
    timestamp started_at
    timestamp ended_at
    string note
  }
  LAPS {
    int id PK
    string session_id FK
    int lap_number
    double lap_time_s
    double best_sector
    double avg_speed_kmh
    double max_combo_g
    double coast_pct
    timestamp recorded_at
  }
  TELEMETRY {
    string session_id FK
    int frame_idx PK
    double timestamp
    double distance_m
    double speed_ms
    double g_lat
    double g_long
    double combo_g
    double brake_bar
    double throttle_pct
    double steering_deg
    double rpm
    double lat
    double lon
  }
  VIDEO_FRAMES {
    string session_id FK
    double timestamp
    bigint avitime_ms
    string file_path
    double file_offset_s
    int width
    int height
  }
  COACHING_NOTES {
    int id PK
    string session_id FK
    int burst_id
    double distance_m
    string text
    string source
    timestamp recorded_at
  }
  DRIVER_EVENTS {
    int id PK
    string driver_id
    string session_id FK
    string corner
    string event_kind
    double value_num
    string value_str
    timestamp recorded_at
  }
```

`session_id` is the universal join key. `timestamp` (epoch seconds) is the universal clock for telemetry × video sync.

---

## Three coaching modes

```mermaid
flowchart TB
  classDef pre fill:#1a4a5d,stroke:#3a6e8a,color:#e0e0e0
  classDef during fill:#5d2a1a,stroke:#8a4e3a,color:#e0e0e0
  classDef post fill:#2e5d3a,stroke:#5a8a6e,color:#e0e0e0
  classDef shared fill:#3a3a3a,stroke:#6e6e6e,color:#e0e0e0

  subgraph PRE["🟦 PRE_BRIEF — paddock, before session"]
    direction LR
    PRE_IN["GET /coach/brief<br/>?driver=&date=<br/>&focus=T4,T7,T11"]
    PRE_PROFILE[driver_profile<br/>compute_profile]
    PRE_WX[sonoma.<br/>weather_phase_for_hour]
    PRE_LLM[LitertCoach.brief<br/>~150 words<br/>≤300 tokens]
    PRE_OUT[narrative_md +<br/>3 focus items]
    PRE_IN --> PRE_PROFILE & PRE_WX --> PRE_LLM --> PRE_OUT
  end

  subgraph DURING["🟥 DURING_DRIVE — every burst (7.5s)"]
    direction LR
    DUR_IN["POST /analyze<br/>{burst summary}"]
    DUR_CTX[build_context<br/>+ marker lookup]
    DUR_BENTLEY[match_<br/>bentley_concept]
    DUR_PROPOSE[coach.propose<br/>≤14 words]
    DUR_ARB[CoachArbiter<br/>P3/P2/P1 + cooldown 3s]
    DUR_OUT[pace_note +<br/>cues + coaching]
    DUR_NOTES[(coaching_notes)]
    DUR_IN --> DUR_CTX --> DUR_BENTLEY --> DUR_PROPOSE --> DUR_ARB --> DUR_OUT
    DUR_OUT --> DUR_NOTES
  end

  subgraph POST["🟩 POST_SESSION — paddock, after session"]
    direction LR
    POST_IN["POST /coach/debrief<br/>{session_id}"]
    POST_FR[(load frames<br/>from telemetry)]
    POST_GR[corner_grader<br/>A-F + Δt loss]
    POST_AN[analytics<br/>13 metrics]
    POST_HL[highlight_finder<br/>top 8 moments]
    POST_LLM[LitertCoach.debrief<br/>~300 words]
    POST_BUNDLE[Visualization<br/>bundle JSON]
    POST_EVENTS[(driver_events)]
    POST_IN --> POST_FR --> POST_GR & POST_AN & POST_HL --> POST_LLM --> POST_BUNDLE
    POST_GR --> POST_EVENTS
  end

  SHARED[(coaching/prompts.py<br/>build_system_prompt<br/>+ build_user_prompt<br/>+ sonoma.SYSTEM_PROMPT_LORE)]:::shared
  PRE_LLM -.uses.-> SHARED
  DUR_PROPOSE -.uses.-> SHARED
  POST_LLM -.uses.-> SHARED

  class PRE,PRE_IN,PRE_PROFILE,PRE_WX,PRE_LLM,PRE_OUT pre
  class DURING,DUR_IN,DUR_CTX,DUR_BENTLEY,DUR_PROPOSE,DUR_ARB,DUR_OUT,DUR_NOTES during
  class POST,POST_IN,POST_FR,POST_GR,POST_AN,POST_HL,POST_LLM,POST_BUNDLE,POST_EVENTS post
```

---

## Session lifecycle (sequence)

```mermaid
sequenceDiagram
  participant App as Vue PWA
  participant Bridge as bridge :8765
  participant Coach as coach_engine
  participant DB as DuckDB
  participant Analyzer as session_analyzer

  Note over App,DB: Pre-session
  App->>Bridge: POST /session/start
  Bridge->>DB: INSERT INTO sessions
  Bridge-->>App: {session_id}

  App->>Bridge: GET /coach/brief?driver=...
  Bridge->>DB: SELECT events for driver
  Bridge->>Coach: brief(driver, focus, weather)
  Coach-->>Bridge: narrative + 3 focus
  Bridge-->>App: pre-brief bundle

  Note over App,DB: During session (every 7.5s)
  loop For each burst
    App->>Bridge: POST /session/&lt;id&gt;/frames {batch}
    Bridge->>DB: INSERT INTO telemetry
    App->>Bridge: POST /session/&lt;id&gt;/video_frames {meta}
    Bridge->>DB: INSERT INTO video_frames
    App->>Bridge: POST /analyze {burst}
    Bridge->>Coach: propose(ctx)
    Coach-->>Bridge: pace_note
    Bridge->>DB: INSERT INTO coaching_notes
    Bridge-->>App: {pace_note, cues, coaching}
  end

  Note over App,DB: End of session
  App->>Bridge: POST /session/&lt;id&gt;/end
  Bridge->>DB: UPDATE sessions SET ended_at

  App->>Bridge: POST /coach/debrief {session_id}
  Bridge->>Analyzer: analyze_session(sid)
  Analyzer->>DB: SELECT * FROM telemetry WHERE session_id
  Analyzer->>Analyzer: grade + analyze + find highlights
  Analyzer->>Coach: debrief(bundle)
  Coach-->>Analyzer: narrative + next_focus
  Analyzer-->>Bridge: bundle JSON
  Bridge->>DB: INSERT into driver_events (longitudinal)
  Bridge-->>App: bundle

  Note over App,DB: Off-track review
  App->>Bridge: GET /session/&lt;id&gt;/scorecard
  Bridge-->>App: A-F per corner

  App->>Bridge: GET /session/&lt;id&gt;/sync?from=&to=
  Bridge->>DB: JOIN telemetry × video_frames on time
  Bridge-->>App: telemetry + video offsets

  App->>Bridge: GET /session/&lt;id&gt;/highlights
  Bridge-->>App: 8 ranked moments + clip cuts
```

---

## Coach-engine internals

```mermaid
classDiagram
  class CoachEngine {
    <<interface>>
    +str name
    +propose(ctx CoachContext) CoachingMessage
  }
  class RuleCoach {
    +str driver_level
    -_render(ctx) str
  }
  class LitertCoach {
    +str driver_level
    -LlmInference _llm
    -RuleCoach _fallback
    +health() dict
    +brief(args) tuple
    +debrief(bundle) tuple
    -_infer(ctx) str
    -_generate(sys, usr) str
  }
  class CoachContext {
    +str driver_level
    +str track_name
    +str next_corner_name
    +str next_brake_marker_label
    +str next_corner_tip
    +float meters_to_entry
    +str bentley_concept
  }
  class CoachingMessage {
    +str text
    +int priority
    +str layer
  }
  class CoachArbiter {
    +float cooldown_s
    +float stale_s
    +submit(msg, now, on_straight) Optional[CoachingMessage]
  }
  class CoachMode {
    <<enum>>
    DURING_DRIVE
    PRE_BRIEF
    POST_SESSION
  }
  CoachEngine <|-- RuleCoach
  CoachEngine <|-- LitertCoach
  LitertCoach o-- RuleCoach : fallback
  CoachEngine ..> CoachContext : consumes
  CoachEngine ..> CoachingMessage : produces
  CoachArbiter ..> CoachingMessage : gates
  LitertCoach ..> CoachMode : uses
```

`make_coach(kind="auto"|"litert"|"rule")` is the factory. `auto` tries `LitertCoach`; if MediaPipe isn't installed or the `.task` file is missing, it falls back to `RuleCoach`. `LitertCoach` itself also falls back per-call when its runtime fails — calling code can always rely on getting *something* back.

---

## Bridge endpoint topology

```mermaid
flowchart LR
  classDef coach fill:#5d2a1a,stroke:#8a4e3a,color:#e0e0e0
  classDef sess fill:#1a4a5d,stroke:#3a6e8a,color:#e0e0e0
  classDef telem fill:#2e5d3a,stroke:#5a8a6e,color:#e0e0e0
  classDef analyze fill:#5d4a1a,stroke:#8a6e3a,color:#e0e0e0
  classDef meta fill:#3a3a3a,stroke:#6e6e6e,color:#e0e0e0

  subgraph C["coaching"]
    direction TB
    H[GET /health]
    A[POST /analyze]
    BR[GET /coach/brief]
    DB[POST /coach/debrief]
  end

  subgraph S["sessions"]
    direction TB
    SLIST[GET /sessions]
    SSTART[POST /session/start]
    SDETAIL[GET /session/&lt;id&gt;]
    SEND[POST /session/&lt;id&gt;/end]
  end

  subgraph T["telemetry + video"]
    direction TB
    FRAMES[POST /session/&lt;id&gt;/frames]
    VFRAMES[POST /session/&lt;id&gt;/video_frames]
    SYNC[GET /session/&lt;id&gt;/sync]
    LAP[POST /lap]
    LAPS[GET /laps]
  end

  subgraph V["analysis bundles"]
    direction TB
    SC[GET /session/&lt;id&gt;/scorecard]
    HL[GET /session/&lt;id&gt;/highlights]
    ST[GET /session/&lt;id&gt;/stats]
    FC[GET /session/&lt;id&gt;/friction_circle]
    HM[GET /session/&lt;id&gt;/hustle_map]
    EOB[GET /session/&lt;id&gt;/eob]
    INC[GET /session/&lt;id&gt;/incidents]
    MAP[GET /session/&lt;id&gt;/map]
    CL[GET /session/&lt;id&gt;/clips]
  end

  subgraph LP["lap-performance &amp; analysis (Phase 6)"]
    direction TB
    LT1[GET /session/&lt;id&gt;/lap_time_table]
    LT2[GET /session/&lt;id&gt;/lap_time_distribution]
    IL[GET /session/&lt;id&gt;/ideal_lap]
    ST2[GET /session/&lt;id&gt;/sector_times]
    PB[GET /session/&lt;id&gt;/pedal_behavior]
    TCB[GET /session/&lt;id&gt;/throttle_corner_box]
    CC[GET /session/&lt;id&gt;/corner_classification]
    SLS[GET /session/&lt;id&gt;/straight_line_speed]
    BA[GET /session/&lt;id&gt;/brake_acceleration]
  end

  subgraph M["track + driver metadata"]
    direction TB
    TM[GET /track/&lt;id&gt;/markers]
    TD[GET /track/&lt;id&gt;/danger_zones]
    TW[GET /track/&lt;id&gt;/weather]
    TE[GET /track/&lt;id&gt;/elevation]
    DP[GET /driver/&lt;id&gt;/profile]
    DE[GET /driver/&lt;id&gt;/evolution]
  end

  class H,A,BR,DB coach
  class SLIST,SSTART,SDETAIL,SEND sess
  class FRAMES,VFRAMES,SYNC,LAP,LAPS telem
  class SC,HL,ST,FC,HM,EOB,INC,MAP,CL analyze
  class LT1,LT2,IL,ST2,PB,TCB,CC,SLS,BA analyze
  class TM,TD,TW,TE,DP,DE meta
```

---

## File tree (FSD Migration)

```
pitwall/
├── data/
│   ├── reference/
│   │   ├── sonoma_gold.json          (per-corner gold)
│   │   └── sonoma_gold_trace.json    (986-frame trace)
│   ├── markers/sonoma/
│   │   ├── manifest.json             (16 thumbnail cut points)
│   │   └── *.jpg                     (when ffmpeg run)
│   └── tracks/
│       ├── sonoma.json               (canonical, w/ markers + GPS)
│       ├── sonoma_real_gps.json      (OSM real coords)
│       ├── sonoma.json.bak
│       └── training_data/
│           ├── track2.json           (ML-only, not deployed)
│           └── track8.json
├── docs/                              (mkdocs site)
│   ├── architecture.md                (sprint design — concept)
│   ├── internal_architecture.md       (this file — code)
│   ├── api.md                         (endpoint reference)
│   └── ...
├── src/
│   ├── pitwall/
│   │   ├── __main__.py                (Flask app, 56 endpoints)
│   │   ├── db.py                      (db_conn() context mgr + DuckDbUnavailable; init_schema_once() at boot)
│   │   ├── state.py                   (process-state holder; no longer stores function pointers — callers import directly)
│   │   └── features/                  (Feature-Sliced Design)
│   │       ├── telemetry/             (can_reader, signals API)
│   │       ├── session/               (analyzer, profiles, debrief, laps.py, frames.py)
│   │       ├── coaching/              (engine_base, prompts, pedagogy, rule_coach, litert_coach,
│   │       │                           arbiter, cue_renderer, ADK agents — coach_engine.py is a
│   │       │                           back-compat shim re-exporting public symbols)
│   │       ├── track/                 (sonoma, track_loader, track_json, gold_standard)
│   │       └── realtime/              (live cue streaming via SSE)
│   └── simulator/
│       ├── pitwall_app.py             (TUI / replay)
│       ├── simulator.py               (VBO-driven simulation)
│       └── can_simulator.py           (CAN bus synthetic playback)
├── tests/
│   └── features/                      (Modularized tests mirroring FSD)
└── scripts/
    ├── enrich_sonoma_track.py
    ├── extract_gold_lap.py
    ├── best_sonoma_lap.py             (S/F line-projection)
    ├── import_sonoma_real_gps.py      (OSM Overpass)
    ├── extract_marker_thumbnails.py
    └── validate_litert.py             (Pixel-side smoke)
```

---

## Lap-performance & analysis pipeline (Phase 6)

The 11 new analysis endpoints all share the same back-end shape: they read frames from `telemetry`, slice them into laps using S/F-line projection, compute per-lap or per-corner aggregates, and return a JSON envelope ready for chart rendering. The frontend never touches raw frames for these views.

```mermaid
flowchart LR
  classDef ingest fill:#5d4a1a,stroke:#8a6e3a,color:#e0e0e0
  classDef store fill:#1a3a52,stroke:#4a6e8a,color:#e0e0e0
  classDef detect fill:#5d2a1a,stroke:#8a4e3a,color:#e0e0e0
  classDef agg fill:#2e5d3a,stroke:#5a8a6e,color:#e0e0e0
  classDef api fill:#1a4a5d,stroke:#3a6e8a,color:#e0e0e0
  classDef ui fill:#5d1a3a,stroke:#8a3a5e,color:#e0e0e0

  IN[VBO / live frames]:::ingest
  TEL[(telemetry table)]:::store
  LAPS[(laps table)]:::store

  LAPDET[lap_detector<br/>S/F sign-change<br/>+ outlier filter]:::detect
  SECDET[sector_splitter<br/>boundaries from<br/>sonoma.SECTORS]:::detect
  CORNDET[corner_pass_detector<br/>per-corner intervals<br/>from track JSON]:::detect

  AGG_LAP[lap_time aggregator<br/>min/median/quantiles]:::agg
  AGG_PEDAL[pedal_state classifier<br/>4-state thresholds]:::agg
  AGG_BAND[corner_band classifier<br/>apex-speed banding]:::agg
  AGG_BOX[throttle box-plot<br/>per-corner Tukey]:::agg
  AGG_BRK[brake_accel aggregator<br/>heavy-decel runs]:::agg
  AGG_STR[straight-speed aggregator<br/>max v in window]:::agg
  AGG_ELEV[elevation_sampler<br/>centerline interp]:::agg

  E1["/session/&lt;id&gt;/lap_time_table"]:::api
  E2["/session/&lt;id&gt;/lap_time_distribution"]:::api
  E3["/session/&lt;id&gt;/ideal_lap"]:::api
  E4["/session/&lt;id&gt;/sector_times"]:::api
  E5["/session/&lt;id&gt;/pedal_behavior"]:::api
  E6["/session/&lt;id&gt;/throttle_corner_box"]:::api
  E7["/session/&lt;id&gt;/corner_classification"]:::api
  E8["/session/&lt;id&gt;/straight_line_speed"]:::api
  E9["/session/&lt;id&gt;/brake_acceleration"]:::api
  E10["/track/&lt;id&gt;/elevation"]:::api
  E11["/driver/&lt;id&gt;/evolution"]:::api

  FE[Vue PWA charts<br/>box-plots, line charts,<br/>track-map overlays]:::ui

  IN --> TEL
  TEL --> LAPDET --> LAPS
  TEL --> SECDET
  TEL --> CORNDET
  LAPS --> AGG_LAP
  SECDET --> AGG_LAP
  TEL --> AGG_PEDAL
  CORNDET --> AGG_BAND & AGG_BOX & AGG_BRK
  TEL --> AGG_STR
  TEL --> AGG_ELEV

  AGG_LAP --> E1 & E2 & E3 & E4
  AGG_PEDAL --> E5
  AGG_BOX --> E6
  AGG_BAND --> E7
  AGG_STR --> E8
  AGG_BRK --> E9
  AGG_ELEV --> E10
  AGG_LAP --> E11
  AGG_BAND --> E11

  E1 & E2 & E3 & E4 & E5 & E6 & E7 & E8 & E9 & E10 & E11 --> FE
```

The `lap_detector` runs once per session and persists boundaries into the existing `laps` table (no new schema). The aggregators are pure functions over telemetry rows + lap boundaries — no global state, easy to test.

---

## Pedal-state classifier (4-state model)

Every frame's `(throttle_pct, brake_bar)` pair maps deterministically to exactly one of four states. `pedal_behavior` returns the distribution; `lap_time_table` and `ideal_lap` use the same classifier internally for sector "trail-brake fraction" annotations.

```mermaid
flowchart TB
  classDef state fill:#1a4a5d,stroke:#3a6e8a,color:#e0e0e0
  classDef axis fill:#3a3a3a,stroke:#6e6e6e,color:#e0e0e0

  F[frame<br/>&#40;throttle_pct, brake_bar&#41;]
  T{throttle_pct &gt; 5%}:::axis
  B1{brake_bar &gt; 1.0}:::axis
  B2{brake_bar &gt; 1.0}:::axis

  TR[trail_brake<br/>both pedals modulating]:::state
  TO[throttle_only<br/>cruise / WOT]:::state
  BO[brake_only<br/>pure stopping]:::state
  CO[coast<br/>off both pedals — alarm]:::state

  F --> T
  T -- yes --> B1
  T -- no --> B2
  B1 -- yes --> TR
  B1 -- no --> TO
  B2 -- yes --> BO
  B2 -- no --> CO
```

Thresholds chosen for road-car drivers (5% / 1 bar). F1 telemetry uses 95% / 5 bar — too aggressive for the Sonoma track-day audience and would classify almost every frame as "coast".

---

## Corner-classification banding

Each corner's apex speed determines its band. The endpoint groups corners and reports per-band stats so the coach can say "you're a low-speed driver, focus on T7/T11".

```mermaid
flowchart LR
  classDef low fill:#5d2a1a,stroke:#8a4e3a,color:#e0e0e0
  classDef med fill:#5d4a1a,stroke:#8a6e3a,color:#e0e0e0
  classDef high fill:#2e5d3a,stroke:#5a8a6e,color:#e0e0e0

  C[corner pass<br/>frames]
  AP[apex_speed = min&#40;v_f&#41;]
  D{apex band}

  L[low_speed<br/>&lt; 80 km/h<br/>T7, T11]:::low
  M[med_speed<br/>80–130 km/h<br/>T1, T2, T3a, T4, T8a, T9]:::med
  H[high_speed<br/>≥ 130 km/h<br/>T6, T10]:::high

  C --> AP --> D
  D -- low --> L
  D -- med --> M
  D -- high --> H
```

Thresholds are query-tunable (`?low_max=80&med_max=130`) so bench analysts can re-classify without redeploying.

---

## Multi-track parameterisation

The bridge currently hardcodes Sonoma per [ADR-014](adr/014-sonoma-as-the-product.md), but the new `/track/<id>/*` route shape lets us add tracks **without code changes** — drop a JSON in `data/tracks/` and the loader resolves it on demand.

```mermaid
flowchart LR
  classDef req fill:#5d2a1a,stroke:#8a4e3a,color:#e0e0e0
  classDef router fill:#1a4a5d,stroke:#3a6e8a,color:#e0e0e0
  classDef cache fill:#5d4a1a,stroke:#8a6e3a,color:#e0e0e0
  classDef data fill:#2e5d3a,stroke:#5a8a6e,color:#e0e0e0
  classDef err fill:#5d1a3a,stroke:#8a3a5e,color:#e0e0e0

  REQ["GET /track/&lt;id&gt;/elevation<br/>GET /track/&lt;id&gt;/markers<br/>GET /track/&lt;id&gt;/danger_zones"]:::req
  ROUTER[Flask router<br/>extracts &lt;id&gt;]:::router
  CACHE["_track_cache: dict&lt;id, TrackMap&gt;"]:::cache
  HIT{cache hit?}
  LOAD[track_loader.load_track<br/>data/tracks/&lt;id&gt;.json]:::router
  EXIST{file exists?}

  D1[/data/tracks/sonoma.json/]:::data
  D2[/data/tracks/laguna_seca.json<br/>future/]:::data
  D3[/data/tracks/road_atlanta.json<br/>future/]:::data

  E404[404 Not Found<br/>track id unknown]:::err
  RESP[200 OK<br/>JSON response]:::router

  REQ --> ROUTER --> HIT
  HIT -- yes --> RESP
  HIT -- no --> EXIST
  EXIST -- yes --> LOAD --> CACHE --> RESP
  EXIST -- no --> E404
  LOAD -.reads.-> D1
  LOAD -.future.-> D2
  LOAD -.future.-> D3
```

The cache lives in-process (the bridge is single-process by design — see [ADR-010](adr/010-http-bridge-warm-path.md)). Track JSONs are small (10–50 KB each) so an LRU isn't needed.

---

## Driver evolution pipeline (multi-session)

`/driver/<id>/evolution` is the only endpoint that joins data **across sessions**. It reads from the existing `sessions`, `laps`, `telemetry`, and `driver_events` tables — no new tables needed.

```mermaid
flowchart TB
  classDef store fill:#1a3a52,stroke:#4a6e8a,color:#e0e0e0
  classDef proc fill:#2e5d3a,stroke:#5a8a6e,color:#e0e0e0
  classDef api fill:#1a4a5d,stroke:#3a6e8a,color:#e0e0e0
  classDef ui fill:#5d1a3a,stroke:#8a3a5e,color:#e0e0e0

  SESS[(sessions<br/>WHERE driver=? AND track=?)]:::store
  LAPS[(laps)]:::store
  TEL[(telemetry)]:::store
  EVT[(driver_events)]:::store

  ORDER[order by started_at ASC<br/>assign session_index]:::proc
  PER_SESS[per-session aggregator<br/>best_lap, median_lap,<br/>sector_pbs, lap_count]:::proc
  CORNER_EVOL[per-corner regression<br/>apex_speed vs session_index<br/>linear least-squares]:::proc
  SUMMARY[summary builder<br/>improvement_s,<br/>biggest_corner_gain]:::proc
  GUARD{session_count<br/>≥ 5?}

  R204[204 No Content<br/>need more sessions]:::api
  R200[200 OK<br/>evolution + summary]:::api

  CHART[Vue PWA line chart<br/>+ hero card]:::ui

  SESS --> ORDER --> PER_SESS
  LAPS --> PER_SESS
  TEL --> CORNER_EVOL
  EVT --> CORNER_EVOL
  PER_SESS --> SUMMARY
  CORNER_EVOL --> SUMMARY
  SUMMARY --> GUARD
  GUARD -- no --> R204
  GUARD -- yes --> R200
  R200 --> CHART
  R204 --> CHART
```

The 5-session minimum is a noise floor — single-session drivers always look like outliers in a regression. The empty-state UI (`204`) tells the frontend to render a "you need 3 more sessions to unlock evolution" placeholder instead of a misleading chart.

---

## Comprehensive backend topology

The full as-shipped picture, including Phase 6. Every node is a real module or table; every edge a real call or query.

```mermaid
flowchart TB
  classDef sensor fill:#5d4a1a,stroke:#8a6e3a,color:#e0e0e0
  classDef bridge fill:#1a4a5d,stroke:#3a6e8a,color:#e0e0e0
  classDef sim fill:#2e5d3a,stroke:#5a8a6e,color:#e0e0e0
  classDef store fill:#1a3a52,stroke:#4a6e8a,color:#e0e0e0
  classDef tools fill:#5d2a1a,stroke:#8a4e3a,color:#e0e0e0
  classDef ui fill:#5d1a3a,stroke:#8a3a5e,color:#e0e0e0
  classDef data fill:#3a3a3a,stroke:#6e6e6e,color:#e0e0e0

  subgraph SENSORS["📡 Sensors"]
    RL[Racelogic VBO<br/>10 Hz]:::sensor
    OBD[USB-CAN Adapter]:::sensor
    CAM[Pixel dashcam]:::sensor
  end

  subgraph TOOLS["🛠 scripts/"]
    BULK[bulk_import_<br/>sonoma_vbos.py]:::tools
    BEST[best_sonoma_lap.py<br/>S/F line projection]:::tools
    EXTRACT[extract_gold_lap.py]:::tools
    THUMB[extract_marker_<br/>thumbnails.py]:::tools
    GPS_IMP[import_sonoma_<br/>real_gps.py]:::tools
    ENRICH[enrich_sonoma_<br/>track.py]:::tools
    VAL[validate_litert.py]:::tools
  end

  subgraph BRIDGE["🌉 src/pitwall/ — 56 endpoints"]
    direction TB

    subgraph BRG_INGEST["ingest"]
      B_FRAMES[/session/&lt;id&gt;/frames]:::bridge
      B_VFRAMES[/session/&lt;id&gt;/video_frames]:::bridge
      B_IMPORT[/session/import]:::bridge
      B_RESET[/session/reset]:::bridge
    end

    subgraph BRG_COACH["coach"]
      B_ANALYZE[/analyze]:::bridge
      B_BRIEF[/coach/brief]:::bridge
      B_DEBRIEF[/coach/debrief]:::bridge
    end

    subgraph BRG_QUERY["analysis"]
      B_SCORE[/scorecard /highlights /stats]:::bridge
      B_FRIC[/friction_circle /hustle_map]:::bridge
      B_EOB[/eob /incidents /map /clips /sync]:::bridge
      B_LAPTAB[/lap_time_table /lap_time_distribution]:::bridge
      B_IDEAL[/ideal_lap /sector_times]:::bridge
      B_PEDAL[/pedal_behavior /throttle_corner_box]:::bridge
      B_BAND[/corner_classification /straight_line_speed]:::bridge
      B_BRK[/brake_acceleration]:::bridge
    end

    subgraph BRG_META["meta"]
      B_HEALTH[/health /insights]:::bridge
      B_TRACK[/track/&lt;id&gt;/markers /danger_zones]:::bridge
      B_WX[/track/&lt;id&gt;/weather /elevation]:::bridge
      B_LAP_CRUD[/lap /laps]:::bridge
    end

    subgraph BRG_PROFILE["profile"]
      B_PROF[/driver/&lt;id&gt;/profile]:::bridge
      B_EVOL[/driver/&lt;id&gt;/evolution]:::bridge
    end
  end

  subgraph SIM["🐍 src/pitwall/features/"]
    direction TB
    S_SONOMA[sonoma.py<br/>constants + lore]:::sim
    S_VBO[vbo_parser.py]:::sim
    S_TRACK[track_loader.py<br/>multi-track aware]:::sim
    S_GOLD[gold_standard.py]:::sim
    S_GRADE[corner_grader.py]:::sim
    S_ANAL[analytics.py<br/>13+ analysers]:::sim
    S_HL[highlight_finder.py]:::sim
    S_PROF[driver_profile.py]:::sim
    S_ANALYZER[session_analyzer.py]:::sim
    S_COACH[coaching/<br/>engine_base + rule_coach +<br/>litert_coach + arbiter +<br/>prompts + pedagogy]:::sim
    S_SONIC[coaching/sonic_model.py]:::sim
    S_APP[pitwall_app.py]:::sim
    S_LAPDET[lap_detector<br/>NEW]:::sim
    S_PEDAL[pedal_classifier<br/>NEW]:::sim
    S_BAND[corner_bander<br/>NEW]:::sim
  end

  subgraph DB["💾 DuckDB"]
    direction TB
    T_S[(sessions)]:::store
    T_L[(laps)]:::store
    T_T[(telemetry)]:::store
    T_V[(video_frames)]:::store
    T_N[(coaching_notes)]:::store
    T_E[(driver_events)]:::store
  end

  subgraph DATA["📂 data/"]
    direction TB
    D_TRACKS[/data/tracks/<br/>&lt;id&gt;.json/]:::data
    D_REAL[/sonoma_real_gps.json/]:::data
    D_GOLD[/reference/<br/>sonoma_gold.json/]:::data
    D_THUMB[/markers/sonoma/<br/>*.jpg/]:::data
  end

  subgraph FE["🌐 Vue PWA (src/pwa/)"]
    direction TB
    UI_HUD[on-track HUD]:::ui
    UI_PADDOCK[paddock review]:::ui
    UI_MAP[track map overlay]:::ui
    UI_CHART[charts<br/>box-plots, lines]:::ui
    UI_EVOL[evolution<br/>hero card]:::ui
  end

  RL --> BULK & B_IMPORT
  OBD --> B_FRAMES
  CAM --> B_VFRAMES

  BULK --> B_IMPORT
  EXTRACT -.feeds.-> D_GOLD
  GPS_IMP -.feeds.-> D_REAL
  ENRICH -.feeds.-> D_TRACKS
  THUMB -.feeds.-> D_THUMB
  BEST -.diagnostics.-> T_T
  VAL -.smoke-tests.-> B_HEALTH

  BRG_INGEST --> T_T & T_V & T_N & T_L
  BRG_COACH --> S_COACH
  BRG_QUERY --> S_ANALYZER & S_LAPDET & S_PEDAL & S_BAND
  BRG_META --> S_TRACK & S_SONOMA
  BRG_PROFILE --> S_PROF & S_ANALYZER

  S_LAPDET --> T_T & T_L
  S_PEDAL --> T_T
  S_BAND --> T_T

  S_ANALYZER --> S_GRADE & S_ANAL & S_HL & S_GOLD & S_PROF
  S_COACH --> S_SONOMA & S_TRACK
  S_GRADE --> S_SONOMA
  S_HL --> S_SONOMA
  S_PROF --> T_E
  S_GOLD -.reads.-> D_GOLD
  S_TRACK -.reads.-> D_TRACKS & D_REAL
  S_APP --> S_COACH & S_SONIC & S_TRACK & S_VBO

  %% (audio_engine.py, sonic_model_v2.py, lstm_predictor*.py, sequence_predictor.py,
  %%  track_map.py, helpers.py — all deleted as dead code in PR #30)

  BRG_QUERY --> UI_HUD & UI_PADDOCK & UI_CHART & UI_MAP
  BRG_PROFILE --> UI_EVOL
  D_THUMB --> UI_MAP
  D_REAL --> UI_MAP
```

This is the canonical "what's in the box" diagram — print it and tape it to the rig.

---

## Endpoint × DuckDB table read/write matrix

Which tables each endpoint touches. Useful when reasoning about migration safety: changing a column shape only affects the rows in the **R** column; deleting an endpoint frees nothing in the **W** column unless every other writer is also gone.

```mermaid
flowchart LR
  classDef tab fill:#1a3a52,stroke:#4a6e8a,color:#e0e0e0
  classDef ep fill:#1a4a5d,stroke:#3a6e8a,color:#e0e0e0

  subgraph T["DuckDB tables"]
    T_S[(sessions)]:::tab
    T_L[(laps)]:::tab
    T_T[(telemetry)]:::tab
    T_V[(video_frames)]:::tab
    T_N[(coaching_notes)]:::tab
    T_E[(driver_events)]:::tab
  end

  EP_FRAMES["/session/&lt;id&gt;/frames"]:::ep
  EP_VFRAMES["/session/&lt;id&gt;/video_frames"]:::ep
  EP_IMPORT["/session/import"]:::ep
  EP_ANALYZE["/analyze"]:::ep
  EP_DEBRIEF["/coach/debrief"]:::ep
  EP_LAPTAB["/lap_time_table /sector_times<br/>/ideal_lap /lap_time_distribution"]:::ep
  EP_PEDAL["/pedal_behavior<br/>/throttle_corner_box<br/>/corner_classification<br/>/straight_line_speed<br/>/brake_acceleration"]:::ep
  EP_EVOL["/driver/&lt;id&gt;/evolution"]:::ep
  EP_PROFILE["/driver/&lt;id&gt;/profile"]:::ep
  EP_SCORE["/scorecard /highlights /stats<br/>/friction_circle /hustle_map<br/>/eob /incidents /map /clips /sync"]:::ep

  EP_FRAMES -- W --> T_T
  EP_VFRAMES -- W --> T_V
  EP_IMPORT -- W --> T_S & T_T & T_L
  EP_ANALYZE -- W --> T_N
  EP_DEBRIEF -- R --> T_T
  EP_DEBRIEF -- W --> T_E
  EP_LAPTAB -- R --> T_T & T_L
  EP_PEDAL -- R --> T_T
  EP_EVOL -- R --> T_S & T_L & T_T & T_E
  EP_PROFILE -- R --> T_E
  EP_SCORE -- R --> T_T & T_V
```

**Rule of thumb:** `telemetry` is the hottest read table — most analysis endpoints touch it. `driver_events` is append-only and small; safe to add columns. `coaching_notes` is the only table written by the live `/analyze` path, so it accumulates fast — consider a TTL prune in a future migration.

---

## Key invariants the architecture enforces

1. **Backend owns inference** ([ADR-013](adr/013-frontend-backend-boundary.md)). Frontend never imports `mediapipe`, never builds prompts, never grades a corner.
2. **One source of truth** for system prompts: `coaching/prompts.py:build_system_prompt(driver_level, track, mode)` (also re-exported from the legacy `coach_engine` shim). Every coach (RuleCoach, LitertCoach, future GeminiCoach) consumes the same composer.
3. **Sonoma is the product** ([ADR-014](adr/014-sonoma-as-the-product.md)). `sonoma.py` is hardcoded; track JSON is the only data file the bridge needs at runtime.
4. **DuckDB is the source-of-truth store** for sessions, laps, telemetry, video metadata, coaching notes, and driver events. `session_id` is the universal join key. `timestamp` (epoch seconds) is the universal clock.
5. **Markers carry both anonymized and real GPS** so analytics that join against the dataset's anonymized frame and frontend that renders on a real-world map both work without conflict.
6. **Three-tier graceful degradation** for the LLM: LitertCoach → RuleCoach → mock. Anything that calls a coach can always rely on a string back.

# ADR-015: Universal Telemetry Sink + Capability Model

**Status:** Accepted
**Date:** 2026-04-29

## Context

Today the bridge accepts a fixed-shape `Frame` — 12 fields covering GPS, IMU, brake, throttle, steering, RPM. This was the right call when the only sources were the Racelogic VBO (10 Hz GPS+IMU) and OBDLink MX (a narrow OBD-II PID slice). The 12-field schema is the foundation the entire analysis stack rests on: lap detection, sector splits, friction circle, the 11 Phase-6 endpoints — every one of them assumes the wide table.

That assumption is about to get pressure-tested:

1. **CAN bus integration is on the roadmap.** The BMW E46 exposes ~80 PIDs through OBD-II, and a custom CAN tap on the powertrain bus opens up 200+ more (gear, clutch position, oil temp, individual wheel speeds, AFR, knock counts, suspension travel). Most of these have nowhere to land.
2. **Different cars expose different signals.** A driver in an M3 has access to clutch position; the same driver in a Cayman doesn't. The system can't crash or render zeros — it should hide what's missing and surface what's available.
3. **Streams arrive at different rates and times.** GPS is 10 Hz deterministic; OBD is 5–20 Hz contention-bound; suspension strain gauges run at 100+ Hz; TPMS is 1 Hz; ECU snapshots are event-driven. Forcing everything into a 10 Hz wide row at ingest either drops data (downsampling slow-and-fast indiscriminately) or invents data (upsampling 1 Hz TPMS to fill 10 Hz cells).
4. **Coaches need to know what they can ask for.** A rule like *"oil temp warning if oil > 105°C at T11 entry"* must be silently disabled — not crash, not fire wrongly — when the session has no `oil_temp` stream.
5. **Frontend widgets must degrade gracefully.** The dashboard should render a coolant gauge when coolant exists and *nothing* when it doesn't, without a configuration matrix per car.

[ADR-006](006-sensor-fusion.md) covered Racelogic + OBDLink fusion at the ingest boundary. [ADR-010](010-http-bridge-warm-path.md) committed to the bridge as the warm-path Tier 1. ADR-015 generalises the **schema** so any feed can land while the existing wide table stays as-is for the canonical 10 Hz fields.

## Decision

Add a **universal telemetry sink** alongside the existing wide table — *not* replacing it. The sink is four small pieces:

1. A **signal registry** (catalog of known signals + units + semantics).
2. A **tall signal store** in DuckDB (one row per signal × moment × value).
3. A **per-session capability advertisement** (which signals this session has, at what rate).
4. A **query-time synchroniser** that aligns selected signals to a chosen time axis on demand.

The wide `telemetry` table keeps owning the 12 canonical fields. Lap detection, sector splits, the 11 Phase-6 analysis endpoints all keep working unchanged. Everything novel lands in the tall store.

```mermaid
flowchart LR
  classDef ingest fill:#5d4a1a,stroke:#8a6e3a,color:#e0e0e0
  classDef store fill:#1a3a52,stroke:#4a6e8a,color:#e0e0e0
  classDef proc fill:#2e5d3a,stroke:#5a8a6e,color:#e0e0e0
  classDef api fill:#1a4a5d,stroke:#3a6e8a,color:#e0e0e0
  classDef ui fill:#5d1a3a,stroke:#8a3a5e,color:#e0e0e0

  GPS[GPS 10 Hz<br/>existing]:::ingest
  OBD[OBD 5–20 Hz<br/>existing + extended]:::ingest
  CAN[Custom CAN<br/>any rate, any DBC]:::ingest
  TPMS[TPMS / suspension /<br/>strain / external]:::ingest

  ADAPT[per-source ingest<br/>adapters<br/>map to registry]:::proc
  REG[(signal_registry<br/>static + discovered)]:::store
  WIDE[(telemetry<br/>fixed 12-field<br/>10 Hz canonical)]:::store
  TALL[(telemetry_signals<br/>tall, sparse,<br/>any-rate)]:::store
  CAPS[(session_capabilities<br/>computed at import)]:::store

  SYNC["query-time<br/>synchroniser<br/>(ASOF JOIN + LERP)"]:::proc
  COACHCAP[coach capability<br/>filter]:::proc
  FECAP[frontend widget<br/>capability filter]:::proc

  EP_SYNC["GET /session/&lt;sid&gt;/signals<br/>?names=&amp;axis=&amp;rate_hz="]:::api
  EP_CAP["GET /session/&lt;sid&gt;/capabilities"]:::api
  EP_REG["GET /signals/registry"]:::api

  COACH[coach engine<br/>rules with<br/>requires=[...]]:::proc
  WIDGETS[Flutter dashboard<br/>conditional widgets]:::ui

  GPS --> ADAPT
  OBD --> ADAPT
  CAN --> ADAPT
  TPMS --> ADAPT
  ADAPT --> WIDE
  ADAPT --> TALL
  ADAPT --> REG
  TALL --> CAPS
  WIDE --> CAPS
  CAPS --> COACHCAP --> COACH
  CAPS --> FECAP --> WIDGETS
  TALL --> SYNC
  WIDE --> SYNC
  SYNC --> EP_SYNC --> WIDGETS
  CAPS --> EP_CAP --> WIDGETS
  REG --> EP_REG --> WIDGETS
```

---

## Schema

### `signal_registry` (static + discovered catalog)

```sql
CREATE TABLE signal_registry (
    signal_id     INTEGER PRIMARY KEY DEFAULT nextval('signal_registry_id_seq'),
    name          VARCHAR UNIQUE NOT NULL,    -- canonical snake_case, e.g. 'oil_temp_c'
    units         VARCHAR NOT NULL,           -- '°C', 'kPa', 'rpm', 'bar', '%', 'g', 'kmh'
    semantics     VARCHAR,                    -- 'temperature', 'pressure', 'angular_velocity', ...
    "group"       VARCHAR,                    -- 'powertrain', 'chassis', 'tires', 'driver_input'
    expected_hz   DOUBLE,                     -- typical rate for this signal class
    min_useful_hz DOUBLE,                     -- below this, coaches won't depend on it
    discovery     VARCHAR,                    -- 'static_obd2' | 'static_dbc' | 'discovered'
    discovered_at TIMESTAMP DEFAULT now()
);
```

Seeded at startup with the well-known OBD-II mode 01 PIDs (~80 entries) plus any per-car DBC dumps in `data/dbc/<car>.dbc`. Novel signals discovered at session-import are inserted with `discovery = 'discovered'` and `units = NULL` — the coach treats them as "logged but not coachable" until a human stamps the units.

### `telemetry_signals` (tall sparse store)

```sql
CREATE TABLE telemetry_signals (
    session_id  VARCHAR NOT NULL,
    signal_id   INTEGER NOT NULL,
    t           DOUBLE  NOT NULL,             -- epoch seconds, native rate
    value       DOUBLE  NOT NULL,
    PRIMARY KEY (session_id, signal_id, t)
);
CREATE INDEX idx_signals_sess_sig_t
    ON telemetry_signals (session_id, signal_id, t);
```

Variable rate. Sparse — a session with no oil temp simply has no rows for that signal. The `t` column is the same epoch-seconds clock the wide `telemetry` table uses; ASOF joins line up out of the box.

**Cardinality check.** A 30-minute session at 100 Hz × 50 signals = 9 M rows. DuckDB swallows that locally without breaking a sweat (~120 MB on disk). For a season's worth of sessions, partition by `session_id` via Parquet export — see migration plan below.

### `session_capabilities` (computed at import)

```sql
CREATE TABLE session_capabilities (
    session_id  VARCHAR NOT NULL,
    signal_id   INTEGER NOT NULL,
    n_samples   INTEGER NOT NULL,
    mean_hz     DOUBLE  NOT NULL,             -- n_samples / (t_end - t_start)
    t_start     DOUBLE  NOT NULL,
    t_end       DOUBLE  NOT NULL,
    PRIMARY KEY (session_id, signal_id)
);
```

Populated by a single SQL aggregate at the end of session import. The frontend hits `GET /session/<sid>/capabilities` once at session-load and uses it to drive the widget tray. The coach engine intersects its `requires` list with this table and disables rules that can't fire.

---

## Endpoints

Three new endpoints, all loopback-only, all return JSON.

### `GET /signals/registry`

Lists every known signal. Frontend caches the registry once on app launch; coach config UI reads it to populate dropdowns.

```jsonc
// 200 OK
{
  "count": 142,
  "signals": [
    {
      "signal_id": 1, "name": "oil_temp_c", "units": "°C",
      "semantics": "temperature", "group": "powertrain",
      "expected_hz": 10, "min_useful_hz": 1, "discovery": "static_obd2"
    },
    {
      "signal_id": 47, "name": "wheel_speed_fl_kmh", "units": "kmh",
      "semantics": "angular_velocity", "group": "chassis",
      "expected_hz": 100, "min_useful_hz": 20, "discovery": "static_dbc"
    },
    /* … */
  ]
}
```

### `GET /session/<sid>/capabilities`

What this session actually has, at what rate. The frontend widget tray reads this; the coach engine's pre-flight check reads this.

```jsonc
// 200 OK
{
  "session_id": "sonoma-raceway-20260428-201503",
  "duration_s": 1387.2,
  "signals": [
    { "name": "speed",           "n_samples": 13872, "mean_hz": 10.0, "useful": true  },
    { "name": "oil_temp_c",      "n_samples":  6940, "mean_hz":  5.0, "useful": true  },
    { "name": "tpms_fl_kpa",     "n_samples":  1387, "mean_hz":  1.0, "useful": false },
    { "name": "clutch_pos_pct",  "n_samples":     0, "mean_hz":  0.0, "useful": false }
  ],
  "coaches_available": ["base_pace_note", "oil_temp_warning", "trail_brake_score"],
  "coaches_disabled":  [
    { "coach_id": "clutch_balance", "reason": "missing signal: clutch_pos_pct" },
    { "coach_id": "tpms_drift",     "reason": "tpms_fl_kpa rate (1.0 Hz) below min_useful_hz (5.0)" }
  ]
}
```

`useful` is `mean_hz ≥ registry.min_useful_hz`. The frontend can render a present-but-low-rate signal as a static badge instead of a live gauge.

### `GET /session/<sid>/signals`

The synchroniser. Pulls one or more signals aligned to a chosen time axis, at a chosen rate, optionally clipped to a lap or distance range.

**Query params:**

| Param | Default | Meaning |
|---|---|---|
| `names` | required | comma-separated signal names |
| `axis` | `gps` | `gps` (= wide-table `t`), `lap_distance` (m), or a specific signal name |
| `rate_hz` | `0` (= native axis rate) | resample to this rate; `0` keeps axis-native |
| `interp` | `hold` | `hold` (ASOF, no extrapolation) or `lerp` (linear between bracketing samples) |
| `t_from`, `t_to` | session bounds | clip window in epoch seconds |
| `lap` | unset | clip to this lap number (uses `laps` table) |

**Math (per requested signal *s*).** With axis sample times $\{a_1, a_2, \dots, a_K\}$ and signal samples $\{(t^s_j, v^s_j)\}$ sorted by *t*:

For `interp = hold` (DuckDB ASOF):

$$\hat{v}^s_k = v^s_{j^*}\quad\text{where } j^* = \max\{j : t^s_j \le a_k\}$$

For `interp = lerp` (linear between bracketing samples):

$$\hat{v}^s_k = v^s_{j} + (v^s_{j+1} - v^s_{j}) \cdot \frac{a_k - t^s_{j}}{t^s_{j+1} - t^s_{j}},\quad t^s_j \le a_k \le t^s_{j+1}$$

If $a_k < t^s_1$ (axis sample precedes first signal sample): emit `null`. Same for tail-end gaps.

**Response — 200**:

```jsonc
{
  "session_id": "sonoma-raceway-20260428-201503",
  "axis":       "gps",
  "rate_hz":    10.0,
  "interp":     "hold",
  "t_from":     1714316103.0,
  "t_to":       1714316130.0,
  "names":      ["speed", "oil_temp_c", "clutch_pos_pct"],
  "rows": [
    { "t": 1714316103.0, "speed": 145.2, "oil_temp_c": 92.1, "clutch_pos_pct": null },
    { "t": 1714316103.1, "speed": 146.8, "oil_temp_c": 92.1, "clutch_pos_pct": null }
    /* … */
  ],
  "missing": ["clutch_pos_pct"]
}
```

`missing` lists signals the session has zero samples for — the frontend renders them as `null` columns and `200 OK` still succeeds (no 404 for partial-availability).

**Status codes:**
- `200` — at least one requested signal had ≥ 1 sample.
- `400` — unknown signal name, or `axis` references a missing signal.
- `404` — session has zero frames in the wide telemetry table.

---

## Capability-aware coaches

Coach rules grow a `requires` declaration:

```python
@coach_rule(
    id="oil_temp_warning_t11",
    requires=["oil_temp_c", "distance_m"],
    min_rates={"oil_temp_c": 1.0},     # accept low-rate oil temp; bumps cooling lag noise
)
def oil_warning(ctx, signals):
    if signals["oil_temp_c"][-1] > 105 and ctx.next_corner == "Turn 11":
        return CoachingMessage("Oil at 105 — short-shift T10 exit, save the run.", priority=2)
```

At session-load, the engine computes `available_rules = {r for r in rules if r.requires ⊂ caps and rates_meet(r.min_rates, caps)}`. Disabled rules are advertised in the capabilities endpoint above so the frontend can show *"Coach 'clutch balance' disabled — your car doesn't expose clutch position"*. This is the **failure-as-data** pattern: missing signals don't crash, they explain themselves.

---

## Frontend integration pattern

The Flutter dashboard's widget tray consumes the capabilities envelope:

```dart
final caps = await api.get('/session/$sid/capabilities');
final available = (caps['signals'] as List)
    .where((s) => s['useful'] == true)
    .map((s) => s['name'] as String)
    .toSet();

return Wrap(children: [
  if (available.contains('speed'))         SpeedGauge(sid: sid),
  if (available.contains('oil_temp_c'))    OilTempCard(sid: sid),
  if (available.contains('coolant_temp_c'))CoolantCard(sid: sid),
  if (available.contains('tpms_fl_kpa'))   TpmsGrid(sid: sid),
  if (available.contains('clutch_pos_pct'))ClutchTrace(sid: sid),
  // … one widget per coachable signal …
]);
```

Each widget then calls `/session/$sid/signals?names=oil_temp_c&axis=gps&rate_hz=2` for its own data and renders it. No widget needs to know about cars; it just asks for its signal and either gets values or doesn't render.

---

## What this ADR rules out

- **Schema-on-write rigidity for new signals.** Anything novel goes to the tall store; the wide table stays frozen at its 12 fields.
- **Implicit unit conversion.** The registry stamps units at ingest. Rules that compare to thresholds (`oil > 105`) declare units; cross-unit comparisons fail loud.
- **Resampling at ingest.** Always store at the source rate. The synchroniser handles alignment at query time. This avoids the upsampling/downsampling entanglement that breaks correlation analysis.
- **Per-car renderers in the frontend.** The widget tray is driven by `capabilities`, not by `car_make`. Adding a new car requires zero frontend changes if its signals already exist in the registry.
- **Replacing the wide table.** Doing so would force re-implementing every existing analysis endpoint on tall data via PIVOT — unnecessary churn for no gain.

---

## Migration list

| Item | Action |
|---|---|
| New table `signal_registry` | Created at bridge startup if missing; seeded from `data/registry/obd2_pids.json` + any `data/dbc/*.dbc` |
| New table `telemetry_signals` | Created at bridge startup if missing |
| New table `session_capabilities` | Created at bridge startup; populated by `_compute_capabilities(session_id)` at end of `/session/import` and `/session/<sid>/frames` (last batch) |
| New endpoints | `/signals/registry`, `/session/<sid>/capabilities`, `/session/<sid>/signals` |
| `coach_engine.py` | Add `@coach_rule(requires=[...], min_rates={...})` decorator; gate rule activation on capabilities at session-load. *Updated 2026-05 (PR #30): the registry now lives in `src/pitwall/features/coaching/pedagogy.py`; `coach_engine` is a re-export shim.* |
| `src/pitwall/__main__.py` | New `_signal_id(name)` helper (registry lookup + insert-on-novel); new ingest path `POST /session/<sid>/signals` for non-12-field data |
| `data/registry/obd2_pids.json` | New static seed file with the standard OBD-II mode 01 PID catalog |
| `data/dbc/` (optional) | Per-car DBC files; ingest-time loader pulls names + units |
| Existing wide ingest paths | Unchanged — `/session/<sid>/frames` keeps writing the 12-field table; per-frame the bridge also fans out to `telemetry_signals` only for fields not in the wide schema (no-op today, becomes useful when adapters start sending extra fields) |
| Frontend widget tray | Read `/session/<sid>/capabilities` once on session load; render conditional widgets |

---

## Phasing

| Phase | Deadline | Slice |
|---|---|---|
| **1 — schema + registry** | May 8 | Three tables, seed registry from OBD-II mode 01 PIDs, `/signals/registry` endpoint. No ingest path yet — read-only catalog. |
| **2 — sink ingest** | May 13 | `POST /session/<sid>/signals` accepts `(name, t, value)` tuples or `(signal_id, t, value)`; novel names auto-register with `units = NULL`. `_compute_capabilities` runs at end of import. |
| **3 — synchroniser** | May 18 | `GET /session/<sid>/capabilities` and `/session/<sid>/signals?names=…`. ASOF + lerp interpolation. Tests for partial availability and rate degradation. |
| **4 — coach gating** | May 22 | `@coach_rule(requires=...)` decorator; capability filter wired into session-load. First test rule: `oil_temp_warning_t11`. |
| **Phase 5 (post-sprint)** | June | DBC import for the BMW E46 powertrain bus, frontend widget tray reads capabilities. |

Phases 1–4 fit in the 25 days remaining without blocking the May 23 field test — the wide-table coaching path is unchanged throughout.

---

## Pressure tests

Things this design must handle without crashing:

1. **Partial availability.** Session has GPS + brake + throttle but no oil temp. Result: oil widgets hidden, oil rules disabled, `/signals?names=oil_temp_c` returns `null` columns + `missing: ["oil_temp_c"]` with `200 OK`.
2. **Rate mismatch.** TPMS arrives at 1 Hz; coach rule wants `min_useful_hz = 5`. Result: capability marks the signal `useful: false`; coach disabled with reason; widget renders a static badge.
3. **Novel signal.** Custom CAN frame with no known mapping. Result: registered with `units = NULL`, `discovery = 'discovered'`; logged + chartable but no rules can require it until a human stamps the units.
4. **Clock skew across sources.** ECU and GPS clocks differ by 80 ms. Result: ingest adapter is responsible for anchoring (typically to the GPS clock); the sink trusts what comes in. ASOF joins survive small skews because the axis is one source's clock and other signals are interpolated relative to it.
5. **Massive cardinality.** 100 Hz × 200 signals × 60 minutes = 72 M rows for one session. Result: DuckDB local file ~1 GB; query latency for a single-signal lap-window read stays sub-100 ms with the `(session_id, signal_id, t)` index. Beyond ~10 sessions of that size, export to Parquet via `COPY TO 'archive/<sid>.parquet'` and read via DuckDB's Parquet view.
6. **Schema mid-migration.** A new ECU firmware adds a signal halfway through a session. Result: the new signal just starts having rows from that point; capability mean_hz reflects the partial coverage; coaches that require it remain disabled because the rate doesn't meet the bar.

---

## Consequences

**Positive**
- **Any data feed is ingestable** with a per-source adapter — no schema migration per car.
- **Coaches and widgets fail open**: missing signals → silently disabled with reason, never crashes.
- **Sync is read-time, not write-time** — preserves source rate and timing for correlation analysis.
- **Existing analysis stack is untouched** — wide table keeps its 12 fields, all 11 Phase-6 endpoints keep working.
- **Capability advertisement is a first-class API surface** — frontend and coaches both query it the same way.

**Negative**
- **Two storage shapes to reason about.** Wide for canonical fields, tall for everything else. New analysis code has to choose; doc the rule of thumb: if the field is in `Frame`, use wide; otherwise tall.
- **Registry-discipline cost.** The "any signal" promise depends on the registry being authoritative for units. A loose registry produces silent unit bugs at coach-rule evaluation. Mitigation: every coach rule that compares to a numeric threshold must declare `units` and the system asserts at registration time.
- **Adapter is the new fragile boundary.** Garbage-in to the sink is garbage-in everywhere. Mitigation: per-adapter unit tests + a `/signals/<sid>/sanity` diagnostic that flags out-of-range values per signal class.

---

## Related

- [ADR-006 — Sensor Fusion for Racelogic + OBDLink](006-sensor-fusion.md) — the original two-source fusion this generalises.
- [ADR-010 — HTTP Bridge as Warm-Path Tier 1](010-http-bridge-warm-path.md) — every new endpoint here lands on the bridge.
- [ADR-013 — Frontend Visualises, Backend Reasons](013-frontend-backend-boundary.md) — capability-driven widget rendering enforces this boundary cleanly.
- [ADR-014 — Sonoma is the Product](014-sonoma-as-the-product.md) — the wide-table schema this ADR preserves was sized for the Sonoma sprint; ADR-015 is the doorway to other tracks/cars without breaking that contract.
- [API — Pitwall HTTP Bridge](../api.md) — the Phase-6 endpoints will gain optional `extras=` query params after Phase 3 of this ADR ships.
- [Internal Architecture](../internal_architecture.md) — the *Comprehensive backend topology* diagram will gain the tall store + registry once this is implemented.

# Analysis Hall

**Status:** Shipped
**Owner:** PWA (`src/pwa/`)
**Route:** `/garage/analysis`

The Analysis Hall is the off-track telemetry workbench. It replaces the
prior Analysis Hub tile-grid with a tabbed surface that queries the
session parquet bundles directly in the browser via DuckDB-Wasm. The old
tile grid still ships as the Modules tab so the per-domain sub-pages
(Lap Times Hall, Corner Mastery, Track Atlas, …) stay one click away.

---

## Overview

- **Why tabs:** the prior tile-grid forced a screen change for every
  view; comparing lap-time and IMU traces meant losing the active lap
  + outlier filter context. The tabbed shell keeps `sessionId`,
  `selectedLapIndex`, and `filterOutliers` constant while the workbench
  pane swaps.
- **What it consumes:** session parquet bundles already exported by the
  bridge (wide canonical telemetry + tall `telemetry_signals` + signal
  registry), plus the bridge's server-side lap detector at
  `GET /session/<sid>/laps`.
- **What it does not do:** it never live-streams. The realtime cockpit
  is owned by the [On-Track HUD](on-track-hud.md). Analysis Hall is a
  paddock surface.

---

## Architecture

```
parquet bundle  ─▶  DuckDB-Wasm (web worker)  ─▶  tab queries
                            ▲                           │
                            │                           ▼
                    /session/<sid>/laps          Chart.js / Leaflet
                            │                       (lazy-loaded)
                            ▼
                     analysisStore (Pinia)
                  sessionId · laps · activeTab
                  selectedLapIndex · filterOutliers
```

- **DuckDB-Wasm worker** is bundled same-origin
  (`src/pwa/src/shared/lib/duckdb/`) to avoid the jsdelivr CORS failure
  that bit the earlier prototype.
- **Tabs are `defineAsyncComponent`-loaded.** The Leaflet bundle ships
  only when the Overview tab opens; Chart.js + the zoom plugin only
  when Telemetry / Systems / IMU / Signals open.
- **Lap filter is one fragment.** `analysisStore.lapFilterSql(col)`
  returns `{ sql, params }` (e.g. `' AND timestamp BETWEEN ? AND ?'`)
  that every tab concatenates into its own DuckDB query. Empty lap
  selection = empty fragment, so the same query string works for "full
  session" or any windowed lap.

---

## Tabs

Six tabs in `src/pwa/src/pages/analysis-hub/tabs/`. Each is independent
and re-runs its queries when `sessionId`, `selectedLapIndex`, or
`filterOutliers` change.

### Overview (`OverviewTab.vue`)

An 11-cell summary grid on the left (duration, wide-row count,
tall-row count, distinct signals, distance, peak speed mph, peak rpm,
peak G, wide rate Hz, signal rate, total registry size) and a Leaflet
map of Sonoma on the right. The map draws three layers: the centerline
from `GET /track/<id>/elevation`, the raw GPS trace from the parquet,
and a virtual path mapped from `distance_m` along the centerline.
DuckDB-Wasm queries against `telemetry`, `telemetry_signals`, and
`signal_registry`.

### Telemetry (`TelemetryTab.vue`)

Three time-series panels: Speed + RPM, driver inputs (throttle / brake
/ steering), and G-forces (`g_lat`, `g_long`, `combo_g`, plus `g_vert`
merged in from the tall store). Decimates to ~4000 points to keep
Chart.js + the zoom plugin responsive. Pure DuckDB-Wasm — no bridge
call.

### Systems (`SystemsTab.vue`)

TPMS 2x2 corner grid (latest sample per corner: pressure / temperature
/ voltage / alarm) plus stock-comparison overlays for engine
temperatures, engine pressures, TPMS pressures + temperatures, wheel
speeds, and GPS-vs-wheel speed. Each comparison panel renders only
when at least one of its signals has samples this session. All values
come from the tall `telemetry_signals` table.

### IMU (`ImuTab.vue`)

Two stacked charts pulled from the 50 Hz tall store: accelerometers
(`inline_accel_g`, `lateral_accel_g`, `vertical_accel_g`) and gyros
(`roll_rate_degs`, `pitch_rate_degs`, `yaw_rate_degs`). DuckDB-Wasm
only.

### Signals (`SignalsTab.vue`)

Full port of the standalone telemetry-viewer's signal picker. Left
pane: search box, preset buttons (speed+rpm, driver inputs, G's, IMU,
oil, clear), grouped signal list with checkboxes (auto-grouped by
`units` from `signal_registry`). Right pane: twin-axis overlay chart
with zoom + pan. Series are capped at two units per axis so the chart
never carries more than two y-axes.

### Modules (`ModulesTab.vue`)

The old tile-grid hub, preserved so the per-domain sub-pages stay
discoverable. Tiles route to Lap Times Hall, Corner Mastery,
Straights & Speed, Track Atlas, Driver Evolution, Pedal Profile,
Ghosts, Replay, and SQL Console. Tile counts come from the session
store + save-slot, never hardcoded.

---

## Toolbar

The toolbar sits above the tab bar and applies to every tab.

| Control | Source | Notes |
|---|---|---|
| Session picker | `GET /sessions?limit=50` | Defaults to the most recent session by `started_at` |
| Lap picker | `GET /session/<sid>/laps` | Index 0 is the synthetic "Full session" pseudo-lap; >0 indexes detected laps |
| Filter outliers checkbox | `src/pwa/src/shared/lib/telemetry/outliers.ts` | Sanity-clips signals against per-signal ranges; OOB values become nulls (chart gaps) |
| Loading / error chips | `analysisStore.loading` / `error` / `lapsError` | Surfaces DuckDB and laps-endpoint failures inline |

### Keyboard

```
1-6      switch tab (Overview / Telemetry / Systems / IMU / Signals / Modules)
◀ / ▶    cycle lap selection
O        toggle outlier filter
B / ⌫    back to /garage
ESC      router.back() (owned by App.vue, not the page)
```

Touch targets on the toolbar are ≥44×44 to keep Pixel 10 landscape taps
clean.

---

## Lap detection

Laps come from the bridge — they're computed server-side off the same
data the parquets export, so the workbench shares the canonical lap
boundaries with Stage Clear, Lap Times Hall, and the HUD's derived
lap counter.

Endpoint: `GET /session/<sid>/laps` →

```json
{
  "laps": [
    { "name": "L01", "t_start": 0, "t_end": 102.3,
      "duration_s": 102.3, "distance_m": 4034.1, "method": "gps" }
  ],
  "track_length_m": 4034.1
}
```

`method` is one of:

- `gps` — start/finish line crossing detected on lat/lon
- `distance` — cumulative `distance_m` modulo the loaded track length
- `stint` — heuristic fallback (continuous driving windows when GPS is
  absent)
- `all` — the synthetic full-session pseudo-lap injected at index 0
  client-side

When the bridge can't serve laps the store surfaces the error in the
toolbar and degrades to "Full session" only — it does not fabricate
laps.

---

## File layout

```
src/pwa/src/pages/analysis-hub/
├── AnalysisHub.vue            ← tabbed shell + toolbar + keyboard
├── tabs/
│   ├── OverviewTab.vue        ← summary grid + Leaflet map
│   ├── TelemetryTab.vue       ← speed/rpm, inputs, G's
│   ├── SystemsTab.vue         ← TPMS + engine compare overlays
│   ├── ImuTab.vue             ← accel + gyro
│   ├── SignalsTab.vue         ← signal picker + overlay
│   └── ModulesTab.vue         ← old tile grid (sub-pages)
├── GhostManager.vue           ← /analysis/ghosts (sub-page)
└── TelemetryReplay.vue        ← /analysis/replay (sub-page)

src/pwa/src/entities/analysis/model/analysisStore.ts
   sessionId · laps · trackLengthM · selectedLapIndex
   filterOutliers · activeTab · loading · error · lapsError
   getters: selectedLap, lapFilterSql(col)
   actions: loadSession, setSelectedLap, cycleLap,
            setFilterOutliers, setActiveTab

src/pwa/src/shared/lib/telemetry/outliers.ts
   SANITY_RANGES (per-signal min/max from AiM MXP v3.0 + DBC hints)
   clipOutliers(name, data, enabled)

src/pwa/src/shared/lib/telemetry/queries.ts
   asNum, decimate, tallT0, fetchSignalSeries, latestSignalValue
```

The shell pulls `CyberTabs`, `CyberPanel`, `CyberCheckbox` from
`src/pwa/src/shared/ui/core/`; charts use
`src/pwa/src/shared/ui/charts/CyberLineChart.vue` for theming.

---

## Known limits

- **Parquet exports are required.** Sessions recorded on backends that
  only ship the SQLite DDL (e.g. the phone deployment running without
  pyarrow) won't have parquet bundles, and the workbench fails open
  with an honest `DATA UNAVAILABLE` chip. The bridge needs either
  DuckDB or pyarrow to materialise the bundles.
- **DuckDB-Wasm is a worker; the first session load incurs a one-time
  Wasm download** that's then cached by the service worker (Workbox
  runtime cache configured in `vite.config.ts`).
- **Leaflet ships only when the Overview tab opens** — if a session has
  no GPS the centerline still draws but the raw GPS and virtual-path
  layers will be empty.
- **Outlier ranges are static** (`SANITY_RANGES` literal). Signals not
  in the table pass through unfiltered regardless of the toggle.

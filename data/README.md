# `data/` — configuration and reference data

Everything the bridge reads from disk at boot or per-session. None of
these files are user-generated session data; recorded sessions live in
the SQLite/DuckDB file (`pitwall_sessions.duckdb`).

## Layout

```
data/
├── cars/                       # per-car CAN pipeline configs
│   └── bmw_e46_m3.yaml         # AiM MXP SmartyCam v3.0 → CANable → Pixel
├── dbc/                        # cantools DBC files
│   └── pitwall.dbc             # on-bus frame layouts for the AiM MXP output
├── tracks/                     # track JSONs (centerline, corners, markers, …)
│   ├── sonoma.json
│   ├── sonoma_real_gps.json    # real GPS frame (the anonymized 23.49°N copy is in sonoma.json)
│   └── training_data/
├── registry/                   # signal catalog seed
│   └── obd2_pids.json          # 54 entries loaded into signal_registry on first boot
├── formulas/                   # AST-allowlisted CAN→engineering-unit formulas
│   └── standard.yaml
├── reference/                  # gold-standard lap traces (when present)
├── markers/                    # marker thumbnails
├── pitwall_sessions.duckdb     # session storage (or .sqlite on Termux)
├── DATASET_OVERVIEW.md         # ─┐
├── DATA_QUALITY.md             #  │ legacy VBO-dataset reference
├── DERIVED_FEATURES.md         #  │ (kept for historical context — the
├── SIGNAL_REFERENCE.md         #  │ live pipeline now reads from cars/,
└── VBO_FORMAT.md               # ─┘ dbc/, registry/, and formulas/)
```

## `cars/*.yaml` — per-car CAN pipeline

YAML-driven. Adding a car requires no Python edits — just a new file. The
schema covers car identity, dash-logger spec, CAN bus parameters, per-
frame channel definitions, sign-recovery rules, and known-broken
channels. See `bmw_e46_m3.yaml` for the live-validated reference.

`bp_cars.py` (`GET /cars`) parses these on demand and flags the one
currently loaded via `--can-car-config`.

## `dbc/pitwall.dbc`

cantools DBC for the AiM MXP SmartyCam output bus (not native BMW
PT-CAN). 20 frames, 66 channels. Loaded at bridge boot via
`--can-dbc data/dbc/pitwall.dbc`.

## `tracks/*.json`

Per-track centerline, corner spec, markers, danger zones, weather
phases. `sonoma.json` is the field-test target. The anonymized
`23.49°N / -122.45°W` GPS frame in `sonoma.json` is the dataset's; the
real Sonoma frame (`38.16°N`) lives in `sonoma_real_gps.json`.

Track JSONs back `/track/<id>/elevation`, `/track/markers`,
`/track/danger_zones`, `/track/weather`, and the GPS-based lap
detection in `/session/<sid>/laps`.

## `registry/obd2_pids.json`

54-entry seed for `signal_registry` (ADR-015 sink). The bridge adds
discovered signals at runtime; this is just the baseline.

## `formulas/standard.yaml`

AST-allowlisted formulas applied during CAN decode (raw → engineering
units). Allowlisting is enforced — arbitrary Python isn't evaluated.

## `pitwall_sessions.duckdb`

Session storage. On x86 laptops this is a DuckDB file; on aarch64 Termux
the same path holds a SQLite database (the duckdb wheel doesn't build
for android). Both backends satisfy `db_conn()`/`state.has_duckdb`. The
file is `.gitignore`d but the directory ships so the bridge has a place
to land its DDL.

## Legacy VBO docs

`DATASET_OVERVIEW.md`, `DATA_QUALITY.md`, `DERIVED_FEATURES.md`,
`SIGNAL_REFERENCE.md`, `VBO_FORMAT.md` describe the original 183-file
Racelogic VBO dataset. They remain accurate for that dataset but the
live pipeline reads from `cars/`, `dbc/`, `registry/`, and `formulas/`
instead of VBOs — VBO import is now one path among several (see
`POST /session/import` in `docs/api.md`).

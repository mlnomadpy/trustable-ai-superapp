# `apps/edge-daemon` — Pitwall in-car bridge

The Python package `pitwall`: the in-car telemetry bridge that runs on the
Pixel 10 under Termux. Owns the sub-100 ms feedback loop (PRD §7) — hardware
ingest, local reflexes, persistence, and the paddock-tier ADK agents.

## Responsibilities

- **AiM MXP / CAN ingest** — `python-can` + `cantools` decode the AiM
  SmartyCam stream via `data/dbc/pitwall.dbc`, then the per-car YAML
  pipeline (`data/cars/bmw_e46_m3.yaml` + `data/formulas/standard.yaml`)
  converts raw signals to wide-table canonicals + a tall signal sink.
- **DuckDB / SQLite persistence** — telemetry, laps, coaching notes,
  conversations, agent traces. DuckDB on dev boxes; SQLite on Termux.
- **Flask bridge** — `pitwall.__main__:main` serves the HTTP/SSE contract on
  `127.0.0.1:8765`.
- **Three-tier coaching** — hot path (`RuleCoach`, <50 ms), warm path
  (`LitertCoach.brief/debrief` over LocalLLM), and the paddock tier: 23 ADK
  agents (ADR-019–026) reasoning over the session via SQL-safe tools.

Every LLM call terminates on-device at LocalLLM (`127.0.0.1:8099/v1`,
ADR-024/025) — no hosted API in any driving-time path.

## Quick start

```bash
# From the repo root (uv workspace):
uv sync --package pitwall --extra dev --extra can

# Run the bridge against the AiM simulator (no car needed):
uv run --package pitwall python -m pitwall --simulate --port 8765

# Tests:
uv run --no-sync pytest        # run from apps/edge-daemon/
```

## Optional extras

| Extra | Pulls in | For |
|-------|----------|-----|
| `can` | `python-can`, `cantools` | CAN ingest + the round-trip tests |
| `ops` | `psutil` | the bridge's RSS monitor thread |
| `dev` | `pytest`, `pytest-cov` | the test suite |
| `all` | `can` + `ops` + `dev` | everything |

`google-adk` + `litellm` are **base** dependencies (ADR-024) — the paddock
ADK tier is required, not optional.

## Layout

```
apps/edge-daemon/
├── pitwall/        the package (bridge, CAN reader, coaching, ADK agents)
├── simulator/      AiM MXP + CAN frame simulators (flat modules)
├── tests/          pytest suite
└── pyproject.toml  package `pitwall`, member of the root uv workspace
```

Shared data (`data/`, tracks, DBC, car configs) and helper `scripts/` live at
the **repo root**, not under this app.

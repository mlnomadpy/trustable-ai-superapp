# trustable-ai-superapp

Monorepo for **Pitwall** — a trustable AI racing coach that runs on a
rooted Pixel 10. Two apps, one repo:

- **`apps/pwa/`** — Vue 3 + Vite + Tailwind PWA, installable as a
  WebAPK. The driver UI (HUD, analysis hall, debrief, garage hub).
- **`apps/bridge/`** — Python (Flask + waitress) bridge that ingests
  AiM MXP CAN telemetry, persists to DuckDB/SQLite, exposes SSE +
  REST, and orchestrates ADK coach agents against a local Gemma‑4‑e2b
  served by LocalLLM at `:8080`.

Plus a third helper:

- **`apps/simulator/`** — synthetic AiM MXP frame generator for
  development without live CAN.

## Repo layout

```
trustable-ai-superapp/
├── apps/
│   ├── pwa/          Vue 3 PWA (self-contained: package.json, vite.config.ts, tests)
│   ├── bridge/       Python Flask bridge (self-contained: pyproject.toml, uv.lock, tests)
│   │   ├── pitwall/  the Python package — keep this name, the bridge imports it
│   │   ├── pyproject.toml
│   │   ├── uv.lock
│   │   ├── .python-version
│   │   └── tests/
│   └── simulator/    synthetic AiM MXP simulator
├── packages/
│   └── contracts/    shared HTTP/SSE contract between bridge and PWA (OpenAPI TBD)
├── docs/             ADRs, screen specs, audits, telemetry pipeline, sonoma intel
├── data/             tracks, cars, DBC files, sample recordings
├── deploy/
│   ├── phone/        scripted Pixel-10 deploy (00-check.sh … 99-stop.sh)
│   └── termux/       Termux service definitions (boot, runit, logging)
├── scripts/          developer helpers
├── tools/            CI utilities, code generators (TBD)
├── .github/          CI workflows (docs.yml, test.yml)
├── mkdocs.yml        docs site build (deploys docs/ to a static site)
├── firebase.json     PWA hosting target (apps/pwa/dist)
├── package.json      umbrella npm scripts (pwa:build, pwa:deploy, docs:serve)
└── README.md
```

## Quick start

### PWA (development)

```bash
npm install --prefix apps/pwa
npm run dev --prefix apps/pwa
# or via the umbrella:
npm run pwa:dev
```

### Bridge (development, on a Mac)

```bash
cd apps/bridge
python -m venv .venv && . .venv/bin/activate
pip install -e ".[can,ops,adk,dev]"
python -m pitwall --simulate --port 8765
```

### Phone deploy (Pixel 10 + Termux)

```bash
./deploy/phone/00-check.sh        # go/no-go for every dependency
./deploy/phone/10-termux-packages.sh
./deploy/phone/20-stage-repo.sh
./deploy/phone/30-python-deps.sh
./deploy/phone/50-build-pwa.sh    # builds PWA on the Mac
./deploy/phone/60-forward-ports.sh
./deploy/phone/70-start-bridge.sh
./deploy/phone/80-open-pwa.sh
```

Full operator's guide: [`deploy/phone/README.md`](deploy/phone/README.md).

## Tests

```bash
# Bridge
cd apps/bridge && pytest

# PWA
npm test --prefix apps/pwa
```

## Docs

Browse [`docs/`](docs/) directly, or build the static site:

```bash
npm run docs:serve    # mkdocs serve at http://127.0.0.1:8000
```

Start points:
- [`docs/index.md`](docs/index.md) — overall orientation
- [`docs/api.md`](docs/api.md) — bridge HTTP/SSE contract
- [`docs/adr/`](docs/adr/) — accepted architecture decisions
- [`docs/vue/screens/`](docs/vue/screens/) — PWA screen specs
- [`docs/telemetry-pipeline.md`](docs/telemetry-pipeline.md) — CAN → DuckDB flow

## Status

The PWA and the Python bridge both run on the Pixel 10 today via the
deploy scripts under `deploy/phone/`. The bridge falls back to SQLite
on Termux (no DuckDB aarch64 wheel) but ingests live CAN at 1 Mbit/s
from a CANable 2.0 and replays recorded sessions on demand.

## License

Proprietary — see individual files for headers.

# trustable-ai-superapp

Monorepo for the **Trustable AI Racing Coach** — a multi-pod
agentic system that runs reliably in a moving racecar. Four apps,
one repo, one shared contract package.

## Apps

| Folder | Runtime | Role |
|--------|---------|------|
| [`apps/edge-daemon/`](apps/edge-daemon/) | Python on Termux/Pixel-10 | In-car logging, hardware parsing (AiM MXP / CAN / VBO), local reflexes. Owns the sub-100ms feedback loop (PRD §7). |
| [`apps/cloud-backend/`](apps/cloud-backend/) | Python (FastAPI + Vertex AI) | Strategic reasoning, DEL synthesis, cold-path curriculum generation, gold-trace storage. |
| [`apps/paddock-dashboard/`](apps/paddock-dashboard/) | Vue 3 PWA | Offline-first visualization, historical engine, paddock-mode conversational telemetry (DuckDB-WASM + text-to-SQL). |
| [`apps/localllm/`](apps/localllm/) | Termux runit / Docker | Deploy config + service definitions for the OpenAI-compatible local model server. Upstream: [`mlnomadpy/localllm`](https://github.com/mlnomadpy/localllm) (Gemma-4-e2b on-phone; QLoRA-fine-tuned Gemma 4 on the trackside laptop for air-gapped fallback per PRD §6.4). |

## Shared package

| Folder | Languages | Role |
|--------|-----------|------|
| [`packages/core-telemetry/`](packages/core-telemetry/) | Python + TypeScript | The **only** legal coupling point between the apps. Telemetry schemas, Domain Expertise Layer (DEL) math, VBO parser, track metadata, learning-plan JSON contract. JSON schemas under `schemas/` are the source of truth. |

## Repo layout

```
trustable-ai-superapp/
├── apps/
│   ├── edge-daemon/        Python in-car bridge — pyproject.toml, pitwall/ package, simulator/, tests/
│   ├── cloud-backend/      FastAPI + Vertex AI — pyproject.toml, cloud_backend/ package, tests/
│   ├── paddock-dashboard/  Vue 3 PWA — package.json, vite.config.ts, src/, tests/
│   └── localllm/           OpenAI-compat local model server (phone runit + trackside docker)
├── packages/
│   └── core-telemetry/     shared schemas + DEL math (python/ + typescript/ + schemas/)
├── docs/                   ADRs, screen specs, audits, telemetry pipeline, sonoma intel, V2 PRD
├── data/                   tracks, cars, DBC files, sample recordings
├── deploy/
│   ├── phone/              scripted Pixel-10 deploy (00-check.sh … 99-stop.sh)
│   └── termux/             Termux service definitions (boot, runit, logging)
├── scripts/                developer helpers
├── tools/                  CI utilities, codegen (TBD)
├── .github/                CI workflows (docs.yml, test.yml)
├── pyproject.toml          uv workspace umbrella (members: apps/edge-daemon, apps/cloud-backend, packages/core-telemetry/python)
├── uv.lock                 workspace lockfile
├── .python-version         3.13
├── package.json            npm workspaces umbrella (members: apps/paddock-dashboard, packages/core-telemetry/typescript)
├── mkdocs.yml              docs site build (deploys docs/)
├── firebase.json           dashboard hosting (apps/paddock-dashboard/dist)
└── README.md
```

## Quick start

### Python apps (edge-daemon, cloud-backend, core-telemetry/python)

```bash
uv sync                                  # resolves the whole workspace
uv run --package edge-daemon python -m pitwall --simulate --port 8765
uv run --package cloud-backend cloud-backend
uv run --package core-telemetry pytest
```

### Paddock dashboard (Vue PWA)

```bash
npm install                              # walks all workspaces
npm run dashboard:dev
# or:
npm run dev --workspace apps/paddock-dashboard
```

### LocalLLM (phone)

```bash
./apps/localllm/scripts/install-phone.sh   # downloads weights, links runit, brings up
curl http://127.0.0.1:8080/v1/models
```

### Phone deploy (full ladder)

```bash
./deploy/phone/00-check.sh
./deploy/phone/10-termux-packages.sh
./deploy/phone/20-stage-repo.sh
./deploy/phone/30-python-deps.sh
./deploy/phone/50-build-pwa.sh
./deploy/phone/60-forward-ports.sh
./deploy/phone/70-start-bridge.sh
./deploy/phone/80-open-pwa.sh
```

Full operator's guide: [`deploy/phone/README.md`](deploy/phone/README.md).

## Tests

```bash
# All Python (edge-daemon, cloud-backend, core-telemetry/python)
uv run pytest

# Paddock dashboard
npm run dashboard:test

# Core-telemetry TypeScript
npm run telemetry:test
```

## Docs

Browse [`docs/`](docs/) directly, or build the static site:

```bash
npm run docs:serve     # mkdocs serve at http://127.0.0.1:8000
```

Start points:
- [`docs/index.md`](docs/index.md) — overall orientation
- [`docs/api.md`](docs/api.md) — legacy bridge HTTP/SSE contract
  (subsumed by `packages/core-telemetry/schemas/` once Phase 0
  closes)
- [`docs/adr/`](docs/adr/) — accepted architecture decisions
- [`docs/vue/screens/`](docs/vue/screens/) — paddock-dashboard screen specs
- [`docs/telemetry-pipeline.md`](docs/telemetry-pipeline.md) — CAN → DuckDB flow

## PRD anchors

V2 product requirements live in the team's PRD (Trustable AI Racing
Coach Super App V2, Rev 3). The four apps + core-telemetry package
in this repo are the structural answer to:

- **PRD §3** — hardware-acceleration / TPU optimization contract
  (the 20–40 tok/s gate lives in `apps/localllm/config/phone.toml`).
- **PRD §4** — Domain Expertise Layer (codified in
  `packages/core-telemetry/`).
- **PRD §5** — greenfield capabilities (biometric, predictive
  health, paddock-mode, video sync, curriculum loop) land as
  routes/modules across `apps/cloud-backend` + `apps/edge-daemon`.
- **PRD §6** — air-gapped paddock-sync topologies (Topology C is
  literally the existing PWA running on the Pixel; Topology A and B
  are FastAPI endpoints on the cloud-backend deployed locally;
  Topology C's air-gapped fallback inference uses `apps/localllm`).
- **PRD §7** — safety guardrails (sub-100ms loop, 4-second debounce,
  cryptographic handshake) enforced in `apps/edge-daemon`.

## Acknowledgments

### Predecessor repositories

This monorepo is the V2 consolidation of work that previously lived
across several focused repositories. We're grateful to every
maintainer and contributor of:

- **[`mlnomadpy/pitwall`](https://github.com/mlnomadpy/pitwall)** —
  the immediate predecessor. The Python bridge, the Vue 3 PWA, the
  Sonoma track intel, the AiM MXP / CAN pipeline, the deploy
  scripts, and the entire `docs/` tree were all forged there over
  the Sonoma field-test cycle. This repo inherits its source tree
  wholesale.
- **[`mlnomadpy/localllm`](https://github.com/mlnomadpy/localllm)** —
  the OpenAI-compatible local model server that every coaching
  call in this monorepo terminates at. `apps/localllm/` holds the
  deploy contract; the server itself lives upstream.
- **[`haruiz/apexai`](https://github.com/haruiz/apexai/)** — the
  ApexAI codebase whose CAN-bus reader prototypes and framing
  conventions live on in `apps/edge-daemon/pitwall/`.
- **[`rabimba/trustable-ai-codelab`](https://github.com/rabimba/trustable-ai-codelab/)** —
  the prototype coaching service / codelab whose reactive hooks and
  TTS triggers are being re-implemented as Vue 3 composables in
  `apps/paddock-dashboard/` per the V2 PRD's frontend-standardization
  mandate.
- Any earlier per-pod fragments (Beginner / Intermediate / Advanced)
  whose post-Sonoma post-mortem (PRD §1.2) directly shaped this V2
  architecture.

### The Pitwall team

Every line of the source tree this monorepo inherits came from the
people who built and operated
[`mlnomadpy/pitwall`](https://github.com/mlnomadpy/pitwall) through
the Sonoma field-test cycle. Thank you for the AiM MXP pipeline,
the SQLite-on-Termux warm path, the no-fake-fallback discipline,
the Sonoma track intel, the deploy ladder, and the docs we read
every day.

- **Vijay Vivekanand** — [@VijayVivekanand](https://github.com/VijayVivekanand) — Google for Startups
- **Aileen Villanueva Lecuona** — [@aileenvl](https://github.com/aileenvl) — Google Developer Expert
- **Hemanth HM** — [@hemanth](https://github.com/hemanth) — Google Developer Expert
- **Rabimba** — [@rabimba](https://github.com/rabimba)
- **Henry** — [@haruiz](https://github.com/haruiz)
- **Taha Bouhsine** — [@mlnomadpy](https://github.com/mlnomadpy) — Google Developer Expert

### In-car data system — Brian Luc

The single thing without which **none** of this exists: **Brian Luc**
designed the in-car data system that gets telemetry off the car in
the first place. The AiM MXP / CAN-over-USB-C pipeline every
downstream component consumes — `apps/edge-daemon`, the
`packages/core-telemetry` DEL math, the paddock-dashboard's analytics,
the cloud-backend's cold-path debriefs — all of them ultimately read
data that exists in software only because of Brian's architecture.
Thank you, Brian.


### Inspirations + pedagogy

- **Ross Bentley** — the Pedagogical RAG store (PRD §4.2) and the
  coaching cue vocabulary draw directly from Bentley's
  performance-driving curriculum. The DEL exists in part to
  translate that curriculum into machine-actionable structure.

### Open-source dependencies

This project would not exist without the ecosystems it sits on top
of: Flask + waitress, DuckDB, Vue, Vite, FastAPI, Pydantic, Ktor,
LiteRT, cantools, python-can, pyarrow, osmdroid, Vico, and the rest
of the dependency graph declared in each app's
`pyproject.toml` / `package.json`. Thanks to all of their
maintainers.

## License

Proprietary — see individual files for headers.

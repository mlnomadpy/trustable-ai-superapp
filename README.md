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
| [`apps/localllm/`](apps/localllm/) | Termux runit / Docker | OpenAI-compatible local model server (Gemma-4-e2b on-phone; QLoRA-fine-tuned Gemma 4 on the trackside laptop for air-gapped fallback per PRD §6.4). |

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

- **PRD §2** — monorepo + GDE / Strike Agency / Founder governance
  topology.
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

## License

Proprietary — see individual files for headers.

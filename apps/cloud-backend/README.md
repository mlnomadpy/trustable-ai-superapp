# `apps/cloud-backend`

FastAPI service that owns the strategic-reasoning workloads kept off
the in-car phone. Boots without GCP credentials so feature engineers
can iterate locally; Vertex AI / Gemini clients are lazy-loaded under
`cloud_backend.services`.

## Responsibilities (PRD §4–5)

- **Cold-path curriculum generation** — post-session, calls Gemini
  1.5 Pro to produce a `<50KB` learning-plan JSON keyed on a single
  highest-impact improvement area.
- **Pedagogical RAG store** — vector index seeded with Ross Bentley's
  performance-driving curriculum (PRD §4.2). Queried per-corner with
  physics-delta vectors, not text keywords.
- **Gold-trace ingestion** — accepts a verified reference lap per
  car/track and exposes it as the diff target for the DEL.
- **Paddock-sync REST surface** — endpoints consumed by the
  paddock-dashboard under all three air-gapped topologies (PRD §6).
- **Cold-to-hot path push** — packages each generated learning plan
  for transport over USB-C ADB, ad-hoc hotspot, or device-local.

## Stack

- FastAPI + uvicorn (`pyproject.toml` deps).
- pydantic v2 for schemas; JSON schemas mirrored at
  `packages/core-telemetry/schemas/`.
- google-cloud-aiplatform + google-genai (optional `[vertex]` extra)
  — the cloud-only entrypoints; air-gapped fallback uses the local
  Gemma 4 container instead (PRD §6.4).

## Quick start

```bash
uv sync --package cloud-backend --extra dev
uv run cloud-backend
# → http://127.0.0.1:8088/health
```

With Vertex AI (production):

```bash
uv sync --package cloud-backend --extra dev --extra vertex
export GOOGLE_CLOUD_PROJECT=...
export GOOGLE_APPLICATION_CREDENTIALS=...
uv run cloud-backend
```

## Tests

```bash
uv run --package cloud-backend pytest
```

## What's not in this scaffold yet

- The actual route modules (`api/curriculum.py`, `api/debrief.py`,
  `api/gold_trace.py`, `api/paddock_sync.py`) — one PR per capability.
- The pedagogical RAG store — needs vector DB choice (Vertex AI
  Matching Engine vs sqlite-vec for the air-gapped case).
- Auth — paddock sync needs cryptographic integrity validation on
  learning-plan transport (PRD §7 connection-handshake safe-gate).

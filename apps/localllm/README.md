# `apps/localllm`

OpenAI-compatible HTTP shim that serves **Gemma-4-e2b** (or any
locally-quantized model) on `127.0.0.1:8080`. Two deploy modes both
live here:

1. **On-phone (PRD §3, §7 cloud-independence mandate)** — runs under
   Termux as a runit service. The edge-daemon's coach loop calls
   `POST /v1/chat/completions` over loopback; no cellular round-trip.
2. **Trackside laptop (PRD §6.4 air-gapped fallback)** — runs as a
   Docker container on the paddock laptop. When Vertex AI is
   unreachable, the cloud-backend reroutes cold-path generation to
   this instance, which holds the QLoRA-fine-tuned Gemma 4 weights.

The actual server binary, model weights, and the inference engine are
**not** vendored into this repo. This folder owns the **deploy
contract**: config, service definitions, install scripts, health
probes, and the documented HTTP surface the edge-daemon and
cloud-backend rely on.

## Layout

```
apps/localllm/
├── README.md
├── config/
│   ├── phone.toml         model + port + max_tokens for Termux/Pixel
│   └── trackside.toml     model + port + max_tokens for Docker/laptop
├── service/
│   └── localllm/          runit definition for Termux
│       ├── run            sv-launchable script
│       └── log/run        svlogd config
├── docker/
│   ├── Dockerfile         trackside Gemma 4 container
│   └── compose.yaml       one-command bring-up for the paddock laptop
├── scripts/
│   ├── install-phone.sh   download weights → ~/llms/, link service
│   ├── install-trackside.sh   docker build + compose up
│   └── healthcheck.sh     curls /v1/models, asserts 200
└── prompts/               (optional) shared system prompts; most
                          coaching prompts belong to packages/core-telemetry
```

## HTTP surface (the contract)

Both deploy modes must respond to the OpenAI-compatible subset the
edge-daemon and cloud-backend depend on:

| Method | Path | Used by |
|--------|------|---------|
| `GET`  | `/v1/models` | health probe |
| `POST` | `/v1/chat/completions` | edge coaching loop + cloud cold path |
| `POST` | `/v1/embeddings` | (cloud only) pedagogical RAG indexing |

Stream tokens via `text/event-stream` (`stream: true`). Token
throughput must clear the PRD §3.1 gate of **20 tok/s** on-device;
sub-threshold deploys fail CI.

## Quick start

### Phone (Termux + runit)

```bash
# Idempotent: re-running just reconciles the service definition.
adb shell 'su 10312 -c "bash"' < apps/localllm/scripts/install-phone.sh
# Then:
sv up localllm
curl http://127.0.0.1:8080/v1/models
```

### Trackside laptop (Docker)

```bash
cd apps/localllm/docker
docker compose up -d
./apps/localllm/scripts/healthcheck.sh
```

## Why this is its own app, not a deploy/ script

Per PRD §6.4 the laptop's Gemma 4 instance ships **fine-tuned
weights** (QLoRA on 20k track-telemetry instruction pairs). That's a
versioned artifact with its own release cadence, distinct from either
the edge-daemon or the cloud-backend. Promoting it to `apps/` makes
the dependency explicit, gives it a CHANGELOG, and lets the platform
team gate weight rollouts behind the same throughput CI as model
config changes.

## Phase 0 deliverables

1. `config/phone.toml` and `config/trackside.toml` — committed with
   the exact knobs the edge-daemon ENV currently sets
   (`PITWALL_ADK_OPENAI_URL`, `PITWALL_ADK_OPENAI_MODEL`, max-tokens,
   context-window cap of 3-second sliding window per PRD §3.2).
2. `service/localllm/run` — port the working runit script from
   `deploy/termux/service/pitwall-bridge/run` for shape.
3. `scripts/install-phone.sh` — supersedes the ad-hoc
   `deploy/phone/30-python-deps.sh` LocalLLM bootstrap; idempotent.
4. `docker/Dockerfile` + `docker/compose.yaml` — Gemma 4 image with
   the fine-tuned weights mounted from a host path.
5. `scripts/healthcheck.sh` — single command the deploy ladder calls
   from `deploy/phone/00-check.sh`.

All five land as separate, named PRs after the contract is reviewed.

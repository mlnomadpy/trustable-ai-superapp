# ADR-022 — On-Phone LocalLLM Server (OpenAI-Compatible)

**Status:** Accepted
**Date:** 2026-05-12
**Relates to:** [ADR-017](017-three-tier-coach-architecture.md), [ADR-019](019-adk-multi-agent-backend.md), [ADR-021](021-adk-second-audit.md)

---

## Context

ADR-017 mandated a fully on-device LLM stack. ADR-019–021 implemented the
paddock tier on ADK with a single, hard-coded model client:
`Gemini(base_url="http://localhost:8001", model="gemma-4-e4b")` against a
separately-launched `lit serve` Python process. The earlier ADK architecture
doc went further and codified this as a constraint: *"Native LiteRT-LM — no
Ollama or LiteLLM."*

That setup was workable on a laptop but awkward on the actual deployment
target. On a Pixel 10, `lit serve` had to run as a second Termux foreground
service alongside the bridge — two wake locks, two processes, two startup
ordering bugs, two things to debug at 4 a.m. before a track day. It also
forced the LLM runtime to live inside the same Termux sandbox as the bridge,
which has no GPU/NPU delegate access on most Android builds.

Meanwhile, a **sibling project shipped**:
[LocalLLM](https://www.tahabouhsine.com/localllm/) — an Apache-2.0 Android
APK ([github.com/mlnomadpy/localllm](https://github.com/mlnomadpy/localllm))
that:

- runs **LiteRT-LM** natively in an Android app process (`com.google.ai.edge.litertlm:litertlm-android:0.11.0`),
- exposes an **OpenAI-compatible HTTP server** on `POST /v1/chat/completions` at port `:8099`,
- accepts `.litertlm` model bundles from the
  [`litert-community`](https://huggingface.co/litert-community) HuggingFace
  collection (Gemma 4 family),
- supports **SSE streaming**, signed-bearer-token auth, and
- uses LiteRT's AUTO delegate (GPU → CPU fallback) for acceleration.

LocalLLM is a normal APK with a Catalog / Chat / Dashboard / Settings UI.
A driver installs it once, downloads a model from the in-app catalog, and
the server autostarts. From Pitwall's perspective, there is now a stable,
authenticated, OpenAI-shaped HTTP endpoint at `127.0.0.1:8099/v1` on the
same phone — without Pitwall having to host the model itself.

That changes the primary deployment story.

---

## Decision

**Adopt LocalLLM as the default on-device LLM server for every pitwall LLM
request** — both the warm path (`LitertCoach.brief()` / `debrief()`) and the
paddock ADK tier. Refactor the paddock model wiring into a **three-way
backend selector** chosen by `PITWALL_ADK_BACKEND` and have `LitertCoach`
honour the same `PITWALL_ADK_OPENAI_URL` env (renamed 2026-05; the legacy
`PITWALL_LITERT_URL` is still accepted with a `DeprecationWarning`). The
defaults are flipped — fresh installs talk to LocalLLM with no env vars set.

| `PITWALL_ADK_BACKEND`  | Transport            | Server                            | Client class                          | Used for                                                  |
| ---------------------- | -------------------- | --------------------------------- | ------------------------------------- | --------------------------------------------------------- |
| `openai` *(default)*   | HTTP → `127.0.0.1`   | **LocalLLM APK** (`:8099/v1`)     | `LiteLlm(api_base=..., api_key=...)`  | **Pixel field deployment — primary path**                 |
| `engine`               | In-process (no HTTP) | *(none — same process as bridge)* | `LitertLmModel(BaseLlm)`              | Headless Termux setups that already load the engine for the warm path |
| `litertlm`             | HTTP → `lit serve`   | `lit serve` Python process        | `Gemini(base_url=..., model=...)`     | Legacy / desktop dev with `lit serve` already running     |

All three speak to a model **on the same phone as the bridge**. None of them
dial out to a hosted API. The privacy guarantee from ADR-017 is unchanged.

The warm-path `LitertCoach` follows the same default. Its constructor reads
`PITWALL_ADK_OPENAI_URL` (default `http://localhost:8099/v1`; legacy alias
`PITWALL_LITERT_URL` still honoured) and routes
`_generate()` over HTTP via stdlib `urllib.request`. Setting the env to an
empty string opts back into the in-process `litert_lm.Engine`.

### Why LocalLLM specifically

- **Native Android process, native delegates.** LocalLLM runs as a regular
  Android app and can use LiteRT's GPU delegate on a Pixel's Tensor G5 NPU
  via the AUTO backend. Termux processes typically cannot.
- **Stable HTTP contract.** OpenAI's `chat.completions` shape is a widely
  supported, well-tested protocol surface — ADK's `LiteLlm` wrapper speaks
  it natively, as do dozens of other ecosystems.
- **No Termux co-tenancy.** Crashes in the model runtime don't bring down
  the bridge; the bridge can reconnect via HTTP. Compared to in-process
  inference, this is a clean process boundary.
- **First-class model catalogue.** A driver doesn't need to know about
  `huggingface-cli` or `.litertlm` paths — they pick a model from the
  in-app catalog and the server autostarts.
- **Signed-bearer-token auth.** LocalLLM supports keyed access so a
  malicious app on the same device can't trivially hit the server.
  Pitwall passes the token via `PITWALL_ADK_OPENAI_API_KEY` (legacy:
  `PITWALL_LITERT_API_KEY`).

### Configuration surface

| Variable                       | Default                              | Used by                          |
| ------------------------------ | ------------------------------------ | -------------------------------- |
| `PITWALL_ADK_BACKEND`          | `openai`                             | paddock selector (`engine` \| `litertlm` \| `openai`) |
| `PITWALL_ADK_OPENAI_URL`       | `http://localhost:8099/v1`           | **both warm and paddock** HTTP base; empty string ⇒ in-process. Legacy: `PITWALL_LITERT_URL` |
| `PITWALL_ADK_OPENAI_MODEL`     | `gemma3n-e2b`                        | model id (must match LocalLLM's loaded model). Legacy: `PITWALL_LITERT_MODEL` |
| `PITWALL_ADK_OPENAI_API_KEY`   | `lit-serve-not-required`             | LocalLLM bearer token. Legacy: `PITWALL_LITERT_API_KEY` |
| `PITWALL_LITERT_SIDECAR_URL`   | `http://127.0.0.1:8080`              | LiteRT-LM Kotlin sidecar URL. Legacy: `PITWALL_LITERTLM_URL` |
| `PITWALL_LITERT_SIDECAR_MODEL` | `gemma-4-e2b`                        | LiteRT-LM Kotlin sidecar model id. Legacy: `PITWALL_LITERTLM_MODEL` |
| `PITWALL_LITERTLM_PATH`        | *(unset)*                            | `engine` (`.litertlm` bundle path) |
| `PITWALL_LITERTLM_BUDGET`      | `30000`                              | `engine` (KV-cache char budget)  |
| `PITWALL_LITERT_HTTP_TIMEOUT_S` | `30`                                | warm-path HTTP client timeout    |

> **Env vars renamed 2026-05 (this ADR amended).** The `PITWALL_LITERT_*`
> family was easy to confuse with `PITWALL_LITERTLM_*` (one letter apart,
> two completely different things). The new names — `PITWALL_ADK_OPENAI_*`
> for the ADK→OpenAI-compatible HTTP shim and `PITWALL_LITERT_SIDECAR_*`
> for the Kotlin LiteRT-LM sidecar — are self-describing. All legacy names
> continue to work and emit a `DeprecationWarning` on first read; the
> fallback lives in `src/pitwall/_env.py:get_env_with_legacy`.

> **Default flipped 2026-05-12.** Fresh installs of pitwall talk to LocalLLM
> with zero env vars set. To restore the previous `lit serve` behaviour:
> `PITWALL_ADK_BACKEND=litertlm PITWALL_ADK_OPENAI_URL=http://localhost:8001`.

### Implementation

**Paddock (`src/pitwall/features/coaching/adk_agents.py`)** branches at
module-load:

```python
_BACKEND  = os.getenv("PITWALL_ADK_BACKEND", "openai").lower()
_MODEL_ID = get_env_with_legacy(
    "PITWALL_ADK_OPENAI_MODEL", "PITWALL_LITERT_MODEL", "gemma3n-e2b")
_MODEL_URL = get_env_with_legacy(
    "PITWALL_ADK_OPENAI_URL", "PITWALL_LITERT_URL",
    "http://localhost:8099/v1")

if _BACKEND == "engine":
    _model = LitertLmModel(model=_MODEL_ID)               # in-process

elif _BACKEND == "openai":                                 # default
    _model = LiteLlm(                                      # OpenAI-compatible HTTP
        model=_MODEL_ID,
        api_base=_MODEL_URL,                               # → LocalLLM at :8099/v1
        api_key=get_env_with_legacy(
            "PITWALL_ADK_OPENAI_API_KEY", "PITWALL_LITERT_API_KEY",
            "lit-serve-not-required"),
    )

else:                                                      # legacy: lit serve
    _model = Gemini(model=_MODEL_ID, base_url=_MODEL_URL)
```

**Warm path (`src/pitwall/features/coaching/coach_engine.py:LitertCoach`)**
honours the same env. Its constructor reads `PITWALL_ADK_OPENAI_URL`
(legacy: `PITWALL_LITERT_URL`); if non-empty (true by default),
`_generate()` POSTs to LocalLLM's
`/chat/completions` via stdlib `urllib.request` — no new dependency. The
in-process `litert_lm.Engine` path is reached only when the env is
explicitly set to an empty string.

```python
# coach_engine.py — LitertCoach.__init__
http_url = (get_env_with_legacy(
    "PITWALL_ADK_OPENAI_URL", "PITWALL_LITERT_URL",
    self.DEFAULT_HTTP_URL) or "").strip()
if http_url:
    self._http_url   = http_url.rstrip("/")               # → :8099/v1
    self._http_model = get_env_with_legacy(
        "PITWALL_ADK_OPENAI_MODEL", "PITWALL_LITERT_MODEL",
        self.DEFAULT_HTTP_MODEL)
    self._http_api_key = get_env_with_legacy(
        "PITWALL_ADK_OPENAI_API_KEY", "PITWALL_LITERT_API_KEY",
        "lit-serve-not-required")
    self._llm = "http"                                    # truthy sentinel
    return
# else: lazy in-process engine load (legacy path)
```

`LiteLlm` ships with `google-adk[litellm]`. It is an optional install — the
import is wrapped in a `HAS_LITELLM` flag and the `openai` branch raises a
clear `RuntimeError` directing the user to install the extra if it's missing.
The warm-path HTTP client uses only stdlib (`urllib.request`), so it works
out of the box.

### What does *not* change

- Hot path (`RuleCoach` + canonical phrases) is untouched — ADK still never
  touches the < 100 ms tier ([ADR-017](017-three-tier-coach-architecture.md)).
- Warm path (`LitertCoach`, in-process Gemma 4 E2B via `litert_lm.Engine`) is
  untouched. The backend selector only governs the **paddock** ADK tier.
- All 18 agents, 15 tools, KV-cache reuse strategy, and the `agent_traces`
  DuckDB schema ([ADR-021](021-adk-second-audit.md)) are byte-identical
  across backends.
- Privacy guarantee: every supported backend is local. The bridge still
  binds to `127.0.0.1`. No cloud round-trip is introduced.

---

## Deployment story (recommended Pixel setup)

```
┌─────────────────────── Pixel 10 ───────────────────────┐
│                                                         │
│   ┌──────────────────────┐                              │
│   │ LocalLLM (APK)       │   downloads .litertlm from   │
│   │  ├─ Catalog UI       │   the in-app catalog;        │
│   │  ├─ LiteRT-LM 0.11   │   AUTO delegate uses GPU on  │
│   │  └─ HTTP :8099       │   Tensor G5 when available   │
│   └──────────┬───────────┘                              │
│              │                                          │
│              │  127.0.0.1:8099/v1/chat/completions      │
│              │  Bearer <signed-token>                   │
│              ▼                                          │
│   ┌──────────────────────┐                              │
│   │ Pitwall bridge       │                              │
│   │  (Termux foreground) │                              │
│   │  PITWALL_ADK_BACKEND │                              │
│   │     = openai         │                              │
│   └──────────────────────┘                              │
└─────────────────────────────────────────────────────────┘
```

Two apps, one phone, one localhost hop, zero cloud.

---

## Consequences

**Positive:**

- Single primary deployment story on Pixel: install LocalLLM APK + Termux
  bridge; no second Python process to babysit.
- LocalLLM owns model lifecycle (download, switch, unload) via its native
  UI — drivers don't shell into Termux to swap models.
- Clean process boundary: a model-runtime crash no longer takes the bridge
  down.
- GPU/NPU access via LiteRT's AUTO delegate, which Termux-hosted runtimes
  generally can't reach.
- Same `openai` code path works on dev machines pointed at Ollama / LM
  Studio / llama.cpp / vLLM — one path covers both production and dev.

**Negative:**

- Two APKs on the phone instead of one. Mitigated: LocalLLM is a published
  open-source APK with its own release cadence and UI; this is a cleaner
  separation than embedding the model runtime in the bridge.
- The `openai` path adds an HTTP hop the `engine` path doesn't have. The
  hop is `127.0.0.1` and measured overhead is sub-millisecond; the paddock
  tier already operates at 2–15 s latencies, so it's noise.
- `LiteLlm` (litellm) is a new optional dependency. Mitigated by gating
  behind `HAS_LITELLM` and only requiring it when `PITWALL_ADK_BACKEND=openai`.

**Neutral:**

- Default behaviour (`litertlm` → `lit serve`) is preserved bit-for-bit.
  Existing deployments need to change nothing. New deployments are
  explicitly directed to set `PITWALL_ADK_BACKEND=openai` and point at
  LocalLLM.

---

## Validation

- ADK tests pass against all three backends.
- Smoke test: `PITWALL_ADK_BACKEND=openai PITWALL_ADK_OPENAI_URL=http://localhost:8099/v1 PITWALL_ADK_OPENAI_MODEL=gemma-4-e2b-it PITWALL_ADK_OPENAI_API_KEY=<token>` round-trips through `PitwallOrchestrator` against a LocalLLM instance loaded with a Gemma 4 E2B `.litertlm`. (Legacy `PITWALL_LITERT_*` names still work for one cycle.)
- The same wiring also passes against an Ollama instance (`:11434/v1`) on a dev macOS box — confirms the `openai` backend is portable across OpenAI-compatible servers.
- The constraint *"Native LiteRT-LM — no Ollama or LiteLLM"* in
  `docs/adk-agent-architecture.md` is removed and replaced with the
  backend-selector matrix above.

---

## References

- LocalLLM website: <https://www.tahabouhsine.com/localllm/>
- LocalLLM repo: <https://github.com/mlnomadpy/localllm>
- ADK `LiteLlm` model wrapper: <https://google.github.io/adk-docs/agents/models/litellm/>
- LiteRT-LM Android: `com.google.ai.edge.litertlm:litertlm-android:0.11.0`
- `litert-community` model collection: <https://huggingface.co/litert-community>

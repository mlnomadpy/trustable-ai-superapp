# ADR-025 — Warm-path `LitertCoach` is LocalLLM-only

**Status:** Accepted
**Date:** 2026-05-28
**Closes:** the open question in [ADR-024](024-localllm-sole-llm-transport.md)
**Relates to:** [ADR-017](017-three-tier-coach-architecture.md), [ADR-018](018-field-readiness-blockers-and-pedagogy-tuning.md), [ADR-022](022-openai-compatible-backend-selector.md), [ADR-024](024-localllm-sole-llm-transport.md)

---

## Context

[ADR-024](024-localllm-sole-llm-transport.md) consolidated the **paddock**
ADK tier to a single LocalLLM HTTP transport and explicitly deferred the
warm-path question: `LitertCoach.brief()` / `debrief()` still carried two
transports — HTTP-to-LocalLLM (default) and in-process `litert_lm.Engine`
when `PITWALL_ADK_OPENAI_URL=""`. That dual-transport state inherited
ADR-022's escape hatches and added its own:

- `LitertCoach.__init__` ran a model-path probe (`DEFAULT_MODEL_PATHS`,
  five candidates), tried to import `litert_lm`, opened an engine context
  manager, and tracked `_engine`, `_engine_ctx`, `_init_error` state.
- `_generate` branched on `self._http_url` to pick HTTP or in-process.
- `make_coach("auto")` probed `LitertCoach._llm is not None` and fell back
  to `RuleCoach` on engine load failure.
- A separate `litert_lm_model.py` (LitertLmModel adapter for ADK) and its
  `test_litert_lm_model.py` lived alongside, even though ADR-024 already
  retired the ADK `engine` backend that called them.
- The coaching conftest had to `os.environ["PITWALL_ADK_OPENAI_URL"] = ""`
  at import time so warm-path tests wouldn't accidentally HTTP to a live
  LocalLLM.

Looking at what production actually did:

- Every shipped warm-path call in field-test logs went through the HTTP
  path. The `.litertlm` engine probe never produced a loaded engine on
  the Pixel build because `litert_lm` doesn't ship on Termux.
- The dual-transport branch existed for "desktop dev without LocalLLM
  installed." That's a configuration nobody operates — desktop dev runs
  Ollama / vLLM, which is the same `openai`-compatible HTTP path.
- The `make_coach("auto") → RuleCoach` fallback existed for "engine fails
  to load." With HTTP it can't fail at construction; it fails at call
  time, which `brief()` / `debrief()` already handle via the no-fake-data
  policy (return empty + record friction) per ADR-018.

Same shape as ADR-024: a single-path system in a two-path coat.

---

## Decision

**`LitertCoach` is HTTP-only.** It dials LocalLLM at
`PITWALL_ADK_OPENAI_URL` (default `http://localhost:8099/v1`) — the same
endpoint and the same `LiteLlm` contract the ADK paddock tier uses
([ADR-024](024-localllm-sole-llm-transport.md)). Warm and paddock now
share one transport story.

Concrete changes:

1. **`pitwall/features/coaching/litert_coach.py`** is rewritten:
   - Constructor takes only `driver_level`, `max_tokens`, `temperature`
     (kwarg-only). `model_path` and `backend` are gone.
   - No engine import, no model-path resolution, no `_engine` /
     `_engine_ctx` / `_init_error` / `_init_runtime` /
     `_resolve_model_path` / `close()` / `__del__`.
   - `_generate` calls `_generate_http` directly; the branch is gone.
   - `health()` reports only the HTTP transport.
   - The no-fake-data policy ([ADR-018](018-field-readiness-blockers-and-pedagogy-tuning.md))
     is preserved: `brief()` / `debrief()` return empty narratives + emit
     friction records when LocalLLM is unreachable.

2. **`pitwall/features/coaching/coach_engine.py`** loses
   `litert_model_path` and `tflite_model_path` kwargs on `make_coach`,
   loses the `"tflite"` alias, and loses the `try/except` engine-load
   probe in the `"auto"` branch. `make_coach("auto")` and
   `make_coach("litert")` now always return a `LitertCoach`; transport
   health is observed at call time, not construction.

3. **`pitwall/features/coaching/litert_lm_model.py`** is **deleted**. It
   was the `BaseLlm` adapter for ADK's retired `engine` backend
   (ADR-024 retired the backend; ADR-025 retires the adapter). It was
   already unused by production code post-ADR-024.

4. **Dead exports removed**: `TfliteCoach` (deprecated alias for
   `LitertCoach`) and `_extract_assistant_text` (engine response parser)
   are deleted from `litert_coach.py` and dropped from `coach_engine.py`'s
   `__all__`.

5. **Tests:**
   - `tests/features/coaching/test_litert_lm_model.py` — **deleted**
     (tests the deleted adapter).
   - `tests/features/coaching/test_coach_engine_litert.py` — **deleted**
     (in-process engine integration tests; the integration target no
     longer exists).
   - `tests/features/coaching/test_coach_engine.py` — five tests that
     monkeypatched `LitertCoach._init_runtime` to simulate engine
     load/failure are rewritten to monkeypatch `_generate_http` and
     simulate HTTP transport success/failure. Same coverage intent
     (friction record fires on backend failure; returns empty narrative;
     sink errors swallowed) over the new transport.
   - `tests/features/coaching/conftest.py` — drops the
     `os.environ["PITWALL_ADK_OPENAI_URL"] = ""` opt-out (which only
     made sense when the engine path existed) and the matching legacy
     alias mutation. Tests now patch `_generate_http` directly.

6. **`VALID_EMOTIONS`** gains `focused` — the ADK system prompt advertises
   it in `_COMMON_PREFIX`, so the parser must accept it. (Caught while
   repairing `test_coach_ask_uses_intent_override`; previously the
   parser silently downgraded `focused` → `neutral`, dropping a valid
   emotion the LLM was explicitly told to emit.)

### Configuration after the change

| Variable                        | Default                       | Used by                                      |
| ------------------------------- | ----------------------------- | -------------------------------------------- |
| `PITWALL_ADK_OPENAI_URL`        | `http://localhost:8099/v1`    | Warm path **and** paddock tier (legacy: `PITWALL_LITERT_URL`) |
| `PITWALL_ADK_OPENAI_MODEL`      | `gemma3n-e2b`                 | Model id (legacy: `PITWALL_LITERT_MODEL`)    |
| `PITWALL_ADK_OPENAI_API_KEY`    | `lit-serve-not-required`      | Bearer token (legacy: `PITWALL_LITERT_API_KEY`) |
| `PITWALL_LITERT_HTTP_TIMEOUT_S` | `30`                          | Warm-path HTTP timeout (seconds)             |
| `PITWALL_LLM_MAX_TOKENS`        | `512`                         | Warm-path completion budget                  |

Retired: `PITWALL_LITERT_SIDECAR_URL`, `PITWALL_LITERT_SIDECAR_MODEL`,
`PITWALL_LITERTLM_PATH`, `PITWALL_LITERTLM_BUDGET`, and any expectation
that setting `PITWALL_ADK_OPENAI_URL=""` opts into an in-process engine
(it never did anything else — there's no engine to opt into).

---

## Consequences

**Positive:**

- One coaching transport, end to end. The three-tier latency budgets
  (Hot < 50 ms, Warm < 100–3 s, Paddock 2–15 s) still hold, but every
  LLM call — warm or paddock — goes through the same `LiteLlm` / urllib
  HTTP shape against the same LocalLLM endpoint.
- `LitertCoach.__init__` is cheap and infallible. No model-path probe at
  boot, no native-lib load, no context manager to leak. Construction is
  ~10 lines of attribute setup.
- The friction record now answers a sharper question — "was the
  configured LocalLLM endpoint reachable, and what did it return?" —
  rather than "did the configured backend (which?) load and respond?"
- Both `litert_lm_model.py` (300 lines + tests) and
  `test_coach_engine_litert.py` (300 lines) come out of the tree.

**Negative:**

- Operators who genuinely want an in-process LiteRT-LM warm path (none
  in the field-test deployments) would need to re-introduce one. The
  upstream `litert_lm` package and the `.litertlm` artifact pipeline
  still exist; bringing back an in-process path is a code change, not
  an env flip. Acceptable given the field signal.
- A fresh dev workstation needs *some* OpenAI-compatible server on
  `127.0.0.1` for the warm path to produce text. Ollama on `:11434`,
  vLLM on `:8000`, or LocalLLM itself all work — point
  `PITWALL_ADK_OPENAI_URL` at them. Without one, briefs and debriefs
  return empty narratives and record friction (which is the explicit
  no-fake-data policy from ADR-018, not a regression).

**Neutral:**

- The on-device guarantee from [ADR-017](017-three-tier-coach-architecture.md)
  is unchanged — every supported transport is still `127.0.0.1`. ADR-025
  removed an implementation degree of freedom, not a product property.
- `propose()` still delegates to `RuleCoach` per ADR-017. LLM latency was
  never appropriate for sub-corner cues regardless of transport.

---

## Validation

- `python -c "from pitwall.features.coaching.coach_engine import make_coach;
  c = make_coach('auto'); print(c.name, c.health())"` →
  `litert {'transport': 'http', 'http_url': 'http://localhost:8099/v1', ...}`.
- `grep -R 'litert_lm_model\|_engine_ctx\|_init_runtime\|DEFAULT_MODEL_PATHS'
  apps/edge-daemon/pitwall` returns no matches.
- `apps/edge-daemon/tests/features/coaching/` runs green for every coaching
  test that doesn't have a pre-existing unrelated failure.

---

## References

- [ADR-024](024-localllm-sole-llm-transport.md) — paddock-tier consolidation that opened this open question
- [ADR-022](022-openai-compatible-backend-selector.md) — original multi-transport selector (superseded)
- [ADR-017](017-three-tier-coach-architecture.md) — three-tier coaching, propose() never goes through LLM
- [ADR-018](018-field-readiness-blockers-and-pedagogy-tuning.md) — no-fake-data policy + friction sink
- [LocalLLM](https://www.tahabouhsine.com/localllm/) — upstream Apache-2.0 APK

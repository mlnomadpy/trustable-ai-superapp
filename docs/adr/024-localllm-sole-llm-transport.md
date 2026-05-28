# ADR-024 — LocalLLM as the Sole LLM Transport

**Status:** Accepted
**Date:** 2026-05-28
**Supersedes:** [ADR-022](022-openai-compatible-backend-selector.md) (the multi-backend selector)
**Relates to:** [ADR-017](017-three-tier-coach-architecture.md), [ADR-019](019-adk-multi-agent-backend.md), [ADR-021](021-adk-second-audit.md), [ADR-023](023-on-device-voice-onnx.md)

---

## Context

[ADR-022](022-openai-compatible-backend-selector.md) introduced a three-way
backend selector (`PITWALL_ADK_BACKEND` ∈ `{openai, engine, litertlm}`) so
operators could choose between LocalLLM over HTTP, an in-process
`litert_lm.Engine`, or a separately-launched `lit serve` process. It also
flipped the default to LocalLLM (`openai`) and kept `google-adk` and `litellm`
as **optional** dependencies — the bridge booted without them and degraded to
`HTTP 503 ADK not available` on every `/coach/*` route.

Two and a half weeks of operating that on the Sonoma field-test build made
the cost clear:

- **The selector was a single-path system in a three-path coat.** Both the
  field-test phone build and CI ran the `openai` branch. The `engine` and
  `litertlm` branches existed for "headless Termux" and "desktop dev with
  lit serve" scenarios that nobody actually deployed. The `litertlm`
  branch's only remaining caller in production was a stale env var on one
  laptop.
- **The optional-dependency story was load-bearing nowhere.** `apps/edge-daemon`
  exists to serve the ADK paddock tier; without ADK installed the bridge has
  no `/coach/*` API surface and is useful only as a CAN logger. No-one ran it
  that way. Meanwhile, every blueprint route had to thread a `state.has_adk`
  guard and return a 503 envelope, and the bridge state object grew a `has_adk`
  flag whose only purpose was telling test code which 503 path to assert.
- **The defensive code rotted.** `adk_agents.py` had module-level stub
  `run_adk` / `stream_adk` / `_delete_session_async` raising `RuntimeError`
  alongside the real implementations, gated by `HAS_ADK`. The `engine` branch
  required a `LitertLmModel` import wrapped in its own `HAS_LITERTLM_MODEL`
  flag. `reset_driver_session` flushed an engine-backend KV cache that
  nothing in the deployed builds ever populated. Tests monkeypatched
  `state.has_adk = False` to exercise a branch that, by product decision,
  shouldn't exist.
- **The constraint we actually care about is the [ADR-017](017-three-tier-coach-architecture.md) on-device guarantee, not "which on-device transport".** Every supported
  backend dialled `127.0.0.1`. The selector wasn't a privacy lever; it was a
  packaging lever for a packaging problem we don't have.

ADR-023 (on-device voice via ONNX, 2026-05-23) reinforced the same pattern at
the voice layer: pick a single on-device transport, commit to it, stop
maintaining the escape hatches.

---

## Decision

**LocalLLM is the sole LLM transport for the paddock ADK tier.**

Concretely:

1. **`google-adk` and `litellm` move into the base `dependencies` of
   `apps/edge-daemon/pyproject.toml`.** The `[adk]` optional extra is
   removed. A bridge that can't import ADK fails to start, loudly.
2. **The `PITWALL_ADK_BACKEND` env var is retired.** `adk_agents.py`
   constructs exactly one model:
   ```python
   _model = LiteLlm(
       model=_LITELLM_MODEL,                # "openai/<id>"
       api_base=_MODEL_URL,                 # http://localhost:8099/v1
       api_key=_API_KEY,                    # LocalLLM bearer token
   )
   ```
   The `engine` (in-process `LitertLmModel`) and `litertlm` (HTTP to
   `lit serve` via `Gemini(base_url=…)`) branches are deleted.
3. **The defensive surface is removed.** Gone:
   - `HAS_ADK` flag and the `try/except ImportError` around `google.adk` imports in `adk_agents.py`
   - `HAS_LITELLM` flag and its missing-`litellm` `RuntimeError`
   - The `LitertLmModel` / `HAS_LITERTLM_MODEL` / `_reset_litertlm_conversations` / `_litertlm_kv_stats` optional-import block (the engine backend's hooks)
   - Stub `run_adk` / `stream_adk` / `_delete_session_async` that raised `"google-adk not installed"`
   - `state.has_adk` field and the `try/except` around `from pitwall.features.coaching.adk_agents import …` in `state.py`
   - Eight `if not state.has_adk: return jsonify({"error": "ADK not available"}), 503` guards across `bp_coaching.py`
   - `if state.has_adk and driver_id:` guard in `bp_session.py:session_start`
   - `HAS_ADK_TOOLS` flag in `adk_tools.py` (the `@_adk_tool` decorator was
     a no-op fallback in production all along — that's documented now)
4. **`reset_driver_session()` no longer flushes a warm-path KV cache.** It
   only manages the ADK `InMemorySessionService` entries it owns. The warm
   path's cache is reachable directly via
   `pitwall.features.coaching.litert_lm_model.reset_all_conversations()`
   for callers that need it.
5. **What stays:** the URL/model/api-key env overrides
   (`PITWALL_ADK_OPENAI_URL`, `_MODEL`, `_API_KEY`) and their legacy
   `PITWALL_LITERT_*` aliases. They're still useful — port overrides on dev
   workstations, model id pinning for CI. The legacy aliases keep working
   with `DeprecationWarning` via `pitwall._env.get_env_with_legacy`.
6. **Tests covering deleted branches are removed**, not merely skipped:
   `test_coach_ask_returns_503_when_adk_disabled`,
   `test_coach_ask_stream_returns_503_when_adk_disabled`,
   `test_coach_traces_returns_unavailable_when_adk_disabled`,
   `test_adk_default_backend_is_litertlm_gemini`,
   `test_adk_openai_backend_uses_litellm` (env-mutation half),
   `test_engine_backend_selectable_via_env`,
   `test_reset_driver_session_flushes_litertlm_cache`.
   A new `test_adk_model_is_local_llm` locks the consolidation.

The warm path (`LitertCoach`) is **not** in scope here. It still loads
`litert_lm.Engine` in-process and reads its own `PITWALL_ADK_OPENAI_URL`
override per ADR-022 — see "Open question" below.

### Configuration after the change

| Variable                        | Default                       | Purpose                                      |
| ------------------------------- | ----------------------------- | -------------------------------------------- |
| `PITWALL_ADK_OPENAI_URL`        | `http://localhost:8099/v1`    | LocalLLM endpoint (legacy: `PITWALL_LITERT_URL`) |
| `PITWALL_ADK_OPENAI_MODEL`      | `gemma3n-e2b`                 | Model id (legacy: `PITWALL_LITERT_MODEL`)    |
| `PITWALL_ADK_OPENAI_API_KEY`    | `lit-serve-not-required`      | Bearer token (legacy: `PITWALL_LITERT_API_KEY`) |
| `PITWALL_ADK_TIMEOUT_S`         | `45`                          | Per-request timeout                          |
| `PITWALL_ADK_CHAR_BUDGET`       | `60000`                       | Session rotation char budget                 |
| `PITWALL_ADK_PROMPT_LOG`        | *(empty)*                     | JSONL prompt log path                        |

Retired: `PITWALL_ADK_BACKEND`, `PITWALL_LITERTLM_PATH`, `PITWALL_LITERTLM_BUDGET`.

---

## Consequences

**Positive:**

- The bridge boot path either reaches "ADK loaded — 17 agents (LocalLLM)" or
  it crashes at import time. There is no quiet degradation, no test fixture
  that mocks a state that production can no longer reach.
- `bp_coaching.py` is ~30 lines shorter and reads as 14 endpoints instead of
  14 endpoints × an absent-ADK branch each.
- `adk_agents.py` is ~50 lines shorter and the model selector reads top-to-
  bottom instead of `if/elif/else` over a non-existent product decision.
- The product invariant is back in the type signatures: if `state` exists,
  `state.adk_orchestrator` exists.

**Negative:**

- `apps/edge-daemon` is no longer installable without `google-adk` +
  `litellm`. This was already the case in practice — every shipped build
  had them — but it's now enforced. Headless CAN-logger-only deployments
  (none today) would need a separate pyproject.
- Switching ADK transports in the future requires a code change, not an env
  flip. Acceptable given LocalLLM is a sibling Apache-2.0 APK we own and
  Tahabouhsine's roadmap already covers the only realistic alternatives
  (Ollama / vLLM on dev workstations) via the same `LiteLlm(api_base=…)`
  call — point `PITWALL_ADK_OPENAI_URL` at them and it just works.

**Neutral:**

- The privacy and on-device guarantees from [ADR-017](017-three-tier-coach-architecture.md) are unchanged. We
  removed an implementation degree of freedom, not a product property.

---

## Open question — warm-path consolidation *(resolved by ADR-025)*

`LitertCoach` (`coach_engine.py` + `litert_lm_model.py`) still ships both an
HTTP path (via `PITWALL_ADK_OPENAI_URL`) and an in-process `litert_lm.Engine`
path (when the env is empty). Field-test data hasn't settled the question of
whether both should remain or whether the warm path should also commit to
LocalLLM-only. That's deferred to its own ADR after the post-Sonoma debrief
window closes. Until then, the warm path keeps its dual transport; this ADR
governs the paddock tier only.

> **2026-05-28 — closed by [ADR-025](025-warm-path-localllm-only.md):** the
> warm path is now LocalLLM-only. `litert_lm_model.py` deleted, the
> in-process engine branch in `LitertCoach.__init__` removed,
> `make_coach`'s `litert_model_path` / `tflite_model_path` kwargs dropped.
> Warm and paddock now share a single transport contract.

---

## Validation

- Module-level smoke import:
  ```python
  >>> from pitwall.features.coaching import adk_agents as a
  >>> a.coach_orchestrator.name
  'PitwallOrchestrator'
  >>> len(a.AGENT_REGISTRY)
  17
  >>> type(a._model).__name__, a._model.model
  ('LiteLlm', 'openai/gemma3n-e2b')
  ```
- Bridge boot prints `"✓ ADK coach_orchestrator loaded — 17 agents (LocalLLM)"`
  exactly once; no `"ADK disabled"` branch can be reached.
- `grep -R 'has_adk\|HAS_ADK\|PITWALL_ADK_BACKEND' apps/edge-daemon` returns
  no matches in shipped code.

---

## References

- [ADR-022](022-openai-compatible-backend-selector.md) — original multi-backend selector this ADR retires
- [LocalLLM](https://www.tahabouhsine.com/localllm/) — upstream Apache-2.0 APK
- ADK `LiteLlm` model wrapper: <https://google.github.io/adk-docs/agents/models/litellm/>

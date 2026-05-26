"""
LitertCoach — backend-owned on-device LLM inference via LiteRT-LM or HTTP.

Either talks HTTP to a LocalLLM OpenAI-compatible endpoint (ADR-022, default)
or in-process to `litert_lm.Engine` loading the Gemma 4 E2B `.litertlm`
bundle. brief() / debrief() are LLM-driven; propose() defers to RuleCoach per
ADR-017 (LLM latency is wrong for sub-corner cues).
"""

from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional


_log = logging.getLogger(__name__)

from pitwall._env import get_env_with_legacy
from pitwall.features.coaching.engine_base import (
    CoachContext,
    CoachEngine,
    CoachingMessage,
    CoachMode,
    _emit_friction,
    _extract_emotion,
)
from pitwall.features.coaching.prompts import (
    _split_brief_narrative_and_focus,
    _split_debrief_narrative_and_focus,
    _templated_pre_brief,
    build_pre_brief_user_prompt,
    build_post_session_user_prompt,
    build_system_prompt,
)
from pitwall.features.coaching.rule_coach import RuleCoach


# ─── On-device LiteRT-LM coach — MediaPipe Genai LLM Inference ────────────────


class LitertCoach(CoachEngine):
    """Backend-owned on-device LLM inference via Google's `litert-lm` package.
    Targets the Gemma 4 LiteRT-LM `.litertlm` artifact published at
    `litert-community/gemma-4-E2B-it-litert-lm` on Hugging Face.

    Why litert-lm (not mediapipe.tasks.python.genai.inference):
      - The `.litertlm` bundle format includes the model, tokenizer, KV-cache
        config, chat template, and platform-specific accelerators all in one
        file. Loaded via `litert_lm.Engine`.
      - The PyPI mediapipe wheel for desktop Python (macOS/Linux) does NOT
        ship the `genai.inference` submodule — that's Android/iOS only. The
        `litert-lm` package is Google's cross-platform replacement.
      - Same model file, same C++ runtime underneath; different Python wrapper.
      - Backends: CPU works on Apple Silicon and Linux; GPU on supported
        devices. We default to CPU and let the model metadata pick the
        accelerator backend.

    Install on a dev machine:
        pip install litert-lm
        litert-lm import --from-huggingface-repo \\
            litert-community/gemma-4-E2B-it-litert-lm \\
            gemma-4-E2B-it.litertlm gemma-4-e2b
        # Model now at ~/.litert-lm/models/gemma-4-e2b/model.litertlm

    On Termux (Pixel): same `litert-lm` package; same import command.

    Coaching scope (per the three-tier architecture):
      - `brief()` — pre-session paddock narrative. LLM-driven. 2-4 s OK.
      - `debrief()` — post-session paddock narrative. LLM-driven. 8-15 s OK.
      - `propose()` — DEPRECATED for LLM use. Returns None to defer to the
        canonical-phrase path (RuleCoach + pre-rendered audio). LLMs are
        too slow (>1 s) for sub-corner cues.

    If `litert-lm` isn't installed, the model file is missing, or any runtime
    error occurs, the LLM-driven methods (brief/debrief) fall back to
    templated narratives. Backend keeps a single source of truth for system
    instructions via build_system_prompt / build_user_prompt per ADR-013.
    """

    name = "litert"

    # Search order for the .litertlm model file. Adjusted to match the
    # `litert-lm import` CLI's storage layout + repo-local + Termux paths.
    DEFAULT_MODEL_PATHS = [
        # Default location used by `litert-lm import <ref>`
        "~/.litert-lm/models/gemma-4-e2b/model.litertlm",
        # Termux on Pixel — shared storage readable from any process
        "~/storage/shared/Pitwall/models/gemma-4-E2B-it.litertlm",
        # Repo-local fallback for dev machines
        "models/gemma-4-E2B-it.litertlm",
        # Legacy .task path — kept so a stale install doesn't 100% silently fail
        "~/storage/shared/Pitwall/models/gemma-4-E2B-it.task",
        "models/gemma-4-E2B-it.task",
    ]

    # Default LocalLLM endpoint — Apache-2.0 Android APK at
    # https://www.tahabouhsine.com/localllm/ exposing OpenAI-compatible
    # /v1/chat/completions. ADR-022 makes this the default transport for
    # both warm (brief/debrief) and paddock (ADK) LLM calls. Override with
    # the PITWALL_ADK_OPENAI_URL env var (legacy: PITWALL_LITERT_URL); set
    # to empty string to fall back to in-process litert_lm.Engine on the
    # same machine.
    DEFAULT_HTTP_URL = "http://localhost:8099/v1"
    DEFAULT_HTTP_MODEL = "gemma3n-e2b"

    def __init__(
        self,
        model_path: str = "",
        *,
        driver_level: str = "intermediate",
        max_tokens: int | None = None,
        temperature: float = 0.4,
        backend: str = "cpu",
    ):
        self.driver_level = driver_level
        # Default output budget: 512 covers ~150 words (briefs target this) with
        # headroom for the emotion tag + focus JSON. Override via
        # PITWALL_LLM_MAX_TOKENS so users can tune for tighter LocalLLM caps.
        if max_tokens is None:
            try:
                max_tokens = int(os.getenv("PITWALL_LLM_MAX_TOKENS", "512"))
            except ValueError:
                max_tokens = 512
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.backend = backend
        self._fallback = RuleCoach(driver_level)
        self._llm = None
        self._engine = None
        self._engine_ctx = None       # context-manager handle (for clean close)
        self._init_error: Optional[str] = None

        # HTTP transport (LocalLLM) state. Truthy `_http_url` means HTTP
        # mode is selected — `_generate` will POST to chat.completions
        # instead of touching the in-process engine.
        self._http_url: str = ""
        self._http_model: str = ""
        self._http_api_key: str = ""
        self._http_timeout_s: float = float(
            os.getenv("PITWALL_LITERT_HTTP_TIMEOUT_S", "30")
        )

        # ADR-022: prefer HTTP-to-LocalLLM by default. Setting
        # PITWALL_ADK_OPENAI_URL (legacy: PITWALL_LITERT_URL) to an empty
        # string opts out and falls back to in-process litert-lm. Anything
        # else (including the default LocalLLM URL) selects HTTP and skips
        # loading the engine in this process.
        http_url = (get_env_with_legacy(
            "PITWALL_ADK_OPENAI_URL", "PITWALL_LITERT_URL",
            self.DEFAULT_HTTP_URL) or "").strip()
        if http_url:
            self._http_url = http_url.rstrip("/")
            self._http_model = get_env_with_legacy(
                "PITWALL_ADK_OPENAI_MODEL", "PITWALL_LITERT_MODEL",
                self.DEFAULT_HTTP_MODEL,
            )
            self._http_api_key = get_env_with_legacy(
                "PITWALL_ADK_OPENAI_API_KEY", "PITWALL_LITERT_API_KEY",
                "lit-serve-not-required",
            )
            # Truthy sentinel — brief()/debrief() gate on `self._llm is not None`.
            self._llm = "http"
            return

        # In-process engine fallback (opt-in via empty PITWALL_ADK_OPENAI_URL).
        # All heavy imports are lazy + caught — LitertCoach must construct
        # cleanly on machines without litert-lm so make_coach("auto") can
        # probe + fall back without crashing the bridge.
        try:
            self._init_runtime(model_path)
        except Exception as e:
            self._init_error = f"{type(e).__name__}: {e}"

    # ---- runtime init -------------------------------------------------------

    def _init_runtime(self, model_path: str):
        try:
            import litert_lm  # type: ignore
        except ImportError as e:
            raise RuntimeError(
                f"litert-lm not installed ({e}). "
                f"Run: pip install litert-lm"
            )

        path = self._resolve_model_path(model_path)
        if path is None:
            raise FileNotFoundError(
                f"no Gemma .litertlm file found in {self.DEFAULT_MODEL_PATHS}"
            )

        backend_enum = (litert_lm.Backend.GPU
                        if self.backend.lower() == "gpu"
                        else litert_lm.Backend.CPU)

        # Engine is a context manager; entering it loads the model + native
        # libs. We keep the entered handle on `self` for the lifetime of the
        # coach and release it via close().
        engine_factory = litert_lm.Engine(
            model_path=str(path),
            backend=backend_enum,
            max_num_tokens=4096,
        )
        self._engine_ctx = engine_factory
        self._engine = engine_factory.__enter__()
        # Sentinel used by callers + tests to confirm the model loaded.
        self._llm = self._engine

    def close(self):
        """Release the engine's native resources. Safe to call repeatedly."""
        if self._engine_ctx is not None:
            try:
                self._engine_ctx.__exit__(None, None, None)
            except Exception as exc:
                # litert_lm.Engine cleanup can surface any of several native
                # errors; keep broad but visible so we notice resource leaks.
                _log.warning("litert_lm engine close failed: %s", exc)
            self._engine_ctx = None
            self._engine = None
            self._llm = None

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass

    def _resolve_model_path(self, model_path: str) -> Optional[Path]:
        candidates = [model_path] if model_path else self.DEFAULT_MODEL_PATHS
        for c in candidates:
            if not c:
                continue
            p = Path(os.path.expanduser(c))
            if p.exists():
                return p
        return None

    # ---- public API ---------------------------------------------------------

    def health(self) -> dict:
        return {
            "loaded":    self._llm is not None,
            "transport": "http" if self._http_url else (
                "engine" if self._engine is not None else "none"
            ),
            "http_url":  self._http_url,
            "http_model": self._http_model,
            "error":     self._init_error or "",
            "fallback":  self._fallback.name,
        }

    def propose(self, ctx: CoachContext) -> Optional[CoachingMessage]:
        """In-drive coaching path is intentionally NOT LLM-driven.

        Three-tier coach architecture (set 2026-04-29):
          - pre-brief / post-session debrief → LLM (this class, brief/debrief)
          - in-drive sub-corner cues          → canonical-phrase library +
                                                 pre-rendered audio (RuleCoach)

        LLM latency on Apple Silicon CPU ≈ 3.5 s for ~30 tokens; on Pixel CPU
        2-4 s. Both are useless for an apex window. Forwarding to RuleCoach
        keeps the in-drive contract honest while preserving all the gating
        logic in one place.
        """
        return self._fallback.propose(ctx)

    # ---- inference (used by brief() + debrief() only) -----------------------

    def _generate(self, system_prompt: str, user_prompt: str,
                  *, session_id: Optional[str] = None,
                  role: str = "", mode: str = "") -> str:
        """One-shot generation.

        Two transports, picked at construction:

        - **HTTP (default, ADR-022)** — POST to LocalLLM's OpenAI-compatible
          `/chat/completions`. Stateless one-shot; system + user message in
          the `messages` array. Response parsed from `choices[0].message.content`.
        - **In-process (opt-in)** — `litert_lm.Engine.create_conversation()`
          + `Conversation.send_message()`. The `.litertlm` bundle ships its
          own chat template; the runtime applies Gemma's chat template
          internally — no manual `<start_of_turn>` tokens needed.

        Every call emits a friction record (success or failure) so the
        bridge's `/diagnostics/llm_friction` endpoint can surface degradation
        before it bites in a session.
        """
        prompt_chars = len(system_prompt) + len(user_prompt)
        if self._llm is None:
            _emit_friction({
                "session_id": session_id, "role": role, "mode": mode,
                "backend": self.backend,
                "prompt_chars": prompt_chars, "completion_chars": 0,
                "latency_ms": 0.0, "truncated": False, "fell_back": True,
                "error": "engine_not_loaded", "emotion": "",
            })
            return ""
        t0 = time.monotonic()
        err = ""
        text = ""
        try:
            if self._http_url:
                text = self._generate_http(system_prompt, user_prompt)
            else:
                conv = self._engine.create_conversation(
                    messages=[{"role": "system", "content": system_prompt}],
                )
                response = conv.send_message(
                    {"role": "user", "content": user_prompt},
                )
                text = _extract_assistant_text(response)
        except Exception as e:
            err = f"{type(e).__name__}: {e}"
            text = ""
        latency_ms = (time.monotonic() - t0) * 1000.0
        # Truncation heuristic: ran the full token budget AND output ended
        # without sentence-final punctuation (no terminal . ! ? }] etc.).
        # Keeps us honest about partial completions until litert-lm exposes
        # an explicit finish_reason in its response shape.
        truncated = bool(
            text
            and len(text) >= self.max_tokens * 3   # ~3 chars/token rough lower bound
            and text.rstrip()[-1:] not in ".!?\"')]}",
        )
        _emit_friction({
            "session_id": session_id, "role": role, "mode": mode,
            "backend": self.backend,
            "prompt_chars": prompt_chars, "completion_chars": len(text),
            "latency_ms": latency_ms, "truncated": truncated,
            "fell_back": bool(err) or not text,
            "error": err, "emotion": "",
        })
        return text

    # ---- HTTP transport (LocalLLM / any OpenAI-compatible local server) ----

    def _generate_http(self, system_prompt: str, user_prompt: str) -> str:
        """POST to LocalLLM's OpenAI-compatible chat.completions endpoint.

        Synchronous; uses urllib.request to avoid an extra HTTP dep. Returns
        the assistant text or raises — the caller's try/except converts that
        into a friction record and a templated fallback.
        """
        url = self._http_url + "/chat/completions"
        payload = {
            "model": self._http_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
            "temperature": self.temperature,
            "max_tokens":  self.max_tokens,
            "stream": False,
        }
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=body,
            method="POST",
            headers={
                "Content-Type":  "application/json",
                "Accept":        "application/json",
                "Authorization": f"Bearer {self._http_api_key}",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=self._http_timeout_s) as resp:
                raw = resp.read()
        except urllib.error.HTTPError as e:
            detail = e.read()[:512].decode("utf-8", errors="replace")
            raise RuntimeError(f"localllm HTTP {e.code}: {detail}") from e
        except urllib.error.URLError as e:
            raise RuntimeError(f"localllm unreachable at {url}: {e.reason}") from e
        data = json.loads(raw.decode("utf-8"))
        choices = data.get("choices") or []
        if not choices:
            raise RuntimeError(f"localllm: empty choices in response: {data!r}")
        msg = choices[0].get("message") or {}
        content = msg.get("content")
        if isinstance(content, str):
            return content
        # Some servers wrap content as a list of parts; concatenate text parts.
        if isinstance(content, list):
            parts = [
                p.get("text", "") for p in content
                if isinstance(p, dict) and p.get("type") in ("text", None)
            ]
            return "\n".join(s for s in parts if s).strip()
        return ""

    # ---- multi-mode entry points (PRE_BRIEF + POST_SESSION) ----------------

    def brief(self, *, driver_id: str, today_iso: str, weather_phase: str,
              surface_state: str, markers_selected: list[str],
              weakest_recent_corner: Optional[str] = None,
              biggest_recent_improvement: Optional[dict] = None,
              danger_zones_today: Optional[list[str]] = None,
              goal: str = "personal best lap",
              driver_level: Optional[str] = None,
              session_id: Optional[str] = None,
              ) -> tuple[str, list[str], str]:
        """PRE_BRIEF mode. Returns (narrative_md, focus_list, emotion).

        `emotion` is one of `coach_engine.VALID_EMOTIONS`; defaults to
        'neutral' when no LLM, when the response lacks the [EMOTION:]
        tag, or when the tag's value is unknown. The PWA's coach
        sprite reads it to pick the matching animation.
        """
        level = driver_level or self.driver_level
        track = "Sonoma Raceway"
        sys_p = build_system_prompt(level, track, mode=CoachMode.PRE_BRIEF)
        usr_p = build_pre_brief_user_prompt(
            driver_id=driver_id, today_iso=today_iso,
            weather_phase=weather_phase, surface_state=surface_state,
            markers_selected=markers_selected,
            weakest_recent_corner=weakest_recent_corner,
            biggest_recent_improvement=biggest_recent_improvement,
            danger_zones_today=danger_zones_today or [],
            goal=goal,
        )
        # No-fake-data policy: never synthesize a brief from a template.
        # If the LLM can't speak, return empty narrative + empty focus and
        # let the PWA render an honest error state. The friction sink
        # records WHY so the user can debug from /diagnostics/llm_friction.
        if self._llm is None:
            _emit_friction({
                "session_id": session_id, "role": "brief",
                "mode": CoachMode.PRE_BRIEF.value, "backend": self.backend,
                "prompt_chars": len(sys_p) + len(usr_p),
                "completion_chars": 0, "latency_ms": 0.0,
                "truncated": False, "fell_back": False,
                "error": self._init_error or "engine_not_loaded",
                "emotion": "neutral",
            })
            return "", [], "neutral"
        try:
            raw = self._generate(
                sys_p, usr_p, session_id=session_id,
                role="brief", mode=CoachMode.PRE_BRIEF.value,
            )
            cleaned, emotion = _extract_emotion(raw)
            narr, focus = _split_brief_narrative_and_focus(cleaned)
            # `_generate` swallows transport/HTTP exceptions and returns "".
            # In that case the LLM didn't actually contribute anything;
            # return an empty narrative (no template synthesis) so the PWA
            # can show "brief unavailable" rather than fabricated text.
            if not narr or not narr.strip():
                _log.warning("brief LLM returned empty — surfacing empty narrative")
                return "", [], "neutral"
            return narr, focus, emotion
        except Exception as exc:
            # LLM / parse failure. Surface the empty + error state instead of
            # synthesizing content. `_generate` already wrote a friction
            # record with the error reason.
            _log.warning("brief LLM/parse failed (%s) — surfacing empty narrative", exc)
            return "", [], "neutral"

    def debrief(self, bundle: dict,
                *, driver_level: Optional[str] = None
                ) -> tuple[str, list[str], str]:
        """POST_SESSION mode. Returns (narrative_md, next_focus_list, emotion)."""
        level = driver_level or self.driver_level
        track = bundle.get("track", "Sonoma Raceway")
        sys_p = build_system_prompt(level, track, mode=CoachMode.POST_SESSION)
        usr_p = build_post_session_user_prompt(bundle)
        sid = (bundle.get("scorecard") or {}).get("session_id") \
            or bundle.get("session_id")
        if self._llm is None:
            _emit_friction({
                "session_id": sid, "role": "debrief",
                "mode": CoachMode.POST_SESSION.value, "backend": self.backend,
                "prompt_chars": len(sys_p) + len(usr_p),
                "completion_chars": 0, "latency_ms": 0.0,
                "truncated": False, "fell_back": False,
                "error": self._init_error or "engine_not_loaded",
                "emotion": "neutral",
            })
            return "", [], "neutral"
        try:
            raw = self._generate(
                sys_p, usr_p, session_id=sid,
                role="debrief", mode=CoachMode.POST_SESSION.value,
            )
            cleaned, emotion = _extract_emotion(raw)
            narr, focus = _split_debrief_narrative_and_focus(cleaned)
            return narr, focus, emotion
        except Exception as exc:
            _log.warning("debrief LLM/parse failed (%s) — returning empty bundle",
                         exc)
            return "", [], "neutral"


# ─── litert-lm helpers (module scope so brief/debrief stay class methods) ───


def _extract_assistant_text(response) -> str:
    """Extract the concatenated text body from a litert-lm send_message reply.

    Response shape: `{'role': 'assistant', 'content': [{'text': '...',
    'type': 'text'}, ...]}`. The `content` is a list of typed parts; we
    concatenate every part with type=='text'.
    """
    if isinstance(response, str):
        return response
    if not isinstance(response, dict):
        return ""
    content = response.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if isinstance(part, dict) and part.get("type") == "text":
                t = part.get("text")
                if isinstance(t, str):
                    parts.append(t)
            elif isinstance(part, str):
                parts.append(part)
        return "\n".join(parts).strip()
    return ""


# Legacy alias — keeps any older callers working until full rename lands
TfliteCoach = LitertCoach

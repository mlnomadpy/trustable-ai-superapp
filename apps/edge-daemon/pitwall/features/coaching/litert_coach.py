"""
LitertCoach — paddock-tier LLM coach over LocalLLM HTTP.

Per ADR-025 the warm path is LocalLLM-only — the same transport the ADK
paddock tier uses (ADR-024). `brief()` and `debrief()` POST OpenAI-shaped
chat-completions to `PITWALL_ADK_OPENAI_URL` (default
`http://localhost:8099/v1`). `propose()` defers to RuleCoach per ADR-017
(LLM latency is wrong for sub-corner cues).
"""

from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.request
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
    build_pre_brief_user_prompt,
    build_post_session_user_prompt,
    build_system_prompt,
)
from pitwall.features.coaching.rule_coach import RuleCoach


# ─── LocalLLM HTTP coach ──────────────────────────────────────────────────────


class LitertCoach(CoachEngine):
    """Warm-path LLM coach that dials LocalLLM over OpenAI-compatible HTTP.

    Per ADR-025 the in-process `litert_lm.Engine` transport was retired.
    Every warm-path LLM call now goes to LocalLLM (or any OpenAI-compatible
    server) at `PITWALL_ADK_OPENAI_URL`. That's the same endpoint the ADK
    paddock tier uses (ADR-024), so the warm and paddock tiers share a
    single transport contract.

    Coaching scope (three-tier architecture):
      - `brief()`   — pre-session paddock narrative. LLM-driven. 2-4 s OK.
      - `debrief()` — post-session paddock narrative. LLM-driven. 8-15 s OK.
      - `propose()` — DEPRECATED for LLM use. Returns None to defer to the
                      canonical-phrase path (RuleCoach + pre-rendered audio).
                      LLMs are too slow (>1 s) for sub-corner cues.

    If LocalLLM is unreachable, `brief()` / `debrief()` return empty
    narratives (no template synthesis) so the PWA can render an honest
    "brief unavailable" state. `_emit_friction` records WHY so operators can
    debug from `/diagnostics/llm_friction`.
    """

    name = "litert"

    # LocalLLM endpoint defaults. Apache-2.0 Android APK at
    # https://www.tahabouhsine.com/localllm/ exposing OpenAI-compatible
    # /v1/chat/completions. Override via PITWALL_ADK_OPENAI_URL (legacy:
    # PITWALL_LITERT_URL).
    DEFAULT_HTTP_URL = "http://localhost:8099/v1"
    DEFAULT_HTTP_MODEL = "gemma3n-e2b"

    def __init__(
        self,
        *,
        driver_level: str = "intermediate",
        max_tokens: int | None = None,
        temperature: float = 0.4,
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
        self._fallback = RuleCoach(driver_level)

        self._http_url = get_env_with_legacy(
            "PITWALL_ADK_OPENAI_URL", "PITWALL_LITERT_URL",
            self.DEFAULT_HTTP_URL,
        ).rstrip("/")
        self._http_model = get_env_with_legacy(
            "PITWALL_ADK_OPENAI_MODEL", "PITWALL_LITERT_MODEL",
            self.DEFAULT_HTTP_MODEL,
        )
        self._http_api_key = get_env_with_legacy(
            "PITWALL_ADK_OPENAI_API_KEY", "PITWALL_LITERT_API_KEY",
            "lit-serve-not-required",
        )
        self._http_timeout_s = float(
            os.getenv("PITWALL_LITERT_HTTP_TIMEOUT_S", "30")
        )

    # ---- public API ---------------------------------------------------------

    def health(self) -> dict:
        return {
            "transport":  "http",
            "http_url":   self._http_url,
            "http_model": self._http_model,
            "fallback":   self._fallback.name,
        }

    def propose(self, ctx: CoachContext) -> Optional[CoachingMessage]:
        """In-drive coaching is intentionally NOT LLM-driven.

        Three-tier coach architecture (set 2026-04-29):
          - pre-brief / post-session debrief → LLM (this class)
          - in-drive sub-corner cues          → canonical-phrase library +
                                                 pre-rendered audio (RuleCoach)

        LLM latency at LocalLLM ranges 0.5-3 s for ~30 tokens — useless for
        an apex window. Forwarding to RuleCoach keeps the in-drive contract
        honest while preserving all gating logic in one place.
        """
        return self._fallback.propose(ctx)

    # ---- HTTP transport -----------------------------------------------------

    def _generate(self, system_prompt: str, user_prompt: str,
                  *, session_id: Optional[str] = None,
                  role: str = "", mode: str = "") -> str:
        """POST to LocalLLM's OpenAI-compatible chat.completions endpoint.

        Emits a friction record (success or failure) so the bridge's
        `/diagnostics/llm_friction` endpoint can surface degradation
        before it bites in a session.
        """
        prompt_chars = len(system_prompt) + len(user_prompt)
        t0 = time.monotonic()
        err = ""
        text = ""
        try:
            text = self._generate_http(system_prompt, user_prompt)
        except Exception as e:
            err = f"{type(e).__name__}: {e}"
            text = ""
        latency_ms = (time.monotonic() - t0) * 1000.0
        # Truncation heuristic: ran the full token budget AND output ended
        # without sentence-final punctuation (no terminal . ! ? }] etc.).
        truncated = bool(
            text
            and len(text) >= self.max_tokens * 3   # ~3 chars/token rough lower bound
            and text.rstrip()[-1:] not in ".!?\"')]}",
        )
        _emit_friction({
            "session_id": session_id, "role": role, "mode": mode,
            "backend": "http",
            "prompt_chars": prompt_chars, "completion_chars": len(text),
            "latency_ms": latency_ms, "truncated": truncated,
            "fell_back": bool(err) or not text,
            "error": err, "emotion": "",
        })
        return text

    def _generate_http(self, system_prompt: str, user_prompt: str) -> str:
        """POST a chat-completions request and return the assistant text.

        Synchronous; uses urllib.request to avoid an extra HTTP dep. Raises
        on transport failure — `_generate` converts that into a friction
        record and an empty narrative.
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
        'neutral' when the response lacks the [EMOTION:] tag or when the
        tag's value is unknown. The PWA's coach sprite reads it to pick
        the matching animation.

        No-fake-data policy: if LocalLLM is unreachable or returns empty,
        the method returns an empty narrative + empty focus rather than
        synthesizing a templated fallback. The PWA renders an honest
        "brief unavailable" state and the friction sink records why.
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
        try:
            raw = self._generate(
                sys_p, usr_p, session_id=session_id,
                role="brief", mode=CoachMode.PRE_BRIEF.value,
            )
            cleaned, emotion = _extract_emotion(raw)
            narr, focus = _split_brief_narrative_and_focus(cleaned)
            if not narr or not narr.strip():
                _log.warning("brief LLM returned empty — surfacing empty narrative")
                return "", [], "neutral"
            return narr, focus, emotion
        except Exception as exc:
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

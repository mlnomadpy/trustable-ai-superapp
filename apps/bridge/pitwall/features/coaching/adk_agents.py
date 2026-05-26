"""
ADK multi-agent topology for pitwall paddock coaching.

Model backends (`PITWALL_ADK_BACKEND`)
--------------------------------------
- **`openai`** (default per ADR-022): HTTP via `LiteLlm` (litellm) against
  any OpenAI-compatible local server. The intended target is
  [LocalLLM](https://www.tahabouhsine.com/localllm/) — an Apache-2.0 Android
  APK ([github.com/mlnomadpy/localllm](https://github.com/mlnomadpy/localllm))
  that hosts LiteRT-LM and exposes `/v1/chat/completions` on port 8099. The
  same backend also covers Ollama, LM Studio, llama.cpp `--server`, vLLM, etc.
  on dev machines.
- **`engine`**: in-process via `litert_lm.Engine` using `LitertLmModel(BaseLlm)`.
  No second process. Useful when the bridge already loads the engine for the
  warm path and you don't want a separate model server APK.
- **`litertlm`**: HTTP via ADK's `Gemini(base_url=..., model=...)` against a
  separately-launched `lit serve`. The path documented at
  https://adk.dev/agents/models/litert-lm/. Kept for desktop dev.

Environment overrides
---------------------
    PITWALL_ADK_BACKEND         default: "openai"  ({engine | litertlm | openai})
    PITWALL_ADK_OPENAI_URL      default: http://localhost:8099/v1  (LocalLLM / OpenAI-shim)
                                (legacy: PITWALL_LITERT_URL — deprecated)
    PITWALL_ADK_OPENAI_MODEL    default: gemma3n-e2b   (must match the loaded model)
                                (legacy: PITWALL_LITERT_MODEL — deprecated)
    PITWALL_ADK_OPENAI_API_KEY  default: lit-serve-not-required (openai bearer token)
                                (legacy: PITWALL_LITERT_API_KEY — deprecated)
    PITWALL_LITERTLM_PATH       .litertlm bundle path (engine backend)
    PITWALL_LITERTLM_BUDGET     KV-cache char budget per agent (default 30000)
    PITWALL_ADK_TIMEOUT_S       default: 45  (raises after this many seconds)
    PITWALL_ADK_CHAR_BUDGET     default: 60000 (rotate ADK session above this)
    PITWALL_ADK_PROMPT_LOG      default: ""   (empty disables prompt JSONL log)

Public API for pitwall_bridge.py
--------------------------------
    run_adk(prompt, user_id="driver") -> (text, adk_session_id)
    stream_adk(prompt, user_id="driver") -> Iterator[str]
    reset_driver_session(user_id) -> None
    get_pending_traces(adk_session_id=None) -> list[dict]
    coach_orchestrator       — PitwallOrchestrator instance
    AGENT_REGISTRY           — list[dict] for /coach/agents

Agent roster (single-parent — pipelines own their own data agents)
------------------------------------------------------------------
  PitwallOrchestrator                  Root, deterministic regex routing
  ├── DebriefPipeline                  Sequential[Parallel[H_d, T_d, P_d], N_d]
  ├── BriefPipeline                    Sequential[P_b, N_b]
  ├── TelemetryAgent                   QA telemetry default
  ├── LapComparisonAgent
  ├── CornerCoachAgent
  ├── ProgressTrackerAgent
  ├── SetupAdvisorAgent
  ├── HighlightFinderAgent             QA highlights (separate from H_d)
  ├── PedagogyAgent                    QA pedagogy (separate from P_d, P_b)
  ├── MindsetCoachAgent
  ├── GoldLapAgent
  ├── WeatherAdaptationAgent
  ├── SessionPlannerAgent
  ├── IncidentReviewAgent
  ├── RacePaceAgent
  ├── GoalSettingAgent
  ├── MentalMapAgent
  ├── VoiceScriptAgent
  └── AgentMetaAgent
"""
from __future__ import annotations

import asyncio
import concurrent.futures
import json
import logging
import os
import queue
import re
import threading
import time
from collections import deque
from typing import AsyncGenerator, Iterable

from pitwall._env import get_env_with_legacy
from pitwall.adk_tools import (
    query_pitwall_db,
    get_lap_delta,
    get_corner_history,
    get_progress_report,
    get_setup_indicators,
    get_session_highlights,
    get_gold_lap_comparison,
    get_weather_adaptation_context,
    get_session_plan_context,
    get_incident_moments,
    get_race_pace_model,
    get_goal_targets,
    get_track_variance_map,
    get_agent_telemetry,
    get_audio_script_context,
    save_voice_scripts,
)

_log = logging.getLogger(__name__)

_RUN_TIMEOUT_S = float(os.getenv("PITWALL_ADK_TIMEOUT_S", "45"))
_SESSION_CHAR_BUDGET = int(os.getenv("PITWALL_ADK_CHAR_BUDGET", "60000"))
_PROMPT_LOG_PATH = os.getenv("PITWALL_ADK_PROMPT_LOG", "")

HAS_ADK = False
try:
    from google.adk.agents import Agent, BaseAgent, ParallelAgent, SequentialAgent
    from google.adk.apps import App
    from google.adk.models import Gemini
    from google.adk.plugins import BasePlugin
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService
    from google.adk.agents.run_config import RunConfig, StreamingMode
    from google.genai.types import Content, Part
    HAS_ADK = True
except ImportError as _e:
    _log.debug("ADK not importable: %s", _e)

# LiteLlm is optional — only needed when PITWALL_ADK_BACKEND=openai.
try:
    from google.adk.models.lite_llm import LiteLlm  # noqa: F401
    HAS_LITELLM = True
except ImportError:
    HAS_LITELLM = False

# LitertLmModel adapter — only needed when PITWALL_ADK_BACKEND=engine.
try:
    from pitwall.features.coaching.litert_lm_model import (
        LitertLmModel,
        reset_all_conversations as _reset_litertlm_conversations,
        get_kv_cache_stats as _litertlm_kv_stats,
        HAS_LITERTLM_MODEL,
    )
except ImportError:
    HAS_LITERTLM_MODEL = False
    _reset_litertlm_conversations = lambda: None  # noqa: E731
    _litertlm_kv_stats = lambda: {"active_conversations": 0}  # noqa: E731

# ── Agent trace buffer (drained by pitwall_bridge after each run_adk call) ────

_pending_traces: deque[dict] = deque(maxlen=4000)
_trace_lock = threading.Lock()


def get_pending_traces(adk_session_id: str | None = None) -> list[dict]:
    """Drain agent traces.

    If `adk_session_id` is provided, only rows whose `trace_id` matches are
    drained — others remain in the deque for their owning request to drain.
    This prevents cross-trace contamination when concurrent Flask requests
    each call _drain_adk_traces() (audit issue #3).
    """
    with _trace_lock:
        if adk_session_id is None:
            traces = list(_pending_traces)
            _pending_traces.clear()
            return traces
        keep: list[dict] = []
        out: list[dict] = []
        for t in _pending_traces:
            if t.get("trace_id") == adk_session_id:
                out.append(t)
            else:
                keep.append(t)
        _pending_traces.clear()
        _pending_traces.extend(keep)
        return out


# ── Persistent session registry (KV cache reuse across calls per driver) ──────
# lit serve has no prefix-cache flags — KV cache reuse happens at the ADK
# session level. Keeping the same ADK session alive means the system instruction
# tokens are already in the KV cache for subsequent calls. The shared
# instruction prefix (_COMMON_PREFIX) compounds this across specialists.

_driver_sessions: dict[str, str] = {}        # user_id → ADK session_id
_driver_sessions_lock = threading.Lock()
_session_chars: dict[str, int] = {}          # user_id → cumulative prompt+completion chars


def reset_driver_session(user_id: str) -> None:
    """Expire a driver's ADK session and delete it inside InMemorySessionService.

    Schedules the actual deletion on the persistent event loop (best-effort,
    bounded by a short timeout). Forgetting the registry entry is always done
    synchronously so the next call starts fresh.

    Also drops the engine-backend KV cache. Conversations there are keyed by
    system_instruction, not user_id, so this clears warmth for *all* drivers.
    Acceptable: the next call rebuilds within ~10ms (system prompt re-prefill)
    and the cold start at the new driving day is the existing UX contract.
    """
    with _driver_sessions_lock:
        old_sid = _driver_sessions.pop(user_id, None)
        _session_chars.pop(user_id, None)

    if HAS_ADK and old_sid and _loop is not None:
        try:
            fut = asyncio.run_coroutine_threadsafe(
                _delete_session_async(user_id, old_sid), _loop)
            fut.result(timeout=2)
        except Exception as exc:
            _log.warning("ADK session %s delete failed: %s", old_sid, exc)

    # Flush the in-process LiteRT-LM conversation cache too.
    try:
        _reset_litertlm_conversations()
    except Exception:
        _log.exception("LiteRT-LM conversation cache reset failed")


def get_kv_cache_stats() -> dict:
    """Expose KV-cache state for /diagnostics endpoints.

    Returns engine-backend stats (active conversations, total chars, budget).
    On non-engine backends returns a placeholder.
    """
    return _litertlm_kv_stats()


# ── Module-level stubs (raise on call when ADK absent) ────────────────────────

_loop: asyncio.AbstractEventLoop | None = None


def run_adk(prompt: str, user_id: str = "driver") -> tuple[str, str]:
    """Run a single ADK coaching query synchronously (stub when ADK is absent)."""
    raise RuntimeError("google-adk not installed — pip install google-adk litellm")


def stream_adk(prompt: str, user_id: str = "driver") -> Iterable[str]:
    """Stream ADK coaching tokens (stub when ADK is absent)."""
    raise RuntimeError("google-adk not installed — pip install google-adk litellm")


async def _delete_session_async(user_id: str, sid: str) -> None:
    raise RuntimeError("google-adk not installed")


# ── Intent classifier (always defined — pure-Python regex, no ADK dep) ───────

_INTENT_PATTERNS: list[tuple[str, re.Pattern]] = [
    # Order matters — first match wins. Whole-flow intents come BEFORE the
    # corner pattern so "brief me on T6" / "debrief Turn 5" / "voice script
    # at T3" route to the appropriate pipeline rather than getting hijacked
    # by the corner regex (audit finding 2026-05-12).
    ("debrief",        re.compile(r"\b(debrief|how did i do|session summary|review my session)\b", re.I)),
    ("brief",          re.compile(r"\b(pre[- ]?session|today'?s plan|before i go out)\b|^\s*brief(\s+me)?\b", re.I)),
    ("voice_script",   re.compile(r"\b(voice\s+scripts?|tts|cue\s+scripts?|pace\s+notes?|audio\s+cues?|generate\s+(?:cue|voice|audio)\s+\w+|write\s+(?:cue|voice|audio)\s+\w+)\b", re.I)),
    # Now the corner pattern — for queries that genuinely target a single corner.
    ("corner",         re.compile(r"\bT\s?\d{1,2}\b|\bturn\s+\d+\b|\bcarousel\b|\bbus\s*stop\b", re.I)),
    ("gold_lap",       re.compile(r"\b(gold lap|reference lap|gold standard)\b|\bAJ\b", re.I)),
    ("weather",        re.compile(r"\b(weather|fog|greasy|track temp|conditions)\b", re.I)),
    ("session_plan",   re.compile(r"\b(practice plan|how should i structure|laps available)\b|\bi have \d+ laps?\b", re.I)),
    ("incident",       re.compile(r"\b(incident|close call|scary|saved it|nearly off|moment at)\b", re.I)),
    ("race_pace",      re.compile(r"\b(race pace|stint|degradation|tyre drop)\b", re.I)),
    ("goal",           re.compile(r"\b(pb target|lap time goal|what time should|target lap|set me a goal)\b", re.I)),
    # Widened 2026-05-12 to cover "consistency" (noun), "repeatable/repeatability",
    # and "stable" — the natural phrasings users reach for when asking about
    # corner-to-corner repeatability.
    ("mental_map",     re.compile(r"\b(variance|consistenc(?:y|ies)|consistent|inconsistent|mental\s*map|repeatab(?:le|ility)|stable)\b", re.I)),
    ("lap_comparison", re.compile(r"\blap\s*\d+\s*vs|compare lap|why was lap|fastest vs slowest\b", re.I)),
    ("progress",       re.compile(r"\b(progress|improving|getting faster|over sessions|this month)\b", re.I)),
    ("setup",          re.compile(r"\b(setup|understeer|oversteer|balance|nervous mid|car feel)\b", re.I)),
    ("mindset",        re.compile(r"\b(frustrated|frustration|plateau|not working|motivation)\b", re.I)),
    ("agent_meta",     re.compile(r"\b(slowest|agent latency|tool call count|agent trace)\b.*\bagent\b|\bagent\b.*\b(slowest|slow|latency|trace)\b", re.I)),
]

_VALID_INTENTS = frozenset(
    [name for name, _ in _INTENT_PATTERNS] + ["telemetry", "debrief", "brief"]
)


def _classify_intent(query: str | None) -> str:
    """Regex-based, ordered, first-match-wins. Returns 'telemetry' on miss.

    Defined at module scope (not gated by HAS_ADK) so unit tests don't need
    google-adk installed to verify routing behaviour.
    """
    if not query:
        return "telemetry"
    for name, pat in _INTENT_PATTERNS:
        if pat.search(query):
            return name
    return "telemetry"


if not HAS_ADK:
    coach_orchestrator = None  # type: ignore[assignment]
    AGENT_REGISTRY: list = []
else:
    # ── Persistent event loop (one daemon thread; reused across requests) ─────

    _loop = asyncio.new_event_loop()

    def _loop_runner() -> None:
        asyncio.set_event_loop(_loop)
        _loop.run_forever()

    _loop_thread = threading.Thread(target=_loop_runner, daemon=True, name="adk-loop")
    _loop_thread.start()

    # ── Model selection ───────────────────────────────────────────────────────
    # Three backends — see module docstring for trade-offs.
    #   engine    → in-process litert_lm.Engine (no second process; NPU on Pixel)
    #   litertlm  → HTTP to `lit serve` via Gemini(base_url=...)
    #   openai    → HTTP to any OpenAI-compatible server via LiteLlm

    # ADR-022: LocalLLM (Android APK exposing OpenAI-compat HTTP on :8099)
    # is the default paddock backend. Override with PITWALL_ADK_BACKEND for
    # legacy lit serve (`litertlm`) or in-process (`engine`) deployments.
    _BACKEND = os.getenv("PITWALL_ADK_BACKEND", "openai").lower()
    _MODEL_ID = get_env_with_legacy(
        "PITWALL_ADK_OPENAI_MODEL", "PITWALL_LITERT_MODEL", "gemma3n-e2b")
    _MODEL_URL = get_env_with_legacy(
        "PITWALL_ADK_OPENAI_URL", "PITWALL_LITERT_URL",
        "http://localhost:8099/v1")

    if _BACKEND == "engine":
        if not HAS_LITERTLM_MODEL:
            raise RuntimeError(
                "PITWALL_ADK_BACKEND=engine requires litert-lm + google-adk — "
                "pip install litert-lm google-adk")
        _model = LitertLmModel(model=_MODEL_ID)
    elif _BACKEND == "openai":
        if not HAS_LITELLM:
            raise RuntimeError(
                "PITWALL_ADK_BACKEND=openai requires litellm — "
                "pip install google-adk[litellm]")
        # litellm routes by provider prefix: `openai/<model>` means
        # OpenAI-compatible HTTP. Without it, litellm cannot resolve the
        # provider and raises BadRequestError. We tolerate users who
        # already provided a prefix (e.g. `ollama/gemma2:2b`).
        _LITELLM_MODEL = _MODEL_ID if "/" in _MODEL_ID else f"openai/{_MODEL_ID}"
        _model = LiteLlm(
            model=_LITELLM_MODEL,
            api_base=_MODEL_URL,
            api_key=get_env_with_legacy(
                "PITWALL_ADK_OPENAI_API_KEY",
                "PITWALL_LITERT_API_KEY",
                "lit-serve-not-required",
            ),
        )
    else:
        # LiteRT-LM via `lit serve` — official ADK doc'd path. Default.
        _model = Gemini(model=_MODEL_ID, base_url=_MODEL_URL)

    # ── Shared instruction prefix (KV cache prefix matches across specialists) ─

    _COMMON_PREFIX = (
        "You are part of pitwall, an on-device track-day coaching system "
        "running locally on a Pixel 10. Be concrete and concise. Reference "
        "real session data; never invent numbers. If a tool call returns an "
        "error, say so plainly and suggest what data is missing. "
        "Always end every response with a tag of the form [EMOTION:x] where x "
        "is one of: neutral, encouraging, focused, concerned, excited.\n"
        "----\n"
    )

    def _instr(specific: str) -> str:
        return _COMMON_PREFIX + specific

    # ── Agent factory helpers ─────────────────────────────────────────────────

    def _qa_agent(name: str, role: str, tools: list, output_key: str | None = None) -> "Agent":
        kwargs: dict = {
            "name": name, "model": _model,
            "description": role, "instruction": _instr(role),
            "tools": tools,
        }
        if output_key:
            kwargs["output_key"] = output_key
        return Agent(**kwargs)

    # ── QA-only specialists (single parent: PitwallOrchestrator) ──────────────

    telemetry_agent = _qa_agent(
        "TelemetryAgent",
        "Report session data — laps, coaching notes, telemetry signals — for one session_id.",
        [query_pitwall_db, get_session_highlights],
        output_key="telemetry_data",
    )
    lap_comparison_agent = _qa_agent(
        "LapComparisonAgent",
        "Frame-by-frame delta between two laps. Identify where time was gained or lost.",
        [get_lap_delta, query_pitwall_db],
    )
    corner_coach_agent = _qa_agent(
        "CornerCoachAgent",
        "Grade history and improvement trend for one corner across sessions.",
        [get_corner_history, query_pitwall_db],
    )
    progress_tracker_agent = _qa_agent(
        "ProgressTrackerAgent",
        "Multi-session lap-time trend, corner arcs, and plateau detection.",
        [get_progress_report, query_pitwall_db],
    )
    setup_advisor_agent = _qa_agent(
        "SetupAdvisorAgent",
        "Infer car balance from telemetry — coasting, oscillation, brake pressure.",
        [get_setup_indicators, query_pitwall_db],
    )
    highlight_finder_agent = _qa_agent(
        "HighlightFinderAgent",
        "Find session best moments: fastest lap, peak grip, cleanest sector.",
        [get_session_highlights, query_pitwall_db],
        output_key="highlights_data",
    )
    mindset_coach_agent = _qa_agent(
        "MindsetCoachAgent",
        "Plateau and frustration coaching — detect stagnation and suggest mindset resets.",
        [get_progress_report, get_corner_history, query_pitwall_db],
    )
    gold_lap_agent = _qa_agent(
        "GoldLapAgent",
        "Compare driver's best lap to AJ's gold standard corner-by-corner.",
        [get_gold_lap_comparison, query_pitwall_db],
    )
    weather_adaptation_agent = _qa_agent(
        "WeatherAdaptationAgent",
        "Translate Sonoma's 4 weather phases into line, braking, and tyre advice.",
        [get_weather_adaptation_context, query_pitwall_db],
    )
    session_planner_agent = _qa_agent(
        "SessionPlannerAgent",
        "Build a lap-by-lap practice plan for N laps weighted by corner leverage and weakness.",
        [get_session_plan_context, query_pitwall_db],
    )
    incident_review_agent = _qa_agent(
        "IncidentReviewAgent",
        "Detect over-limit grip events, emergency brakes, and steering saves in telemetry.",
        [get_incident_moments, query_pitwall_db],
    )
    race_pace_agent = _qa_agent(
        "RacePaceAgent",
        "Model lap-time degradation to separate qualifying pace from sustainable race pace.",
        [get_race_pace_model, query_pitwall_db],
    )
    goal_setting_agent = _qa_agent(
        "GoalSettingAgent",
        "Set realistic PB targets from improvement rate and corner leverage.",
        [get_goal_targets, get_progress_report, query_pitwall_db],
    )
    mental_map_agent = _qa_agent(
        "MentalMapAgent",
        "Corner-by-corner speed-variance map. High variance = inconsistent.",
        [get_track_variance_map, query_pitwall_db],
    )
    voice_script_agent = _qa_agent(
        "VoiceScriptAgent",
        "Generate 2-3 word TTS cue phrases per driving phase per corner; "
        "write the result to the audio cache via save_voice_scripts. "
        "Use query_pitwall_db to validate corner names and adapt script "
        "tone to the driver's actual performance level on this corner.",
        [get_audio_script_context, save_voice_scripts, query_pitwall_db],
    )
    pedagogy_agent = _qa_agent(
        "PedagogyAgent",
        "Map driver profile to Ross Bentley concepts. Recommend one focus concept.",
        [query_pitwall_db],
        output_key="pedagogy_data",
    )
    agent_meta_agent = _qa_agent(
        "AgentMetaAgent",
        "Answer meta questions about agent performance: slowest agents, top tools, traces.",
        [get_agent_telemetry],
    )

    # ── Pipeline-internal data agents (separate instances; single-parent) ─────
    # output_key matches the QA siblings so the narrative templates fill the
    # same slots regardless of which path produced them.

    _telemetry_d = _qa_agent(
        "TelemetryAgentDebrief",
        "Pipeline copy of TelemetryAgent — used inside DebriefPipeline.",
        [query_pitwall_db, get_session_highlights],
        output_key="telemetry_data",
    )
    _highlight_finder_d = _qa_agent(
        "HighlightFinderAgentDebrief",
        "Pipeline copy of HighlightFinderAgent — used inside DebriefPipeline.",
        [get_session_highlights, query_pitwall_db],
        output_key="highlights_data",
    )
    _pedagogy_d = _qa_agent(
        "PedagogyAgentDebrief",
        "Pipeline copy of PedagogyAgent — used inside DebriefPipeline.",
        [query_pitwall_db],
        output_key="pedagogy_data",
    )
    _pedagogy_b = _qa_agent(
        "PedagogyAgentBrief",
        "Pipeline copy of PedagogyAgent — used inside BriefPipeline.",
        [query_pitwall_db],
        output_key="pedagogy_data",
    )

    # ── Narrative / output agents ─────────────────────────────────────────────

    _NARRATIVE_TAIL = (
        "Write the final coaching narrative from the structured data below.\n"
        "Session highlights: {highlights_data?}\n"
        "Telemetry analysis: {telemetry_data?}\n"
        "Pedagogy context:   {pedagogy_data?}\n\n"
        "Format rules:\n"
        "- Brief: 2-4 sentences then a FOCUS list of 3 items.\n"
        "- Debrief: 1 highlight opener then a 3-item next-session focus.\n"
        "- Q&A: max 4 sentences with specific data references.\n"
        "- Voice scripts: 2-3 word rally-style cues in T-Rod's voice."
    )

    _narrative_brief = Agent(
        name="NarrativeAgentBrief", model=_model,
        description="Pre-session brief text from pedagogy context.",
        instruction=_instr(_NARRATIVE_TAIL), tools=[],
    )
    _narrative_debrief = Agent(
        name="NarrativeAgentDebrief", model=_model,
        description="Post-session debrief text from highlights, telemetry, and pedagogy.",
        instruction=_instr(_NARRATIVE_TAIL), tools=[],
    )

    # ── Pipelines ─────────────────────────────────────────────────────────────

    _debrief_data_phase = ParallelAgent(
        name="DebriefDataPhase",
        sub_agents=[_highlight_finder_d, _telemetry_d, _pedagogy_d],
    )
    debrief_pipeline = SequentialAgent(
        name="DebriefPipeline",
        sub_agents=[_debrief_data_phase, _narrative_debrief],
    )
    brief_pipeline = SequentialAgent(
        name="BriefPipeline",
        sub_agents=[_pedagogy_b, _narrative_brief],
    )

    # ── Intent → specialist agent map (QA paths) ──────────────────────────────

    _INTENT_TO_AGENT: dict[str, Agent] = {
        "gold_lap":       gold_lap_agent,
        "weather":        weather_adaptation_agent,
        "session_plan":   session_planner_agent,
        "incident":       incident_review_agent,
        "race_pace":      race_pace_agent,
        "goal":           goal_setting_agent,
        "mental_map":     mental_map_agent,
        "voice_script":   voice_script_agent,
        "lap_comparison": lap_comparison_agent,
        "corner":         corner_coach_agent,
        "progress":       progress_tracker_agent,
        "setup":          setup_advisor_agent,
        "mindset":        mindset_coach_agent,
        "agent_meta":     agent_meta_agent,
        "telemetry":      telemetry_agent,
    }

    # ── Root orchestrator ─────────────────────────────────────────────────────

    class PitwallOrchestrator(BaseAgent):
        """Deterministic-routing orchestrator. Regex classifier → one sub-tree."""

        async def _run_async_impl(self, ctx) -> AsyncGenerator:  # type: ignore[override]
            try:
                query: str = ctx.user_content.parts[0].text  # type: ignore[union-attr]
            except (AttributeError, IndexError, TypeError) as exc:
                _log.warning(
                    "PitwallOrchestrator: could not read user_content (%s) — "
                    "defaulting to telemetry", exc)
                query = ""

            # Honour intent_override stashed in session.state by the bridge.
            override = ""
            try:
                override = (ctx.session.state.get("temp:intent_override") or "").strip().lower()
            except (AttributeError, KeyError, TypeError) as exc:
                _log.debug("intent_override lookup failed: %s", exc)
            intent = override if override in _VALID_INTENTS else _classify_intent(query)

            # Record routing decision as a trace row.
            try:
                trace_id = getattr(ctx.session, "id", "unknown")
                with _trace_lock:
                    _pending_traces.append({
                        "trace_id":   trace_id,
                        "agent_name": "PitwallOrchestrator",
                        "event_type": "intent",
                        "detail":     intent,
                        "latency_ms": None,
                        "success":    True,
                    })
            except Exception:
                _log.exception("trace append for intent=%s failed", intent)

            if intent == "debrief":
                async for event in debrief_pipeline.run_async(ctx):
                    yield event
            elif intent == "brief":
                async for event in brief_pipeline.run_async(ctx):
                    yield event
            else:
                agent = _INTENT_TO_AGENT.get(intent, telemetry_agent)
                async for event in agent.run_async(ctx):
                    yield event

    coach_orchestrator = PitwallOrchestrator(
        name="PitwallOrchestrator",
        sub_agents=[
            debrief_pipeline,
            brief_pipeline,
            telemetry_agent,
            lap_comparison_agent,
            corner_coach_agent,
            progress_tracker_agent,
            setup_advisor_agent,
            highlight_finder_agent,
            pedagogy_agent,
            mindset_coach_agent,
            gold_lap_agent,
            weather_adaptation_agent,
            session_planner_agent,
            incident_review_agent,
            race_pace_agent,
            goal_setting_agent,
            mental_map_agent,
            voice_script_agent,
            agent_meta_agent,
        ],
    )

    # ── Tracing plugin — writes to _pending_traces (drained → DuckDB) ─────────

    def _tool_response_ok(response) -> bool:
        if isinstance(response, dict) and "error" in response:
            return False
        if (isinstance(response, list) and response
                and isinstance(response[0], dict) and "error" in response[0]):
            return False
        return True

    def _trace_id_from(maybe_ctx) -> str:
        sess = getattr(maybe_ctx, "session", None)
        if sess is not None:
            return getattr(sess, "id", "unknown")
        # Some ADK callback contexts wrap an _invocation_context with .session
        inv = getattr(maybe_ctx, "_invocation_context", None)
        if inv is not None:
            return getattr(getattr(inv, "session", None), "id", "unknown")
        return "unknown"

    def _state_of(maybe_ctx):
        # Try direct .state, then ._invocation_context.session.state.
        s = getattr(maybe_ctx, "state", None)
        if s is not None:
            return s
        sess = getattr(maybe_ctx, "session", None)
        if sess is not None:
            return getattr(sess, "state", None)
        inv = getattr(maybe_ctx, "_invocation_context", None)
        if inv is not None:
            return getattr(getattr(inv, "session", None), "state", None)
        return None

    class PitwallTracingPlugin(BasePlugin):
        """Logs every agent run, tool call, and (optionally) model prompt.

        Per-agent timestamp keys (`temp:_agent_start_ms__<name>`) prevent the
        ParallelAgent race that ADR-021 missed: three concurrent debrief
        sub-agents each had their start time clobbered by the next, producing
        wrong latencies.

        ADK 1.32 hook signatures (async, kwargs-only) — see google.adk.plugins.
        We also expose plain `before_agent` / `after_agent` / `after_tool`
        synchronous shims so unit tests can drive the plugin without spinning
        up an async loop.
        """

        def __init__(self) -> None:
            super().__init__(name="pitwall_tracing")

        # ── Sync test-friendly shims (used by tests/test_adk.py) ─────────────

        def _record_agent_start(self, ctx, agent=None) -> None:
            try:
                name = (getattr(agent, "name", None)
                        or getattr(ctx, "agent_name", None) or "unknown")
                state = _state_of(ctx)
                if state is not None:
                    state[f"temp:_agent_start_ms__{name}"] = time.time() * 1000
            except Exception:
                _log.exception("agent-start trace failed")

        def _record_agent_end(self, ctx, agent=None) -> None:
            try:
                name = (getattr(agent, "name", None)
                        or getattr(ctx, "agent_name", None) or "unknown")
                state = _state_of(ctx)
                start = None
                if state is not None:
                    key = f"temp:_agent_start_ms__{name}"
                    start = state.pop(key, None) if hasattr(state, "pop") else state.get(key)
                latency = round(time.time() * 1000 - start, 1) if start else None
                with _trace_lock:
                    _pending_traces.append({
                        "trace_id":   _trace_id_from(ctx),
                        "agent_name": name,
                        "event_type": "agent",
                        "detail":     "",
                        "latency_ms": latency,
                        "success":    True,
                    })
            except Exception:
                _log.exception("agent-end trace failed")

        def _record_tool(self, tool, tool_context, result, event_type="tool") -> None:
            try:
                tool_name = getattr(tool, "name", None) or getattr(tool, "__name__", "unknown")
                agent_name = getattr(tool_context, "agent_name", "unknown")
                with _trace_lock:
                    _pending_traces.append({
                        "trace_id":   _trace_id_from(tool_context),
                        "agent_name": agent_name,
                        "event_type": event_type,
                        "detail":     tool_name,
                        "latency_ms": None,
                        "success":    _tool_response_ok(result) if event_type == "tool" else True,
                    })
            except Exception:
                _log.exception("tool-trace append failed")

        # Plain sync hooks (test entry points)
        def before_agent(self, ctx, agent=None):
            """Sync shim — record agent start for testing without an async loop."""
            self._record_agent_start(ctx, agent)
            return None

        def after_agent(self, ctx, agent=None):
            """Sync shim — record agent end and compute latency."""
            self._record_agent_end(ctx, agent)
            return None

        def before_tool(self, *, tool, args=None, tool_context):
            """Sync shim — record tool invocation start."""
            self._record_tool(tool, tool_context, None, event_type="tool_start")
            return None

        def after_tool(self, *, tool, args=None, tool_context, response=None):
            """Sync shim — record a tool invocation result."""
            self._record_tool(tool, tool_context, response)
            return None

        # ── Real ADK 1.32 async hooks (called by the Runner) ────────────────

        async def before_agent_callback(self, *, agent, callback_context):
            """ADK 1.32 async hook — record agent start timestamp."""
            self._record_agent_start(callback_context, agent)
            return None

        async def after_agent_callback(self, *, agent, callback_context):
            """ADK 1.32 async hook — record agent end and compute latency."""
            self._record_agent_end(callback_context, agent)
            return None

        async def before_tool_callback(self, *, tool, tool_args, tool_context):
            """ADK 1.32 async hook — record tool invocation start."""
            self._record_tool(tool, tool_context, None, event_type="tool_start")
            return None

        async def after_tool_callback(self, *, tool, tool_args, tool_context, result):
            """ADK 1.32 async hook — record tool invocation result."""
            self._record_tool(tool, tool_context, result)
            return None

        async def before_model_callback(self, *, callback_context, llm_request):
            """ADK 1.32 async hook — optionally log full prompts to disk."""
            if not _PROMPT_LOG_PATH:
                return None
            try:
                parts: list[str] = []
                for c in (getattr(llm_request, "contents", None) or []):
                    for p in (getattr(c, "parts", None) or []):
                        t = getattr(p, "text", None)
                        if t:
                            parts.append(t)
                flat = "\n".join(parts)
                row = {
                    "ts":          time.time(),
                    "agent_name":  getattr(callback_context, "agent_name", "unknown"),
                    "char_count":  len(flat),
                    "prompt_snip": flat[:4000],
                }
                with open(_PROMPT_LOG_PATH, "a") as fh:
                    fh.write(json.dumps(row) + "\n")
            except (OSError, TypeError, ValueError) as exc:
                _log.warning("prompt log write to %s failed: %s",
                             _PROMPT_LOG_PATH, exc)
            return None


    # ── Runner (uses App so plugins ride on the app, not the deprecated arg) ─

    _session_service = InMemorySessionService()
    _app = App(
        name="pitwall",
        root_agent=coach_orchestrator,
        plugins=[PitwallTracingPlugin()],
    )
    _runner = Runner(
        app=_app,
        session_service=_session_service,
    )

    async def _delete_session_async(user_id: str, sid: str) -> None:  # noqa: F811
        try:
            await _session_service.delete_session(
                app_name="pitwall", user_id=user_id, session_id=sid)
        except Exception as exc:
            _log.warning("ADK session delete failed for %s: %s", sid, exc)

    async def _get_or_create_session(user_id: str):
        """Return a persistent ADK session for this driver.

        Reuse keeps the system-instruction KV cache warm. Rotates when the
        cumulative prompt+completion char count exceeds _SESSION_CHAR_BUDGET
        (a proxy for token usage that doesn't require a tokenizer).
        """
        with _driver_sessions_lock:
            existing_sid = _driver_sessions.get(user_id)
            chars = _session_chars.get(user_id, 0)
            should_rotate = chars >= _SESSION_CHAR_BUDGET
            if should_rotate:
                _log.info("ADK session for '%s' hit %d chars — rotating", user_id, chars)
                _driver_sessions.pop(user_id, None)
                _session_chars.pop(user_id, None)

        if should_rotate and existing_sid:
            await _delete_session_async(user_id, existing_sid)
            existing_sid = None

        if existing_sid:
            try:
                session = await _session_service.get_session(
                    app_name="pitwall", user_id=user_id, session_id=existing_sid)
                if session:
                    return session
            except Exception as exc:
                _log.warning("ADK session lookup failed (%s) — creating new", exc)

        session = await _session_service.create_session(
            app_name="pitwall", user_id=user_id)
        
        # Initialize app-wide state if this is a fresh session
        session.state["app:platform"] = "Pixel 10"
        session.state["app:version"] = "0.1.0"
        
        with _driver_sessions_lock:
            _driver_sessions[user_id] = session.id
            _session_chars[user_id] = 0
        _log.debug("ADK session created: user=%s sid=%s", user_id, session.id)
        return session

    async def _run_adk_async(prompt: str, user_id: str, state_overrides: dict | None = None) -> tuple[str, str]:
        session = await _get_or_create_session(user_id)
        if state_overrides:
            session.state.update(state_overrides)
            
        final_text = ""
        async for event in _runner.run_async(
            user_id=user_id,
            session_id=session.id,
            new_message=Content(parts=[Part(text=prompt)]),
        ):
            if hasattr(event, "is_final_response") and event.is_final_response():
                if event.content and event.content.parts:
                    final_text = event.content.parts[0].text or final_text
        with _driver_sessions_lock:
            _session_chars[user_id] = (
                _session_chars.get(user_id, 0) + len(prompt) + len(final_text)
            )
        return final_text, session.id

    async def _stream_adk_async(prompt: str, user_id: str, state_overrides: dict | None = None) -> AsyncGenerator[str, None]:
        session = await _get_or_create_session(user_id)
        if state_overrides:
            session.state.update(state_overrides)
            
        rc = RunConfig(streaming_mode=StreamingMode.SSE)
        total_chars = 0
        async for event in _runner.run_async(
            user_id=user_id,
            session_id=session.id,
            new_message=Content(parts=[Part(text=prompt)]),
            run_config=rc,
        ):
            if event.content and event.content.parts:
                text = event.content.parts[0].text or ""
                if text:
                    total_chars += len(text)
                    yield text
        with _driver_sessions_lock:
            _session_chars[user_id] = (
                _session_chars.get(user_id, 0) + len(prompt) + total_chars
            )

    def run_adk(prompt: str, user_id: str = "driver", state_overrides: dict | None = None) -> tuple[str, str]:  # noqa: F811
        """Synchronous entry point for pitwall_bridge.py (Flask is sync).

        Returns (final_text, adk_session_id). Bounded by PITWALL_ADK_TIMEOUT_S.
        """
        if _loop is None:
            raise RuntimeError("ADK loop not started")
        fut = asyncio.run_coroutine_threadsafe(
            _run_adk_async(prompt, user_id, state_overrides), _loop)
        try:
            return fut.result(timeout=_RUN_TIMEOUT_S)
        except concurrent.futures.TimeoutError:
            fut.cancel()
            raise RuntimeError(f"ADK run exceeded {_RUN_TIMEOUT_S}s timeout")

    _STREAM_SENTINEL = object()

    def stream_adk(prompt: str, user_id: str = "driver", state_overrides: dict | None = None) -> Iterable[str]:  # noqa: F811
        """Sync generator yielding text chunks. Schedules the async generator
        on the persistent loop and bridges chunks via a thread-safe queue.
        """
        if _loop is None:
            raise RuntimeError("ADK loop not started")
        out_q: queue.Queue = queue.Queue()

        async def _produce() -> None:
            try:
                async for chunk in _stream_adk_async(prompt, user_id, state_overrides):
                    out_q.put(("chunk", chunk))
            except Exception as exc:
                out_q.put(("error", f"{type(exc).__name__}: {exc}"))
            finally:
                out_q.put((_STREAM_SENTINEL, None))

        asyncio.run_coroutine_threadsafe(_produce(), _loop)

        deadline = time.monotonic() + _RUN_TIMEOUT_S
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise RuntimeError(f"ADK stream exceeded {_RUN_TIMEOUT_S}s timeout")
            try:
                kind, payload = out_q.get(timeout=remaining)
            except queue.Empty:
                raise RuntimeError(f"ADK stream exceeded {_RUN_TIMEOUT_S}s timeout")
            if kind is _STREAM_SENTINEL:
                return
            if kind == "error":
                raise RuntimeError(payload or "ADK stream failed")
            yield payload


    # ── Vue PWA registry exposed via GET /coach/agents ────────────────────────

    AGENT_REGISTRY = [
        {"name": "TelemetryAgent",
         "role": "Session data — laps, coaching notes, telemetry signals",
         "example_questions": ["What happened in today's session?",
                               "How many coaching notes fired?"]},
        {"name": "LapComparisonAgent",
         "role": "Lap-vs-lap delta analysis",
         "example_questions": ["Why was lap 4 faster than lap 2?",
                               "What changed between my best and worst lap?"]},
        {"name": "CornerCoachAgent",
         "role": "Single-corner deep-dive across sessions",
         "example_questions": ["What am I doing wrong at Turn 7?",
                               "Am I improving at the Carousel?"]},
        {"name": "ProgressTrackerAgent",
         "role": "Multi-session improvement arc",
         "example_questions": ["Am I getting faster?",
                               "Where am I stuck?"]},
        {"name": "SetupAdvisorAgent",
         "role": "Telemetry → car balance and setup inference",
         "example_questions": ["My car feels understeery at T3, what does the data say?",
                               "What setup changes should I try?"]},
        {"name": "HighlightFinderAgent",
         "role": "Best moments and peak performance finder",
         "example_questions": ["What was my best moment today?",
                               "When was I highest on the limit?"]},
        {"name": "MindsetCoachAgent",
         "role": "Plateau detection + motivational coaching",
         "example_questions": ["I'm stuck at the same lap time.",
                               "I'm frustrated, nothing is clicking."]},
        {"name": "GoldLapAgent",
         "role": "Compare your lap against AJ's gold standard corner by corner",
         "example_questions": ["How do I compare to the reference lap?",
                               "Which corner costs me the most vs gold?"]},
        {"name": "WeatherAdaptationAgent",
         "role": "Weather phase → concrete line and braking adjustments",
         "example_questions": ["How should I adjust for morning fog?",
                               "The track is greasy, what should I do differently?"]},
        {"name": "SessionPlannerAgent",
         "role": "N laps available → structured lap-by-lap practice plan",
         "example_questions": ["I have 8 laps, what should I focus on?",
                               "Build me a practice plan for this session."]},
        {"name": "IncidentReviewAgent",
         "role": "Anomaly detection — over-limit events, emergency brakes, saves",
         "example_questions": ["I had a moment at T6, what does the data show?",
                               "Did I have any close calls today?"]},
        {"name": "RacePaceAgent",
         "role": "Lap degradation model — qualifying pace vs sustainable race pace",
         "example_questions": ["What would my race pace be?",
                               "How much do my tyres drop off over a stint?"]},
        {"name": "GoalSettingAgent",
         "role": "Next realistic PB target + top 3 corners to attack",
         "example_questions": ["What lap time should I target next session?",
                               "Where should I focus to go faster?"]},
        {"name": "MentalMapAgent",
         "role": "Corner-by-corner consistency map from speed variance",
         "example_questions": ["Where is my biggest lap-to-lap variance?",
                               "Which corners am I most consistent through?"]},
        {"name": "VoiceScriptAgent",
         "role": "Pre-rendered TTS audio cache script generator (ADR-017)",
         "example_questions": ["Generate cue scripts for Turn 7.",
                               "Write the audio cache phrases for T10."]},
        {"name": "PedagogyAgent",
         "role": "Driver profile + Ross Bentley concept selection",
         "example_questions": ["What Bentley concept should I focus on today?",
                               "What is my weakest skill right now?"]},
        {"name": "AgentMetaAgent",
         "role": "ADK system telemetry — agent latency, tool call frequency, trace history",
         "example_questions": ["Which agent is slowest?",
                               "What tools are called most often?"]},
    ]

"""pitwall.state — shared mutable state for the Pitwall bridge process.

Every Blueprint imports `state` from this module instead of reaching into
module-level globals. This eliminates the coupling that forced 4,500 lines
into a single file.

The singleton is initialised lazily by the entry-point after CLI parsing —
Blueprints just read from it.

NOTE — this is a STATE container, not a service locator. First-party
functions (compute_cues, load_track, build_context, analyze_session,
run_adk, …) are imported at their call sites, not stashed here. Only
genuinely-mutable runtime state (track, coach, can_reader, caches, locks,
feature flags) and namespace handles (sonoma, adk_orchestrator) live on
this object.
"""

import logging
import os
import sys
import threading
from typing import Optional

log = logging.getLogger("pitwall.state")


# ── Path setup ─────────────────────────────────────────────────────────────────
# src/pitwall/ is a sibling of src/simulator/
SIM_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "simulator")
)
if SIM_DIR not in sys.path:
    sys.path.insert(0, SIM_DIR)

# Project root for resolving data/ paths
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

# DuckDB lives in data/
DB_PATH = os.path.join(PROJECT_ROOT, "data", "pitwall_sessions.duckdb")


class BridgeState:
    """Shared mutable state for the bridge process.

    Attributes are set by the entry-point at startup; Blueprints read them
    at request time. Thread-safe access to DuckDB goes through `db_lock`.
    """

    def __init__(self):
        # ── Track ──────────────────────────────────────────────────────────
        self.track = None              # loaded TrackMap (from track_loader)

        # ── DuckDB ─────────────────────────────────────────────────────────
        # RLock (not Lock) so nested acquires from one thread don't deadlock.
        # 42+ acquire sites across db.py + blueprints; non-reentrant Lock
        # would block silently on any accidental re-entry from a refactor.
        self.db_lock = threading.RLock()
        self.db_path: str = os.path.abspath(DB_PATH)

        # ── Coach engine ───────────────────────────────────────────────────
        self.coach = None              # CoachEngine instance (LitertCoach / RuleCoach)
        self.arbiter = None            # CoachArbiter instance

        # ── Session burst accumulator (for /insights) ──────────────────────
        self.session_bursts: list = []
        self.burst_lock = threading.RLock()

        # ── Session analysis bundle cache ──────────────────────────────────
        self.session_bundles: dict[str, dict] = {}
        self.bundles_lock = threading.RLock()

        # ── CAN reader ─────────────────────────────────────────────────────
        self.can_reader = None
        self.active_session_id: Optional[str] = None


        # ── ADK Q&A ───────────────────────────────────────────────────────
        # `adk_orchestrator` is the root LlmAgent instance (a namespace handle,
        # not a wrapper). Module-level run_adk / stream_adk / get_pending_traces /
        # reset_driver_session are imported directly at call sites from
        # `pitwall.features.coaching.adk_agents`.
        self.adk_orchestrator = None
        self.adk_agent_registry: list = []

        # ── Feature flags ──────────────────────────────────────────────────
        self.has_sonic: bool = False
        self.has_coach: bool = False
        self.has_analyzer: bool = False
        self.has_duckdb: bool = False
        self.has_adk: bool = False

        # ── Namespace handles (set during init) ────────────────────────────
        # `sonoma` is a module handle — callers do `state.sonoma.DANGER_ZONES`.
        # This is legitimate state because the active track namespace can swap.
        self.sonoma = None             # sonoma module

        # ── Constants ──────────────────────────────────────────────────────
        self.sim_dir: str = SIM_DIR

    def init_imports(self):
        """Probe optional third-party dependencies and set feature flags.

        Called once at startup. First-party imports are NOT wrapped in
        try/except — a typo in `pitwall.features.*` should crash startup
        rather than silently degrade to "feature unavailable". Only
        genuinely-optional THIRD-PARTY deps (duckdb, google.adk, …) are
        probed defensively.

        All five of (sonic_model, track_loader, coach_engine,
        session_analyzer, driver_profile) are pure stdlib + first-party —
        no third-party probe needed; their import is the smoke test.
        """
        # ── sonic_model + track_loader (pure stdlib + first-party) ─────────
        import pitwall.features.coaching.sonic_model  # noqa: F401
        import pitwall.features.track.track_loader    # noqa: F401
        self.has_sonic = True
        log.info("✓  sonic_model + track_loader loaded")

        # ── coach_engine (pure stdlib + first-party) ───────────────────────
        # make_coach() may probe LiteRT-LM internally, but it returns a
        # RuleCoach fallback rather than raising — so this is non-fatal.
        from pitwall.features.coaching.coach_engine import make_coach, CoachArbiter
        self.coach = make_coach(kind="auto")
        self.arbiter = CoachArbiter()
        self.has_coach = True
        log.info("✓  coach_engine loaded (%s)", self.coach.name)

        # ── session_analyzer + driver_profile + sonoma ─────────────────────
        # Pure stdlib + first-party. A bug here is a first-party crash.
        import pitwall.features.track.sonoma as _sonoma
        import pitwall.features.session.session_analyzer  # noqa: F401
        import pitwall.features.session.driver_profile    # noqa: F401
        self.sonoma = _sonoma
        self.has_analyzer = True
        log.info("✓  session_analyzer + driver_profile loaded")

        # ── DB backend: DuckDB if usable, else SQLite (stdlib) ─────────────
        # `has_duckdb` is kept as the canonical name across the codebase
        # for back-compat — it now means "an embedded DB backend is
        # reachable", which on Termux/Android resolves to SQLite.
        from pitwall.db import db_backend
        self.has_duckdb = True
        log.info("✓  DB backend: %s", db_backend())

        # ── Schema init (DDL once at boot, not per connection) ─────────────
        # Hoist DDL out of get_db()'s hot path. All bridge tables are
        # `CREATE TABLE IF NOT EXISTS`, so this is idempotent across restarts.
        try:
            from pitwall.db import init_schema_once
            init_schema_once()
            log.info("✓  DB schema initialised (%s)", db_backend())
        except Exception as e:
            log.warning("DB schema init failed: %s", e)

        # ── ADK multi-agent backend (google-adk is genuinely optional) ─────
        # adk_agents imports google.adk at module top; an ImportError here
        # means the SDK isn't installed. First-party bugs in adk_agents
        # itself will still crash because the module body executes on import.
        try:
            from pitwall.features.coaching.adk_agents import (
                coach_orchestrator,
                HAS_ADK as _adk_loaded,
                AGENT_REGISTRY,
            )
            self.adk_orchestrator = coach_orchestrator
            self.adk_agent_registry = AGENT_REGISTRY
            self.has_adk = _adk_loaded and coach_orchestrator is not None
            if self.has_adk:
                log.info("✓  ADK coach_orchestrator loaded — %d agents (LiteRT-LM E4B)",
                         len(AGENT_REGISTRY))
            else:
                log.warning("adk_agents imported but google-adk not installed — ADK disabled")
        except ImportError as e:
            log.warning("adk_agents not importable (%s) — ADK disabled", e)


# Module-level singleton — all Blueprints import this.
state = BridgeState()

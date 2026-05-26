"""bridge — modular Flask package for the Pitwall coaching HTTP surface.

Splits the monolithic pitwall_bridge.py into focused modules:
    state.py         shared mutable state (singletons, locks, feature flags)
    db.py            DuckDB schema DDL + helper functions
    helpers.py       lap detection, frame transforms, coaching helpers
    bp_core.py       Blueprint: /health, /analyze
    bp_session.py    Blueprint: session CRUD, import/export, frames
    bp_analysis.py   Blueprint: Phase-6 lap endpoints + analytics proxies
    bp_coaching.py   Blueprint: brief, debrief, ask, score, insights
    bp_signals.py    Blueprint: ADR-015 signal sink + capabilities
    bp_track.py      Blueprint: markers, weather, elevation, corners, driver
    bp_realtime.py   Blueprint: SSE cue/notification streams, spectator tokens
    bp_diagnostics.py Blueprint: LLM friction, CAN state

Usage (from pitwall_bridge.py):
    from pitwall.state import state
    from pitwall.db import get_db
    from bridge import register_blueprints
    register_blueprints(app)
"""

from flask import Flask
from flask_cors import CORS

from pitwall.state import state  # noqa: F401
from pitwall import db  # noqa: F401
from pitwall.db import get_db, seed_signal_registry, compute_capabilities as _compute_capabilities, WIDE_SIGNAL_NAMES as _WIDE_SIGNAL_NAMES  # noqa: F401


def register_blueprints(app):
    """Register all bridge Blueprints on the Flask app."""
    from pitwall.features.bp_core import bp as bp_core
    from pitwall.features.session.bp_session import bp as bp_session
    from pitwall.features.session.bp_analysis import bp as bp_analysis
    from pitwall.features.session.bp_replay import bp as bp_replay
    from pitwall.features.coaching.bp_coaching import bp as bp_coaching
    from pitwall.features.telemetry.bp_signals import bp as bp_signals
    from pitwall.features.track.bp_track import bp as bp_track
    from pitwall.features.realtime.bp_realtime import bp as bp_realtime
    from pitwall.features.bp_diagnostics import bp as bp_diagnostics
    from pitwall.features.bp_leaderboard import bp as bp_leaderboard
    from pitwall.features.bp_cars import bp as bp_cars

    for blueprint in (bp_core, bp_session, bp_analysis, bp_replay,
                      bp_coaching, bp_signals, bp_track, bp_realtime,
                      bp_diagnostics, bp_leaderboard, bp_cars):
        app.register_blueprint(blueprint)

def create_app() -> Flask:
    """Factory: create Flask app, register blueprints, wire CORS."""
    app = Flask(__name__)
    CORS(app)
    register_blueprints(app)
    return app


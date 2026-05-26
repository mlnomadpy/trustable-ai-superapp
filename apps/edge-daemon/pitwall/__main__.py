#!/usr/bin/env python3
"""Pitwall Bridge — modular entry point.

All domain logic, endpoints, and shared state live in the `src/pitwall/`
package. This file handles only:
  1. CLI argument parsing
  2. Flask app creation
  3. Bridge state initialization
  4. Blueprint registration
  5. CAN reader startup
  6. app.run()

Usage:
    python -m pitwall --track data/tracks/sonoma.json --port 8765
"""

import argparse
import atexit
import logging
import os
import signal
import subprocess
import sys
import threading
import time

from flask import Flask
from flask_cors import CORS

log = logging.getLogger("pitwall.main")

# ── Bootstrap path so pitwall/ can find src/simulator + src/pitwall ─────────────
SRC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
SIM_DIR = os.path.join(SRC_DIR, "simulator")
for p in (SRC_DIR, SIM_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

# ── Pitwall backend package ───────────────────────────────────────────────────
from pitwall.state import state
from pitwall.db import (
    db_conn, DuckDbUnavailable,
    seed_signal_registry, log_llm_friction, reset_live_session, ensure_session_row,
)
from pitwall import create_app, register_blueprints


app = create_app()


# ── Graceful shutdown ─────────────────────────────────────────────────────────
# DuckDB invalidates the whole file when a write is killed mid-flight (we
# already had to write rotation-recovery for this in db.py::reset_live_session).
# The right answer is to never let it happen: handle SIGTERM/SIGINT, stop the
# CAN reader + simulator, CHECKPOINT, release the Termux wake-lock, then exit.
# Belt and suspenders via atexit in case we're terminated by a path that
# doesn't go through main()'s normal flow.

_shutdown_done = threading.Event()


def _shutdown(reason: str = "exit"):
    """Idempotent graceful shutdown. Safe to call from signal handler or atexit."""
    if _shutdown_done.is_set():
        return
    _shutdown_done.set()
    log.info("⏻  shutdown (%s)", reason)

    sim = getattr(state, "simulator", None)
    if sim is not None:
        try:
            sim.stop(timeout=2.0)
            log.info("   simulator stopped")
        except Exception as e:
            log.warning("   simulator stop failed: %s", e)

    reader = getattr(state, "can_reader", None)
    if reader is not None:
        try:
            reader.stop(timeout=2.0)
            log.info("   CAN reader stopped")
        except Exception as e:
            log.warning("   CAN reader stop failed: %s", e)

    if getattr(state, "has_duckdb", False):
        try:
            with db_conn() as conn:
                conn.execute("CHECKPOINT")
                log.info("   DuckDB CHECKPOINT ok")
        except DuckDbUnavailable:
            pass
        except Exception as e:
            log.warning("   DuckDB CHECKPOINT failed: %s", e)

    # Release Termux wake-lock if one was acquired. termux-wake-unlock is a
    # no-op if no lock is held; safe to call unconditionally.
    try:
        subprocess.run(
            ["termux-wake-unlock"],
            timeout=2.0, check=False,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass


def _signal_shutdown(signum, _frame):
    _shutdown(reason=f"signal {signum}")
    # Re-raise default behavior for SIGINT so Python exits with the right code
    sys.exit(0 if signum == signal.SIGTERM else 130)


signal.signal(signal.SIGTERM, _signal_shutdown)
signal.signal(signal.SIGINT, _signal_shutdown)
atexit.register(_shutdown, "atexit")


def _start_can_reader(*, session_id, interface, channel, bitrate, dbc_paths,
                      flush_ms, car_config_path=None):
    """Start a CanReader thread that pumps CAN frames into pitwall's stores.

    Also records the start args on `state.can_reader_args` so the watchdog
    can restart the reader with the same configuration if it gets stuck
    (USB unplug/re-plug, kernel transient).
    """
    try:
        from pitwall.features.telemetry.can_reader import CanReader
    except ImportError as e:
        log.warning("CAN reader unavailable (%s); install python-can + cantools", e)
        return None
    try:
        # CanReader needs the top-level `pitwall` package as `bridge` so it
        # can reach both `bridge.state.db_lock` and `bridge.db.get_db()`.
        # Passing `pitwall.state` was a pre-existing bug — the wide/tall
        # sink calls crash with AttributeError once frames actually flow.
        reader = CanReader(
            session_id=session_id, interface=interface, channel=channel,
            bitrate=bitrate, dbc_paths=dbc_paths, flush_ms=flush_ms,
            bridge=sys.modules["pitwall"],
            car_config_path=car_config_path,
        )
        reader.start()
        state.can_reader = reader
        # Watchdog needs these to spawn a replacement reader with the same
        # configuration. Store the kwargs verbatim so the restart path is
        # an obvious one-line _start_can_reader(**state.can_reader_args).
        state.can_reader_args = dict(
            session_id=session_id, interface=interface, channel=channel,
            bitrate=bitrate, dbc_paths=dbc_paths, flush_ms=flush_ms,
            car_config_path=car_config_path,
        )
        log.info("✓  CAN reader started (interface=%s channel=%s session=%s)",
                 interface, channel, session_id)
        return reader
    except Exception as e:
        log.warning("CAN reader failed to start: %s", e)
        return None


# ── Background monitors ───────────────────────────────────────────────────────
#
# Two daemon threads that observe the bridge's runtime health.
#   _rss_monitor:   logs the bridge process RSS every 60 s. Flags growth
#                   above the alert threshold so memory leaks surface in
#                   logs instead of as OOM kills on the phone.
#   _can_watchdog:  if the CAN reader is "loaded" but reports zero fps for
#                   > 30 s, restart it. Recovers from USB unplug/replug
#                   without bridge restart.
# Both threads are daemon=True so they never block process exit; both
# defer-import their heavy deps so a missing module degrades gracefully.

_RSS_ALERT_GROWTH_MB_PER_MIN = 10.0
_CAN_WATCHDOG_STUCK_S = 30.0


def _rss_monitor():
    try:
        import psutil
    except ImportError:
        log.info("psutil not installed; skipping RSS monitor")
        return
    proc = psutil.Process()
    last_rss_mb = None
    last_t = time.monotonic()
    while True:
        time.sleep(60.0)
        try:
            rss_mb = proc.memory_info().rss / (1024 * 1024)
        except Exception as e:
            log.warning("RSS monitor read failed: %s", e)
            continue
        now = time.monotonic()
        if last_rss_mb is None:
            log.info("RSS baseline: %.1f MB", rss_mb)
        else:
            dt_min = (now - last_t) / 60.0 or 1.0
            growth_per_min = (rss_mb - last_rss_mb) / dt_min
            level = (logging.WARNING
                     if growth_per_min > _RSS_ALERT_GROWTH_MB_PER_MIN
                     else logging.INFO)
            log.log(level, "RSS: %.1f MB (Δ %+.1f MB/min over %.0f s)",
                    rss_mb, growth_per_min, dt_min * 60.0)
        last_rss_mb = rss_mb
        last_t = now


def _can_watchdog():
    log.info("CAN watchdog started (restart if fps=0 for >%.0fs)",
             _CAN_WATCHDOG_STUCK_S)
    while True:
        time.sleep(15.0)
        reader = getattr(state, "can_reader", None)
        args = getattr(state, "can_reader_args", None)
        if reader is None or args is None:
            continue
        try:
            snap = reader.state()
        except Exception as e:
            log.warning("watchdog: reader.state() failed: %s", e)
            continue
        if not snap.get("loaded"):
            continue
        last_age = snap.get("last_frame_age_s")
        fps      = snap.get("frames_per_second", 0.0) or 0.0
        if fps > 0:
            continue
        if last_age is None or last_age < _CAN_WATCHDOG_STUCK_S:
            continue
        # Stuck: alive but no frames in >30s. Restart with the same config.
        log.error(
            "CAN reader appears stuck (fps=%.1f, last_frame_age=%.1fs); "
            "restarting on %s/%s", fps, last_age, args["interface"], args["channel"],
        )
        try:
            reader.stop(timeout=2.0)
        except Exception as e:
            log.warning("watchdog: reader.stop failed: %s", e)
        state.can_reader = None
        try:
            _start_can_reader(**args)
        except Exception as e:
            log.error("watchdog: reader restart failed: %s", e)


def _spawn_monitors(*, with_watchdog: bool):
    """Launch the daemon monitor threads. Idempotent at startup."""
    threading.Thread(target=_rss_monitor, name="pitwall-rss-monitor",
                     daemon=True).start()
    if with_watchdog:
        threading.Thread(target=_can_watchdog, name="pitwall-can-watchdog",
                         daemon=True).start()


def main():
    """CLI entry point for the Pitwall Bridge server."""
    parser = argparse.ArgumentParser(description="Pitwall Bridge Server")
    parser.add_argument("--track", default=os.path.join(SIM_DIR, "sonoma.json"))
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--can-channel", default=None)
    parser.add_argument("--can-interface", default="virtual")
    parser.add_argument("--can-bitrate", type=int, default=1_000_000,
                        help="CAN bus bitrate; AiM MXP CAN2 output is 1 Mbit/s")
    parser.add_argument("--can-dbc", action="append", default=None)
    parser.add_argument("--can-car-config", default=None,
                        help="per-car YAML for the post-decode pipeline "
                             "(default: data/cars/bmw_e46_m3.yaml; "
                             "pass --can-no-car-config to skip)")
    parser.add_argument("--can-no-car-config", action="store_true",
                        help="skip car config; emit raw DBC signal names")
    parser.add_argument("--can-session-id", default=None)
    parser.add_argument("--can-flush-ms", type=int, default=100)
    parser.add_argument("--dev", action="store_true",
                        help="serve via Flask's dev server instead of waitress "
                             "(local debugging only; never use in prod)")
    parser.add_argument("--simulate", action="store_true",
                        help="spawn the AiM MXP synthetic simulator and a "
                             "virtual-bus CanReader so the bridge has live "
                             "telemetry without any real car connected")
    parser.add_argument("--simulate-speed", type=float, default=1.0,
                        help="simulator speed multiplier (1.0 = real time)")
    parser.add_argument("--simulate-lap-seconds", type=float, default=60.0,
                        help="duration of one synthetic lap in seconds")
    parser.add_argument("--log-level", default="INFO",
                        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
                        help="logging level for the bridge process")
    parser.add_argument("--no-watchdog", action="store_true",
                        help="skip the CAN reader watchdog (don't auto-restart on stuck)")
    args = parser.parse_args()

    # 0. Logging — set up first so every subsequent step can log.
    #    The bridge prints to stdout (Termux's runit/svlogd captures it),
    #    so a single-line format with %(asctime)s + %(levelname)s + %(name)s
    #    survives the trip through log rotation. Keep the unicode badges
    #    (✓/⚠/⏻) in messages where they're load-bearing context.
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)-7s %(name)s  %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    # 1. Initialize imports (feature flags, coach engine, etc.)
    state.init_imports()

    # 2. Load track
    if state.has_sonic and os.path.exists(args.track):
        try:
            from pitwall.features.track.track_loader import load_track
            state.track = load_track(args.track)
            log.info("✓  Track: %s (%d corners)",
                     state.track.name, len(state.track.corners))
        except Exception as e:
            log.warning("Track load failed: %s", e)

    # 3. Wire LLM friction logger
    if state.has_coach:
        from pitwall.features.coaching.coach_engine import set_friction_logger
        set_friction_logger(log_llm_friction)

    # 4. Seed signal registry
    if state.has_duckdb:
        try:
            from pitwall.db import REGISTRY_SEED_PATH
            n = seed_signal_registry()
            log.info("✓  signal_registry seeded (%d entries from %s)",
                     n, os.path.relpath(REGISTRY_SEED_PATH))
        except Exception as e:
            log.warning("signal_registry seed skipped: %s", e)

    # 5. CAN reader (+ optional synthetic simulator)
    if args.simulate and not args.can_channel:
        # Auto-pick a virtual channel so the simulator and reader meet
        # in-process. Override --can-interface/--can-channel only if the
        # user didn't set them.
        args.can_interface = "virtual"
        args.can_channel = "pitwall_simulate"

    if args.can_channel:
        sid = args.can_session_id or "_live"
        if sid == "_live":
            reset_live_session()
        ensure_session_row(sid, track=(state.track.name if state.track else None),
                           note="auto-created by bridge --can-channel" + (" (live placeholder)" if sid == "_live" else ""))
        _start_can_reader(session_id=sid, interface=args.can_interface, channel=args.can_channel,
                          bitrate=args.can_bitrate, dbc_paths=args.can_dbc, flush_ms=args.can_flush_ms,
                          car_config_path=(False if args.can_no_car_config else args.can_car_config))
        # Stash the YAML + DBC paths on state so /diagnostics/can can surface
        # them to the PWA's Pit Stall page (it used to hardcode bogus values).
        state.car_config_path = (args.can_car_config or "") if not args.can_no_car_config else ""
        state.can_dbc_path = args.can_dbc or ""
        log.info("CAN session: %s", sid)

        if args.simulate:
            try:
                # src/simulator is on sys.path (see bootstrap above), so
                # import the module name directly.
                from aim_mxp_simulator import AimMxpSimulator, LapProfile
                sim = AimMxpSimulator(
                    interface=args.can_interface, channel=args.can_channel,
                    bitrate=args.can_bitrate, speed_x=args.simulate_speed,
                    profile=LapProfile(lap_seconds=args.simulate_lap_seconds),
                )
                sim.start()
                state.simulator = sim
                log.info("✓  Synthetic simulator running on %s/%s "
                         "(%.2f× speed, %ds laps)",
                         args.can_interface, args.can_channel,
                         args.simulate_speed, int(args.simulate_lap_seconds))
            except Exception as e:
                log.warning("Simulator failed to start: %s", e)

    # 6. Background monitors (RSS + CAN watchdog).
    # Spawn after the reader is up so the watchdog sees a real state().
    _spawn_monitors(with_watchdog=(args.can_channel is not None
                                   and not args.no_watchdog))

    # 7. Launch
    port = args.port
    db_path = state.db_path
    log.info("🏁  Pitwall Bridge v2 on http://127.0.0.1:%d", port)
    log.info("    Engine: %s",
             "sonic_model (real cues)" if state.has_sonic else "rule fallback")
    log.info("    DuckDB: %s",
             ("enabled → " + db_path) if state.has_duckdb else "disabled")
    if args.can_channel:
        log.info("    CAN:    %s/%s", args.can_interface, args.can_channel)
    log.info("    Emulator tunnel: ~/Library/Android/sdk/platform-tools/adb "
             "reverse tcp:%d tcp:%d", port, port)

    if args.dev:
        # Dev path: Flask's built-in server. Re-prints the production
        # warning at boot — that's the intended signal.
        try:
            app.run(host="127.0.0.1", port=port, debug=False, threaded=True)
        finally:
            _shutdown(reason="dev server stopped")
    else:
        # Production path: waitress is a pure-Python WSGI server with
        # bounded thread pool + per-request channel timeout. No DNS
        # surprise, no kernel module, runs on Termux. Same `127.0.0.1`
        # bind as before.
        try:
            from waitress import serve
        except ImportError:
            log.warning("waitress not installed — falling back to Flask dev server. "
                        "pip install waitress for production-ready serving")
            try:
                app.run(host="127.0.0.1", port=port, debug=False, threaded=True)
            finally:
                _shutdown(reason="dev fallback stopped")
        else:
            try:
                serve(
                    app, host="127.0.0.1", port=port,
                    threads=8,                   # bounded worker pool
                    channel_timeout=30,          # kill stuck requests
                    cleanup_interval=10,         # housekeep dead channels
                    ident="pitwall-bridge",      # appears in Server: header
                )
            finally:
                _shutdown(reason="waitress stopped")


if __name__ == "__main__":
    main()

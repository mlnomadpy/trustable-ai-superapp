"""bridge.bp_replay — Blueprint: session replay (simulated car from recording).

Drives the PWA's live HUD from a previously-recorded session in the bridge
DB, instead of from a real CAN bus. Publishes frames to `telemetry_bus`
with the exact same canonical shape `can_reader._flush_wide` uses, so the
PWA can't tell the difference between live and replay.

Endpoints:
    POST /session/replay/start   — body { source_session_id, speed, loop }
    POST /session/replay/stop    — { stopped, frames_emitted }
    GET  /session/replay/status  — running/idle, frame_idx, elapsed_s, ...

One replay thread per bridge process. Starting a replay while a CAN reader
is running stops the CAN reader first (avoids two publishers on the same
session_id).
"""

import logging
import threading
import time

from flask import Blueprint, request, jsonify

from pitwall.state import state
from pitwall.db import db_conn, DuckDbUnavailable, WIDE_SIGNAL_NAMES  # noqa: F401


log = logging.getLogger(__name__)

bp = Blueprint("replay", __name__)


# ── Module-level replay state ────────────────────────────────────────────────

_replay_lock = threading.Lock()
_replay_thread: threading.Thread | None = None
_replay_stop_event = threading.Event()
_replay_status: dict = {"running": False}


# Mapping from the wide-table column names to the SSE canonical names that
# `can_reader._flush_wide` publishes. The PWA reads these — don't rename.
_WIDE_COL_TO_SSE = {
    "timestamp":    "timestamp",
    "distance_m":   "distance",
    "speed_ms":     "speed",
    "g_lat":        "g_lat",
    "g_long":       "g_long",
    "combo_g":      "combo_g",
    "brake_bar":    "brake_pressure",
    "throttle_pct": "throttle",
    "steering_deg": "steering",
    "rpm":          "rpm",
    "lat":          "lat",
    "lon":          "lon",
}


def _load_replay_data(sid: str):
    """Return (wide_rows, extras_by_frame_idx) for the given session.

    wide_rows: list of dicts in canonical SSE shape, one per telemetry row.
    extras_by_frame_idx: list[dict] parallel to wide_rows; each dict holds
    the latest-known tall-signal value (by signal name) at that frame's
    timestamp, for signal names not already in the wide snapshot.
    """
    with db_conn() as conn:
        wide = conn.execute(
            """SELECT timestamp, distance_m, speed_ms, g_lat, g_long,
                      combo_g, brake_bar, throttle_pct, steering_deg,
                      rpm, lat, lon
               FROM telemetry
               WHERE session_id = ?
               ORDER BY timestamp""",
            [sid],
        ).fetchall()

        # Tall signals join their human-readable name from signal_registry.
        tall = conn.execute(
            """SELECT ts.t, sr.name, ts.value
               FROM telemetry_signals ts
               JOIN signal_registry sr USING(signal_id)
               WHERE ts.session_id = ?
               ORDER BY ts.t""",
            [sid],
        ).fetchall()

    wide_cols = ("timestamp", "distance_m", "speed_ms", "g_lat", "g_long",
                 "combo_g", "brake_bar", "throttle_pct", "steering_deg",
                 "rpm", "lat", "lon")

    wide_rows: list[dict] = []
    for row in wide:
        snap = {}
        for col, val in zip(wide_cols, row):
            sse_key = _WIDE_COL_TO_SSE[col]
            snap[sse_key] = float(val) if val is not None else None
        wide_rows.append(snap)

    # Group tall samples by nearest wide-row timestamp. Walk both lists in
    # one O(N+M) pass — both are timestamp-sorted.
    extras_by_frame: list[dict] = [dict() for _ in wide_rows]
    if not wide_rows or not tall:
        return wide_rows, extras_by_frame

    # latest[name] = most recent value seen so far across all earlier tall samples
    latest: dict[str, float] = {}
    j = 0  # cursor into tall
    n_tall = len(tall)
    wide_ts = [r["timestamp"] for r in wide_rows]
    n_wide = len(wide_rows)

    # Skip any used SSE canonical names so extras don't shadow them.
    canonical_keys = set(_WIDE_COL_TO_SSE.values())

    for i in range(n_wide):
        t_i = wide_ts[i]
        # advance j while tall_t <= t_i
        while j < n_tall and tall[j][0] <= t_i:
            _, name, value = tall[j]
            if name not in canonical_keys and value is not None:
                try:
                    latest[name] = float(value)
                except (TypeError, ValueError):
                    pass
            j += 1
        # Snapshot of latest tall values at this frame
        if latest:
            extras_by_frame[i] = dict(latest)

    return wide_rows, extras_by_frame


def _replay_loop(source_sid: str, speed: float, loop: bool,
                 wide_rows: list[dict], extras_by_frame: list[dict]):
    """Background thread: emit frames to telemetry_bus at recorded cadence."""
    try:
        from pitwall.features.realtime.bp_realtime import telemetry_bus
    except Exception as e:  # noqa: BLE001
        log.exception("replay: failed to import telemetry_bus: %s", e)
        with _replay_lock:
            _replay_status.clear()
            _replay_status.update({"running": False, "error": str(e)})
        return

    n_frames = len(wide_rows)
    started_at = time.monotonic()
    frames_emitted = 0
    last_log_idx = -1

    try:
        while not _replay_stop_event.is_set():
            for i in range(n_frames):
                if _replay_stop_event.is_set():
                    break
                snap = wide_rows[i]
                extras = extras_by_frame[i] or {}
                frame = {**snap, **{k: v for k, v in extras.items()
                                    if k not in snap}}
                telemetry_bus.publish(source_sid, frame)
                frames_emitted += 1

                # Update status (cheap, under lock)
                with _replay_lock:
                    _replay_status["frame_idx"] = i
                    _replay_status["total_frames"] = n_frames
                    _replay_status["elapsed_s"] = time.monotonic() - started_at
                    _replay_status["frames_emitted"] = frames_emitted
                    # est_remaining_s = (last_ts - cur_ts) / speed
                    last_ts = wide_rows[-1].get("timestamp") or 0.0
                    cur_ts = snap.get("timestamp") or 0.0
                    rem = max(0.0, (last_ts - cur_ts)) / max(speed, 1e-6)
                    _replay_status["est_remaining_s"] = rem

                # Keep state.active_session_id accurate (for /health)
                state.active_session_id = source_sid

                if i // 500 != last_log_idx:
                    last_log_idx = i // 500
                    log.info("replay: frame %d/%d (sid=%s)",
                             i, n_frames, source_sid)

                # Sleep to the next frame's timestamp
                if i + 1 < n_frames:
                    t_now = snap.get("timestamp")
                    t_next = wide_rows[i + 1].get("timestamp")
                    if t_now is not None and t_next is not None:
                        dt = (t_next - t_now) / max(speed, 1e-6)
                        if dt < 0:
                            dt = 0.0
                        # Cap individual sleep so a stop signal isn't blocked
                        # for too long. Use Event.wait so we exit early on stop.
                        remaining = dt
                        while remaining > 0 and not _replay_stop_event.is_set():
                            chunk = min(remaining, 1.0)
                            if _replay_stop_event.wait(timeout=chunk):
                                break
                            remaining -= chunk

            if not loop or _replay_stop_event.is_set():
                break
            # On loop, restart timing baseline so elapsed_s reflects current pass
            started_at = time.monotonic()
            log.info("replay: looping back to frame 0 (sid=%s)", source_sid)
    except Exception as e:  # noqa: BLE001
        log.exception("replay: thread crashed: %s", e)
        with _replay_lock:
            _replay_status.clear()
            _replay_status.update({
                "running": False,
                "error": str(e),
                "frames_emitted": frames_emitted,
            })
        return

    with _replay_lock:
        _replay_status["running"] = False
        _replay_status["frames_emitted"] = frames_emitted
    log.info("replay: thread exiting (frames_emitted=%d, loop=%s)",
             frames_emitted, loop)


# ── HTTP routes ──────────────────────────────────────────────────────────────

@bp.route("/session/replay/start", methods=["POST"])
def replay_start():
    """Start a session replay. Body JSON: source_session_id, speed, loop."""
    global _replay_thread

    body = request.get_json(silent=True) or {}
    sid = (body.get("source_session_id") or "").strip()
    if not sid:
        return jsonify({"error": "source_session_id required"}), 400
    try:
        speed = float(body.get("speed", 1.0))
    except (TypeError, ValueError):
        speed = 1.0
    if speed <= 0:
        speed = 1.0
    loop = bool(body.get("loop", False))

    with _replay_lock:
        if _replay_thread is not None and _replay_thread.is_alive():
            return jsonify({
                "error": "a replay is already running; stop it first",
                "source_session_id": _replay_status.get("source_session_id"),
            }), 409

    # Load recorded frames (outside the lock — DB read can take a moment)
    try:
        wide_rows, extras_by_frame = _load_replay_data(sid)
    except DuckDbUnavailable:
        return jsonify({"error": "no DB backend available"}), 503
    except Exception as e:  # noqa: BLE001
        log.exception("replay: load failed: %s", e)
        return jsonify({"error": f"failed to load replay data: {e}"}), 500

    if not wide_rows:
        return jsonify({
            "error": "source session has no telemetry rows",
            "source_session_id": sid,
        }), 404

    # est_duration_s = (last_ts - first_ts) / speed
    first_ts = wide_rows[0].get("timestamp") or 0.0
    last_ts = wide_rows[-1].get("timestamp") or 0.0
    est_duration_s = max(0.0, (last_ts - first_ts)) / max(speed, 1e-6)

    # Stop any running CAN reader to avoid two publishers on the same sid
    if state.can_reader is not None:
        try:
            log.info("replay: stopping existing CAN reader before replay")
            state.can_reader.stop(timeout=2.0)
        except Exception as e:  # noqa: BLE001
            log.warning("replay: CAN reader stop raised: %s", e)
        state.can_reader = None

    state.active_session_id = sid

    with _replay_lock:
        _replay_stop_event.clear()
        _replay_status.clear()
        _replay_status.update({
            "running": True,
            "source_session_id": sid,
            "speed": speed,
            "loop": loop,
            "frame_idx": 0,
            "total_frames": len(wide_rows),
            "elapsed_s": 0.0,
            "est_remaining_s": est_duration_s,
            "frames_emitted": 0,
        })
        _replay_thread = threading.Thread(
            target=_replay_loop,
            args=(sid, speed, loop, wide_rows, extras_by_frame),
            name="pitwall-replay",
            daemon=True,
        )
        _replay_thread.start()

    return jsonify({
        "replay_id": sid,
        "source_session_id": sid,
        "total_frames": len(wide_rows),
        "est_duration_s": est_duration_s,
        "speed": speed,
        "loop": loop,
    }), 200


@bp.route("/session/replay/stop", methods=["POST"])
def replay_stop():
    """Stop the running replay (no-op if not running)."""
    global _replay_thread

    with _replay_lock:
        running = (_replay_thread is not None
                   and _replay_thread.is_alive())
        if not running:
            return jsonify({
                "stopped": False,
                "frames_emitted": int(_replay_status.get("frames_emitted", 0)),
            }), 200
        thread = _replay_thread

    _replay_stop_event.set()
    thread.join(timeout=2.0)

    with _replay_lock:
        _replay_thread = None
        _replay_status["running"] = False
        frames_emitted = int(_replay_status.get("frames_emitted", 0))

    return jsonify({"stopped": True, "frames_emitted": frames_emitted}), 200


@bp.route("/session/replay/status", methods=["GET"])
def replay_status():
    """Snapshot of the replay state. {"running": false} when idle."""
    with _replay_lock:
        running = (_replay_thread is not None
                   and _replay_thread.is_alive())
        if not running:
            # If a thread crashed it may have left running=False + error set
            if _replay_status.get("error"):
                return jsonify({
                    "running": False,
                    "error": _replay_status.get("error"),
                    "frames_emitted": int(_replay_status.get("frames_emitted", 0)),
                }), 200
            return jsonify({"running": False}), 200
        # Return a shallow copy so callers don't see further mutation mid-serialise
        snap = dict(_replay_status)
    return jsonify(snap), 200

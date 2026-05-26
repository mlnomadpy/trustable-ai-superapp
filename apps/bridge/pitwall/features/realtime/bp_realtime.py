"""bridge.bp_realtime — Blueprint: SSE streams + spectator tokens.

Owns the in-memory pub/sub buses for coaching cues and notifications,
the spectator token CRUD, and the SSE generator endpoints.
"""

import json
import queue as _queue
import secrets as _secrets
import threading
import time
from typing import Optional

from flask import Blueprint, request, jsonify, Response, stream_with_context

bp = Blueprint("realtime", __name__)


# ── CueBus — in-memory pub/sub ─────────────────────────────────────────────────

class CueBus:
    """In-memory pub/sub of coaching cues, keyed by session_id.

    Each SSE subscriber (one HTTP connection from the PWA's on-track HUD)
    gets its own bounded queue. `publish(sid, event)` pushes to every
    subscriber for that session. Lost queues (subscriber disconnected,
    queue full) are cleaned up lazily on the next publish.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._subs: dict[str, list[_queue.Queue]] = {}

    def subscribe(self, sid: str, maxsize: int = 32) -> _queue.Queue:
        """Register a new SSE client queue for the given session."""
        q: _queue.Queue = _queue.Queue(maxsize=maxsize)
        with self._lock:
            self._subs.setdefault(sid, []).append(q)
        return q

    def unsubscribe(self, sid: str, q: _queue.Queue):
        """Remove a client queue and clean up empty session entries."""
        with self._lock:
            if sid in self._subs:
                try:
                    self._subs[sid].remove(q)
                except ValueError:
                    pass
                if not self._subs[sid]:
                    del self._subs[sid]

    def publish(self, sid: str, event: dict):
        """Push an event dict to all subscribed queues for this session."""
        dead: list[_queue.Queue] = []
        with self._lock:
            queues = list(self._subs.get(sid, []))
        for q in queues:
            try:
                q.put_nowait(event)
            except _queue.Full:
                dead.append(q)
        for q in dead:
            self.unsubscribe(sid, q)


# Module-level bus instances — imported by bp_core for /analyze fan-out.
cue_bus = CueBus()
notif_bus = CueBus()
telemetry_bus = CueBus()


# ── SSE: /cues/stream ─────────────────────────────────────────────────────────

@bp.route("/cues/stream", methods=["GET"])
def cues_stream():
    """Server-Sent Events stream of coaching cues for a session.

    Query params:
        session_id   required — only events for this session are streamed

    Each event is JSON:
        {ts, burst_id, phrase_id, text, priority, emotion, source}

    The PWA's on-track HUD subscribes once at session start, reads cues
    until the connection closes (Pause menu's QUIT, page hide, network
    drop). Auto-reconnect logic is the client's responsibility.
    """
    sid = request.args.get("session_id")
    if not sid:
        return jsonify({"error": "session_id query param required"}), 400

    q = cue_bus.subscribe(sid)

    def gen():
        try:
            yield "event: hello\n"
            yield f"data: {json.dumps({'session_id': sid})}\n\n"
            while True:
                try:
                    event = q.get(timeout=15.0)
                except _queue.Empty:
                    yield ": keepalive\n\n"
                    continue
                yield "event: cue\n"
                yield f"data: {json.dumps(event)}\n\n"
        finally:
            cue_bus.unsubscribe(sid, q)

    return Response(
        stream_with_context(gen()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ── SSE: /telemetry/stream ────────────────────────────────────────────────────

@bp.route("/telemetry/stream", methods=["GET"])
def telemetry_stream():
    """Server-Sent Events stream of high-frequency telemetry for a session.
    
    Query params:
        session_id   required — only events for this session are streamed
    """
    sid = request.args.get("session_id")
    if not sid:
        return jsonify({"error": "session_id query param required"}), 400

    q = telemetry_bus.subscribe(sid, maxsize=128)

    def gen():
        try:
            yield "event: hello\n"
            yield f"data: {json.dumps({'session_id': sid})}\n\n"
            while True:
                try:
                    event = q.get(timeout=15.0)
                except _queue.Empty:
                    yield ": keepalive\n\n"
                    continue
                yield "event: telemetry\n"
                yield f"data: {json.dumps(event)}\n\n"
        finally:
            telemetry_bus.unsubscribe(sid, q)

    return Response(
        stream_with_context(gen()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ── SSE: /notifications ───────────────────────────────────────────────────────

def emit_notification(driver: Optional[str], kind: str, **fields):
    """Publish an async event for the PWA's notification center.

    Used by debrief-ready, medal-earned, level-up, hardware-warning,
    evolution-ready callsites elsewhere in the bridge. Fan-out is per-driver
    (or global when `driver` is None).
    """
    event = {
        "ts":     time.time(),
        "kind":   kind,
        "driver": driver,
        **fields,
    }
    notif_bus.publish(driver or "*", event)
    notif_bus.publish("*", event)


@bp.route("/notifications", methods=["GET"])
def notifications_stream():
    """SSE stream of async events for the notification center.

    Query params:
        driver   filter to events for this driver only ('*' or omitted = all)

    Each event is JSON: {ts, kind, driver, ...kind-specific fields}.
    Kinds match `screens/33-notification-center.md`:
      debrief-ready · medal-earned · level-up · affinity-tier ·
      track-unlock · hardware-warning · evolution-ready · session-saved
    """
    driver = request.args.get("driver") or "*"
    q = notif_bus.subscribe(driver)

    def gen():
        try:
            yield "event: hello\n"
            yield f"data: {json.dumps({'driver': driver})}\n\n"
            while True:
                try:
                    event = q.get(timeout=30.0)
                except _queue.Empty:
                    yield ": keepalive\n\n"
                    continue
                yield "event: notification\n"
                yield f"data: {json.dumps(event)}\n\n"
        finally:
            notif_bus.unsubscribe(driver, q)

    return Response(
        stream_with_context(gen()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control":     "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ── Spectator tokens ──────────────────────────────────────────────────────────

_spectator_tokens: dict[str, dict] = {}
_SPECTATOR_TTL_S = 4 * 3600


def _purge_expired_tokens():
    now = time.time()
    expired = [t for t, info in _spectator_tokens.items() if info["expires_at"] < now]
    for t in expired:
        _spectator_tokens.pop(t, None)


@bp.route("/spectator/token", methods=["POST"])
def spectator_token_create():
    """Generate a one-time, time-limited token granting read-only access
    to a session's live cue stream. Used by the PWA's Live Spectator
    screen to share a viewing link with a passenger or external display.

    Body: { session_id: str } — the session this token grants access to
    Response: { token, session_id, expires_at, url } — `url` is the
    suggested deep-link the PWA renders as a QR code.
    """
    body = request.get_json(force=True, silent=True) or {}
    sid = body.get("session_id")
    if not sid:
        return jsonify({"error": "session_id required"}), 400

    _purge_expired_tokens()
    token = _secrets.token_urlsafe(24)
    expires_at = time.time() + _SPECTATOR_TTL_S
    _spectator_tokens[token] = {"session_id": sid, "expires_at": expires_at}
    return jsonify({
        "token":      token,
        "session_id": sid,
        "expires_at": expires_at,
        "ttl_s":      _SPECTATOR_TTL_S,
        "url":        f"/spectator/{sid}?token={token}",
    })


def validate_spectator_token(token: str) -> Optional[str]:
    """Returns the session_id the token grants access to, or None if
    invalid / expired. Caller should 401 on None."""
    _purge_expired_tokens()
    info = _spectator_tokens.get(token)
    if info is None:
        return None
    if info["expires_at"] < time.time():
        _spectator_tokens.pop(token, None)
        return None
    return info["session_id"]


@bp.route("/spectator/token/<token>", methods=["DELETE"])
def spectator_token_revoke(token: str):
    """Driver explicitly revokes a spectator token (e.g., session ended)."""
    existed = _spectator_tokens.pop(token, None) is not None
    return jsonify({"revoked": existed})

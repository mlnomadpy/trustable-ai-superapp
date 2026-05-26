"""
Shared VBO-replay primitives for the Pitwall simulator clients.

Hosts:
  • the file-loading shim (delegates to the production parser in
    `pitwall.features.session.vbo_parser`, so there is exactly one
    .vbo parser in the repo)
  • the `frame_to_payload` adapter that converts a production
    `TelemetryFrame` into the flat dict that the backend HTTP
    `/session/<id>/frame` endpoint expects
  • the `SSEListener` cue-stream consumer
  • the `replay_frames` loop that posts frames at native (or scaled)
    rate, invoking a per-frame `on_frame` callback for rendering

Both `simulator.py` (ANSI single-mode) and `pitwall_app.py` (Textual
TUI + ANSI fallback) build their UIs on top of this module so the
replay loop itself isn't duplicated.
"""
from __future__ import annotations

import json
import sys
import threading
import time
from pathlib import Path

# Make `pitwall.features.session.vbo_parser` importable when this
# package is run directly from a checkout (the repo's source layout
# puts everything under src/, and the simulators are launched as
# scripts, not through the installed `pitwall` distribution).
_THIS_DIR = Path(__file__).resolve().parent
_SRC_DIR = _THIS_DIR.parent
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from pitwall.features.session.vbo_parser import TelemetryFrame, parse_vbo  # noqa: E402


def load_frames(filepath) -> list[TelemetryFrame]:
    """Parse a .vbo file into a list of TelemetryFrame.

    Thin wrapper around `parse_vbo` that drops the metadata tuple —
    the simulator clients only care about the frame stream.
    """
    _meta, frames = parse_vbo(filepath)
    return frames


def frame_to_payload(f: TelemetryFrame) -> dict:
    """Convert a TelemetryFrame into the flat dict the backend's
    HTTP `/session/<id>/frame` endpoint expects.

    Kept as an explicit adapter (rather than `dataclasses.asdict`) so
    we don't accidentally leak production-only fields like `lap`,
    `corner_name`, or `avitime` onto the wire — those are computed
    server-side and clients shouldn't pre-fill them.
    """
    return {
        "timestamp": f.timestamp,
        "lat": f.lat,
        "lon": f.lon,
        "speed": f.speed,
        "heading": f.heading,
        "altitude": f.altitude,
        "g_lat": f.g_lat,
        "g_long": f.g_long,
        "combo_g": f.combo_g,
        "brake_pressure": f.brake_pressure,
        "brake_position": f.brake_position,
        "throttle": f.throttle,
        "steering": f.steering,
        "rpm": f.rpm,
        "coolant_temp": f.coolant_temp,
        "oil_temp": f.oil_temp,
        "fuel_level": f.fuel_level,
        "distance": f.distance,
    }


class SSEListener:
    """Background SSE consumer for `/api/cues/stream?session_id=…`.

    Pushes incoming cue payloads onto `self.cues` (newest-first,
    capped at 5). Optional `on_cue` callback fires per cue for
    push-driven UIs (e.g. Textual).
    """

    def __init__(self, backend_url: str, session_id: str, on_cue=None):
        self.url = f"{backend_url}/api/cues/stream?session_id={session_id}"
        self.cues: list[dict] = []
        self.on_cue = on_cue
        self._thread: threading.Thread | None = None
        self.running = False

    def start(self) -> None:
        self.running = True
        self._thread = threading.Thread(target=self._listen, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self.running = False

    def _listen(self) -> None:
        try:
            import requests
            import sseclient
            response = requests.get(
                self.url, stream=True, headers={"Accept": "text/event-stream"}
            )
            client = sseclient.SSEClient(response)
            for event in client.events():
                if not self.running:
                    break
                if event.event == "cue":
                    data = json.loads(event.data)
                    self.cues.insert(0, data)
                    if len(self.cues) > 5:
                        self.cues.pop()
                    if self.on_cue:
                        try:
                            self.on_cue(data)
                        except Exception:
                            pass
        except Exception:
            # Connection lost — surface as silent stop; callers can
            # inspect `self.running` if they care.
            pass


def replay_frames(
    frames: list[TelemetryFrame],
    speed_mult: float,
    on_frame,
    *,
    should_continue=None,
) -> int:
    """Walk a frame list at native (timestamp-delta / speed_mult) rate.

    Parameters
    ----------
    frames : list[TelemetryFrame]
        Parsed frames, ordered by timestamp.
    speed_mult : float
        Playback multiplier. 1.0 = realtime, 2.0 = 2x, 0 = as-fast-as-possible.
    on_frame : callable(i, frame) -> None
        Per-frame callback — typically posts to the backend + redraws UI.
    should_continue : callable() -> bool, optional
        Return False to abort the loop (used by Textual stop button).

    Returns the index of the last frame processed.
    """
    if not frames:
        return -1

    last_i = 0
    for i, f in enumerate(frames):
        if should_continue is not None and not should_continue():
            break
        on_frame(i, f)
        last_i = i

        if speed_mult > 0 and i < len(frames) - 1:
            dt = (frames[i + 1].timestamp - f.timestamp) / speed_mult
            if dt > 0:
                time.sleep(max(0.001, dt))
    return last_i

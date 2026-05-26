"""
Pitwall Terminal App — touchable TUI for laptop and Termux.
Acts as a standalone HTTP client connecting to the Flask backend.

Usage:
    python pitwall_app.py --replay session.vbo --backend http://127.0.0.1:5000
"""

import argparse
import sys
import time

try:
    import requests
except ImportError:
    print("Dependencies missing! Please install: pip install requests sseclient-py")
    sys.exit(1)

# Check for textual
try:
    from textual.app import App, ComposeResult
    from textual.widgets import Button, Static
    from textual.containers import Horizontal
    from textual import work
    HAS_TEXTUAL = True
except ImportError:
    HAS_TEXTUAL = False

from vbo_replay import SSEListener, frame_to_payload, load_frames


class BackendClient:
    """Handles HTTP communication with the Pitwall backend.

    Thin wrapper over `requests` + the shared `SSEListener`. Holds the
    session id, posts frames, and exposes the incoming-cue queue.
    """

    def __init__(self, backend_url, driver="sim-driver", track="Sonoma Raceway"):
        self.backend_url = backend_url
        self.driver = driver
        self.track = track
        self.session_id = None
        self._listener: SSEListener | None = None
        self.on_cue_received = None

    @property
    def cues(self) -> list:
        return self._listener.cues if self._listener else []

    @property
    def running(self) -> bool:
        return bool(self._listener and self._listener.running)

    def start_session(self):
        r = requests.post(f"{self.backend_url}/api/session/start", json={
            "driver": self.driver,
            "track": self.track,
            "note": "TUI Simulator Client"
        })
        r.raise_for_status()
        self.session_id = r.json().get("session_id")

        self._listener = SSEListener(
            self.backend_url,
            self.session_id,
            on_cue=lambda d: self.on_cue_received(d) if self.on_cue_received else None,
        )
        self._listener.start()
        return self.session_id

    def post_frame(self, frame_dict):
        if not self.session_id:
            return
        try:
            requests.post(f"{self.backend_url}/api/session/{self.session_id}/frame",
                          json=frame_dict, timeout=0.5)
        except requests.RequestException:
            pass  # silently drop if overloaded

    def stop_session(self):
        if self._listener:
            self._listener.stop()
        if self.session_id:
            try:
                requests.post(f"{self.backend_url}/api/session/{self.session_id}/end", timeout=2)
            except Exception:
                pass


def run_simple(args):
    """Simple terminal mode — no textual dependency."""
    print("Pitwall — Simple Terminal Mode (HTTP Client)")
    print("=" * 60)
    
    frames = load_frames(args.replay)
    if not frames:
        print("No frames parsed!")
        return

    client = BackendClient(args.backend, track="Simulator Track")
    sid = client.start_session()
    print(f"Session started: {sid}")

    try:
        for i, f in enumerate(frames):
            client.post_frame(frame_to_payload(f))
            
            speed_mph = f.speed * 2.237
            lines = []
            lines.append(f"Frame {i+1}/{len(frames)} | Speed {speed_mph:5.1f} mph | RPM {f.rpm:5.0f}")
            lines.append(f"G-Lat {f.g_lat:+5.2f}  G-Long {f.g_long:+5.2f}")
            
            if client.cues:
                for c in client.cues[:3]:
                    lines.append(f"  ♪ {c.get('layer')} Hz: {c.get('frequency', 0):.0f} | {c.get('reason', '')[:40]}")
            else:
                lines.append("  (no cues)")
                
            sys.stdout.write("\033[2J\033[H" + "\n".join(lines) + "\n")
            sys.stdout.flush()

            if args.speed > 0 and i < len(frames) - 1:
                dt = (frames[i + 1].timestamp - f.timestamp) / args.speed
                if dt > 0:
                    time.sleep(max(0.001, dt))
    except KeyboardInterrupt:
        pass
    finally:
        client.stop_session()


if HAS_TEXTUAL:
    class PitwallTUI(App):
        CSS = """
        Screen { background: #1a1a1a; }
        #header_bar { background: #d32f2f; color: white; height: 3; padding: 1; text-align: center; }
        #speed_display { color: white; text-style: bold; height: 3; padding: 0 2; }
        #telemetry { height: auto; padding: 0 2; color: #cccccc; }
        #cue_display { height: auto; min-height: 4; padding: 0 2; color: #ffd600; border-top: solid #333333; }
        #status_bar { height: 2; padding: 0 2; color: #888888; }
        .button-row { height: 5; align: center middle; }
        Button { margin: 0 1; min-width: 14; }
        Button.start { background: #2e7d32; }
        Button.stop { background: #c62828; }
        """

        BINDINGS = [
            ("q", "quit", "Quit"),
            ("s", "start_session", "Start"),
            ("x", "stop_session", "Stop"),
        ]

        def __init__(self, replay_path, backend_url, speed=1.0):
            super().__init__()
            self.replay_path = replay_path
            self.backend_url = backend_url
            self.speed = speed
            self.client = BackendClient(backend_url)
            self.frames = []
            self.playing = False

        def compose(self) -> ComposeResult:
            yield Static("🏁 PITWALL CLIENT", id="header_bar")
            yield Static("Speed: --- mph", id="speed_display")
            yield Static("Brake: --- | Throttle: --- | G: ---", id="telemetry")
            yield Static("(waiting for cues)", id="cue_display")
            with Horizontal(classes="button-row"):
                yield Button("▶ START", id="start", classes="start")
                yield Button("■ STOP", id="stop", classes="stop")
            yield Static("Ready", id="status_bar")

        def on_mount(self):
            if self.replay_path:
                self.frames = load_frames(self.replay_path)
                self.query_one("#status_bar").update(f"Loaded {len(self.frames)} frames")

        def on_button_pressed(self, event: Button.Pressed):
            if event.button.id == "start":
                self.action_start_session()
            elif event.button.id == "stop":
                self.action_stop_session()

        @work(thread=True)
        def action_start_session(self):
            if not self.frames:
                self.call_from_thread(self.notify, "No replay file loaded.")
                return
            if self.playing:
                return

            sid = self.client.start_session()
            self.playing = True
            
            def update_cues(_):
                cues = self.client.cues[:3]
                if cues:
                    text = "\\n".join(f"♪ {c.get('layer')}: {c.get('reason', '')[:50]}" for c in cues)
                else:
                    text = "(no cues)"
                self.call_from_thread(self.query_one("#cue_display").update, text)
            
            self.client.on_cue_received = update_cues

            for i, f in enumerate(self.frames):
                if not self.playing:
                    break

                self.client.post_frame(frame_to_payload(f))

                speed_mph = f.speed * 2.237
                self.call_from_thread(
                    self.query_one("#speed_display").update,
                    f"Speed: {speed_mph:.0f} mph  RPM: {f.rpm:.0f}"
                )
                self.call_from_thread(
                    self.query_one("#telemetry").update,
                    f"Brake: {f.brake_pressure:5.1f} bar  Throttle: {f.throttle:4.0f}%\\n"
                    f"G-Lat: {f.g_lat:+.2f}  G-Long: {f.g_long:+.2f}  Steer: {f.steering:+.0f}°"
                )
                self.call_from_thread(
                    self.query_one("#status_bar").update,
                    f"LIVE | Session {sid} | Frame {i+1}/{len(self.frames)}"
                )

                if self.speed > 0 and i < len(self.frames) - 1:
                    dt = (self.frames[i+1].timestamp - f.timestamp) / self.speed
                    if dt > 0:
                        time.sleep(max(0.001, dt))
            
            self.action_stop_session()

        def action_stop_session(self):
            self.playing = False
            self.client.stop_session()
            self.query_one("#status_bar").update("Stopped")
            self.notify("Session stopped")


def main():
    parser = argparse.ArgumentParser(description="Pitwall Terminal App (Client)")
    parser.add_argument("--replay", required=True, help="VBO file to replay")
    parser.add_argument("--backend", default="http://127.0.0.1:5000", help="Backend URL")
    parser.add_argument("--speed", type=float, default=1.0, help="Playback speed")
    parser.add_argument("--simple", action="store_true", help="Force simple mode")
    args = parser.parse_args()

    if args.simple or not HAS_TEXTUAL:
        run_simple(args)
    else:
        app = PitwallTUI(args.replay, args.backend, args.speed)
        app.run()


if __name__ == "__main__":
    main()

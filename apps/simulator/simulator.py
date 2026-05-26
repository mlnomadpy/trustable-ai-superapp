"""
Pitwall Simulator Client.
Standalone HTTP client that replays a VBO file, pushes telemetry to the
Pitwall backend API, and listens to the SSE stream for coaching cues.

Usage:
    python simulator.py session.vbo --backend http://127.0.0.1:5000 --speed 1
"""

import argparse
import sys
import time

import requests

from vbo_replay import SSEListener, frame_to_payload, load_frames

RED = "\033[91m"; GREEN = "\033[92m"; YELLOW = "\033[93m"
DIM = "\033[2m"; BOLD = "\033[1m"; RESET = "\033[0m"


def run(vbo_path, backend_url, speed_mult, driver, track_name):
    print(f"{BOLD}Starting Pitwall HTTP Simulator Client{RESET}")
    print(f"Backend: {backend_url}")
    print(f"Loading telemetry: {vbo_path}")

    frames = load_frames(vbo_path)
    if not frames:
        print("No data parsed!"); return
    print(f"  {len(frames)} frames loaded.\n")

    # 1. Init session
    try:
        r = requests.post(f"{backend_url}/session/start", json={
            "driver": driver,
            "track": track_name,
            "note": "Live simulation via HTTP client"
        })
        r.raise_for_status()
        session_id = r.json().get("session_id")
    except Exception as e:
        print(f"{RED}Failed to start session: {e}{RESET}")
        return

    print(f"{GREEN}Session created: {session_id}{RESET}")

    # 2. Start SSE listener
    listener = SSEListener(backend_url, session_id)
    listener.start()

    print(f"\nPlayback at {speed_mult}x. Ctrl+C to stop.\n")
    time.sleep(1)

    start_ts = frames[0].timestamp
    last_i = 0

    try:
        for i, f in enumerate(frames):
            elapsed = f.timestamp - start_ts

            # Post frame
            payload = frame_to_payload(f)
            try:
                requests.post(f"{backend_url}/session/{session_id}/frame", json=payload, timeout=0.5)
            except requests.RequestException:
                sys.stdout.write(f"\r{RED}Warning: Dropped frame {i} due to connection error.{RESET}          ")

            # Render minimal dashboard
            lines = []
            lines.append(f"{BOLD}Frame {i}/{len(frames)}{RESET} | Time: {elapsed:.1f}s")
            lines.append(f"Speed: {f.speed * 2.237:5.1f}mph | RPM: {f.rpm:5.0f} | G-Lat: {f.g_lat:+.2f}")
            lines.append(f"Brake: {f.brake_pressure:5.1f}bar | Throttle: {f.throttle:4.0f}%")
            lines.append(f"{'─'*50}")

            if listener.cues:
                for c in listener.cues[:3]:
                    lines.append(f"{YELLOW}♪ {c.get('layer', 'cue')}: {c.get('reason', '')[:50]}{RESET}")
            else:
                lines.append(f"{DIM}(waiting for cues...){RESET}")

            sys.stdout.write("\033[2J\033[H" + "\n".join(lines) + "\n")
            sys.stdout.flush()

            last_i = i
            if speed_mult > 0 and i < len(frames) - 1:
                dt = (frames[i+1].timestamp - f.timestamp) / speed_mult
                if dt > 0:
                    time.sleep(max(0.001, dt))

    except KeyboardInterrupt:
        print(f"\n\nStopped at frame {last_i+1}")
    finally:
        listener.stop()
        print(f"Ending session {session_id}...")
        try:
            requests.post(f"{backend_url}/session/{session_id}/end", timeout=2)
        except Exception:
            pass


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Pitwall HTTP Simulator Client")
    p.add_argument("vbo_file", help=".vbo file to replay")
    p.add_argument("--backend", default="http://127.0.0.1:5000", help="Backend API URL")
    p.add_argument("--speed", type=float, default=1.0, help="Playback speed")
    p.add_argument("--driver", default="sim-driver", help="Driver ID")
    p.add_argument("--track", default="Sonoma Raceway", help="Track name")
    a = p.parse_args()
    run(a.vbo_file, a.backend, a.speed, a.driver, a.track)

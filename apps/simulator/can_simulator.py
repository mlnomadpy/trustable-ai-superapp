#!/usr/bin/env python3
"""
can_simulator.py — emit pitwall CAN frames over a python-can Bus.

Two source modes:

  --vbo <path>     Replay a Racelogic VBO file as CAN frames at the file's
                   native sample rate (modulated by --speed). Encodes each
                   frame's 11 wide-table canonicals into PitwallMotion +
                   PitwallPosition + PitwallDistance + PitwallDriverInputs.

  --synthetic      Generate plausible Sonoma laps from scratch (handy when
                   no VBO is around). Same emit shape as VBO mode.

Plus optional sink-signal injection (default on) so we exercise the full
ADR-015 path:

  --inject-sink    Emit oil_temp_c, coolant_temp_c, clutch_pos_pct, tpms_*
                   on their own messages at realistic rates. Models a
                   warming oil temp curve, a 1 Hz TPMS, etc. Default ON.

Defaults to `interface=virtual, channel=pitwall_dev` so it talks to a
can_reader on the same channel. Flip to `--interface socketcan --channel
vcan0` for a Linux dev box, or `--interface slcan --channel /dev/ttyACM0`
to test against a real USB-CAN adapter in loopback.

    # Terminal A
    python3 tools/can_reader.py --session-id sim-001

    # Terminal B
    python3 tools/can_simulator.py --vbo path/to/sonoma.vbo --speed 2.0
"""
from __future__ import annotations

import argparse
import logging
import math
import sys
import time
from pathlib import Path
from typing import Iterable, Optional

import can
import cantools

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_DBC = ROOT / "data" / "dbc" / "pitwall.dbc"


def _vbo_frames(vbo_path: str):
    """Yield TelemetryFrame objects from a VBO file."""
    from vbo_replay import load_frames
    return load_frames(vbo_path)


def _synthetic_frames(n_laps: int = 3, fps: int = 10):
    """Generate ~3 synthetic laps of Sonoma-shaped data."""
    from types import SimpleNamespace
    track_len = 4258.0
    n_per_lap = 90 * fps
    base_t = 1000.0
    base_d = 0.0
    corner_distances = [56, 536, 668, 976, 1098, 1294, 1540, 1586, 1820, 2556, 4100]
    out = []
    for lap in range(n_laps):
        speed_factor = 1.0 + lap * 0.05
        for i in range(n_per_lap):
            d = (i / (n_per_lap - 1)) * track_len
            t = base_t + i / fps / speed_factor
            gaps = [(c - d) % track_len for c in corner_distances]
            ng = min(gaps)
            if ng < 80:
                t_in = 1 - (ng / 80)
                speed_kmh = (110 - 60 * t_in) * speed_factor
                brake = 30 * t_in if ng > 20 else 5 * t_in
                gl = 1.2 * t_in
                thr = 20 if ng < 30 else 60
            else:
                speed_kmh = 170 * speed_factor
                brake = 0
                gl = 0
                thr = 99
            prev_kmh = (out[-1].speed * 3.6) if out else speed_kmh
            g_long = (speed_kmh - prev_kmh) / 9.81 if out else 0
            out.append(SimpleNamespace(
                timestamp=t, distance=base_d + d,
                speed=speed_kmh / 3.6,
                g_lat=gl, g_long=g_long,
                combo_g=math.hypot(gl, g_long),
                brake_pressure=brake, throttle=thr,
                steering=gl * 30, rpm=2000 + (speed_kmh / 200) * 6500,
                lat=23.49 + d * 1e-7, lon=-73.78 + d * 1e-7,
            ))
        base_t = out[-1].timestamp + 1 / fps
        base_d += track_len
    return out


def _send(bus: can.BusABC, db: cantools.database.Database,
          msg_name: str, signals: dict, t: float):
    msg = db.get_message_by_name(msg_name)
    data = msg.encode(signals)
    bus.send(can.Message(
        arbitration_id=msg.frame_id, data=data, timestamp=t,
        is_extended_id=False,
    ))


def _emit_motion_block(bus, db, frame, t):
    _send(bus, db, "PitwallMotion", {
        "speed_ms": float(frame.speed),
        "g_lat": float(frame.g_lat),
        "g_long": float(frame.g_long),
        "combo_g": float(frame.combo_g),
    }, t)
    _send(bus, db, "PitwallPosition", {
        "lat": float(getattr(frame, "lat", 0.0)),
        "lon": float(getattr(frame, "lon", 0.0)),
    }, t)
    _send(bus, db, "PitwallDistance", {
        "distance_m": float(getattr(frame, "distance", 0.0)),
    }, t)
    _send(bus, db, "PitwallDriverInputs", {
        "throttle_pct": float(frame.throttle),
        "brake_bar": float(frame.brake_pressure),
        "steering_deg": float(frame.steering),
        "rpm": float(frame.rpm),
    }, t)


def _maybe_emit_sink(bus, db, t: float, t0: float, last_emit: dict):
    """Emit ADR-015 sink-only signals at their realistic rates."""
    elapsed = t - t0

    # Oil temp at 2 Hz, warms 85 → 105°C over the session
    if elapsed - last_emit.get("oil", -10) >= 0.5:
        oil_c = 85.0 + min(20.0, elapsed * 0.05)
        coolant_c = 82.0 + min(15.0, elapsed * 0.04)
        oil_kpa = 350 + (1500 if elapsed > 30 else 300) * 0.1
        fuel_pct = max(20.0, 100.0 - elapsed * 0.02)
        _send(bus, db, "PitwallPowertrain", {
            "oil_temp_c": oil_c, "coolant_temp_c": coolant_c,
            "oil_pressure_kpa": oil_kpa, "fuel_level_pct": fuel_pct,
        }, t)
        last_emit["oil"] = elapsed

    # Clutch + wheel speeds at 50 Hz (every frame in practice)
    if elapsed - last_emit.get("driveline", -10) >= 0.02:
        gear = max(1, min(6, int(2 + elapsed % 4)))
        clutch = 0.0
        _send(bus, db, "PitwallDriveline", {
            "gear": gear, "clutch_pos_pct": clutch,
            "wheel_speed_fl_kmh": 100.0, "wheel_speed_fr_kmh": 100.0,
        }, t)
        last_emit["driveline"] = elapsed

    # TPMS at 1 Hz
    if elapsed - last_emit.get("tpms", -10) >= 1.0:
        base = 230.0 + elapsed * 0.05
        _send(bus, db, "PitwallTpms", {
            "tpms_fl_kpa": base, "tpms_fr_kpa": base + 1.5,
            "tpms_rl_kpa": base + 0.5, "tpms_rr_kpa": base + 2.0,
        }, t)
        last_emit["tpms"] = elapsed


def play(
    frames: Iterable,
    *,
    interface: str = "virtual",
    channel: str = "pitwall_dev",
    bitrate: int = 1_000_000,
    dbc_paths: Optional[list[str]] = None,
    speed: float = 1.0,
    inject_sink: bool = True,
    log: Optional[logging.Logger] = None,
):
    """Play a sequence of frames out as CAN frames over a python-can bus."""
    log = log or logging.getLogger("pitwall.can_simulator")

    paths = dbc_paths or [str(DEFAULT_DBC)]
    db = cantools.database.load_file(paths[0])
    for extra in paths[1:]:
        db.add_dbc_file(extra)

    kwargs = {"interface": interface, "channel": channel}
    if interface in ("socketcan", "slcan", "pcan", "kvaser"):
        kwargs["bitrate"] = bitrate
    bus = can.Bus(**kwargs)
    log.info("simulator started (interface=%s channel=%s speed=%.2fx)",
             interface, channel, speed)

    frames_list = list(frames)
    if not frames_list:
        log.warning("no frames to play")
        return

    t0 = frames_list[0].timestamp
    wall0 = time.time()
    last_emit: dict = {}
    n = 0

    try:
        for frame in frames_list:
            elapsed_session = frame.timestamp - t0
            if speed > 0:
                target_wall = wall0 + elapsed_session / speed
                lag = target_wall - time.time()
                if lag > 0:
                    time.sleep(lag)
            _emit_motion_block(bus, db, frame, frame.timestamp)
            if inject_sink:
                _maybe_emit_sink(bus, db, frame.timestamp, t0, last_emit)
            n += 1
            if n % 1000 == 0:
                log.info("emitted %d frames", n)
    finally:
        try:
            bus.shutdown()
        except Exception:
            pass
        log.info("simulator finished — %d frames emitted", n)


def main():
    """CLI entry point — replay VBO or synthetic frames as CAN traffic."""
    p = argparse.ArgumentParser(description="pitwall CAN simulator")
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--vbo", help="path to a VBO file to replay")
    src.add_argument("--synthetic", action="store_true",
                     help="emit ~3 synthetic laps of Sonoma-shaped data")
    p.add_argument("--interface", default="virtual")
    p.add_argument("--channel", default="pitwall_dev")
    p.add_argument("--bitrate", type=int, default=1_000_000,
                   help="match the AiM MXP CAN2 output: 1 Mbit/s")
    p.add_argument("--dbc", action="append", default=None)
    p.add_argument("--speed", type=float, default=1.0,
                   help="playback speed multiplier (1.0 = real-time, "
                        "0 = as fast as possible, 5.0 = 5× realtime)")
    p.add_argument("--no-sink", action="store_true",
                   help="don't inject ADR-015 sink signals (oil temp, TPMS, …)")
    p.add_argument("--verbose", action="store_true")
    args = p.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    if args.vbo:
        frames = _vbo_frames(args.vbo)
    else:
        frames = _synthetic_frames()

    play(
        frames,
        interface=args.interface,
        channel=args.channel,
        bitrate=args.bitrate,
        dbc_paths=args.dbc,
        speed=args.speed,
        inject_sink=not args.no_sink,
    )


if __name__ == "__main__":
    main()

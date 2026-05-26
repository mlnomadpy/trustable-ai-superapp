#!/usr/bin/env python3
"""
aim_mxp_simulator.py — synthesize the AiM MXP CAN2 output indefinitely.

Generates realistic-looking telemetry frames matching the AiM MXP
SmartyCam Enhanced CAN v3.0 protocol (data/dbc/pitwall.dbc), so the
pitwall bridge + every downstream service can be exercised without a
real car plugged in.

What it emits

  Eight frames, in MXP-native units (mph, psi, °F, AiM sign convention
  including the vertical-accel inversion the PDF §6.2 calls out):

      0x420 SmartyCam01     10 Hz   rpm, speed_mph, gear, water_temp_f
      0x421 SmartyCam02     50 Hz   water_press, roll_rate, oil_filter_temp,
                                   oil_press
      0x422 SmartyCam03     50 Hz   brake_press_psi, pedal_pos, brake_switch,
                                   pitch_rate
      0x423 SmartyCam04     50 Hz   steer, yaw_rate, lateral_g, inline_g
      0x424 SmartyCam05     50 Hz   fuel_gal, battery_v, vertical_g
      0x450 AimExtended01   10 Hz   wheel speeds FL/FR/RL/RR
      0x451 AimExtended02   10 Hz   ecu_speed, ambient_temp, engine_oil_temp,
                                   dsc_reg
      0x452 AimExtended03   20 Hz   gps_lat, gps_lon

  The lap profile loops indefinitely. One lap = `lap_seconds`, two
  corners per lap. Speed sweeps idle → top → idle through each corner
  with braking, apex, and acceleration phases; longitudinal + lateral
  accel + steering + throttle/brake all derive from the same profile so
  they stay physically consistent.

Why MXP-native units

  The CarConfig pipeline on the *reader* side handles unit conversion
  (mph→m/s, psi→bar, °F→°C) and sign normalization (vertical-accel
  flip). The simulator therefore emits exactly what a real MXP would
  put on the bus, so end-to-end pipeline behavior matches production.

CLI

      python3 -m simulator.aim_mxp_simulator \\
          --interface virtual --channel pitwall_sim

  Pair with a CanReader on the same channel (or use
  `python -m pitwall --simulate` for one-process all-in-one).
"""
from __future__ import annotations

import argparse
import logging
import math
import signal
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import can
import cantools


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DBC = ROOT / "data" / "dbc" / "pitwall.dbc"


# ── lap profile ─────────────────────────────────────────────────────────

@dataclass
class LapProfile:
    """Generates synthetic engineering values at time `t` along a looping
    lap. Two corners per lap, smooth piecewise speed profile, derived
    inputs (g, steer, RPM, brake/throttle) follow physically.

    Output units are MXP-native (mph, psi, °F) and follow AiM sign
    conventions including the vertical-accel inversion the PDF §6.2
    documents — so the reader's CarConfig pipeline transforms exactly
    as it would on a real car.
    """
    lap_seconds: float = 60.0
    top_mph: float = 135.0
    idle_mph: float = 28.0
    top_rpm: float = 7800.0
    idle_rpm: float = 900.0
    cold_water_f: float = 75.0
    hot_water_f: float = 195.0
    cold_oil_f: float = 75.0
    hot_oil_f: float = 215.0
    ambient_f: float = 72.0
    fuel_start_gal: float = 14.0
    fuel_per_lap_gal: float = 0.12
    battery_v: float = 13.9
    # Anonymized Sonoma — same convention as can_simulator.py
    gps_lat0: float = 23.49
    gps_lon0: float = -73.78
    gps_extent_deg: float = 0.005

    def at(self, t: float) -> dict[str, float]:
        """Return all engineering values at session time `t` (seconds)."""
        lap_idx = int(t // self.lap_seconds)
        lap_t = t - lap_idx * self.lap_seconds
        lap_phase = lap_t / self.lap_seconds          # 0..1
        # Two corners per lap → fold into a half-lap phase
        half_phase = (lap_phase * 2.0) % 1.0          # 0..1 within each half
        in_first_half = lap_phase < 0.5

        # Phase regions:
        #   0.00–0.20 braking
        #   0.20–0.35 apex / steady through corner
        #   0.35–1.00 acceleration onto next straight
        if half_phase < 0.20:
            f = half_phase / 0.20
            speed_mph = self.top_mph - (self.top_mph - self.idle_mph) * f
            brake_pct = 75.0 * f
            throttle_pct = 0.0
            g_long = -1.0 * f                          # decel = negative inline
            g_lat = 0.4 * f                            # turning-in
            steer_factor = f
        elif half_phase < 0.35:
            f = (half_phase - 0.20) / 0.15
            apex_bump = math.sin(math.pi * f)
            speed_mph = self.idle_mph + (self.top_mph - self.idle_mph) * 0.05
            brake_pct = 15.0 * (1 - f)
            throttle_pct = 8.0 + 15.0 * f
            g_long = -0.2 + 0.4 * f
            g_lat = 1.3 * apex_bump                    # peak g at apex
            steer_factor = 1.0
        else:
            f = (half_phase - 0.35) / 0.65
            speed_mph = self.idle_mph + (self.top_mph - self.idle_mph) * f
            brake_pct = 0.0
            throttle_pct = 30.0 + 70.0 * f
            g_long = 0.7 * (1.0 - f * 0.5)
            g_lat = 1.0 * (1.0 - f)
            steer_factor = (1.0 - f)

        # Left- or right-handed alternating corners
        sign = 1.0 if in_first_half else -1.0
        g_lat *= sign
        steer_deg = sign * 75.0 * steer_factor

        # Tame the inline jitter at high speed
        g_long += 0.05 * math.sin(t * 7.0)
        g_lat += 0.03 * math.sin(t * 11.0 + 1.0)
        roll_rate_dps = 6.0 * math.sin(t * 4.0) * (abs(g_lat) > 0.3)
        pitch_rate_dps = 4.0 * math.sin(t * 3.5) * (abs(g_long) > 0.3)
        yaw_rate_dps = sign * 20.0 * steer_factor + 0.5 * math.sin(t * 5.0)

        # Vertical accel: AiM convention reads –1 g at rest (PDF §6.2
        # audit case). The CarConfig pipeline flips it back to +1 g.
        vertical_g = -1.0 + 0.06 * math.sin(t * 13.0)

        # RPM tracks speed; coarse single-speed-ratio for the synthetic case.
        rpm = self.idle_rpm + (self.top_rpm - self.idle_rpm) * (
            (speed_mph - self.idle_mph) / (self.top_mph - self.idle_mph)
        )
        rpm = max(self.idle_rpm, min(self.top_rpm, rpm))

        # Brake pressure in PSI: a fast brake event peaks ~600 psi
        brake_psi = brake_pct * 8.0

        # Temperatures warm up over the first few minutes then plateau
        # with a small oscillation; oil lags water slightly.
        warm_factor = 1.0 - math.exp(-t / 120.0)
        water_f = self.cold_water_f + (self.hot_water_f - self.cold_water_f) * warm_factor \
                  + 2.0 * math.sin(t * 0.15)
        oil_filter_f = self.cold_oil_f + (self.hot_oil_f - self.cold_oil_f) * warm_factor \
                       + 3.0 * math.sin(t * 0.10 + 0.5)
        engine_oil_f = oil_filter_f - 8.0 + 1.5 * math.sin(t * 0.07)

        # Pressures scale roughly with RPM
        rpm_norm = (rpm - self.idle_rpm) / (self.top_rpm - self.idle_rpm)
        oil_press_psi = 25.0 + 55.0 * rpm_norm + 2.0 * math.sin(t * 1.2)
        water_press_psi = 8.0 + 12.0 * rpm_norm + 1.5 * math.sin(t * 0.9)

        # Fuel slowly drops, never goes below 0.5 gal
        elapsed_laps = t / self.lap_seconds
        fuel_gal = max(0.5, self.fuel_start_gal - elapsed_laps * self.fuel_per_lap_gal)

        # GPS: a small ellipse around the anonymized start point. One
        # lap = one full orbit.
        gps_lat = self.gps_lat0 + self.gps_extent_deg * math.cos(
            2 * math.pi * lap_phase,
        )
        gps_lon = self.gps_lon0 + self.gps_extent_deg * math.sin(
            2 * math.pi * lap_phase,
        ) * 1.3       # ellipse aspect ratio

        # Wheel speeds: same as overall speed on the straight, small split
        # in corners (outside faster, inside slower).
        split = abs(g_lat) * 0.6  # mph of differential per g
        outside = speed_mph + split
        inside = max(0.0, speed_mph - split)
        if sign > 0:                                     # right-hand corner
            wheel_speeds = (outside, outside, outside, outside)  # placeholder before mapping
            wheel_speeds = (outside, inside, outside, inside)    # L=outside, R=inside
            # Correction: in a right-hander, LEFT wheels travel further
            # (outside), RIGHT wheels are inside → slower.
            wheel_speeds = (outside, inside, outside, inside)
        else:                                            # left-hand corner
            wheel_speeds = (inside, outside, inside, outside)
        # (FL, FR, RL, RR)

        return dict(
            # 0x420
            rpm=rpm,
            speed_mph=speed_mph,
            gear=0.0,                                    # PDF §9: always 0 on MSS54HP
            water_temp_f=water_f,
            # 0x421
            water_press_psi=water_press_psi,
            roll_rate_degs=roll_rate_dps,
            oil_filter_temp_f=oil_filter_f,              # DBC name is oil_temp_f
            oil_press_psi=oil_press_psi,
            # 0x422
            brake_press_psi=brake_psi,
            pedal_pos_pct=throttle_pct,                  # DBC: throttle_pos_pct
            brake_switch=1.0 if brake_pct > 5.0 else 0.0,
            pitch_rate_degs=pitch_rate_dps,
            # 0x423
            steer_angle_deg=steer_deg,
            yaw_rate_degs=yaw_rate_dps,
            lateral_accel_g=g_lat,
            inline_accel_g=g_long,
            # 0x424
            fuel_level_gal=fuel_gal,
            battery_volt=self.battery_v + 0.1 * math.sin(t * 0.3),
            vertical_accel_g=vertical_g,
            # 0x450
            wheel_speed_fl_mph=wheel_speeds[0],
            wheel_speed_fr_mph=wheel_speeds[1],
            wheel_speed_rl_mph=wheel_speeds[2],
            wheel_speed_rr_mph=wheel_speeds[3],
            # 0x451
            ecu_speed_mph=speed_mph,
            ambient_temp_f=self.ambient_f + 0.3 * math.sin(t * 0.05),
            engine_oil_temp_f=engine_oil_f,
            dsc_reg=1.0 if abs(g_lat) > 1.2 else 0.0,
            # 0x452
            gps_lat=gps_lat,
            gps_lon=gps_lon,
            # housekeeping
            _lap_idx=lap_idx,
            _lap_phase=lap_phase,
        )


# ── frame scheduler ─────────────────────────────────────────────────────

# Frame_id → (dbc message name, rate Hz, list of (signal_name, key_in_profile))
FRAME_PLAN = [
    (0x420, "SmartyCam01", 10.0, [
        ("rpm", "rpm"),
        ("speed_mph", "speed_mph"),
        ("gear", "gear"),
        ("water_temp_f", "water_temp_f"),
    ]),
    (0x421, "SmartyCam02", 50.0, [
        ("water_press_psi", "water_press_psi"),
        ("roll_rate_degs", "roll_rate_degs"),
        ("oil_temp_f", "oil_filter_temp_f"),       # DBC name vs PDF name
        ("oil_press_psi", "oil_press_psi"),
    ]),
    (0x422, "SmartyCam03", 50.0, [
        ("brake_press_psi", "brake_press_psi"),
        ("throttle_pos_pct", "pedal_pos_pct"),     # DBC name vs PDF name
        ("brake_switch", "brake_switch"),
        ("pitch_rate_degs", "pitch_rate_degs"),
    ]),
    (0x423, "SmartyCam04", 50.0, [
        ("steer_angle_deg", "steer_angle_deg"),
        ("yaw_rate_degs", "yaw_rate_degs"),
        ("lateral_accel_g", "lateral_accel_g"),
        ("inline_accel_g", "inline_accel_g"),
    ]),
    (0x424, "SmartyCam05", 50.0, [
        ("fuel_level_gal", "fuel_level_gal"),
        ("battery_volt", "battery_volt"),
        ("vertical_accel_g", "vertical_accel_g"),
    ]),
    (0x450, "AimExtended01", 10.0, [
        ("wheel_speed_fl_mph", "wheel_speed_fl_mph"),
        ("wheel_speed_fr_mph", "wheel_speed_fr_mph"),
        ("wheel_speed_rl_mph", "wheel_speed_rl_mph"),
        ("wheel_speed_rr_mph", "wheel_speed_rr_mph"),
    ]),
    (0x451, "AimExtended02", 10.0, [
        ("ecu_speed_mph", "ecu_speed_mph"),
        ("ambient_temp_f", "ambient_temp_f"),
        ("engine_oil_temp_f", "engine_oil_temp_f"),
        ("dsc_reg", "dsc_reg"),
    ]),
    (0x452, "AimExtended03", 20.0, [
        ("gps_lat", "gps_lat"),
        ("gps_lon", "gps_lon"),
    ]),
]


# ── simulator ───────────────────────────────────────────────────────────

class AimMxpSimulator:
    """Background CAN simulator emitting AiM MXP frames indefinitely.

    Mirrors `CanReader`'s lifecycle (start / stop / run_forever) so it
    can be embedded in the bridge process via `--simulate`.
    """

    def __init__(
        self,
        *,
        interface: str = "virtual",
        channel: str = "pitwall_sim",
        bitrate: int = 1_000_000,
        dbc_path: str | Path = DEFAULT_DBC,
        profile: Optional[LapProfile] = None,
        speed_x: float = 1.0,
        log: Optional[logging.Logger] = None,
    ):
        self.interface = interface
        self.channel = channel
        self.bitrate = bitrate
        self.speed_x = max(0.01, float(speed_x))
        self.profile = profile or LapProfile()
        self.log = log or logging.getLogger("pitwall.aim_mxp_sim")
        self._db = cantools.database.load_file(str(dbc_path))
        self._bus: Optional[can.BusABC] = None
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

        # Precompute per-frame period for the scheduler
        self._frames = []
        for frame_id, msg_name, hz, sig_map in FRAME_PLAN:
            self._frames.append({
                "id": frame_id,
                "msg": self._db.get_message_by_name(msg_name),
                "period": 1.0 / hz,
                "last_emit": -1e9,
                "sig_map": sig_map,
            })

    # ── lifecycle ─────────────────────────────────────────────────────

    def _open_bus(self):
        kwargs = {"interface": self.interface, "channel": self.channel}
        if self.interface in ("socketcan", "slcan", "pcan", "kvaser"):
            kwargs["bitrate"] = self.bitrate
        self._bus = can.Bus(**kwargs)

    def start(self):
        self._open_bus()
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._loop, name="pitwall-aim-mxp-sim", daemon=True,
        )
        self._thread.start()
        self.log.info(
            "aim_mxp simulator started (interface=%s channel=%s speed=%.2fx)",
            self.interface, self.channel, self.speed_x,
        )

    def stop(self, *, timeout: float = 2.0):
        self._stop.set()
        if self._bus is not None:
            try:
                self._bus.shutdown()
            except Exception:
                pass
        if self._thread is not None:
            self._thread.join(timeout=timeout)

    def run_forever(self):
        self.start()
        try:
            while not self._stop.is_set():
                time.sleep(0.5)
        except KeyboardInterrupt:
            self.log.info("interrupt — stopping")
        finally:
            self.stop()

    # ── scheduler loop ────────────────────────────────────────────────

    def _loop(self):
        assert self._bus is not None
        t0_wall = time.monotonic()
        # Sleep granularity sized to the fastest frame (50 Hz → 20 ms).
        # Use 5 ms ticks for jitter headroom.
        tick = 0.005
        n_emitted = 0
        next_log = time.monotonic() + 30.0
        while not self._stop.is_set():
            wall = time.monotonic() - t0_wall
            sim_t = wall * self.speed_x
            profile_vals = self.profile.at(sim_t)
            for fr in self._frames:
                if sim_t - fr["last_emit"] + 1e-9 >= fr["period"]:
                    signals = {
                        dbc_name: float(profile_vals[profile_key])
                        for dbc_name, profile_key in fr["sig_map"]
                    }
                    try:
                        data = fr["msg"].encode(signals, strict=False)
                    except Exception as e:
                        self.log.error(
                            "encode failed for 0x%X (%s): %s",
                            fr["id"], fr["msg"].name, e,
                        )
                        fr["last_emit"] = sim_t
                        continue
                    self._bus.send(can.Message(
                        arbitration_id=fr["id"], data=data,
                        is_extended_id=False, timestamp=time.time(),
                    ))
                    fr["last_emit"] = sim_t
                    n_emitted += 1
            # Periodic status line so the user can confirm the sim is alive
            now = time.monotonic()
            if now >= next_log:
                self.log.info(
                    "simulator alive: %d frames emitted, lap=%d phase=%.2f, "
                    "speed=%.1f mph, water=%.0f°F",
                    n_emitted, profile_vals["_lap_idx"],
                    profile_vals["_lap_phase"], profile_vals["speed_mph"],
                    profile_vals["water_temp_f"],
                )
                next_log = now + 30.0
            time.sleep(tick)


# ── CLI ────────────────────────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser(
        description="pitwall AiM MXP synthetic CAN simulator",
    )
    p.add_argument("--interface", default="virtual",
                   help="python-can interface (virtual, slcan, socketcan, ...)")
    p.add_argument("--channel", default="pitwall_sim",
                   help="python-can channel (e.g. pitwall_sim, /dev/ttyACM0, vcan0)")
    p.add_argument("--bitrate", type=int, default=1_000_000,
                   help="CAN bitrate; AiM MXP CAN2 is 1 Mbit/s")
    p.add_argument("--speed", type=float, default=1.0,
                   help="simulation speed multiplier (1.0 = real time)")
    p.add_argument("--lap-seconds", type=float, default=60.0,
                   help="duration of one synthetic lap in seconds")
    p.add_argument("--top-mph", type=float, default=135.0,
                   help="straight-line top speed in mph")
    p.add_argument("--idle-mph", type=float, default=28.0,
                   help="apex / corner-minimum speed in mph")
    p.add_argument("--verbose", action="store_true")
    args = p.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    profile = LapProfile(
        lap_seconds=args.lap_seconds,
        top_mph=args.top_mph,
        idle_mph=args.idle_mph,
    )
    sim = AimMxpSimulator(
        interface=args.interface, channel=args.channel,
        bitrate=args.bitrate, profile=profile, speed_x=args.speed,
    )
    # Clean SIGTERM handling so docker / systemd stops are graceful
    signal.signal(signal.SIGTERM, lambda *_: sim.stop())
    sim.run_forever()


if __name__ == "__main__":
    main()

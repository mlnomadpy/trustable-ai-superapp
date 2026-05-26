#!/usr/bin/env python3
"""
generate_sample_vbo.py — generates a synthetic Racelogic VBO file
simulating 3 laps of Sonoma Raceway (Turn 3-heavy data, BMW M3 spec).

Usage:
    python3 tools/generate_sample_vbo.py > session.vbo
    adb push session.vbo /sdcard/Download/
"""

import math
import random

# ── Sonoma track parameters (from architecture.md / stub track) ───────────────
SF_LAT = 38.1614
SF_LON = -122.4549
TRACK_LENGTH_M = 3765.0
LAP_TIME_S = 102.0        # intermediate driver, not gold standard

# Corner definitions: (distance_m, lat_delta, lon_delta, min_speed_ms, max_g)
CORNERS = [
    (150,   0.0008,  0.0004, 30.0, 0.8),   # T1
    (620,   0.0015,  0.0010, 22.0, 1.4),   # T3 — key braking zone
    (1250,  0.0030,  0.0020, 20.0, 1.6),   # T6
    (2150, -0.0010,  0.0040, 30.0, 1.1),   # T9
    (2560, -0.0020,  0.0050, 18.0, 1.7),   # T10 — tightest
    (2950, -0.0008,  0.0060, 25.0, 1.5),   # T11
]

DT = 0.1           # 10Hz
LAPS = 3
NOISE = 0.02       # ±2% sensor noise

def noise(val, scale=NOISE):
    """Apply uniform ±scale% sensor noise to a value."""
    return val * (1 + random.uniform(-scale, scale))

def lerp(a, b, t):
    """Linear interpolation from a toward b by factor t."""
    return a + (t - a) * b

def track_speed(dist_m):
    """Returns target speed in m/s based on position on track."""
    d = dist_m % TRACK_LENGTH_M
    base = 34.0  # ~122 km/h straight speed
    for (corner_d, *_, min_sp, _mg) in CORNERS:
        proximity = abs(d - corner_d)
        if proximity < 300:
            # Smooth deceleration into corner, acceleration out
            t = proximity / 300.0
            base = min(base, min_sp + (base - min_sp) * t)
    return base

def track_glat(dist_m, speed_ms):
    """Lateral G based on corner proximity and speed."""
    d = dist_m % TRACK_LENGTH_M
    max_g = 0.0
    for (corner_d, *_, min_sp, mg) in CORNERS:
        proximity = abs(d - corner_d)
        if proximity < 80:
            # Peak G at apex (~50m from nominal corner dist)
            apex_prox = abs(d - (corner_d + 30))
            g = mg * max(0, 1 - apex_prox / 80)
            max_g = max(max_g, g)
    return noise(max_g)

def track_glong(speed_ms, prev_speed_ms, dt):
    """Longitudinal G from speed change."""
    if dt <= 0:
        return 0.0
    delta = (speed_ms - prev_speed_ms) / dt
    g = delta / 9.81
    return noise(g)

def track_brake(dist_m, speed_ms):
    """Brake pressure in bar."""
    d = dist_m % TRACK_LENGTH_M
    for (corner_d, *_, min_sp, _mg) in CORNERS:
        if corner_d - 150 < d < corner_d - 10:
            # Braking zone: 10–60 bar
            brake_start = corner_d - 150
            t = 1 - (d - brake_start) / 140
            return noise(max(0, t * 50))
    return 0.0

def track_throttle(dist_m, speed_ms):
    """Throttle percentage."""
    d = dist_m % TRACK_LENGTH_M
    brake = track_brake(d, speed_ms)
    if brake > 2:
        return noise(0.0, 0)
    for (corner_d, *_, min_sp, _mg) in CORNERS:
        if corner_d + 10 < d < corner_d + 200:
            # Throttle build post-apex
            t = (d - (corner_d + 10)) / 190
            return noise(min(100, t * 90))
    return noise(85)   # on straight

def lat_lon_at(dist_m):
    """Very rough lat/lon along an oval approximation of Sonoma."""
    t = (dist_m % TRACK_LENGTH_M) / TRACK_LENGTH_M
    angle = t * 2 * math.pi
    # Ellipse approximating the track footprint
    lat = SF_LAT + 0.006 * math.sin(angle)
    lon = SF_LON + 0.010 * math.cos(angle)
    return round(lat, 6), round(lon, 6)

def main():
    """Generate a synthetic 3-lap VBO file and print to stdout."""
    lines = []

    # ── VBO header ────────────────────────────────────────────────────────────
    lines += [
        "[header]",
        "File Version,2",
        "Date,13/04/2026",
        "Comments,Pitwall synthetic session - Sonoma Raceway - BMW M3",
        "",
        "[channel names]",
        "time,satellites (raw),latitude,longitude,velocity kmh,heading,"
        "lateral-g,longitudinal-g,combined-g,distance,"
        "brake pressure,throttle pos,engine rpm,steering angle,coolant temp,oil temp",
        "",
        "[data]",
    ]

    t = 0.0
    dist = 0.0
    speed_ms = 10.0
    heading = 0.0
    total_frames = int(LAPS * LAP_TIME_S / DT)

    for frame in range(total_frames):
        target_speed = track_speed(dist)
        prev_speed = speed_ms
        # Smooth speed convergence
        speed_ms += (target_speed - speed_ms) * 0.15
        speed_ms = max(5.0, speed_ms)

        dist += speed_ms * DT
        speed_kmh = speed_ms * 3.6

        lat, lon = lat_lon_at(dist)

        # Heading follows the track angle
        t2 = ((dist % TRACK_LENGTH_M) / TRACK_LENGTH_M) * 2 * math.pi
        heading = math.degrees(t2) % 360

        g_lat = track_glat(dist, speed_ms)
        g_long = track_glong(speed_ms, prev_speed, DT)
        combo_g = math.sqrt(g_lat**2 + g_long**2)

        brake = track_brake(dist, speed_ms)
        throttle = track_throttle(dist, speed_ms)
        rpm = noise(speed_ms * 220 + 800, 0.05)   # rough rpm from speed
        steering = noise(g_lat * 45, 0.1)          # steering correlates with glat
        coolant = noise(88, 0.01)
        oil_temp = noise(92, 0.01)
        sats = 120                                  # good GPS lock

        row = (
            f"{t:.1f},{sats},"
            f"{lat:.6f},{lon:.6f},"
            f"{speed_kmh:.2f},{heading:.1f},"
            f"{g_lat:.3f},{g_long:.3f},{combo_g:.3f},"
            f"{dist:.1f},"
            f"{brake:.1f},{throttle:.1f},{rpm:.0f},{steering:.1f},"
            f"{coolant:.1f},{oil_temp:.1f}"
        )
        lines.append(row)
        t = round(t + DT, 1)

    print("\n".join(lines))

if __name__ == "__main__":
    random.seed(42)
    main()

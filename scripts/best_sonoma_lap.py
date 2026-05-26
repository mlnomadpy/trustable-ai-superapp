"""
Rank Sonoma VBO sessions by best lap time.

Detection method: project each frame's GPS position onto the line through
the start/finish point, perpendicular to `start_finish.heading`. A lap
crossing is a sign-change of the projected (signed) distance from positive
to negative (or vice-versa, depending on travel direction). Robust to the
fact that the dataset's S/F point is offset 30–40 m from the actual
crossing line.

Usage:
    python3 tools/best_sonoma_lap.py /path/to/vbo/dir
    python3 tools/best_sonoma_lap.py /path/to/vbo/dir --top 15
"""
from __future__ import annotations

import argparse
import json
import math
import os
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "simulator"))

from pitwall.features.session.vbo_parser import parse_vbo  # noqa: E402

EARTH_R = 6_371_000.0


def haversine_m(a_lat: float, a_lon: float, b_lat: float, b_lon: float) -> float:
    """Great-circle distance in metres between two GPS coordinates."""
    p1, p2 = math.radians(a_lat), math.radians(b_lat)
    dlat = math.radians(b_lat - a_lat)
    dlon = math.radians(b_lon - a_lon)
    h = math.sin(dlat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_R * math.asin(math.sqrt(h))


def latlon_to_local_xy(lat: float, lon: float, ref_lat: float, ref_lon: float) -> tuple[float, float]:
    """Equirectangular projection → metres in a local east-north frame."""
    dlat = math.radians(lat - ref_lat)
    dlon = math.radians(lon - ref_lon)
    x = EARTH_R * dlon * math.cos(math.radians(ref_lat))
    y = EARTH_R * dlat
    return x, y


def signed_perp_distance_to_sf_line(lat: float, lon: float,
                                     sf_lat: float, sf_lon: float,
                                     sf_heading_deg: float) -> float:
    """Signed perpendicular distance to the S/F line.

    The S/F line is perpendicular to the heading direction. Sign is
    positive when the frame is "ahead" of the S/F point along the heading,
    negative when "behind". Lap crossings are sign changes from negative
    → positive.
    """
    x, y = latlon_to_local_xy(lat, lon, sf_lat, sf_lon)
    h_rad = math.radians(sf_heading_deg)
    # Heading is measured from north, clockwise. Forward unit vector:
    fx = math.sin(h_rad)
    fy = math.cos(h_rad)
    return x * fx + y * fy


def detect_laps(frames, sf_lat: float, sf_lon: float, sf_heading_deg: float,
                near_radius_m: float = 80.0,
                cooldown_s: float = 30.0,
                min_lap_s: float = 60.0,
                max_lap_s: float = 300.0) -> list[float]:
    """Return list of lap times. Crossing fires when the signed perpendicular
    distance to the S/F line transitions from negative to positive AND the
    frame is within `near_radius_m` of the S/F point."""
    crossings: list[float] = []
    last_signed = None
    last_cross_t = None

    for f in frames:
        if not (f.lat or f.lon):
            continue
        d_to_sf = haversine_m(f.lat, f.lon, sf_lat, sf_lon)
        if d_to_sf > near_radius_m * 3:
            last_signed = None
            continue

        signed = signed_perp_distance_to_sf_line(f.lat, f.lon, sf_lat, sf_lon, sf_heading_deg)

        if last_signed is not None and last_signed < 0 <= signed and d_to_sf < near_radius_m:
            t = f.timestamp
            if last_cross_t is None or t - last_cross_t >= cooldown_s:
                crossings.append(t)
                last_cross_t = t

        last_signed = signed

    laps = []
    for a, b in zip(crossings[:-1], crossings[1:]):
        gap = b - a
        if min_lap_s <= gap <= max_lap_s:
            laps.append(gap)
    return laps


def session_centroid(frames) -> tuple[float, float]:
    """Return the median lat/lon of a frame list as a rough session location."""
    lats = [f.lat for f in frames if f.lat]
    lons = [f.lon for f in frames if f.lon]
    if not lats:
        return 0.0, 0.0
    return statistics.median(lats), statistics.median(lons)


def fmt_lap(s: float) -> str:
    """Format a lap time in seconds as M:SS.cc for display."""
    if not s or s != s:
        return "       —"
    m = int(s // 60)
    rest = s - 60 * m
    return f"{m:d}:{rest:05.2f}"


def main():
    """CLI entry point — rank VBO sessions by best Sonoma lap time."""
    ap = argparse.ArgumentParser()
    ap.add_argument("vbo_dir", help="Directory containing .vbo files")
    ap.add_argument("--track", default=str(ROOT / "data" / "tracks" / "sonoma.json"))
    ap.add_argument("--centroid-radius-km", type=float, default=10.0,
                    help="Session centroid must be within this many km of S/F to count as Sonoma")
    ap.add_argument("--top", type=int, default=20)
    ap.add_argument("--quiet", action="store_true",
                    help="Suppress per-file progress output")
    args = ap.parse_args()

    track = json.loads(Path(args.track).read_text())
    sf = track["start_finish"]
    sf_lat, sf_lon = float(sf["lat"]), float(sf["lon"])
    sf_heading = float(sf.get("heading", 0))
    track_name = track.get("name", "track")
    print(f"Track: {track_name}  S/F=({sf_lat:.5f}, {sf_lon:.5f})  heading={sf_heading:.1f}°  "
          f"expected length={track.get('track_length_m','?')}m")

    vbo_dir = Path(args.vbo_dir).expanduser()
    vbos = sorted(vbo_dir.glob("*.vbo"))
    print(f"Scanning {len(vbos)} VBO files in {vbo_dir}\n")

    rows = []
    for path in vbos:
        try:
            _, frames = parse_vbo(path)
        except Exception as e:
            if not args.quiet:
                print(f"  SKIP  {path.name}  parse error: {e}")
            continue
        if len(frames) < 50:
            continue
        c_lat, c_lon = session_centroid(frames)
        cdist_km = haversine_m(c_lat, c_lon, sf_lat, sf_lon) / 1000.0
        if cdist_km > args.centroid_radius_km:
            continue

        laps = detect_laps(frames, sf_lat, sf_lon, sf_heading)
        if not laps:
            continue
        rows.append({
            "file": path.name,
            "frames": len(frames),
            "duration_min": (frames[-1].timestamp - frames[0].timestamp) / 60.0,
            "centroid_km_from_sf": cdist_km,
            "n_laps": len(laps),
            "best_s": min(laps),
            "median_s": statistics.median(laps),
            "p25_s": sorted(laps)[max(0, len(laps) // 4)],
            "spread_s": (max(laps) - min(laps)) if len(laps) > 1 else 0.0,
            "max_speed_kmh": max(f.speed for f in frames) * 3.6,
            "max_brake_bar": max(f.brake_pressure for f in frames),
            "max_glat_g": max(abs(f.g_lat) for f in frames),
        })

    if not rows:
        print("No Sonoma sessions detected. Check --track and --centroid-radius-km.")
        return

    rows.sort(key=lambda r: r["best_s"])
    print(f"Found {len(rows)} Sonoma session(s) with detectable laps. Ranked by BEST LAP:\n")
    print(f"{'rank':>4}  {'file':<40} {'laps':>4}  {'best':>8}  {'p25':>8}  {'median':>8}  "
          f"{'spread':>6}  {'minutes':>7}  {'topkmh':>6}  {'maxbar':>6}  {'maxgL':>5}")
    print("  " + "─" * 132)
    for i, r in enumerate(rows[:args.top], 1):
        print(f"{i:>4}  {r['file']:<40} {r['n_laps']:>4}  "
              f"{fmt_lap(r['best_s']):>8}  {fmt_lap(r['p25_s']):>8}  {fmt_lap(r['median_s']):>8}  "
              f"{r['spread_s']:>5.1f}s  {r['duration_min']:>6.1f}m  "
              f"{r['max_speed_kmh']:>6.1f}  {r['max_brake_bar']:>6.1f}  {r['max_glat_g']:>5.2f}")

    print()
    winner = rows[0]
    print(f"BEST: {winner['file']}  best lap {fmt_lap(winner['best_s'])}  "
          f"({winner['n_laps']} laps, median {fmt_lap(winner['median_s'])}, "
          f"spread {winner['spread_s']:.1f}s)")
    print()
    print("Tip: a low BEST + low MEDIAN + low SPREAD is a clean fast session.")
    print("     A low BEST with high MEDIAN/SPREAD is one hot lap inside an inconsistent run.")


if __name__ == "__main__":
    main()

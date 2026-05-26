"""
Import the real Sonoma Raceway centerline from OpenStreetMap (Overpass API)
and emit `data/tracks/sonoma_real_gps.json`.

The output mirrors the structure of `data/tracks/sonoma.json` but uses
real-world GPS coordinates (~38.16°N) instead of the dataset's anonymised
~23.49°N coords. Maps every anonymised marker / corner reference point
to its real-world lat/lon by fractional position around the closed loop.

The dataset's anonymised track length (~4258 m) does not match real Sonoma
(~4060 m); the mapping preserves shape and relative position around the
loop, not absolute distance. That's good enough for marker pins on a map.

Usage:
    pip install requests
    python3 tools/import_sonoma_real_gps.py
    python3 tools/import_sonoma_real_gps.py --no-fetch     # use cached /tmp/sonoma_osm.json
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ANON_TRACK = ROOT / "data" / "tracks" / "sonoma.json"
REAL_TRACK = ROOT / "data" / "tracks" / "sonoma_real_gps.json"
CACHE = Path("/tmp/sonoma_osm.json")
EARTH_R = 6_371_000.0


def fetch_osm() -> dict:
    """Query Overpass API for the Sonoma Raceway centerline and cache the result."""
    import requests
    query = (
        '[out:json][timeout:25];'
        'way["highway"="raceway"]["name"="Sonoma Raceway"]'
        '(around:2000,38.1601,-122.4594);'
        'out geom;'
    )
    r = requests.post(
        "https://overpass-api.de/api/interpreter",
        data={"data": query}, timeout=30,
    )
    r.raise_for_status()
    data = r.json()
    CACHE.write_text(json.dumps(data))
    return data


def haversine_m(a, b):
    """Great-circle distance in metres between two (lat, lon) tuples."""
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    dlat = math.radians(b[0] - a[0])
    dlon = math.radians(b[1] - a[1])
    h = math.sin(dlat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_R * math.asin(math.sqrt(h))


def stitch_ways_into_loop(ways: list[dict]) -> list[tuple[float, float]]:
    """Chain raceway ways into a closed loop by matching endpoints.

    Each way is a polyline. The track is a closed loop, so when we chain
    correctly, the last point of one way meets the first point of the next
    (within ~1 m tolerance). Use a greedy nearest-endpoint walk.
    """
    # Drop auxiliary ways: anything < 30 nodes is likely a connector or
    # garage road, not the main loop. Keep only the longest contiguous set.
    polylines = []
    for w in ways:
        coords = [(p["lat"], p["lon"]) for p in w.get("geometry", [])]
        if len(coords) >= 5:
            polylines.append({
                "id": w["id"],
                "coords": coords,
                "length_m": sum(
                    haversine_m(coords[i], coords[i + 1])
                    for i in range(len(coords) - 1)
                ),
            })
    polylines.sort(key=lambda p: -p["length_m"])
    print(f"  {len(polylines)} ways ≥5 nodes")
    for p in polylines:
        print(f"    way {p['id']:>12}  {len(p['coords']):>3} nodes  {p['length_m']:>7.0f} m")

    if not polylines:
        return []

    # Start with the longest way; walk through the others matching endpoints
    used = {polylines[0]["id"]}
    loop = list(polylines[0]["coords"])
    while True:
        appended = False
        for cand in polylines:
            if cand["id"] in used:
                continue
            cs = cand["coords"]
            d_end_to_cs = haversine_m(loop[-1], cs[0])
            d_end_to_cs_rev = haversine_m(loop[-1], cs[-1])
            d_start_to_cs = haversine_m(loop[0], cs[-1])
            d_start_to_cs_rev = haversine_m(loop[0], cs[0])
            best = min(d_end_to_cs, d_end_to_cs_rev,
                       d_start_to_cs, d_start_to_cs_rev)
            if best > 5.0:
                continue
            if best == d_end_to_cs:
                loop.extend(cs[1:])
            elif best == d_end_to_cs_rev:
                loop.extend(reversed(cs[:-1]))
            elif best == d_start_to_cs:
                loop = list(cs[:-1]) + loop
            elif best == d_start_to_cs_rev:
                loop = list(reversed(cs[1:])) + loop
            used.add(cand["id"])
            appended = True
            break
        if not appended:
            break
    return loop


def resample_loop(loop: list[tuple[float, float]], step_m: float = 5.0) -> list[dict]:
    """Resample the closed loop at ~step_m intervals; emit (distance, lat, lon)."""
    if len(loop) < 2:
        return []
    # Cumulative distance
    cum = [0.0]
    for i in range(1, len(loop)):
        cum.append(cum[-1] + haversine_m(loop[i - 1], loop[i]))
    total = cum[-1]
    samples = []
    n_steps = max(2, int(total / step_m))
    for i in range(n_steps + 1):
        target = (i / n_steps) * total
        # Find segment containing `target`
        for j in range(1, len(cum)):
            if cum[j] >= target:
                segment_len = cum[j] - cum[j - 1]
                t = (target - cum[j - 1]) / segment_len if segment_len > 0 else 0
                lat = loop[j - 1][0] + t * (loop[j][0] - loop[j - 1][0])
                lon = loop[j - 1][1] + t * (loop[j][1] - loop[j - 1][1])
                samples.append({
                    "distance": round(target, 1),
                    "lat": round(lat, 6),
                    "lon": round(lon, 6),
                })
                break
    return samples


def map_fractional(real_samples: list[dict], anon_distance: float,
                   anon_total: float) -> tuple[float, float]:
    """Map an anonymised distance to a real lat/lon by fractional position.

    The anonymised track is anon_total m; this function returns the real-GPS
    lat/lon at the same fraction-around-the-loop. That preserves the shape
    correspondence between anonymised and real frames even though the
    absolute lengths differ slightly.
    """
    if not real_samples:
        return 0.0, 0.0
    real_total = real_samples[-1]["distance"]
    frac = (anon_distance % anon_total) / anon_total if anon_total else 0
    target = frac * real_total
    for j in range(1, len(real_samples)):
        if real_samples[j]["distance"] >= target:
            seg_len = real_samples[j]["distance"] - real_samples[j - 1]["distance"]
            t = (target - real_samples[j - 1]["distance"]) / seg_len if seg_len > 0 else 0
            lat = real_samples[j - 1]["lat"] + t * (
                real_samples[j]["lat"] - real_samples[j - 1]["lat"]
            )
            lon = real_samples[j - 1]["lon"] + t * (
                real_samples[j]["lon"] - real_samples[j - 1]["lon"]
            )
            return round(lat, 6), round(lon, 6)
    return real_samples[-1]["lat"], real_samples[-1]["lon"]


def main():
    """CLI entry point — import Sonoma centerline from OSM and map markers to real GPS."""
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-fetch", action="store_true",
                    help="Use cached /tmp/sonoma_osm.json instead of hitting Overpass")
    ap.add_argument("--step-m", type=float, default=5.0,
                    help="Resample step size for the centerline")
    args = ap.parse_args()

    if args.no_fetch and CACHE.exists():
        print(f"Using cached {CACHE}")
        osm = json.loads(CACHE.read_text())
    else:
        print("Fetching from Overpass API...")
        osm = fetch_osm()

    ways = osm.get("elements", [])
    print(f"OSM returned {len(ways)} ways")

    print("\nStitching into closed loop:")
    loop = stitch_ways_into_loop(ways)
    if not loop:
        print("ERROR: could not stitch a loop")
        return 2

    closure_gap_m = haversine_m(loop[0], loop[-1])
    total_m = sum(haversine_m(loop[i - 1], loop[i]) for i in range(1, len(loop)))
    print(f"\nLoop: {len(loop)} nodes, total {total_m:.0f} m, "
          f"closure gap {closure_gap_m:.1f} m")

    # Resample
    real_samples = resample_loop(loop, step_m=args.step_m)
    print(f"Resampled to {len(real_samples)} points at {args.step_m} m intervals")

    # Read anonymised track + map every marker / corner to real GPS
    anon = json.loads(ANON_TRACK.read_text())
    anon_total = anon.get("track_length_m", 0)
    print(f"\nAnonymised track length: {anon_total} m, real OSM loop: {total_m:.0f} m  "
          f"(scale {total_m/anon_total:.3f})")

    # Build the real-GPS track JSON
    real_corners = []
    for c in anon["corners"]:
        e_lat, e_lon = map_fractional(real_samples, c["entry"]["distance"], anon_total)
        a_lat, a_lon = map_fractional(real_samples, c["apex"]["distance"], anon_total)
        x_lat, x_lon = map_fractional(real_samples, c["exit"]["distance"], anon_total)
        real_corners.append({
            **c,
            "entry": {**c["entry"], "real_lat": e_lat, "real_lon": e_lon},
            "apex": {**c["apex"], "real_lat": a_lat, "real_lon": a_lon},
            "exit": {**c["exit"], "real_lat": x_lat, "real_lon": x_lon},
            "markers": [
                {**m,
                 "real_lat": map_fractional(real_samples, m["distance"], anon_total)[0],
                 "real_lon": map_fractional(real_samples, m["distance"], anon_total)[1]}
                for m in c.get("markers", [])
            ],
        })

    real_markers = [
        {**m,
         "real_lat": map_fractional(real_samples, m["distance"], anon_total)[0],
         "real_lon": map_fractional(real_samples, m["distance"], anon_total)[1]}
        for m in anon.get("markers", [])
    ]

    out = {
        "name": "Sonoma Raceway (real GPS)",
        "track_length_m": round(total_m, 1),
        "anon_track_length_m": anon_total,
        "scale_real_over_anon": round(total_m / anon_total, 4) if anon_total else 1.0,
        "source": "OpenStreetMap (Overpass API)",
        "fetched_at": "2026-04-28",
        "real_centerline": real_samples,
        "corners": real_corners,
        "markers": real_markers,
        "intel_notes": anon.get("intel_notes", {}),
        "note": (
            "All `real_lat` / `real_lon` fields are in real Sonoma GPS frame "
            "(~38.16°N, -122.45°W). Anonymised distance positions are mapped "
            "to real GPS by fractional position around the closed loop. "
            "Use this file for any map UI; use sonoma.json for analytics "
            "that need to match the dataset's anonymised coords."
        ),
    }

    REAL_TRACK.write_text(json.dumps(out, indent=2) + "\n")
    print(f"\nwrote {REAL_TRACK}")
    print(f"  {len(real_samples)} centerline points")
    print(f"  {len(real_corners)} corners with real_lat/real_lon")
    print(f"  {len(real_markers)} markers with real_lat/real_lon")

    # Sanity check — first few markers
    print("\nSample marker GPS (real Sonoma frame):")
    for m in real_markers[:5]:
        print(f"  {m['id']:<28} d={m['distance']:>6.1f}m  "
              f"real=({m['real_lat']:.5f}, {m['real_lon']:.5f})  -> {m['label']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

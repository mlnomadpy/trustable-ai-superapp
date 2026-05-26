"""
Track Builder — auto-generates track definitions from VBO telemetry data.

Usage:
    # Single file
    python track_builder.py /path/to/session.vbo -o sonoma.json

    # Multiple files (averages traces for better accuracy)
    python track_builder.py /path/to/data/*.vbo -o sonoma.json

    # Filter by track (auto-clusters by GPS, picks the most common)
    python track_builder.py /path/to/data/*.vbo -o sonoma.json --track auto
"""

import argparse
import json
import math
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path

from pitwall.features.session.vbo_parser import parse_vbo, TelemetryFrame


# ─── Data Structures ────────────────────────────────────────────────────────

@dataclass
class GeoPoint:
    """A GPS coordinate with optional distance and altitude."""
    lat: float
    lon: float
    distance: float = 0.0
    altitude: float = 0.0


@dataclass
class Corner:
    """Auto-detected corner with geometry, speed profiles, and brake data."""
    name: str
    number: int
    direction: str              # "left" or "right"
    severity: int               # 1 (hairpin) to 6 (flat out)
    entry: dict = field(default_factory=dict)
    apex: dict = field(default_factory=dict)
    exit: dict = field(default_factory=dict)
    curvature_peak: float = 0.0
    typical_speed_ms: dict = field(default_factory=dict)
    typical_brake_point: dict = field(default_factory=dict)
    elevation_change_m: float = 0.0


@dataclass
class Sector:
    """A track sector bounded by distance markers."""
    name: str
    start_distance: float
    end_distance: float


@dataclass
class TrackDefinition:
    """Complete auto-generated track definition ready for JSON serialisation."""
    name: str
    generated_from: list[str]
    track_length_m: float
    start_finish: dict
    corners: list[Corner]
    sectors: list[Sector]
    elevation_profile: list[dict]
    reference_line: list[dict]


# ─── Haversine ──────────────────────────────────────────────────────────────

def haversine(lat1, lon1, lat2, lon2):
    """Distance in meters between two GPS coordinates."""
    R = 6371000
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ─── Step 1: Filter Hot Laps ───────────────────────────────────────────────

def filter_hot_laps(frames: list[TelemetryFrame], min_speed_kmh=80, min_glat=0.5) -> list[TelemetryFrame]:
    """Keep only frames where the car is actually racing."""
    max_speed = max(f.speed * 3.6 for f in frames)
    max_glat = max(abs(f.g_lat) for f in frames)

    if max_speed < min_speed_kmh or max_glat < min_glat:
        return []  # not a hot lap session

    # Filter out pit/transit (speed < 30 km/h for extended periods)
    filtered = []
    slow_count = 0
    for f in frames:
        if f.speed * 3.6 < 20:
            slow_count += 1
            if slow_count > 50:  # 5 seconds at <20 km/h = pit stop
                continue
        else:
            slow_count = 0
            filtered.append(f)

    return filtered


# ─── Step 2: Compute Cumulative Distance ───────────────────────────────────

def compute_distances(frames: list[TelemetryFrame]) -> list[TelemetryFrame]:
    """Add cumulative distance to each frame."""
    if not frames:
        return frames

    frames[0].distance = 0.0
    for i in range(1, len(frames)):
        d = haversine(frames[i - 1].lat, frames[i - 1].lon, frames[i].lat, frames[i].lon)
        # Reject GPS jumps > 50m in one frame (100ms at 10Hz = max ~5m at 180 km/h)
        if d > 50:
            d = frames[i].speed * 0.1  # fallback: speed × dt
        frames[i].distance = frames[i - 1].distance + d

    return frames


# ─── Step 3: Detect Lap Boundaries ─────────────────────────────────────────

def detect_laps(frames: list[TelemetryFrame], sf_lat=None, sf_lon=None, threshold_m=30) -> list[list[TelemetryFrame]]:
    """Split frames into individual laps based on start/finish line crossing."""
    if not frames:
        return []

    # Try to get S/F from VBO laptiming section (most reliable)
    if sf_lat is None or sf_lon is None:
        # Auto-detect: find the point where the car is at max speed on the
        # longest straight. The S/F line is typically on the main straight.
        # Heuristic: median position of frames in the top 10% speed.
        speeds = [f.speed for f in frames]
        speed_threshold = sorted(speeds)[int(len(speeds) * 0.90)]
        fast_frames = [f for f in frames if f.speed >= speed_threshold]
        if fast_frames:
            sf_lat = sorted([f.lat for f in fast_frames])[len(fast_frames) // 2]
            sf_lon = sorted([f.lon for f in fast_frames])[len(fast_frames) // 2]
        else:
            sf_lat = frames[0].lat
            sf_lon = frames[0].lon

    laps = []
    current_lap = []
    was_near = True  # start near S/F
    min_lap_frames = 200  # at least 20 seconds at 10Hz
    cooldown = 0  # prevent double-triggers

    for f in frames:
        d = haversine(f.lat, f.lon, sf_lat, sf_lon)
        near = d < threshold_m

        if cooldown > 0:
            cooldown -= 1

        if near and not was_near and len(current_lap) > min_lap_frames and cooldown == 0:
            # Crossed S/F line — new lap
            laps.append(current_lap)
            current_lap = [f]
            cooldown = 50  # don't trigger again for 5 seconds
        else:
            current_lap.append(f)

        was_near = near

    if len(current_lap) > min_lap_frames:
        laps.append(current_lap)

    return laps


# ─── Step 4: Distance-Normalize a Lap ─────────────────────────────────────

def distance_normalize(lap: list[TelemetryFrame], resolution_m=2.0) -> list[dict]:
    """Resample a lap to fixed distance intervals. Returns list of dicts."""
    if not lap:
        return []

    compute_distances(lap)
    total_dist = lap[-1].distance

    if total_dist < 100:
        return []

    normalized = []
    frame_idx = 0

    for d in range(0, int(total_dist), int(resolution_m)):
        # Find the frame closest to this distance
        while frame_idx < len(lap) - 1 and lap[frame_idx + 1].distance < d:
            frame_idx += 1

        f = lap[frame_idx]
        normalized.append({
            "distance": float(d),
            "lat": f.lat,
            "lon": f.lon,
            "speed": f.speed,
            "heading": f.heading,
            "altitude": f.altitude,
            "g_lat": f.g_lat,
            "g_long": f.g_long,
            "combo_g": f.combo_g,
            "brake_pressure": f.brake_pressure,
            "throttle": f.throttle,
            "steering": f.steering,
        })

    return normalized


# ─── Step 5: Average Multiple Laps ────────────────────────────────────────

def average_laps(normalized_laps: list[list[dict]]) -> list[dict]:
    """Average distance-normalized laps to reduce GPS noise."""
    if not normalized_laps:
        return []

    # Use the shortest lap as the reference length
    min_len = min(len(lap) for lap in normalized_laps)

    averaged = []
    for i in range(min_len):
        samples = [lap[i] for lap in normalized_laps if i < len(lap)]
        n = len(samples)
        if n == 0:
            continue

        avg = {
            "distance": samples[0]["distance"],
            "lat": sum(s["lat"] for s in samples) / n,
            "lon": sum(s["lon"] for s in samples) / n,
            "speed": sum(s["speed"] for s in samples) / n,
            "heading": _circular_mean([s["heading"] for s in samples]),
            "altitude": sum(s["altitude"] for s in samples) / n,
            "g_lat": sum(s["g_lat"] for s in samples) / n,
            "g_long": sum(s["g_long"] for s in samples) / n,
            "combo_g": sum(s["combo_g"] for s in samples) / n,
            "brake_pressure": sum(s["brake_pressure"] for s in samples) / n,
            "throttle": sum(s["throttle"] for s in samples) / n,
            "steering": sum(s["steering"] for s in samples) / n,
        }
        averaged.append(avg)

    return averaged


def _circular_mean(angles_deg: list[float]) -> float:
    """Mean of angles, handling the 0/360 wraparound."""
    sin_sum = sum(math.sin(math.radians(a)) for a in angles_deg)
    cos_sum = sum(math.cos(math.radians(a)) for a in angles_deg)
    return math.degrees(math.atan2(sin_sum, cos_sum)) % 360


# ─── Step 6: Compute Curvature ─────────────────────────────────────────────

def compute_curvature(trace: list[dict], smooth_window=10) -> list[float]:
    """
    Compute curvature at each point: d(heading) / d(distance).
    Smoothed with a Gaussian-like moving average.
    """
    n = len(trace)
    raw_curvature = [0.0] * n

    for i in range(1, n):
        dh = trace[i]["heading"] - trace[i - 1]["heading"]
        # Handle 0/360 wrap
        if dh > 180:
            dh -= 360
        elif dh < -180:
            dh += 360

        dd = trace[i]["distance"] - trace[i - 1]["distance"]
        if dd > 0:
            raw_curvature[i] = dh / dd  # deg/m
        else:
            raw_curvature[i] = raw_curvature[i - 1]

    # Smooth with moving average
    smoothed = [0.0] * n
    for i in range(n):
        start = max(0, i - smooth_window)
        end = min(n, i + smooth_window + 1)
        window = raw_curvature[start:end]
        smoothed[i] = sum(window) / len(window)

    return smoothed


# ─── Step 7: Detect Corners ────────────────────────────────────────────────

def detect_corners(trace: list[dict], curvature: list[float], min_corner_length_m=20) -> list[Corner]:
    """Find corners from curvature data."""
    n = len(curvature)
    abs_curv = [abs(c) for c in curvature]

    # Adaptive threshold: 70th percentile of absolute curvature
    sorted_curv = sorted(abs_curv)
    threshold = sorted_curv[int(n * 0.70)]
    threshold = max(threshold, 0.3)  # minimum threshold to avoid noise

    # Find contiguous regions above threshold
    corners = []
    in_corner = False
    start_idx = 0

    for i in range(n):
        if abs_curv[i] > threshold and not in_corner:
            in_corner = True
            start_idx = i
        elif abs_curv[i] <= threshold and in_corner:
            in_corner = False
            end_idx = i

            # Check minimum corner length
            corner_length = trace[end_idx]["distance"] - trace[start_idx]["distance"]
            if corner_length < min_corner_length_m:
                continue

            # Find apex (peak curvature within the corner)
            apex_idx = start_idx + max(
                range(end_idx - start_idx),
                key=lambda j: abs_curv[start_idx + j]
            )

            # Direction from curvature sign
            direction = "right" if curvature[apex_idx] > 0 else "left"

            # Severity from peak curvature (1=tightest, 6=fastest)
            peak = abs_curv[apex_idx]
            if peak > 3.0:
                severity = 1  # hairpin
            elif peak > 2.0:
                severity = 2
            elif peak > 1.2:
                severity = 3
            elif peak > 0.7:
                severity = 4
            elif peak > 0.4:
                severity = 5
            else:
                severity = 6  # barely a corner

            # Typical speeds at entry/apex/exit
            entry_speed = trace[start_idx]["speed"]
            apex_speed = trace[apex_idx]["speed"]
            exit_speed = trace[min(end_idx, n - 1)]["speed"]

            # Brake point: search backward from entry for brake_pressure rise
            brake_dist = 0
            brake_bar = 0
            # Find peak brake pressure in the 200m before corner entry
            search_start = max(0, start_idx - 100)  # ~200m at 2m resolution
            brake_region = [(j, trace[j]["brake_pressure"]) for j in range(search_start, start_idx)]
            if brake_region:
                peak_j, peak_bar = max(brake_region, key=lambda x: x[1])
                if peak_bar > 3:  # meaningful braking
                    brake_bar = peak_bar
                    # Find where braking started (first frame > 3 bar working backward from peak)
                    for j in range(peak_j, search_start, -1):
                        if trace[j]["brake_pressure"] < 3:
                            brake_dist = trace[start_idx]["distance"] - trace[j]["distance"]
                            break
                    else:
                        brake_dist = trace[start_idx]["distance"] - trace[search_start]["distance"]

            # Elevation change
            elev_change = trace[min(end_idx, n - 1)]["altitude"] - trace[start_idx]["altitude"]

            corner_num = len(corners) + 1
            corners.append(Corner(
                name=f"Turn {corner_num}",
                number=corner_num,
                direction=direction,
                severity=severity,
                entry={
                    "distance": trace[start_idx]["distance"],
                    "lat": trace[start_idx]["lat"],
                    "lon": trace[start_idx]["lon"],
                },
                apex={
                    "distance": trace[apex_idx]["distance"],
                    "lat": trace[apex_idx]["lat"],
                    "lon": trace[apex_idx]["lon"],
                },
                exit={
                    "distance": trace[min(end_idx, n - 1)]["distance"],
                    "lat": trace[min(end_idx, n - 1)]["lat"],
                    "lon": trace[min(end_idx, n - 1)]["lon"],
                },
                curvature_peak=peak,
                typical_speed_ms={
                    "entry": round(entry_speed, 1),
                    "apex": round(apex_speed, 1),
                    "exit": round(exit_speed, 1),
                },
                typical_brake_point={
                    "distance_before_entry": round(brake_dist, 1),
                    "pressure_bar": round(brake_bar, 1),
                },
                elevation_change_m=round(elev_change, 1),
            ))

    return corners


# ─── Step 8: Generate Sectors ──────────────────────────────────────────────

def generate_sectors(trace: list[dict], curvature: list[float], n_sectors=3) -> list[Sector]:
    """Split the track into sectors at the longest straights."""
    abs_curv = [abs(c) for c in curvature]

    # Find straights: contiguous regions of low curvature
    straights = []
    in_straight = False
    start_idx = 0

    for i in range(len(abs_curv)):
        if abs_curv[i] < 0.2 and not in_straight:
            in_straight = True
            start_idx = i
        elif abs_curv[i] >= 0.2 and in_straight:
            in_straight = False
            length = trace[i]["distance"] - trace[start_idx]["distance"]
            mid_idx = (start_idx + i) // 2
            straights.append((length, trace[mid_idx]["distance"]))

    # Sort by length, take top n_sectors-1 as sector boundaries
    straights.sort(reverse=True)
    boundaries = sorted([s[1] for s in straights[:n_sectors - 1]])

    track_length = trace[-1]["distance"]
    sectors = []
    prev = 0
    for i, b in enumerate(boundaries):
        sectors.append(Sector(f"Sector {i + 1}", round(prev, 1), round(b, 1)))
        prev = b
    sectors.append(Sector(f"Sector {len(boundaries) + 1}", round(prev, 1), round(track_length, 1)))

    return sectors


# ─── Step 9: Build Elevation Profile ──────────────────────────────────────

def build_elevation_profile(trace: list[dict], resolution_m=10) -> list[dict]:
    """Subsample the elevation at regular intervals."""
    profile = []
    for i in range(0, len(trace), max(1, int(resolution_m / 2))):
        profile.append({
            "distance": round(trace[i]["distance"], 1),
            "altitude": round(trace[i]["altitude"], 1),
        })
    return profile


# ─── Step 10: Build Reference Line ────────────────────────────────────────

def build_reference_line(trace: list[dict], resolution_m=5) -> list[dict]:
    """Subsample the GPS trace for the racing line reference."""
    line = []
    for i in range(0, len(trace), max(1, int(resolution_m / 2))):
        line.append({
            "distance": round(trace[i]["distance"], 1),
            "lat": round(trace[i]["lat"], 6),
            "lon": round(trace[i]["lon"], 6),
        })
    return line


# ─── Main Pipeline ─────────────────────────────────────────────────────────

def build_track(vbo_paths: list[str], track_name: str = "Auto-Generated Track") -> TrackDefinition:
    """Full pipeline: VBO files → TrackDefinition."""

    all_normalized_laps = []
    source_files = []

    for path in vbo_paths:
        print(f"  Parsing {Path(path).name}...")
        meta, frames = parse_vbo(path)
        if not frames:
            print(f"    Skipped: no data")
            continue

        # Filter to hot laps only
        hot = filter_hot_laps(frames)
        if not hot:
            print(f"    Skipped: not hot laps (max gLat {max(abs(f.g_lat) for f in frames):.2f}G)")
            continue

        # Compute distances
        compute_distances(hot)

        # Detect individual laps
        laps = detect_laps(hot)
        print(f"    Found {len(laps)} laps ({len(hot)} hot frames)")

        if not laps:
            # No clear lap boundaries — use the whole session as one "lap"
            laps = [hot]

        # Distance-normalize each lap, filtering outliers
        lap_distances = []
        for lap in laps:
            compute_distances(lap)
            if lap:
                lap_distances.append(lap[-1].distance)

        if lap_distances:
            # Use median lap distance as reference, reject laps > ±20% off
            median_dist = sorted(lap_distances)[len(lap_distances) // 2]
            for lap_idx, lap in enumerate(laps):
                if not lap:
                    continue
                lap_dist = lap[-1].distance
                if median_dist > 0 and abs(lap_dist - median_dist) / median_dist > 0.20:
                    print(f"      Lap {lap_idx + 1}: {lap_dist:.0f}m — skipped (outlier vs median {median_dist:.0f}m)")
                    continue
                normed = distance_normalize(lap)
                if normed and len(normed) > 100:
                    all_normalized_laps.append(normed)

        source_files.append(Path(path).name)

    if not all_normalized_laps:
        print("ERROR: No usable laps found in any file!")
        sys.exit(1)

    print(f"\nAveraging {len(all_normalized_laps)} laps from {len(source_files)} files...")
    averaged = average_laps(all_normalized_laps)
    track_length = averaged[-1]["distance"] if averaged else 0

    print(f"Track length: {track_length:.0f}m")

    # Compute curvature
    curvature = compute_curvature(averaged)

    # Detect corners
    corners = detect_corners(averaged, curvature)
    print(f"Detected {len(corners)} corners:")
    for c in corners:
        print(f"  {c.name}: {c.direction} severity {c.severity} "
              f"at {c.entry['distance']:.0f}m "
              f"(apex {c.typical_speed_ms.get('apex', 0):.0f} m/s, "
              f"brake {c.typical_brake_point.get('distance_before_entry', 0):.0f}m before)")

    # Generate sectors
    sectors = generate_sectors(averaged, curvature)
    print(f"\nSectors:")
    for s in sectors:
        print(f"  {s.name}: {s.start_distance:.0f}m – {s.end_distance:.0f}m "
              f"({s.end_distance - s.start_distance:.0f}m)")

    # Elevation profile
    elevation = build_elevation_profile(averaged)
    elev_range = max(e["altitude"] for e in elevation) - min(e["altitude"] for e in elevation)
    print(f"\nElevation range: {elev_range:.1f}m")

    # Reference line
    ref_line = build_reference_line(averaged)

    # Start/finish from first point
    sf = averaged[0] if averaged else {"lat": 0, "lon": 0, "heading": 0}

    track = TrackDefinition(
        name=track_name,
        generated_from=source_files,
        track_length_m=round(track_length, 1),
        start_finish={
            "lat": round(sf["lat"], 6),
            "lon": round(sf["lon"], 6),
            "heading": round(sf.get("heading", 0), 1),
        },
        corners=corners,
        sectors=sectors,
        elevation_profile=elevation,
        reference_line=ref_line,
    )

    return track


# ─── Serialization ─────────────────────────────────────────────────────────

def track_to_json(track: TrackDefinition) -> dict:
    """Convert TrackDefinition to JSON-serializable dict."""
    d = {
        "name": track.name,
        "generated_from": track.generated_from,
        "track_length_m": track.track_length_m,
        "start_finish": track.start_finish,
        "corners": [asdict(c) for c in track.corners],
        "sectors": [asdict(s) for s in track.sectors],
        "elevation_profile": track.elevation_profile,
        "reference_line": track.reference_line,
    }
    return d


# ─── CLI ───────────────────────────────────────────────────────────────────

def main():
    """CLI entry point — parse VBO files and generate a track definition JSON."""
    parser = argparse.ArgumentParser(description="Build track definition from VBO files")
    parser.add_argument("vbo_files", nargs="+", help="One or more .vbo files")
    parser.add_argument("-o", "--output", default="track.json", help="Output JSON file")
    parser.add_argument("-n", "--name", default="Auto-Generated Track", help="Track name")
    args = parser.parse_args()

    print(f"Track Builder — processing {len(args.vbo_files)} file(s)")
    print(f"{'=' * 60}\n")

    track = build_track(args.vbo_files, track_name=args.name)
    track_dict = track_to_json(track)

    with open(args.output, "w") as f:
        json.dump(track_dict, f, indent=2)

    print(f"\n{'=' * 60}")
    print(f"Track definition saved to {args.output}")
    print(f"  {len(track.corners)} corners")
    print(f"  {len(track.sectors)} sectors")
    print(f"  {len(track.reference_line)} reference line points")
    print(f"  {len(track.elevation_profile)} elevation profile points")
    print(f"  Track length: {track.track_length_m:.0f}m")


if __name__ == "__main__":
    main()

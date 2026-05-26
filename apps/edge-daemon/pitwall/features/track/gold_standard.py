"""
Gold-standard lap extractor for Sonoma.

Per ADR-014, the Gold Standard is a per-corner reference profile of the
fastest verified Sonoma lap available. It freezes once and is read by
the corner grader, time-loss decomposition, highlight finder, and the
LLM post-session prompt.

Two artifacts:
    data/reference/sonoma_gold.json       — per-corner aggregate
    data/reference/sonoma_gold_trace.json — full per-frame trace

The 1:47.5 BMW M3 lap from `forza/data/Sonoma Intermediate - 1_47.5.vbo`
is the current canonical source. Replace with AJ's pro lap when available.
"""
from __future__ import annotations

import json
import math
import statistics
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

from pitwall.features.track.track_loader import load_track, CornerDef
from pitwall.features.session.vbo_parser import parse_vbo


# ─── Data shapes ──────────────────────────────────────────────────────────────


@dataclass
class GoldCornerPass:
    """Per-corner aggregate from the gold lap."""
    corner: str
    entry_speed_kmh: float
    apex_speed_kmh: float
    exit_speed_kmh: float
    min_speed_kmh: float
    peak_brake_bar: float
    brake_point_m: Optional[float]          # distance before entry where brake first > 5 bar
    brake_release_m: Optional[float]        # distance into corner where brake first < 2 bar
    trail_brake_bar_at_apex: float
    throttle_at_exit_pct: float
    max_g_lat: float
    max_combo_g: float
    corner_time_s: float
    apex_distance_m: float
    entry_distance_m: float
    exit_distance_m: float


@dataclass
class GoldStandard:
    """Full gold reference for one lap."""
    track: str
    source_file: str
    lap_time_s: float
    total_distance_m: float
    corners: dict[str, GoldCornerPass]
    n_frames: int


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _find_lap_time(frames) -> tuple[float, int, int]:
    """Find the fastest single lap by S/F crossing detection.

    Returns (lap_time_s, start_idx, end_idx). Falls back to the whole
    file as one "lap" if no clear S/F crossings can be detected.
    """
    if len(frames) < 100:
        return frames[-1].timestamp - frames[0].timestamp, 0, len(frames) - 1

    distances = [f.distance for f in frames]
    total = distances[-1]
    if total < 4000:
        return frames[-1].timestamp - frames[0].timestamp, 0, len(frames) - 1

    # Detect approximate lap boundaries by scanning for distance % track_length
    # local minima. This is a rough heuristic — replaces the broken
    # tools/best_sonoma_lap.py for now.
    track_len = 4258
    boundaries = [0]
    last_b = 0
    for i, d in enumerate(distances):
        if d - distances[last_b] >= track_len * 0.95 and i - last_b > 50:
            boundaries.append(i)
            last_b = i
    boundaries.append(len(frames) - 1)

    best_dt = float("inf")
    best_pair = (0, len(frames) - 1)
    for a, b in zip(boundaries[:-1], boundaries[1:]):
        dt = frames[b].timestamp - frames[a].timestamp
        if 60 < dt < 240 and dt < best_dt:
            best_dt = dt
            best_pair = (a, b)

    if best_dt == float("inf"):
        return frames[-1].timestamp - frames[0].timestamp, 0, len(frames) - 1
    return best_dt, best_pair[0], best_pair[1]


def _frames_in_corner(frames, corner: CornerDef, lap_distances=None):
    """Yield frame indices whose track-distance lies within this corner."""
    out = []
    for i, f in enumerate(frames):
        d = (lap_distances[i] if lap_distances else f.distance) % 4258
        if corner.entry_distance <= d <= corner.exit_distance:
            out.append(i)
    return out


def _frames_before_entry(frames, corner: CornerDef, lookback_m: float = 200,
                         lap_distances=None):
    """Frames in the brake-zone window leading into the corner."""
    start_dist = corner.entry_distance - lookback_m
    out = []
    for i, f in enumerate(frames):
        d = (lap_distances[i] if lap_distances else f.distance) % 4258
        if start_dist <= d < corner.entry_distance:
            out.append(i)
    return out


def _aggregate_corner_pass(frames, corner: CornerDef, lap_distances=None) -> Optional[GoldCornerPass]:
    """Compute per-corner aggregates from frames in this corner."""
    in_corner = _frames_in_corner(frames, corner, lap_distances)
    pre_entry = _frames_before_entry(frames, corner, 200, lap_distances)

    if not in_corner:
        return None

    entry_idx = in_corner[0]
    exit_idx = in_corner[-1]
    apex_dist = corner.apex_distance
    apex_idx = min(in_corner, key=lambda i: abs(
        (lap_distances[i] if lap_distances else frames[i].distance) % 4258 - apex_dist
    ))

    speeds_in = [frames[i].speed * 3.6 for i in in_corner]
    brakes_in = [frames[i].brake_pressure for i in in_corner]
    glats_in = [abs(frames[i].g_lat) for i in in_corner]
    combos_in = [frames[i].combo_g for i in in_corner]

    # Brake point: first frame in pre-entry where brake > 5 bar
    brake_point_m: Optional[float] = None
    for i in pre_entry:
        if frames[i].brake_pressure > 5:
            d = (lap_distances[i] if lap_distances else frames[i].distance) % 4258
            brake_point_m = corner.entry_distance - d
            break

    # Brake release: first frame in-corner where brake < 2 bar
    brake_release_m: Optional[float] = None
    for i in in_corner:
        if frames[i].brake_pressure < 2:
            d = (lap_distances[i] if lap_distances else frames[i].distance) % 4258
            brake_release_m = d - corner.entry_distance
            break

    return GoldCornerPass(
        corner=corner.name,
        entry_speed_kmh=frames[entry_idx].speed * 3.6,
        apex_speed_kmh=frames[apex_idx].speed * 3.6,
        exit_speed_kmh=frames[exit_idx].speed * 3.6,
        min_speed_kmh=min(speeds_in) if speeds_in else 0,
        peak_brake_bar=max(brakes_in) if brakes_in else 0,
        brake_point_m=brake_point_m,
        brake_release_m=brake_release_m,
        trail_brake_bar_at_apex=frames[apex_idx].brake_pressure,
        throttle_at_exit_pct=frames[exit_idx].throttle,
        max_g_lat=max(glats_in) if glats_in else 0,
        max_combo_g=max(combos_in) if combos_in else 0,
        corner_time_s=frames[exit_idx].timestamp - frames[entry_idx].timestamp,
        apex_distance_m=corner.apex_distance,
        entry_distance_m=corner.entry_distance,
        exit_distance_m=corner.exit_distance,
    )


# ─── Public API ───────────────────────────────────────────────────────────────


def _segment_passes(frames, track_len: float):
    """Yield (lap_index, frame_index_list) for each contiguous run of frames
    where cumulative distance progresses by approximately one track-length.

    Robust to pit-stops (distance flatlines): a run ends when distance
    progresses by >= 95 % of track_len since its start, or when distance
    stops growing for >5 s (lap aborted).
    """
    if not frames or track_len <= 0:
        return

    runs = []
    start = 0
    last_progress_t = frames[0].timestamp
    for i in range(1, len(frames)):
        prev = frames[i - 1]
        cur = frames[i]
        progress = cur.distance - frames[start].distance
        if progress >= track_len * 0.95:
            runs.append((start, i))
            start = i
            last_progress_t = cur.timestamp
            continue
        if cur.distance - prev.distance < 0.5:
            if cur.timestamp - last_progress_t > 5:
                # Aborted run — re-start from here
                start = i
                last_progress_t = cur.timestamp
        else:
            last_progress_t = cur.timestamp
    if start < len(frames) - 1:
        runs.append((start, len(frames) - 1))

    for idx, (a, b) in enumerate(runs):
        yield idx, list(range(a, b + 1))


def _frames_in_corner_abs(frames, corner: CornerDef, track_len: float, idxs: list[int]):
    """Indices among `idxs` whose track-distance lies inside this corner."""
    out = []
    for i in idxs:
        d = frames[i].distance % track_len if track_len else frames[i].distance
        if corner.entry_distance <= d <= corner.exit_distance:
            out.append(i)
    return out


def _frames_before_entry_abs(frames, corner: CornerDef, track_len: float,
                              idxs: list[int], lookback_m: float = 200):
    out = []
    start_d = corner.entry_distance - lookback_m
    for i in idxs:
        d = frames[i].distance % track_len if track_len else frames[i].distance
        if start_d <= d < corner.entry_distance:
            out.append(i)
    return out


def _aggregate_corner_pass_abs(frames, corner: CornerDef,
                                track_len: float, in_idxs: list[int],
                                pre_idxs: list[int]) -> Optional[GoldCornerPass]:
    if not in_idxs:
        return None
    in_frames = [frames[i] for i in in_idxs]
    speeds = [f.speed * 3.6 for f in in_frames]
    brakes = [f.brake_pressure for f in in_frames]
    glats = [abs(f.g_lat) for f in in_frames]
    combos = [f.combo_g for f in in_frames]

    apex_d = corner.apex_distance
    apex_local = min(range(len(in_frames)),
                     key=lambda j: abs((in_frames[j].distance % track_len) - apex_d))

    brake_point_m: Optional[float] = None
    for i in pre_idxs:
        if frames[i].brake_pressure > 5:
            d = frames[i].distance % track_len
            brake_point_m = corner.entry_distance - d
            break

    brake_release_m: Optional[float] = None
    for f in in_frames:
        if f.brake_pressure < 2:
            d = f.distance % track_len
            brake_release_m = d - corner.entry_distance
            break

    return GoldCornerPass(
        corner=corner.name,
        entry_speed_kmh=in_frames[0].speed * 3.6,
        apex_speed_kmh=in_frames[apex_local].speed * 3.6,
        exit_speed_kmh=in_frames[-1].speed * 3.6,
        min_speed_kmh=min(speeds) if speeds else 0,
        peak_brake_bar=max(brakes) if brakes else 0,
        brake_point_m=brake_point_m,
        brake_release_m=brake_release_m,
        trail_brake_bar_at_apex=in_frames[apex_local].brake_pressure,
        throttle_at_exit_pct=in_frames[-1].throttle,
        max_g_lat=max(glats) if glats else 0,
        max_combo_g=max(combos) if combos else 0,
        corner_time_s=in_frames[-1].timestamp - in_frames[0].timestamp,
        apex_distance_m=corner.apex_distance,
        entry_distance_m=corner.entry_distance,
        exit_distance_m=corner.exit_distance,
    )


def extract_gold_from_vbo(vbo_path: str, track_json_path: str) -> tuple[GoldStandard, list]:
    """Parse a VBO, segment into laps, aggregate the BEST pass per corner
    across all laps. Robust to the dataset's anonymised GPS — works
    entirely in cumulative-distance space.

    Returns (GoldStandard, frame_trace_list_of_best_lap).
    """
    track = load_track(track_json_path)
    _, frames = parse_vbo(vbo_path)
    if not frames:
        raise RuntimeError(f"no frames in {vbo_path}")

    track_len = track.track_length
    runs = list(_segment_passes(frames, track_len))

    # Best pass per corner — minimum corner_time_s across all laps
    best_per_corner: dict[str, GoldCornerPass] = {}
    fastest_run: Optional[tuple[int, list[int], float]] = None     # (idx, idxs, lap_time)

    for run_idx, idxs in runs:
        if len(idxs) < 50:
            continue
        run_lap_time = frames[idxs[-1]].timestamp - frames[idxs[0]].timestamp
        if 60 < run_lap_time < 300 and (fastest_run is None
                                         or run_lap_time < fastest_run[2]):
            fastest_run = (run_idx, idxs, run_lap_time)

        # Per-corner aggregation for this run
        for c in track.corners:
            in_idxs = _frames_in_corner_abs(frames, c, track_len, idxs)
            pre_idxs = _frames_before_entry_abs(frames, c, track_len, idxs)
            if len(in_idxs) < 3:
                continue
            agg = _aggregate_corner_pass_abs(frames, c, track_len, in_idxs, pre_idxs)
            if agg is None:
                continue
            prior = best_per_corner.get(c.name)
            # Best = fastest pass that ALSO actually slowed at the apex.
            # Filter out drive-throughs where the driver never properly hit
            # the apex (typical when frames cover multiple laps' worth and
            # the segmentation picks a partial). Heuristic:
            #   - require the pass to span >= 80 % of the corner geometry
            #   - require min_speed < 0.95 × entry_speed (some braking)
            corner_span = c.exit_distance - c.entry_distance
            actual_span = agg.exit_distance_m - agg.entry_distance_m
            spans_ok = (in_idxs[-1] - in_idxs[0] + 1) >= max(5, int(corner_span / 8))
            slowed = agg.min_speed_kmh < agg.entry_speed_kmh * 0.97
            valid_pass = spans_ok and (slowed or agg.peak_brake_bar > 5)

            if not valid_pass:
                continue

            # Score: lower min_speed (more disciplined slowdown) is better,
            # tie-broken by higher exit speed (better drive-out).
            agg_score = (-agg.min_speed_kmh, agg.exit_speed_kmh)
            prior_score = ((-prior.min_speed_kmh, prior.exit_speed_kmh)
                           if prior else (-1e9, -1e9))
            if agg_score > prior_score:
                best_per_corner[c.name] = agg

    # Lap time for the gold standard: prefer the actual fastest detected lap;
    # fall back to the sum of best-per-corner times scaled up for inter-corner
    # straights.
    if fastest_run is not None:
        gold_lap_s = fastest_run[2]
        trace_idxs = fastest_run[1]
    else:
        gold_lap_s = sum(p.corner_time_s for p in best_per_corner.values()) * 1.5
        trace_idxs = list(range(min(len(frames), 1000)))

    base_t = frames[trace_idxs[0]].timestamp
    base_d = frames[trace_idxs[0]].distance
    trace = [
        {
            "t":     round(frames[i].timestamp - base_t, 3),
            "d":     round(frames[i].distance - base_d, 1),
            "v":     round(frames[i].speed * 3.6, 2),
            "brk":   round(frames[i].brake_pressure, 2),
            "thr":   round(frames[i].throttle, 1),
            "gLat":  round(frames[i].g_lat, 3),
            "gLong": round(frames[i].g_long, 3),
        }
        for i in trace_idxs
    ]

    gold = GoldStandard(
        track=track.name,
        source_file=Path(vbo_path).name,
        lap_time_s=round(gold_lap_s, 3),
        total_distance_m=track_len,
        corners=best_per_corner,
        n_frames=len(trace_idxs),
    )
    return gold, trace


def gold_to_dict(gold: GoldStandard) -> dict:
    """JSON-serializable form."""
    return {
        "track":            gold.track,
        "source_file":      gold.source_file,
        "lap_time_s":       round(gold.lap_time_s, 3),
        "total_distance_m": round(gold.total_distance_m, 1),
        "n_frames":         gold.n_frames,
        "corners":          {name: asdict(p) for name, p in gold.corners.items()},
    }


def load_gold_standard(path: str) -> GoldStandard:
    """Read a frozen sonoma_gold.json back into typed form."""
    data = json.loads(Path(path).read_text())
    corners = {
        name: GoldCornerPass(**pass_dict)
        for name, pass_dict in data["corners"].items()
    }
    return GoldStandard(
        track=data["track"],
        source_file=data["source_file"],
        lap_time_s=data["lap_time_s"],
        total_distance_m=data["total_distance_m"],
        corners=corners,
        n_frames=data["n_frames"],
    )


__all__ = [
    "GoldCornerPass", "GoldStandard",
    "extract_gold_from_vbo", "gold_to_dict", "load_gold_standard",
]

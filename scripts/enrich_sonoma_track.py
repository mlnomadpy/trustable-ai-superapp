"""
Enrich data/tracks/sonoma.json with named markers and per-corner Bentley tips
from docs/sonoma_track_intelligence.md.

Idempotent: re-running overwrites the `markers` and `coaching_tip` fields with
the canonical content here, leaves everything else untouched. Writes a `.bak`
beside the original before mutating.

Usage:
    python3 scripts/enrich_sonoma_track.py            # enrich the canonical copy
    python3 scripts/enrich_sonoma_track.py --dry-run  # show diff, do not write
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CANONICAL = ROOT / "data" / "tracks" / "sonoma.json"


# Per-corner enrichment.
#
# `nicknames`        : informal names a coach might use ("the Carousel", "Calamity Corner")
# `coaching_tip`     : one-line cue grounded in Ross Bentley's Sonoma session
#                      and Kanga Motorsports notes — short enough for TTS
# `markers`          : list of named reference points the driver actually uses,
#                      typed by `kind` so coach_engine can pick the right one
#                      for the current driving phase. `at_offset_m_from_entry`
#                      is positive when the marker is BEFORE the corner entry
#                      (brake refs), zero at entry, negative after (apex/exit).
#
# Sources are documented per-entry so this can be audited against the intel doc.
ENRICHMENT: dict[str, dict] = {
    "Turn 1": {
        "nicknames": [],
        "coaching_tip": "carry throttle through, swing tight to the K-wall bend",
        "markers": [
            {"id": "T1_kwall_bend",  "kind": "apex_ref",  "label": "the K-wall bend",
             "at_offset_m_from_entry": -10, "source": "kanga"},
        ],
    },
    "Turn 2": {
        "nicknames": [],
        "coaching_tip": "you can brake less than you think; carry speed uphill",
        "markers": [
            {"id": "T2_bridge",          "kind": "brake_ref", "label": "the bridge",
             "at_offset_m_from_entry": 60, "source": "kanga"},
            {"id": "T2_pavement_cracks", "kind": "brake_ref", "label": "the pavement cracks",
             "at_offset_m_from_entry": 30, "source": "kanga", "note": "alt to bridge"},
        ],
    },
    "Turn 3": {
        "nicknames": [],
        "coaching_tip": "give-away corner — sacrifice T3 entry to win T3a and T4",
        "markers": [
            {"id": "T3_right_curbing", "kind": "apex_ref", "label": "the right-hand curbing",
             "at_offset_m_from_entry": 0, "source": "kanga"},
            {"id": "T3_light_poles",   "kind": "visual",  "label": "the light poles in the stands",
             "at_offset_m_from_entry": 60, "source": "kanga"},
        ],
    },
    "Turn 4": {
        "nicknames": [],
        "coaching_tip": "downhill, off-camber — back the brake up by one marker",
        "markers": [
            {"id": "T4_left_wall_step", "kind": "brake_ref", "label": "where the left wall steps up",
             "at_offset_m_from_entry": 40, "source": "kanga"},
        ],
    },
    "Turn 5": {
        "nicknames": [],
        "coaching_tip": "throwaway corner — preserve T6 entry, breathe the throttle",
        "markers": [],
    },
    "Turn 6": {
        "nicknames": ["the Carousel"],
        "coaching_tip": "smooth exit — speed here carries the long straight; no early throttle",
        "markers": [
            {"id": "T6_crest",         "kind": "brake_ref", "label": "just after the slight crest",
             "at_offset_m_from_entry": 30, "source": "kanga"},
            {"id": "T6_tires_left",    "kind": "brake_ref", "label": "the tire stacks on the left",
             "at_offset_m_from_entry": 50, "source": "kanga"},
            {"id": "T6_corner_station","kind": "visual",    "label": "the corner station on the right",
             "at_offset_m_from_entry": 0,  "source": "kanga"},
        ],
    },
    "Turn 7": {
        "nicknames": [],
        "coaching_tip": "eyes up — late turn-in, late apex; second apex matters more",
        "markers": [
            {"id": "T7_300_board", "kind": "brake_ref", "label": "the 300 board",
             "at_offset_m_from_entry": 80, "source": "blayze"},
        ],
    },
    "Turn 8": {
        "nicknames": ["the Esses"],
        "coaching_tip": "smooth, don't pinch — apexes all slightly late, throttle on exit",
        "markers": [],
    },
    "Turn 9": {
        "nicknames": [],
        "coaching_tip": "setup for T10 — exit T8a at full throttle",
        "markers": [],
    },
    "Turn 10": {
        "nicknames": [],
        "coaching_tip": "lift, don't brake — fastest corner; carry full throttle past apex",
        "markers": [
            {"id": "T10_toyota_sign", "kind": "visual",    "label": "the Toyota sign letters",
             "at_offset_m_from_entry": 0,  "source": "kanga"},
            {"id": "T10_left_berm",   "kind": "apex_ref",  "label": "the left berm",
             "at_offset_m_from_entry": -10, "source": "kanga"},
        ],
    },
    "Turn 11": {
        "nicknames": ["Calamity Corner", "the hairpin"],
        "coaching_tip": "wait for the bump to settle, trail to the apex, all the road on exit",
        "markers": [
            {"id": "T11_bump",         "kind": "brake_ref", "label": "the bump where the road widens left",
             "at_offset_m_from_entry": 100, "source": "blayze",
             "note": "best brake reference — wait for the car to compress and settle"},
            {"id": "T11_pit_entry",    "kind": "brake_ref", "label": "the pit-entry lines on the left",
             "at_offset_m_from_entry": 70, "source": "kanga", "note": "alt to bump"},
            {"id": "T11_tire_stack_3", "kind": "apex_ref",  "label": "the third tire stack",
             "at_offset_m_from_entry": -20, "source": "blayze"},
            {"id": "T11_tire_stacks_turnin", "kind": "turn_in_ref",
             "label": "the start of the tire stacks on the left",
             "at_offset_m_from_entry": 0, "source": "blayze"},
        ],
    },
}


# Track-wide nuggets that aren't per-corner.
TRACK_NOTES = {
    "elevation_change_m": 49,
    "real_centroid_lat": 38.1601,
    "real_centroid_lon": -122.4594,
    "real_finish_line_lat": 38.16152,
    "real_finish_line_lon": -122.45472,
    "weather_pattern": "morning fog burns off mid-morning; cool damp surface in first session of an HPDE day",
    "common_strategy_notes": [
        "T3 is a give-away — sacrifice T3 to win T3a and T4",
        "T5 is throwaway — preserve T6 entry",
        "T6 carousel punishes early throttle (off-camber + downhill)",
        "T10 is fastest — most drivers brake when they only need a lift",
        "T11 has no painted brake marker — use the bump in the road",
    ],
    "intel_source": "docs/sonoma_track_intelligence.md (compiled 2026-04-28)",
}


def _sample_reference_line(reference_line: list, distance_m: float) -> tuple[float, float]:
    """Linear-interp lat/lon at this track-distance from the reference_line trace.
    Returns (0.0, 0.0) if the trace is empty."""
    if not reference_line:
        return 0.0, 0.0
    track_len = max(p["distance"] for p in reference_line)
    d = distance_m % track_len if track_len else distance_m
    # Find the two surrounding samples
    for i in range(len(reference_line) - 1):
        a = reference_line[i]
        b = reference_line[i + 1]
        if a["distance"] <= d <= b["distance"]:
            span = b["distance"] - a["distance"]
            t = (d - a["distance"]) / span if span > 0 else 0
            return (
                round(a["lat"] + t * (b["lat"] - a["lat"]), 6),
                round(a["lon"] + t * (b["lon"] - a["lon"]), 6),
            )
    last = reference_line[-1]
    return last["lat"], last["lon"]


def enrich(track: dict) -> dict:
    """Apply the canonical enrichment to an in-memory track dict."""
    track["intel_notes"] = TRACK_NOTES

    reference_line = track.get("reference_line", [])

    for corner in track.get("corners", []):
        name = corner.get("name", "")
        e = ENRICHMENT.get(name)
        if not e:
            continue

        # Compute concrete distance along the track for each marker by
        # combining its offset-from-entry with the corner's entry_distance.
        entry_d = corner.get("entry", {}).get("distance", 0)
        track_len = track.get("track_length_m", 0)

        materialised_markers = []
        for m in e["markers"]:
            dist = entry_d - m["at_offset_m_from_entry"]
            if track_len:
                dist = dist % track_len
            lat, lon = _sample_reference_line(reference_line, dist)
            materialised_markers.append({
                **m,
                "distance": round(dist, 1),
                "lat": lat,
                "lon": lon,
                "corner": name,
            })

        corner["nicknames"] = e["nicknames"]
        corner["coaching_tip"] = e["coaching_tip"]
        corner["markers"] = materialised_markers

    # Also surface a flat top-level markers array so consumers can do a single
    # nearest-search without iterating corners.
    flat = []
    for corner in track.get("corners", []):
        for m in corner.get("markers", []):
            flat.append(m)
    flat.sort(key=lambda m: m["distance"])
    track["markers"] = flat

    return track


def write_pretty(path: Path, data: dict):
    """Write a JSON dict to disk with indent-2 formatting."""
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def main():
    """CLI entry point — enrich sonoma.json with markers and coaching tips."""
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true",
                    help="Print summary without writing anything")
    args = ap.parse_args()

    if not CANONICAL.exists():
        print(f"ERROR: canonical track JSON not found at {CANONICAL}")
        return 2

    track = json.loads(CANONICAL.read_text())
    enrich(track)

    n_corners = len(track.get("corners", []))
    n_corners_with_tip = sum(1 for c in track["corners"] if c.get("coaching_tip"))
    n_markers = len(track.get("markers", []))
    n_corners_with_markers = sum(1 for c in track["corners"] if c.get("markers"))

    print(f"Enriched track={track.get('name','?')}")
    print(f"  corners        : {n_corners}")
    print(f"  with coaching  : {n_corners_with_tip}")
    print(f"  with markers   : {n_corners_with_markers}")
    print(f"  total markers  : {n_markers}")
    print()
    print("By kind:")
    by_kind: dict[str, int] = {}
    for m in track["markers"]:
        by_kind[m["kind"]] = by_kind.get(m["kind"], 0) + 1
    for k, v in sorted(by_kind.items()):
        print(f"  {k:<13}: {v}")

    if args.dry_run:
        print("\n(dry run — no files written)")
        return 0

    backup = CANONICAL.with_suffix(".json.bak")
    shutil.copy2(CANONICAL, backup)
    write_pretty(CANONICAL, track)
    print(f"\nwrote {CANONICAL}")
    print(f"backup {backup}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

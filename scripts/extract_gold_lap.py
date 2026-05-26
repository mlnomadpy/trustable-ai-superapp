"""
Extract a frozen Sonoma gold-standard lap from a VBO file.

Writes:
    data/reference/sonoma_gold.json       — per-corner aggregate
    data/reference/sonoma_gold_trace.json — full per-frame trace

Default source file is the 1:47.5 BMW M3 lap in the forza dataset.
Use --vbo to point at a different file (e.g. AJ's pro reference when available).

Usage:
    python3 tools/extract_gold_lap.py
    python3 tools/extract_gold_lap.py --vbo /path/to/lap.vbo
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "simulator"))

from gold_standard import extract_gold_from_vbo, gold_to_dict   # noqa: E402

DEFAULT_VBO = "/Users/tahabsn/Documents/GitHub/forza/data/Sonoma Intermediate - 1_47.5.vbo"
DEFAULT_TRACK = str(ROOT / "data" / "tracks" / "sonoma.json")
GOLD_OUT = ROOT / "data" / "reference" / "sonoma_gold.json"
TRACE_OUT = ROOT / "data" / "reference" / "sonoma_gold_trace.json"


def main():
    """CLI entry point — extract a frozen gold-standard lap from a VBO file."""
    ap = argparse.ArgumentParser()
    ap.add_argument("--vbo", default=DEFAULT_VBO,
                    help=f"VBO file to extract gold lap from (default: {DEFAULT_VBO})")
    ap.add_argument("--track", default=DEFAULT_TRACK,
                    help="Track JSON")
    ap.add_argument("--dry-run", action="store_true",
                    help="Print summary, do not write files")
    args = ap.parse_args()

    print(f"Extracting gold from {args.vbo}")
    print(f"Track: {args.track}")
    gold, trace = extract_gold_from_vbo(args.vbo, args.track)

    print(f"\nGold lap: {gold.lap_time_s:.2f}s, {gold.n_frames} frames, "
          f"{gold.total_distance_m:.0f} m")
    print(f"Corners aggregated: {len(gold.corners)}")
    print()
    print(f"{'corner':<10} {'entry':>7} {'apex':>7} {'exit':>7}  "
          f"{'BP_m':>7} {'peak_bar':>9}  {'time_s':>7}")
    print("-" * 70)
    for name, p in gold.corners.items():
        print(
            f"{name:<10} "
            f"{p.entry_speed_kmh:>7.1f} {p.apex_speed_kmh:>7.1f} {p.exit_speed_kmh:>7.1f}  "
            f"{p.brake_point_m:>7.1f} {p.peak_brake_bar:>9.1f}  {p.corner_time_s:>7.2f}"
        )

    if args.dry_run:
        print("\n(dry run — no files written)")
        return 0

    GOLD_OUT.parent.mkdir(parents=True, exist_ok=True)
    GOLD_OUT.write_text(json.dumps(gold_to_dict(gold), indent=2) + "\n")
    print(f"\nwrote {GOLD_OUT}")

    TRACE_OUT.write_text(json.dumps({
        "track":      gold.track,
        "source_file": gold.source_file,
        "lap_time_s": round(gold.lap_time_s, 3),
        "n_frames":   gold.n_frames,
        "frames":     trace,
    }) + "\n")
    print(f"wrote {TRACE_OUT}  ({len(trace)} frames)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

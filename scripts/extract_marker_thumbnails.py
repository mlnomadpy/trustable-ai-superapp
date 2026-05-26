"""
Extract still images from a synced dashcam video at every Sonoma marker.

Maps each marker's `distance` along the track to the closest VBO frame,
reads that frame's `avitime` (in ms), then runs ffmpeg to cut a 1-frame
JPG out of the matching .mp4 file. Saves to:
    data/markers/sonoma/<marker_id>.jpg

Companion to the marker schema in `data/tracks/sonoma.json`. The Flutter
side renders these thumbnails next to a marker pin on the map UI so the
driver can "preview what to look for" before a lap.

Requires ffmpeg on PATH. Default video is the 1:47.5 forza sample.

Usage:
    python3 tools/extract_marker_thumbnails.py
    python3 tools/extract_marker_thumbnails.py --vbo a.vbo --mp4 a.mp4
    python3 tools/extract_marker_thumbnails.py --dry-run    # print plan, don't extract
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "simulator"))

from pitwall.features.session.vbo_parser import parse_vbo  # noqa: E402

DEFAULT_VBO = "/Users/tahabsn/Documents/GitHub/forza/data/Sonoma Intermediate - 1_47.5.vbo"
DEFAULT_MP4 = "/Users/tahabsn/Documents/GitHub/forza/data/Sonoma Intermediate - 1_47.5.mp4"
TRACK_JSON = ROOT / "data" / "tracks" / "sonoma.json"
OUT_DIR = ROOT / "data" / "markers" / "sonoma"


def find_frame_at_distance(frames, target_m: float, track_len: float = 4258.0):
    """Find the VBO frame closest to a target track-distance.

    Walks all frames and picks the one whose `distance % track_len` is
    closest to `target_m`. Returns None if no frame matches within 30 m.
    """
    best_i = -1
    best_gap = float("inf")
    for i, f in enumerate(frames):
        d = f.distance % track_len if track_len else f.distance
        gap = abs(d - target_m)
        if gap < best_gap:
            best_gap = gap
            best_i = i
    if best_i < 0 or best_gap > 30:
        return None, best_gap
    return best_i, best_gap


def main():
    """CLI entry point — extract dashcam stills at each Sonoma marker distance."""
    ap = argparse.ArgumentParser()
    ap.add_argument("--vbo", default=DEFAULT_VBO)
    ap.add_argument("--mp4", default=DEFAULT_MP4)
    ap.add_argument("--track", default=str(TRACK_JSON))
    ap.add_argument("--out", default=str(OUT_DIR))
    ap.add_argument("--dry-run", action="store_true",
                    help="Print plan, do not invoke ffmpeg")
    ap.add_argument("--force", action="store_true",
                    help="Re-extract even when output JPG already exists")
    args = ap.parse_args()

    if not os.path.exists(args.vbo):
        print(f"ERROR: VBO not found: {args.vbo}")
        return 2
    if not os.path.exists(args.mp4):
        print(f"ERROR: MP4 not found: {args.mp4}")
        return 2

    track = json.loads(Path(args.track).read_text())
    track_len = track.get("track_length_m", 4258)
    markers = track.get("markers", [])
    if not markers:
        print("ERROR: track JSON has no markers — run tools/enrich_sonoma_track.py first")
        return 2

    print(f"VBO: {args.vbo}")
    print(f"MP4: {args.mp4}")
    print(f"Markers: {len(markers)}  (track length {track_len:.0f} m)")
    _, frames = parse_vbo(args.vbo)
    print(f"VBO frames: {len(frames)}")
    if frames:
        print(f"avitime range: {frames[0].avitime:.0f} → {frames[-1].avitime:.0f} ms")

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    have_ffmpeg = shutil.which("ffmpeg") is not None
    if not have_ffmpeg and not args.dry_run:
        print("\nWARNING: ffmpeg not on PATH — falling back to dry-run mode.")
        print("Install with: brew install ffmpeg  (macOS) or pkg install ffmpeg  (Termux)")
        args.dry_run = True

    plan = []
    for m in markers:
        idx, gap = find_frame_at_distance(frames, m["distance"], track_len)
        if idx is None:
            print(f"  SKIP  {m['id']}  (no frame within 30 m of distance={m['distance']})")
            continue
        avitime_ms = frames[idx].avitime
        avitime_s = avitime_ms / 1000.0
        plan.append({
            "marker_id":  m["id"],
            "label":      m["label"],
            "distance_m": m["distance"],
            "frame_idx":  idx,
            "frame_gap_m": round(gap, 2),
            "avitime_s":  round(avitime_s, 3),
            "out_path":   str(out_dir / f"{m['id']}.jpg"),
        })

    print(f"\nplanned: {len(plan)} thumbnails")
    print(f"{'marker':<28} {'frame':>6}  {'gap':>6}  {'avitime_s':>10}  out")
    print("-" * 100)
    for p in plan:
        print(f"  {p['marker_id']:<26} {p['frame_idx']:>6}  "
              f"{p['frame_gap_m']:>4.1f}m  {p['avitime_s']:>9.3f}  "
              f"{p['out_path']}")

    if args.dry_run:
        print(f"\n(dry run — no JPGs written; install ffmpeg to extract)")
        manifest = out_dir / "manifest.json"
        manifest.write_text(json.dumps({
            "source_vbo": args.vbo, "source_mp4": args.mp4,
            "track_length_m": track_len, "thumbnails": plan,
        }, indent=2) + "\n")
        print(f"wrote manifest {manifest}")
        return 0

    n_ok = n_skip = 0
    for p in plan:
        out_path = Path(p["out_path"])
        if out_path.exists() and not args.force:
            n_skip += 1
            continue
        cmd = [
            "ffmpeg", "-y", "-loglevel", "error",
            "-ss", str(p["avitime_s"]),
            "-i", args.mp4,
            "-frames:v", "1",
            "-q:v", "2",
            str(out_path),
        ]
        try:
            subprocess.run(cmd, check=True, timeout=30)
            n_ok += 1
            print(f"  ✓  {out_path.name}")
        except Exception as e:
            print(f"  ✗  {out_path.name}  {e}")

    manifest = out_dir / "manifest.json"
    manifest.write_text(json.dumps({
        "source_vbo": args.vbo, "source_mp4": args.mp4,
        "track_length_m": track_len, "thumbnails": plan,
        "n_extracted": n_ok, "n_existing": n_skip,
    }, indent=2) + "\n")

    print(f"\nextracted {n_ok} thumbnails ({n_skip} pre-existing)")
    print(f"manifest: {manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

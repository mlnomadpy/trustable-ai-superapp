"""
Bulk-import every Sonoma VBO from a directory into the bridge's DuckDB.

Walks a directory of `.vbo` files, filters to those whose GPS centroid
matches Sonoma (tunable by `--centroid-radius-km` against the track's
S/F lat/lon), and ingests each file as one session into the
`tools/pitwall_sessions.duckdb` database.

Each imported session gets:
- A row in `sessions` (driver_id derived from filename, track="Sonoma Raceway")
- One row per VBO frame in `telemetry`

After running, the bridge endpoints `/sessions`, `/session/<id>`,
`/coach/debrief` work against the imported data exactly as if it had
streamed in live.

Usage:
    pip install duckdb
    python3 tools/bulk_import_sonoma_vbos.py /path/to/forza/data
    python3 tools/bulk_import_sonoma_vbos.py /path/to/forza/data --dry-run
    python3 tools/bulk_import_sonoma_vbos.py /path/to/forza/data --driver "AJ"
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
sys.path.insert(0, str(ROOT / "src"))

from pitwall.features.session.vbo_parser import parse_vbo  # noqa: E402

DEFAULT_TRACK = ROOT / "data" / "tracks" / "sonoma.json"
DEFAULT_DB = ROOT / "tools" / "pitwall_sessions.duckdb"

EARTH_R = 6_371_000.0


def _haversine_m(a_lat, a_lon, b_lat, b_lon):
    p1, p2 = math.radians(a_lat), math.radians(b_lat)
    dlat = math.radians(b_lat - a_lat)
    dlon = math.radians(b_lon - a_lon)
    h = math.sin(dlat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_R * math.asin(math.sqrt(h))


def _ensure_schema(conn):
    """Replicate the bridge's schema initialisation."""
    conn.execute("""
        CREATE SEQUENCE IF NOT EXISTS sessions_id_seq;
        CREATE TABLE IF NOT EXISTS sessions (
            session_id    VARCHAR PRIMARY KEY,
            driver        VARCHAR,
            driver_level  VARCHAR,
            track         VARCHAR,
            car           VARCHAR,
            started_at    TIMESTAMP DEFAULT now(),
            ended_at      TIMESTAMP,
            note          VARCHAR
        );
        CREATE SEQUENCE IF NOT EXISTS laps_id_seq;
        CREATE TABLE IF NOT EXISTS laps (
            id            INTEGER PRIMARY KEY DEFAULT nextval('laps_id_seq'),
            session_id    VARCHAR,
            lap_number    INTEGER,
            lap_time_s    DOUBLE,
            best_sector   DOUBLE,
            avg_speed_kmh DOUBLE,
            max_combo_g   DOUBLE,
            coast_pct     DOUBLE,
            recorded_at   TIMESTAMP DEFAULT now()
        );
        CREATE TABLE IF NOT EXISTS telemetry (
            session_id   VARCHAR,
            frame_idx    INTEGER,
            timestamp    DOUBLE,
            distance_m   DOUBLE,
            speed_ms     DOUBLE,
            g_lat        DOUBLE,
            g_long       DOUBLE,
            combo_g      DOUBLE,
            brake_bar    DOUBLE,
            throttle_pct DOUBLE,
            steering_deg DOUBLE,
            rpm          DOUBLE,
            lat          DOUBLE,
            lon          DOUBLE
        );
        CREATE INDEX IF NOT EXISTS idx_telemetry_session ON telemetry(session_id, frame_idx);
    """)


def _session_id_from_filename(path: Path) -> str:
    """Stable session_id derived from the filename so re-running this tool
    is idempotent: import-existing → 409 conflict, skip."""
    stem = path.stem.lower().replace(" ", "-")
    return f"sonoma-import-{stem}"


def _is_sonoma_file(frames, sf_lat, sf_lon, radius_km) -> bool:
    if not frames:
        return False
    lats = [f.lat for f in frames if f.lat]
    lons = [f.lon for f in frames if f.lon]
    if not lats:
        return False
    c_lat = statistics.median(lats)
    c_lon = statistics.median(lons)
    return _haversine_m(c_lat, c_lon, sf_lat, sf_lon) / 1000.0 <= radius_km


def main():
    """CLI entry point — bulk-import Sonoma VBO files into pitwall's DuckDB."""
    ap = argparse.ArgumentParser()
    ap.add_argument("vbo_dir", help="Directory containing .vbo files")
    ap.add_argument("--track", default=str(DEFAULT_TRACK))
    ap.add_argument("--db", default=str(DEFAULT_DB))
    ap.add_argument("--driver", default="dataset",
                    help="Driver ID for imported sessions (one or many)")
    ap.add_argument("--driver-level", default="intermediate",
                    choices=["beginner", "intermediate", "pro"])
    ap.add_argument("--centroid-radius-km", type=float, default=10.0)
    ap.add_argument("--dry-run", action="store_true",
                    help="Print plan, do not write to DB")
    ap.add_argument("--force", action="store_true",
                    help="Re-import sessions that already exist (delete first)")
    args = ap.parse_args()

    try:
        import duckdb
    except ImportError:
        print("ERROR: duckdb not installed. pip install duckdb")
        return 2

    track = json.loads(Path(args.track).read_text())
    sf = track["start_finish"]
    sf_lat, sf_lon = float(sf["lat"]), float(sf["lon"])
    print(f"Track:  {track.get('name')}  S/F=({sf_lat:.5f}, {sf_lon:.5f})")

    vbo_dir = Path(args.vbo_dir).expanduser()
    vbos = sorted(vbo_dir.glob("*.vbo"))
    print(f"VBOs:   {len(vbos)} in {vbo_dir}")

    if not args.dry_run:
        conn = duckdb.connect(args.db)
        _ensure_schema(conn)
    else:
        conn = None

    n_imported = n_skipped_other_track = n_skipped_existing = n_failed = 0
    total_frames = 0

    for path in vbos:
        try:
            meta, frames = parse_vbo(path)
        except Exception as e:
            print(f"  FAIL  {path.name}  {e}")
            n_failed += 1
            continue

        if not _is_sonoma_file(frames, sf_lat, sf_lon, args.centroid_radius_km):
            n_skipped_other_track += 1
            continue

        sid = _session_id_from_filename(path)

        if not args.dry_run:
            existing = conn.execute(
                "SELECT count(*) FROM telemetry WHERE session_id = ?", [sid],
            ).fetchone()[0]
            if existing > 0 and not args.force:
                n_skipped_existing += 1
                continue
            if existing > 0 and args.force:
                conn.execute("DELETE FROM telemetry WHERE session_id = ?", [sid])
                conn.execute("DELETE FROM sessions WHERE session_id = ?", [sid])

            conn.execute(
                "INSERT INTO sessions (session_id, driver, driver_level, "
                "track, car, note) VALUES (?, ?, ?, ?, ?, ?)",
                [sid, args.driver, args.driver_level,
                 track.get("name", "Sonoma Raceway"),
                 meta.device_type or "", f"bulk-import: {path.name}"],
            )
            rows = [
                (sid, i, f.timestamp, f.distance, f.speed,
                 f.g_lat, f.g_long, f.combo_g, f.brake_pressure,
                 f.throttle, f.steering, f.rpm, f.lat, f.lon)
                for i, f in enumerate(frames)
            ]
            conn.executemany(
                "INSERT INTO telemetry VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                rows,
            )

        n_imported += 1
        total_frames += len(frames)
        if n_imported <= 10:
            print(f"  ✓  {path.name:<46}  {len(frames):>5} frames  "
                  f"{(frames[-1].timestamp - frames[0].timestamp) / 60:>5.1f} min")

    if not args.dry_run:
        conn.close()

    print()
    print("=" * 60)
    print(f"  Imported:        {n_imported}")
    print(f"  Total frames:    {total_frames:,}")
    print(f"  Skipped (other): {n_skipped_other_track}")
    print(f"  Skipped (exist): {n_skipped_existing}")
    print(f"  Failed:          {n_failed}")
    if args.dry_run:
        print("  (dry run — nothing written)")
    else:
        print(f"  DB:              {args.db}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

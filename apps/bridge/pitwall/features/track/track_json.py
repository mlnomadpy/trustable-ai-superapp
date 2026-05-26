"""pitwall.features.track.track_json — read data/tracks/<id>.json + corners.

Pure domain logic with no Flask dependency. Can be unit-tested independently.
"""

import json
import os

from pitwall.state import SIM_DIR


def load_track_json(track_id: str) -> dict | None:
    """Load data/tracks/<id>.json or return None."""
    path = os.path.abspath(os.path.join(
        SIM_DIR, "..", "..", "data", "tracks", f"{track_id}.json",
    ))
    if not os.path.exists(path):
        return None
    try:
        with open(path) as fh:
            return json.load(fh)
    except Exception:
        return None


def corner_bounds_from_track(track: dict) -> list:
    """Return [{name, entry_m, apex_m, exit_m}] for each corner in track JSON."""
    out: list = []
    for c in (track or {}).get("corners", []):
        try:
            out.append({
                "name":    c["name"],
                "entry_m": float(c["entry"]["distance"]),
                "apex_m":  float(c["apex"]["distance"]),
                "exit_m":  float(c["exit"]["distance"]),
            })
        except (KeyError, TypeError, ValueError):
            continue
    return out

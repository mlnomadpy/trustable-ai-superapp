"""bridge.bp_cars — Blueprint: GET /cars (real per-car YAML inventory).

Scans `data/cars/*.yaml` and returns parsed identity + CAN-pipeline facts
so the PWA can render real car-setup info instead of mocked sliders.

The currently-loaded config (per `--can-car-config`) is flagged via
`loaded: true`; everything else is just available.

Intentionally read-only: no setup-tracking persistence is exposed here.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from flask import Blueprint, jsonify

try:
    import yaml
except ImportError:  # pragma: no cover — yaml is a runtime dep
    yaml = None  # type: ignore[assignment]

from pitwall.state import state

bp = Blueprint("cars", __name__)


# Repo root: src/pitwall/features/bp_cars.py → up 3 = repo root
_REPO_ROOT = Path(__file__).resolve().parents[3]
_CARS_DIR = _REPO_ROOT / "data" / "cars"


def _channels_from_frames(frames: dict) -> list[dict[str, Any]]:
    """Flatten per-frame channel lists into a single ordered channel inventory."""
    out: list[dict[str, Any]] = []
    if not isinstance(frames, dict):
        return out
    for fid, fdef in frames.items():
        if not isinstance(fdef, dict):
            continue
        for ch in fdef.get("channels", []) or []:
            out.append({
                "name": str(ch),
                "frame_id": str(fid),
                "rate_hz": fdef.get("rate_hz"),
                "role": fdef.get("role") or "",
            })
    return out


def _parse_car_yaml(path: Path, loaded: bool) -> dict[str, Any]:
    """Parse one car YAML into the PWA-facing shape."""
    if yaml is None:
        return {
            "id": path.stem,
            "path": str(path),
            "loaded": loaded,
            "error": "pyyaml not available on bridge host",
        }
    try:
        with path.open("r", encoding="utf-8") as fh:
            doc = yaml.safe_load(fh) or {}
    except (OSError, yaml.YAMLError) as exc:
        return {
            "id": path.stem,
            "path": str(path),
            "loaded": loaded,
            "error": f"{type(exc).__name__}: {exc}",
        }

    car = doc.get("car", {}) or {}
    dash = doc.get("dash_logger", {}) or {}
    can_bus = doc.get("can_bus", {}) or {}
    frames = doc.get("frames", {}) or {}
    channels = _channels_from_frames(frames)

    return {
        "id": path.stem,
        "path": str(path),
        "loaded": loaded,
        "make": car.get("make") or "",
        "model": car.get("model") or "",
        "chassis": car.get("chassis") or "",
        "year": car.get("year"),
        "engine": car.get("engine") or "",
        "notes": (car.get("notes") or "").strip(),
        "dash_logger": {
            "make": dash.get("make") or "",
            "model": dash.get("model") or "",
            "protocol": dash.get("protocol") or "",
            "total_frames": dash.get("total_frames"),
            "total_channels": dash.get("total_channels"),
        },
        "can_bus": {
            "name": can_bus.get("name") or "",
            "bitrate_bps": can_bus.get("bitrate_bps"),
            "frame_format": can_bus.get("frame_format") or "",
            "id_width": can_bus.get("id_width"),
        },
        "frame_count": len(frames),
        "channel_count": len(channels),
        "channels": channels,
    }


@bp.route("/cars", methods=["GET"])
def list_cars():
    """Return every YAML in data/cars/ with the currently-loaded one flagged.

    Response shape:
        {
            "cars": [<parsed-yaml>...],
            "loaded_id": "<id-or-empty>",
            "cars_dir": "<abs path>"
        }
    """
    if not _CARS_DIR.exists():
        return jsonify({
            "cars": [],
            "loaded_id": "",
            "cars_dir": str(_CARS_DIR),
            "error": "cars directory missing",
        }), 404

    loaded_path = getattr(state, "car_config_path", "") or ""
    loaded_stem = Path(loaded_path).stem if loaded_path else ""

    files = sorted(_CARS_DIR.glob("*.yaml")) + sorted(_CARS_DIR.glob("*.yml"))
    cars = [_parse_car_yaml(p, loaded=(p.stem == loaded_stem)) for p in files]
    # If --can-car-config pointed outside data/cars/, surface that too so
    # the PWA can warn rather than silently show "loaded: none".
    return jsonify({
        "cars": cars,
        "loaded_id": loaded_stem if any(c.get("loaded") for c in cars) else "",
        "loaded_path": loaded_path,
        "cars_dir": str(_CARS_DIR),
    })

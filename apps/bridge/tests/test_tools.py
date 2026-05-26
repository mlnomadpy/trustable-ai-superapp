"""Unit tests for the helper functions inside `scripts/` CLI scripts."""
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))

import enrich_sonoma_track as enrich_mod
import best_sonoma_lap as ranker
import import_sonoma_real_gps as gps_imp
import extract_marker_thumbnails as thumbs
import bulk_import_sonoma_vbos as bulk


# ─── enrich_sonoma_track ──────────────────────────────────────────────────────


def test_sample_reference_line_empty():
    assert enrich_mod._sample_reference_line([], 100) == (0.0, 0.0)


def test_sample_reference_line_interpolates_midpoint():
    rl = [
        {"distance": 0,   "lat": 23.49, "lon": -73.78},
        {"distance": 100, "lat": 23.50, "lon": -73.79},
    ]
    lat, lon = enrich_mod._sample_reference_line(rl, 50)
    assert abs(lat - 23.495) < 0.001
    assert abs(lon - (-73.785)) < 0.001


def test_sample_reference_line_wraps_modulo():
    """Closed-loop track: a distance past the last sample wraps modulo
    track_length and returns the interpolated lat/lon at the wrapped position."""
    rl = [
        {"distance": 0,   "lat": 23.49, "lon": -73.78},
        {"distance": 100, "lat": 23.50, "lon": -73.79},
    ]
    # 999 % 100 = 99 → very close to the last sample
    lat, lon = enrich_mod._sample_reference_line(rl, 999)
    assert abs(lat - 23.4999) < 0.001
    assert abs(lon - (-73.7899)) < 0.001


def test_enrich_populates_known_corner():
    """The ENRICHMENT dict has Turn 11 — verify enrich populates it."""
    track = {
        "track_length_m": 4258,
        "corners": [{
            "name": "Turn 11", "number": 11, "direction": "right", "severity": 3,
            "entry": {"distance": 4100, "lat": 0, "lon": 0},
            "apex":  {"distance": 4158, "lat": 0, "lon": 0},
            "exit":  {"distance": 4256, "lat": 0, "lon": 0},
        }],
        "reference_line": [],
    }
    out = enrich_mod.enrich(track)
    c = out["corners"][0]
    assert c["coaching_tip"]
    assert c["nicknames"]
    assert c["markers"]
    assert any("bump" in m["label"] for m in c["markers"])


# ─── best_sonoma_lap ──────────────────────────────────────────────────────────


def test_haversine_one_degree_at_equator():
    """1° longitude at the equator is approximately 111000 m."""
    d = ranker.haversine_m(0, 0, 0, 1)
    assert abs(d - 111000) < 2000


def test_haversine_zero_distance():
    assert ranker.haversine_m(38.16, -122.45, 38.16, -122.45) == 0


def test_latlon_to_local_xy_origin():
    x, y = ranker.latlon_to_local_xy(38.16, -122.45, 38.16, -122.45)
    assert abs(x) < 0.01
    assert abs(y) < 0.01


def test_signed_perp_distance_sign_changes_with_position():
    """Heading=0 (north): a point north of S/F → positive; south → negative."""
    sf = (38.16, -122.45)
    pos = ranker.signed_perp_distance_to_sf_line(38.17, -122.45, sf[0], sf[1], 0)
    neg = ranker.signed_perp_distance_to_sf_line(38.15, -122.45, sf[0], sf[1], 0)
    assert pos > 0
    assert neg < 0


def test_fmt_lap_basic():
    assert ranker.fmt_lap(107.5) == "1:47.50"


def test_fmt_lap_zero_returns_dash():
    assert "—" in ranker.fmt_lap(0)


def test_session_centroid_returns_median(make_frame_fn):
    frames = [
        make_frame_fn(t=0, lat=23.49, lon=-73.78),
        make_frame_fn(t=0.1, lat=23.50, lon=-73.79),
        make_frame_fn(t=0.2, lat=23.51, lon=-73.80),
    ]
    lat, lon = ranker.session_centroid(frames)
    assert abs(lat - 23.50) < 0.001
    assert abs(lon - (-73.79)) < 0.001


def test_detect_laps_empty():
    assert ranker.detect_laps([], 0, 0, 0) == []


# ─── import_sonoma_real_gps ──────────────────────────────────────────────────


def test_gps_import_haversine():
    d = gps_imp.haversine_m((0, 0), (0, 1))
    assert abs(d - 111000) < 2000


def test_resample_loop_produces_correct_length():
    # ~3 points spanning a small ~150m perimeter; step 10m → ~15 samples
    loop = [(0, 0), (0.0005, 0.0005), (0.0010, 0.0010), (0, 0)]
    samples = gps_imp.resample_loop(loop, step_m=20)
    assert len(samples) > 5


def test_map_fractional_at_zero():
    samples = [
        {"distance": 0,   "lat": 38.0, "lon": -122.0},
        {"distance": 100, "lat": 38.1, "lon": -122.1},
    ]
    lat, lon = gps_imp.map_fractional(samples, anon_distance=0, anon_total=4258)
    assert abs(lat - 38.0) < 0.001
    assert abs(lon - (-122.0)) < 0.001


def test_map_fractional_at_full_loop():
    samples = [
        {"distance": 0,   "lat": 38.0, "lon": -122.0},
        {"distance": 100, "lat": 38.1, "lon": -122.1},
    ]
    # anon_distance == anon_total → fraction wraps to 0 (modulo)
    lat, lon = gps_imp.map_fractional(samples, anon_distance=4258, anon_total=4258)
    assert abs(lat - 38.0) < 0.001


# ─── extract_marker_thumbnails ───────────────────────────────────────────────


def test_find_frame_at_distance_picks_closest(make_frame_fn):
    frames = [
        make_frame_fn(t=0,   distance=0),
        make_frame_fn(t=0.1, distance=50),
        make_frame_fn(t=0.2, distance=100),
        make_frame_fn(t=0.3, distance=150),
    ]
    idx, gap = thumbs.find_frame_at_distance(frames, 120, track_len=4258)
    assert idx == 2  # distance 100 is closest to target 120
    assert gap == 20


def test_find_frame_at_distance_returns_none_when_far(make_frame_fn):
    frames = [
        make_frame_fn(t=0, distance=0),
        make_frame_fn(t=0.1, distance=50),
    ]
    # Target 1000m, all frames are < 100m → gap > 30m → return None
    idx, gap = thumbs.find_frame_at_distance(frames, 1000, track_len=4258)
    assert idx is None
    assert gap > 30


# ─── bulk_import_sonoma_vbos ─────────────────────────────────────────────────


def test_session_id_from_filename():
    sid = bulk._session_id_from_filename(Path("VBOX0229.vbo"))
    assert sid.startswith("sonoma-import-")
    assert "vbox0229" in sid


def test_session_id_from_filename_handles_spaces():
    sid = bulk._session_id_from_filename(Path("Sonoma Intermediate - 1_47.5.vbo"))
    assert sid.startswith("sonoma-import-")
    assert " " not in sid


def test_bulk_haversine_zero():
    assert bulk._haversine_m(38.0, -122.0, 38.0, -122.0) == 0

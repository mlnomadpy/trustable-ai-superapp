"""Unit tests for src/simulator/vbo_parser.py."""
from pitwall.features.session.vbo_parser import parse_vbo, parse_vbo_coord, TelemetryFrame


def test_parse_vbo_coord_decimal():
    """VBO format DDDMM.MMMMM → decimal degrees."""
    # 38°09.6912' = 3809.6912 → 38.16152
    assert abs(parse_vbo_coord(3809.6912) - 38.16152) < 1e-4


def test_parse_vbo_coord_zero():
    assert parse_vbo_coord(0.0) == 0.0


def test_parse_vbo_real_file(forza_vbo_path):
    meta, frames = parse_vbo(forza_vbo_path)
    assert len(frames) > 1000
    f = frames[0]
    assert isinstance(f, TelemetryFrame)
    # Sanity: the dataset's anonymised frame
    assert 23 < abs(f.lat) < 24
    assert 73 < abs(f.lon) < 74


def test_parse_vbo_extracts_avitime(forza_vbo_path):
    """Regression: avitime field added 2026-04-28 for video sync."""
    _, frames = parse_vbo(forza_vbo_path)
    assert frames[0].avitime > 0
    # avitime should be monotonically increasing
    avis = [f.avitime for f in frames[:100]]
    assert all(b >= a for a, b in zip(avis, avis[1:]))


def test_parse_vbo_distance_grows(forza_vbo_path):
    """Cumulative distance should be monotonically non-decreasing."""
    _, frames = parse_vbo(forza_vbo_path)
    ds = [f.distance for f in frames[:200]]
    assert all(b >= a - 0.5 for a, b in zip(ds, ds[1:]))   # tolerate GPS jitter


def test_parse_vbo_metadata_columns(forza_vbo_path):
    meta, _ = parse_vbo(forza_vbo_path)
    assert "time" in meta.columns
    assert "velocity" in meta.columns

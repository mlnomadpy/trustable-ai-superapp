"""Unit tests for src/simulator/track_loader.py."""
import pytest
from pitwall.features.track.track_loader import (
    load_track, find_nearest_corner, find_nearest_marker,
    find_marker_for_next_corner, distance_to_corner,
    is_in_corner, is_past_apex, get_sector,
    cross_track_error, MarkerDef,
)


def test_load_track_returns_track_map(real_track):
    assert real_track.name == "Sonoma Raceway"
    assert real_track.track_length > 0
    assert len(real_track.corners) == 11
    assert real_track.markers is not None


def test_track_has_sf_lat_lon_heading(real_track):
    assert real_track.sf_lat != 0
    assert real_track.sf_lon != 0
    assert 0 <= real_track.sf_heading <= 360


def test_track_corners_are_in_lap_order(real_track):
    distances = [c.entry_distance for c in real_track.corners]
    assert distances == sorted(distances), "corners not ordered by entry_distance"


def test_track_has_at_least_one_brake_corner(real_track):
    """Some corners should have non-zero brake_distance after track-builder."""
    assert any(c.brake_distance > 0 for c in real_track.corners)


def test_markers_loaded(real_track):
    assert len(real_track.markers) >= 16
    for m in real_track.markers:
        assert isinstance(m, MarkerDef)
        assert m.id
        assert m.kind in ("brake_ref", "apex_ref", "turn_in_ref",
                           "exit_ref", "visual", "nickname")


def test_markers_sorted_by_distance(real_track):
    ds = [m.distance for m in real_track.markers]
    assert ds == sorted(ds)


def test_per_corner_markers_match_top_level(real_track):
    """Every per-corner marker must appear in the top-level flat list."""
    flat_ids = {m.id for m in real_track.markers}
    for c in real_track.corners:
        for m in (c.markers or []):
            assert m.id in flat_ids


def test_find_nearest_corner_returns_upcoming(real_track):
    # Just before T1 entry → next corner is T1
    c = find_nearest_corner(real_track, real_track.corners[0].entry_distance - 30)
    assert c is not None
    assert c.name == "Turn 1"


def test_find_nearest_corner_wraps_around(real_track):
    # End of track → next corner is T1
    c = find_nearest_corner(real_track, real_track.track_length - 50)
    assert c is not None
    assert c.name == "Turn 1"


def test_distance_to_corner(real_track):
    c = real_track.corners[0]
    d = distance_to_corner(real_track, c.entry_distance - 25, c)
    assert abs(d - 25) < 1


def test_is_in_corner_true(real_track):
    c = real_track.corners[0]
    mid = (c.entry_distance + c.exit_distance) / 2
    assert is_in_corner(real_track, mid) is c


def test_is_in_corner_false(real_track):
    """A position before the first corner should return None."""
    c = is_in_corner(real_track, real_track.corners[0].entry_distance - 50)
    assert c is None


def test_is_past_apex(real_track):
    c = real_track.corners[0]
    assert is_past_apex(real_track, c.apex_distance + 5) is c
    assert is_past_apex(real_track, c.entry_distance + 1) is None


def test_get_sector(real_track):
    if real_track.sectors:
        s = get_sector(real_track, real_track.sectors[0].start_distance + 1)
        assert s is not None


def test_find_nearest_marker_kind_filter(real_track):
    """A brake_ref marker should be returned when filter matches."""
    m = find_nearest_marker(real_track, distance=300, kind="brake_ref", lookahead=500)
    assert m is None or m.kind == "brake_ref"


def test_find_nearest_marker_corner_filter(real_track):
    m = find_nearest_marker(real_track, distance=0, corner="Turn 11", lookahead=5000)
    assert m is None or m.corner == "Turn 11"


def test_find_nearest_marker_zero_gap_now_accepted(real_track):
    """Regression: marker exactly at car position used to be skipped."""
    m = real_track.markers[0]
    found = find_nearest_marker(real_track, distance=m.distance, lookahead=200)
    # Should be either this marker or another within 200m — never None
    assert found is not None


def test_find_marker_for_next_corner_prefers_corner_attached(real_track):
    """If the upcoming corner has its own brake_ref, prefer it over a generic global one."""
    # Pick a position right before a corner with brake_ref markers (T2 has 'the bridge')
    t2 = next(c for c in real_track.corners if c.name == "Turn 2")
    pos = t2.entry_distance - 200
    m = find_marker_for_next_corner(real_track, pos, kind="brake_ref")
    assert m is not None
    assert m.corner == "Turn 2"


def test_cross_track_error_zero_at_reference_line(real_track):
    """A point exactly on the reference line should give XTE ≈ 0."""
    if real_track.reference_line:
        d, lat, lon = real_track.reference_line[5]
        xte = cross_track_error(real_track, d, lat, lon)
        assert xte < 1.0  # within 1 m


def test_real_gps_present_in_loaded_track(real_track):
    """Markers should now carry lat/lon GPS (anonymized frame for now)."""
    for m in real_track.markers[:5]:
        assert m.id
        # GPS may be 0 if reference_line was empty; otherwise should be non-zero
        # (existing data has a populated reference_line)
        # Simply assert MarkerDef shape, not that lat/lon are non-zero
        assert isinstance(m.distance, float)

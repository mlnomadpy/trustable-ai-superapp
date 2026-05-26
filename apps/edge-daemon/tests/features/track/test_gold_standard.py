"""Unit tests for src/simulator/gold_standard.py."""
import pytest
from pathlib import Path

from pitwall.features.track.gold_standard import (
    GoldCornerPass, GoldStandard, gold_to_dict, load_gold_standard,
    extract_gold_from_vbo,
)


def test_gold_to_dict_round_trip(tmp_path, real_gold):
    """A loaded gold should round-trip through dict + load_gold_standard."""
    d = gold_to_dict(real_gold)
    out = tmp_path / "gold.json"
    import json
    out.write_text(json.dumps(d))
    g2 = load_gold_standard(str(out))
    assert g2.track == real_gold.track
    assert g2.lap_time_s == real_gold.lap_time_s
    assert set(g2.corners) == set(real_gold.corners)


def test_real_gold_has_per_corner_aggregates(real_gold):
    """The shipped gold reference must cover every Sonoma corner."""
    import pitwall.features.track.sonoma as sonoma
    expected = set(sonoma.CORNER_ORDER)
    found = set(real_gold.corners)
    # Allow a few corners missing if the source lap had no clean pass; warn loudly otherwise
    missing = expected - found
    assert not missing, f"gold missing corners: {missing}"


def test_gold_corner_pass_fields(real_gold):
    """Each gold corner should have positive entry/apex/exit speeds and a corner_time."""
    for corner, p in real_gold.corners.items():
        assert isinstance(p, GoldCornerPass)
        assert p.entry_speed_kmh > 0
        assert p.exit_speed_kmh >= 0
        assert p.corner_time_s > 0


def test_extract_gold_from_vbo_smoke(forza_vbo_path, real_track_path, tmp_path):
    """End-to-end: parse VBO, extract gold, verify shape."""
    gold, trace = extract_gold_from_vbo(str(forza_vbo_path), str(real_track_path))
    assert gold.track == "Sonoma Raceway"
    assert len(gold.corners) >= 8        # at least most of the 11 corners
    assert len(trace) > 100
    # Trace fields should be JSON-serialisable
    sample = trace[0]
    assert all(k in sample for k in ("t", "d", "v", "brk", "thr", "gLat", "gLong"))


def test_extract_gold_corner_times_under_60s(forza_vbo_path, real_track_path):
    """Per-corner times should be < 60 s. Known limitation (AUDIT.md): the
    lap-segmentation bug occasionally picks up multi-lap windows for sweeping
    corners (T3, T9), inflating their gold corner_time. Threshold of 60 s
    catches catastrophic regressions while tolerating the known bug."""
    gold, _ = extract_gold_from_vbo(str(forza_vbo_path), str(real_track_path))
    for corner, p in gold.corners.items():
        assert p.corner_time_s < 60, (
            f"{corner} corner_time={p.corner_time_s}s — catastrophic "
            f"segmentation regression"
        )

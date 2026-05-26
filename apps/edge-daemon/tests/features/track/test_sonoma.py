"""Unit tests for src/simulator/sonoma.py — hardcoded constants module."""
import pitwall.features.track.sonoma as sonoma


def test_corner_order_has_11_corners():
    assert len(sonoma.CORNER_ORDER) == 11
    assert sonoma.CORNER_ORDER[0] == "Turn 1"
    assert sonoma.CORNER_ORDER[-1] == "Turn 11"


def test_lap_time_leverage_sums_to_one():
    """LAP_TIME_LEVERAGE drives weighted-grade math; drift here breaks scoring silently."""
    assert abs(sum(sonoma.LAP_TIME_LEVERAGE.values()) - 1.0) < 1e-6


def test_lap_time_leverage_covers_every_corner():
    """Every corner in CORNER_ORDER must have a leverage weight, no extras."""
    assert set(sonoma.LAP_TIME_LEVERAGE) == set(sonoma.CORNER_ORDER)


def test_t10_is_highest_leverage_corner():
    """T10 is fastest + biggest brake-zone leverage at Sonoma."""
    weights = sonoma.LAP_TIME_LEVERAGE
    assert weights["Turn 10"] == max(weights.values())


def test_corner_tips_cover_every_corner():
    assert set(sonoma.CORNER_TIPS) == set(sonoma.CORNER_ORDER)


def test_weather_phase_for_morning():
    p = sonoma.weather_phase_for_hour(7)
    assert p.id == "morning_fog"


def test_weather_phase_for_noon():
    p = sonoma.weather_phase_for_hour(13)
    assert p.id == "peak_grip"


def test_weather_phase_for_late_afternoon():
    p = sonoma.weather_phase_for_hour(16)
    assert p.id == "late_session"


def test_weather_phase_at_boundary_hour_18():
    """Regression: hour 18 used to fall through the loop and return peak_grip default."""
    p = sonoma.weather_phase_for_hour(18)
    assert p.id == "late_session"


def test_weather_phase_at_evening():
    p = sonoma.weather_phase_for_hour(20)
    # 20 is past late_session.end_hour=18 — folds into late_session
    assert p.id == "late_session"


def test_weather_phase_for_unknown_hour():
    p = sonoma.weather_phase_for_hour(3)  # 3 AM
    # Pre-morning_fog hours fall back to peak_grip default
    assert p.id == "peak_grip"


def test_danger_zones_have_required_fields():
    for d in sonoma.DANGER_ZONES:
        assert d.id and d.description
        assert d.severity in ("low", "medium", "high")
        assert d.start_m < d.end_m


def test_sectors_cover_full_track():
    sectors = sonoma.SECTORS
    assert sectors[0].start_m == 0
    assert sectors[-1].end_m == sonoma.TRACK_LENGTH_M
    for a, b in zip(sectors, sectors[1:]):
        assert a.end_m == b.start_m   # contiguous


def test_real_gps_constants_are_in_sonoma_california():
    """Real Sonoma is at 38.16°N, -122.45°W. Sanity-check the constants."""
    assert 38 < sonoma.TRACK_CENTROID_LAT < 39
    assert -123 < sonoma.TRACK_CENTROID_LON < -122
    assert 38 < sonoma.SF_LAT < 39


def test_system_prompt_lore_mentions_canonical_landmarks():
    lore = sonoma.SYSTEM_PROMPT_LORE
    for landmark in ["bridge", "Carousel", "Calamity Corner",
                     "bump", "Toyota sign", "tire stack", "300 board"]:
        assert landmark in lore, f"system prompt missing canonical landmark: {landmark}"


def test_system_prompt_lore_includes_repave_fact():
    """Feb 2024 repave is a load-bearing fact for gold-standard interpretation."""
    assert "2024" in sonoma.SYSTEM_PROMPT_LORE
    assert "repaved" in sonoma.SYSTEM_PROMPT_LORE.lower()


def test_trod_voice_is_non_empty():
    assert len(sonoma.TROD_VOICE) >= 5
    assert any("Distance is king" in v for v in sonoma.TROD_VOICE)


def test_surface_history_is_documented():
    sh = sonoma.SURFACE_HISTORY
    assert sh["last_repave_iso"] == "2024-02"
    assert sh["repave_lap_time_drop_s"] > 0

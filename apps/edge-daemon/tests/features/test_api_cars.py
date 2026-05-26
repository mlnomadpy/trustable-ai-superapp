"""Tests for GET /cars — real per-car YAML inventory."""


def test_cars_endpoint_returns_real_yaml(client):
    r = client.get("/cars")
    assert r.status_code == 200
    body = r.get_json()
    assert "cars" in body
    assert "loaded_id" in body
    assert "cars_dir" in body
    assert isinstance(body["cars"], list)
    assert len(body["cars"]) >= 1, "expected at least bmw_e46_m3.yaml in data/cars"


def test_cars_endpoint_shape_matches_yaml(client):
    r = client.get("/cars")
    body = r.get_json()
    car = next((c for c in body["cars"] if c["id"] == "bmw_e46_m3"), None)
    assert car is not None, "bmw_e46_m3 entry expected"

    # Identity fields sourced from the real YAML
    assert car["make"] == "BMW"
    assert car["model"] == "M3"
    assert car["chassis"] == "E46"
    assert car["year"] == 2003
    assert "S54" in car["engine"]

    # Pipeline summary
    assert car["frame_count"] > 0
    assert car["channel_count"] > 0
    assert car["can_bus"]["bitrate_bps"] == 1_000_000
    assert car["dash_logger"]["make"] == "AiM"

    # Channels are real, ordered, and attributed to a frame
    assert isinstance(car["channels"], list)
    first = car["channels"][0]
    for key in ("name", "frame_id", "rate_hz", "role"):
        assert key in first
